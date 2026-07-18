"""g50t L1 anchor2 (task #83): test the PLAIN //6 absolute cell mapping.

The task-#83 finding: colour-5 floor bbox is stable (7,7,55,55) x3, and reading
blobs via bbox_topleft//6 gives goal cell (3,4) = the ENGINE goal cell. So the
render grid == engine grid under plain floor-division (origin 0) — the prior
"offset instability" was `centroid%6` offset-derivation, a bug.

This validates: (a) SETTLE non-displacing (left-nudge; LEFT is walled at spawn),
(b) parse spawn via probe-motion + //6, (c) confirm spawn/goal/plate cells match
the engine constants spawn(4,8) plateB(4,6) plateA(6,2) goal(3,4) — x3 runs.
If stable and matching, absolute engine constants are usable at runtime.
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
    """colour-9 blobs in the play area, as (cell, size, bbox)."""
    out = []
    for reg in find_regions(grid, background=None):
        if reg["color"] != MOVER:
            continue
        r0, c0 = reg["bbox"][0], reg["bbox"][1]
        if r0 < 7 or r0 > 58 or not (8 <= reg["size"] <= 40):
            continue
        out.append(((r0 // CELL, c0 // CELL), reg["size"], reg["bbox"]))
    return out


def floor_cells(grid):
    """colour-5 floor cells via plain //6, cropping the HUD rows."""
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


def settle_stable(env, obs, nudge, max_steps=12):
    """Issue `nudge` (an expected-walled action) until 2 consecutive byte-identical
    frames — settles the level-transition artifact WITHOUT displacing the player if
    `nudge` is truly walled."""
    prev = canonical_layer(obs)
    for _ in range(max_steps):
        obs = env.step(A[nudge])
        cur = canonical_layer(obs)
        if cur == prev:
            return obs, cur
        prev = cur
    return obs, canonical_layer(obs)


def run_once(tag):
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("g50t")
    obs = reach_l1(env, env.observation_space)
    if int(getattr(obs, "levels_completed", 0) or 0) != 1:
        print(f"[{tag}] no L1"); return None
    # settle with LEFT (walled at spawn per wiki); confirm player did not move
    grid0 = canonical_layer(obs)
    m0 = movers(grid0)
    obs, grid = settle_stable(env, obs, nudge=3)
    m = movers(grid)
    fl = floor_cells(grid)
    # probe motion: issue DOWN, flush LAG, see which colour-9 cell changed
    cells_before = {c for c, _, _ in m}
    for _ in range(1 + LAG):
        obs = env.step(A[2])
    gp = canonical_layer(obs)
    mp = movers(gp)
    cells_after = {c for c, _, _ in mp}
    moved_from = cells_before - cells_after
    moved_to = cells_after - cells_before
    static = cells_before & cells_after
    spawn = next(iter(moved_from)) if moved_from else None
    goal = next(iter(static)) if static else None
    reach = reachable(fl, spawn) if spawn else set()
    plateB, plateA, goalc = (4, 6), (6, 2), (3, 4)
    print(f"[{tag}] settled movers(cell,size)={[(c, s) for c, s, _ in m]}")
    print(f"[{tag}]   spawn={spawn} goal={goal} moved_to={moved_to} floor={len(fl)} reach={len(reach)}")
    print(f"[{tag}]   engine-const check: spawn==(4,8)? {spawn == (4, 8)}  goal==(3,4)? {goal == goalc}")
    print(f"[{tag}]   plateB(4,6) in floor? {plateB in fl}  reach-adj? "
          f"{any((plateB[0]+dr, plateB[1]+dc) in reach for dr, dc in MV.values())}")
    print(f"[{tag}]   plateA(6,2) reach-adj? "
          f"{any((plateA[0]+dr, plateA[1]+dc) in reach for dr, dc in MV.values())}  "
          f"goal(3,4) in reach? {goalc in reach}")
    return (spawn, goal, frozenset(fl))


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    res = [run_once(f"run{i}") for i in range(n)]
    res = [r for r in res if r]
    spawns = {r[0] for r in res}
    goals = {r[1] for r in res}
    floors = {r[2] for r in res}
    print(f"\nspawn stable x{len(res)}: {len(spawns) == 1} {spawns}")
    print(f"goal  stable x{len(res)}: {len(goals) == 1} {goals}")
    print(f"floor stable x{len(res)}: {len(floors) == 1} (sizes {[len(f) for f in floors]})")


if __name__ == "__main__":
    main()
