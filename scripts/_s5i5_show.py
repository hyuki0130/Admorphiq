"""s5i5 level 7 — RENDER the least-blocked winning configuration, per chain orientation.

"Illegal" is a verdict, not a finding. Every one of the 10,848 length assignments that puts the
chain's rider on the uncovered destination is refused by the engine's own overlap predicate, and
before that is written down as "this level cannot be won" the board has to be LOOKED AT: which
bar lies where, and by how many cells it misses.

One job per orientation. Each prints the winning configuration with the FEWEST overlapping cells,
as a 64x64 picture plus the boxes, so the obstruction can be read rather than inferred.
"""
from __future__ import annotations

import itertools
import json
import sys

sys.path.insert(0, "scripts")

from _s5i5_legal import cells, overlaps  # noqa: E402
from _s5i5_plan import CHAIN, dirs, turn_paths  # noqa: E402
from _s5i5_reach import MOVER, TARGET, act, alphabet, load, restore, snap  # noqa: E402


def picture(g):
    fr = g.camera._raw_render(g.current_level.get_sprites())
    chars = "0123456789ABCDEF"
    return ["".join(chars[v] if 0 <= v < 16 else "." for v in row) for row in fr]


def boxes(g):
    out = {}
    for s in g.current_level.get_sprites_by_tag("0001qwdmnlybkb"):
        out[s.name] = [s.x, s.y, s.width, s.height]
    for s in g.current_level.get_sprites_by_tag(MOVER):
        out.setdefault("riders", []).append([s.x, s.y])
    return out


def main() -> None:
    job = int(sys.argv[1])
    _mod, g = load()
    sn0 = snap(g)
    turns, reach = turn_paths(g, sn0, no_collide=True)
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
    loose = [a for a in alphabet(g) if a[0] == "turn" and a[1] not in chain_cols]
    target = [(s.x, s.y) for s in g.current_level.get_sprites_by_tag(TARGET)]
    uncovered = [t for t in target if t != (21, 6)]

    best = None
    for extra in range(4):
        restore(g, sn0)
        g.qownxibuiy = lambda: False
        g.next_level = lambda: None
        for i in prefix:
            act(g, turns[i][2], turns[i][3])
        for _ in range(extra):
            for t in loose:
                act(g, t[2], t[3])
        if dirs(g) != want:
            continue
        base_sn = snap(g)

        def rider():
            tg = set(target)
            free = [(s.x, s.y) for s in g.current_level.get_sprites_by_tag(MOVER)
                    if (s.x, s.y) not in tg]
            return free[0] if free else None

        r0 = rider()
        vecs = []
        for c in chain_cols:
            restore(g, base_sn)
            act(g, *grows[c][2:])
            r1 = rider()
            vecs.append((r1[0] - r0[0], r1[1] - r0[1]))
        restore(g, base_sn)
        lens = [max(next(x for x in g.current_level.get_sprites() if x.name == n).width,
                    next(x for x in g.current_level.get_sprites() if x.name == n).height) // 3
                for n in CHAIN]
        ranges = [range(1 - L, 25) for L in lens]
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
                pr = overlaps(g)
                win = bool(g.neurwiqfry())
                g.qownxibuiy = lambda: False
                if not win:
                    continue
                # Count the cells, not the pairs — one bar three cells into the wall is a very
                # different report from one lying across it end to end.
                bad = sum(len(cells(next(s for s in g.current_level.get_sprites_by_tag(
                    "0001qwdmnlybkb") if s.name == p["a"])) & cells(next(
                        s for s in g.current_level.get_sprites_by_tag("0001qwdmnlybkb")
                        if s.name == p["b"]))) for p in pr)
                if best is None or bad < best[0]:
                    best = (bad, extra, list(ns), pr, boxes(g), picture(g))
                if bad == 0:
                    break
            if best and best[0] == 0:
                break
        if best and best[0] == 0:
            break

    if best is None:
        print(json.dumps({"job": job, "orientation": list(want), "no_winning_lengths": True}))
        return
    bad, extra, ns, pr, bx, pic = best
    print(json.dumps({"job": job, "orientation": list(want), "extra_turns": extra,
                      "lengths_added": ns, "overlap_cells": bad, "pairs": pr, "boxes": bx,
                      "picture": pic}))


if __name__ == "__main__":
    main()
