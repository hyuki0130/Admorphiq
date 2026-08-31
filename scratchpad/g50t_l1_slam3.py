"""g50t L1 SLAM stage 3: track the REAL (moving) player, verify the world is
static after the one-time transition snap, and test goal reachability over the
frame floor.

Hypothesis (from stage 2): the "camera-lock scrolling" bank was a tracking bug —
the prior tracker's min() locked onto the STATIC GOAL blob (colour-9, size~19).
The real player is the MOVING colour-9 blob (size~24). After the level's one-time
transition snap the camera is FIXED and the player moves normally in absolute
frame cells. If so, L1 is a plain frame-readable maze + the L0 plate/ghost circuit.
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
CELL, FLOOR = 6, 5
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
    out = []
    for reg in find_regions(grid, background=None):
        if reg["color"] != 9:
            continue
        r0 = reg["bbox"][0]
        if r0 < 7 or r0 > 58 or not (8 <= reg["size"] <= 40):
            continue
        out.append(reg)
    return out


def floor_cells(grid, off):
    h, w = len(grid), len(grid[0])
    cells = set()
    i = 0
    while off[0] + i * CELL < h - 2:
        j = 0
        while off[1] + j * CELL < w - 2:
            r, c = off[0] + i * CELL, off[1] + j * CELL
            if grid[r][c] == FLOOR:
                cells.add((i, j))
            j += 1
        i += 1
    return cells


def to_cell(centroid, off):
    return (round((centroid[0] - off[0]) / CELL), round((centroid[1] - off[1]) / CELL))


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("g50t")
    obs = reach_l1(env, env.observation_space)
    if int(getattr(obs, "levels_completed", 0) or 0) != 1:
        print("no L1")
        return
    # settle the one-time transition snap: issue a probe move, then track.
    prev = {(round(r["centroid"][0], 1), round(r["centroid"][1], 1)) for r in nine(canonical_layer(obs))}
    obs = env.step(A[2])  # DN probe triggers the snap
    grid = canonical_layer(obs)
    regs = nine(grid)
    print("post-snap colour-9 blobs (cy,cx,size):",
          [(round(r["centroid"][0], 1), round(r["centroid"][1], 1), r["size"]) for r in regs])

    # identify player by motion: probe moves, the blob that DISPLACES is the player.
    id_cells = [(round(r["centroid"][0], 1), round(r["centroid"][1], 1)) for r in regs]
    player_c = None
    goal_c = None
    off = (int(round(regs[0]["centroid"][0])) % CELL, int(round(regs[0]["centroid"][1])) % CELL)
    for tryi, a in enumerate([2, 4, 1, 3, 2, 4, 1, 3]):
        obs = env.step(A[a])
        grid = canonical_layer(obs)
        regs = nine(grid)
        now = [(round(r["centroid"][0], 1), round(r["centroid"][1], 1)) for r in regs]
        moved = [c for c in now if c not in id_cells]
        static = [c for c in now if c in id_cells]
        if moved:
            player_c = moved[0]
            goal_c = static[0] if static else None
            print(f"identified after {tryi+1} probes: player_px={player_c} goal_px={goal_c}")
            break
        id_cells = now
    if player_c is None:
        print("could not identify moving player")
        return
    off = (int(round(player_c[0])) % CELL, int(round(player_c[1])) % CELL)
    pcell = to_cell(player_c, off)
    gcell = to_cell(goal_c, off) if goal_c else None
    print(f"off={off} player_cell={pcell} goal_cell={gcell}")

    floor = floor_cells(grid, off)
    print(f"floor cells: {len(floor)}")
    # BFS reachability from player over floor
    seen = {pcell}
    q = deque([pcell])
    while q:
        cur = q.popleft()
        for dr, dc in MOVE.values():
            n = (cur[0] + dr, cur[1] + dc)
            if n in floor and n not in seen:
                seen.add(n)
                q.append(n)
    print(f"reachable from player: {len(seen)} cells")
    if gcell:
        print(f"goal reachable over floor? {gcell in seen}  (goal_cell={gcell})")
        # goal +(1,1) too (win is goal+(1,1))
        print(f"goal+(1,1)={ (gcell[0]+1, gcell[1]+1) } reachable? {(gcell[0]+1, gcell[1]+1) in seen}")


if __name__ == "__main__":
    main()
