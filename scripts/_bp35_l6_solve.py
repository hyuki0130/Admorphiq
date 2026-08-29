"""Is bp35's level 6 solvable, and is the `yuuqpmlxorv` toggle on the solution path?

The wiki records that tile as a CRUMBLING PLATFORM whose four sprites shrink in stages and whose
change is "driven by use, not by clicks". The game's source says the opposite: `gwfodrkvzx` swaps it
with `oonshderxef` (pass-through) on a CLICK, and swaps back, so it is a build/remove block and the
four sprites are that swap's animation. Nobody has tested whether it blocks the level.

This searches the verified simulator (`scripts/_bp35_sim.py`, 0 mismatches over 40 random trials on
this level) breadth-first inside the engine's own 64-action allowance, and reports the shortest win
plus whether that plan clicks the toggle.

Expected feedback: a plan with toggle clicks in it makes the toggle load-bearing and names the move
vocabulary crag lacks. A plan without any makes the toggle decoration, exactly as dc22's cycling tile
turned out to be. No plan at all means the level is not winnable in its own budget and the whole
reading is wrong.

Usage: _bp35_l6_solve.py <seed>  — seed selects a tie-break ordering so 60 of these explore the
frontier in different orders; seed 1 is the deterministic reference.
"""
from __future__ import annotations

import json
import heapq
import random
import sys
import time
from collections import deque

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _bp35_sim import PASS_TOGGLE, SOLID_TOGGLE, load_module, make_level  # noqa: E402

BUDGET = 64


GEM_XY = {6: (2, 31)}


def solve(seed: int, cap: int, level: int = 6, force_local: bool = False, radius: int = 0):
    """mode 0 = plain BFS inside the engine's own 64-action allowance (finds the SHORTEST win);
    mode 1 = greedy best-first on distance to the gem (finds A win fast, not the shortest);
    mode 2 = BFS with the allowance lifted to 200 — "winnable at all?" is a DIFFERENT claim from
    "winnable inside the budget" and the two must not be conflated.

    ⛔ States are held as (Sim, parent index, action) with the path reconstructed at the end. A
    per-state path list makes a complete search of this level impossible to run on memory alone."""
    mode = (seed - 1) % 3 if force_local else (seed - 1) % 6
    limit = 200 if mode % 3 == 2 else BUDGET
    # modes 3..5 restrict the click candidates to crag's OWN site rule (`_sites`): the support, the
    # two cells beside the body, the two that would hold it one step away — plus every gravity
    # switch on screen. If a win still exists under that restriction the tool's frontier is wide
    # enough and the wall is search depth; if it does not, the site rule itself excludes the route.
    local = force_local or mode >= 3
    m = load_module()
    _, start = make_level(m, level)
    rng = random.Random(seed)
    t0 = time.time()
    gx0, gy0 = GEM_XY.get(level, (2, 31))

    sims = [start]
    par = [(-1, None)]
    depth = [0]
    seen = {(start.key(), start.cam_y)}
    q = deque([0])
    heap = [(abs(start.px - gx0) + abs(start.py - gy0), 0.0, 0)]
    best = None
    nodes = 0
    tick = 0
    while q or heap:
        if mode == 1:
            if not heap:
                break
            _, _, idx = heapq.heappop(heap)
        else:
            if not q:
                break
            idx = q.popleft()
        s = sims[idx]
        d = depth[idx]
        tick += 1
        if tick % 20000 == 0:
            print(f"# seed={seed} mode={mode} nodes={nodes} states={len(sims)} depth={d} "
                  f"secs={round(time.time()-t0,1)}", file=sys.stderr, flush=True)
        if d >= limit - 1:
            continue
        cand = s.clickables()
        if local:
            dy = -1 if s.grav_up else 1
            near = {(s.px, s.py + dy), (s.px - 1, s.py), (s.px + 1, s.py),
                    (s.px - 1, s.py + dy), (s.px + 1, s.py + dy)}
            # radius 0 is crag's rule EXACTLY; radius k also offers every editable cell within
            # Chebyshev distance k of the body, which is the cheapest way to size how far the site
            # rule has to widen before a win exists at all.
            cand = [c for c in cand
                    if c in near
                    or next(iter(s.at(*c)), "") == "lrpkmzabbfa"
                    or (radius and max(abs(c[0] - s.px), abs(c[1] - s.py)) <= radius)]
        opts = [("L",), ("R",)] + [("C", c) for c in cand]
        rng.shuffle(opts)
        for a in opts:
            nxt = s.clone()
            if a[0] == "L":
                nxt.move(False)
            elif a[0] == "R":
                nxt.move(True)
            else:
                nxt.click_cell(*a[1])
            nodes += 1
            if nxt.lost:
                continue
            if nxt.won:
                sims.append(nxt); par.append((idx, a)); depth.append(d + 1)
                best = len(sims) - 1
                break
            k = (nxt.key(), nxt.cam_y)
            if k in seen:
                continue
            seen.add(k)
            sims.append(nxt); par.append((idx, a)); depth.append(d + 1)
            j = len(sims) - 1
            if mode == 1:
                heapq.heappush(heap, (abs(nxt.px - gx0) + abs(nxt.py - gy0) + (d + 1) // 8,
                                      rng.random(), j))
            else:
                q.append(j)
        if best is not None or nodes > cap:
            break

    out = {"seed": seed, "mode": mode, "local": local, "radius": radius, "limit": limit, "level": level, "nodes": nodes,
           "states": len(sims), "secs": round(time.time() - t0, 1)}
    if best is not None:
        seq = []
        j = best
        while par[j][0] >= 0:
            seq.append(par[j][1])
            j = par[j][0]
        seq.reverse()
        out["actions"] = len(seq)
        out["plan"] = ["L" if a[0] == "L" else "R" if a[0] == "R" else f"C{a[1][0]},{a[1][1]}"
                       for a in seq]
        _, s2 = make_level(m, level)
        kinds = []
        far = 0
        for a in seq:
            if a[0] == "C":
                kinds.append(next(iter(s2.at(*a[1])), ""))
                dy2 = -1 if s2.grav_up else 1
                near2 = {(s2.px, s2.py + dy2), (s2.px - 1, s2.py), (s2.px + 1, s2.py),
                         (s2.px - 1, s2.py + dy2), (s2.px + 1, s2.py + dy2)}
                if a[1] not in near2 and kinds[-1] != "lrpkmzabbfa":
                    far += 1
                s2.click_cell(*a[1])
            else:
                s2.move(a[0] == "R")
        out["far_clicks"] = far
        out["click_kinds"] = kinds
        out["toggle_clicks"] = sum(1 for n in kinds if n in (SOLID_TOGGLE, PASS_TOGGLE))
        out["switch_clicks"] = sum(1 for n in kinds if n == "lrpkmzabbfa")
        out["won_replay"] = s2.won
    else:
        out["actions"] = None
    print(json.dumps(out), flush=True)


def main() -> None:
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 40_000_000
    arg = sys.argv[3] if len(sys.argv) > 3 else ""
    if arg.startswith("r"):
        # seeds walk the radius: r means "crag's rule plus a Chebyshev-k neighbourhood", k from the
        # seed, so one fan measures the whole widening curve instead of one point on it.
        solve(seed, cap, force_local=True, radius=(seed - 1) // 3 + 1)
    else:
        solve(seed, cap, force_local=(arg == "local"))


if __name__ == "__main__":
    main()
