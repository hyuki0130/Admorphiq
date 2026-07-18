"""g50t L1 anchor4 (task #83): FRAME-NATIVE plate discovery (no engine constants).

anchor3 proved the pristine-first-L1 spawn parse is STABLE x3 = (8,7), floor=25.
But engine-cell deltas do NOT transfer: spawn is at frame row 8 (bottom); plateA =
spawn + Δ(2,-6) = row 10 = below the HUD-cropped play area. The frame is a
flipped/scrolled camera view, so engine constants are unusable at runtime.

This probe instead DISCOVERS the plate frame-natively: walk the reachable region;
at each cell watch for a barrier SLIDE (floor-set changes while standing there,
`added = floor_now - floor_base`). A cell that changes the floor set = a plate.
Reports: stable spawn/floor x3, and for run0 the discovered plate cells + what
each opens. If plates are discoverable this way, the chain is frame-native and
needs no anchoring to engine.
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


def pcell(grid):
    out = []
    for reg in find_regions(grid, background=None):
        if reg["color"] != MOVER or not (7 <= reg["bbox"][0] <= 58 and 8 <= reg["size"] <= 40):
            continue
        out.append((reg["bbox"][0] // CELL, reg["bbox"][1] // CELL))
    return out


def floor_cells(grid):
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


def bfs_path(floor, start, target):
    prev = {start: None}
    q = deque([start])
    while q:
        cur = q.popleft()
        if cur == target:
            path = []
            while prev[cur] is not None:
                p = prev[cur]
                for a, (dr, dc) in MV.items():
                    if (p[0] + dr, p[1] + dc) == cur:
                        path.append(a)
                        break
                cur = p
            return path[::-1]
        for a, (dr, dc) in MV.items():
            n = (cur[0] + dr, cur[1] + dc)
            if n in floor and n not in prev:
                prev[n] = cur
                q.append(n)
    return None


def player_cell(grid):
    cs = pcell(grid)
    if not cs:
        return None
    # player = topmost-leftmost mover (2-cell sprite -> take min)
    return min(cs)


def step_seq(env, obs, seq):
    for a in seq:
        obs = env.step(A[a])
    for _ in range(LAG):
        obs = env.step(A[1])  # flush lag; A1=up nudges into wall if at top
    return obs


def run_stability(tag):
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("g50t")
    obs = reach_l1(env, env.observation_space)
    if int(getattr(obs, "levels_completed", 0) or 0) != 1:
        return None
    grid = canonical_layer(obs)
    sp = player_cell(grid)
    fl = frozenset(floor_cells(grid))
    print(f"[{tag}] spawn={sp} floor={len(fl)} reach={len(reachable(set(fl), sp)) if sp else 0}")
    return (sp, fl, env, obs)


def discover_plates(env, obs):
    """Walk the reachable region; at each cell test for a barrier slide (floor set
    change while standing). Returns dict cell -> added floor cells."""
    grid = canonical_layer(obs)
    spawn = player_cell(grid)
    floor0 = floor_cells(grid)
    reach = reachable(floor0, spawn)
    print(f"  discover: spawn={spawn} reach={len(reach)} cells")
    plates = {}
    # visit each reachable cell (except spawn); walk from spawn each time via BFS.
    for target in sorted(reach - {spawn}):
        # re-parse current player (should be at/near spawn after a wall-nudge reset)
        g = canonical_layer(obs)
        cur = player_cell(g)
        if cur is None:
            continue
        path = bfs_path(floor0, cur, target)
        if path is None:
            continue
        obs = step_seq(env, obs, path)
        g = canonical_layer(obs)
        here = player_cell(g)
        fl_now = floor_cells(g)
        added = fl_now - floor0
        removed = floor0 - fl_now
        if added or removed:
            plates[target] = (frozenset(added), frozenset(removed), here)
            print(f"    PLATE? target={target} arrived={here} added={sorted(added)} removed={sorted(removed)}")
        # walk back toward spawn
        back = bfs_path(floor0, here if here else target, spawn)
        if back:
            obs = step_seq(env, obs, back)
    return plates, obs


def main():
    print("=== x3 stability ===")
    envs = []
    for i in range(3):
        r = run_stability(f"run{i}")
        if r:
            envs.append(r)
    spawns = {r[0] for r in envs}
    floors = {r[1] for r in envs}
    print(f"spawn stable: {len(spawns) == 1} {spawns}")
    print(f"floor stable: {len(floors) == 1} sizes={[len(f) for f in floors]}")
    print("\n=== run0 frame-native plate discovery ===")
    if envs:
        _, _, env, obs = envs[0]
        plates, obs = discover_plates(env, obs)
        print(f"discovered plates: {sorted(plates.keys())}")


if __name__ == "__main__":
    main()
