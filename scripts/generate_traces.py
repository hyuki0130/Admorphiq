"""Dev-time training-data generator for a frame->action policy (DriesSmit-style).

Goal
----
Produce EFFICIENT solution trajectories across the 25 ARC-AGI-3 public games so a
CNN action predictor can learn ``frame -> action`` and generalise to the 110
private games (where hand-built per-game solvers don't transfer). The deployed
policy consumes ONLY frames; this script is a DEV-TIME label generator and is
allowed to use game internals to construct gold (efficient, correct) clears.

How it works
------------
We run the proven :class:`EnsembleAgent` (``src/admorphiq/agent_ensemble.py``)
on each game through a thin :class:`RecordingEnv` proxy that intercepts every
``env.step`` and records the transition ``(frame_t, action, x, y, next_frame_t,
reward, level_index, done)``. The ensemble combines all three trajectory
sources the task asks for in a single pass:

  (a) our working frame-only solvers (nav / toggle / click strategies),
  (b) search/BFS strategies that find short clearing sequences,
  (c) dev-time internal-access solvers that read a game's solution structure
      (sprite tags / internal state) to construct an efficient clear.

Gold labelling
--------------
Transitions are segmented into episodes (a RESET starts a new episode). Inside
an episode, the contiguous block of actions that ends in a level-up is the
sequence that CLEARED that level -> it is marked ``is_gold=True`` with the
cleared ``level_index``. Only blocks no longer than ``--gold-max-len`` are kept
as gold, because the efficiency-squared metric gives near-zero value to
inefficient (very long) clears -- short clears are the high-value training
signal. The trailing exploration tail of an episode is sampled (strided, capped)
as non-gold context so the policy also sees negative / exploratory frames.

Output
------
One ``data/traces/<game>.npz`` per game plus ``data/traces/index.json`` and
``data/traces/SCHEMA.md``. See SCHEMA.md (written by ``--write-schema``, also
emitted automatically on the first run) for the on-disk array contract.

Usage
-----
    uv run python scripts/generate_traces.py --games tu93,ft09,lp85,tn36
    uv run python scripts/generate_traces.py --games all --budget 50000
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from collections import deque
from pathlib import Path
from typing import Any

import numpy as np

# Allow running from the repo root without installing the package.
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "src"))

from arc_agi import Arcade, OperationMode  # noqa: E402

from admorphiq.agent_ensemble import EnsembleAgent, get_frame  # noqa: E402

# ── Tunables ─────────────────────────────────────────────────────────────────

# Max length of a level-clearing block still accepted as gold. Human L1
# baselines are ~16-123 actions; a clear far longer than that is inefficient
# (scores ~0 under efficiency^2) and is low-value training signal. 600 is a
# generous ceiling that keeps genuinely-solved-but-slow clears while rejecting
# brute-force thrash.
GOLD_MAX_LEN_DEFAULT = 600
# Retained transition window (with frames) per episode. Sized just above
# GOLD_MAX_LEN so any accepted gold block is always fully in memory when its
# terminating level-up fires. Bounds per-game transient memory to O(window).
FRAME_WINDOW_PAD = 16
# Keep every Nth non-gold transition from an episode's tail as exploration.
EXPLORE_STRIDE_DEFAULT = 25
# Per-game cap on non-gold exploration transitions retained.
EXPLORE_CAP_DEFAULT = 1200
# Reward shaping.
_R_LEVEL_UP = 1.0  # per level cleared by a transition (biggest signal)
_R_FRAME_PROGRESS = 0.02  # small credit when a non-clearing action changes the frame
_R_GAME_OVER = -0.5  # penalty for a transition that ends in GAME_OVER

_OUT_DIR_DEFAULT = _REPO / "data" / "traces"


def _base_id(game_id: str) -> str:
    """Strip the ``-<hash>`` version suffix from an env game_id."""
    return game_id.split("-")[0]


def _has_frame(obs: Any) -> bool:
    """True iff ``obs`` carries at least one renderable 64x64 layer.

    Games return frameless transition states on some level / reset boundaries;
    ``get_frame`` would IndexError on ``obs.frame[0]`` for those, so callers
    gate on this first.
    """
    if obs is None:
        return False
    fr = getattr(obs, "frame", None)
    return fr is not None and len(fr) > 0


# ── Transition recording ─────────────────────────────────────────────────────


class TraceCollector:
    """Streaming recorder that segments transitions into gold / exploration.

    Memory is bounded to a sliding window of ``frame_window`` transitions per
    episode; gold blocks are emitted the moment their level-up fires and only
    if they fit the window, so a pathologically long BFS episode never blows up
    RAM (its over-long clear is correctly rejected as non-gold anyway).
    """

    def __init__(
        self,
        *,
        gold_max_len: int = GOLD_MAX_LEN_DEFAULT,
        explore_stride: int = EXPLORE_STRIDE_DEFAULT,
        explore_cap: int = EXPLORE_CAP_DEFAULT,
    ) -> None:
        self.gold_max_len = gold_max_len
        self.frame_window = gold_max_len + FRAME_WINDOW_PAD
        self.explore_stride = max(1, explore_stride)
        self.explore_cap = explore_cap

        self.gold: list[dict] = []
        self.explore: list[dict] = []
        self.explore_count = 0

        # Per-episode state.
        self._ep_id = 0
        self._ep_step = 0
        self._seg_start = 0  # ep_step at which the current (uncleared) segment began
        self._prev_completed = 0
        self._gold_steps: set[int] = set()
        self._win: deque[dict] = deque(maxlen=self.frame_window)

        self.last_obs: Any = None
        self.num_layers = 1
        self.max_levels_seen = 0

    # -- proxy entry points --------------------------------------------------

    def bind(self, obs: Any) -> None:
        """Seed the collector with the make()-time observation."""
        self.last_obs = obs
        if obs is not None and getattr(obs, "frame", None) is not None:
            self.num_layers = len(obs.frame)
            self._prev_completed = int(getattr(obs, "levels_completed", 0) or 0)

    def record(self, action: Any, data: dict | None, before_obs: Any, after_obs: Any) -> None:
        """Record one ``env.step`` transition.

        Args:
            action: the GameAction passed to ``env.step``.
            data: the optional ``data={"x":..,"y":..}`` for ACTION6.
            before_obs: observation BEFORE this step (the state acted upon).
            after_obs: observation returned by this step.
        """
        if after_obs is None:
            return

        aid = int(getattr(action, "value", 0))
        lvl_after = int(getattr(after_obs, "levels_completed", 0) or 0)

        # RESET ends the current episode regardless of whether the post-reset
        # observation carries a renderable frame (some games return a frameless
        # transition state on reset / level boundaries).
        if aid == 0:
            self._flush_episode()
            self._ep_id += 1
            self._win.clear()
            self._gold_steps.clear()
            self._ep_step = 0
            self._seg_start = 0
            self._prev_completed = lvl_after
            if _has_frame(after_obs):
                self.last_obs = after_obs
            return

        # Frameless boundary state: skip recording but KEEP the last good obs so
        # the next renderable transition still pairs against a valid "before"
        # (and any level-up that happened across the gap is still credited).
        if not _has_frame(after_obs):
            return
        if before_obs is None or not _has_frame(before_obs):
            before_obs = self.last_obs if _has_frame(self.last_obs) else after_obs
        self.last_obs = after_obs

        if aid == 6 and data is not None:
            x = int(data.get("x", -1))
            y = int(data.get("y", -1))
        else:
            x, y = -1, -1

        fb = get_frame(before_obs).astype(np.uint8)
        fa = get_frame(after_obs).astype(np.uint8)
        lvl_before = int(getattr(before_obs, "levels_completed", 0) or 0)
        lvl_after = int(getattr(after_obs, "levels_completed", 0) or 0)
        self.max_levels_seen = max(self.max_levels_seen, lvl_after)
        state_name = getattr(getattr(after_obs, "state", None), "name", "")
        done = state_name in ("WIN", "GAME_OVER")
        delta = lvl_after - lvl_before
        changed = bool(np.any(fb != fa))

        reward = _R_LEVEL_UP * max(0, delta)
        if delta <= 0 and changed:
            reward += _R_FRAME_PROGRESS
        if state_name == "GAME_OVER":
            reward += _R_GAME_OVER

        rec = {
            "frame": fb,
            "next_frame": fa,
            "action": aid,
            "x": x,
            "y": y,
            "reward": float(reward),
            "level_index": lvl_before,
            "levels_completed_after": lvl_after,
            "done": done,
            "episode_id": self._ep_id,
            "ep_step": self._ep_step,
            "is_gold": False,
        }
        self._win.append(rec)
        self._ep_step += 1

        if delta > 0:
            self._emit_gold_block()
            self._seg_start = self._ep_step
            self._prev_completed = lvl_after

    # -- internal segmentation ----------------------------------------------

    def _emit_gold_block(self) -> None:
        """Mark the just-completed level's action block as gold, if short enough."""
        block = [r for r in self._win if r["ep_step"] >= self._seg_start]
        if not block:
            return
        # Require the whole block to still be in the window (its first step is
        # exactly seg_start) and to be efficient (<= gold_max_len).
        if block[0]["ep_step"] != self._seg_start or len(block) > self.gold_max_len:
            return
        level_idx = self._prev_completed
        for r in block:
            r2 = dict(r)
            r2["is_gold"] = True
            r2["level_index"] = level_idx
            self.gold.append(r2)
            self._gold_steps.add(r["ep_step"])

    def _flush_episode(self) -> None:
        """Sample the episode's non-gold tail as strided exploration context."""
        if self.explore_count >= self.explore_cap:
            return
        for r in self._win:
            if r["ep_step"] in self._gold_steps:
                continue
            if r["ep_step"] % self.explore_stride != 0:
                continue
            if self.explore_count >= self.explore_cap:
                break
            self.explore.append(dict(r))
            self.explore_count += 1

    def finalize(self) -> None:
        """Flush the final (un-RESET-terminated) episode."""
        self._flush_episode()


