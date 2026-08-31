"""g50t L1 solver as a GENERATOR (per-call protocol), driven by a harness-like
loop that mimics the adapter's choose_action. Validates the exact protocol the
adapter will use: the solver `grid = yield action` — the loop sends the frame
observed AFTER issuing each action. If this clears L1, the adapter port is a
copy-paste of the generator + helpers.
"""
from __future__ import annotations

import sys
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.g50t import Adapter
from admorphiq.adapters25.base import canonical_layer, state_name
from admorphiq.kernels import find_regions

A = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3,
     4: GameAction.ACTION4, 5: GameAction.ACTION5}
CELL = 6
MOVE = {1: (-1, 0), 2: (1, 0), 3: (0, -1), 4: (0, 1)}


def reach_l1(env, obs):
    ad = Adapter(giveup=2000)
    s = 0
    while s < 2000 and int(getattr(obs, "levels_completed", 0) or 0) < 1 and not ad.is_done([], obs):
        a = ad.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        s += 1
    return obs


class GenSolver:
    """Two-ghost L1 solver exposed as a generator (`_run`). Mirrors solve5 but in
    per-call form. All perception frame-only; no hardcoded cells."""

    def __init__(self):
        self.off = None
        self.goal = None
        self.pcell = None
        self.grid = None
        self.blocked: set = set()
        self.barriers: set = set()

    # ---- perception ----
    def nine(self, grid):
        return [r for r in find_regions(grid, background=None)
                if r["color"] == 9 and 7 <= r["bbox"][0] <= 58 and 8 <= r["size"] <= 40]

    def to_cell(self, cy, cx):
        return (round((cy - self.off[0]) / CELL), round((cx - self.off[1]) / CELL))

    def obs_player(self, grid):
        cands = [self.to_cell(*(r["centroid"])) for r in self.nine(grid)]
        if not cands:
            return None
        cands = [c for c in cands if c != self.goal] or cands
        if self.pcell is not None:
            pc = self.pcell
            return min(cands, key=lambda c: abs(c[0]-pc[0]) + abs(c[1]-pc[1]))
        return cands[0]

    def floor(self, grid):
        if not grid or not grid[0]:
            return set()
        h, w = len(grid), len(grid[0])
        cells = set(); i = 0
        while self.off[0]+i*CELL < h-2:
            j = 0
            while self.off[1]+j*CELL < w-2:
                if grid[self.off[0]+i*CELL][self.off[1]+j*CELL] == 5:
                    cells.add((i, j))
                j += 1
            i += 1
        return cells

    def color(self, grid, cell):
        r, c = self.off[0]+cell[0]*CELL, self.off[1]+cell[1]*CELL
        if 0 <= r < len(grid) and 0 <= c < len(grid[0]):
            return grid[r][c]
        return -1

    def open_barriers(self):
        return {c for c in self.barriers if self.color(self.grid, c) == 5}

    def wall_bump(self, cell):
        floor = self.floor(self.grid)
        for a, (dr, dc) in MOVE.items():
            if (cell[0]+dr, cell[1]+dc) not in floor:
                return a
        return None

    def reach(self, passable, start):
        seen = {start}; q = deque([start])
        while q:
            cur = q.popleft()
            for a, (dr, dc) in MOVE.items():
                if (cur, a) in self.blocked:
                    continue
                n = (cur[0]+dr, cur[1]+dc)
                if n in passable and n not in seen:
                    seen.add(n); q.append(n)
        return seen

    def plan(self, start, target, enter):
        pass_set = self.floor(self.grid) | self.open_barriers()
        seen = {start}; parent = {}; q = deque([start])
        while q:
            cur = q.popleft()
            if cur == target:
                acts = []; c = cur
                while c in parent:
                    a, p = parent[c]; acts.append(a); c = p
                return acts[::-1]
            for a, (dr, dc) in MOVE.items():
                if (cur, a) in self.blocked:
                    continue
                n = (cur[0]+dr, cur[1]+dc)
                if (n in pass_set or n == target or n == enter) and n not in seen:
                    seen.add(n); parent[n] = (a, cur); q.append(n)
        return None

    # ---- generator primitives ----
    def _yield(self, a):
        g = yield a
        self.grid = g
        return g

    def _batch(self, plan):
        """Open-loop plan + 1 flush, reconcile lag-1. Returns (confirmed, wall)."""
        start = self.pcell
        planned = [start]
        for a in plan:
            dr, dc = MOVE[a]
            planned.append((planned[-1][0]+dr, planned[-1][1]+dc))
        obs_log = [start]
        for a in plan:
            g = yield from self._yield(a)
            p = self.obs_player(g)
            obs_log.append(p)
            if p is None:
                return start, None
        wb = self.wall_bump(planned[-1]) or self.wall_bump(start) or 1
        g = yield from self._yield(wb)
        pf = self.obs_player(g)
        obs_log.append(pf if pf is not None else obs_log[-1])
        for k in range(len(plan)):
            true_after = obs_log[k+2] if k+2 < len(obs_log) else obs_log[-1]
            if true_after == planned[k+1]:
                continue
            self.blocked.add((planned[k], plan[k]))
            self.pcell = planned[k]
            return planned[k], (planned[k], plan[k])
        self.pcell = planned[-1]
        return planned[-1], None

    def _filler(self):
        floor = self.floor(self.grid)
        for a, (dr, dc) in MOVE.items():
            n = (self.pcell[0]+dr, self.pcell[1]+dc)
            if n in floor and (self.pcell, a) not in self.blocked:
                yield from self._batch([a])
                return
        wb = self.wall_bump(self.pcell) or 1
        yield from self._yield(wb)

    def _drive(self, target, enter=None, cycles=80, max_wait=45):
        waited = 0
        for _ in range(cycles):
            if self.pcell == target:
                return True
            if not self.nine(self.grid):
                return False
            plan = self.plan(self.pcell, target, enter)
            if not plan:
                if waited >= max_wait:
                    return False
                waited += 1
                yield from self._filler()
                continue
            conf, wall = yield from self._batch(plan)
            if self.pcell == target:
                return True
            if wall is None and conf != target:
                if waited >= max_wait:
                    return False
                waited += 1
                yield from self._filler()
        return self.pcell == target

    def _frontier8(self, region):
        out = set()
        for cell in region:
            for dr, dc in MOVE.values():
                n = (cell[0]+dr, cell[1]+dc)
                if n not in region and self.color(self.grid, n) == 8:
                    out.add(n)
        return out

    def _discover(self, seated, wait, known_plates):
        floor = self.floor(self.grid)
        reach_seat = self.reach(floor | seated, self.pcell)
        near = {(c[0]+dr, c[1]+dc) for c in self.barriers for dr, dc in MOVE.values()} | self.barriers
        pool = self._frontier8(reach_seat) - self.barriers - set(known_plates) - near
        p = self.pcell
        ordered = sorted(pool, key=lambda c: abs(c[0]-p[0]) + abs(c[1]-p[1]))
        cands = []
        for cand in ordered:
            for a, (dr, dc) in MOVE.items():
                ap = (cand[0]-dr, cand[1]-dc)
                if ap in reach_seat and (ap, a) not in self.blocked:
                    cands.append(cand); break
        for cand in cands:
            fb = self.floor(self.grid)
            ok = yield from self._drive(cand, enter=cand, max_wait=wait)
            added = {c for c in (self.floor(self.grid) - fb) if c != cand}
            if ok and added:
                return cand, added
        return None, None

    def _settle_rewind(self, spawn, tries=12):
        for _ in range(tries):
            obs = self.obs_player(self.grid)
            if obs is not None:
                self.pcell = obs
            if self.pcell == spawn:
                return
            wb = self.wall_bump(self.pcell) or 1
            yield from self._yield(wb)

    def _identify(self):
        g = yield from self._yield(2)  # snap probe
        idc = [(r["centroid"][0], r["centroid"][1]) for r in self.nine(g)]
        for a in [2, 4, 1, 3, 2, 4, 1, 3]:
            g = yield from self._yield(a)
            now = [(r["centroid"][0], r["centroid"][1]) for r in self.nine(g)]
            moved = [c for c in now if all(abs(c[0]-o[0])+abs(c[1]-o[1]) > 2 for o in idc)]
            static = [c for c in now if any(abs(c[0]-o[0])+abs(c[1]-o[1]) <= 2 for o in idc)]
            if moved:
                self.off = (int(round(moved[0][0])) % CELL, int(round(moved[0][1])) % CELL)
                self.pcell = self.to_cell(*moved[0])
                self.goal = self.to_cell(*static[0]) if static else None
                wb = self.wall_bump(self.pcell) or 1
                g = yield from self._yield(wb)  # drain
                op = self.obs_player(g)
                if op is not None:
                    self.pcell = op
                return
            idc = now

    def run(self):
        self.grid = yield  # prime
        yield from self._identify()
        print(f"  [gen] identify off={self.off} spawn={self.pcell} goal={self.goal}", flush=True)
        if self.off is None or self.goal is None:
            while True:
                yield 1
        spawn = self.pcell
        seated = set()
        known = []
        for gi in range(4):
            if self.goal in self.reach(self.floor(self.grid) | seated, self.pcell):
                print(f"  [gen] goal reachable after {gi} ghosts; walking", flush=True)
                break
            wait = 60 if seated else 0
            plate, barr = yield from self._discover(seated, wait, known)
            print(f"  [gen] ghost {gi}: plate={plate} barr={sorted(barr) if barr else None}", flush=True)
            if plate is None:
                break
            self.barriers |= barr
            known.append(plate)
            yield from self._yield(5)
            yield from self._settle_rewind(spawn)
            seated |= barr
        for gt in (self.goal, (self.goal[0]+1, self.goal[1]+1),
                   (self.goal[0]+1, self.goal[1]), (self.goal[0], self.goal[1]+1)):
            yield from self._drive(gt, enter=gt, cycles=60)
        print(f"  [gen] done walking; player={self.pcell}", flush=True)
        while True:
            yield 1


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("g50t")
    obs = reach_l1(env, env.observation_space)
    if int(getattr(obs, "levels_completed", 0) or 0) != 1:
        print("no L1"); return
    sol = GenSolver()
    gen = sol.run()
    next(gen)  # prime
    lvl_seen = 1
    steps = 0
    while steps < 800:
        if state_name(obs) == "GAME_OVER":
            print(f"GAME_OVER at step {steps}"); break
        lvl = int(getattr(obs, "levels_completed", 0) or 0)
        if lvl != lvl_seen:  # mimic adapter: fresh solver per level
            print(f"*** LEVEL {lvl_seen}->{lvl} at step {steps} ***")
            lvl_seen = lvl
            sol = GenSolver()
            gen = sol.run()
            next(gen)
        grid = canonical_layer(obs)
        try:
            act = gen.send(grid)
        except StopIteration:
            act = 1
        obs = env.step(A[act])
        steps += 1
    fin = int(getattr(obs, 'levels_completed', 0) or 0)
    print(f"END steps={steps} levels_completed={fin}")


if __name__ == "__main__":
    main()
