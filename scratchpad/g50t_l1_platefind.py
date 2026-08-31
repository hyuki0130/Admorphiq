"""g50t L1 definitive PLATE-FINDER (polarity- and colour-agnostic).

The expansion-based discovery that clears L0 finds NO floor-expanding plate on
L1 (all 3 colour-8 frontier candidates open nothing; the win-script DIAG shows
ACTION5 seating REMOVES a floor cell instead). So L1's plate mechanic is not the
L0 "enter frontier colour-8 -> floor expands" model.

This walks the player over EVERY reachable floor cell (closed-loop single steps,
lag-tolerant: re-read each step) plus the colour-8 frontier candidates, and after
each settled position reports ANY floor change (added OR removed) vs the baseline,
excluding the player-occupied cell. Whatever cell causes a change is the plate;
the changed cells are the wired barrier/block, and the sign is the polarity.
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

A = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3, 4: GameAction.ACTION4, 5: GameAction.ACTION5}
CELL, FLOOR, MOVER, CIRCUIT = 6, 5, 9, 8
MV = {1: (-1, 0), 2: (1, 0), 3: (0, -1), 4: (0, 1)}
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


def detect_goal(env, obs, off):
    frames = []
    for a in (2, 4, 2, 4, 1, 3, 2, 4):
        obs = env.step(A[a])
        frames.append(set(movers(canonical_layer(obs), off)))
    common = set.intersection(*frames[-5:]) if frames else set()
    return obs, (next(iter(common)) if common else None)


def step_to(env, obs, off, goal, target, floor, tries=6):
    """Closed-loop single hop to an adjacent target; re-issue until reached or
    stuck. Returns (obs, reached)."""
    for _ in range(tries):
        grid = canonical_layer(obs)
        p = pcell(grid, off, goal)
        if p == target:
            return obs, True
        dr = max(-1, min(1, target[0] - p[0]))
        dc = max(-1, min(1, target[1] - p[1]))
        act = None
        for vec in ((dr, 0), (0, dc)):
            if vec in {v: k for k, v in MV.items()}:
                act = {v: k for k, v in MV.items()}[vec]; break
        if act is None:
            return obs, False
        obs = env.step(A[act])
    return obs, pcell(canonical_layer(obs), off, goal) == target


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("g50t")
    obs = reach_l1(env, env.observation_space)
    if int(getattr(obs, "levels_completed", 0) or 0) != 1:
        print("no L1"); return
    off = derive_off(canonical_layer(obs))
    obs, goal = detect_goal(env, obs, off)
    # settle
    for _ in range(4):
        obs = env.step(A[1])
    off = derive_off(canonical_layer(obs)) or off
    grid = canonical_layer(obs)
    base_floor = floor_cells(grid, off)
    spawn = pcell(grid, off, goal)
    reach = reachable(base_floor, spawn)
    print(f"off {off} spawn {spawn} goal {goal} base_floor {len(base_floor)} reach {len(reach)}")

    # BFS order over reachable cells so consecutive targets are adjacent.
    order = []
    seen = {spawn}
    q = deque([spawn])
    while q:
        cur = q.popleft()
        order.append(cur)
        for dr, dc in MV.values():
            n = (cur[0] + dr, cur[1] + dc)
            if n in reach and n not in seen:
                seen.add(n); q.append(n)

    changes = []
    for tgt in order:
        obs, ok = step_to(env, obs, off, goal, tgt, base_floor)
        if not ok:
            continue
        # settle 1 read, then diff
        obs = env.step(A[1]) if (tgt[0] - 1, tgt[1]) not in base_floor else env.step(A[2])
        g = canonical_layer(obs)
        p = pcell(g, off, goal)
        fnow = floor_cells(g, off)
        added = fnow - base_floor - {p}
        removed = base_floor - fnow - {p}
        if added or removed:
            changes.append((tgt, sorted(added), sorted(removed)))
            print(f"  STOOD {tgt}: added={sorted(added)} removed={sorted(removed)}")
    if not changes:
        print("NO floor change from any reachable cell — plate not among reachable floor")
    # Also report frontier colour-8 candidates for reference.
    cands = set()
    for cell in reach:
        for dr, dc in MV.values():
            n = (cell[0] + dr, cell[1] + dc)
            if n not in reach and cell_color(grid, off, n) == CIRCUIT:
                cands.add(n)
    print(f"frontier colour-8 candidates: {sorted(cands)}")


if __name__ == "__main__":
    main()
