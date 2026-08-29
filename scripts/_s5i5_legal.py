"""s5i5 level 7 — PROVE the legality instrument, then name what actually blocks the win.

⛔ 10,848 length assignments put the chain's rider exactly on the uncovered destination, the
engine's OWN win predicate fired on every one of them, and the engine's OWN overlap predicate
called every one illegal. A verdict that uniform is either the board's answer or a broken
instrument, and the difference has to be measured before either is written down (rule 7g).

  job 1  the instrument: is the UNTOUCHED level legal, and is it still legal after a click the
         engine visibly accepted? If the start reads illegal the predicate is not measuring what
         the name says and every conclusion drawn from it is void.
  job 2+ take one winning configuration per chain orientation and NAME the overlapping pair —
         which two bars, and over which cells. "Illegal" is not a finding; "this bar lies across
         the wall between x and y" is.
"""
from __future__ import annotations

import itertools
import json
import sys

sys.path.insert(0, "scripts")

from _s5i5_plan import CHAIN, dirs, turn_paths  # noqa: E402
from _s5i5_reach import MOVER, TARGET, act, alphabet, key, load, restore, snap  # noqa: E402

ARM_TAG = "0001qwdmnlybkb"


def cells(s):
    px = s.pixels
    return {(s.x + i, s.y + j) for j in range(px.shape[0]) for i in range(px.shape[1])
            if px[j, i] >= 0}


def overlaps(g):
    arms = g.current_level.get_sprites_by_tag(ARM_TAG)
    out = []
    for a, b in itertools.combinations(arms, 2):
        if a.collides_with(b):
            common = cells(a) & cells(b)
            out.append({"a": a.name, "b": b.name, "n_cells": len(common),
                        "sample": sorted(common)[:6]})
    return out


def main() -> None:
    job = int(sys.argv[1])
    _mod, g = load()
    sn0 = snap(g)

    if job == 1:
        base = key(g)
        rec = {"job": 1, "start_overlap_predicate": bool(g.qownxibuiy()),
               "start_overlapping_pairs": overlaps(g)}
        moved = None
        for kind, colour, x, y in alphabet(g):
            restore(g, sn0)
            act(g, x, y)
            if key(g) != base:
                moved = {"click": [kind, colour, x, y],
                         "overlap_predicate_after": bool(g.qownxibuiy()),
                         "overlapping_pairs_after": overlaps(g)}
                break
        rec["after_an_accepted_click"] = moved
        restore(g, sn0)
        print(json.dumps(rec))
        return

    turns, reach = turn_paths(g, sn0, no_collide=True)
    g.qownxibuiy = type(g).qownxibuiy.__get__(g)
    orients = sorted(reach)
    if job - 1 > len(orients):
        print(json.dumps({"job": job, "skip": len(orients)}))
        return
    want = orients[job - 2]
    prefix = reach[want]

    chain_cols = [int(next(x for x in g.current_level.get_sprites() if x.name == n).pixels[1, 1])
                  for n in CHAIN]
    grows = {a[1]: a for a in alphabet(g) if a[0] == "grow"}
    shrinks = {a[1]: a for a in alphabet(g) if a[0] == "shrink"}
    target = [(s.x, s.y) for s in g.current_level.get_sprites_by_tag(TARGET)]
    uncovered = [t for t in target if t != (21, 6)]

    restore(g, sn0)
    g.qownxibuiy = lambda: False
    g.next_level = lambda: None
    for i in prefix:
        act(g, turns[i][2], turns[i][3])
    if dirs(g) != want:
        print(json.dumps({"job": job, "error": "orientation drifted", "got": list(dirs(g))}))
        return
    base_sn = snap(g)

    def rider():
        tg = {t for t in target}
        free = [(s.x, s.y) for s in g.current_level.get_sprites_by_tag(MOVER) if (s.x, s.y) not in tg]
        return free[0] if free else None

    r0 = rider()
    vecs = []
    for c in chain_cols:
        restore(g, base_sn)
        act(g, *grows[c][2:])
        r1 = rider()
        vecs.append((r1[0] - r0[0], r1[1] - r0[1]))
    restore(g, base_sn)
    lens = []
    for n in CHAIN:
        sp = next(x for x in g.current_level.get_sprites() if x.name == n)
        lens.append(max(sp.width, sp.height) // 3)
    ranges = [range(1 - L, 25) for L in lens]

    reasons: dict = {}
    examples = []
    n_checked = 0
    for gx, gy in uncovered:
        need = (gx - r0[0], gy - r0[1])
        for ns in itertools.product(*ranges):
            if (sum(n * v[0] for n, v in zip(ns, vecs)),
                    sum(n * v[1] for n, v in zip(ns, vecs))) != need:
                continue
            restore(g, base_sn)
            for c, n in zip(chain_cols, ns):
                for _ in range(abs(n)):
                    act(g, *(grows[c][2:] if n > 0 else shrinks[c][2:]))
            g.qownxibuiy = type(g).qownxibuiy.__get__(g)
            pairs = overlaps(g)
            win = bool(g.neurwiqfry())
            g.qownxibuiy = lambda: False
            n_checked += 1
            tag = "|".join(sorted({f"{p['a']}~{p['b']}" for p in pairs})) or "NONE"
            reasons[tag] = reasons.get(tag, 0) + 1
            if not pairs and win:
                examples.append({"lengths_added": list(ns), "WIN_AND_LEGAL": True})
            elif len(examples) < 2:
                examples.append({"lengths_added": list(ns), "win": win, "pairs": pairs})
    print(json.dumps({"job": job, "orientation": list(want), "checked": n_checked,
                      "blocking_pairs": reasons, "examples": examples[:3],
                      "unit_vectors": [list(v) for v in vecs], "lengths": lens}))


if __name__ == "__main__":
    main()
