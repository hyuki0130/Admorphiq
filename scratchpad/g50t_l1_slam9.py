"""g50t L1 SLAM stage 9: ghost-B seat test. Drive to plate B, press ACTION5,
observe: does the player rewind to spawn, does ghost B seat & hold barrier B
open, and does plate A / the goal region become reachable?
"""
from __future__ import annotations

import sys
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.g50t import Adapter
from admorphiq.adapters25.base import canonical_layer
from g50t_l1_slam8 import L1, nine, reach_set, MOVE, CELL  # reuse the driver

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


def dump(g, grid, tag):
    off = g.off
    h, w = len(grid), len(grid[0])
    nrows = (h-off[0])//CELL+1; ncols = (w-off[1])//CELL+1
    floor = g.floor(grid)
    reach = reach_set(g, floor, g.player_cell)
    print(f"[{tag}] player={g.player_cell} floor={len(floor)} reach={len(reach)} goal_in={g.goal_cell in reach}")
    # count colour-9 blobs (players + ghosts + goal)
    n9 = [(round(r['centroid'][0],1), round(r['centroid'][1],1), r['size']) for r in nine(grid)]
    print(f"       colour-9 blobs: {n9}")


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("g50t")
    obs = reach_l1(env, env.observation_space)
    if int(getattr(obs, "levels_completed", 0) or 0) != 1:
        print("no L1"); return
    g = L1(env)
    grid = g.identify()
    spawn = g.player_cell
    dump(g, grid, "start")
    plate_b = (4, 6)
    grid, ok = g.drive(grid, plate_b, enter=plate_b)
    lg_b = None
    print(f"drive->B arrived={ok} player={g.player_cell} steps={g.steps}")
    if not ok:
        return
    dump(g, grid, "on-plate-B")
    # press ACTION5 to bank ghost B
    grid = canonical_layer(env.step(A[5])); g.steps += 1
    # settle: wait for rewind (player back near spawn). issue a few reads.
    for _ in range(8):
        obs_p = g.obs_player(grid)
        if obs_p is not None:
            g.player_cell = obs_p
        dump(g, grid, f"post-A5")
        if g.player_cell == spawn:
            break
        grid = canonical_layer(env.step(A[g.wall_bump(grid, g.player_cell) or 1])); g.steps += 1
    print(f"final player after A5 settle: {g.player_cell} (spawn={spawn})")
    dump(g, grid, "after-A5-settle")


if __name__ == "__main__":
    main()
