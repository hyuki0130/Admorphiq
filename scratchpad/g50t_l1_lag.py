"""g50t L1: precise lag calibration for the CORRECTLY-tracked (moving) player.

Issue an unambiguous sequence from the open col-8 corridor and log the observed
player cell each frame, so we know exactly how many frames after issuing a move
its displacement appears. The wiki claims lag-2 (measured on the buggy goal-track);
stage-2 suggested lag-1 for the real player. Pin it.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.g50t import Adapter
from admorphiq.adapters25.base import canonical_layer
from admorphiq.kernels import find_regions

A = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3,
     4: GameAction.ACTION4, 5: GameAction.ACTION5}
CELL = 6


def reach_l1(env, obs):
    ad = Adapter(giveup=2000)
    s = 0
    while s < 2000 and int(getattr(obs, "levels_completed", 0) or 0) < 1 and not ad.is_done([], obs):
        a = ad.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        s += 1
    return obs


def nine(grid):
    return [r for r in find_regions(grid, background=None)
            if r["color"] == 9 and 7 <= r["bbox"][0] <= 58 and 8 <= r["size"] <= 40]


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("g50t")
    obs = reach_l1(env, env.observation_space)
    if int(getattr(obs, "levels_completed", 0) or 0) != 1:
        print("no L1"); return
    grid = canonical_layer(env.step(A[2]))
    id_cells = [(r["centroid"][0], r["centroid"][1]) for r in nine(grid)]
    off = pcell = gcell = None
    for a in [2, 4, 1, 3, 2, 4, 1, 3]:
        grid = canonical_layer(env.step(A[a]))
        now = [(r["centroid"][0], r["centroid"][1]) for r in nine(grid)]
        moved = [c for c in now if all(abs(c[0]-o[0])+abs(c[1]-o[1]) > 2 for o in id_cells)]
        static = [c for c in now if any(abs(c[0]-o[0])+abs(c[1]-o[1]) <= 2 for o in id_cells)]
        if moved:
            off = (int(round(moved[0][0])) % CELL, int(round(moved[0][1])) % CELL)
            gcell = (round((static[0][0]-off[0])/CELL), round((static[0][1]-off[1])/CELL)) if static else None
            break
        id_cells = now

    def pc(grid):
        cands = [(round((r["centroid"][0]-off[0])/CELL), round((r["centroid"][1]-off[1])/CELL)) for r in nine(grid)]
        cands = [c for c in cands if c != gcell] or cands
        return cands

    names = {1: "UP", 2: "DN", 3: "LF", 4: "RT"}
    # A known sequence: UP x5 (climb col8), then LF x3, then DN x2
    seq = [1, 1, 1, 1, 1, 3, 3, 3, 2, 2]
    print(f"off={off} goal={gcell}  player cells before seq: {pc(grid)}")
    print("issue -> observed player cells (all non-goal colour-9)")
    for k, a in enumerate(seq):
        grid = canonical_layer(env.step(A[a]))
        print(f"  issue{k:2d} {names[a]} -> {pc(grid)}")


if __name__ == "__main__":
    main()
