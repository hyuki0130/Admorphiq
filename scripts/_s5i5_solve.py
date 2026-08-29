"""s5i5 level 7 — SOLVE the lengths instead of searching them, then ask the engine if it is legal.

⛔ A* over the click alphabet answered the wrong question for eleven fan-outs. With the furniture
switched off the tip of a jointed chain is an AFFINE function of the bar lengths: one click on a
length control displaces the tip by a fixed vector, so the tip is `start + sum(n_i * v_i)` and the
lengths that put a rider on a destination are a linear solve, not a search. Measure the four
vectors with four clicks, solve, BUILD the configuration, then switch the furniture back on and ask
the engine two separate questions:

    qownxibuiy()   is this configuration legal at all — does anything overlap?
    neurwiqfry()   is it a win — is every destination covered?

That separates "no winning configuration exists" from "one exists and the search cannot reach it",
which every previous run conflated. One job per reachable chain orientation; the unattached bar
that sits across one approach is tried at all four of its own turns.
"""
from __future__ import annotations

import itertools
import json
import sys

sys.path.insert(0, "scripts")

from _s5i5_plan import CHAIN, dirs, turn_paths  # noqa: E402
from _s5i5_reach import MOVER, TARGET, act, alphabet, load, restore, snap  # noqa: E402


def rider_of_chain(g):
    """The rider carried by the chain — the one whose x,y is not a destination at level start."""
    tg = {(s.x, s.y) for s in g.current_level.get_sprites_by_tag(TARGET)}
    free = [(s.x, s.y) for s in g.current_level.get_sprites_by_tag(MOVER) if (s.x, s.y) not in tg]
    return free[0] if free else None


def main() -> None:
    job = int(sys.argv[1])
    free_turns = len(sys.argv) > 2 and sys.argv[2] == "all"
    _mod, g = load()
    sn0 = snap(g)
    turns, reach = turn_paths(g, sn0, no_collide=free_turns)
    if free_turns:
        g.qownxibuiy = type(g).qownxibuiy.__get__(g)
    orients = sorted(reach)
    if job > len(orients):
        print(json.dumps({"job": job, "skip": len(orients)}))
        return
    want = orients[job - 1]
    prefix = reach[want]

    chain_cols = [int(next(x for x in g.current_level.get_sprites() if x.name == n).pixels[1, 1])
                  for n in CHAIN]
    grows = {a[1]: a for a in alphabet(g) if a[0] == "grow"}
    shrinks = {a[1]: a for a in alphabet(g) if a[0] == "shrink"}
    loose_turns = [a for a in alphabet(g) if a[0] == "turn" and a[1] not in chain_cols]
    target = [(s.x, s.y) for s in g.current_level.get_sprites_by_tag(TARGET)]

    def stage(extra_turns: int):
        restore(g, sn0)
        if free_turns:
            g.qownxibuiy = lambda: False
        for i in prefix:
            act(g, turns[i][2], turns[i][3])
        if free_turns:
            g.qownxibuiy = type(g).qownxibuiy.__get__(g)
        for _ in range(extra_turns):
            for t in loose_turns:
                act(g, t[2], t[3])
        return dirs(g)

    print(f"# job {job} orient {want}", file=sys.stderr, flush=True)
    out = {"job": job, "orientation": list(want), "turn_prefix": len(prefix), "results": []}
    for extra in range(4):
        got = stage(extra)
        if got != want:
            out["results"].append({"extra_turns": extra, "error": "orientation drifted",
                                   "got": list(got)})
            continue
        g.qownxibuiy = lambda: False           # furniture off while the vectors are measured
        g.next_level = lambda: None            # a win mid-solve must not swap the level away
        base_sn = snap(g)
        r0 = rider_of_chain(g)
        vecs = []
        for c in chain_cols:
            restore(g, base_sn)
            act(g, *grows[c][2:])
            r1 = rider_of_chain(g)
            vecs.append((r1[0] - r0[0], r1[1] - r0[1]))
        restore(g, base_sn)
        # Which destination the chain's rider must take is not assumed: try every one.
        # ⛔ SHRINKING IS A MOVE TOO. The first version of this solve searched only n_i >= 0 and
        # reported "no solution" for 24 of 26 orientations — a statement about the search, not
        # about the board. Each bar may go down to one unit and up to a length the grid can hold.
        lens = []
        for n in CHAIN:
            sp = next(x for x in g.current_level.get_sprites() if x.name == n)
            lens.append(max(sp.width, sp.height) // 3)
        ranges = [range(1 - L, 25) for L in lens]
        uncovered = [t for t in target if t != (21, 6)]
        sols = []
        for gx, gy in uncovered:
            need = (gx - r0[0], gy - r0[1])
            for ns in itertools.product(*ranges):
                dx = sum(n * v[0] for n, v in zip(ns, vecs))
                dy = sum(n * v[1] for n, v in zip(ns, vecs))
                if (dx, dy) == need:
                    sols.append(((gx, gy), ns))
                    if len(sols) >= 4000:
                        break
            if len(sols) >= 4000:
                break
        checked = []
        for goal_cell, ns in sols:
            restore(g, base_sn)
            for c, n in zip(chain_cols, ns):
                for _ in range(abs(n)):
                    act(g, *(grows[c][2:] if n > 0 else shrinks[c][2:]))
            rid = rider_of_chain(g)
            movers = {(s.x, s.y) for s in g.current_level.get_sprites_by_tag(MOVER)}
            g.qownxibuiy = type(g).qownxibuiy.__get__(g)   # furniture back on
            legal = not g.qownxibuiy()
            win = g.neurwiqfry()
            g.qownxibuiy = lambda: False
            checked.append({"goal": list(goal_cell), "lengths_added": list(ns),
                            "rider_lands": list(rid) if rid else None,
                            "all_movers": sorted(map(list, movers)),
                            "legal_no_overlap": bool(legal), "engine_says_win": bool(win)})
        wins = [c for c in checked if c["engine_says_win"] and c["legal_no_overlap"]]
        out["results"].append({"extra_turns": extra, "start_rider": list(r0),
                               "unit_vectors": [list(v) for v in vecs], "lengths": lens,
                               "n_solutions": len(sols), "n_legal_wins": len(wins),
                               "wins": wins[:3],
                               # Instrument proof: the solve claims these lengths put the rider on
                               # the destination, so the ENGINE must agree it landed there, and the
                               # win predicate must fire whenever it did. A run where the rider
                               # lands but the predicate never fires is a broken probe, not a
                               # verdict about the board.
                               "n_win_predicate": sum(1 for c in checked if c["engine_says_win"]),
                               "n_landed": sum(1 for c in checked if c["rider_lands"] is None),
                               "n_illegal": sum(1 for c in checked if not c["legal_no_overlap"]),
                               "solutions": checked[:2]})
        g.qownxibuiy = type(g).qownxibuiy.__get__(g)
    print(json.dumps(out))


if __name__ == "__main__":
    main()
