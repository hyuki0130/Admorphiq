"""g50t L1 full solver v5 — REACTIVE barrier gating (frame-observed), WIN attempt.

Key insight (measured): after ACTION5 the ghost replays its recorded path
autonomously and seats on its plate after ~len(path) of my env.steps; the barrier
cell's OPEN/CLOSED state is directly FRAME-OBSERVABLE (colour 5 = open floor,
8 = closed block). The ghost is NOT a colour-9 blob, so player tracking is
unaffected. So instead of computing the ghost clock (Lg), gate every barrier
cell LIVE by its current frame colour, and do safe filler moves while a needed
barrier is still closed (which advances the ghost clock until it opens).

Phases: discover+seat ghost B -> reach+seat ghost A -> walk to goal. All barrier
crossings gated on live frame colour. No hardcoded cells.
"""
from __future__ import annotations

import sys
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.base import canonical_layer, state_name
from g50t_l1_slam8 import L1, nine, reach_set, MOVE, VEC

A = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3,
     4: GameAction.ACTION4, 5: GameAction.ACTION5}


def reach_l1(env, obs):
    from admorphiq.adapters25.g50t import Adapter
    ad = Adapter(giveup=2000)
    s = 0
    while s < 2000 and int(getattr(obs, "levels_completed", 0) or 0) < 1 and not ad.is_done([], obs):
        a = ad.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        s += 1
    return obs


class Solver(L1):
    def __init__(self, env):
        super().__init__(env)
        self.barriers: set = set()  # all known barrier cells (union over circuits)

    def open_barriers(self):
        return {c for c in self.barriers if self.color(self._grid, c) == 5}

    def passable(self, cell, enter):
        if cell == enter:
            return True
        if cell in self.barriers:
            return self.color(self._grid, cell) == 5
        return cell in self.floor(self._grid)

    def plan(self, start, target, enter):
        floor = self.floor(self._grid)
        openb = self.open_barriers()
        pass_set = floor | openb
        seen = {start}
        parent = {}
        q = deque([start])
        while q:
            cur = q.popleft()
            if cur == target:
                acts = []
                c = cur
                while c in parent:
                    a, p = parent[c]
                    acts.append(a); c = p
                return acts[::-1]
            for a, (dr, dc) in MOVE.items():
                if (cur, a) in self.blocked:
                    continue
                n = (cur[0]+dr, cur[1]+dc)
                if (n in pass_set or n == target or n == enter) and n not in seen:
                    seen.add(n); parent[n] = (a, cur); q.append(n)
        return None

    def batch_execute(self, plan):
        """Execute ``plan`` (list of actions) open-loop, then ONE flush no-op, and
        reconcile the lag-1 observation log. Returns (confirmed_cell, wall) where
        wall=(cell,action) if a sprite-mask wall was hit (learn+replan), else None.
        Assumes the pipeline is DRAINED at entry (player_cell = true current)."""
        start = self.player_cell
        planned = [start]
        for a in plan:
            dr, dc = MOVE[a]
            planned.append((planned[-1][0]+dr, planned[-1][1]+dc))
        obs_log = [start]
        for a in plan:
            grid = self.step(a)
            p = self.obs_player(grid)
            obs_log.append(p)
            self._grid = grid
            if p is None:
                return start, None  # blank frame
        # flush no-op so plan[-1]'s result is observed (lag-1: needs 1 extra read)
        wb = self.wall_bump(self._grid, planned[-1]) or self.wall_bump(self._grid, start) or 1
        self._grid = self.step(wb)
        pflush = self.obs_player(self._grid)
        obs_log.append(pflush if pflush is not None else obs_log[-1])
        # lag-1: obs_log[1] reflects the pre-batch no-op (== start); the true
        # position after plan[k] is obs_log[k+2].
        for k in range(len(plan)):
            true_after = obs_log[k+2] if k+2 < len(obs_log) else obs_log[-1]
            if true_after == planned[k+1]:
                continue
            self.blocked.add((planned[k], plan[k]))
            self.player_cell = planned[k]
            return planned[k], (planned[k], plan[k])
        self.player_cell = planned[-1]
        return planned[-1], None

    def safe_filler(self):
        """One displacing move (drained via batch) to advance the ghost clock
        while waiting for a barrier to replay open."""
        floor = self.floor(self._grid)
        for a, (dr, dc) in MOVE.items():
            n = (self.player_cell[0]+dr, self.player_cell[1]+dc)
            if n in floor and (self.player_cell, a) not in self.blocked:
                self.batch_execute([a])
                return
        wb = self.wall_bump(self._grid, self.player_cell) or 1
        self._grid = self.step(wb)  # no floor neighbour: plain wall-bump

    def drive_reactive(self, target, enter=None, cycles=80, max_wait=45):
        waited = 0
        for _ in range(cycles):
            if self.player_cell == target:
                return True
            if state_name(self.env.observation_space) in ("GAME_OVER", "WIN"):
                return self.player_cell == target
            if not nine(self._grid):
                return False
            plan = self.plan(self.player_cell, target, enter)
            if not plan:
                if waited >= max_wait:
                    return False
                waited += 1
                self.safe_filler()
                continue
            conf, wall = self.batch_execute(plan)
            if self.player_cell == target:
                return True
            if wall is None and conf != target:
                # batch finished without reaching target (barrier still closed
                # when planned across); wait a beat then re-plan on live state
                if waited >= max_wait:
                    return False
                waited += 1
                self.safe_filler()
        return self.player_cell == target

    def settle_rewind(self, spawn, tries=12):
        for _ in range(tries):
            obs = self.obs_player(self._grid)
            if obs is not None:
                self.player_cell = obs
            if self.player_cell == spawn:
                return
            wb = self.wall_bump(self._grid, self.player_cell) or 1
            self._grid = self.step(wb)

    def identify(self):
        self._grid = super().identify()
        return self._grid


