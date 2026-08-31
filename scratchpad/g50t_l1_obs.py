"""g50t L1 driver v5: a proper 2-call-delay OBSERVER.

Timing (re-derived, measured): choose_action at call t receives frame F_t =
state AFTER actions a_0..a_{t-2} (BEFORE a_{t-1}). So the result of the action I
issue at call k is first visible at call k+2. Confirmation delay = 2 calls.

Observer: keep `inflight` = actions issued but not yet confirmed (steady-state 2).
Each call: the observed cell O confirms the OLDEST inflight action (compare O to
the previous O). If no move -> that edge is walled (learn it); else advance the
confirmed `true`. Predict the current position = confirmed `true` advanced by the
still-inflight action. Plan from the prediction; NEVER declare success on
prediction — a plate PRESS is confirmed only by observed floor-expansion.

Validates: reliably press plate (4,6) via the (3,6)->DOWN route, learning the
(4,8)-LEFT and (4,7)-LEFT sprite-mask walls.
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
        if reg["color"] != MOVER:
            continue
        if not (7 <= reg["bbox"][0] <= 58 and 8 <= reg["size"] <= 40):
            continue
        cy, cx = reg["centroid"]
        out.append((round((cy - off[0]) / CELL), round((cx - off[1]) / CELL)))
    return out


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


def player_cell(grid, off, goal):
    ms = movers(grid, off)
    cs = [c for c in ms if c != goal]
    return cs[0] if cs else (ms[0] if ms else None)


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("g50t")
    obs = ar and env.observation_space
    obs = reach_l1(env, obs)
    if int(getattr(obs, "levels_completed", 0) or 0) != 1:
        print("no L1"); return
    # settle the transition frame WITHOUT displacing: issue UP (wall at spawn top?)
    # then derive offset + goal + true spawn from a stable read.
    for _ in range(3):
        obs = env.step(A[1])
    grid = canonical_layer(obs)
    off = derive_off(grid)
    goal = (3, 4)
    floor0 = floor_cells(grid, off)
    target = (4, 6)
    # confirmed true spawn: read the player cell now (after the settle UPs it is
    # at the top of col-8). We drive from wherever it is; the observer tracks it.
    true = player_cell(grid, off, goal)
    print("off", off, "floor", len(floor0), "true(start)", true, "goal", goal, "target", target)

    blocked = set()
    confirmed_pass = set()  # (from_cell, action) edges observed to actually move
    inflight = deque()      # (action, from_cell) issued, unconfirmed
    Oprev = true
    steps = 0
    pressed = False
    while steps < 250:
        grid = canonical_layer(obs)
        O = player_cell(grid, off, goal)
        if O is None:
            obs = env.step(A[1]); steps += 1; continue
        # confirm the OLDEST inflight action — only once it is 2 calls old (the
        # confirmation delay), i.e. inflight holds both a_{t-2} and a_{t-1}.
        if len(inflight) >= 2:
            a_old, frm = inflight.popleft()
            if O == Oprev:                       # no displacement -> walled
                blocked.add((frm, a_old))
                true = frm
            else:
                confirmed_pass.add((frm, a_old))  # this edge really moves
                true = O                          # a_old moved us here
        Oprev = O
        # plate press?
        opened = floor_cells(grid, off) - floor0
        if opened:
            print(f"PLATE PRESSED {target} @ step {steps} O={O} opened={sorted(opened)} "
                  f"nblk={len(blocked)}")
            pressed = True
            break
        # predicted current position = true advanced by still-inflight moves,
        # but ONLY through edges already confirmed passable (never optimistically
        # onto a never-traversed edge — that is what phantomed onto the plate).
        pred = true
        for a, _frm in inflight:
            dr, dc = MV[a]
            nxt = (pred[0] + dr, pred[1] + dc)
            if (pred, a) in confirmed_pass:
                pred = nxt
        # plan from pred; if pred is a non-floor phantom or unreachable, fall back
        # to the confirmed `true` so a walled edge still gets tried + learned.
        start = pred if (pred in floor0 or pred == target) else true
        pth = plan(floor0, blocked, start, target)
        if not pth and start != true:
            pth = plan(floor0, blocked, true, target)
            start = true
        if not pth:
            print(f"NO PATH start={start} true={true} O={O} nblk={len(blocked)}"); break
        a = pth[0]
        inflight.append((a, start))
        obs = env.step(A[a]); steps += 1
    print("pressed" if pressed else "NOT pressed", "| walls learned:", sorted(blocked))


if __name__ == "__main__":
    main()
