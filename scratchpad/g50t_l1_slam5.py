"""g50t L1 SLAM stage 5: learned-passability driver + plate-B press confirmation.

The frame floor OVER-connects (sprite-mask walls render as colour-5). So drive
with a learned-blocked-edge model: issue one hop, read the player at lag-1; if it
did NOT displace, mark that directed edge blocked and re-plan. Reach plate B
(4,6), HOLD on it (momentary-aware: read the floor WHILE standing, no flush), and
report the floor delta = does standing on it slide/open a barrier?
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
CELL, FLOOR, CIRC = 6, 5, 8
MOVE = {1: (-1, 0), 2: (1, 0), 3: (0, -1), 4: (0, 1)}
VEC = {v: k for k, v in MOVE.items()}


def reach_l1(env, obs):
    ad = Adapter(giveup=2000)
    s = 0
    while s < 2000 and int(getattr(obs, "levels_completed", 0) or 0) < 1 and not ad.is_done([], obs):
        a = ad.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        s += 1
    return obs


def nine(grid):
    out = []
    for reg in find_regions(grid, background=None):
        if reg["color"] != 9:
            continue
        r0 = reg["bbox"][0]
        if 7 <= r0 <= 58 and 8 <= reg["size"] <= 40:
            out.append(reg)
    return out


class L1:
    def __init__(self, env):
        self.env = env
        self.off = None
        self.goal_cell = None
        self.player_cell = None
        self.blocked: set[tuple] = set()  # (from_cell, action) directed edges

    def to_cell(self, cy, cx):
        return (round((cy - self.off[0]) / CELL), round((cx - self.off[1]) / CELL))

    def player_px(self, grid):
        cands = [(r["centroid"][0], r["centroid"][1]) for r in nine(grid)]
        if self.goal_cell is not None:
            cands = [c for c in cands if self.to_cell(*c) != self.goal_cell] or cands
        if self.player_cell is not None:
            pc = self.player_cell
            return min(cands, key=lambda c: abs(self.to_cell(*c)[0]-pc[0]) + abs(self.to_cell(*c)[1]-pc[1]))
        return cands[0] if cands else None

    def floor(self, grid):
        h, w = len(grid), len(grid[0])
        cells = set()
        i = 0
        while self.off[0] + i * CELL < h - 2:
            j = 0
            while self.off[1] + j * CELL < w - 2:
                if grid[self.off[0]+i*CELL][self.off[1]+j*CELL] == FLOOR:
                    cells.add((i, j))
                j += 1
            i += 1
        return cells

    def cell_color(self, grid, cell):
        r, c = self.off[0]+cell[0]*CELL, self.off[1]+cell[1]*CELL
        if 0 <= r < len(grid) and 0 <= c < len(grid[0]):
            return grid[r][c]
        return -1

    def step(self, a):
        return canonical_layer(self.env.step(A[a]))

    def plan(self, floor, start, goal, enter_nonfloor=None):
        """BFS over floor minus learned-blocked edges. enter_nonfloor: a target
        colour-8 cell that is an enterable DESTINATION (not pass-through)."""
        seen = {start}
        parent = {}
        q = deque([start])
        while q:
            cur = q.popleft()
            if cur == goal:
                break
            for a, (dr, dc) in MOVE.items():
                n = (cur[0]+dr, cur[1]+dc)
                if (cur, a) in self.blocked:
                    continue
                passable = n in floor or n == goal or n == enter_nonfloor
                if passable and n not in seen:
                    seen.add(n)
                    parent[n] = (cur, a)
                    q.append(n)
        if goal not in parent and goal != start:
            return None
        path = []
        cur = goal
        while cur in parent:
            path.append(parent[cur][1])
            cur = parent[cur][0]
        return path[::-1]

    def drive(self, grid, goal, enter_nonfloor=None, max_cycles=12):
        """Learned-passability drive to goal. Re-plans on a learned wall."""
        for _ in range(max_cycles):
            if self.player_cell == goal:
                return grid, True
            floor = self.floor(grid)
            plan = self.plan(floor, self.player_cell, goal, enter_nonfloor)
            if not plan:
                return grid, False
            for a in plan:
                frm = self.player_cell
                grid = self.step(a)
                px = self.player_px(grid)
                if px:
                    self.player_cell = self.to_cell(*px)
                if self.player_cell == frm:
                    # no displacement -> sprite-mask wall on this edge; learn + replan
                    self.blocked.add((frm, a))
                    break
                if self.player_cell == goal:
                    return grid, True
        return grid, self.player_cell == goal

    def identify(self):
        grid = self.step(2)
        id_cells = [(r["centroid"][0], r["centroid"][1]) for r in nine(grid)]
        for a in [2, 4, 1, 3, 2, 4, 1, 3]:
            grid = self.step(a)
            now = [(r["centroid"][0], r["centroid"][1]) for r in nine(grid)]
            moved = [c for c in now if all(abs(c[0]-o[0])+abs(c[1]-o[1]) > 2 for o in id_cells)]
            static = [c for c in now if any(abs(c[0]-o[0])+abs(c[1]-o[1]) <= 2 for o in id_cells)]
            if moved:
                self.off = (int(round(moved[0][0])) % CELL, int(round(moved[0][1])) % CELL)
                self.player_cell = self.to_cell(*moved[0])
                self.goal_cell = self.to_cell(*static[0]) if static else None
                return grid
            id_cells = now
        return grid


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("g50t")
    obs = reach_l1(env, env.observation_space)
    if int(getattr(obs, "levels_completed", 0) or 0) != 1:
        print("no L1"); return
    g = L1(env)
    grid = g.identify()
    print(f"off={g.off} player={g.player_cell} goal={g.goal_cell}")
    floor0 = g.floor(grid)
    reach0, _ = g.plan, None
    # BFS reach set
    def reach_set(fl, st):
        seen = {st}; q = deque([st])
        while q:
            cur = q.popleft()
            for a, (dr, dc) in MOVE.items():
                if (cur, a) in g.blocked: continue
                n = (cur[0]+dr, cur[1]+dc)
                if n in fl and n not in seen:
                    seen.add(n); q.append(n)
        return seen
    print(f"floor={len(floor0)} reach={len(reach_set(floor0, g.player_cell))}")

    # drive to plate B (4,6) via learned passability
    plate_b = (4, 6)
    grid, ok = g.drive(grid, plate_b, enter_nonfloor=plate_b)
    print(f"drive to plate B {plate_b}: arrived={ok} player={g.player_cell} learned_walls={sorted(g.blocked)}")
    if ok:
        # HOLD on the plate (momentary-aware): read floor while standing
        floor_on = g.floor(grid)
        added = floor_on - floor0
        removed = floor0 - floor_on
        print(f"  standing on plate B: floor_added={sorted(added)} floor_removed={sorted(removed)}")
        reach_on = reach_set(floor_on, g.player_cell)
        print(f"  reach while standing: {len(reach_on)} (was {len(reach_set(floor0, (5,8)))})")


if __name__ == "__main__":
    main()
