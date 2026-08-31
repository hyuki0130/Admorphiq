"""g50t L1 lag-aware + learned-passability DRIVER validation.

Model (measured): env.step(a) returns the frame reflecting state AFTER all
PREVIOUS actions but BEFORE a (a one-action observation lag). So the result of
the action I issue this step is only visible on the NEXT read.

Driver: maintain `pred` = predicted true cell after every issued move. Plan over
frame-floor edges MINUS learned-blocked edges. Issue ONE planned move per step;
predict pred += effect if the edge is believed passable. Each step, the observed
cell O confirms the move issued TWO steps ago; if O disagrees with the
prediction, learn that edge blocked and re-plan from the confirmed cell.

Goal of this scratch: reliably drive the L1 player from spawn to plate (4,6),
learning the col-8 sprite-mask walls on the way. Prints WIN/where it lands.
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
VM = {v: k for k, v in MV.items()}


def reach_l1(env, obs):
    ad = Adapter(giveup=2000)
    steps = 0
    while steps < 2000 and int(getattr(obs, "levels_completed", 0) or 0) < 1 and not ad.is_done([], obs):
        a = ad.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        steps += 1
    return obs, steps


def movers(grid, off):
    out = []
    for reg in find_regions(grid, background=None):
        if reg["color"] != MOVER:
            continue
        r0 = reg["bbox"][0]
        if r0 < 7 or r0 > 58 or not (8 <= reg["size"] <= 40):
            continue
        cy, cx = reg["centroid"]
        out.append((round((cy - off[0]) / CELL), round((cx - off[1]) / CELL), reg["size"]))
    return out


def derive_off(grid):
    for reg in find_regions(grid, background=None):
        if reg["color"] == MOVER and 8 <= reg["size"] <= 40 and 7 <= reg["bbox"][0] <= 58:
            cy, cx = reg["centroid"]
            return (int(round(cy)) % CELL, int(round(cx)) % CELL)
    return None


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
    """BFS start->goal over floor edges minus learned-blocked directed edges.
    `goal` may be a non-floor enterable cell (a colour-8 plate) — it is a valid
    destination even though you cannot pass THROUGH it."""
    if start == goal:
        return []
    seen = {start}
    q = deque([(start, [])])
    while q:
        cur, path = q.popleft()
        for a, (dr, dc) in MV.items():
            n = (cur[0] + dr, cur[1] + dc)
            if n == goal and (cur, a) not in blocked:
                return path + [a]
            if n in floor and n not in seen and (cur, a) not in blocked:
                seen.add(n)
                q.append((n, path + [a]))
    return None


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("g50t")
    obs = env.observation_space
    obs, s0 = reach_l1(env, obs)
    if int(getattr(obs, "levels_completed", 0) or 0) != 1:
        print("did not reach L1"); return
    # settle transition frame
    for _ in range(3):
        obs = env.step(A[1])
    grid = canonical_layer(obs)
    off = derive_off(grid)
    floor = floor_cells(grid, off)
    ms = movers(grid, off)
    print("off", off, "floor", len(floor), "movers", ms)
    # after 3 UP the player is at top of col-8; identify by which mover is at col 8
    # goal is static (3,4). spawn known from wiki = (4,8); player now near (1,8).
    goal = (3, 4)
    player_now = None
    for (r, c, _s) in ms:
        if (r, c) != goal:
            player_now = (r, c)
    print("player_now(lagged)", player_now, "target plate (4,6)")

    blocked = set()
    pred = player_now  # trust the lagged read as current (player is settled after 3 UP+lag)
    target = (4, 6)
    # confirm settle: issue UP into top wall twice so obs==true
    for _ in range(2):
        obs = env.step(A[1])
    grid = canonical_layer(obs)
    ms = movers(grid, off)
    pred = next(((r, c) for (r, c, _s) in ms if (r, c) != goal), pred)
    print("settled pred", pred)

    floor0 = set(floor)
    prev_O = pred
    last_action = None
    frozen = 0        # consecutive steps O has not changed while issuing a move
    steps = 0
    O = pred
    while steps < 300:
        grid = canonical_layer(obs)
        ms = movers(grid, off)
        newO = next(((r, c) for (r, c, _s) in ms if (r, c) != goal), None)
        if newO is None:
            obs = env.step(A[1]); steps += 1; continue
        if newO == prev_O:
            frozen += 1
        else:
            frozen = 0
        O = newO
        # real position = observed advanced by the in-flight move IF it produced
        # motion (the player glides one cell ahead of the lagged observation).
        real = O
        if last_action is not None and O != prev_O:
            dr, dc = MV[last_action]
            cand = (O[0] + dr, O[1] + dc)
            if cand in floor0 or cand == target:
                real = cand
        # learned passability by STABILITY: O frozen >= 2 steps at O while we keep
        # issuing `last_action` toward (O + eff) means that edge is truly walled
        # (a single-step freeze is just the one-frame lag, not a wall).
        if last_action is not None and frozen >= 2:
            dr, dc = MV[last_action]
            tgt = (O[0] + dr, O[1] + dc)
            if tgt != O:
                blocked.add((O, last_action))
            real = O
            frozen = 0
        prev_O = O

        opened = floor_cells(grid, off) - floor0
        if opened:
            print(f"PLATE PRESSED {target} @ step {steps} O={O} real={real} opened={sorted(opened)}")
            break
        pth = plan(floor0, blocked, real, target)
        if not pth:
            print("NO PATH from", real, "blocked", sorted(blocked)); break
        a = pth[0]
        last_action = a
        obs = env.step(A[a]); steps += 1
    else:
        print("driver budget hit; last O", O)
    print("blocked edges learned:", sorted(blocked))


if __name__ == "__main__":
    main()
