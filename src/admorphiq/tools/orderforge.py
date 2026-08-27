"""Forge exactly the order the header prints, then park it in the sockets.

RECOVERED MECHANIC (frame-only, measured on live boards 2026-08-27). The board is a table of
loose pieces, a header that states an ORDER, and a set of sockets. One click opens a short
vacuum: everything whose rectangle lies within a fixed reach of the clicked cell is dragged so
its CENTRE lands exactly on that cell. Two pieces that land together and share a rank FUSE into
one piece a rung UP a ladder; two that land together with different ranks are REJECTED -- the
board flashes, the move is rolled back and the allowance is docked twice over. The level is won
the instant the sockets hold exactly what the header asked for, counted by piece centre.

The header is the specification and it prints two separate things, told apart by STRUCTURE and
never by what they are printed on. A LADDER is a run of three or more identical marks, evenly
spaced, every one a different colour: that is the rank order, and a ladder never names a rank
twice. A second such run, where the board has strikers, is the striker kinds. Everything else in
the header is the ORDER -- one icon per item wanted, drawn as the very shape and colour it asks
for, so an icon is matched to a board object by colour alone. The board also draws its ALLOWANCE
as a bar along the bottom edge that shortens by a cell a turn; this tool does not read it,
because its plans are ten turns long against allowances of thirty-two and forty-eight, and a
plan that needed the bar would already be the wrong plan.

A STRIKER is the ladder run backwards, and it is the reason the deep boards are not just a
merge exercise. It walks toward the NEAREST piece under its own power -- no click required,
four cells for every turn taken anywhere on the board -- and a touch knocks that piece one rung
DOWN (a touch at the bottom rung destroys it outright). Two strikers that touch each other fuse
one kind UP, exactly like pieces. The deep boards hand out one oversized piece and no way to
split it, so descending the ladder ON PURPOSE is the only route to the rank asked for, and on
some of them a struck-up striker must itself be parked. That is the whole of the late game:
a piece is built by fusing up, or by being eaten down, and both are planned, not stumbled into.

Three measurements shape the code and none is guessable from a still frame:

* ONE CLICK IS ONE ACTION, and the settled board is the LAST layer of the stack the action hands
  back -- layer 0 is the board BEFORE the vacuum ran. Reading layer 0 forces a second, wasted
  action per vacuum to see the outcome, which doubles the action count of every level; the
  metric is the square of the action ratio, so that alone is a 4x price. Measured side by side
  on this family: the incumbent, which pays the extra look, clears 7 of 9 levels in 147 actions
  and spends one level that a human clears in 8 on 18 of its own; reading the last layer, the
  same 7 levels cost 57 and that level costs 5.
* THE LOWEST STRIKER KIND IS LAUNCHED, NOT DRAGGED. A vacuum takes only the DIRECTION from it
  to the click and then flies it a fixed distance, sailing well past the clicked cell -- so it
  cannot be carried onto a victim, and a click placed on the far side of one SHOVES it away
  from a piece that must survive. Higher kinds are dragged like pieces.
* NOTHING WAITS. Strikers advance on every turn, including turns spent elsewhere, so an idle
  board eats itself: measured on one board, fourteen turns spent poking an empty corner took
  three pieces from ranks 3/3/5 down to 0/0 and the level from winnable to lost. There is no
  exploring here; every turn is bought from the allowance and paid for by the strikers.

HOW IT PLANS. The ladder arithmetic is solved first, as a search over MULTISETS of ranks -- fuse
two of r into one r+1, strike one r into one r-1, fuse two strikers of k into one k+1 -- for the
shortest sequence whose result contains the order. That sequence is a distance, not a script:
the tool then scores every click it could make by simulating the turn and asking how much closer
the board is to the end of that sequence, and takes the best one. Re-solving from the board every
single turn is what makes it robust to the strikers, because an unwanted strike simply changes the
multiset and the next turn plans from where the board actually is.

SELECTIVITY comes from the conjunction and never from one part: a board that offers only clicks,
a header that prints an ORDER over its chrome, at least one SOCKET, at least one piece whose
colour the header names, and a ladder arithmetic that actually reaches the order. A board that
draws an order it cannot name in its own pieces is not this family and ``detect`` scores 0.
"""

from __future__ import annotations

import math
from collections import Counter, deque
from dataclasses import dataclass, replace
from typing import Any

import numpy as np

from admorphiq.tools.base import Step, availability, has_frame
from admorphiq.tools.segment import background

__all__ = ["OrderForgeTool"]

# --- measured physics, held as defaults and checked against every turn -------
# The vacuum's reach, in cells from the clicked cell to the nearest cell of a piece. Refined
# online: a piece predicted to move and did not shrinks it, one that moved and was not predicted
# grows it. Started at the value the sample boards exhibit rather than at zero, because a first
# guess that is too small merely wastes a turn while one that is too large mixes ranks and is
# docked twice.
_REACH0 = 8
# How far a dragged object closes on the clicked cell per tick, and how many ticks a vacuum runs.
# Their product bounds the drag, and it exceeds the reach, so a caught object always ARRIVES.
_DRAG = 4
_TICKS = 4
# A launched striker's per-tick flight, as a fraction of the drag. Measured: 0.85.
_LAUNCH = 0.85 * _DRAG
# Ticks a striker is deaf for after a hit, and how far its victim is thrown.
_COOLDOWN = 9
_KNOCKBACK = 10

# Board geometry limits, all of them about telling furniture from pieces.
_MIN_SOCKET = 16
_MAX_SOCKET_SIDE = 20
_MIN_SOCKET_SIDE = 5
_MAX_PIECE_SIDE = 12
# A ladder strip needs this many swatches before it is a ladder rather than two stray marks.
_MIN_LADDER = 3
# A header shorter than this cannot be one: it has to carry an order, and usually a ladder
# above it. A board of this family puts a handful of pieces out, never a crowd, and the table
# they sit on is mostly empty.
_MIN_HEADER = 6
_MIN_EMPTY = 0.8
_MAX_PIECES = 24
# Search caps. The multiset search is tiny; the click search is bounded by the objects on the
# board, because a click that catches nothing is only ever a stalling move.
_MAX_PLAN_STATES = 40000
_MAX_OPS = 24
_MAX_CANDIDATES = 1400
# The reach is one number and the board keeps re-proving it; a correction loop that never
# settles is a bug, so the online fit is allowed a handful of moves and then stands.
_MAX_REACH_FIXES = 6
# Turns of watching one COLOUR before a glyph that has never moved is struck off the striker
# list. Not two: a striker that has just landed a hit stands still for a couple of turns.
_SIFT_AFTER = 4
# Lookahead. Kept shallow on purpose: the board is re-read and re-planned every turn, so depth
# buys the ONE thing a single turn cannot see -- a setup move that looks like a step backwards.
_DEPTH = 3
_BEAM = 10
_TURN_COST = 5.0
# What a striker's remaining distance to a socket is worth next to a piece's. Low because it
# closes that distance by itself, on turns that are being spent on something else.
_STRIKER_FARE = 0.25
# One level's worth of turns on this family is tens, not hundreds. Past this the board is not one
# this tool reads and holding the turn spends the whole game -- measured on this very family, the
# incumbent spent 1200 turns on a board it could not finish.
_MAX_TURNS = 240
_CONF = 0.86

