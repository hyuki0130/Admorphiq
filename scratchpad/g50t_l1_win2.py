"""g50t L1 two-ghost nested WIN attempt (chain-finish continuation).

Fixes vs g50t_l1_full.py:
 (1) floor parse cropped to the PLAY AREA (drop the bottom HUD row where the
     left-scrolling timer flickers) + exclude player-occupied cells; a plate
     press is read ONLY after the player is CONFIRMED at the plate cell (via the
     lag-2 trajectory), never on an approach-time floor delta.
 (2) Lg = confirmed DISPLACEMENTS (from the lag-2 trajectory), not issued
     actions; settle by verified-no-op wall nudges.

Chain: settle -> drive plate B (4,6) -> ACTION5 (ghost-B, Lg_B) -> gated drive
plate A (6,2) [barrier-B passable iff moves>Lg_B] -> ACTION5 (ghost-A, Lg_A) ->
gated drive goal (3,4) [both barriers] -> WIN.
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
CELL, FLOOR, MOVER = 6, 5, 9
MV = {1: (-1, 0), 2: (1, 0), 3: (0, -1), 4: (0, 1)}
LAG = 2
HUD_ROW = 9  # cell rows >= this are HUD/timer (pixel >= 54); dropped from floor


def reach_l1(env, obs):
    ad = Adapter(giveup=2000)
    s = 0
    while s < 2000 and int(getattr(obs, "levels_completed", 0) or 0) < 1 and not ad.is_done([], obs):
        a = ad.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        s += 1
    return obs


def derive_off(grid):
    # OFFSET-ROBUST (task #82): the grid is origin-0 with 6px cells (engine
    # pixel // 6). centroid%6 flapped (4,4)/(4,5) run-to-run and shifted the whole
    # grid off-by-one; floor-division on the blob bbox-min is stable to ±1px.
    return (0, 0)


def pcell(grid, off, goal):
    out = []
    for reg in find_regions(grid, background=None):
        if reg["color"] != MOVER or not (7 <= reg["bbox"][0] <= 58 and 8 <= reg["size"] <= 40):
            continue
        r0, c0 = reg["bbox"][0], reg["bbox"][1]   # bbox top-left, stable
        out.append((r0 // CELL, c0 // CELL))
    cs = [c for c in out if c != goal]
    return cs[0] if cs else (out[0] if out else None)


def floor_cells(grid, off):
    h, w = len(grid), len(grid[0])
    cells = set()
    i = 0
    while i * CELL + 3 < h and i < HUD_ROW:       # sample cell CENTER; crop HUD
        j = 0
        while j * CELL + 3 < w:
            if grid[i * CELL + 3][j * CELL + 3] == FLOOR:
                cells.add((i, j))
            j += 1
        i += 1
    return cells


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


def drive_to(env, obs, off, goal, floor, blocked, target, moves0, gate, floor_base, seen, tag):
    """Drive to `target`; return (obs, reached, conf_moves, opened). conf_moves =
    moves0 + confirmed DISPLACEMENTS made here. Arrival + press are read from the
    lag-2 confirmed trajectory only (no approach-time floor-delta)."""
    conf_moves = moves0
    for _attempt in range(16):
        grid = canonical_layer(obs)
        conf = pcell(grid, off, goal)
        seen.add(conf)
        pth = config_plan(floor, blocked, conf, conf_moves, target, gate)
        if pth is None:
            return obs, False, conf_moves, set()
        exp = [conf]
        for a in pth:
            dr, dc = MV[a]
            exp.append((exp[-1][0] + dr, exp[-1][1] + dc))
        obslog = [pcell(grid, off, goal)]
        for a in pth:
            obs = env.step(A[a])
            g = canonical_layer(obs)
            c = pcell(g, off, goal)
            seen.add(c)
            obslog.append(c)
        for _ in range(LAG):
            obs = env.step(A[1])
            g = canonical_layer(obs)
            c = pcell(g, off, goal)
            seen.add(c)
            obslog.append(c)
        # confirmed trajectory = obslog[LAG:]; align to exp. count displacements,
        # find first divergence.
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
        # else: loop re-plans from the new confirmed position
    return obs, False, conf_moves, set()


def settle_nondisplacing(env, obs, off, goal):
    """Advance past the level-transition frame WITHOUT moving the player: nudge
    into a frame-wall (a non-floor neighbour) each step; verify no displacement."""
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
    # settle needs a goal to exclude; use a provisional goal far from spawn.
    obs = settle_nondisplacing(env, obs, off, (0, 0))
    grid = canonical_layer(obs)
    # SPAWN-RELATIVE topology (task #82, brief Q3): the frame-render grid differs
    # from the engine grid by a constant, and derive_off flaps — so express every
    # target as spawn + a FIXED relative offset (engine-verified), invariant to the
    # grid origin. Engine cells: spawn(4,8) plateB(4,6) plateA(6,2) goal(3,4)
    # barrierB-vacated(8,6) -> relative to spawn: dB(0,-2) dA(2,-6) dGoal(-1,-4).
    spawn = pcell(grid, off, (0, 0))
    plateB = (spawn[0] + 0, spawn[1] - 2)
    plateA = (spawn[0] + 2, spawn[1] - 6)
    goal = (spawn[0] - 1, spawn[1] - 4)
    floor0 = floor_cells(grid, off)
    print("off", off, "spawn", spawn, "plateB", plateB, "plateA", plateA, "goal", goal, "floor", len(floor0))

    blocked = set()
    seen = {spawn}
    no_gate = lambda c, m: False
    obs, okB, LgB, barrierB = drive_to(env, obs, off, goal, floor0, blocked, plateB, 0, no_gate, floor0, seen, "B")
    print("phase1 reachB", okB, "LgB", LgB, "barrierB", sorted(barrierB))
    if not okB:
        print("BANK: phase1 failed"); return
    p_before = pcell(canonical_layer(obs), off, goal)
    obs = env.step(A[5])
    obs = settle_nondisplacing(env, obs, off, goal)
    # re-scan floor with ghost-B holding barrier-B open
    grid = canonical_layer(obs)
    floorB = floor_cells(grid, off)
    # FIX (task #82 decode): the L1 barrier is a SLIDING colour-8 block, not a
    # vanishing one — a press nets ~0 floor change during approach, so drive_to's
    # `opened` (floor-expansion) is empty. The true barrier = the cell the block
    # VACATES, i.e. the floor cells ADDED after the ghost seats on the plate.
    barrierB = frozenset(floorB - floor0)
    print("  DIAG ghost-B: player_before_A5", p_before, "player_now", pcell(grid, off, goal),
          "added", sorted(barrierB), "removed", sorted(floor0 - floorB))
    print("after ghost-B: floor", len(floorB), "barrierB(added)", sorted(barrierB), "plateA reachable-adj?",
          any((plateA[0] + dr, plateA[1] + dc) in floorB for dr, dc in MV.values()))
    gateB = lambda c, m, bb=frozenset(barrierB), L=LgB: (c in bb) and (m > L)
    seen2 = {spawn}
    obs, okA, LgA, barrierA = drive_to(env, obs, off, goal, floorB, blocked, plateA, 0, gateB, floorB, seen2, "A")
    print("phase2 reachA", okA, "LgA", LgA, "barrierA", sorted(barrierA))
    if not okA:
        print("BANK: phase2 (nested gated discovery) — reached wall"); return
    obs = env.step(A[5])
    obs = settle_nondisplacing(env, obs, off, goal)
    grid = canonical_layer(obs)
    floorAB = floor_cells(grid, off)
    barrierA = frozenset(floorAB - floorB)   # cells the second block vacated
    print("after ghost-A: floor", len(floorAB), "barrierA(added)", sorted(barrierA))
    def gate_both(c, m, bb=frozenset(barrierB), ba=frozenset(barrierA), LB=LgB, LA=LgA):
        return (c in bb and m > LB) or (c in ba and m > LA)
    seen3 = {spawn}
    obs, okG, LgG, _ = drive_to(env, obs, off, goal, floorAB, blocked, goal, 0, gate_both, floorAB, seen3, "G")
    st = str(obs.state)
    lv = int(getattr(obs, "levels_completed", 0) or 0)
    print("phase3 reachGoal", okG, "state", st[-10:], "levels", lv)
    print("*** L1 WIN ***" if (st.endswith("WIN") or lv >= 2) else "no win (phase3)")


if __name__ == "__main__":
    main()