class RecordingEnv:
    """Transparent proxy over an arc_agi env that records every ``step``.

    Forwards ``observation_space`` and all other attributes (notably ``_game``,
    used by internal-access strategies) to the wrapped env, so the
    EnsembleAgent runs unchanged while we capture transitions.
    """

    def __init__(self, env: Any, collector: TraceCollector) -> None:
        object.__setattr__(self, "_env", env)
        object.__setattr__(self, "_rec", collector)
        collector.bind(env.observation_space)

    def step(self, action: Any, data: dict | None = None, **kwargs: Any) -> Any:
        before = self._rec.last_obs
        if data is not None:
            result = self._env.step(action, data=data, **kwargs)
        else:
            result = self._env.step(action, **kwargs)
        self._rec.record(action, data, before, result)
        return result

    @property
    def observation_space(self) -> Any:
        return self._env.observation_space

    def __getattr__(self, name: str) -> Any:
        # Only reached for attributes not defined on the proxy (e.g. _game).
        return getattr(object.__getattribute__(self, "_env"), name)


# ── Per-game driver ──────────────────────────────────────────────────────────


def generate_for_game(
    arcade: Arcade,
    env_info: Any,
    *,
    budget: int,
    gold_max_len: int,
    explore_stride: int,
    explore_cap: int,
    out_dir: Path,
) -> dict[str, Any]:
    """Run the ensemble on one game, record transitions, and write an .npz."""
    gid = env_info.game_id
    base = _base_id(gid)
    title = env_info.title or ""
    baseline = list(getattr(env_info, "baseline_actions", []) or [])

    env = arcade.make(gid)
    if env is None:
        return {"game_id": gid, "base": base, "error": "make() returned None"}

    collector = TraceCollector(
        gold_max_len=gold_max_len,
        explore_stride=explore_stride,
        explore_cap=explore_cap,
    )
    rec_env = RecordingEnv(env, collector)

    agent = EnsembleAgent(total_budget=budget)
    start = time.time()
    solve_meta: dict[str, Any] = {}
    try:
        result = agent.solve_game(rec_env, game_id=gid)
        solve_meta = {
            "cleared": result.get("cleared", False),
            "levels_completed": result.get("levels_completed", 0),
            "strategy": result.get("strategy", ""),
        }
    except Exception as exc:  # noqa: BLE001 - one game's failure must not abort the run
        traceback.print_exc()
        solve_meta = {"error": repr(exc)}
    collector.finalize()
    elapsed = time.time() - start

    records = collector.gold + collector.explore
    n_total = len(records)
    n_gold = len(collector.gold)
    gold_levels = sorted({r["level_index"] for r in collector.gold})

    meta = {
        "game_id": gid,
        "base_game": base,
        "title": title,
        "num_layers": collector.num_layers,
        "win_levels": int(getattr(env.observation_space, "win_levels", 0) or 0),
        "baseline_actions": baseline,
        "source": "ensemble",
        "frame_layout": "canonical_layer0_uint8",
        "n_total": n_total,
        "n_gold": n_gold,
        "n_explore": len(collector.explore),
        "gold_level_indices": gold_levels,
        "max_levels_seen": collector.max_levels_seen,
        "elapsed_s": round(elapsed, 2),
        **solve_meta,
    }

    if n_total == 0:
        meta["written"] = False
        return meta

    out_path = out_dir / f"{base}.npz"
    np.savez_compressed(
        out_path,
        frames=np.stack([r["frame"] for r in records]).astype(np.uint8),
        next_frames=np.stack([r["next_frame"] for r in records]).astype(np.uint8),
        actions=np.array([r["action"] for r in records], dtype=np.int8),
        coords_x=np.array([r["x"] for r in records], dtype=np.int8),
        coords_y=np.array([r["y"] for r in records], dtype=np.int8),
        rewards=np.array([r["reward"] for r in records], dtype=np.float32),
        level_index=np.array([r["level_index"] for r in records], dtype=np.int16),
        levels_completed_after=np.array(
            [r["levels_completed_after"] for r in records], dtype=np.int16
        ),
        is_gold=np.array([r["is_gold"] for r in records], dtype=bool),
        episode_id=np.array([r["episode_id"] for r in records], dtype=np.int32),
        done=np.array([r["done"] for r in records], dtype=bool),
        meta=np.array(json.dumps(meta)),
    )
    meta["written"] = True
    meta["path"] = str(out_path.relative_to(_REPO))
    return meta


