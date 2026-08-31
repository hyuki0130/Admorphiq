"""g50t L1 SLAM stage 8: confirmed-hop lag-1 driver + plate-B open confirmation.

Each confirmed hop = issue the move, then issue a wall-bump NO-OP (a move whose
neighbour is not floor) and read: because lag is exactly 1, that read reflects
the real move's result while the wall-bump itself is the (harmless) new pending.
So after every hop `player_cell` is the TRUE settled cell. A move that fails to
displace is a sprite-mask wall -> learn (cell, action), re-plan.
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
    return [r for r in find_regions(grid, background=None)
            if r["color"] == 9 and 7 <= r["bbox"][0] <= 58 and 8 <= r["size"] <= 40]


class L1:
    def __init__(self, env):
        self.env = env
        self.off = self.goal_cell = self.player_cell = None
        self.blocked: set[tuple] = set()
        self.steps = 0

    def to_cell(self, cy, cx):
        return (round((cy-self.off[0])/CELL), round((cx-self.off[1])/CELL))

    def step(self, a):
        self.steps += 1
        return canonical_layer(self.env.step(A[a]))

    def obs_player(self, grid):
        cands = [self.to_cell(*(r["centroid"])) for r in nine(grid)]
        if not cands:
            return None
        cands = [c for c in cands if c != self.goal_cell] or cands
        if self.player_cell is not None:
            pc = self.player_cell
            return min(cands, key=lambda c: abs(c[0]-pc[0])+abs(c[1]-pc[1]))
        return cands[0]

    def floor(self, grid):
        if not grid or not grid[0]:
            return set()
        h, w = len(grid), len(grid[0])
        cells = set(); i = 0
        while self.off[0]+i*CELL < h-2:
            j = 0
            while self.off[1]+j*CELL < w-2:
                if grid[self.off[0]+i*CELL][self.off[1]+j*CELL] == FLOOR:
                    cells.add((i, j))
                j += 1
            i += 1
        return cells

    def color(self, grid, cell):
        r, c = self.off[0]+cell[0]*CELL, self.off[1]+cell[1]*CELL
        if 0 <= r < len(grid) and 0 <= c < len(grid[0]):
            return grid[r][c]
        return -1

    def wall_bump(self, grid, cell):
        floor = self.floor(grid)
        for a, (dr, dc) in MOVE.items():
            if (cell[0]+dr, cell[1]+dc) not in floor:
                return a
        return None

    def hop(self, grid, a, enter=None):
        """Issue move a from player_cell, confirm via wall-bump. Returns
        (grid, moved_bool). Updates player_cell + learns walls."""
        frm = self.player_cell
        dr, dc = MOVE[a]
        expect = (frm[0]+dr, frm[1]+dc)
        grid = self.step(a)                    # a now pending
        wb = self.wall_bump(grid, expect if self.color(grid, expect) == FLOOR or expect == enter else frm)
        if wb is None:
            wb = a  # no wall neighbour; re-issue (may overshoot, corrected next hop)
        grid = self.step(wb)                   # read now reflects a
        obs = self.obs_player(grid)
        if obs is None:
            return grid, False                 # blank frame (level lost/over)
        # drain wb: issue a second wall-bump so wb resolves and the NEXT read is clean
        if obs == expect:
            self.player_cell = expect
            moved = True
        elif obs == frm:
            self.blocked.add((frm, a))
            self.player_cell = frm
            moved = False
        else:
            self.player_cell = obs
            moved = obs != frm
        return grid, moved

    def bfs(self, floor, start, goal, enter):
        seen = {start}; parent = {}; q = deque([start])
        while q:
            cur = q.popleft()
            if cur == goal:
                break
            for a, (dr, dc) in MOVE.items():
                if (cur, a) in self.blocked:
                    continue
                n = (cur[0]+dr, cur[1]+dc)
                if (n in floor or n == goal or n == enter) and n not in seen:
                    seen.add(n); parent[n] = (cur, a); q.append(n)
        if goal not in parent:
            return None
        acts = []; cur = goal
        while cur in parent:
            acts.append(parent[cur][1]); cur = parent[cur][0]
        return acts[::-1]

    def drive(self, grid, target, enter=None, cycles=30):
        for _ in range(cycles):
            if self.player_cell == target:
                return grid, True
            plan = self.bfs(self.floor(grid), self.player_cell, target, enter)
            if not plan:
                return grid, False
            for a in plan:
                grid, moved = self.hop(grid, a, enter)
                if not moved:
                    break  # learned a wall; re-plan
                if self.player_cell == target:
                    return grid, True
        return grid, self.player_cell == target

    def drain(self, grid):
        """Issue a wall-bump to settle player_cell to the true cell."""
        wb = self.wall_bump(grid, self.player_cell)
        if wb is not None:
            grid = self.step(wb)
            self.player_cell = self.obs_player(grid)
        return grid

    def identify(self):
        grid = self.step(2)
        idc = [(r["centroid"][0], r["centroid"][1]) for r in nine(grid)]
        for a in [2, 4, 1, 3, 2, 4, 1, 3]:
            grid = self.step(a)
            now = [(r["centroid"][0], r["centroid"][1]) for r in nine(grid)]
            moved = [c for c in now if all(abs(c[0]-o[0])+abs(c[1]-o[1]) > 2 for o in idc)]
            static = [c for c in now if any(abs(c[0]-o[0])+abs(c[1]-o[1]) <= 2 for o in idc)]
            if moved:
                self.off = (int(round(moved[0][0])) % CELL, int(round(moved[0][1])) % CELL)
                self.player_cell = self.to_cell(*moved[0])
                self.goal_cell = self.to_cell(*static[0]) if static else None
                grid = self.drain(grid)  # settle after the pending identify move
                return grid
            idc = now
        return grid


def reach_set(g, floor, start):
    seen = {start}; q = deque([start])
    while q:
        cur = q.popleft()
        for a, (dr, dc) in MOVE.items():
            if (cur, a) in g.blocked:
                continue
            n = (cur[0]+dr, cur[1]+dc)
            if n in floor and n not in seen:
                seen.add(n); q.append(n)
    return seen


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("g50t")
    obs = reach_l1(env, env.observation_space)
    if int(getattr(obs, "levels_completed", 0) or 0) != 1:
        print("no L1"); return
    g = L1(env)
    grid = g.identify()
    floor0 = g.floor(grid)
    print(f"off={g.off} player={g.player_cell} goal={g.goal_cell} floor={len(floor0)} reach={len(reach_set(g, floor0, g.player_cell))}")
    plate_b = (4, 6)
    grid, ok = g.drive(grid, plate_b, enter=plate_b)
    print(f"drive->plate B {plate_b}: arrived={ok} player={g.player_cell} steps={g.steps} walls={sorted(g.blocked)}")
    if ok:
        floor_on = g.floor(grid)
        print(f"  ON PLATE: added={sorted(floor_on-floor0)} removed={sorted(floor0-floor_on)}")


if __name__ == "__main__":
    main()
