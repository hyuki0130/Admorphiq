"""Dev-time optimizer for the BC gold dataset on two axes.

The competition metric is efficiency-SQUARED -- per level the score is
``min(human_actions / agent_actions, 1) ** 2`` -- so a clear that uses 4x the
human action count scores ~1/16 of a tight clear. Behaviour cloning reproduces
its demonstrations, so SHORTER gold demonstrations directly raise the deployed
policy's score. This script improves the gold dataset two ways and rewrites the
on-disk traces in the SAME schema as ``generate_traces.py``:

  1. EFFICIENCY (existing 18 gold games): each game's gold rows already form the
     gapless, replayable action prefix from the episode's RESET to its last
     level-up (RESET itself is never recorded; level-clearing blocks are stored
     contiguously in row order). We reconstruct that per-episode action
     sequence, replay it in a fresh env to confirm it still clears, then
     MINIMISE it (no-op pruning + bounded delta-debugging), re-verifying every
     candidate by actually replaying in arc_agi. The shortened, still-winning
     sequence is re-recorded into fresh gold rows; the original exploration rows
     are preserved as negative context.

  2. COVERAGE (the 7 zero-gold games): re86, su15, cn04, tr87, ka59, s5i5,
     tn36. We run the proven ``EnsembleAgent`` across every available version
     hash of the game (the public set serves 1-2 hashes per game; brittle
     internal-access solvers that fail on one hash often clear another -- the
     learned frame->action policy transfers across hashes because the mechanics
     are identical). Any clear is captured via a full action log, minimised the
     same way, and written as new gold.

Both paths funnel through the proven ``TraceCollector`` segmentation so the
output npz files are byte-compatible with the trainer.

Usage
-----
    uv run python scripts/optimize_gold.py                 # all games
    uv run python scripts/optimize_gold.py --games lp85,ls20,ar25
    uv run python scripts/optimize_gold.py --missing-only  # only the 7 gaps
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path
from typing import Any

import numpy as np

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "src"))

from arc_agi import Arcade, OperationMode  # noqa: E402
from arcengine import GameAction  # noqa: E402

# Reuse the proven recorder/segmenter so output is schema-identical.
from generate_traces import (  # noqa: E402
    RecordingEnv,
    TraceCollector,
    _base_id,
    write_schema,
)

from admorphiq.agent_ensemble import EnsembleAgent, get_frame  # noqa: E402

TRACES_DIR = _REPO / "data" / "traces"
MISSING_GAMES = ["re86", "su15", "cn04", "tr87", "ka59", "s5i5", "tn36"]

# Minimisation safety rails (env.step is the cost; bound total replayed work).
_MAX_REPLAY_STEPS = 400_000  # per game, summed across all verification replays
_MAX_MINIMISE_S = 180.0      # per game wall-clock cap for the minimise pass


def _state_name(obs: Any) -> str:
    st = getattr(obs, "state", None)
    return getattr(st, "name", "")


def _has_frame(obs: Any) -> bool:
    fr = getattr(obs, "frame", None)
    return fr is not None and len(fr) > 0


class _StepBudget:
    """Mutable counter so replays share one per-game env.step budget."""

    def __init__(self, cap: int) -> None:
        self.used = 0
        self.cap = cap

    def ok(self, n: int) -> bool:
        return self.used + n <= self.cap

    def add(self, n: int) -> None:
        self.used += n


def replay(
    arcade: Arcade,
    game_id: str,
    actions: list[tuple[int, int, int]],
    budget: _StepBudget,
) -> tuple[int, list[dict]]:
    """Replay an action list in a fresh env; return (levels_cleared, per-step info).

    ``actions`` is a list of ``(action_id, x, y)``; ``x/y`` are used only for
    ACTION6. A leading RESET is issued implicitly by including it in ``actions``
    (action_id 0). Stops early on WIN/GAME_OVER. ``info[i]`` carries
    ``changed`` (frame changed vs the previous framed obs), ``ld`` (level delta)
    and ``frameless``.
    """
    env = arcade.make(game_id)
    obs = env.observation_space
    prev_frame = get_frame(obs) if _has_frame(obs) else None
    prev_levels = int(getattr(obs, "levels_completed", 0) or 0)
    info: list[dict] = []
    budget.add(len(actions))
    for aid, x, y in actions:
        if aid == 6:
            obs = env.step(GameAction.ACTION6, data={"x": int(x), "y": int(y)})
        else:
            obs = env.step(GameAction.from_id(aid))
        lvl = int(getattr(obs, "levels_completed", 0) or 0)
        ld = lvl - prev_levels
        if _has_frame(obs):
            fr = get_frame(obs)
            changed = prev_frame is None or bool(np.any(fr != prev_frame))
            prev_frame = fr
            frameless = False
        else:
            changed = True
            frameless = True
        info.append({"changed": changed, "ld": ld, "frameless": frameless})
        prev_levels = lvl
        if _state_name(obs) in ("WIN", "GAME_OVER"):
            break
    return prev_levels, info


def _clears(
    arcade: Arcade, game_id: str, actions: list[tuple[int, int, int]],
    target: int, budget: _StepBudget,
) -> bool:
    """True iff replaying ``actions`` reaches at least ``target`` levels."""
    if not actions or not budget.ok(len(actions)):
        return False
    lvls, _ = replay(arcade, game_id, actions, budget)
    return lvls >= target


def minimise(
    arcade: Arcade,
    game_id: str,
    actions: list[tuple[int, int, int]],
    target: int,
    budget: _StepBudget,
) -> list[tuple[int, int, int]]:
    """Return a shorter action list that still clears >= ``target`` levels.

    Step 1: drop frame-unchanged, non-level-up, non-RESET actions (pure no-ops
    that BFS/click-spam strategies emit) and re-verify. Step 2: bounded
    delta-debugging that removes contiguous chunks and re-verifies. Every
    acceptance is proven by an actual replay; on any failure the longer
    sequence is kept (never returns something that doesn't clear).
    """
    t0 = time.time()
    base = list(actions)
    if not _clears(arcade, game_id, base, target, budget):
        return base  # can't even reproduce the original clear; leave it alone

    # -- Step 1: no-op pruning (one replay to label, one to verify) -----------
    lvls, info = replay(arcade, game_id, base, budget)
    if lvls >= target and len(info) == len(base):
        pruned = [
            a for a, nfo in zip(base, info)
            if a[0] == 0 or nfo["ld"] > 0 or nfo["changed"] or nfo["frameless"]
        ]
        if len(pruned) < len(base) and _clears(arcade, game_id, pruned, target, budget):
            base = pruned

    # -- Step 2: bounded delta-debugging (ddmin-style chunk removal) ----------
    n_chunks = 2
    while (
        len(base) > 1
        and time.time() - t0 < _MAX_MINIMISE_S
        and budget.ok(len(base) * 4)
    ):
        chunk = max(1, len(base) // n_chunks)
        removed_any = False
        i = 0
        while i < len(base):
            # Never drop the leading RESET.
            lo = max(i, 1) if base and base[0][0] == 0 else i
            cand = base[:lo] + base[i + chunk:]
            if (
                len(cand) < len(base)
                and time.time() - t0 < _MAX_MINIMISE_S
                and _clears(arcade, game_id, cand, target, budget)
            ):
                base = cand
                removed_any = True
                # keep i; the window now holds later actions
            else:
                i += chunk
        if removed_any:
            n_chunks = max(2, n_chunks - 1)
        elif n_chunks >= len(base):
            break
        else:
            n_chunks = min(len(base), n_chunks * 2)
    return base


# ── full-log recorder for the coverage path ──────────────────────────────────


class _FullLogEnv:
    """Transparent env proxy that records every step as (ep, aid, x, y, lvl)."""

    def __init__(self, env: Any) -> None:
        object.__setattr__(self, "_env", env)
        object.__setattr__(self, "_log", [])
        object.__setattr__(self, "_ep", 0)

    def step(self, action: Any, data: dict | None = None, **kw: Any) -> Any:
        aid = int(getattr(action, "value", 0))
        if aid == 0:
            object.__setattr__(self, "_ep", self._ep + 1)
        if data is not None:
            result = self._env.step(action, data=data, **kw)
        else:
            result = self._env.step(action, **kw)
        x = int(data.get("x", -1)) if (aid == 6 and data) else -1
        y = int(data.get("y", -1)) if (aid == 6 and data) else -1
        lvl = int(getattr(result, "levels_completed", 0) or 0)
        self._log.append((self._ep, aid, x, y, lvl))
        return result

    @property
    def observation_space(self) -> Any:
        return self._env.observation_space

    def __getattr__(self, name: str) -> Any:
        return getattr(object.__getattribute__(self, "_env"), name)


# ── npz <-> records helpers ───────────────────────────────────────────────────


def _records_from_minimised(
    arcade: Arcade, game_id: str, actions: list[tuple[int, int, int]],
) -> tuple[TraceCollector, dict]:
    """Replay ``actions`` through the proven collector to get clean gold rows."""
    env = arcade.make(game_id)
    collector = TraceCollector()
    rec_env = RecordingEnv(env, collector)
    for aid, x, y in actions:
        if aid == 6:
            rec_env.step(GameAction.ACTION6, data={"x": int(x), "y": int(y)})
        else:
            rec_env.step(GameAction.from_id(aid))
    collector.finalize()
    return collector, {}


def _explore_rows_from_npz(d: Any) -> list[dict]:
    """Pull the original non-gold (exploration) rows out of an existing npz."""
    gold = d["is_gold"]
    keep = ~gold
    out: list[dict] = []
    for i in np.nonzero(keep)[0]:
        out.append(
            {
                "frame": d["frames"][i],
                "next_frame": d["next_frames"][i],
                "action": int(d["actions"][i]),
                "x": int(d["coords_x"][i]),
                "y": int(d["coords_y"][i]),
                "reward": float(d["rewards"][i]),
                "level_index": int(d["level_index"][i]),
                "levels_completed_after": int(d["levels_completed_after"][i]),
                "done": bool(d["done"][i]),
                "episode_id": int(d["episode_id"][i]),
                "is_gold": False,
            }
        )
    return out


def _write_npz(out_path: Path, gold_rows: list[dict], explore_rows: list[dict], meta: dict) -> None:
    records = gold_rows + explore_rows
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


def _gold_rows_from_npz(d: Any) -> list[dict]:
    """Pull the original gold rows out of an existing npz (full-coverage demos)."""
    gold = d["is_gold"]
    out: list[dict] = []
    for i in np.nonzero(gold)[0]:
        out.append(
            {
                "frame": d["frames"][i],
                "next_frame": d["next_frames"][i],
                "action": int(d["actions"][i]),
                "x": int(d["coords_x"][i]),
                "y": int(d["coords_y"][i]),
                "reward": float(d["rewards"][i]),
                "level_index": int(d["level_index"][i]),
                "levels_completed_after": int(d["levels_completed_after"][i]),
                "done": bool(d["done"][i]),
                "episode_id": int(d["episode_id"][i]),
                "is_gold": True,
            }
        )
    return out


def _gold_action_seq_by_episode(d: Any) -> dict[int, list[tuple[int, int, int]]]:
    """Reconstruct per-episode gold action sequences from an existing npz.

    Gold rows are stored in episode/level order and form the gapless prefix from
    each episode's RESET to its last recorded level-up (RESET is not recorded).
    Returns ``{episode_id: [(aid, x, y), ...]}`` with a leading RESET prepended.
    """
    gold = d["is_gold"]
    eps = d["episode_id"][gold]
    acts = d["actions"][gold]
    cx = d["coords_x"][gold]
    cy = d["coords_y"][gold]
    seqs: dict[int, list[tuple[int, int, int]]] = {}
    for ep in np.unique(eps):
        sel = eps == ep
        seq = [(0, -1, -1)]  # leading RESET
        for a, x, y in zip(acts[sel], cx[sel], cy[sel]):
            seq.append((int(a), int(x), int(y)))
        seqs[int(ep)] = seq
    return seqs


# ── per-game drivers ──────────────────────────────────────────────────────────


# Minimized-block episode ids are offset so the trainer treats them as separate
# efficiency demos (it groups gold blocks by (episode_id, level_index) to size
# the efficiency weight). Without the offset a short minimized block would merge
# with the long original block of the same (ep, level) and corrupt both weights.
_MIN_EP_OFFSET = 1_000_000


def optimise_existing(arcade: Arcade, base: str) -> dict:
    """Augment a trace npz: keep original gold (coverage) + add minimized demos.

    Replacing the gold with a single minimized episode discards multi-level and
    multi-episode coverage, which collapses the deployed policy's clear rate
    (measured). Instead we KEEP every original gold row and ADD a minimized,
    still-winning version of each gold episode. The trainer's efficiency-squared
    weighting up-weights the short minimized blocks and down-weights the long
    originals, so the policy is biased toward efficient play without losing the
    trajectory coverage it needs to navigate live.
    """
    npz_path = TRACES_DIR / f"{base}.npz"
    d = np.load(npz_path, allow_pickle=False)
    meta = json.loads(str(d["meta"]))
    game_id = meta["game_id"]
    orig_gold = int(d["is_gold"].sum())

    orig_gold_rows = _gold_rows_from_npz(d)
    explore_rows = _explore_rows_from_npz(d)
    seqs = _gold_action_seq_by_episode(d)
    d.close()

    budget = _StepBudget(_MAX_REPLAY_STEPS)
    # Collect the SHORTEST minimized block per level across all episodes. Adding
    # one minimized demo per BFS episode floods level-0 (a game can have 9
    # single-level episodes) and the efficiency weighting then starves the rarer
    # deeper-level demos -- which measurably collapsed AR25/M0R0 level-2 clears.
    # Keeping only the shortest block for each level gives a clean efficiency
    # nudge without crowding out depth.
    best_block_per_level: dict[int, list[dict]] = {}
    for ep, base_seq in sorted(seqs.items()):
        lvls, _ = replay(arcade, game_id, base_seq, budget)
        if lvls <= 0:
            continue  # this episode's gold doesn't reproduce a clear; skip
        mini = minimise(arcade, game_id, base_seq, lvls, budget)
        collector, _ = _records_from_minimised(arcade, game_id, mini)
        if not collector.gold:
            continue
        by_level: dict[int, list[dict]] = {}
        for r in collector.gold:
            by_level.setdefault(int(r["level_index"]), []).append(dict(r))
        for lvl, block in by_level.items():
            prev = best_block_per_level.get(lvl)
            if prev is None or len(block) < len(prev):
                best_block_per_level[lvl] = block

    mini_rows: list[dict] = []
    mini_action_total = 0
    for lvl, block in sorted(best_block_per_level.items()):
        for r in block:
            r["episode_id"] = _MIN_EP_OFFSET + lvl  # distinct from originals
            mini_rows.append(r)
        mini_action_total += len(block)
    mini_eps_done = len(best_block_per_level)

    gold_rows = orig_gold_rows + mini_rows
    new_gold = len(gold_rows)
    gold_levels = sorted({r["level_index"] for r in gold_rows})
    meta.update(
        {
            "n_total": new_gold + len(explore_rows),
            "n_gold": new_gold,
            "n_explore": len(explore_rows),
            "gold_level_indices": gold_levels,
            "augmented_minimized": True,
            "orig_n_gold": orig_gold,
            "n_minimized_gold": len(mini_rows),
            "min_actions_total": mini_action_total,
        }
    )
    _write_npz(npz_path, gold_rows, explore_rows, meta)
    return {
        "base": base,
        "status": "ok",
        "orig_gold": orig_gold,
        "added_min_gold": len(mini_rows),
        "min_episodes": mini_eps_done,
        "min_actions_total": mini_action_total,
        "gold_levels": gold_levels,
    }


def _solve_one_hash(arcade: Arcade, game_id: str, budget: int) -> tuple[int, list, Any]:
    """Run the ensemble through a full-log env; return (levels, log, env_info)."""
    env = arcade.make(game_id)
    if env is None:
        return 0, [], None
    log_env = _FullLogEnv(env)
    agent = EnsembleAgent(total_budget=budget)
    try:
        result = agent.solve_game(log_env, game_id=game_id)
        lvls = int(result.get("levels_completed", 0) or 0)
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        lvls = 0
    return lvls, log_env._log, env.observation_space


def generate_missing(arcade: Arcade, base: str, envs_by_base: dict, budget: int) -> dict:
    """Try every available hash of a zero-gold game; minimise + write any clear."""
    candidates = envs_by_base.get(base, [])
    best: dict | None = None
    for env_info in candidates:
        gid = env_info.game_id
        lvls, log, obs = _solve_one_hash(arcade, gid, budget)
        if lvls <= 0 or not log:
            continue
        # Best episode = the one that reached the most levels.
        ep_max: dict[int, int] = {}
        for ep, _aid, _x, _y, lvl in log:
            ep_max[ep] = max(ep_max.get(ep, 0), lvl)
        win_ep = max(ep_max, key=lambda e: ep_max[e])
        ep_actions = [(aid, x, y) for ep, aid, x, y, _lvl in log if ep == win_ep]
        if not ep_actions or ep_actions[0][0] != 0:
            ep_actions = [(0, -1, -1)] + ep_actions
        bud = _StepBudget(_MAX_REPLAY_STEPS)
        target, _ = replay(arcade, gid, ep_actions, bud)
        if target <= 0:
            continue
        mini = minimise(arcade, gid, ep_actions, target, bud)
        collector, _ = _records_from_minimised(arcade, gid, mini)
        if not collector.gold:
            continue
        cand = {
            "game_id": gid,
            "env_info": env_info,
            "obs": obs,
            "gold_rows": collector.gold,
            "explore_rows": collector.explore,
            "collector": collector,
            "min_actions": len(mini) - 1,
            "target_levels": target,
        }
        if best is None or len(cand["gold_rows"]) and ep_max[win_ep] > best.get("target_levels", 0):
            best = cand
        # First clear is enough; prefer more levels but stop after one solid clear.
        break

    if best is None:
        return {"base": base, "status": "no_clear"}

    env_info = best["env_info"]
    obs = best["obs"]
    meta = {
        "game_id": best["game_id"],
        "base_game": base,
        "title": env_info.title or base.upper(),
        "num_layers": best["collector"].num_layers,
        "win_levels": int(getattr(obs, "win_levels", 0) or 0),
        "baseline_actions": list(getattr(env_info, "baseline_actions", []) or []),
        "source": "ensemble",
        "frame_layout": "canonical_layer0_uint8",
        "n_total": len(best["gold_rows"]) + len(best["explore_rows"]),
        "n_gold": len(best["gold_rows"]),
        "n_explore": len(best["explore_rows"]),
        "gold_level_indices": sorted({r["level_index"] for r in best["gold_rows"]}),
        "max_levels_seen": best["collector"].max_levels_seen,
        "cleared": True,
        "levels_completed": best["target_levels"],
        "strategy": "ensemble+minimise",
        "minimized": True,
        "min_actions": best["min_actions"],
    }
    _write_npz(TRACES_DIR / f"{base}.npz", best["gold_rows"], best["explore_rows"], meta)
    return {
        "base": base,
        "status": "ok",
        "game_id": best["game_id"],
        "new_gold": len(best["gold_rows"]),
        "gold_levels": meta["gold_level_indices"],
        "min_actions": best["min_actions"],
    }


def rebuild_index() -> dict:
    """Regenerate index.json from the current npz files."""
    games = []
    for f in sorted(TRACES_DIR.glob("*.npz")):
        d = np.load(f, allow_pickle=False)
        meta = json.loads(str(d["meta"]))
        meta["path"] = str(f.relative_to(_REPO))
        meta["written"] = True
        games.append(meta)
        d.close()
    index = {
        "optimizer": "scripts/optimize_gold.py",
        "games": games,
        "summary": {
            "games_total": len(games),
            "games_with_gold": sum(1 for m in games if m.get("n_gold", 0) > 0),
            "total_gold_transitions": sum(m.get("n_gold", 0) for m in games),
            "total_transitions": sum(m.get("n_total", 0) for m in games),
        },
    }
    (TRACES_DIR / "index.json").write_text(json.dumps(index, indent=2))
    return index


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--games", default="all", help="Comma-separated base ids or 'all'.")
    p.add_argument("--missing-only", action="store_true", help="Only fill the 7 zero-gold games.")
    p.add_argument("--budget", type=int, default=50000, help="Ensemble budget for coverage path.")
    args = p.parse_args()

    write_schema(TRACES_DIR)
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    all_envs = arcade.get_environments()
    envs_by_base: dict[str, list] = {}
    for e in all_envs:
        envs_by_base.setdefault(_base_id(e.game_id), []).append(e)

    existing = sorted(p2.stem for p2 in TRACES_DIR.glob("*.npz"))
    with_gold = set()
    for b in existing:
        d = np.load(TRACES_DIR / f"{b}.npz", allow_pickle=False)
        if d["is_gold"].any():
            with_gold.add(b)
        d.close()

    if args.games != "all":
        wanted = {g.strip().lower() for g in args.games.split(",") if g.strip()}
    else:
        wanted = None

    t0 = time.time()
    results = []

    # --- coverage path (7 missing games) ---
    missing = [b for b in MISSING_GAMES if (wanted is None or b in wanted)]
    for b in missing:
        print(f"[coverage] {b} ...", flush=True)
        try:
            r = generate_missing(arcade, b, envs_by_base, args.budget)
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            r = {"base": b, "status": f"error: {exc!r}"}
        print(f"   -> {r}", flush=True)
        results.append(r)

    # --- efficiency path (existing gold games) ---
    if not args.missing_only:
        targets = sorted(with_gold)
        if wanted is not None:
            targets = [b for b in targets if b in wanted]
        for b in targets:
            print(f"[minimise] {b} ...", flush=True)
            try:
                r = optimise_existing(arcade, b)
            except Exception as exc:  # noqa: BLE001
                traceback.print_exc()
                r = {"base": b, "status": f"error: {exc!r}"}
            print(f"   -> {r}", flush=True)
            results.append(r)

    index = rebuild_index()
    s = index["summary"]
    print("\n" + "=" * 60)
    print(f"  games with gold : {s['games_with_gold']}/{s['games_total']}")
    print(f"  gold transitions: {s['total_gold_transitions']}")
    print(f"  elapsed         : {time.time() - t0:.1f}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
