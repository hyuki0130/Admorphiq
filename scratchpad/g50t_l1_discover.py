"""g50t L1 FRAME-ONLY discovery diagnostic (offset-agnostic, no hardcoded cells).

Per the OFFSET INSTABILITY finding (commit f4f7f63): derive_off returns (4,4) OR
(4,5) run-to-run, so wiki cell constants (plate (4,6)/(6,2), goal (3,4)) do NOT
map to real cells. Everything must be DISCOVERED frame-only, L0-style
(_frontier_circuit: colour-8 frontier cell adjacent to the reachable region →
drive to it via the lag-2 driver → confirm by floor-EXPANSION).

This diagnostic: reach L1, settle past the transition frame, detect goal by
MOTION (the static colour-9 region), compute reachable frame-floor from spawn,
list colour-8 frontier candidates, and drive to each with the lag-2 driver to
report which one EXPANDS the floor (= plate B) and what barrier it opens.
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
    cs = [c for c in movers(grid, off) if c != goal]
    return cs[0] if cs else (movers(grid, off)[0] if movers(grid, off) else None)


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
                seen.add(n)
                q.append(n)
    return seen


def frontier_circuit(grid, off, reach):
    cands = set()
    for cell in reach:
        for dr, dc in MV.values():
            n = (cell[0] + dr, cell[1] + dc)
            if n not in reach and cell_color(grid, off, n) == CIRCUIT:
                cands.add(n)
    return cands


def detect_goal(env, obs, off):
    """Static colour-9 region = goal; the moving one = player. The first
    post-level-up frame is a transition artifact, so only trust the STEADY
    state: probe several varied moves and take the movers()-cell present in ALL
    of the last few frames (the static goal); the player moves out of the set."""
    frames: list[set] = []
    for a in (2, 4, 2, 4, 1, 3, 2, 4):
        obs = env.step(A[a])
        frames.append(set(movers(canonical_layer(obs), off)))
    tail = frames[-5:]
    common = set.intersection(*tail) if tail else set()
    goal = next(iter(common)) if common else None
    return obs, goal


def config_plan(floor, blocked, start, moves0, target, gate):
    def passable(cell, moves):
        if cell == target:
            return True
        if cell in floor:
            return True
        return gate(cell, moves)

    def succ(state):
        cell, moves = state
        for a, (dr, dc) in MV.items():
            n = (cell[0] + dr, cell[1] + dc)
            if (cell, a) in blocked:
                continue
            if passable(n, moves + 1):
                yield a, (n, moves + 1)
    return configuration_path((start, moves0), lambda s: s[0] == target, succ, max_states=300_000)


def drive_to(env, obs, off, goal, floor, blocked, target, moves0, gate, floor_base, seen, max_attempts=20):
    conf_moves = moves0
    for _attempt in range(max_attempts):
        grid = canonical_layer(obs)
        conf = pcell(grid, off, goal)
        seen.add(conf)
        pth = config_plan(floor, blocked, conf, conf_moves, target, gate)
        if pth is None:
            return obs, False, conf_moves, set()
        if not pth:
            g = canonical_layer(obs)
            opened = floor_cells(g, off) - floor_base - seen
            return obs, True, conf_moves, opened
        exp = [conf]
        for a in pth:
            dr, dc = MV[a]
            exp.append((exp[-1][0] + dr, exp[-1][1] + dc))
        obslog = [conf]
        for a in pth:
            obs = env.step(A[a])
            c = pcell(canonical_layer(obs), off, goal)
            seen.add(c)
            obslog.append(c)
        for _ in range(LAG):
            obs = env.step(A[1])
            c = pcell(canonical_layer(obs), off, goal)
            seen.add(c)
            obslog.append(c)
        wall = False
        conf_cell = conf
        disp = 0
        for k in range(len(pth)):
            actual = obslog[k + LAG] if k + LAG < len(obslog) else None
            if actual is None:
                break
            if actual == exp[k + 1]:
                if actual != conf_cell:
                    disp += 1
                conf_cell = actual
                continue
            blocked.add((exp[k], pth[k]))
            wall = True
            break
        conf_moves += disp
        if not wall and conf_cell == target:
            g = canonical_layer(obs)
            opened = floor_cells(g, off) - floor_base - seen
            return obs, True, conf_moves, opened
    return obs, False, conf_moves, set()


def settle_nondisplacing(env, obs, off, goal):
    for _ in range(5):
        grid = canonical_layer(obs)
        p = pcell(grid, off, goal)
        fl = floor_cells(grid, off)
        wall_dir = next((a for a, (dr, dc) in MV.items() if (p[0] + dr, p[1] + dc) not in fl), None)
        if wall_dir is None:
            break
        obs = env.step(A[wall_dir])
    return obs


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("g50t")
    obs = reach_l1(env, env.observation_space)
    if int(getattr(obs, "levels_completed", 0) or 0) != 1:
        print("no L1"); return
    grid = canonical_layer(obs)
    off = derive_off(grid)
    obs, goal = detect_goal(env, obs, off)
    obs = settle_nondisplacing(env, obs, off, goal)
    grid = canonical_layer(obs)
    off = derive_off(grid) or off
    spawn = pcell(grid, off, goal)
    floor0 = floor_cells(grid, off)
    reach0 = reachable(floor0, spawn)
    cands = frontier_circuit(grid, off, reach0)
    goal_reach = goal in reach0
    print(f"off {off} spawn {spawn} goal {goal} floor {len(floor0)} reach {len(reach0)} goal_in_reach {goal_reach}")
    print(f"frontier colour-8 candidates ({len(cands)}): {sorted(cands)}")
    if goal is None:
        print("GOAL NONE — abort"); return
    # Drive to the farthest-from-goal candidate (L0 heuristic = plate B) and
    # report floor-expansion. Single pass (no re-reach), so only the first
    # candidate is probed live.
    order = sorted(cands, key=lambda c: -(abs(c[0] - goal[0]) + abs(c[1] - goal[1])))
    no_gate = lambda c, m: False
    blocked: set = set()
    for cand in order:
        seen = {spawn, pcell(canonical_layer(obs), off, goal)}
        floor_base = floor_cells(canonical_layer(obs), off)
        obs, reached, lg, opened = drive_to(env, obs, off, goal, floor0, blocked, cand, 0, no_gate, floor_base, seen, max_attempts=8)
        final = pcell(canonical_layer(obs), off, goal)
        print(f"  cand {cand}: reached={reached} Lg={lg} final={final} opened={sorted(opened)}")
        if reached and opened:
            print(f"  >>> PLATE B = {cand}, barrier = {sorted(opened)}"); break


if __name__ == "__main__":
    main()
