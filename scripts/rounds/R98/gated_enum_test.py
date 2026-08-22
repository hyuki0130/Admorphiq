"""R98 gated-enum prediction test — Codex binding correction 5.

Purpose
-------
Two questions, answered against the live engine:

1. **Faithfulness** — does the oracle response table, run through the reference
   propagator, reproduce what the engine actually does? Checked on the exact
   trajectory for the probe placements, and on the win/lose outcome plus the
   satisfied-sink count for EVERY reachable placement.
2. **Discriminability** — does each gated enum slot actually change a prediction?
   A slot that changes neither the predicted trajectory nor the predicted outcome
   on any reachable placement is decoration: the propagator's own behaviour would
   carry the run whatever the model picked, which manufactures a FALSE PASS. Such
   slots must be demoted to UNKNOWN / non-gating before the contract freezes.

Expected feedback
-----------------
Faithfulness FAIL blocks the freeze — the propagator, not the schema, is wrong.
A slot reported INERT is not a failure; it is an instruction to demote that slot.
Only slots reported DISCRIMINATING may be gated in the contract.
"""

from __future__ import annotations

import os
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from arc_agi import Arcade, OperationMode  # noqa: E402
from arcengine import GameAction  # noqa: E402
from reference_propagator import (  # noqa: E402
    ORACLE,
    SCALE,
    Prediction,
    predict,
    read_board,
)

FLOW = 6
SINK_SATISFIED = 13

SLOT_ALTERNATIVES = {
    "piece_spawn": ["both_flanks", "none"],
    "piece_direction": ["outward_turned"],
    "piece_propagation": ["edge_teleport"],
    "sink_predicate": ["contact"],
    "sink_miss": ["stop", "absorb"],
    "hazard": ["terminate_local", "pass_through"],
    "own_flow": ["overwrite", "terminate"],
    "boundary": ["reflect"],
}


