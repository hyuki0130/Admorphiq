"""g50t L1 SLAM stage 7: lag-1 batch driver (open-loop + flush + reconcile +
learn sprite-walls) -> reach plate B (4,6), confirm the barrier-open mechanic.

Lag is uniformly 1 (calibrated): the frame after issuing move k reflects move
k-1. Drive in batches: plan over frame-floor minus learned walls, execute the
plan open-loop, issue ONE flush no-op (a move into a known wall from the final
cell) so the last move's result is observed, then shift the observation log by 1
to recover the true trajectory. The first cell that fails to advance = a
sprite-mask wall on that (cell,action) edge; learn it and re-plan.
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

    def to_cell(self, cy, cx):
        return (round((cy - self.off[0]) / CELL), round((cx - self.off[1]) / CELL))

    def step(self, a):
        return canonical_layer(self.env.step(A[a]))

    def player_obs(self, grid):
        cands = [self.to_cell(*(r["centroid"])) for r in nine(grid)]
        cands = [c for c in cands if c != self.goal_cell] or cands
        if self.player_cell is not None:
            pc = self.player_cell
            return min(cands, key=lambda c: abs(c[0]-pc[0])+abs(c[1]-pc[1]))
        return cands[0] if cands else None

    def floor(self, grid):
        h, w = len(grid), len(grid[0])
        cells = set()
        i = 0
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

    def wall_dir_from(self, grid, cell, floor):
        """A move whose neighbour is not floor -> guaranteed no-op flush."""
        for a, (dr, dc) in MOVE.items():
            n = (cell[0]+dr, cell[1]+dc)
            if n not in floor:
                return a
        return 1

    def drive(self, grid, target, enter=None, cycles=16):
        for _ in range(cycles):
            pos = self.player_cell
            if pos == target:
                return grid, True
            floor = self.floor(grid)
            plan = self.bfs(floor, pos, target, enter)
            if not plan:
                return grid, False
            # planned trajectory
            traj = [pos]
            for a in plan:
                dr, dc = MOVE[a]
                traj.append((traj[-1][0]+dr, traj[-1][1]+dc))
            # execute open-loop
            obs_log = []
            for a in plan:
                grid = self.step(a)
                obs_log.append(self.player_obs(grid))
            # flush: one no-op from final planned cell so plan[-1]'s result shows
            fa = self.wall_dir_from(grid, traj[-1], floor)
            grid = self.step(fa)
            obs_log.append(self.player_obs(grid))
            # obs_log[i] reflects plan[i-1]; obs_log[i+1] reflects plan[i].
            # so true pos after plan[i] = obs_log[i+1]. compare to traj[i+1].
            wall_found = False
            confirmed = pos
            for i in range(len(plan)):
                true_after = obs_log[i+1]
                if true_after == traj[i+1]:
                    confirmed = true_after
                    continue
                # plan[i] failed to advance from traj[i]; learn wall
                self.blocked.add((traj[i], plan[i]))
                confirmed = obs_log[i] if i < len(obs_log) else true_after
                wall_found = True
                break
            self.player_cell = confirmed
            if not wall_found:
                self.player_cell = obs_log[-1]  # settled at end (flush may have moved)
                # correct: after flush no-op, obs_log[-1] should equal traj[-1]
                self.player_cell = traj[-1]
        return grid, self.player_cell == target

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
                # drain lag: one no-op read so player_cell reflects reality
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
    print(f"drive->plate B {plate_b}: arrived={ok} player={g.player_cell} walls={sorted(g.blocked)}")
    if ok:
        floor_on = g.floor(grid)
        print(f"  on plate: added={sorted(floor_on-floor0)} removed={sorted(floor0-floor_on)}")
        print(f"  reach on-plate from goal-approach: {len(reach_set(g, floor_on, g.player_cell))}")


if __name__ == "__main__":
    main()
