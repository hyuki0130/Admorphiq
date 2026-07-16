"""g50t L1 driver v6 — plan / execute-open-loop / verify-at-lag-2 / learn-wall.

Calibrated: obs at call t reflects the cumulative result through action t-2 (a
UNIFORM 2-call observation lag). So after issuing a planned action sequence, the
recorded observations reconstruct the TRUE trajectory (shifted by 2), and the
first place the observed trajectory diverges from the planned one is a sprite-mask
wall the colour frame renders as floor. Learn that edge, re-plan from the last
confirmed cell, repeat. No in-flight extrapolation (that phantomed onto the plate).

Validates: reliably PRESS plate (4,6) (confirmed by frame floor-expansion),
learning the col-8 lateral walls, then report the action count.
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


def player_cell(grid, off, goal):
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


def plan(floor, blocked, start, goal):
    if start == goal:
        return []
    seen = {start}
    q = deque([(start, [])])
    while q:
        cur, path = q.popleft()
        for a, (dr, dc) in MV.items():
            n = (cur[0] + dr, cur[1] + dc)
            if (cur, a) in blocked:
                continue
            if n == goal:
                return path + [a]
            if n in floor and n not in seen:
                seen.add(n)
                q.append((n, path + [a]))
    return None


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("g50t")
    obs = reach_l1(env, env.observation_space)
    if int(getattr(obs, "levels_completed", 0) or 0) != 1:
        print("no L1"); return
    for _ in range(3):
        obs = env.step(A[1])
    grid = canonical_layer(obs)
    off = derive_off(grid)
    goal = (3, 4)
    floor0 = floor_cells(grid, off)
    target = (4, 6)
    conf = player_cell(grid, off, goal)
    print("off", off, "floor", len(floor0), "start", conf, "target", target)

    blocked = set()
    total = 0
    pressed = False
    for attempt in range(12):
        pth = plan(floor0, blocked, conf, target)
        if pth is None:
            print(f"NO PATH from {conf}; blocked={sorted(blocked)}"); break
        # expected trajectory from conf
        exp = [conf]
        for a in pth:
            dr, dc = MV[a]
            exp.append((exp[-1][0] + dr, exp[-1][1] + dc))
        # execute open-loop, logging obs BEFORE each step; flush LAG extra reads
        obslog = []
        seq = list(pth)
        for a in seq:
            g = canonical_layer(obs)
            obslog.append(player_cell(g, off, goal))
            opened = floor_cells(g, off) - floor0
            if opened:
                print(f"PLATE PRESSED {target} @ total={total} opened={sorted(opened)} attempts={attempt}")
                pressed = True
                break
            obs = env.step(A[a]); total += 1
        if pressed:
            break
        # flush LAG reads so the last issued actions become observable
        for _ in range(LAG):
            g = canonical_layer(obs)
            obslog.append(player_cell(g, off, goal))
            opened = floor_cells(g, off) - floor0
            if opened:
                print(f"PLATE PRESSED {target} @ total={total} opened={sorted(opened)} attempts={attempt}")
                pressed = True
                break
            obs = env.step(A[1]); total += 1   # UP flush (top wall = no-op at (1,x))
        if pressed:
            break
        # actual trajectory = obslog shifted by LAG: obslog[k+LAG] == cell after pth[..k]
        # find first divergence between actual and expected
        wall_found = False
        last_ok = conf
        for k in range(len(pth)):
            actual = obslog[k + LAG] if k + LAG < len(obslog) else None
            if actual is None:
                break
            if actual == exp[k + 1]:
                last_ok = actual
                continue
            # divergence: pth[k] from exp[k] did not reach exp[k+1]
            blocked.add((exp[k], pth[k]))
            conf = last_ok
            wall_found = True
            print(f"  wall learned {(exp[k], pth[k])}; resync conf={conf}")
            break
        if not wall_found:
            # trajectory matched fully but no press -> re-sync to last obs and retry
            g = canonical_layer(obs)
            conf = player_cell(g, off, goal) or conf
            if conf == target or (target in floor0):
                pass
            print(f"  full match no press; conf={conf}")
            if not blocked:
                break
    print(("PRESSED" if pressed else "NOT pressed"), "| total actions", total, "| walls", sorted(blocked))


if __name__ == "__main__":
    main()