Point = tuple[int, int]


def _settled(obs: Any) -> np.ndarray:
    """The board AFTER the vacuum has run, not while it is running.

    ⛔ Read deliberately, and only inside this tool. The shared reader takes layer 0 and one
    action on this family hands back a five-layer stack whose first layer is the board BEFORE
    the click took effect. A tool reading it cannot see its own move and must spend a second
    action to look, which doubles every level's action count under a squared metric. The last
    layer is where the vacuum has finished and the ring overlay has been cleared.
    """
    arr = np.asarray(getattr(obs, "frame", None))
    if arr.ndim >= 3:
        arr = arr[-1]
    return arr.astype(np.int64)


# --- perception -------------------------------------------------------------


@dataclass(frozen=True)
class _Obj:
    """One movable thing: ``x``/``y`` is its top-left cell, ``w``/``h`` its rectangle.

    ``rank`` is its rung on its own ladder (pieces and strikers keep separate ladders) and
    ``striker`` says which. The rectangle, not the painted cells, is what the board collides
    with -- a striker is drawn as a sparse glyph but occupies its whole box.
    """

    x: int
    y: int
    w: int
    h: int
    colour: int
    rank: int
    striker: bool

    @property
    def cx(self) -> int:
        return self.x + self.w // 2

    @property
    def cy(self) -> int:
        return self.y + self.h // 2


@dataclass(frozen=True)
class _Socket:
    x: int
    y: int
    w: int
    h: int

    @property
    def cx(self) -> int:
        return self.x + self.w // 2

    @property
    def cy(self) -> int:
        return self.y + self.h // 2

    def holds(self, o: _Obj) -> bool:
        return self.x <= o.cx < self.x + self.w and self.y <= o.cy < self.y + self.h


@dataclass
class _Read:
    """Everything one frame says about the board."""

    top: int
    bottom: int
    bg: int
    ladder: list[int]
    slad: list[int]
    order: Counter          # (striker?, rank) -> count
    objs: list[_Obj]
    sockets: list[_Socket]
    named: frozenset          # striker colours the HEADER names, which are never in doubt
    icon_side: dict           # colour -> the width the ORDER draws it at, rungs included


def _row_modes(g: np.ndarray) -> list[int]:
    return [int(np.bincount(row[row >= 0]).argmax()) if (row >= 0).any() else -1 for row in g]


def _band(g: np.ndarray, bg: int) -> tuple[int, int] | None:
    """The playfield is the longest run of rows whose commonest colour is the board's own."""
    modes = _row_modes(g)
    best: tuple[int, int] | None = None
    run = -1
    for y, m in enumerate(modes + [-2]):
        if m == bg and run < 0:
            run = y
        elif m != bg and run >= 0:
            if best is None or y - run > best[1] - best[0] + 1:
                best = (run, y - 1)
            run = -1
    if best is None or best[1] - best[0] + 1 < 32 or best[0] < 2:
        return None
    return best


def _blobs(g: np.ndarray, y0: int, y1: int, bg: int, weld: bool) -> list[dict[str, Any]]:
    """Same-colour clusters between two rows; ``weld`` joins diagonals as well.

    Welding is not cosmetic: a striker is drawn as an X of single cells that plain
    4-connectivity shatters into five separate objects.
    """
    h, w = g.shape
    seen = np.zeros((h, w), dtype=bool)
    nbr = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    if weld:
        nbr += [(-1, -1), (-1, 1), (1, -1), (1, 1)]
    out: list[dict[str, Any]] = []
    for y in range(y0, y1 + 1):
        for x in range(w):
            c = int(g[y, x])
            if seen[y, x] or c == bg or c < 0:
                continue
            stack = [(y, x)]
            seen[y, x] = True
            cells = []
            while stack:
                cy, cx = stack.pop()
                cells.append((cy, cx))
                for dy, dx in nbr:
                    ny, nx = cy + dy, cx + dx
                    if y0 <= ny <= y1 and 0 <= nx < w and not seen[ny, nx] and int(g[ny, nx]) == c:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            ys = [q[0] for q in cells]
            xs = [q[1] for q in cells]
            out.append({
                "colour": c, "n": len(cells),
                "y": min(ys), "x": min(xs),
                "h": max(ys) - min(ys) + 1, "w": max(xs) - min(xs) + 1,
            })
    return out


