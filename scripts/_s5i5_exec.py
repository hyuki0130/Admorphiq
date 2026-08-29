"""s5i5 level 7 — find a legal ORDER for the winning configuration, then play it and check.

MEASURED by `scripts/_s5i5_show.py` job 25: the level HAS a legal winning configuration, and it is
the four-segment snake the maze forces —

    0059  (48,12) 3x27   down the right chamber
    0060  ( 9,39) 42x3   left along the one floor lane the pillar leaves clear (rows 39-41)
    0061  ( 6,18) 3x24   up through the three-cell gap at x=6..8
    0062  ( 6,15) 21x3   right to the destination, its rider landing on (24,15)

with the loose bar turned TWICE so it stands above the grid at (12,-6) instead of lying across the
last segment. Zero overlapping cells, both riders home, and the engine's own win predicate fires.

⛔ A CONFIGURATION IS NOT A PLAN. Every click is tested by the engine and UNDONE if it overlaps, so
the order matters and the target lengths say nothing about it. This searches the order — which bar
to lengthen next, and when to turn the loose one — with the real engine deciding every step, and
then REPLAYS the winning sequence from a fresh level and reports the level number, not a boolean
(rule 7f).
"""
from __future__ import annotations

import json
import sys
from collections import deque

sys.path.insert(0, "scripts")

from _s5i5_plan import CHAIN, dirs, turn_paths  # noqa: E402
from _s5i5_reach import act, alphabet, load, restore, snap  # noqa: E402

WANT = (180, 270, 0, 90)
ADD = (8, 12, 6, 6)


def bar_units(g, name):
    s = next(x for x in g.current_level.get_sprites() if x.name == name)
    return max(s.width, s.height) // 3


def main() -> None:
    job = int(sys.argv[1])
    extra_c8 = job % 4                     # where the loose bar is turned to
    order_seed = job // 4                  # which tie-break the order search uses
    _mod, g = load()
    start_level = g.level_index
    sn0 = snap(g)
    turns, reach = turn_paths(g, sn0, no_collide=True)
    g.qownxibuiy = type(g).qownxibuiy.__get__(g)
    if WANT not in reach:
        print(json.dumps({"job": job, "error": "orientation unreachable"}))
        return
    prefix = reach[WANT]

    chain_cols = [int(next(x for x in g.current_level.get_sprites() if x.name == n).pixels[1, 1])
                  for n in CHAIN]
    grows = {a[1]: a for a in alphabet(g) if a[0] == "grow"}
    loose = [a for a in alphabet(g) if a[0] == "turn" and a[1] not in chain_cols]

    plan_head = [list(turns[i]) for i in prefix]
    for _ in range(extra_c8):
        plan_head += [list(t) for t in loose]

    restore(g, sn0)
    for step in plan_head:
        act(g, step[2], step[3])
    if dirs(g) != WANT:
        print(json.dumps({"job": job, "error": "orientation drifted", "got": list(dirs(g))}))
        return
    base = snap(g)
    print(f"# job {job} staged, head {len(plan_head)} clicks", file=sys.stderr, flush=True)

    # ⛔ A MONOTONE BUILD IS NOT THE SEARCH. Growing each bar toward its final length and never
    # shortening anything stalls at (8, 8, 1, 6) of the (8, 12, 6, 6) needed, in all twelve
    # orderings — the second segment has to pass a place the third is occupying, so some bar must
    # go BACKWARDS on the way. The state is therefore the four LENGTHS, bounded generously around
    # the target, and shrinks are moves like any other.
    shrinks = {a[1]: a for a in alphabet(g) if a[0] == "shrink"}
    goal_len = [bar_units(g, n) + a for n, a in zip(CHAIN, ADD)]
    hi = [gl + 4 + order_seed for gl in goal_len]
    steps = []
    for i in range(4):
        steps.append(("g", i, grows[chain_cols[i]]))
        steps.append(("s", i, shrinks[chain_cols[i]]))
    for t in loose:
        steps.append(("t", -1, t))

    def state():
        return tuple(bar_units(g, n) for n in CHAIN) + (
            g.gnpdxxlhrp(next(x for x in g.current_level.get_sprites()
                              if x.name == "0008iqvkanhnxj")),)

    seen = {state()}
    q = deque([(state(), (), base)])
    found = None
    seen_n = 0
    while q and found is None:
        _st, path, sn = q.popleft()
        seen_n += 1
        if seen_n % 2000 == 0:
            print(f"# order search {seen_n} states, depth {len(path)}", file=sys.stderr, flush=True)
        for si, (_kind, i, mv) in enumerate(steps):
            restore(g, sn)
            act(g, mv[2], mv[3])
            if g.level_index > start_level:
                found = path + (si,)
                break
            ns = state()
            if ns in seen or (i >= 0 and (ns[i] > hi[i] or ns[i] < 1)):
                continue
            seen.add(ns)
            q.append((ns, path + (si,), snap(g)))
    if found is None:
        print(json.dumps({"job": job, "CLEARED": False, "states": seen_n,
                          "n_states": len(seen), "bounds": hi, "goal_lengths": goal_len,
                          "reached_goal_lengths": any(s[:4] == tuple(goal_len) for s in seen)}))
        return

    plan = plan_head + [list(steps[si][2]) for si in found]
    # REPLAY from a clean level 7 — the search ran on a restored board, and a plan that only works
    # against the search's own bookkeeping is not a plan.
    _mod2, g2 = load()
    lvl_before = g2.level_index
    for kind, colour, x, y in plan:
        act(g2, x, y)
    lvl_after = g2.level_index
    print(json.dumps({"job": job, "CLEARED": lvl_after > lvl_before,
                      "level_before": lvl_before, "level_after": lvl_after,
                      "actions": len(plan), "declared_budget":
                          g2._clean_levels[6].get_data("StepCounter"),
                      "plan": plan}))


if __name__ == "__main__":
    main()
