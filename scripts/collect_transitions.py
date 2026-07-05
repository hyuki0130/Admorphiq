"""R35: collect (frame, action_idx, next_frame) transitions per game to .npz.

Why this exists (R35 big idea):
  A BC POLICY has ~0% transfer to unseen games because the right ACTIONS differ
  per game. A FORWARD MODEL — "what does action A do to this frame" — instead
  captures game-agnostic core-knowledge dynamics (a click toggles a cell, a push
  moves an object) that may GENERALISE across games. To test that empirically we
  first need transition data. This script drives a RANDOM + light-exploration
  agent over each game via the OFFLINE arcengine and records every
  ``(frame_int(64,64), action_idx, next_frame_int(64,64))`` transition it sees.

The run loop mirrors ``scripts/score_efficiency.py`` (Arcade OFFLINE, step with
``action_data.model_dump()`` for complex actions, RESET on GAME_OVER). The
recorded ``action_idx`` uses the SAME combined-logit convention the forward
model consumes (``_action_planes``): indices 0..4 are ACTION1..5, and index
``COORD_OFFSET + y*64 + x`` is an ACTION6 click at ``(x, y)``.

Usage:
  uv run python scripts/collect_transitions.py \\
      --titles tu93,ar25,dc22 --max-actions 2000 --seed 0 --out data/transitions
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path
from typing import Any

import numpy as np

# Allow running from repo root without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# Combined-logit action convention shared with the forward model.
from admorphiq.world_model.forward_model import COORD_OFFSET, GRID  # noqa: E402

NUM_SIMPLE_ACTIONS = COORD_OFFSET  # 5


def action_index_to_spec(idx: int) -> tuple[int, int | None, int | None]:
    """Decode a combined-logit index into ``(action_id, x, y)``.

    ``action_id`` is the 1-based ARC action id (1..5 simple, 6 for a click).
    For a click, ``x``/``y`` are the grid coordinates; otherwise both are None.
    """
    if idx < NUM_SIMPLE_ACTIONS:
        return idx + 1, None, None
    coord = idx - COORD_OFFSET
    y, x = divmod(coord, GRID)
    return 6, x, y


def _availability(obs: Any) -> tuple[list[int], bool]:
    """Return ``(available simple ids, action6_available)`` from an observation."""
    simple: list[int] = []
    action6 = False
    for a in getattr(obs, "available_actions", []) or []:
        aid = a if isinstance(a, int) else getattr(a, "value", getattr(a, "id", None))
        if aid is None:
            continue
        if 1 <= aid <= 5:
            simple.append(int(aid))
        elif aid == 6:
            action6 = True
    return simple, action6


def _get_frame(obs: Any) -> np.ndarray | None:
    """Extract the (64, 64) int frame from an observation, or None if absent."""
    fr = getattr(obs, "frame", None)
    if fr is None or len(fr) == 0:
        return None
    return np.asarray(fr[0], dtype=np.int16)


def _state_name(obs: Any) -> str:
    state = getattr(obs, "state", None)
    return getattr(state, "name", str(state) if state is not None else "")


def _sample_action_index(
    rng: random.Random,
    simple: list[int],
    action6: bool,
    explore_bias: int | None,
) -> int:
    """Pick a combined-logit action index, biased toward a changing action.

    Light exploration: with probability 0.5 (when ``explore_bias`` is set and
    still available) repeat the action index that changed the frame last step;
    otherwise draw uniformly from the available actions (ACTION6 -> uniform
    x, y). Repeating a productive action makes multi-step effects (pushes,
    animations) more likely to be sampled than pure uniform random.
    """
    idx_pool = [i - 1 for i in simple]  # 1-based ids -> 0-based indices
    if action6:
        idx_pool.append(-6)  # sentinel: draw a random click

    if explore_bias is not None and rng.random() < 0.5:
        if explore_bias < NUM_SIMPLE_ACTIONS:
            if (explore_bias + 1) in simple:
                return explore_bias
        elif action6:
            return explore_bias

    pick = rng.choice(idx_pool)
    if pick == -6:
        x = rng.randrange(GRID)
        y = rng.randrange(GRID)
        return COORD_OFFSET + y * GRID + x
    return pick


def collect_game(
    arcade: Any,
    game_id: str,
    max_actions: int,
    rng: random.Random,
) -> dict[str, np.ndarray]:
    """Drive one game and return stacked transition arrays.

    Returns a dict with:
      frames      (N, 64, 64) int16 — the frame BEFORE each action
      actions     (N,)        int32 — combined-logit action index
      next_frames (N, 64, 64) int16 — the frame AFTER each action
    Only steps that yield a valid before/after frame are recorded. RESET steps
    and GAME_OVER revivals are NOT stored as transitions.
    """
    from arcengine import GameAction, GameState

    env = arcade.make(game_id)
    if env is None:
        return _empty_transitions()
    obs = env.observation_space
    if obs is None:
        return _empty_transitions()

    frames: list[np.ndarray] = []
    actions: list[int] = []
    next_frames: list[np.ndarray] = []

    explore_bias: int | None = None
    action_count = 0

    while action_count < max_actions:
        state = _state_name(obs)
        if state == "WIN":
            break
        if state == "GAME_OVER":
            obs = env.step(GameAction.RESET)
            explore_bias = None
            if obs is None:
                break
            continue

        cur = _get_frame(obs)
        if cur is None:
            obs = env.step(GameAction.RESET)
            if obs is None:
                break
            continue

        simple, action6 = _availability(obs)
        if not simple and not action6:
            obs = env.step(GameAction.RESET)
            explore_bias = None
            if obs is None:
                break
            continue

        idx = _sample_action_index(rng, simple, action6, explore_bias)
        aid, x, y = action_index_to_spec(idx)

        action = GameAction.from_id(aid)
        if action.is_complex():
            action.set_data({"x": int(x), "y": int(y)})
            obs = env.step(action, data=action.action_data.model_dump())
        else:
            obs = env.step(action)

        action_count += 1
        if obs is None:
            break

        nxt = _get_frame(obs)
        if nxt is not None:
            frames.append(cur)
            actions.append(idx)
            next_frames.append(nxt)
            # Light exploration: bias toward this action next step if it changed
            # the frame, else clear the bias so we resume uniform sampling.
            explore_bias = idx if not np.array_equal(cur, nxt) else None

        if obs.state == GameState.WIN:
            break

    if not frames:
        return _empty_transitions()
    return {
        "frames": np.stack(frames).astype(np.int16),
        "actions": np.asarray(actions, dtype=np.int32),
        "next_frames": np.stack(next_frames).astype(np.int16),
    }


def _empty_transitions() -> dict[str, np.ndarray]:
    return {
        "frames": np.zeros((0, GRID, GRID), dtype=np.int16),
        "actions": np.zeros((0,), dtype=np.int32),
        "next_frames": np.zeros((0, GRID, GRID), dtype=np.int16),
    }


def _resolve_games(arcade: Any, titles: str) -> list[tuple[str, str]]:
    """Return ``[(game_id, title)]`` for the requested comma-separated titles.

    Matches on case-insensitive substring of ``"<game_id> <title>"``, dedups by
    game_id (first hash wins), preserving the requested title order.
    """
    envs = arcade.get_environments()
    wanted = [t.strip().lower() for t in titles.split(",") if t.strip()]
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for w in wanted:
        for e in envs:
            hay = f"{e.game_id} {e.title or ''}".lower()
            if w in hay and e.game_id not in seen:
                seen.add(e.game_id)
                out.append((e.game_id, e.title or e.game_id))
                break
    return out


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Collect (frame, action, next_frame) transitions per game."
    )
    p.add_argument(
        "--titles",
        required=True,
        help="Comma-separated case-insensitive title/id substrings "
        "(e.g. 'tu93,ar25,dc22').",
    )
    p.add_argument(
        "--max-actions",
        type=int,
        default=2000,
        help="Per-game action budget (default: 2000).",
    )
    p.add_argument("--seed", type=int, default=0, help="RNG seed (default: 0).")
    p.add_argument(
        "--out",
        default="data/transitions",
        help="Output directory; one <title>.npz written per game "
        "(default: data/transitions).",
    )
    return p


def main() -> None:
    from arc_agi import Arcade, OperationMode

    args = _build_parser().parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    games = _resolve_games(arcade, args.titles)
    if not games:
        print("No games matched --titles; nothing to collect.", flush=True)
        return

    print(
        f"Collecting from {len(games)} game(s), "
        f"{args.max_actions} actions each, seed={args.seed} …",
        flush=True,
    )

    for i, (game_id, title) in enumerate(games):
        # Per-game seed derived from the base seed keeps runs reproducible while
        # giving each game an independent action stream.
        rng = random.Random(args.seed + i)
        data = collect_game(arcade, game_id, args.max_actions, rng)
        n = int(data["actions"].shape[0])
        out_path = out_dir / f"{title.lower()}.npz"
        np.savez_compressed(
            out_path,
            frames=data["frames"],
            actions=data["actions"],
            next_frames=data["next_frames"],
            game_id=np.asarray(game_id),
            title=np.asarray(title),
        )
        changed = (
            int(np.any(data["frames"] != data["next_frames"], axis=(1, 2)).sum())
            if n
            else 0
        )
        print(
            f"  [{i + 1}/{len(games)}] {title} ({game_id}): "
            f"{n} transitions ({changed} changed) -> {out_path}",
            flush=True,
        )

    print("Done.", flush=True)


if __name__ == "__main__":
    main()
