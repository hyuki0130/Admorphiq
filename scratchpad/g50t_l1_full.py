"""g50t L1 full two-ghost nested solve (scratch validation, aiming for WIN).

Reliable driver (validated): plan over (cell, moves) config space minus learned
sprite-mask walls -> execute open-loop -> verify against the UNIFORM 2-call
observation lag -> learn the wall at the first divergence -> re-plan.

Chain: settle WITHOUT displacing (preserve true spawn — ACTION5 rewinds there) ->
drive to plate B (4,6), ACTION5 (seat ghost-B, Lg_B = genuine moves) -> drive to
plate A (6,2) through barrier-B (gated moves>Lg_B), ACTION5 (seat ghost-A, Lg_A) ->
drive to goal (3,4) with BOTH barriers gated -> WIN.
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


def pcell(grid, off, goal):
    out = []
    for reg in find_regions(grid, background=None):
        if reg["color"] != MOVER or not (7 <= reg["bbox"][0] <= 58 and 8 <= reg["size"] <= 40):
            continue
        cy, cx = reg["centroid"]
        out.append((round((cy - off[0]) / CELL), round((cx - off[1]) / CELL)))
    cs = [c for c in out if c != goal]
    return cs[0] if cs else (out[0] if out else None)


def floor_cells(grid, off):
    h, w = len(grid), len(grid[0])
    cells = set()
    i = 0
    while off[0] + i * CELL < h:
        j = 0
        while off[1] + j * CELL < w:
            if grid[off[0] + i * CELL][off[1] + j * CELL] == FLOOR:
                cells.add((i, j))
            j += 1
        i += 1
    return cells


def config_plan(floor, blocked, start, moves0, target, gate):
    """BFS over (cell, moves): gate(cell) tells whether a non-floor barrier cell
    is passable at that move count; target is an enterable destination."""
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
    path = configuration_path((start, moves0), lambda s: s[0] == target, succ, max_states=200_000)
    return path


def _opened(grid, off, floor_base, seen_player):
    """Floor cells that appeared vs the base, EXCLUDING any cell the player has
    occupied (the player blob occludes its floor; vacating it reads as a false
    expansion). A real plate press opens BARRIER cells, never player cells."""
    return floor_cells(grid, off) - floor_base - seen_player


def drive_to(env, obs, off, goal, floor, blocked, target, moves0, gate, floor_base, seen_player, tag):
    """Reliable driver to `target` from the current player cell; returns
    (obs, reached, moves_after, opened_set). moves0 = genuine move count so far
    (for gate). Detects arrival/press by target reach OR barrier floor-expansion."""
    moves = moves0
    for attempt in range(14):
        grid = canonical_layer(obs)
        conf = pcell(grid, off, goal)
        seen_player.add(conf)
        pth = config_plan(floor, blocked, conf, moves, target, gate)
        if pth is None:
            return obs, False, moves, set()
        exp = [(conf, moves)]
        for a in pth:
            dr, dc = MV[a]
            exp.append(((exp[-1][0][0] + dr, exp[-1][0][1] + dc), exp[-1][1] + 1))
        obslog = []
        for a in pth:
            g = canonical_layer(obs)
            cur = pcell(g, off, goal)
            seen_player.add(cur)
            obslog.append(cur)
            opened = _opened(g, off, floor_base, seen_player)
            if cur == target or opened:
                return obs, True, moves, opened
            obs = env.step(A[a]); moves += 1
        for _ in range(LAG):
            g = canonical_layer(obs)
            cur = pcell(g, off, goal)
            seen_player.add(cur)
            obslog.append(cur)
            opened = _opened(g, off, floor_base, seen_player)
            if cur == target or opened:
                return obs, True, moves, opened
            obs = env.step(A[1]); moves += 1
        # verify vs lag, learn first wall
        wall = False
        for k in range(len(pth)):
            actual = obslog[k + LAG] if k + LAG < len(obslog) else None
            if actual is None:
                break
            if actual == exp[k + 1][0]:
                continue
            blocked.add((exp[k][0], pth[k]))
            wall = True
            break
        if not wall:
            # matched but not reached -> resync and retry
            pass
    return obs, False, moves, set()


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("g50t")
    obs = reach_l1(env, env.observation_space)
    if int(getattr(obs, "levels_completed", 0) or 0) != 1:
        print("no L1"); return
    # non-displacing settle: nudge into a frame wall until the transition frame stabilises
    grid = canonical_layer(obs)
    off = derive_off(grid)
    goal = (3, 4)
    for _ in range(4):
        grid = canonical_layer(obs)
        p = pcell(grid, off, goal)
        fl = floor_cells(grid, off)
        wall_dir = next((a for a, (dr, dc) in MV.items() if (p[0] + dr, p[1] + dc) not in fl), 1)
        obs = env.step(A[wall_dir])
    grid = canonical_layer(obs)
    off = derive_off(grid) or off
    spawn = pcell(grid, off, goal)
    floor0 = floor_cells(grid, off)
    plateB, plateA = (4, 6), (6, 2)
    print("off", off, "spawn", spawn, "goal", goal, "floor", len(floor0))

    blocked = set()
    seen_player = {spawn}
    no_gate = lambda c, m: False
    # phase 1: seat ghost-B on plate (4,6)
    obs, okB, movesB, opened = drive_to(env, obs, off, goal, floor0, blocked, plateB, 0, no_gate, floor0, seen_player, "B")
    print("phase1 reachB", okB, "movesB(Lg_B)", movesB, "opened", sorted(opened))
    if not okB:
        print("FAILED phase1"); return
    LgB = movesB
    barrierB = opened
    obs = env.step(A[5])  # seat ghost-B
    # settle rewind
    for _ in range(6):
        obs = env.step(A[1])
    grid = canonical_layer(obs)
    floorB = floor_cells(grid, off)  # floor with barrier-B open (ghost seated)
    print("after ghost-B: floor now", len(floorB), "plateA in floor?", plateA in floorB,
          "barrierB", sorted(barrierB))
    # gate for barrier-B: its cells passable once moves > LgB
    gateB = lambda c, m, bb=barrierB, L=LgB: (c in bb) and (m > L)
    # phase 2: reach plate (6,2)
    obs, okA, movesA, openedA = drive_to(env, obs, off, goal, floorB, blocked, plateA, 0, gateB, floorB, seen_player, "A")
    print("phase2 reachA", okA, "movesA(Lg_A)", movesA, "openedA", sorted(openedA))
    if not okA:
        print("reached phase2 wall — banking"); return
    # phase 3: final walk to goal with both barriers gated
    LgA = movesA
    obs = env.step(A[5])  # seat ghost-A
    for _ in range(6):
        obs = env.step(A[1])
    grid = canonical_layer(obs)
    floorAB = floor_cells(grid, off)
    def gate_both(c, m, bb=barrierB, ba=openedA, LB=LgB, LA=LgA):
        if c in bb and m > LB:
            return True
        if c in ba and m > LA:
            return True
        return False
    obs, okG, movesG, _ = drive_to(env, obs, off, goal, floorAB, blocked, goal, 0, gate_both, floorAB, seen_player, "G")
    st = str(obs.state)
    print("phase3 reachGoal", okG, "state", st[-10:], "levels", int(getattr(obs, "levels_completed", 0) or 0))
    if st.endswith("WIN") or int(getattr(obs, "levels_completed", 0) or 0) >= 2:
        print("*** L1 WIN ***")


if __name__ == "__main__":
    main()
