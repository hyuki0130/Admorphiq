"""Offline exhaustive solver for lf52 level 6 — the model the live clear was planned from.

⛔ Rule 2: this lived in `/tmp` while it produced the line that cleared the level, which is exactly
how a measurement stops existing. It is here so the line can be REGENERATED rather than trusted.

The rules are `equnaohchtj`, read out of `environment_files/lf52/271a04aa/lf52.py`, and each one was
checked against a live frame before the search was believed (rule 7g — the source says what is
POSSIBLE, only a run says what HAPPENS):

  * `qikmikecdf` — a jump is legal when the MIDPOINT holds a `fozwvlovdui*` or a `dgxfozncuiz` and
    the LANDING is bare floor or a cart. MEASURED: the two pads this predicts can move are exactly
    the two that lit a selection marker, and the two it says cannot lit nothing at all.
  * `cfilhtifcb` — the midpoint is removed only when its name EQUALS the jumper's, so green over red
    captures nothing. MEASURED: the green count stayed at 36 through that jump.
  * `tmhxwcojkh` — a cart moves only into a `kraubslpehi` and drags whatever shares its cell; a pad
    named exactly `fozwvlovdui` riding one scrolls the camera by `-dx*6`. MEASURED: ACTION1/2/3
    leave the frame byte-identical while ACTION4 changes it three times and then stops, which is the
    carts leaving the ten-cell window rather than the carts stopping.

Level 6 in one paragraph: 28 cells wide against a screen that shows about ten, 7 green pads, ONE RED
pad (which counts toward the win because `ndtvadsrqf` matches by prefix), 3 `dgxfozncuiz` stepping
stones and 3 carts. The win is the pad count reaching 2, so it needs SIX captures.

Plain python, no engine. Prints the winning line as JSON; `scripts/_lf52_l6_play.py` replays it.

    uv run python scripts/_lf52_l6_model.py > scripts/_lf52_l6_line.json

Expected feedback: `win: true` with a move count means level 6 is solvable under the camera, and the
line is directly playable. `win: false` with `capped: true` means the search ran out of states and
proves nothing either way.
"""
from __future__ import annotations

import json
from collections import deque

ROWS = [
    "",
    " ....         ....   ",
    " .r..         .x.........>. ",
    " .x..         p..p     p |x",
    " ....         |  |    .?.|.",
    " ......       |  |    x| |",
    " ......,,-----t--3  ...L-3",
    " x.....             x",
    "   x                .",
]
MAP = {
    "x": ["fozwvlovdui", "hupkpseyuim"],
    "o": ["jmbixtieild", "hupkpseyuim"],
    ".": ["hupkpseyuim"],
    ",": ["hupkpseyuim2", "kraubslpehi"],
    "p": ["dgxfozncuiz", "hupkpseyuim"],
    "r": ["fozwvlovdui_red", "hupkpseyuim"],
    "?": ["hupkpseyuim2", "kraubslpehi-up"],
    "P": ["dgxfozncuiz", "hupkpseyuim2", "kraubslpehi"],
    "-": ["kraubslpehi"],
    "|": ["kraubslpehi-up"],
    "L": ["kraubslpehi-L"],
    "3": ["kraubslpehi-3"],
    "<": ["kraubslpehi-<"],
    ">": ["kraubslpehi->"],
    "T": ["kraubslpehi-T"],
    "t": ["kraubslpehi-t"],
}
DIRS = [(0, -1), (1, 0), (0, 1), (-1, 0)]
OX0 = 5                     # the grid's pixel offset at level 6's start
CELL = 6

STATIC: dict[tuple[int, int], list[str]] = {}
PADS0: dict[tuple[int, int], str] = {}
_carts: list[tuple[int, int]] = []
for _y, _row in enumerate(ROWS):
    for _x, _ch in enumerate(_row):
        if _ch == " ":
            continue
        _rest = []
        for _n in MAP[_ch]:
            if _n == "hupkpseyuim2":
                _carts.append((_x, _y))
            elif _n.startswith("fozwvlovdui"):
                PADS0[(_x, _y)] = _n
            else:
                _rest.append(_n)
        STATIC[(_x, _y)] = _rest
CARTS0 = tuple(sorted(_carts))


