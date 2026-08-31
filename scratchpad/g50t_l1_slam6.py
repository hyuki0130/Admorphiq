"""g50t L1 SLAM stage 6: dump the maze geometry (floor + colour-8 + goal) as an
ASCII grid, and the reachable region from the player, to plan the real routing.
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
from admorphiq.kernels import find_regions

A = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3,
     4: GameAction.ACTION4, 5: GameAction.ACTION5}
CELL = 6
MOVE = {1: (-1, 0), 2: (1, 0), 3: (0, -1), 4: (0, 1)}


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
    grid = canonical_layer(env.step(A[2]))  # snap
    # identify
    id_cells = [(r["centroid"][0], r["centroid"][1]) for r in nine(grid)]
    off = player_cell = goal_cell = None
    for a in [2, 4, 1, 3, 2, 4, 1, 3]:
        grid = canonical_layer(env.step(A[a]))
        now = [(r["centroid"][0], r["centroid"][1]) for r in nine(grid)]
        moved = [c for c in now if all(abs(c[0]-o[0])+abs(c[1]-o[1]) > 2 for o in id_cells)]
        static = [c for c in now if any(abs(c[0]-o[0])+abs(c[1]-o[1]) <= 2 for o in id_cells)]
        if moved:
            off = (int(round(moved[0][0])) % CELL, int(round(moved[0][1])) % CELL)
            player_cell = (round((moved[0][0]-off[0])/CELL), round((moved[0][1]-off[1])/CELL))
            goal_cell = (round((static[0][0]-off[0])/CELL), round((static[0][1]-off[1])/CELL)) if static else None
            break
        id_cells = now
    print(f"off={off} player={player_cell} goal={goal_cell}")

    h, w = len(grid), len(grid[0])
    ncols = (w - off[1]) // CELL + 1
    nrows = (h - off[0]) // CELL + 1

    def color(i, j):
        r, c = off[0]+i*CELL, off[1]+j*CELL
        if 0 <= r < h and 0 <= c < w:
            return grid[r][c]
        return -1

    floor = {(i, j) for i in range(nrows) for j in range(ncols) if color(i, j) == 5}
    seen = {player_cell}; q = deque([player_cell])
    while q:
        cur = q.popleft()
        for dr, dc in MOVE.values():
            n = (cur[0]+dr, cur[1]+dc)
            if n in floor and n not in seen:
                seen.add(n); q.append(n)

    print(f"grid {nrows}x{ncols}  floor={len(floor)} reach={len(seen)}")
    print("legend: P=player G=goal .=floor(reach) o=floor(unreach) #=colour8 space=other")
    for i in range(nrows):
        line = ""
        for j in range(ncols):
            cell = (i, j)
            if cell == player_cell: line += "P"
            elif cell == goal_cell: line += "G"
            elif color(i, j) == 8: line += "#"
            elif cell in seen: line += "."
            elif cell in floor: line += "o"
            elif color(i, j) == 5: line += "."
            else: line += " "
        print(f"{i:2d} {line}")


if __name__ == "__main__":
    main()
