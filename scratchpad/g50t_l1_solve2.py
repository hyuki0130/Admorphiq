"""g50t L1 full two-ghost nested solver (empirical WIN attempt).

Phases (all frame-only, confirmed-hop lag-1 driver):
  P1: identify; drive to plate B (4,6) learning sprite-walls; Lg_B = displacements.
      press ACTION5 -> ghost B banked (replays in lockstep, holds barrier B open
      after Lg_B moves).
  P2: player rewound to spawn. Drive to plate A (6,2) over the GATED graph:
      barrier-B cell(s) passable iff moves_made > Lg_B. Lg_A = displacements.
      press ACTION5 -> ghost A banked.
  P3: player rewound. Drive to goal (3,4) over the graph gated by BOTH barriers
      (moves>Lg_B, moves>Lg_A). WIN when the player reaches goal (+ (1,1)).

The plates/barriers are DISCOVERED frame-only (colour-8 frontier + floor-expansion
on seat), NOT hardcoded cells. Prints each phase outcome + final state.
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


def discover_barrier(g, grid, floor_before, plate):
    """After arriving on `plate`, the barrier cells = floor cells added (slide-
    aware) minus the plate itself."""
    floor_after = g.floor(grid)
    added = floor_after - floor_before
    return {c for c in added if c != plate}


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("g50t")
    obs = reach_l1(env, env.observation_space)
    if int(getattr(obs, "levels_completed", 0) or 0) != 1:
        print("no L1"); return
    g = L1(env)
    grid = g.identify()
    spawn = g.player_cell
    floor0 = g.floor(grid)
    print(f"identify: spawn={spawn} goal={g.goal_cell} floor={len(floor0)} reach={len(reach_set(g, floor0, spawn))}")

    # ---- discover the two plates by driving to each colour-8 frontier cell ----
    def frontier(grid, reach):
        out = set()
        for cell in reach:
            for dr, dc in MOVE.values():
                n = (cell[0]+dr, cell[1]+dc)
                if n not in reach and g.color(grid, n) == 8:
                    out.add(n)
        return out

    reach0 = reach_set(g, floor0, spawn)
    fr = frontier(grid, reach0)
    print(f"colour-8 frontier: {sorted(fr)}")

    # Plate B = a reachable frontier cell whose entry expands floor. Try each.
    plate_b = barrier_b = None
    for cand in sorted(fr):
        fb = g.floor(grid)
        grid, ok = g.drive(grid, cand, enter=cand)
        if ok:
            bset = discover_barrier(g, grid, fb, cand)
            if bset:
                plate_b, barrier_b, lg_b = cand, bset, g.moves_since if hasattr(g, 'moves_since') else None
                print(f"plate B={cand} barrier_b={sorted(bset)} (reached, floor expanded)")
                break
        # not a plate; leave it (can't easily un-drive, but continue)
    if plate_b is None:
        print("no plate B found"); return

    # count Lg_B = displacements from spawn to plate B (path length)
    # recompute cleanly: BFS spawn->plate_b over learned graph
    def gated_bfs(start, goal, barriers, enter=None):
        """barriers: list of (cellset, Lg). A cell in cellset passable iff moves>Lg."""
        floor = g.floor(grid)
        seen = {(start, 0)}
        parent = {}
        q = deque([(start, 0)])
        while q:
            (cur, m) = q.popleft()
            if cur == goal:
                path = []
                s = (cur, m)
                while s in parent:
                    a, ps = parent[s]
                    path.append(a); s = ps
                return path[::-1]
            for a, (dr, dc) in MOVE.items():
                if (cur, a) in g.blocked:
                    continue
                n = (cur[0]+dr, cur[1]+dc)
                m2 = m+1
                ok = (n in floor) or (n == goal) or (n == enter)
                for (cs, lg) in barriers:
                    if n in cs:
                        ok = m2 > lg
                if ok and (n, m2) not in seen:
                    seen.add((n, m2)); parent[(n, m2)] = (a, (cur, m)); q.append((n, m2))
        return None

    print(f"walls learned so far: {sorted(g.blocked)}")
    print("NOTE: full nested phase execution is the next build step; this run "
          "validates plate/barrier discovery + gated BFS availability.")
    # gated BFS spawn->plate_a exists?
    # find plate A among remaining frontier now that barrier B is open
    reach_now = reach_set(g, g.floor(grid), g.player_cell)
    fr2 = frontier(grid, reach_now)
    print(f"frontier after B seated (live): {sorted(fr2)} reach={len(reach_now)} goal_in={g.goal_cell in reach_now}")


if __name__ == "__main__":
    main()