def frontier8(s, reach):
    out = set()
    for cell in reach:
        for dr, dc in MOVE.values():
            n = (cell[0]+dr, cell[1]+dc)
            if n not in reach and s.color(s._grid, n) == 8:
                out.add(n)
    return out


def discover_plate(s, spawn, seated, wait, known_plates):
    """Drive to each colour-8 frontier cell of the region reachable ASSUMING the
    SEATED-ghost barriers open (those WILL open this phase). Exclude known
    barriers + already-found plates. Return the first whose entry EXPANDS the
    floor (a plate) + its opened barrier cells. ``wait`` = filler budget while a
    seated barrier is still replaying open."""
    floor = s.floor(s._grid)
    reach_if_seated = reach_set2(s, floor | seated, s.player_cell)
    p = s.player_cell
    # a barrier BLOCK's cells cluster (a slide occupies adjacent colour-8 cells);
    # the next circuit's plate is elsewhere, so drop colour-8 cells touching a
    # known barrier cell -- they are the same block, not a new plate.
    near_barrier = {(c[0]+dr, c[1]+dc) for c in s.barriers for dr, dc in MOVE.values()} | s.barriers
    pool = frontier8_of(s, reach_if_seated) - s.barriers - set(known_plates) - near_barrier
    ordered = sorted(pool, key=lambda c: abs(c[0]-p[0]) + abs(c[1]-p[1]))
    cands = []
    for cand in ordered:
        for a, (dr, dc) in MOVE.items():
            ap = (cand[0] - dr, cand[1] - dc)
            if ap in reach_if_seated and (ap, a) not in s.blocked:
                cands.append(cand)
                break
    print(f"  discover candidates: {cands} (wait={wait})")
    for cand in cands:
        fb = s.floor(s._grid)
        ok = s.drive_reactive(cand, enter=cand, max_wait=wait)
        added = {c for c in (s.floor(s._grid) - fb) if c != cand}
        print(f"    try {cand}: reached={ok} player={s.player_cell} added={sorted(added)} steps={s.steps}")
        if ok and added:
            return cand, added
    return None, None


def frontier8_of(s, region):
    out = set()
    for cell in region:
        for dr, dc in MOVE.values():
            n = (cell[0]+dr, cell[1]+dc)
            if n not in region and s.color(s._grid, n) == 8:
                out.add(n)
    return out


def reach_set2(s, passable, start):
    seen = {start}
    q = deque([start])
    while q:
        cur = q.popleft()
        for a, (dr, dc) in MOVE.items():
            if (cur, a) in s.blocked:
                continue
            n = (cur[0]+dr, cur[1]+dc)
            if n in passable and n not in seen:
                seen.add(n); q.append(n)
    return seen


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("g50t")
    obs = reach_l1(env, env.observation_space)
    if int(getattr(obs, "levels_completed", 0) or 0) != 1:
        print("no L1"); return
    s = Solver(env)
    s.identify()
    spawn = s.player_cell
    goal = s.goal_cell
    print(f"identify spawn={spawn} goal={goal} floor={len(s.floor(s._grid))}")

    # Phase 1: plate B (no ghost seated yet -> no barrier can open, wait=0)
    plate_b, barr_b = discover_plate(s, spawn, seated=set(), wait=0, known_plates=[])
    if plate_b is None:
        print("FAIL: no plate B"); return
    s.barriers |= barr_b
    print(f"plate B={plate_b} barrier_b={sorted(barr_b)} (on plate, steps={s.steps})")
    s._grid = s.step(5)
    s.settle_rewind(spawn)
    print(f"after A5(B): player={s.player_cell}")

    # Phase 2: plate A (ghost B seating -> barrier B WILL open; wait for it)
    plate_a, barr_a = discover_plate(s, spawn, seated=barr_b, wait=60, known_plates=[plate_b])
    if plate_a is None:
        print(f"FAIL: no plate A (player={s.player_cell} steps={s.steps})"); return
    s.barriers |= barr_a
    print(f"plate A={plate_a} barrier_a={sorted(barr_a)} (steps={s.steps})")
    s._grid = s.step(5)
    s.settle_rewind(spawn)
    print(f"after A5(A): player={s.player_cell}")

    # Phase 3: goal (both barriers open reactively). Also try the win cell
    # goal+(1,1) (source win = player at goal+(1,1)). Detect levels increment.
    lvl0 = int(getattr(env.observation_space, "levels_completed", 0) or 0)
    for gtarget in (goal, (goal[0]+1, goal[1]+1), (goal[0]+1, goal[1]), (goal[0], goal[1]+1)):
        ok = s.drive_reactive(gtarget, enter=gtarget, cycles=60)
        lvl = int(getattr(env.observation_space, "levels_completed", 0) or 0)
        st = state_name(env.observation_space)
        print(f"phase3 -> {gtarget}: arrived={ok} player={s.player_cell} state={st} levels={lvl} steps={s.steps}")
        if lvl > lvl0:
            print(f"*** L1 CLEARED! levels {lvl0}->{lvl} ***")
            break
        if st in ("GAME_OVER", "WIN") or not nine(s._grid):
            break


if __name__ == "__main__":
    main()
