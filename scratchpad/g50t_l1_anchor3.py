"""g50t L1 anchor3 (task #83): capture SPAWN at the transition frame, before any
displacement, and confirm it parses to the engine spawn cell (4,8) x3.

Method: reach_l1 returns the FIRST L1 frame (player at spawn). Read the two
colour-9 cells RAW (candidates). Then probe motion: issue one move + LAG flush;
the candidate that vanished = spawn (pre-probe cell), the static = goal. Cycle
directions until motion is seen. Report spawn/goal cells and whether the plain
//6 mapping matches engine constants spawn(4,8) plateB(4,6) plateA(6,2) goal(3,4).
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
CELL, FLOOR, MOVER = 6, 5, 9
MV = {1: (-1, 0), 2: (1, 0), 3: (0, -1), 4: (0, 1)}
LAG = 2
HUD_ROW = 9


def reach_l1(env, obs):
    ad = Adapter(giveup=2000)
    s = 0
    while s < 2000 and int(getattr(obs, "levels_completed", 0) or 0) < 1 and not ad.is_done([], obs):
        a = ad.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        s += 1
    return obs


def movers(grid):
    out = []
    for reg in find_regions(grid, background=None):
        if reg["color"] != MOVER:
            continue
        r0, c0 = reg["bbox"][0], reg["bbox"][1]
        if r0 < 7 or r0 > 58 or not (8 <= reg["size"] <= 40):
            continue
        out.append((r0 // CELL, c0 // CELL))
    return out


def floor_cells(grid):
    h, w = len(grid), len(grid[0])
    cells = set()
    i = 0
    while i * CELL + 3 < h and i < HUD_ROW:
        j = 0
        while j * CELL + 3 < w:
            if grid[i * CELL + 3][j * CELL + 3] == FLOOR:
                cells.add((i, j))
            j += 1
        i += 1
    return cells


def reachable(floor, start):
    seen = {start}
    q = deque([start])
    while q:
        cur = q.popleft()
        for dr, dc in MV.values():
            n = (cur[0] + dr, cur[1] + dc)
            if n in floor and n not in seen:
                seen.add(n)
                q.append(n)
    return seen


def run_once(tag):
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("g50t")
    obs = reach_l1(env, env.observation_space)
    if int(getattr(obs, "levels_completed", 0) or 0) != 1:
        print(f"[{tag}] no L1"); return None
    grid0 = canonical_layer(obs)
    cand = set(movers(grid0))
    print(f"[{tag}] raw L1 movers cells = {sorted(cand)}")
    spawn = goal = None
    # probe directions in order; capture spawn = mover's pre-probe cell.
    for d in (2, 1, 4, 3):
        before = set(movers(canonical_layer(obs)))
        for _ in range(1 + LAG):
            obs = env.step(A[d])
        after = set(movers(canonical_layer(obs)))
        moved_from = before - after
        static = before & after
        if moved_from:
            spawn = next(iter(moved_from))
            goal = next(iter(static)) if static else None
            print(f"[{tag}] probe dir={d} moved_from={sorted(moved_from)} -> spawn={spawn} goal={goal}")
            break
        else:
            print(f"[{tag}] probe dir={d} no motion (before={sorted(before)})")
    fl = floor_cells(grid0)
    reach = reachable(fl, spawn) if spawn else set()
    plateB, plateA, goalc = (4, 6), (6, 2), (3, 4)
    print(f"[{tag}]   spawn==(4,8)? {spawn == (4, 8)}  goal==(3,4)? {goal == goalc}  "
          f"floor={len(fl)} reach={len(reach)}")
    print(f"[{tag}]   plateB(4,6) reach-adj? "
          f"{any((plateB[0]+dr, plateB[1]+dc) in reach for dr, dc in MV.values())}  "
          f"plateA(6,2) reach-adj? {any((plateA[0]+dr, plateA[1]+dc) in reach for dr, dc in MV.values())}  "
          f"goal in reach? {goalc in reach}")
    return (spawn, goal, frozenset(fl))


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    res = [r for r in (run_once(f"run{i}") for i in range(n)) if r]
    spawns = {r[0] for r in res}
    goals = {r[1] for r in res}
    floors = {r[2] for r in res}
    print(f"\nspawn stable x{len(res)}: {len(spawns) == 1} {spawns}")
    print(f"goal  stable x{len(res)}: {len(goals) == 1} {goals}")
    print(f"floor stable x{len(res)}: {len(floors) == 1} (sizes {[len(f) for f in floors]})")


if __name__ == "__main__":
    main()
