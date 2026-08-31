"""g50t L1: pin the ghost-B replay CLOCK. After ACTION5, drive the player on a
DIFFERENT path (fixed bounce, not path_B) and count env.steps until barrier
(8,6) opens. If it opens at ~len(path_B) env.steps regardless of my direction,
the ghost replays on issued-move-count; if it tracks my displacements, count
those. Also report whether a 2nd (ghost) blob separates from the player.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.base import canonical_layer, state_name
from g50t_l1_solve3 import Solver, reach_l1, frontier8, reach_set
from g50t_l1_slam8 import nine

A = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3,
     4: GameAction.ACTION4, 5: GameAction.ACTION5}


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("g50t")
    obs = reach_l1(env, env.observation_space)
    if int(getattr(obs, "levels_completed", 0) or 0) != 1:
        print("no L1"); return
    s = Solver(env)
    s._grid = s.identify()
    spawn = s.player_cell
    floor0 = s.floor(s._grid)
    reach0 = reach_set(s, floor0, spawn)
    n_before_a5 = s.steps
    cands = sorted(frontier8(s, reach0))
    for cand in cands:
        fb = s.floor(s._grid)
        ok, d = s.drive_gated(cand, [], enter=cand)
        if ok and (s.floor(s._grid) - fb - {cand}):
            break
    path_len = s.steps - n_before_a5
    print(f"path_B env.steps={path_len} (from level start incl identify={s.steps})")
    s._grid = s.step(5)  # ACTION5

    def blobs(grid):
        return [(round(r['centroid'][0], 1), round(r['centroid'][1], 1), r['size']) for r in nine(grid)]

    # bounce the player UP/DOWN in the right column (far from plate B on the left),
    # counting env.steps until barrier(8,6) opens.
    opened_at = None
    for k in range(120):
        act = 1 if k % 2 == 0 else 2  # UP/DOWN bounce
        s._grid = s.step(act)
        col = s.color(s._grid, (8, 6))
        b = blobs(s._grid)
        if col == 5:
            opened_at = k
            print(f"  BARRIER OPENED at env.step {k} (blobs={len(b)}): {b}")
            break
        if k < 6 or k % 10 == 0:
            print(f"  step{k:3d} act={act} barrier(8,6)col={col} blobs={len(b)} {b}")
        if len(b) == 0 or state_name(env.observation_space) == "GAME_OVER":
            print(f"  level lost at step {k}"); break
    print(f"RESULT: path_B_steps={path_len}, barrier opened at phase2 env.step={opened_at}")


if __name__ == "__main__":
    main()
