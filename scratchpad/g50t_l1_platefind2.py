"""g50t L1 plate-finder v2 — sweep ALL frame-reachable cells with the LAG-2
wall-learning driver (not the naive closed-loop stepper, which cannot cross the
sprite-mask lateral walls and only reached 14/21 cells). For each cell the
driver genuinely reaches, report ANY floor change (added OR removed), excluding
the player-occupied cell and the spawn-reveal cell. Whatever changes the floor
is the plate; the sign is the polarity.
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
from admorphiq.kernels import configuration_path, find_regions

A = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3, 4: GameAction.ACTION4, 5: GameAction.ACTION5}
CELL, FLOOR, MOVER, CIRCUIT = 6, 5, 9, 8
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


def derive_off(grid):
    for reg in find_regions(grid, background=None):
        if reg["color"] == MOVER and 8 <= reg["size"] <= 40 and 7 <= reg["bbox"][0] <= 58:
            cy, cx = reg["centroid"]
            return (int(round(cy)) % CELL, int(round(cx)) % CELL)
    return None


def movers(grid, off):
    out = []
    for reg in find_regions(grid, background=None):
        if reg["color"] != MOVER or not (7 <= reg["bbox"][0] <= 58 and 8 <= reg["size"] <= 40):
            continue
        cy, cx = reg["centroid"]
        out.append((round((cy - off[0]) / CELL), round((cx - off[1]) / CELL)))
    return out


def pcell(grid, off, goal):
    ms = movers(grid, off)
    cs = [c for c in ms if c != goal]
    return cs[0] if cs else (ms[0] if ms else None)


def cell_color(grid, off, cell):
    r, c = off[0] + cell[0] * CELL, off[1] + cell[1] * CELL
    if 0 <= r < len(grid) and 0 <= c < len(grid[0]):
        return grid[r][c]
    return -1


def floor_cells(grid, off):
    h, w = len(grid), len(grid[0])
    cells = set()
    i = 0
    while off[0] + i * CELL < h and i < HUD_ROW:
        j = 0
        while off[1] + j * CELL < w:
            if grid[off[0] + i * CELL][off[1] + j * CELL] == FLOOR:
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
                seen.add(n); q.append(n)
    return seen


def detect_goal(env, obs, off):
    frames = []
    for a in (2, 4, 2, 4, 1, 3, 2, 4):
        obs = env.step(A[a])
        frames.append(set(movers(canonical_layer(obs), off)))
    common = set.intersection(*frames[-5:]) if frames else set()
    return obs, (next(iter(common)) if common else None)


def plan(floor, blocked, start, goal):
    def succ(state):
        for a, (dr, dc) in MV.items():
            n = (state[0] + dr, state[1] + dc)
            if (state, a) in blocked:
                continue
            if n == goal or n in floor:
                yield a, n
    return configuration_path(start, lambda s: s == goal, succ, max_states=200_000)


def drive_to(env, obs, off, goal, floor, blocked, target):
    """lag-2 plan/execute/verify/learn-wall to `target`. Returns (obs, reached)."""
    for _ in range(10):
        grid = canonical_layer(obs)
        conf = pcell(grid, off, goal)
        if conf == target:
            return obs, True
        pth = plan(floor, blocked, conf, target)
        if not pth:
            return obs, False
        exp = [conf]
        for a in pth:
            dr, dc = MV[a]
            exp.append((exp[-1][0] + dr, exp[-1][1] + dc))
        obslog = [conf]
        for a in pth:
            obs = env.step(A[a])
            obslog.append(pcell(canonical_layer(obs), off, goal))
        for _ in range(LAG):
            obs = env.step(A[1])
            obslog.append(pcell(canonical_layer(obs), off, goal))
        conf_cell = conf
        wall = False
        for k in range(len(pth)):
            actual = obslog[k + LAG] if k + LAG < len(obslog) else None
            if actual is None:
                break
            if actual == exp[k + 1]:
                conf_cell = actual
                continue
            blocked.add((exp[k], pth[k]))
            wall = True
            break
        if not wall and conf_cell == target:
            return obs, True
    return obs, pcell(canonical_layer(obs), off, goal) == target


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("g50t")
    obs = reach_l1(env, env.observation_space)
    if int(getattr(obs, "levels_completed", 0) or 0) != 1:
        print("no L1"); return
    off = derive_off(canonical_layer(obs))
    obs, goal = detect_goal(env, obs, off)
    for _ in range(4):
        obs = env.step(A[1])
    off = derive_off(canonical_layer(obs)) or off
    grid = canonical_layer(obs)
    spawn = pcell(grid, off, goal)
    base_floor = floor_cells(grid, off) | {spawn}   # count spawn as floor (player occludes it)
    reach = reachable(floor_cells(grid, off), spawn) | {spawn}
    cands = set()
    for cell in reach:
        for dr, dc in MV.values():
            n = (cell[0] + dr, cell[1] + dc)
            if n not in reach and cell_color(grid, off, n) == CIRCUIT:
                cands.add(n)
    targets = sorted(reach) + sorted(cands)
    print(f"off {off} spawn {spawn} goal {goal} base_floor {len(base_floor)} reach {len(reach)} cands {sorted(cands)}")

    blocked: set = set()
    reached_cells = []
    for tgt in targets:
        obs, ok = drive_to(env, obs, off, goal, base_floor, blocked, tgt)
        if not ok:
            continue
        reached_cells.append(tgt)
        g = canonical_layer(obs)
        p = pcell(g, off, goal)
        fnow = floor_cells(g, off) | ({p} if p else set())
        added = fnow - base_floor
        removed = base_floor - fnow
        if added or removed:
            print(f"  STOOD {tgt}: added={sorted(added)} removed={sorted(removed)}  <-- PLATE?")
    print(f"reached {len(reached_cells)}/{len(targets)} cells: {reached_cells}")
    print(f"learned walls: {sorted(blocked)}")


if __name__ == "__main__":
    main()
