"""Dev-time GOLD trace generator for hard games via brittle internal-access solvers.

Context
-------
``scripts/generate_traces.py`` runs the full :class:`EnsembleAgent` and records
``frame -> action`` transitions. For a handful of hard games (su15, tn36, tr87,
s5i5, cn04) the ensemble's feature-based dispatch clears 0 levels on the
API-served hash, so those ``data/traces/<g>.npz`` carry ``n_gold=0`` and the
behaviour-cloning policy can never learn them.

But ``agent_ensemble.py`` still contains the original brittle solvers
(``strat_su15_vacuum``, ``strat_tn36_puzzle``, ``strat_s5i5_slider``, ...) that
clear those games by reading game-internal sprite tags / state. Those solvers do
NOT transfer to the private 110, but the ``frame -> action`` TRACES they emit DO
train a frame-only policy that may transfer. This script drives the matching
solver directly and records its clearing trajectory as gold.

Hash matching
-------------
The brittle solvers were written against the v1 game internals. The API now
serves the v2-obfuscated hash, on which the solvers short-circuit to 0. Both
hashes ship locally under ``environment_files/<game>/<hash>/``; we instantiate
the *matching* hash so the solver can read the internals it expects. The frames
produced are still valid renderings of the same game, so the gold labels are
correct ``frame -> action`` demonstrations.

Recording / gold labelling reuse the exact machinery in
``scripts/generate_traces.py`` (:class:`RecordingEnv`, :class:`TraceCollector`)
so the on-disk schema (``data/traces/SCHEMA.md``) is identical.

Isolation
---------
Writes ONLY ``data/traces/{su15,tn36,tr87,s5i5,cn04}.npz`` and rewrites the
matching entries inside ``data/traces/index.json`` (preserving every other
game's entry and the top-level summary). Touches nothing else.

Usage
-----
    uv run python scripts/generate_brittle_traces.py --games su15,tn36,s5i5
    uv run python scripts/generate_brittle_traces.py --games all
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Callable

import numpy as np

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "src"))
sys.path.insert(0, str(_REPO))

from arc_agi import Arcade, OperationMode  # noqa: E402

from admorphiq import agent_ensemble  # noqa: E402
from scripts.generate_traces import (  # noqa: E402
    RecordingEnv,
    TraceCollector,
    _base_id,
)

_OUT_DIR = _REPO / "data" / "traces"


# ── Plan ───────────────────────────────────────────────────────────────────
#
# Per game: the hash whose internals the brittle solver matches, an ordered list
# of (solver_fn, kwargs) candidates (first one to clear >=1 level wins), and the
# gold_max_len ceiling (generous enough to keep every clearing block this solver
# produces, since brittle clears are already short).


def _ensemble_solver(budget: int) -> Callable[[Any], tuple[int, str, int]]:
    """Adapter so the whole EnsembleAgent can be used as a (levels,name,used) fn."""

    def _run(env: Any, _budget: int = budget) -> tuple[int, str, int]:
        agent = agent_ensemble.EnsembleAgent(total_budget=_budget)
        result = agent.solve_game(env, game_id=getattr(env, "game_id", ""))
        return (
            int(result.get("levels_completed", 0)),
            str(result.get("strategy", "ensemble")),
            int(result.get("total_actions", 0) or 0),
        )

    return _run


def _build_plan() -> dict[str, dict]:
    e = agent_ensemble
    return {
        "su15": {
            "play_hash": "su15-4c352900",
            "candidates": [(e.strat_su15_vacuum, {"budget": 5000})],
            "gold_max_len": 600,
        },
        "tn36": {
            "play_hash": "tn36-ab4f63cc",
            "candidates": [(e.strat_tn36_puzzle, {"budget": 500})],
            "gold_max_len": 600,
        },
        "s5i5": {
            "play_hash": "s5i5-a48e4b1d",
            "candidates": [(e.strat_s5i5_slider, {"budget": 4000})],
            "gold_max_len": 4000,
        },
        "tr87": {
            "play_hash": "tr87-cd924810",
            "candidates": [
                (e.strat_tr87_rotation, {"budget": 500000}),
                (_ensemble_solver(80000), {}),
            ],
            "gold_max_len": 4000,
        },
        "cn04": {
            # The served 2fe56bfb hash clears 0; the alternate local hash
            # 65d47d14 clears L1 via the ensemble's zig3_A2A4 zigzag.
            "play_hash": "cn04-65d47d14",
            "candidates": [(_ensemble_solver(80000), {})],
            "gold_max_len": 4000,
        },
    }


def _served_info(arcade: Arcade) -> dict[str, Any]:
    """Map base game id -> served env_info (for title / baseline_actions)."""
    out: dict[str, Any] = {}
    for e in arcade.get_environments():
        b = _base_id(e.game_id)
        out.setdefault(b, e)
    return out


def generate_for_game(
    arcade: Arcade,
    base: str,
    spec: dict,
    served: Any,
) -> dict[str, Any]:
    """Run the matching brittle solver on one game and write its .npz."""
    play_gid = spec["play_hash"]
    env = arcade.make(play_gid)
    if env is None:
        return {"game_id": play_gid, "base_game": base, "error": "make() returned None"}

    title = (getattr(served, "title", "") or base.upper()) if served else base.upper()
    baseline = list(getattr(served, "baseline_actions", []) or []) if served else []

    # Capture win_levels NOW: after the solver leaves the env mid-probe, a later
    # read of observation_space.win_levels can report 0 (frameless/terminal
    # state). Fall back to the served per-level human baseline length.
    win_levels = int(getattr(env.observation_space, "win_levels", 0) or 0)
    if win_levels == 0:
        win_levels = len(baseline)

    collector = TraceCollector(gold_max_len=spec["gold_max_len"])
    rec_env = RecordingEnv(env, collector)

    start = time.time()
    best_levels, best_name = 0, ""
    tried: list[dict] = []
    for fn, kwargs in spec["candidates"]:
        try:
            levels, name, used = fn(rec_env, **kwargs)
        except Exception as exc:  # noqa: BLE001 - report, try next candidate
            traceback.print_exc()
            tried.append({"fn": getattr(fn, "__name__", "solver"), "error": repr(exc)})
            continue
        tried.append({"fn": getattr(fn, "__name__", "solver"), "levels": int(levels), "actions": int(used)})
        if levels > best_levels:
            best_levels, best_name = int(levels), name or getattr(fn, "__name__", "")
        if levels > 0:
            break
    collector.finalize()
    elapsed = time.time() - start

    records = collector.gold + collector.explore
    n_total = len(records)
    n_gold = len(collector.gold)
    gold_levels = sorted({r["level_index"] for r in collector.gold})

    meta = {
        "game_id": play_gid,
        "base_game": base,
        "title": title,
        "num_layers": collector.num_layers,
        "win_levels": win_levels,
        "baseline_actions": baseline,
        "source": "brittle_solver",
        "frame_layout": "canonical_layer0_uint8",
        "n_total": n_total,
        "n_gold": n_gold,
        "n_explore": len(collector.explore),
        "gold_level_indices": gold_levels,
        "max_levels_seen": collector.max_levels_seen,
        "elapsed_s": round(elapsed, 2),
        "cleared": best_levels > 0,
        "levels_completed": best_levels,
        "strategy": best_name,
        "candidates_tried": tried,
    }

    if n_total == 0:
        meta["written"] = False
        return meta

    out_path = _OUT_DIR / f"{base}.npz"
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


def _update_index(updated: dict[str, dict]) -> None:
    """Rewrite ONLY the touched games' entries in data/traces/index.json."""
    index_path = _OUT_DIR / "index.json"
    index = json.loads(index_path.read_text())
    games = index.get("games", [])
    by_base = {g.get("base_game"): i for i, g in enumerate(games)}
    for base, meta in updated.items():
        entry = {k: v for k, v in meta.items() if k != "candidates_tried"}
        if base in by_base:
            games[by_base[base]] = entry
        else:
            games.append(entry)
    index["games"] = games
    # Recompute summary from the (now-updated) full list.
    index["summary"] = {
        "games_total": len(games),
        "games_with_gold": sum(1 for g in games if g.get("n_gold", 0) > 0),
        "total_gold_transitions": sum(g.get("n_gold", 0) for g in games),
        "total_transitions": sum(g.get("n_total", 0) for g in games),
    }
    index_path.write_text(json.dumps(index, indent=2))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--games", default="all", help="Comma-separated base ids or 'all'.")
    args = p.parse_args()

    plan = _build_plan()
    if args.games.strip().lower() == "all":
        wanted = list(plan)
    else:
        wanted = [g.strip().lower() for g in args.games.split(",") if g.strip()]

    arcade = Arcade(operation_mode=OperationMode.NORMAL)
    served = _served_info(arcade)

    updated: dict[str, dict] = {}
    for base in wanted:
        if base not in plan:
            print(f"[skip] {base}: not in plan")
            continue
        print(f"[run] {base} via {plan[base]['play_hash']} ...", flush=True)
        meta = generate_for_game(arcade, base, plan[base], served.get(base))
        updated[base] = meta
        print(
            f"   -> gold={meta.get('n_gold', 0)} explore={meta.get('n_explore', 0)} "
            f"levels={meta.get('levels_completed', 0)}/{meta.get('win_levels', '?')} "
            f"gold_levels={meta.get('gold_level_indices', [])} "
            f"strat={meta.get('strategy', '')!r} {meta.get('elapsed_s', 0)}s"
            + (f"  ERROR: {meta['error']}" if "error" in meta else "")
        )

    if updated:
        _update_index(updated)
        print(f"\nindex.json updated for: {sorted(updated)}")


if __name__ == "__main__":
    main()
