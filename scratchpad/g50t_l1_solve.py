"""g50t L1 FRAME-ONLY two-ghost solver (no hardcoded cells) — standalone WIN attempt.

Assembles the validated components:
  - fixed goal detection (static colour-9 region, read from the STEADY state);
  - L0-style frontier-circuit plate DISCOVERY (offset-agnostic);
  - the lag-2 driver (plan / execute-open-loop / verify-at-lag-2 / learn-wall);
  - two-ghost seating over a (cell, moves) gated config_plan.

Chain: settle -> DISCOVER plate B (frontier colour-8, drive, confirm expansion)
-> ACTION5 (ghost-B, Lg_B) -> re-scan floor -> DISCOVER plate A gated behind
barrier-B -> ACTION5 (ghost-A, Lg_A) -> drive goal with BOTH barriers -> WIN.

Nothing here reads wiki cell constants; plates/goal are discovered each run
because derive_off shifts run-to-run (OFFSET INSTABILITY, commit f4f7f63).
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
    return configuration_path((start, moves0), lambda s: s[0] == target, succ, max_states=400_000)


def drive_to(env, obs, off, goal, floor, blocked, target, moves0, gate, floor_base, seen, max_attempts=20):
    """Drive to `target` via lag-2 plan/execute/verify/learn-wall. Returns
    (obs, reached, conf_moves, opened). conf_moves = moves0 + confirmed
    DISPLACEMENTS. opened = floor cells that appeared and were never stood on."""
    conf_moves = moves0
    for _ in range(max_attempts):
        grid = canonical_layer(obs)
        conf = pcell(grid, off, goal)
        seen.add(conf)
        pth = config_plan(floor, blocked, conf, conf_moves, target, gate)
        if pth is None:
            return obs, False, conf_moves, set()
        if not pth:
            g = canonical_layer(obs)
            return obs, True, conf_moves, floor_cells(g, off) - floor_base - seen
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
            return obs, True, conf_moves, floor_cells(g, off) - floor_base - seen
    return obs, False, conf_moves, set()


def settle_nondisplacing(env, obs, off, goal):
    for _ in range(5):
        grid = canonical_layer(obs)
        p = pcell(grid, off, goal)
        fl = floor_cells(grid, off)
        wall_dir = next((a for a, (dr, dc) in MV.items() if p and (p[0] + dr, p[1] + dc) not in fl), None)
        if wall_dir is None:
            break
        obs = env.step(A[wall_dir])
    return obs


def discover_plate(env, obs, off, goal, floor, blocked, gate, moves0, seen):
    """Try each colour-8 frontier candidate; the first one the driver can ENTER
    and whose entry EXPANDS the floor is the plate. Returns
    (obs, plate, barrier, conf_moves, ok). conf_moves accumulates across probes
    so the ghost's Lg (banked at the next ACTION5) counts every displacement."""
    grid = canonical_layer(obs)
    conf = pcell(grid, off, goal)
    reach = reachable(floor, conf)
    cands = frontier_circuit(grid, off, reach)
    # nearest-to-player first (a reachable plate is usually the closest frontier;
    # closed barriers cost the fewest wasted moves when they are far).
    order = sorted(cands, key=lambda c: abs(c[0] - conf[0]) + abs(c[1] - conf[1]))
    conf_moves = moves0
    for cand in order:
        floor_base = floor_cells(canonical_layer(obs), off)
        seen.add(pcell(canonical_layer(obs), off, goal))
        obs, reached, conf_moves, opened = drive_to(
            env, obs, off, goal, floor, blocked, cand, conf_moves, gate, floor_base, seen, max_attempts=8
        )
        real_open = {c for c in opened if c != cand}
        if reached and real_open:
            return obs, cand, real_open, conf_moves, True
    return obs, None, set(), conf_moves, False


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("g50t")
    obs = reach_l1(env, env.observation_space)
    if int(getattr(obs, "levels_completed", 0) or 0) != 1:
        print("no L1"); return
    off = derive_off(canonical_layer(obs))
    obs, goal = detect_goal(env, obs, off)
    obs = settle_nondisplacing(env, obs, off, goal)
    off = derive_off(canonical_layer(obs)) or off
    spawn = pcell(canonical_layer(obs), off, goal)
    floor0 = floor_cells(canonical_layer(obs), off)
    print(f"off {off} spawn {spawn} goal {goal} floor {len(floor0)}")
    if goal is None:
        print("GOAL NONE — abort"); return

    blocked: set = set()
    seenB = {spawn}
    no_gate = lambda c, m: False
    obs, plateB, barrierB, LgB, okB = discover_plate(env, obs, off, goal, floor0, blocked, no_gate, 0, seenB)
    print(f"phase1 plateB={plateB} barrierB={sorted(barrierB)} LgB={LgB} ok={okB}")
    if not okB:
        print("BANK: phase1 discovery failed"); return
    obs = env.step(A[5])                       # ghost-B seats on plateB
    obs = settle_nondisplacing(env, obs, off, goal)
    floorB = floor_cells(canonical_layer(obs), off)
    print(f"after ghost-B: floor {len(floorB)} (was {len(floor0)}) added {sorted(floorB - floor0)}")

    gateB = lambda c, m, bb=frozenset(barrierB), L=LgB: (c in bb) and (m > L)
    seenA = {pcell(canonical_layer(obs), off, goal)}
    obs, plateA, barrierA, LgA, okA = discover_plate(env, obs, off, goal, floorB, blocked, gateB, 0, seenA)
    print(f"phase2 plateA={plateA} barrierA={sorted(barrierA)} LgA={LgA} ok={okA}")
    if not okA:
        print("BANK: phase2 nested gated discovery failed"); return
    obs = env.step(A[5])                       # ghost-A seats on plateA
    obs = settle_nondisplacing(env, obs, off, goal)
    floorAB = floor_cells(canonical_layer(obs), off)

    def gate_both(c, m, bb=frozenset(barrierB), ba=frozenset(barrierA), LB=LgB, LA=LgA):
        return (c in bb and m > LB) or (c in ba and m > LA)
    seenG = {pcell(canonical_layer(obs), off, goal)}
    obs, okG, LgG, _ = drive_to(env, obs, off, goal, floorAB, blocked, goal, 0, gate_both,
                                floorAB, seenG, max_attempts=16)
    st = str(obs.state)
    lv = int(getattr(obs, "levels_completed", 0) or 0)
    print(f"phase3 reachGoal={okG} state={st[-10:]} levels={lv}")
    print("*** L1 WIN ***" if (st.endswith("WIN") or lv >= 2) else "no win (phase3)")


if __name__ == "__main__":
    main()
