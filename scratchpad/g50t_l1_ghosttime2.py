"""g50t L1: does ACTION5 ghost B actually seat & hold barrier B open? Record the
exact phase-1 issued action sequence, press ACTION5, replay the SAME sequence
open-loop, and log blob count + barrier(8,6) colour + reach each step. This
isolates the ghost MECHANIC from the multi-blob perception problem.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.g50t import Adapter
from admorphiq.adapters25.base import canonical_layer, state_name
from g50t_l1_solve3 import Solver, reach_l1, frontier8, reach_set
from g50t_l1_slam8 import MOVE, nine

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

    # phase 1 to plate B, recording the EXACT issued actions
    issued = []
    orig_step = s.step
    def rec_step(a):
        issued.append(a)
        return orig_step(a)
    s.step = rec_step

    cands = sorted(frontier8(s, reach0))
    plate_b = None
    for cand in cands:
        fb = s.floor(s._grid)
        ok, d = s.drive_gated(cand, [], enter=cand)
        if ok and (s.floor(s._grid) - fb - {cand}):
            plate_b, lg_disp = cand, d
            break
    print(f"plate B={plate_b} Lg_disp={lg_disp}")
    print(f"phase-1 issued {len(issued)} actions to reach plate B (incl wall-bumps): {issued}")
    # displacing subset:
    print(f"barrier(8,6) colour on plate: {s.color(s._grid,(8,6))}  reach={len(reach_set(s, s.floor(s._grid), plate_b))}")

    # ACTION5
    s.step = orig_step
    s._grid = orig_step(5)
    # count blobs right after A5
    def blobs(grid):
        return [(round(r['centroid'][0],1), round(r['centroid'][1],1), r['size']) for r in nine(grid)]
    print(f"immediately post-A5: state={state_name(env.observation_space) if False else '?'} blobs={blobs(s._grid)}")

    # replay the phase-1 issued sequence open-loop, watch barrier + blobs
    for k, a in enumerate(issued):
        s._grid = orig_step(a)
        st = None
        b = blobs(s._grid)
        bc = s.color(s._grid, (8, 6)) if s.off else '?'
        print(f"  replay{k:2d} act={a} blobs={len(b)} barrier(8,6)col={bc}  {b}")
        if len(b) == 0:
            print("   -> frame blank (level lost/over)"); break


if __name__ == "__main__":
    main()