def names_at(cell, pads, carts) -> list[str]:
    out = list(STATIC.get(cell, []))
    if cell in pads:
        out.append(pads[cell])
    if cell in carts:
        out.append("hupkpseyuim2")
    return out


def jump_legal(pads, carts, cell, d):
    """`qikmikecdf`: something jumpable in the middle, somewhere landable beyond."""
    mid = (cell[0] + d[0], cell[1] + d[1])
    land = (mid[0] + d[0], mid[1] + d[1])
    mn = names_at(mid, pads, carts)
    if not any(k in n for n in mn for k in ("fozwvlovdui", "dgxfozncuiz")):
        return None
    ln = names_at(land, pads, carts)
    ok = (len(ln) == 1 and "hupkpseyuim" in ln[0]) or (len(ln) == 2 and "hupkpseyuim2" in ln)
    return (mid, land) if ok else None


def onscreen(cell, ox) -> bool:
    x = cell[0] * CELL + ox
    return 0 <= x and x + CELL - 1 <= 63


def successors(state):
    pads = dict(state[0])
    carts = set(state[1])
    ox = state[2]
    out = []
    for cell, nm in list(pads.items()):
        if not onscreen(cell, ox):
            continue                                  # off screen is unclickable
        for d in DIRS:
            r = jump_legal(pads, carts, cell, d)
            if r is None:
                continue
            mid, land = r
            if not onscreen(land, ox):
                continue
            nxt = dict(pads)
            del nxt[cell]
            if nxt.get(mid) == nm:                    # same NAME or no capture at all
                del nxt[mid]
            nxt[land] = nm
            nox = ox
            if land == (7, 6) and ox == 5:
                nox = ox - 20
            elif land == (18, 2) and ox == -57:
                nox = ox - 44
            out.append(((tuple(sorted(nxt.items())), tuple(sorted(carts)), nox),
                        ("jump", cell, d)))
    for d in DIRS:
        dx, dy = d
        order = (sorted(carts, key=lambda c: c[0], reverse=dx > 0) if dx
                 else sorted(carts, key=lambda c: c[1], reverse=dy > 0))
        nxt = dict(pads)
        nc = set(carts)
        moved = False
        nox = ox
        scrolled = False
        for c in order:
            nb = (c[0] + dx, c[1] + dy)
            nn = names_at(nb, nxt, nc)
            if "hupkpseyuim2" in nn:
                continue
            if not any("kraubslpehi" in n for n in nn):
                continue
            rider = nxt.get(c)
            nc.discard(c)
            nc.add(nb)
            moved = True
            if rider is not None:
                nxt.pop(c)
                nxt[nb] = rider
            if rider == "fozwvlovdui" and not scrolled:
                shift = -dx * CELL
                scrolled = True
                if ox >= 5 and shift > 0:
                    break                             # the guard returns; later carts stay put
                nox = ox + shift
        if moved:
            out.append(((tuple(sorted(nxt.items())), tuple(sorted(nc)), nox), ("drive", d)))
    return out


def main() -> None:
    root = (tuple(sorted(PADS0.items())), CARTS0, OX0)
    seen = {root: None}
    q = deque([root])
    win = None
    cap = 4_000_000
    while q and len(seen) < cap:
        s = q.popleft()
        if len(s[0]) == 2:                            # the win is the pad count reaching two
            win = s
            break
        for ns, mv in successors(s):
            if ns not in seen:
                seen[ns] = (s, mv)
                q.append(ns)
    if win is None:
        best = min(seen, key=lambda s: len(s[0]))
        print(json.dumps({"win": False, "states": len(seen), "fewest_pads": len(best[0]),
                          "capped": len(seen) >= cap}))
        return
    path = []
    node = win
    while seen[node] is not None:
        parent, mv = seen[node]
        path.append(mv)
        node = parent
    path.reverse()
    steps = []
    s = root
    for mv in path:
        nxt = next(ns for ns, m in successors(s) if m == mv)
        steps.append({"mv": mv, "ox": s[2], "ox_after": nxt[2],
                      "pads": len(s[0]), "pads_after": len(nxt[0])})
        s = nxt
    print(json.dumps({"meta": {"win": True, "states": len(seen), "moves": len(path),
                               "actions": sum(2 if m[0] == "jump" else 1 for m in path)},
                      "steps": steps}))


if __name__ == "__main__":
    main()