# ── Schema doc ───────────────────────────────────────────────────────────────

_SCHEMA_MD = """# ARC-AGI-3 Training-Trace Schema

Generated by `scripts/generate_traces.py`. Each game is one
`data/traces/<base_game>.npz` (base = game id with the `-<hash>` suffix
stripped). All per-transition arrays share the same length `N` and the same
row order; row `i` is one `env.step` transition.

## Per-transition arrays

| Key | Dtype | Shape | Meaning |
|-----|-------|-------|---------|
| `frames` | uint8 | `(N, 64, 64)` | Canonical layer (`obs.frame[0]`) BEFORE the action. Values 0-15. |
| `next_frames` | uint8 | `(N, 64, 64)` | Canonical layer AFTER the action. |
| `actions` | int8 | `(N,)` | Action id: `RESET=0, ACTION1..5=1..5, ACTION6=6, ACTION7=7`. |
| `coords_x` | int8 | `(N,)` | ACTION6 click x (0-63); `-1` for non-ACTION6. |
| `coords_y` | int8 | `(N,)` | ACTION6 click y (0-63); `-1` for non-ACTION6. |
| `rewards` | float32 | `(N,)` | `+1.0` per level cleared, `+0.02` per frame change, `-0.5` on GAME_OVER. |
| `level_index` | int16 | `(N,)` | 0-indexed level PLAYED at action time (gold: the level this block clears). |
| `levels_completed_after` | int16 | `(N,)` | Cumulative levels completed after the action. |
| `is_gold` | bool | `(N,)` | `True` iff the row is in a block of actions that CLEARED a level. `False` = exploration. |
| `episode_id` | int32 | `(N,)` | Episode index (incremented on each RESET). |
| `done` | bool | `(N,)` | `True` iff the action ended in WIN or GAME_OVER. |
| `meta` | json str | scalar | Per-game metadata (see below). |

## `meta` (JSON string scalar)

`game_id`, `base_game`, `title`, `num_layers` (original layer count; only
layer 0 is stored), `win_levels`, `baseline_actions` (per-level HUMAN action
counts = the efficiency target), `source` (`"ensemble"`), `frame_layout`
(`"canonical_layer0_uint8"`), `n_total`, `n_gold`, `n_explore`,
`gold_level_indices`, `max_levels_seen`, `cleared`, `levels_completed`,
`strategy`, `elapsed_s`.

## Consuming the data (trainer)

```python
import json, numpy as np
d = np.load("data/traces/tu93.npz", allow_pickle=False)
meta = json.loads(str(d["meta"]))
gold = d["is_gold"]
# Frame->action supervised policy: train on gold rows.
X = d["frames"][gold]                 # (G, 64, 64) uint8
y_action = d["actions"][gold]         # (G,) action id
y_xy = np.stack([d["coords_x"], d["coords_y"]], 1)[gold]  # (G, 2), -1 when N/A
```

Train the action head on `actions`; train the coordinate head only on rows
where `actions == 6` (others have `coords == -1`). One-hot the 16 colour values
into 16 channels for the DriesSmit-style CNN. Use `is_gold` to weight or filter:
gold rows are correct efficient demonstrations; non-gold rows are exploratory
context (optionally down-weighted or used for a dynamics / change head).

## Provenance / honesty note

Gold labels may come from dev-time internal-access solvers (sprite tags /
internal game state) — this is LABEL GENERATION only. The deployed policy reads
ONLY `frames` (+ `coords` for its own ACTION6 output); it never sees internals.
"""


