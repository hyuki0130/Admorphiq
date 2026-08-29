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


def solve(seed: int, cap: int, level: int = 6):
    """mode 0 = plain BFS in the engine's 64-action allowance (finds the SHORTEST win);
    mode 1 = greedy best-first on distance to the gem (finds A win fast, not the shortest);
    mode 2 = BFS with the allowance lifted to 200, which answers "winnable at all?" separately
    from "winnable inside the budget" — two different claims that must not be conflated."""
    mode = (seed - 1) % 3
    limit = 200 if mode == 2 else BUDGET
    m = load_module()
    _, start = make_level(m, level)
    rng = random.Random(seed)
    t0 = time.time()
    seen = {(start.key(), start.cam_y)}
    gx0, gy0 = GEM_XY.get(level, (2, 31))
    q = deque([(start, [])])
    heap = [(abs(start.px - gx0) + abs(start.py - gy0), 0, start, [])]
    best = None
    nodes = 0
    tick = 0
    while q or heap:
        if mode == 1:
            if not heap:
                break
            _, _, s, path = heapq.heappop(heap)
        else:
            if not q:
                break
            s, path = q.popleft()
        tick += 1
        if tick % 20000 == 0:
            print(f"# seed={seed} mode={mode} nodes={nodes} states={len(seen)} "
                  f"depth={len(path)} secs={round(time.time()-t0,1)}", file=sys.stderr, flush=True)
        if len(path) >= limit - 1:
            continue
        opts = [("L",), ("R",)] + [("C", c) for c in s.clickables()]
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
            p = path + [a]
            if nxt.won:
                best = p
                q.clear()
                break
            k = (nxt.key(), nxt.cam_y)
            if k in seen:
                continue
            seen.add(k)
            if mode == 1:
                heapq.heappush(heap, (abs(nxt.px - gx0) + abs(nxt.py - gy0) + len(p) // 8,
                                      rng.random(), nxt, p))
            else:
                q.append((nxt, p))
        if best or nodes > cap:
            break
    out = {"seed": seed, "mode": mode, "limit": limit, "level": level, "nodes": nodes,
           "states": len(seen), "secs": round(time.time() - t0, 1)}
    if best:
        toggles = sum(1 for a in best if a[0] == "C"
                      and next(iter(make_level(m, level)[1].at(*a[1])), "") in ())
        out["actions"] = len(best)
        out["plan"] = ["L" if a[0] == "L" else "R" if a[0] == "R" else f"C{a[1][0]},{a[1][1]}"
                       for a in best]
        # replay to label which clicks hit a toggle tile at the moment they are made
        _, s = make_level(m, level)
        kinds = []
        for a in best:
            if a[0] == "C":
                n = next(iter(s.at(*a[1])), "")
                kinds.append(n)
                s.click_cell(*a[1])
            else:
                s.move(a[0] == "R")
        out["click_kinds"] = kinds
        out["toggle_clicks"] = sum(1 for n in kinds if n in (SOLID_TOGGLE, PASS_TOGGLE))
        out["won_replay"] = s.won
        del toggles
    else:
        out["actions"] = None
    print(json.dumps(out), flush=True)


def main() -> None:
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 40_000_000
    solve(seed, cap)


if __name__ == "__main__":
    main()
