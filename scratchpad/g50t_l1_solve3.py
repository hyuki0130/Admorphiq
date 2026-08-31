"""g50t L1 full two-ghost nested solver — WIN attempt (frame-only, generic).

Uses the validated confirmed-hop lag-1 driver (g50t_l1_slam8.L1). Plates and
barriers are DISCOVERED from colour-8 frontier + floor-expansion-on-seat; the
gated (cell, displacements) BFS handles the lockstep ghost replay (a barrier cell
is passable only after displacements > Lg_i, since a blocked move does not advance
a ghost). No hardcoded cells.
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
from g50t_l1_slam8 import L1, nine, reach_set, MOVE

DISP_CAP = 120
A = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3,
     4: GameAction.ACTION4, 5: GameAction.ACTION5}


def reach_l1(env, obs):
    ad = Adapter(giveup=2000)
    s = 0
    while s < 2000 and int(getattr(obs, "levels_completed", 0) or 0) < 1 and not ad.is_done([], obs):
        a = ad.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        s += 1
    return obs


class Solver(L1):
    def gated_plan(self, start, goal, barriers, enter=None):
        """BFS over (cell, disp): barrier cellset passable iff disp > Lg."""
        floor = self.floor(self._grid)
        seen = {(start, 0)}
        parent = {}
        q = deque([(start, 0)])
        while q:
            cur, m = q.popleft()
            if cur == goal:
                acts = []
                s = (cur, m)
                while s in parent:
                    a, ps = parent[s]
                    acts.append(a); s = ps
                return acts[::-1]
            for a, (dr, dc) in MOVE.items():
                if (cur, a) in self.blocked:
                    continue
                n = (cur[0]+dr, cur[1]+dc)
                m2 = m + 1
                if m2 > DISP_CAP:
                    continue
                ok = (n in floor) or (n == goal) or (n == enter)
                for cs, lg in barriers:
                    if n in cs:
                        ok = (m2 > lg) or (n == goal) or (n == enter)
                if ok and (n, m2) not in seen:
                    seen.add((n, m2)); parent[(n, m2)] = (a, (cur, m)); q.append((n, m2))
        return None

    def gated_reach(self, start, barriers):
        floor = self.floor(self._grid)
        seen = {(start, 0)}
        cells = {start}
        q = deque([(start, 0)])
        while q:
            cur, m = q.popleft()
            for a, (dr, dc) in MOVE.items():
                if (cur, a) in self.blocked:
                    continue
                n = (cur[0]+dr, cur[1]+dc)
                m2 = m+1
                if m2 > DISP_CAP:
                    continue
                ok = n in floor
                for cs, lg in barriers:
                    if n in cs:
                        ok = m2 > lg
                if ok and (n, m2) not in seen:
                    seen.add((n, m2)); cells.add(n); q.append((n, m2))
        return cells

    def drive_gated(self, target, barriers, enter=None, cycles=40):
        """Confirmed-hop drive over the gated graph, counting displacements."""
        disp = 0
        for _ in range(cycles):
            if self.player_cell == target:
                return True, disp
            plan = self.gated_plan_from(self.player_cell, disp, target, barriers, enter)
            if not plan:
                return False, disp
            for a in plan:
                frm = self.player_cell
                self._grid, moved = self.hop(self._grid, a, enter)
                if moved:
                    disp += 1
                    if self.player_cell == target:
                        return True, disp
                else:
                    break
        return self.player_cell == target, disp

    def gated_plan_from(self, start, disp0, goal, barriers, enter):
        floor = self.floor(self._grid)
        seen = {(start, disp0)}
        parent = {}
        q = deque([(start, disp0)])
        while q:
            cur, m = q.popleft()
            if cur == goal:
                acts = []
                s = (cur, m)
                while s in parent:
                    a, ps = parent[s]
                    acts.append(a); s = ps
                return acts[::-1]
            for a, (dr, dc) in MOVE.items():
                if (cur, a) in self.blocked:
                    continue
                n = (cur[0]+dr, cur[1]+dc)
                m2 = m+1
                if m2 > DISP_CAP:
                    continue
                ok = (n in floor) or (n == goal) or (n == enter)
                for cs, lg in barriers:
                    if n in cs:
                        ok = (m2 > lg) or (n == goal) or (n == enter)
                if ok and (n, m2) not in seen:
                    seen.add((n, m2)); parent[(n, m2)] = (a, (cur, m)); q.append((n, m2))
        return None

    def settle_rewind(self, spawn):
        for _ in range(10):
            obs = self.obs_player(self._grid)
            if obs is not None:
                self.player_cell = obs
            if self.player_cell == spawn:
                break
            wb = self.wall_bump(self._grid, self.player_cell) or 1
            self._grid = self.step(wb)


def frontier8(s, reach):
    out = set()
    for cell in reach:
        for dr, dc in MOVE.values():
            n = (cell[0]+dr, cell[1]+dc)
            if n not in reach and s.color(s._grid, n) == 8:
                out.add(n)
    return out


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("g50t")
    obs = reach_l1(env, env.observation_space)
    if int(getattr(obs, "levels_completed", 0) or 0) != 1:
        print("no L1"); return
    s = Solver(env)
    s._grid = s.identify()
    spawn = s.player_cell
    floor0 = s.floor(s._grid)
    goal = s.goal_cell
    print(f"identify spawn={spawn} goal={goal} floor={len(floor0)}")

    # -- Phase 1: discover + drive to plate B, seat ghost B --
    reach0 = reach_set(s, floor0, spawn)
    cands = sorted(frontier8(s, reach0))
    plate_b = barrier_b = None
    lg_b = 0
    for cand in cands:
        fb = s.floor(s._grid)
        # count displacements while driving to this candidate
        disp0 = s.steps
        ok, d = s.drive_gated(cand, [], enter=cand)
        if ok:
            added = s.floor(s._grid) - fb
            bset = {c for c in added if c != cand}
            if bset:
                plate_b, barrier_b, lg_b = cand, bset, d
                print(f"plate B={cand} barrier_b={sorted(bset)} Lg_B={d}")
                break
    if plate_b is None:
        print("FAIL: no plate B"); return
    s._grid = s.step(5)  # ACTION5 ghost B
    s.settle_rewind(spawn)
    print(f"after A5(B): player={s.player_cell}")

    # -- Phase 2: discover plate A in the barrier-B-open region, drive gated, seat ghost A --
    barsB = [(barrier_b, lg_b)]
    s.player_cell = s.obs_player(s._grid) or s.player_cell
    print(f"phase2 start player={s.player_cell} blocked_walls={sorted(s.blocked)}")
    greach = s.gated_reach(s.player_cell, barsB)
    print(f"gated_reach from player incl (8,6)? {(8,6) in greach} (8,5)? {(8,5) in greach} (3,1)? {(3,1) in greach} (3,2)? {(3,2) in greach}")
    candsA = sorted(frontier8(s, greach) - {plate_b})
    print(f"gated reach (B open) = {len(greach)} plateA candidates={candsA}")
    print(f"gated reach cells: {sorted(greach)}")
    for t in [(6, 2), (6, 1)]:
        pl = s.gated_plan_from(s.player_cell, 0, t, barsB, t)
        print(f"plan player->{t}: len={len(pl) if pl else None} {pl}")
    plate_a = barrier_a = None
    lg_a = 0
    for cand in candsA:
        fb = s.floor(s._grid)
        ok, d = s.drive_gated(cand, barsB, enter=cand)
        if ok:
            added = s.floor(s._grid) - fb
            bset = {c for c in added if c != cand}
            plate_a, barrier_a, lg_a = cand, bset, d
            print(f"plate A={cand} barrier_a={sorted(bset)} Lg_A={d} arrived")
            break
        else:
            print(f"  cand {cand}: drive failed (player={s.player_cell})")
    if plate_a is None:
        print("FAIL: no plate A reached"); return
    s._grid = s.step(5)  # ACTION5 ghost A
    s.settle_rewind(spawn)
    print(f"after A5(A): player={s.player_cell}")

    # -- Phase 3: drive to goal gated by both barriers --
    barsAll = [(barrier_b, lg_b), (barrier_a, lg_a)]
    ok, d = s.drive_gated(goal, barsAll, enter=None)
    st = state_name(canonical_layer(env.observation_space)) if False else None
    print(f"phase3 drive to goal: arrived={ok} player={s.player_cell} disp={d} steps={s.steps}")
    # check WIN
    from admorphiq.adapters25.base import state_name as sn
    # peek current state via a no-op read
    g = s._grid
    print("done. (WIN detection: run under script25 for authoritative levels_completed)")


if __name__ == "__main__":
    main()