def write_schema(out_dir: Path) -> None:
    (out_dir / "SCHEMA.md").write_text(_SCHEMA_MD)


# ── CLI ──────────────────────────────────────────────────────────────────────


def _select_envs(envs: list, games_arg: str) -> list:
    """Pick one env per requested base game (first version hash wins)."""
    if games_arg.strip().lower() == "all":
        wanted = None
    else:
        wanted = {g.strip().lower() for g in games_arg.split(",") if g.strip()}
    seen: set[str] = set()
    out = []
    for e in envs:
        b = _base_id(e.game_id)
        if b in seen:
            continue
        if wanted is not None and b.lower() not in wanted:
            continue
        seen.add(b)
        out.append(e)
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--games", default="all", help="Comma-separated base ids (e.g. tu93,ft09) or 'all'.")
    p.add_argument("--budget", type=int, default=50000, help="EnsembleAgent total_budget per game.")
    p.add_argument("--gold-max-len", type=int, default=GOLD_MAX_LEN_DEFAULT)
    p.add_argument("--explore-stride", type=int, default=EXPLORE_STRIDE_DEFAULT)
    p.add_argument("--explore-cap", type=int, default=EXPLORE_CAP_DEFAULT)
    p.add_argument("--out-dir", default=str(_OUT_DIR_DEFAULT))
    args = p.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_schema(out_dir)

    arcade = Arcade(operation_mode=OperationMode.NORMAL)
    envs = arcade.get_environments()
    chosen = _select_envs(envs, args.games)
    print(f"Selected {len(chosen)} game(s): {[_base_id(e.game_id) for e in chosen]}\n")

    all_meta: list[dict] = []
    t0 = time.time()
    for i, env_info in enumerate(chosen):
        base = _base_id(env_info.game_id)
        print(f"[{i + 1:2d}/{len(chosen)}] {base} ({env_info.title}) ...", flush=True)
        try:
            meta = generate_for_game(
                arcade,
                env_info,
                budget=args.budget,
                gold_max_len=args.gold_max_len,
                explore_stride=args.explore_stride,
                explore_cap=args.explore_cap,
                out_dir=out_dir,
            )
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            meta = {"game_id": env_info.game_id, "base": base, "error": repr(exc)}
        all_meta.append(meta)
        gl = meta.get("gold_level_indices", [])
        print(
            f"     -> gold={meta.get('n_gold', 0)} explore={meta.get('n_explore', 0)} "
            f"levels_cleared={meta.get('levels_completed', 0)}/{meta.get('win_levels', '?')} "
            f"gold_levels={gl} {meta.get('elapsed_s', 0)}s"
            + (f"  ERROR: {meta['error']}" if "error" in meta else "")
        )

    # Aggregate index.
    index = {
        "generated_s": round(time.time() - t0, 1),
        "budget": args.budget,
        "gold_max_len": args.gold_max_len,
        "games": all_meta,
        "summary": {
            "games_total": len(all_meta),
            "games_with_gold": sum(1 for m in all_meta if m.get("n_gold", 0) > 0),
            "total_gold_transitions": sum(m.get("n_gold", 0) for m in all_meta),
            "total_transitions": sum(m.get("n_total", 0) for m in all_meta),
        },
    }
    (out_dir / "index.json").write_text(json.dumps(index, indent=2))

    s = index["summary"]
    print("\n" + "=" * 60)
    print(f"  games with gold : {s['games_with_gold']}/{s['games_total']}")
    print(f"  gold transitions: {s['total_gold_transitions']}")
    print(f"  all transitions : {s['total_transitions']}")
    print(f"  index           : {out_dir / 'index.json'}")
    print("=" * 60)


if __name__ == "__main__":
    main()
