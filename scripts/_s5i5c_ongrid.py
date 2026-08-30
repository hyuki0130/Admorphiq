"""s5i5 level 7 — is the recorded 45-click witness SOUND, and is the win reachable ON-GRID?

⛔ THE INSTRUMENT THE WITNESS WAS TAKEN WITH WALKS THROUGH CONFIGURATIONS THE ENGINE REFUSED.
`_s5i5_reach.search` does `restore(g, sn); act(g, x, y); k = key(g)` and never asks whether the
click was refused. On a refusal `S5i5.step` leaves the sprites IN the overlapping position and
parks the undo in `self.whoonmfbnp` for the NEXT step to apply — so `key`/`snap` read the illegal
board, `restore` then clears `whoonmfbnp`, and the illegal configuration becomes a first-class
search node with the undo thrown away. Every probe in `scripts/_s5i5_*.py` mentions `whoonmfbnp`
exactly once, inside `restore`, so this affects all of them.

That matters in ONE direction only, and both halves are worth stating:

  * the POSITIVE result ("an A* with collisions ON wins level 7 in 45 clicks, opening by moving a
    rider that is already home") was computed in a space LARGER than the engine's, so it may not
    be a legal win at all;
  * the NEGATIVE results ("every search with ban=[10] is EXHAUSTED") were computed in that same
    larger space, so they get STRONGER, not weaker — no win exists even with illegal intermediate
    states allowed. That conclusion stands and is not re-tested here beyond one control.

Job 9 is the instrument check, run in BOTH directions on input whose verdict is already known
(CLAUDE.md's standing rule): click a control, confirm a REFUSED click leaves the sprites moved
with `whoonmfbnp` non-empty, and confirm an ACCEPTED click leaves it empty.

The search arms then re-run the A* with a strict successor test — a refused click is not a state —
and vary the one thing that decides whether `swivel` needs knowledge it cannot have:

    HOW FAR OFF THE 64x64 GRID a driven bar may travel.

`swivel.legal` bounds it at `_MARGIN = 3` and cannot see the furniture out there (the level's frame
`0006` is 70x51 at (-3,-3): 708 solid cells, 291 of them off-grid, and a predictor built from the
visible border is 51% wrong). If a legal win exists at margin 0, the tool never needs that
knowledge and the fix is a search change. If it needs the margin, the fix needs geometry.

Arms (`bash scripts/pfan.sh s5i5cgrid scripts/_s5i5c_ongrid.py 9 "" 8`):

    1  LOOSE (the old instrument), unbounded, nothing banned   <- positive control: must find ~45
    2  strict, unbounded
    3  strict, margin 0        <- the question
    4  strict, margin 3        <- swivel's own bound
    5  strict, unbounded, ban c10                              <- negative control: must NOT find
    6  strict, unbounded, length cap 24
    7  strict, unbounded, Manhattan heuristic
    8  strict, margin 1
    9  instrument check

Every arm prints the plan it found, and for each step of it the largest off-grid excursion of any
driven bar, so "does the win leave the grid" is read off the witness rather than inferred.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from heapq import heappop, heappush

sys.path.insert(0, "scripts")

from _s5i5_reach import (  # noqa: E402
    ARM,
    MOD,
    act,
    alphabet,
    gap,
    key,
    load,
    maze_field,
    maze_gap,
    movable,
    restore,
    snap,
)

ARMS = {
    1: dict(strict=False, margin=None, ban=(), cap=20, hmode=1, w=4),
    2: dict(strict=True, margin=None, ban=(), cap=20, hmode=1, w=4),
    3: dict(strict=True, margin=0, ban=(), cap=20, hmode=1, w=4),
    4: dict(strict=True, margin=3, ban=(), cap=20, hmode=1, w=4),
    5: dict(strict=True, margin=None, ban=(10,), cap=20, hmode=1, w=4),
    6: dict(strict=True, margin=None, ban=(), cap=24, hmode=1, w=4),
    7: dict(strict=True, margin=None, ban=(), cap=20, hmode=0, w=4),
    8: dict(strict=True, margin=1, ban=(), cap=20, hmode=1, w=4),
}


def driven_names(g, alpha):
    """The bars any control drives — the wall is an arm too and must not be length-capped."""
    used = {a[1] for a in alpha}
    out = set()
    for s in g.current_level.get_sprites_by_tag(ARM):
        if int(s.pixels[1, 1]) in used:
            out.add(s.name)
    return out


def offgrid(g, names):
    """The largest number of cells any driven bar reaches beyond the 64x64 grid, per side."""
    worst = 0
    for s in g.current_level.get_sprites():
        if s.name not in names:
            continue
        worst = max(worst, -s.x, -s.y, s.x + s.width - 64, s.y + s.height - 64)
    return max(0, worst)


def instrument():
    """Both directions, on clicks whose verdict is already known from the engine itself."""
    _mod, g = load()
    alpha = alphabet(g)
    sn = snap(g)
    out = []
    for kind, colour, x, y in alpha:
        restore(g, sn)
        before = [(s.name, s.x, s.y) for s in movable(g)]
        act(g, x, y)
        after = [(s.name, s.x, s.y) for s in movable(g)]
        out.append({"kind": kind, "colour": colour,
                    "refused": bool(g.whoonmfbnp),
                    "moved": before != after})
    restore(g, sn)
    both = {"refused_and_moved": sum(1 for r in out if r["refused"] and r["moved"]),
            "refused_not_moved": sum(1 for r in out if r["refused"] and not r["moved"]),
            "accepted_and_moved": sum(1 for r in out if not r["refused"] and r["moved"]),
            "accepted_not_moved": sum(1 for r in out if not r["refused"] and not r["moved"])}
    print(json.dumps({"job": 9, "instrument": out, "summary": both,
                      "md5": hashlib.md5(open(MOD, "rb").read()).hexdigest()}))


def search(arm, deadline):
    strict, margin, ban = arm["strict"], arm["margin"], tuple(arm["ban"])
    cap, hmode, weight = arm["cap"], arm["hmode"], arm["w"]
    _mod, g = load()
    alpha = [a for a in alphabet(g) if a[1] not in ban]
    names = driven_names(g, alpha)
    field = maze_field(g)
    h = (lambda: maze_gap(g, field)) if hmode else (lambda: gap(g))
    start = g.level_index
    sn0 = snap(g)
    seen = {key(g)}
    heap = [(weight * h(), 0, 0, sn0, ())]
    tick = opened = refused = clipped = 0
    best = h()
    while heap:
        if time.time() > deadline:
            return {"found": False, "opened": opened, "best_gap": best, "reason": "cap",
                    "refused_skipped": refused, "margin_skipped": clipped}
        _f, _g0, _t, sn, path = heappop(heap)
        for ai, (_kind, _colour, x, y) in enumerate(alpha):
            restore(g, sn)
            act(g, x, y)
            opened += 1
            tick += 1
            if tick % 5000 == 0:
                print(f"# opened={opened} best={best} heap={len(heap)} d={len(path)}",
                      file=sys.stderr, flush=True)
            if strict and g.whoonmfbnp:
                # ⛔ THE ENGINE REFUSED THIS CLICK. The sprites are sitting in the overlapping
                # position with the undo parked; it is not a board the player can ever be on.
                refused += 1
                continue
            if g.level_index > start:
                return {"found": True, "plan_len": len(path) + 1,
                        "plan": [list(alpha[i]) for i in path] + [list(alpha[ai])],
                        "opened": opened, "refused_skipped": refused,
                        "margin_skipped": clipped}
            k = key(g)
            if k in seen:
                continue
            if any(max(s.width, s.height) > cap * 3 for s in movable(g) if s.name in names):
                continue
            if margin is not None and offgrid(g, names) > margin:
                clipped += 1
                continue
            seen.add(k)
            gg = h()
            best = min(best, gg)
            heappush(heap, (len(path) + 1 + weight * gg, gg, len(seen), snap(g), path + (ai,)))
    return {"found": False, "opened": opened, "best_gap": best, "reason": "exhausted",
            "refused_skipped": refused, "margin_skipped": clipped}


def replay(plan):
    """Walk the found plan and report, per step, the off-grid reach and whether it was refused."""
    _mod, g = load()
    alpha = alphabet(g)
    names = driven_names(g, alpha)
    steps = []
    for _kind, _colour, x, y in plan:
        act(g, x, y)
        steps.append({"refused": bool(g.whoonmfbnp), "offgrid": offgrid(g, names),
                      "gap": gap(g), "lvl": g.level_index})
        g.gwiuiwqizb.current_steps = 10 ** 9
    return {"steps": steps, "max_offgrid": max(s["offgrid"] for s in steps),
            "refused_in_replay": sum(1 for s in steps if s["refused"]),
            "ended_level": g.level_index}


def main() -> None:
    job = int(sys.argv[1])
    budget = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2] else 1500
    if job == 9:
        return instrument()
    arm = ARMS[job]
    t0 = time.time()
    r = search(arm, time.time() + budget)
    out = {"job": job, **{k: (list(v) if isinstance(v, tuple) else v) for k, v in arm.items()},
           **r, "wall_s": round(time.time() - t0, 1),
           "md5": hashlib.md5(open(MOD, "rb").read()).hexdigest()}
    if r.get("found"):
        out["replay"] = replay(r["plan"])
    print(json.dumps(out))


if __name__ == "__main__":
    main()
