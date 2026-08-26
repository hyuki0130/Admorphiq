"""Does the STATIC notch shortlist name the same targets as the spill-grounded one?

Purpose: R98 open item 3 asks for "a shortlist that can name targets from static structure
and not only from satisfaction". `sink_candidates()` needs `self._animations`, so it cannot
run before the first commit. `_mouths()` needs only a shape. This measures whether the two
agree on the boards R98 already captured, where `sinks` is the grounded answer.

Expected feedback: agreement means the static shortlist is a drop-in for the pre-spill case
and item 3 closes. Disagreement, in either direction, is the specific gap to fix — a static
set that MISSES a real target is unusable, one that ADDS regions is a shortlist and may be
fine, since the schema calls it "a shortlist, never a decision".

⛔ RUN IT ON REST-STATE BOARDS. On R98's `walk_idx*` captures this reports 12/20, and that
number measures THIS SCRIPT's blind spot rather than the shortlist's coverage: on idx0/idx1/idx2
the grounded target cells carry the BACKGROUND colour in the capture (idx0 target 0 is {12: 5}
with background 12), and `notch_regions` excludes the background, so they cannot be found at
all. idx3's targets wear colour 11 and are found 3/3 on all four of its boards. The walk
captures are taken around a spill, when a target is not wearing its own appearance; the
comparison needs boards captured at REST, before any commit. Until then this script is
written and unvalidated, not a result.
"""

from __future__ import annotations

import glob
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))


def notch_regions(colours: dict[str, int], size: int) -> list[frozenset[tuple[int, int]]]:
    """Every 4-connected same-colour region holding a notch, background excluded."""
    cells = {(int(k.split(",")[0]), int(k.split(",")[1])): v for k, v in colours.items()}
    bg = max({c: list(cells.values()).count(c) for c in set(cells.values())}.items(),
             key=lambda kv: kv[1])[0]
    out: list[frozenset[tuple[int, int]]] = []
    for colour in set(cells.values()) - {bg}:
        todo = {c for c, v in cells.items() if v == colour}
        while todo:
            seed = todo.pop()
            comp, stack = {seed}, [seed]
            while stack:
                r, c = stack.pop()
                for n in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
                    if n in todo:
                        todo.remove(n)
                        comp.add(n)
                        stack.append(n)
            held = comp
            notched = any(
                (r, c) not in held and (r, c - 1) in held and (r, c + 1) in held
                for r in {y for y, _ in held}
                for c in range(min(x for y, x in held if y == r),
                               max(x for y, x in held if y == r) + 1)
            )
            if notched:
                out.append(frozenset(held))
    return out


def main() -> int:
    here = os.path.dirname(__file__)
    rows = []
    for path in sorted(glob.glob(os.path.join(here, "evidence", "walk_idx*.json"))):
        d = json.load(open(path))
        if not d.get("sinks"):
            continue
        # The grounded answer comes from the WALK capture (taken around a commit); the
        # colours must come from the REST capture of the same level, because in the walk
        # capture a target is not wearing its own appearance.
        level = os.path.basename(path).split("_idx")[1].split("_")[0]
        rest = os.path.join(here, "evidence", f"rest_idx{level}.json")
        if not os.path.exists(rest):
            print(f"{os.path.basename(path):20s} no rest capture for idx{level} — SKIPPED")
            continue
        r = json.load(open(rest))
        grounded = [frozenset(map(tuple, s)) for s in d["sinks"]]
        static = notch_regions(r["colours"], r["size"])
        # a grounded target is COVERED when some static region contains all its cells
        covered = sum(1 for g in grounded if any(g <= s for s in static))
        rows.append((os.path.basename(path), len(grounded), len(static), covered))
        print(f"{os.path.basename(path):20s} grounded {len(grounded)}  static {len(static)}  "
              f"grounded-covered-by-static {covered}/{len(grounded)}")
    if rows:
        g = sum(r[1] for r in rows)
        c = sum(r[3] for r in rows)
        print(f"\nover {len(rows)} captured boards: {c}/{g} grounded targets are named statically")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
