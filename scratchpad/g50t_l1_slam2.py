"""g50t L1 SLAM stage 2: is the player REALLY camera-locked, or were we tracking
the static GOAL blob (also colour-9)?

Dump EVERY colour-9 region (centroid, size, bbox) per step for a known move
sequence. If one blob moves while another stays fixed, the "locked at (3,4)"
reading was the static GOAL and the real player DOES move on screen -> the whole
camera-lock/SLAM premise needs revisiting.
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


def reach_l1(env, obs):
    ad = Adapter(giveup=2000)
    s = 0
    while s < 2000 and int(getattr(obs, "levels_completed", 0) or 0) < 1 and not ad.is_done([], obs):
        a = ad.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        s += 1
    return obs


def nine_regions(grid):
    out = []
    for reg in find_regions(grid, background=None):
        if reg["color"] != 9:
            continue
        cy, cx = reg["centroid"]
        out.append((round(cy, 1), round(cx, 1), reg["size"], reg["bbox"]))
    return sorted(out)


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("g50t")
    obs = reach_l1(env, env.observation_space)
    if int(getattr(obs, "levels_completed", 0) or 0) != 1:
        print("no L1")
        return
    grid = canonical_layer(obs)
    print("L1 start colour-9 regions (cy,cx,size,bbox):")
    for r in nine_regions(grid):
        print("   ", r)
    seq = [2, 2, 4, 4, 1, 1, 3, 3, 2, 4, 1, 3]
    names = {1: "UP", 2: "DN", 3: "LF", 4: "RT"}
    for k, a in enumerate(seq):
        obs = env.step(A[a])
        g = canonical_layer(obs)
        regs = nine_regions(g)
        print(f"step{k:2d} {names[a]}: " + " | ".join(f"({cy},{cx})s{sz}" for cy, cx, sz, _bb in regs))


if __name__ == "__main__":
    main()