def _cells(grid, colour: int) -> set[tuple[int, int]]:
    return {
        (y // SCALE, x // SCALE)
        for y, row in enumerate(grid)
        for x, v in enumerate(row)
        if v == colour
    }


def _fresh():
    arcade = Arcade(
        operation_mode=OperationMode.OFFLINE,
        environments_dir=os.environ.get("ARC_ENVIRONMENTS_DIR") or None,
    )
    gid = next(e.game_id for e in arcade.get_environments()
               if e.game_id.startswith("sp80"))
    env = arcade.make(gid)
    return env, env.step(GameAction.RESET)


def live_outcome(dx: int) -> dict:
    """Commit the layout dx cells right of entry and read the settle verdict."""
    env, obs = _fresh()
    for _ in range(abs(dx)):
        obs = env.step(GameAction.ACTION4 if dx > 0 else GameAction.ACTION3)
    obs = env.step(GameAction.ACTION5)

    satisfied_cells: set[tuple[int, int]] = set()
    trail: set[tuple[int, int]] = set()
    frontier: list[list[tuple[int, int]]] = []
    stopped = False

    def absorb(frame) -> bool:
        nonlocal stopped
        for layer in frame:
            water = _cells(layer, FLOW)
            if trail and water and not (trail <= water):
                return True
            satisfied_cells.update(_cells(layer, SINK_SATISFIED))
            frontier.append(sorted(water - trail))
            trail.update(water)
        return False

    stopped = absorb(obs.frame)
    advanced = obs.levels_completed >= 1
    if not advanced:
        for _ in range(30):
            obs = env.step(GameAction.ACTION5)
            if not stopped:
                stopped = absorb(obs.frame)
            if obs.levels_completed >= 1:
                advanced = True
                break

    groups: list[set[int]] = []
    for c in sorted({c for (_, c) in satisfied_cells}):
        if groups and c - max(groups[-1]) <= 1:
            groups[-1].add(c)
        else:
            groups.append({c})

    return {
        "dx": dx,
        "advanced": advanced,
        "sinks_filled": len(groups),
        "frontier": [f for f in frontier if f],
        "deepest": max((r for (r, _) in trail), default=-1),
    }


def _trajectory(p: Prediction) -> list[list[tuple[int, int]]]:
    return [f for f in p.frontier if f]


def main() -> int:
    _, obs = _fresh()
    entry = read_board(obs.frame[0])
    print(f"board: piece {sorted(entry.piece_cells)}")
    print(f"       sinks {[sorted(s) for s in entry.sinks]}")
    print(f"       emitter {sorted(entry.emitter_cells)} "
          f"standing flow {sorted(entry.standing_flow)}")
    print(f"       hazard cells {len(entry.hazard_cells)} on row "
          f"{sorted({r for (r, _) in entry.hazard_cells})}")

    placements = list(range(-3, 9))
    live = {dx: live_outcome(dx) for dx in placements}
    oracle_pred = {dx: predict(entry.moved(0, dx), ORACLE) for dx in placements}

    print("\n--- faithfulness: oracle table vs the live engine ---")
    outcome_ok = trajectory_ok = True
    for dx in placements:
        lv, pr = live[dx], oracle_pred[dx]
        same_outcome = (pr.wins == lv["advanced"]
                        and len(pr.satisfied) == lv["sinks_filled"])
        outcome_ok &= same_outcome
        flag = "ok " if same_outcome else "MISMATCH"
        print(f"  dx={dx:+d}  live(advanced={lv['advanced']}, sinks={lv['sinks_filled']})"
              f"  predicted(wins={pr.wins}, sinks={len(pr.satisfied)})  {flag}")

    for dx in (2, 3):
        lv_traj = live[dx]["frontier"]
        pr_traj = _trajectory(oracle_pred[dx])
        n = min(len(lv_traj), len(pr_traj))
        same = lv_traj[:n] == pr_traj[:n] and abs(len(lv_traj) - len(pr_traj)) <= 1
        trajectory_ok &= same
        print(f"  dx={dx:+d} trajectory: {'EXACT' if same else 'DIVERGES'} "
              f"({len(lv_traj)} live steps vs {len(pr_traj)} predicted)")
        if not same:
            for i in range(n):
                if lv_traj[i] != pr_traj[i]:
                    print(f"      first divergence at step {i}: "
                          f"live {lv_traj[i]} vs predicted {pr_traj[i]}")
                    break

    print("\n--- discriminability: does each gated slot change a prediction? ---")
    verdicts: dict[str, str] = {}
    for slot, alternatives in SLOT_ALTERNATIVES.items():
        rows = []
        for alt in alternatives:
            table = replace(ORACLE, **{slot: alt})
            traj_diff = outcome_diff = 0
            for dx in placements:
                pr = predict(entry.moved(0, dx), table)
                base = oracle_pred[dx]
                if _trajectory(pr) != _trajectory(base):
                    traj_diff += 1
                if (pr.wins, len(pr.satisfied)) != (base.wins, len(base.satisfied)):
                    outcome_diff += 1
            rows.append((alt, traj_diff, outcome_diff))
        best_traj = max(r[1] for r in rows)
        best_out = max(r[2] for r in rows)
        verdict = "DISCRIMINATING" if best_out else ("TRAJECTORY-ONLY" if best_traj
                                                     else "INERT")
        verdicts[slot] = verdict
        detail = ", ".join(f"{a}: {t}/{len(placements)} trajectories, "
                           f"{o}/{len(placements)} outcomes" for a, t, o in rows)
        print(f"  {slot:<18} {verdict:<15} [{detail}]")

    inert = [s for s, v in verdicts.items() if v == "INERT"]
    print(f"\n[faithfulness] {'PASS' if outcome_ok and trajectory_ok else 'FAIL'}")
    print(f"[gated slots]  {len(verdicts) - len(inert)}/{len(verdicts)} carry a "
          f"prediction; demote to non-gating: {inert or 'none'}")
    return 0 if outcome_ok and trajectory_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