def _strips(marks: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Pick out the LADDER strips: runs of equal marks, evenly spaced, all different colours.

    ⛔ Read from the strip's own structure, never from what field it is printed on. The first
    version told a ladder swatch from an order icon by the colour BEHIND it, which is exactly
    what the sample board shows -- and the archived re-render of that same board draws the
    backing strip two swatches shorter, so the last two rungs of the ladder sit on the chrome
    and were read as two extra items in the order. The board became unreadable at its second
    level while the live copy played out to the end. Structure survives a re-render; a
    backdrop's width does not.

    All-different colours is what keeps an order of three identical items from being mistaken
    for a ladder: a ladder never names a rung twice.
    """
    out: list[list[dict[str, Any]]] = []
    bands: list[list[dict[str, Any]]] = []
    for m in sorted(marks, key=lambda b: (b["y"], b["x"])):
        for band in bands:
            if abs(band[0]["y"] - m["y"]) <= 1 and band[0]["h"] == m["h"] and band[0]["w"] == m["w"]:
                band.append(m)
                break
        else:
            bands.append([m])
    for band in bands:
        band.sort(key=lambda b: b["x"])
        if len(band) < _MIN_LADDER:
            continue
        cols = [b["colour"] for b in band]
        if len(set(cols)) != len(cols):
            continue
        gaps = [b["x"] - a["x"] for a, b in zip(band, band[1:])]
        if max(gaps) - min(gaps) > 1:
            continue
        out.append(band)
    return out


def _cells_of(g: np.ndarray, b: dict[str, Any]) -> set[tuple[int, int]]:
    return {(y, x)
            for y in range(b["y"], b["y"] + b["h"])
            for x in range(b["x"], b["x"] + b["w"])
            if int(g[y, x]) == b["colour"]}


def _split_glyphs(g: np.ndarray, group: list[dict[str, Any]],
                  known: dict[int, tuple[set, int, int]] | None = None) -> list[dict[str, Any]]:
    """Break clusters that hold SEVERAL glyphs of one colour back into single glyphs.

    ⛔ Two strikers standing corner to corner weld into one cluster, and a cluster that big is
    thrown out as furniture -- so a board momentarily has three strikers where it has four, the
    ladder arithmetic declares the order out of reach, and the tool withdraws from a board it
    was three clicks from finishing. Same-kind strikers that actually OVERLAP fuse on the spot,
    so an oversized cluster is always neighbours, never a doubling.

    The glyph is drawn identically everywhere it appears, so the smallest clean instance is the
    template and the rest is a scan.
    """
    fit = [b for b in group if 3 <= b["w"] <= 8 and 3 <= b["h"] <= 8]
    seen = (known or {}).get(group[0]["colour"])
    if fit:
        b0 = min(fit, key=lambda b: (b["w"] * b["h"], b["n"]))
        shape = {(y - b0["y"], x - b0["x"]) for y, x in _cells_of(g, b0)}
        base = {"w": b0["w"], "h": b0["h"]}
        if seen is not None and len(seen[0]) < len(shape):
            shape, base = seen[0], {"w": seen[1], "h": seen[2]}
    elif seen is not None:
        # ⛔ REMEMBERED, because a frame can arrive in which every glyph of a colour is welded
        # to another and there is no clean one left to measure. That is not a corner case: two
        # strikers stalking the same piece converge and end up exactly one glyph apart. The
        # shape is drawn identically wherever it appears, so one clean sighting settles it for
        # the rest of the game -- and without that memory the board silently drops a striker
        # and the ladder arithmetic declares a winnable order out of reach.
        shape, base = seen[0], {"w": seen[1], "h": seen[2]}
    else:
        return []
    if not shape:
        return fit
    need = max(1, int(math.ceil(0.8 * len(shape))))
    out: list[dict[str, Any]] = []
    h, w = g.shape
    for b in group:
        # ⛔ The test is against the TEMPLATE, not against a fixed size. Judging it by whether
        # the cluster fits inside eight cells missed the case that actually occurs: two glyphs
        # a couple of cells apart weld into a cluster still small enough to look like one, and
        # the board silently loses a striker. Cell count is what gives it away.
        if b["w"] <= base["w"] and b["h"] <= base["h"] and b["n"] <= 1.4 * len(shape):
            out.append(b)
            continue
        cells = _cells_of(g, b)
        want = max(1, round(b["n"] / len(shape)))
        hits = []
        for y in range(b["y"], b["y"] + b["h"]):
            for x in range(b["x"], b["x"] + b["w"]):
                if y + base["h"] > h or x + base["w"] > w:
                    continue
                score = sum(1 for dy, dx in shape if (y + dy, x + dx) in cells)
                if score >= need:
                    hits.append((-score, y, x))
        hits.sort()
        taken: list[tuple[int, int]] = []
        for _, y, x in hits:
            if len(taken) >= want:
                break
            if any(abs(y - ty) < base["h"] and abs(x - tx) < base["w"] for ty, tx in taken):
                continue
            taken.append((y, x))
            out.append({"colour": b["colour"], "n": len(shape),
                        "y": y, "x": x, "h": base["h"], "w": base["w"]})
    if known is not None:
        prev = known.get(group[0]["colour"])
        if prev is None or len(shape) < len(prev[0]):
            known[group[0]["colour"]] = (shape, base["w"], base["h"])
    return out


def _split_squares(b: dict[str, Any]) -> list[dict[str, Any]]:
    """A solid bar of one piece colour is two or more pieces standing shoulder to shoulder."""
    if b["n"] != b["w"] * b["h"] or b["w"] == b["h"]:
        return []
    lo, hi = min(b["w"], b["h"]), max(b["w"], b["h"])
    if lo < 1 or hi % lo:
        return []
    out = []
    for i in range(hi // lo):
        if b["w"] > b["h"]:
            out.append({**b, "x": b["x"] + i * lo, "w": lo, "n": lo * lo})
        else:
            out.append({**b, "y": b["y"] + i * lo, "h": lo, "n": lo * lo})
    return out


def _read_frame(g: np.ndarray, cached: list[_Socket] | None,
                deny: set[int] | None = None,
                glyphs: dict[int, tuple[set, int, int]] | None = None) -> _Read | None:
    """Turn one settled frame into the board: ladders, order, objects, sockets."""
    bg = next(iter(background(g)))
    band = _band(g, bg)
    if band is None:
        return None
    top, bottom = band
    # ⛔ Three shape guards, every one of them a measured false bid. Run on a live board of a
    # DIFFERENT game -- not its title screen, thirty-nine turns in -- this reader found a
    # two-row "header", read a column of chrome down the frame's own edge as sixty-two pieces
    # of the bottom rung, and bid 0.86 on a board another tool was solving. A header has to be
    # tall enough to print an order under a ladder; a table of loose pieces is mostly EMPTY
    # table; and no board of this family puts two dozen pieces out at once.
    if top < _MIN_HEADER:
        return None
    header = g[:top]
    if header.size == 0:
        return None
    chrome = Counter(int(v) for v in header.ravel()).most_common(1)[0][0]
    play = g[top:bottom + 1]
    if float((play == bg).mean()) < _MIN_EMPTY:
        return None

    marks = _blobs(g, 0, top - 1, chrome, weld=True)
    marks = [m for m in marks if m["colour"] != bg and m["w"] <= 12 and m["h"] <= 12]
    strips = _strips(marks)
    laid = {(m["y"], m["x"]) for st in strips for m in st}
    icons = [m for m in marks if (m["y"], m["x"]) not in laid]
    if not icons:
        return None

    # An icon drawn as a filled square asks for a PIECE; anything sparser asks for a striker.
    def _solid(m: dict[str, Any]) -> bool:
        return m["n"] == m["w"] * m["h"] and m["w"] == m["h"]

    piece_cols = {m["colour"] for m in icons if _solid(m)}
    striker_cols = {m["colour"] for m in icons if not _solid(m)}
    solid = _blobs(g, top, bottom, bg, weld=False)
    welded = _blobs(g, top, bottom, bg, weld=True)
    board_pieces = {b["colour"] for b in solid
                    if b["w"] == b["h"] and b["n"] == b["w"] * b["h"] and b["w"] <= _MAX_PIECE_SIDE}
    ladder: list[int] = []
    slad: list[int] = []
    spare: list[list[int]] = []
    for st in strips:
        cols = [m["colour"] for m in st]
        if striker_cols & set(cols):
            slad = cols
        elif (piece_cols | board_pieces) & set(cols):
            ladder = cols
        else:
            spare.append(cols)
    for cols in spare:
        if not ladder:
            ladder = cols
        elif not slad:
            slad = cols
    if ladder:
        piece_cols |= set(ladder)
    if slad:
        striker_cols |= set(slad)
    if not piece_cols:
        return None

    # --- the board itself
    objs: list[_Obj] = []
    for b in solid:
        if b["colour"] not in piece_cols:
            continue
        for p in ([b] if b["w"] == b["h"] and b["n"] == b["w"] * b["h"] else _split_squares(b)):
            if p["w"] > _MAX_PIECE_SIDE:
                continue
            objs.append(_Obj(p["x"], p["y"], p["w"], p["h"], p["colour"], -1, False))

    # Sockets are printed behind everything, in a colour the header never names, and they are
    # read before the strikers because a socket is exactly the kind of large hollow shape a
    # striker glyph would otherwise be mistaken for.
    sockets: list[_Socket] = []
    for b in solid:
        if b["colour"] in piece_cols:
            continue
        if b["n"] < _MIN_SOCKET or abs(b["w"] - b["h"]) > 2:
            continue
        if not (_MIN_SOCKET_SIDE <= b["w"] <= _MAX_SOCKET_SIDE):
            continue
        if b["n"] < 0.5 * b["w"] * b["h"]:
            continue
        sockets.append(_Socket(b["x"], b["y"], b["w"], b["h"]))
    taken = {(s.x, s.y) for s in sockets}

    named = frozenset(striker_cols)
    # A striker is a GLYPH: a welded cluster too sparse to be a piece, small enough not to be
    # furniture, in a colour the pieces do not use.
    #
    # ⛔ Naming them off the header alone is not enough, and the board that hands out eight
    # bottom-rung pieces proved it: it prints no striker in its order and no striker strip, so
    # its one striker was invisible, nothing guarded the pieces, and the exact arithmetic that
    # board needs was destroyed by the first touch. Anything glyph-shaped is a striker on
    # suspicion; ``deny`` carries back the ones that turned out never to move, because moving
    # under its own power is what a striker actually is.
    by_col: dict[int, list[dict[str, Any]]] = {}
    for b in welded:
        c = b["colour"]
        if c in piece_cols or c in (deny or set()) or (b["x"], b["y"]) in taken:
            continue
        if b["n"] < 5 or b["n"] >= 0.9 * b["w"] * b["h"]:
            continue
        by_col.setdefault(c, []).append(b)
    for c, group in by_col.items():
        for b in _split_glyphs(g, group, glyphs):
            objs.append(_Obj(b["x"], b["y"], b["w"], b["h"], c, -1, True))
            striker_cols.add(c)

    # Ranks. The ladder strip gives the order outright; without one, size order stands in --
    # the pieces on this family grow strictly with rank, which the strip's own order confirms
    # wherever both are visible.
    if not ladder:
        sizes: dict[int, int] = {}
        for m in icons:
            if _solid(m):
                sizes[m["colour"]] = m["w"]
        for o in objs:
            if not o.striker:
                sizes[o.colour] = o.w
        ladder = [c for c, _ in sorted(sizes.items(), key=lambda kv: kv[1])]
    rank_of = {c: i for i, c in enumerate(ladder)}
    skind_of = {c: i for i, c in enumerate(slad)} if slad else {
        c: i for i, c in enumerate(sorted(striker_cols))}
    objs = [replace(o, rank=(skind_of if o.striker else rank_of).get(o.colour, -1)) for o in objs]
    objs = [o for o in objs if o.rank >= 0]
    if not any(not o.striker for o in objs):
        return None
    if sum(1 for o in objs if not o.striker) > _MAX_PIECES:
        return None

    order: Counter = Counter()
    for m in icons:
        st = not _solid(m)
        table = skind_of if st else rank_of
        if m["colour"] not in table:
            return None
        order[(st, table[m["colour"]])] += 1
    if not order:
        return None

    if cached and len(sockets) < len(cached):
        sockets = cached
    if not sockets:
        return None
    icon_side = {m["colour"]: m["w"] for m in icons if _solid(m)}
    return _Read(top, bottom, bg, ladder, list(slad) or sorted(striker_cols),
                 order, objs, sockets, named, icon_side)


# --- ladder arithmetic ------------------------------------------------------


def _plan(objs: list[_Obj], order: Counter, nranks: int, nkinds: int) -> list[tuple[str, int]] | None:
    """Shortest sequence of fusions and strikes whose result contains the order.

    The board is reduced to two multisets -- piece ranks and striker kinds -- because the only
    thing the ladder cares about is how many of each rung exist. Positions decide how EXPENSIVE
    a step is, not whether it is possible, and they are handled by the click search.
    """
    pc = [0] * max(nranks, 1)
    sc = [0] * max(nkinds, 1)
    for o in objs:
        if o.striker:
            if o.rank < len(sc):
                sc[o.rank] += 1
        elif o.rank < len(pc):
            pc[o.rank] += 1
    want_p = [0] * len(pc)
    want_s = [0] * len(sc)
    for (st, r), n in order.items():
        if st:
            if r >= len(want_s):
                return None
            want_s[r] += n
        else:
            if r >= len(want_p):
                return None
            want_p[r] += n

    def done(p: tuple[int, ...], s: tuple[int, ...]) -> bool:
        return all(p[i] >= want_p[i] for i in range(len(p))) and \
            all(s[i] >= want_s[i] for i in range(len(s)))

    start = (tuple(pc), tuple(sc))
    if done(*start):
        return []
    seen = {start: None}
    q: deque = deque([start])
    states = 0
    while q and states < _MAX_PLAN_STATES:
        p, s = q.popleft()
        states += 1
        nxt: list[tuple[tuple, tuple, tuple[str, int]]] = []
        has_striker = sum(s) > 0
        for r in range(len(p)):
            if p[r] >= 2 and r + 1 < len(p):
                np_ = list(p)
                np_[r] -= 2
                np_[r + 1] += 1
                nxt.append((tuple(np_), s, ("fuse", r)))
            if p[r] >= 1 and has_striker:
                np_ = list(p)
                np_[r] -= 1
                if r >= 1:
                    np_[r - 1] += 1
                nxt.append((tuple(np_), s, ("strike", r)))
        for k in range(len(s)):
            if s[k] >= 2 and k + 1 < len(s):
                ns = list(s)
                ns[k] -= 2
                ns[k + 1] += 1
                nxt.append((p, tuple(ns), ("sfuse", k)))
        for np_, ns, op in nxt:
            key = (np_, ns)
            if key in seen:
                continue
            seen[key] = (p, s, op)
            if done(np_, ns):
                ops: list[tuple[str, int]] = []
                cur = key
                while seen[cur] is not None:
                    pp, ss, oo = seen[cur]
                    ops.append(oo)
                    cur = (pp, ss)
                    if len(ops) > _MAX_OPS:
                        return None
                ops.reverse()
                return ops
            q.append(key)
    return None


# --- the turn simulator -----------------------------------------------------


def _reaches(q: Point, o: _Obj, reach: int) -> bool:
    cx = min(max(q[0], o.x), o.x + o.w - 1)
    cy = min(max(q[1], o.y), o.y + o.h - 1)
    return (q[0] - cx) ** 2 + (q[1] - cy) ** 2 <= reach * reach


def _overlap(a: _Obj, b: _Obj) -> bool:
    return (a.x < b.x + b.w and b.x < a.x + a.w
            and a.y < b.y + b.h and b.y < a.y + a.h)


def _clamp(o: _Obj, x: int, y: int, top: int, bot: int) -> tuple[int, int]:
    x = max(0, min(x, 64 - o.w))
    y = max(top, min(y, min(bot + 1, 64 - o.h)))
    return x, y


def _side_table(read: _Read) -> dict[int, int]:
    """Rung -> side length, from every piece and icon the frame shows, extrapolated.

    A fused piece is a rung higher and therefore WIDER, and its width decides what the next
    click can catch. The boards draw the run of sizes on their own pieces and icons; where a
    rung has never been seen, the observed run is continued rather than guessed at, and one
    cell per rung is what every observed run does.
    """
    known: dict[int, int] = {}
    for c, side in read.icon_side.items():
        if c in read.ladder:
            known[read.ladder.index(c)] = side
    for o in read.objs:
        if not o.striker:
            known[o.rank] = o.w
    if not known:
        return {}
    lo = min(known)
    out = dict(known)
    for r in range(len(read.ladder)):
        if r not in out:
            out[r] = max(1, known[lo] + (r - lo))
    return out


class _Sim:
    """One turn of the board, played out exactly as the vacuum does it.

    Object identity is held by SLOT, never by list position after a removal: a striker that
    fuses mid-turn would otherwise renumber the pieces a click had already caught, and the
    fusion at the end of the turn would then be scored against the wrong ones.
    """

    def __init__(self, read: _Read, reach: int, sides: dict[int, int]) -> None:
        self.order = read.order
        self.sockets = read.sockets
        self.top = read.top
        self.bot = read.bottom
        self.reach = reach
        self.nkinds = max(len(read.slad), 1)
        self.nranks = max(len(read.ladder), 1)
        self.sides = sides

    def _resize(self, o: _Obj, rank: int) -> _Obj:
        """Re-rank a piece about its own centre, in the width its new rung is drawn at."""
        side = self.sides.get(rank, max(1, o.w + (rank - o.rank)))
        x = o.cx - side // 2
        y = o.cy - side // 2
        n = replace(o, rank=rank, w=side, h=side)
        x, y = _clamp(n, x, y, self.top, self.bot)
        return replace(n, x=x, y=y)

    def step(self, objs: list[_Obj], q: Point) -> tuple[list[_Obj], bool, bool]:
        """The board after one click: what stands, whether the rungs were REJECTED, and whether
        the order was ever complete DURING the turn.

        ⛔ The last of those is not a nicety. The board is read for a win after EVERY tick, not
        at the end, and a striker parked in its socket walks straight back out of it the moment
        a piece exists to chase -- so on the boards that ask for a striker the order holds for a
        tick or two and never again. Scoring only the settled board made a level that is one
        click from won look no better than doing nothing, and the tool sat on it until the
        allowance ran out.
        """
        if not (self.top <= q[1] <= self.bot):
            return objs, False, False
        n = len(objs)
        cur: list[_Obj | None] = list(objs)
        cool = [0] * n
        caught = [i for i in range(n) if _reaches(q, objs[i], self.reach)]
        cset = set(caught)
        launch: dict[int, tuple[float, float]] = {}
        for i in caught:
            o = objs[i]
            if o.striker and o.rank == 0:
                dx, dy = q[0] - o.cx, q[1] - o.cy
                d = math.hypot(dx, dy)
                launch[i] = (dx / d, dy / d) if d else (0.0, 0.0)
        fpos = {i: (float(objs[i].x), float(objs[i].y)) for i in launch}
        ever = False
        for _ in range(_TICKS):
            for i in caught:
                o = cur[i]
                if o is None:
                    continue
                if i in launch:
                    ux, uy = launch[i]
                    fx, fy = fpos[i]
                    nx, ny = _clamp(o, round(fx + ux * _LAUNCH), round(fy + uy * _LAUNCH),
                                    self.top, self.bot)
                    fpos[i] = (float(nx), float(ny))
                else:
                    dx = max(-_DRAG, min(_DRAG, q[0] - o.cx))
                    dy = max(-_DRAG, min(_DRAG, q[1] - o.cy))
                    nx, ny = _clamp(o, o.x + dx, o.y + dy, self.top, self.bot)
                cur[i] = replace(o, x=nx, y=ny)
            self._strikers(cur, cool, cset)
            ever = ever or _won([o for o in cur if o is not None], self.sockets, self.order)
        out, rejected = self._fuse(objs, cur, caught)
        return out, rejected, ever or _won(out, self.sockets, self.order)

    def _strikers(self, cur: list[_Obj | None], cool: list[int], cset: set[int]) -> None:
        """Strikers walk at the nearest piece, hit it, then fuse with one another."""
        pieces = [i for i, o in enumerate(cur) if o is not None and not o.striker]
        for i, o in enumerate(cur):
            if o is None or not o.striker or i in cset:
                continue
            if cool[i] > 0:
                cool[i] -= 1
                continue
            if not pieces:
                continue
            j = min(pieces, key=lambda k: (cur[k].cx - o.cx) ** 2 + (cur[k].cy - o.cy) ** 2)
            sp = 2 if (o.rank == self.nkinds - 1 and self.nkinds >= 3) else 1
            t = cur[j]
            dx = sp if t.cx > o.cx else (-sp if t.cx < o.cx else 0)
            dy = sp if t.cy > o.cy else (-sp if t.cy < o.cy else 0)
            nx, ny = _clamp(o, o.x + dx, o.y + dy, self.top, self.bot)
            cur[i] = replace(o, x=nx, y=ny)
        for i, o in enumerate(cur):
            if o is None or not o.striker or i in cset or cool[i] > 0:
                continue
            for j in pieces:
                p = cur[j]
                if p is None or not _overlap(o, p):
                    continue
                cool[i] = _COOLDOWN
                if p.rank <= 0:
                    cur[j] = None
                    break
                dx, dy = p.cx - o.cx, p.cy - o.cy
                d = math.hypot(dx, dy) or 1.0
                hit = self._resize(p, p.rank - 1)
                nx, ny = _clamp(hit, round(hit.x + dx / d * _KNOCKBACK),
                                round(hit.y + dy / d * _KNOCKBACK), self.top, self.bot)
                cur[j] = replace(hit, x=nx, y=ny)
                break
        idx = [i for i, o in enumerate(cur) if o is not None and o.striker]
        for a in range(len(idx)):
            for b in range(a + 1, len(idx)):
                i, j = idx[a], idx[b]
                oi, oj = cur[i], cur[j]
                if oi is None or oj is None or not _overlap(oi, oj):
                    continue
                if oi.rank != oj.rank or oi.rank + 1 >= self.nkinds:
                    continue
                cur[i] = replace(oi, rank=oi.rank + 1,
                                 x=(oi.x + oj.x) // 2, y=(oi.y + oj.y) // 2)
                cur[j] = None

    def _fuse(self, before: list[_Obj], cur: list[_Obj | None],
              caught: list[int]) -> tuple[list[_Obj], bool]:
        """Pieces that arrived together fuse a rung up; mixed rungs roll the whole turn back."""
        live = [i for i in caught if cur[i] is not None and not cur[i].striker]
        groups: list[list[int]] = []
        for i in live:
            for gr in groups:
                if any(_overlap(cur[i], cur[j]) for j in gr):
                    gr.append(i)
                    break
            else:
                groups.append([i])
        for gr in groups:
            if len(gr) < 2:
                continue
            ranks = {cur[i].rank for i in gr}
            if len(ranks) > 1:
                return before, True
            o = cur[gr[0]]
            if o.rank + 1 >= self.nranks:
                return before, True
            cur[gr[0]] = self._resize(o, o.rank + 1)
            for i in gr[1:]:
                cur[i] = None
        return [o for o in cur if o is not None], False


# --- scoring ----------------------------------------------------------------


def _hops(dx: int, dy: int, reach: int) -> float:
    """Turns to carry something that far, one vacuum being worth about one reach.

    Deliberately CONTINUOUS. Rounding it up to whole turns was measured to flatten the score
    over every click inside the same rung of the reach, and a search with nothing to walk
    downhill on wandered until the allowance ran out with the piece three cells from its socket.
    """
    return max(abs(dx), abs(dy)) / float(max(1, reach))


def _parked(objs: list[_Obj], sockets: list[_Socket]) -> Counter:
    held: Counter = Counter()
    for o in objs:
        if any(s.holds(o) for s in sockets):
            held[(o.striker, o.rank)] += 1
    return held


def _won(objs: list[_Obj], sockets: list[_Socket], order: Counter) -> bool:
    held = _parked(objs, sockets)
    return all(held.get(k, 0) == n for k, n in order.items())


def _park_cost(objs: list[_Obj], sockets: list[_Socket], order: Counter, reach: int) -> float:
    """Turns to carry the finished items into a socket, plus what is still missing.

    ⛔ ANY socket, and the same one twice over if that is nearest. The first version handed each
    item its own socket, which is a rule the board does not have: the order is counted over
    every socket at once, by piece centre. Insisting on distinct sockets made the boards that
    ask for a striker unwinnable as modelled -- a striker walks at the nearest piece, so the one
    place it reliably ends up is the socket the piece is already sitting in, and refusing that
    left the tool freezing the board with a vacuum centred on the striker rather than finishing.
    """
    cost = 0.0
    for (st, r), n in sorted(order.items()):
        have = [o for o in objs if o.striker == st and o.rank == r]
        have.sort(key=lambda o: min(_hops(s.cx - o.cx, s.cy - o.cy, reach) for s in sockets))
        for i in range(n):
            if i >= len(have):
                cost += 6.0
                continue
            o = have[i]
            # Being INSIDE is not the end of it: the order is read every tick and a striker
            # leaves a socket the instant it has a piece to chase, so an item on the rim holds
            # for one tick and one in the middle holds for four. The gradient buys that.
            best = min(sockets, key=lambda s: _hops(s.cx - o.cx, s.cy - o.cy, reach))
            d = _hops(best.cx - o.cx, best.cy - o.cy, reach)
            d = 0.3 * d if any(s.holds(o) for s in sockets) else 1.0 + d
            # A striker's journey is not paid for in turns. It walks at the nearest piece by
            # itself, on every turn including the ones spent elsewhere, so once a piece is
            # sitting in a socket the striker delivers itself into that same socket for free.
            # Charging its distance at full rate made carrying the piece look like a step
            # backwards -- the striker drifts off its socket the moment the piece moves -- and
            # the tool froze the board rather than pay it.
            cost += _STRIKER_FARE * d if st else d
    over = 0
    held = _parked(objs, sockets)
    for k, n in held.items():
        if n > order.get(k, 0):
            over += n - order.get(k, 0)
    return cost + 4.0 * over


def _pair_cost(objs: list[_Obj], ops: list[tuple[str, int]], reach: int) -> float:
    """Turns to bring together whatever each pending fusion or strike needs.

    Without this the plan length alone is flat over every click that does not complete a step,
    and the search has nothing to walk downhill on.
    """
    cost = 0.0
    for kind, r in ops[:4]:
        if kind in ("fuse", "sfuse"):
            st = kind == "sfuse"
            cand = [o for o in objs if o.striker == st and o.rank == r]
            if len(cand) < 2:
                continue
            cost += min(_hops(a.cx - b.cx, a.cy - b.cy, reach)
                        for i, a in enumerate(cand) for b in cand[i + 1:])
        elif kind == "strike":
            vic = [o for o in objs if not o.striker and o.rank == r]
            sts = [o for o in objs if o.striker]
            if not vic or not sts:
                continue
            cost += min(_hops(a.cx - b.cx, a.cy - b.cy, reach) for a in vic for b in sts)
    return cost


def _danger(objs: list[_Obj], ops: list[tuple[str, int]], order: Counter,
            sockets: list[_Socket], reach: int) -> float:
    """How exposed the pieces are to a strike the plan did not ask for.

    ⛔ This covers EVERY piece, not only the ones already at a wanted rung. The first version
    guarded the finished pieces alone and lost the board that hands out eight pieces of the
    bottom rung for a rung-three order: the arithmetic is exact there, a single touch destroys
    a bottom-rung piece outright, and the ladder can no longer reach the order however the rest
    are played. What is at stake is the WEIGHT on the board, and every piece carries some.

    One piece per planned strike is exempt -- that one is supposed to be caught.
    """
    sts = [o for o in objs if o.striker]
    if not sts:
        return 0.0
    exempt: set[int] = set()
    for kind, r in ops:
        if kind != "strike":
            continue
        cand = [o for o in objs if not o.striker and o.rank == r and id(o) not in exempt]
        if cand:
            exempt.add(id(min(cand, key=lambda o: min(
                max(abs(o.cx - s.cx), abs(o.cy - s.cy)) for s in sts))))
    wants_striker = any(st for st, _ in order)
    pen = 0.0
    for o in objs:
        if o.striker or id(o) in exempt:
            continue
        # A piece already in a socket, on a board whose order also wants a striker, is BAIT by
        # design: the striker walking in to eat it is what carries it into the socket, and the
        # order is read on the tick it arrives, before the blow lands.
        if wants_striker and any(s.holds(o) for s in sockets):
            continue
        d = min(max(abs(o.cx - s.cx), abs(o.cy - s.cy)) for s in sts)
        pen += max(0.0, 3 * reach - d) / float(_DRAG)
    return pen


def _toward(o: _Obj, g: Point, reach: int, top: int, bot: int, frac: float = 1.0) -> Point:
    """The furthest cell a single vacuum can carry ``o`` toward ``g``.

    A caught object lands exactly on the clicked cell, so the longest useful click sits at the
    edge of the reach measured from the object's own rectangle -- which is why the half-width
    is added rather than the click being aimed at the object's centre.
    """
    dx, dy = g[0] - o.cx, g[1] - o.cy
    d = math.hypot(dx, dy)
    span = min(d, (reach + o.w // 2) * frac)
    if d <= 1e-6:
        return (o.cx, o.cy)
    x = int(round(o.cx + dx / d * span))
    y = int(round(o.cy + dy / d * span))
    return (max(0, min(63, x)), max(top, min(bot, y)))


class OrderForgeTool:
    """Build exactly the order the header prints, then park it."""

    name = "orderforge"

    def __init__(self) -> None:
        self._cache: tuple[bytes, _Read | None] | None = None
        # The glyph a striker is drawn as does not change between levels, so this survives a
        # reset -- one clean sighting on any board reads every welded pair on every later one.
        self._shapes: dict[int, tuple[set, int, int]] = {}
        # The reach is a constant of the GAME, not of a board, so what one level proved about
        # it is worth keeping for the next.
        self._reach = _REACH0
        self._fixes = 0
        self.reset()

    # --- lifecycle ---------------------------------------------------------

    def reset(self) -> None:
        """A new board reprints the order; everything about the old one goes, except the two
        things that belong to the GAME rather than to a board -- the reach, and how a striker
        of each colour is drawn."""
        self._sockets: list[_Socket] | None = None
        self._plans: dict[tuple, list[tuple[str, int]] | None] = {}
        self._pending: tuple[Point, list[_Obj], list[_Obj]] | None = None
        self._deny: set[int] = set()
        self._glyphs: dict[int, frozenset] = {}
        self._moved: set[int] = set()
        self._seen: Counter = Counter()
        self._turns = 0
        self._stuck = False

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """Every fact this tool acts on is re-read from the board, so a transition carries none.

        The one thing a transition WOULD carry -- whether the reach guess was right -- needs the
        settled board that follows it, which ``observe`` is not given, so it is checked at the
        top of the next ``propose`` instead.
        """

    # --- perception cache --------------------------------------------------

    def _read(self, obs: Any) -> _Read | None:
        g = _settled(obs)
        key = g.tobytes()
        if self._cache is not None and self._cache[0] == key:
            return self._cache[1]
        read = _read_frame(g, self._sockets, self._deny, self._shapes)
        if read is not None:
            self._sockets = read.sockets
        self._cache = (key, read)
        return read

    def _solve(self, read: _Read, objs: list[_Obj]) -> list[tuple[str, int]] | None:
        pc = tuple(sorted((o.rank for o in objs if not o.striker)))
        sc = tuple(sorted((o.rank for o in objs if o.striker)))
        key = (pc, sc)
        if key not in self._plans:
            self._plans[key] = _plan(objs, read.order,
                                     max(len(read.ladder), 1), max(len(read.slad), 1))
        return self._plans[key]

    # --- the bid -----------------------------------------------------------

    def detect(self, frames: list[Any], obs: Any) -> float:
        """A printed order, a ladder that reaches it, sockets to park it in -- or nothing."""
        if self._stuck or not has_frame(obs):
            return 0.0
        simple, action6 = availability(obs)
        # This board is worked entirely by clicking. A board that also walks an avatar around
        # is a different family however much its header resembles one.
        if not action6 or any(1 <= a <= 4 for a in simple):
            return 0.0
        read = self._read(obs)
        if read is None:
            return 0.0
        if not any(not o.striker for o in read.objs):
            return 0.0
        return _CONF if self._solve(read, read.objs) is not None else 0.0

    # --- the turn ----------------------------------------------------------

    def _learn_reach(self, objs: list[_Obj]) -> None:
        """Correct the reach against what the last click actually carried.

        The evidence is the disagreement between the simulated turn and the board that came
        back, and only PIECES count: a striker walks under its own power every turn, so its
        having moved says nothing about what the vacuum caught. A piece whose rung changed is
        thrown out too -- it was struck, and a struck piece is thrown clear of wherever the
        vacuum would have put it.

        ⛔ The first version compared before to after instead, and shrank the reach every time a
        click landed a piece exactly where it already stood. Three such turns took the reach
        from 8 to 5, after which the tool could no longer reach its own socket and stalled one
        cell away from finishing the opening level.
        """
        if self._pending is None or self._fixes >= _MAX_REACH_FIXES:
            return
        q, before, predicted = self._pending
        self._pending = None
        pred = {(o.x, o.y, o.rank) for o in predicted if not o.striker}
        act = {(o.x, o.y, o.rank) for o in objs if not o.striker}
        if pred == act or len(pred) != len(act):
            return
        for o in before:
            if o.striker:
                continue
            key = (o.x, o.y, o.rank)
            if key not in act:
                continue
            if _reaches(q, o, self._reach) and key not in pred:
                self._reach = max(3, self._reach - 1)
                self._fixes += 1
                return
        for o in before:
            if o.striker:
                continue
            key = (o.x, o.y, o.rank)
            if key in act or _reaches(q, o, self._reach) or key not in pred:
                continue
            self._reach = min(12, self._reach + 1)
            self._fixes += 1
            return

    def _sift_glyphs(self, read: _Read) -> None:
        """Drop from the striker set any glyph that has never moved under its own power.

        Suspicion is how a glyph gets in (see ``_read_frame``), and this is how it gets out. A
        board can print a hint or a marker that is every bit as sparse as a striker; the one
        thing it will not do is walk. Colours the header itself names are exempt -- those are
        strikers whatever they happen to be doing.
        """
        now: dict[int, set] = {}
        for o in read.objs:
            if o.striker:
                now.setdefault(o.colour, set()).add((o.x, o.y))
        for c, pos in now.items():
            if c in self._glyphs and self._glyphs[c] != frozenset(pos):
                self._moved.add(c)
        self._glyphs = {c: frozenset(p) for c, p in now.items()}
        for c in now:
            self._seen[c] += 1
        # ⛔ Counted PER COLOUR, not per turn. Counting turns struck off a striker that had just
        # been born -- two strikers fuse into a new kind partway through a board, and the new
        # kind was denied on the turn it first appeared because the board itself was already
        # several turns old. The board then had an invisible striker eating the pieces it
        # needed, and an exact arithmetic went unwinnable without a single click looking wrong.
        fresh = {c for c in now
                 if self._seen[c] >= _SIFT_AFTER and c not in self._moved and c not in read.named}
        if fresh - self._deny:
            self._deny |= fresh
            self._cache = None

    def _candidates(self, read: _Read, objs: list[_Obj], wide: bool = True) -> list[Point]:
        """Every click worth simulating: it either carries something, or it buys a turn.

        The named points come first and are never dropped -- a socket's own cell finishes a
        park, a pair's midpoint completes a fusion, and the far side of a striker shoves it off
        a piece that has to survive. The lattice behind them is what covers everything else a
        vacuum could reach, at a coarse pitch because the reach is many cells wide.
        """
        top, bot, reach = read.top, read.bottom, self._reach

        def ok(p: Point) -> bool:
            return top <= p[1] <= bot and 0 <= p[0] <= 63

        named: list[Point] = [(s.cx, s.cy) for s in read.sockets]
        for o in objs:
            named.append((o.cx, o.cy))
            for g in [(s.cx, s.cy) for s in read.sockets] + [(p.cx, p.cy) for p in objs]:
                named.append(_toward(o, g, reach, top, bot))
                named.append(_toward(o, g, reach, top, bot, 0.6))
            for p in objs:
                if p is p and p is not o:
                    named.append(((o.cx + p.cx) // 2, (o.cy + p.cy) // 2))
                    named.append(_toward(o, (2 * o.cx - p.cx, 2 * o.cy - p.cy), reach, top, bot))
        # turns spent letting a striker close its own distance are moves too
        named += [(1, top), (62, top), (1, bot), (62, bot), (32, (top + bot) // 2)]

        lattice: list[Point] = []
        span = reach + _MAX_PIECE_SIDE
        for o in (objs if wide else []):
            for dy in range(-span, span + 1, 2):
                for dx in range(-span, span + 1, 2):
                    p = (o.cx + dx, o.cy + dy)
                    if ok(p) and _reaches(p, o, reach):
                        lattice.append(p)
        out: list[Point] = []
        seen: set[Point] = set()
        for p in named + lattice:
            if p in seen or not ok(p):
                continue
            seen.add(p)
            out.append(p)
            if len(out) >= _MAX_CANDIDATES:
                break
        return out

    def _score(self, read: _Read, objs: list[_Obj], rejected: bool) -> float:
        if _won(objs, read.sockets, read.order):
            return -1e9
        ops = self._solve(read, objs)
        if ops is None:
            return 1e6
        return (40.0 * len(ops)
                + 6.0 * _pair_cost(objs, ops, self._reach)
                + 6.0 * _park_cost(objs, read.sockets, read.order, self._reach)
                + 8.0 * _danger(objs, ops, read.order, read.sockets, self._reach)
                + (30.0 if rejected else 0.0))

    def _search(self, read: _Read, sim: _Sim) -> Point | None:
        """Pick the click by looking a few turns ahead, not one.

        ⛔ One turn is not enough on this family and the boards that ask for a striker prove it.
        A striker sitting on its socket walks OUT of it the moment a piece exists to chase, so
        the turn that wins is the one where the piece lands while the striker happens to be
        crossing its own socket -- and getting it to cross means first SHOVING it past, which
        makes the board look worse for exactly one turn. Scored one turn at a time the tool
        found a click that froze the board instead (a vacuum centred on a striker moves it
        nowhere and stops it chasing) and sat there until the allowance ran out.
        """
        beam: list[tuple[float, list[_Obj], Point]] = []
        for q in self._candidates(read, read.objs, wide=True):
            after, rejected, won = sim.step(read.objs, q)
            if won:
                return q
            beam.append((self._score(read, after, rejected), after, q))
        if not beam:
            return None
        beam.sort(key=lambda t: t[0])
        best = beam[0]
        beam = beam[:_BEAM]
        for depth in range(1, _DEPTH):
            nxt: list[tuple[float, list[_Obj], Point]] = []
            for _, objs, first in beam:
                for q in self._candidates(read, objs, wide=False):
                    after, rejected, won = sim.step(objs, q)
                    if won:
                        return first
                    s = self._score(read, after, rejected) + _TURN_COST * depth
                    nxt.append((s, after, first))
            if not nxt:
                break
            nxt.sort(key=lambda t: t[0])
            if nxt[0][0] < best[0]:
                best = nxt[0]
            beam = nxt[:_BEAM]
        return best[2]

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        read = self._read(obs)
        if read is None:
            return []
        self._turns += 1
        if self._turns > _MAX_TURNS:
            self._stuck = True
            return []
        self._learn_reach(read.objs)
        self._sift_glyphs(read)
        sim = _Sim(read, self._reach, _side_table(read))
        q = self._search(read, sim)
        if q is None:
            return []
        self._pending = (q, read.objs, sim.step(read.objs, q)[0])
        return [(6, q)]
