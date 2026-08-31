"""g50t L1: measure the TRUE ghost-B replay gating (when does barrier B open in
phase 2, in units of my displacements?).

Seat ghost B on plate B, rewind, then in phase 2 drive to (8,7) [adjacent to
barrier (8,6)] and repeatedly try LEFT onto (8,6), bouncing to add displacements,
reporting the displacement count at which the crossing first succeeds. That pins
whether the ghost seats at Lg=displacements or Lg=issued-moves.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.g50t import Adapter
from admorphiq.adapters25.base import canonical_layer
from g50t_l1_solve3 import Solver, reach_l1, frontier8, reach_set
from g50t_l1_slam8 import MOVE

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
    cands = sorted(frontier8(s, reach0))
    plate_b = None
    for cand in cands:
        fb = s.floor(s._grid)
        ok, d = s.drive_gated(cand, [], enter=cand)
        if ok and (s.floor(s._grid) - fb - {cand}):
            plate_b, lg_b_disp = cand, d
            break
    print(f"plate B={plate_b} Lg_B(disp)={lg_b_disp} steps_used={s.steps}")
    s._grid = s.step(5)  # ACTION5
    s.settle_rewind(spawn)
    s.player_cell = s.obs_player(s._grid) or s.player_cell
    print(f"after A5+rewind: player={s.player_cell}")

    # drive to (8,7) ungated (it's reachable without the barrier)
    ok, d0 = s.drive_gated((8, 7), [], enter=None)
    print(f"drive to (8,7): ok={ok} player={s.player_cell} disp_this_drive={d0}")
    # now bounce (8,7)<->(8,8) counting displacements, trying LEFT onto (8,6) each cycle
    disp = d0
    for k in range(20):
        # try LEFT onto (8,6)
        frm = s.player_cell
        s._grid, moved = s.hop(s._grid, 3, enter=None)  # LEFT
        if moved:
            disp += 1
        if s.player_cell == (8, 6) or (s.player_cell[1] < 7 and s.player_cell[0] == 8):
            print(f"  CROSSED barrier at disp={disp} player={s.player_cell}")
            break
        # if didn't cross, bounce right then it will try left again next iter
        if s.player_cell == (8, 7):
            s._grid, m2 = s.hop(s._grid, 4, enter=None)  # RIGHT to (8,8)
            if m2:
                disp += 1
        print(f"  k={k} disp={disp} player={s.player_cell} (barrier still closed)")


if __name__ == "__main__":
    main()
