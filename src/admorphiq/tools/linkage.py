"""Reach every ring marker with a dot marker by winding framed two-way controls.

The mechanic this recovers, stated in frame terms only. A board carries two kinds of small
marker in one rare colour: a LONE CELL (the thing that moves) and a DIAMOND of four cells
around an empty centre (the place it must reach). Elsewhere sit framed widgets — a rectangle
whose border is exactly the perimeter of its own bounding box. A widget split by a single line
down its middle is a TWO-WAY control: clicking one side of the line translates some subset of
the lone cells by a fixed vector, clicking the other side translates them back. A widget with
no such line is a ONE-WAY control, and clicking it re-articulates the board so that every
two-way control means something different afterwards. The level is won when every diamond has
a marker cell at its centre.

Nothing about which control moves which marker is assumed. Each two-way control is probed once,
the observed displacement IS the model, and the plan is an A* over the WINDING — how far each
control has been driven from where the level started it.

⛔ THE FIRST FRAME LAYER AFTER A REFUSED MOVE IS A LIE, AND THE LAST LAYER IS THE TRUTH. This
is the one measurement the whole tool is built on, and reading the wrong layer is what a first
version of this got wrong. A click whose result would overlap is applied, tested, and undone —
and the engine hands back BOTH renders in one observation: layer 0 shows the marker three cells
inside the wall it never entered, layer -1 shows it where it actually is. A tool reading layer 0
sees the marker keep advancing after the arm has stopped, learns displacements no control can
produce, and walls itself in; MEASURED, it drifted for fifty actions on a board it can now
finish in fifteen. Reading the last layer costs nothing, needs no probe, and needs no algebra:
**a refusal is exactly an observation with more than one layer whose first and last differ**.

⛔ Why the winding is ONE COUNT PER CONTROL and not one per direction. Two controls that shift a
marker the same way are NOT interchangeable — each drives its own linkage, each has its own stop,
and each contributes its own geometry to whether a configuration overlaps. Folding them into a
single count makes the planner believe a direction is still open when only the exhausted one of
the two is being asked for, and makes every refusal it banks ambiguous. The per-control winding
costs a wider search and buys a model that is exactly right.

⛔ Why a REFUSED WINDING is banked globally rather than as "this move, from here". What the
engine tests is the shape of the whole board AFTER the click, and that shape is a function of
the winding alone. So a winding that overlaps overlaps however it was reached, and one refused
action teaches the planner about every route that would have ended there.

⛔ Why a mover is found by SUBTRACTING the rings rather than by isolation. A mover that comes to
rest on its ring stops being a lone cell — it becomes the centre of a five-cell plus — and a
mover that merely passes next to a ring stops being lone for one frame. Counting isolated cells
therefore loses movers exactly when the board is closest to solved. Ring cells are identified
first and every remaining marker cell is a mover, which survives both cases.
"""

from __future__ import annotations

import heapq
import math
from collections import Counter
from itertools import permutations
from typing import Any

import numpy as np

from admorphiq.tools import segment
from admorphiq.tools.base import Step, availability, has_frame

__all__ = ["LinkageReachTool", "Markers", "Piece", "marker_colour", "read_markers",
           "read_controls", "read_pieces"]

Cell = tuple[int, int]
Vec = tuple[Cell, ...]
Key = tuple[int, int]

# A framed control is furniture, not the board: everything found is small.
_MAX_WIDGET = 24
_MIN_WIDGET = 4
# Boards in this family carry a handful of markers; a colour with more is painting something.
_MAX_MARKERS = 12
# A* refuses to grind: these boards resolve in tens of clicks or the model is wrong.
_MAX_EXPAND = 40_000
_MAX_DEPTH = 96
# How far a single control may be wound from where the level started it. A control that shifts a
# marker three cells cannot usefully be wound past the width of the board.
_MAX_WIND = 22
# Actions to spend without getting closer before handing the turn back.
_GIVE_UP = 45
# Attempts to characterise one control before giving up on it for this level.
_MAX_PROBES = 4
# How far the search leans on its estimate of the distance left. ⛔ At 1 the search is optimal and
# unusable: the winding is six-dimensional, several of its axes move no marker at all so the
# estimate cannot separate them, and one plan took longer than the game it was planning. Leaning
# on the estimate finds a route a few moves longer in a fraction of the nodes, and on a board
# scored by ACTIONS a plan that arrives is worth far more than a plan that is shortest.
_LEAN = 3
# What routing a marker through a cell a refusal already reached costs, in moves. Big enough to
# send the plan the long way round, small enough that a marker which must FINISH there still can.
_WALL_COST = 20
_UNREACHABLE = 1 << 20


# --- perception --------------------------------------------------------------


class Markers:
    """What one colour's cells say: where the places are, and what is on the move."""

    __slots__ = ("movers", "places", "sound")

    def __init__(self, movers: list[Cell], places: list[Cell], sound: bool) -> None:
        self.movers = movers
        self.places = places
        self.sound = sound


def _diamond(y: int, x: int) -> list[Cell]:
    return [(y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)]


def read_markers(g: np.ndarray, colour: int) -> Markers:
    """Split one colour's cells into the places (diamonds) and the movers (everything else).

    ``sound`` says the split accounted for every cell of the colour with nothing ragged left
    over — the test that keeps this from latching onto a colour that also paints a wall.
    """
    h, w = g.shape
    on = g == colour
    places: list[Cell] = []
    occupied: list[Cell] = []
    used: set[Cell] = set()
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            ring = _diamond(y, x)
            if not all(on[a, b] for a, b in ring):
                continue
            places.append((y, x))
            used.update(ring)
            if on[y, x]:
                occupied.append((y, x))
                used.add((y, x))
    movers = [(int(y), int(x)) for y, x in np.argwhere(on) if (int(y), int(x)) not in used]
    sound = True
    for y, x in movers:
        near = [(a, b) for a, b in _diamond(y, x) if 0 <= a < h and 0 <= b < w]
        if any(on[a, b] for a, b in near):
            sound = False
    return Markers(sorted(movers + occupied), sorted(places), sound)


def marker_colour(g: np.ndarray) -> int | None:
    """The colour that reads cleanly as places-plus-movers, or None if no colour does."""
    bg = segment.background(g)
    best: tuple[int, int] | None = None
    chosen: int | None = None
    for colour in sorted({int(v) for v in np.unique(g)} - bg):
        m = read_markers(g, colour)
        if not m.places or not m.sound:
            continue
        if len(m.places) + len(m.movers) > _MAX_MARKERS:
            continue
        if len(m.movers) != len(m.places):
            continue
        score = (len(m.places), -int((g == colour).sum()))
        if best is None or score > best:
            best, chosen = score, colour
    return chosen


def _perimeter(y0: int, x0: int, y1: int, x1: int) -> set[Cell]:
    ring = set()
    for x in range(x0, x1 + 1):
        ring.add((y0, x))
        ring.add((y1, x))
    for y in range(y0, y1 + 1):
        ring.add((y, x0))
        ring.add((y, x1))
    return ring


def _divider(box: np.ndarray) -> tuple[str, int, int] | None:
    """The middle line that splits a widget in two — axis, offset and COLOUR — or None.

    Two tests, both needed. The line must sit at the EXACT middle of the widget, and its colour
    must appear nowhere else inside it. Measured: a one-way button whose glyph is a plus has a
    uniform middle column too, and only the second test rejects it — that glyph colour also
    paints the arms of the plus, so its count exceeds the line's length.
    """
    h, w = box.shape
    for axis in ("v", "h") if w >= h else ("h", "v"):
        across = w if axis == "v" else h
        mid = across // 2
        if not 1 <= mid <= across - 2:
            continue
        line = box[1:h - 1, mid] if axis == "v" else box[mid, 1:w - 1]
        if line.size < 1 or len({int(v) for v in line}) != 1:
            continue
        colour = int(line[0])
        if int((box == colour).sum()) != int(line.size):
            continue
        return axis, mid, colour
    return None


def read_controls(g: np.ndarray) -> list[dict[str, Any]]:
    """Every framed widget on the board, each with the click points that work it.

    A widget is a colour component that is EXACTLY the perimeter of its own bounding box. A
    solid bar fails that test (its component fills the box) and so does an L-shaped wall, which
    is why the board's own pieces do not register as furniture.
    """
    grid = g.tolist()
    palette = {int(v) for v in np.unique(g)}
    found: list[dict[str, Any]] = []
    for colour in sorted(palette - segment.background(g)):
        for cells in segment.components(grid, palette - {colour}):
            ys = [c[0] for c in cells]
            xs = [c[1] for c in cells]
            y0, y1, x0, x1 = min(ys), max(ys), min(xs), max(xs)
            h, w = y1 - y0 + 1, x1 - x0 + 1
            if not (_MIN_WIDGET <= h <= _MAX_WIDGET and _MIN_WIDGET <= w <= _MAX_WIDGET):
                continue
            if set(cells) != _perimeter(y0, x0, y1, x1):
                continue
            split = _divider(g[y0:y1 + 1, x0:x1 + 1])
            if split is None:
                found.append({"box": (y0, x0, y1, x1), "band": None,
                              "clicks": [(x0 + w // 2, y0 + h // 2)]})
                continue
            axis, mid, band = split
            if axis == "v":
                cy = y0 + h // 2
                clicks = [(x0 + mid + 1, cy), (x0 + mid - 1, cy)]
            else:
                cx = x0 + w // 2
                clicks = [(cx, y0 + mid + 1), (cx, y0 + mid - 1)]
            found.append({"box": (y0, x0, y1, x1), "band": band, "clicks": clicks})
    return found


def _board_same(a: np.ndarray, b: np.ndarray) -> bool:
    """Are these two renders the same BOARD, ignoring an edge-pinned counter?

    ⛔ MEASURED, and it cost a level: this family draws its remaining-actions budget as a bar
    along the last row, so two renders of an unchanged board are almost never equal. A tool that
    asks "did anything change" with a plain comparison reads "the control moved something" from
    the budget ticking down, and concludes that a control which in fact refused to retract past
    its stop is instead driving a linkage that carries no marker. That mislabelling removed the
    only control that could raise the marker, and the board became unreachable by arithmetic.
    """
    return bool(np.array_equal(a[1:-1, 1:-1], b[1:-1, 1:-1]))


class Piece:
    """One structure component: what it looks like, and how each control moves its edges."""

    __slots__ = ("cells", "colour", "law", "rect", "solid")

    def __init__(self, cells: set[Cell], rect: tuple[int, int, int, int], solid: bool,
                 colour: int) -> None:
        self.cells = cells
        self.rect = rect
        self.solid = solid
        self.colour = colour
        self.law: dict[int, tuple[int, int, int, int]] = {}

    def at(self, counts: tuple[int, ...]) -> tuple[int, int, int, int]:
        """Where this piece's box sits at a winding, one edge at a time.

        Recording a per-EDGE response rather than a displacement is what lets one representation
        carry both things a control does: a piece that is carried moves all four edges together,
        and a piece that is LENGTHENED moves one edge while the opposite one stays anchored.
        """
        y0, x0, y1, x1 = self.rect
        for i, n in enumerate(counts):
            if not n:
                continue
            d = self.law.get(i)
            if d is None:
                continue
            y0 += n * d[0]
            x0 += n * d[1]
            y1 += n * d[2]
            x1 += n * d[3]
        return y0, x0, y1, x1


def _around(y: int, x: int, shape: tuple[int, int]) -> list[Cell]:
    h, w = shape
    return [(y + dy, x + dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1)
            if (dy or dx) and 0 <= y + dy < h and 0 <= x + dx < w]


def _sane(law: tuple[int, int, int, int]) -> bool:
    """Is this a response a linkage can actually have — a carry, a lengthening, or both?

    Every real response moves each edge by a whole number of the board's own step, and lengthens
    along at most one axis. A response that fails either test came from pairing two pieces that
    are not the same piece, and a model built on one of those forbids moves that are fine.
    """
    dy0, dx0, dy1, dx1 = law
    if any(d % 3 or abs(d) > 9 for d in law):
        return False
    return dy1 == dy0 or dx1 == dx0


def _box_of(cells: set[Cell]) -> tuple[int, int, int, int]:
    ys = [c[0] for c in cells]
    xs = [c[1] for c in cells]
    return min(ys), min(xs), max(ys), max(xs)


def _fills(cells: set[Cell], holes: set[Cell]) -> tuple[tuple[int, int, int, int], bool]:
    y0, x0, y1, x1 = _box_of(cells)
    box = {(y, x) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)}
    return (y0, x0, y1, x1), len(cells | (box & holes)) == len(box)


def _merge_bands(pieces: list[Piece], holes: set[Cell], band: int) -> list[Piece]:
    """Put each marked edge back onto the piece it belongs to.

    ⛔ Every piece of this linkage carries a one-cell stripe in the same colour the widgets use
    for their own divider, marking the end it is anchored by — so plain colour components cut
    every piece in two, and the halves change shape as the piece lengthens, which makes them
    unmatchable across a frame. Merging by ADJACENCY alone is not safe either: two pieces lying
    side by side merge into one box that is solid and wrong. The stripe's colour is the test, and
    the frame states it — it is the colour the two-way widgets rule themselves with.
    """
    out = [p for p in pieces if p.colour != band]
    for strip in (p for p in pieces if p.colour == band):
        hosts = []
        for host in out:
            y0, x0, y1, x1 = strip.rect
            a0, b0, a1, b1 = host.rect
            if y0 > a1 + 1 or a0 > y1 + 1 or x0 > b1 + 1 or b0 > x1 + 1:
                continue
            rect, solid = _fills(host.cells | strip.cells, holes)
            if solid:
                hosts.append((host, rect))
        if len(hosts) != 1:
            out.append(strip)
            continue
        host, rect = hosts[0]
        host.cells |= strip.cells
        host.rect = rect
        host.solid = True
    return out


def read_pieces(g: np.ndarray, marker: int, boxes: list[tuple[int, int, int, int]],
                band: int | None = None) -> list[Piece]:
    """Every structure component of the board: the things that are not allowed to overlap.

    Structure is what is left after the background, the markers and the framed widgets are taken
    out. ⛔ A marker cell is a HOLE in the piece under it, not an absence of piece: a marker sits
    ON the thing that carries it and is painted over it, so a component with a marker in the
    middle is still a filled box. Counting the hole against it makes the carrier read as ragged
    scenery, and the one piece whose position matters most drops out of the model.

    The outer ring is left out entirely — that is where this family draws its budget bar, and a
    bar that shrinks by a cell every few actions would otherwise re-cut the board each time.
    """
    board = g.copy()
    for y0, x0, y1, x1 in boxes:
        board[max(0, y0):y1 + 1, max(0, x0):x1 + 1] = -1
    board[0, :] = board[-1, :] = board[:, 0] = board[:, -1] = -1
    # ⛔ A marker painted on a piece is a HOLE THROUGH IT, and leaving it as one cuts the piece
    # into fragments whose boxes are nonsense — MEASURED, a marker resting in a ring split its
    # carrier into two single cells with laws no linkage could produce. Where a marker cell is
    # surrounded by one structure colour it is filled back in with that colour, which puts the
    # piece back together; a marker standing on the background is left alone.
    holes = {(int(y), int(x)) for y, x in np.argwhere(board == marker)}
    ground = segment.background(g)
    for y, x in sorted(holes):
        near = Counter(int(board[b, a]) for b, a in _around(y, x, board.shape)
                       if int(board[b, a]) not in ground and int(board[b, a]) not in (-1, marker))
        if near:
            board[y, x] = near.most_common(1)[0][0]
    palette = {int(v) for v in np.unique(board)} - {-1, marker}
    skip = segment.background(g) | {marker, -1}
    grid = board.tolist()
    out: list[Piece] = []
    for colour in sorted(palette - skip):
        for cells in segment.components(grid, (palette | {-1, marker}) - {colour}):
            rect, solid = _fills(set(cells), holes)
            out.append(Piece(set(cells), rect, solid, colour))
    return out if band is None else _merge_bands(out, holes, band)


def _pair_pieces(before: list[Piece], after: list[Piece]) -> dict[int, tuple[int, int, int, int]]:
    """Match each piece to the box it became, by the pairing that changed it least.

    Matching is by COLOUR first and box second, and the colour is load-bearing. ⛔ MEASURED: on a
    chain of equal-sized pieces, one notch slides each piece into the box its neighbour just left,
    so the cheapest box pairing is "nothing moved" — cost zero, and completely wrong. Every law
    read that way is nonsense. Within one colour the pieces are far apart and the nearest box is
    the right one.
    """
    pairs: list[tuple[int, int, int]] = []
    for bi, b in enumerate(before):
        for ai, a in enumerate(after):
            if a.colour != b.colour:
                continue
            cost = sum(abs(u - v) for u, v in zip(b.rect, a.rect))
            if cost <= 12:
                pairs.append((cost, bi, ai))
    pairs.sort()
    taken_b: set[int] = set()
    taken_a: set[int] = set()
    out: dict[int, tuple[int, int, int, int]] = {}
    for _, bi, ai in pairs:
        if bi in taken_b or ai in taken_a:
            continue
        taken_b.add(bi)
        taken_a.add(ai)
        out[bi] = after[ai].rect
    return out


def _layers(obs: Any) -> list[np.ndarray]:
    """Every render the engine produced for one action, oldest first.

    An action that is simply taken renders once. An action the engine tests and then UNDOES
    renders twice — the attempt, then the board put back — and an action that finishes a level
    renders twice as well, the solved board and then the next one. In both cases the last
    render is the board that now exists.
    """
    fr = getattr(obs, "frame", None)
    if fr is None:
        return []
    arr = np.asarray(fr)
    if arr.ndim == 2:
        return [arr.astype(np.int64)]
    if arr.ndim == 3:
        return [a.astype(np.int64) for a in arr]
    return []


# --- planning ----------------------------------------------------------------


def _assign_cost(pos: Vec, goals: Vec) -> int:
    """Cheapest total Manhattan distance over pairings of movers to places."""
    if not goals:
        return 0
    if len(goals) > len(pos):
        return _UNREACHABLE
    best = math.inf
    for order in permutations(range(len(pos)), len(goals)):
        total = 0
        for gi, pi in enumerate(order):
            total += abs(pos[pi][0] - goals[gi][0]) + abs(pos[pi][1] - goals[gi][1])
        best = min(best, total)
    return int(best)


def _at(base: Vec, units: list[Vec], counts: tuple[int, ...]) -> Vec:
    """Where the movers sit when each control has been wound to its count."""
    out = []
    for m, start in enumerate(base):
        y, x = start
        for n, unit in zip(counts, units):
            if n:
                y += n * unit[m][0]
                x += n * unit[m][1]
        out.append((y, x))
    return tuple(out)


def _wind(counts: tuple[int, ...], key: Key) -> tuple[int, ...]:
    """The winding after driving one control one notch the way that key drives it."""
    i, side = key
    return counts[:i] + (counts[i] + (1 if side == 0 else -1),) + counts[i + 1:]


def _plan(
    base: Vec,
    units: list[Vec],
    counts: tuple[int, ...],
    goals: Vec,
    live: list[int],
    forbidden: set[tuple[int, ...]],
    blocked: set[tuple[tuple[int, ...], Key]],
    bounds: dict[int, tuple[int, int]],
    walls: set[Cell],
    caps: dict[tuple[int, int, tuple[int, ...]], int],
    overlaps: Any,
) -> tuple[list[Key] | None, bool]:
    """A* over the winding — how far each control has been driven — not over marker cells.

    ⛔ The marker's cell is not the state, and treating it as one is what a first version of this
    got wrong. MEASURED: the same cell was reached two ways — with the base linkage wound out and
    with it wound in — and only one of them could then be lifted, because the wound-out base parks
    the next joint against scenery. A planner keyed on the cell banks "cannot go up from here",
    carries that to the other configuration where up is fine, and walls itself in. The winding
    distinguishes them and every refusal it banks is about a real configuration.

    ⛔ A refusal is CARRIED ALONG ITS OWN AXIS, and without that the tool cannot finish a board.
    The exact fact a refusal gives is about one winding out of thousands, and every route to the
    places is a permutation of the same few moves — so a plan that knows only exact windings
    re-orders itself after each refusal, walks into the same obstruction by a different road, and
    pays one action per permutation. MEASURED: a whole level's budget spent that way on a board
    that needs fourteen moves. What is banked instead is "with the other controls where they are,
    this one goes no further this way", which is what an arm running into scenery actually means,
    and it retires an entire branch for one action.
    """
    if not live or not goals:
        return None, True
    step = max(1, max((abs(units[i][m][0]) + abs(units[i][m][1])
                       for i in live for m in range(len(base))), default=1))
    start = _at(base, units, counts)
    seen: dict[tuple[int, ...], int] = {counts: 0}
    heap: list[tuple[int, int, tuple[int, ...], tuple[Key, ...]]] = [
        (_LEAN * (_assign_cost(start, goals) // step), 0, counts, ())
    ]
    expanded = 0
    while heap and expanded < _MAX_EXPAND:
        _, g_cost, state, path = heapq.heappop(heap)
        if g_cost > seen.get(state, _UNREACHABLE):
            continue
        pos = _at(base, units, state)
        if _assign_cost(pos, goals) == 0:
            return list(path), False
        if len(path) >= _MAX_DEPTH:
            continue
        expanded += 1
        for i in live:
            lo, hi = bounds.get(i, (-_MAX_WIND, _MAX_WIND))
            for side in (0, 1):
                key = (i, side)
                if (state, key) in blocked:
                    continue
                n = state[i] + (1 if side == 0 else -1)
                if not lo <= n <= hi:
                    continue
                nxt = state[:i] + (n,) + state[i + 1:]
                if nxt in forbidden:
                    continue
                stop = caps.get((i, side, state[:i] + state[i + 1:]))
                if stop is not None and (n >= stop if side == 0 else n <= stop):
                    continue

                where = _at(base, units, nxt)
                if any(not (0 <= a < 64 and 0 <= b < 64) for a, b in where):
                    continue
                if overlaps is not None and overlaps(nxt):
                    continue
                ng = g_cost + 1 + _WALL_COST * sum(1 for c in where if c in walls)
                if ng >= seen.get(nxt, _UNREACHABLE):
                    continue
                seen[nxt] = ng
                heapq.heappush(heap, (ng + _LEAN * (_assign_cost(where, goals) // step),
                                      ng, nxt, path + (key,)))
    return None, not heap


def _rematch(prev: list[Cell], now: list[Cell]) -> list[Cell]:
    """Keep mover identity across a frame by the pairing that moved them least."""
    if len(prev) != len(now) or not prev:
        return sorted(now)
    best, out = math.inf, sorted(now)
    for order in permutations(now):
        total = sum(abs(a[0] - b[0]) + abs(a[1] - b[1]) for a, b in zip(prev, order))
        if total < best:
            best, out = total, list(order)
    return out


# --- the tool ----------------------------------------------------------------


class LinkageReachTool:
    """Probe each framed control once, then wind the controls until every place is filled."""

    name = "linkage"

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._colour: int | None = None
        self._places: Vec = ()
        self._controls: list[dict[str, Any]] = []
        self._buttons: list[Cell] = []
        self._vec: dict[int, Vec] = {}
        self._bounds: dict[int, tuple[int, int]] = {}
        self._probes: dict[int, int] = {}
        self._state: tuple[int, ...] = ()
        self._base: Vec = ()
        self._pos: Vec = ()
        self._forbidden: set[tuple[int, ...]] = set()
        self._walls: set[Cell] = set()
        self._caps: dict[tuple[int, int, tuple[int, ...]], int] = {}
        self._pieces: list[Piece] = []
        self._movers: list[Piece] = []
        self._static = np.zeros((0, 0), dtype=bool)
        self._sum: list[list[int]] = []
        self._overlap: dict[tuple[int, ...], bool] = {}
        self._geometry = False
        self._misses = 0
        self._blocked: set[tuple[tuple[int, ...], Key]] = set()
        self._pending: tuple[Key | None, tuple[int, ...], Vec, np.ndarray, bool] | None = None
        self._undo: Key | None = None
        self._unread: set[int] = set()
        self._boxes: list[tuple[int, int, int, int]] = []
        self._band: int | None = None
        self._path: list[Key] = []
        self._path_at: tuple[int, ...] | None = None
        self._turns = 0
        self._best = _UNREACHABLE
        self._stale = 0
        self._knew = 0

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """No-op: every transition is read back off the observation in ``propose``."""

    def detect(self, frames: list[Any], obs: Any) -> float:
        """Confidence, which is 0.0 unless this board is actually workable.

        Three things must all hold: a colour whose cells read cleanly as diamond places plus
        movers, at least one OPEN place to fill, and at least one two-way control to move a
        mover with. A board missing any of them has no plan here, and a tool that bids for a
        board it cannot plan on costs the game that could.
        """
        if not has_frame(obs):
            return 0.0
        _, action6 = availability(obs)
        if not action6:
            return 0.0
        layers = _layers(obs)
        if not layers:
            return 0.0
        g = layers[-1]
        colour = marker_colour(g)
        if colour is None:
            return 0.0
        m = read_markers(g, colour)
        if not set(m.places) - set(m.movers):
            return 0.0
        if not any(len(c["clicks"]) == 2 for c in read_controls(g)):
            return 0.0
        return 0.9

    # -- acting --------------------------------------------------------------

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        if not has_frame(obs):
            return []
        layers = _layers(obs)
        if not layers:
            return []
        g = layers[-1]
        colour = self._colour if self._colour is not None else marker_colour(g)
        if colour is None:
            return []
        m = read_markers(g, colour)
        places = tuple(m.places)
        if not places:
            return []
        if colour != self._colour or places != self._places:
            self._start(g, colour, m)
        elif self._pending is not None:
            self._resolve(layers, m)
        else:
            self._pos = self._read(m, self._state)
        self._reseat()

        if not set(places) - set(self._pos):
            # Every place is filled and the level has not turned over: nothing here to add.
            return []
        gap = _assign_cost(self._pos, places)
        known = self._known()
        if gap < self._best or known > self._knew:
            # Learning that a winding overlaps is progress even though it moves nothing: it is
            # what lets the next plan route around the obstruction. Counting it as a wasted
            # action retires the tool in the middle of working a board out.
            self._best, self._stale = min(gap, self._best), 0
            self._knew = known
        else:
            self._stale += 1
            if self._stale > _GIVE_UP:
                # Closer is the only evidence this tool is the right one for the board. Once it
                # has stopped getting closer it is spending a budget that ENDS THE GAME on two
                # of the sample games, so it hands the turn back rather than grinding it away.
                return []

        probe = self._next_probe()
        if self._undo is not None:
            back, self._undo = self._undo, None
            if probe is not None:
                return [self._fire(back, g)]
        if probe is not None:
            self._probes[probe[0]] = self._probes.get(probe[0], 0) + 1
            return [self._fire(probe, g, probe=True)]
        if self._pieces and not self._geometry and not self._overlap:
            self._build_geometry()

        live = sorted(self._vec)
        if self._path and self._path_at == self._state:
            key = self._path.pop(0)
            self._path_at = _wind(self._state, key)
            return [self._fire(key, g)]
        units = self._units()
        found, proved = _plan(self._base, units, self._state, places, live, self._forbidden,
                              self._blocked, self._bounds, self._walls, self._caps,
                              self._collides if self._geometry else None)
        if found is None and self._geometry:
            # ⛔ The model has just claimed there is no way to the places at all. It is built from
            # one probe per control, and on a board where two pieces could not be told apart it
            # makes exactly that claim about a board that is thirty moves from finished. A claim
            # that large is the model failing its last test: it is retired, and the search runs
            # again on the facts the engine itself has handed back.
            if proved:
                self._geometry = False
            found, _ = _plan(self._base, units, self._state, places, live, self._forbidden,
                             self._blocked, self._bounds, self._walls, self._caps, None)
        self._path = found or []
        if self._path:
            key = self._path.pop(0)
            self._path_at = _wind(self._state, key)
            return [self._fire(key, g)]
        self._path_at = None
        turn = self._next_turn()
        if turn is None:
            return []
        # No winding of the controls as they stand reaches the places. A one-way control
        # re-articulates the board, so everything learnt about the two-way ones is void
        # afterwards and the probing starts again from the shape the click leaves behind.
        self._turns += 1
        self._pending = (None, self._state, self._pos, g, False)
        return [(6, turn)]

    # -- state keeping -------------------------------------------------------

    def _fire(self, key: Key, g: np.ndarray, probe: bool = False) -> Step:
        self._pending = (key, self._state, self._pos, g, probe)
        return (6, self._controls[key[0]]["clicks"][key[1]])

    def _read_pieces(self, g: np.ndarray) -> list[Piece]:
        assert self._colour is not None
        return read_pieces(g, self._colour, self._boxes, self._band)

    def _start(self, g: np.ndarray, colour: int, m: Markers) -> None:
        """A different set of places means a different board: everything learnt is stale."""
        self.reset()
        widgets = read_controls(g)
        self._colour = colour
        self._places = tuple(m.places)
        self._controls = [c for c in widgets if len(c["clicks"]) == 2]
        self._buttons = [c["clicks"][0] for c in widgets if len(c["clicks"]) == 1]
        self._pos = tuple(sorted(m.movers))
        self._base = self._pos
        self._state = tuple(0 for _ in self._controls)
        self._boxes = [c["box"] for c in widgets]
        bands = [c["band"] for c in widgets if c["band"] is not None]
        self._band = bands[0] if len({*bands}) == 1 else None
        self._pieces = read_pieces(g, colour, self._boxes, self._band)
        # A control panel is drawn OVER the board, so a marker driven under one vanishes from
        # the frame. Pricing the panels keeps the plan on routes it can watch.
        self._walls = {(y, x) for y0, x0, y1, x1 in (c["box"] for c in widgets)
                       for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)} - set(self._places)

    def _units(self) -> list[Vec]:
        zero = tuple((0, 0) for _ in self._base)
        return [self._vec.get(i, zero) for i in range(len(self._controls))]

    def _readable(self, m: Markers) -> bool:
        """Does this frame show every mover, or is one of them painted over?"""
        return len(m.movers) == len(self._places)

    def _read(self, m: Markers, expect: tuple[int, ...]) -> Vec:
        """The movers this frame shows, or where the model says they are when it cannot show them.

        ⛔ A mover driven under a control panel is painted over and simply is not in the frame,
        and the winding it is read against must be the one the action was REACHING FOR, not the
        one it left. MEASURED: reading a hidden mover against the old winding makes every action
        look like it moved nothing, which marks every control as driving nothing, which retires
        a tool that was in fact working perfectly.
        """
        found = sorted(m.movers)
        if self._readable(m) and len(found) == len(self._pos):
            return tuple(_rematch(list(self._pos), found))
        return _at(self._base, self._units(), expect)

    def _resolve(self, layers: list[np.ndarray], m: Markers) -> None:
        """Fold the action just taken into the model, from what the observation actually shows."""
        assert self._pending is not None
        key, state, pos, before, probe = self._pending
        self._pending = None
        g = layers[-1]

        if key is None:
            # A one-way control fired. The linkage is a different shape now, so every learnt
            # vector, stop and refused winding describes a board that no longer exists.
            self._vec, self._bounds, self._probes = {}, {}, {}
            self._forbidden, self._blocked, self._caps = set(), set(), {}
            # The linkage has a different SHAPE now, so the decomposition is re-cut from the
            # board the click left behind rather than carried over from the one it replaced.
            self._pieces = self._read_pieces(g)
            self._movers, self._overlap, self._unread = [], {}, set()
            self._geometry = False
            self._path, self._path_at = [], None
            self._pos = tuple(sorted(m.movers)) if len(m.movers) == len(pos) else pos
            self._base = self._pos
            self._state = tuple(0 for _ in self._controls)
            self._best, self._stale, self._knew = _UNREACHABLE, 0, self._known()
            return

        if len(layers) > 1:
            # More than one render for one action means the engine drew a move, judged the board
            # it made and put it back — nothing else in this family renders twice within a
            # level. That judgement is about the WINDING, not about the route to it.
            spoiled = _wind(state, key)
            self._forbidden.add(spoiled)
            if self._geometry and not self._collides(spoiled):
                # ⛔ The model's whole job is to know this move would overlap BEFORE it is spent.
                # An engine refusal it did not see coming means the decomposition missed a piece,
                # and a model that misses pieces is wrong in both directions — it will also
                # forbid moves that are fine. Two surprises and it is retired in favour of the
                # facts, which are only ever right.
                self._misses += 1
                self._geometry = self._misses < 2
            i, side = key
            self._caps[(i, side, state[:i] + state[i + 1:])] = state[i] + (1 if side == 0 else -1)
            self._state, self._pos = state, pos
            self._path, self._path_at = [], None
            return

        i, side = key
        after = _wind(state, key)
        now = self._read(m, after if i in self._vec else state)
        delta = tuple((a[0] - b[0], a[1] - b[1]) for a, b in zip(now, pos))
        if all(d == (0, 0) for d in delta):
            if not self._readable(m):
                # The frame cannot say what happened and the model cannot say either, because
                # this control has never been characterised. Conclude nothing.
                self._state, self._pos = state, pos
                self._path, self._path_at = [], None
                return
            if _board_same(before, g):
                # Nothing on the board moved at all: this control is at its stop, and that is a
                # bound on the winding rather than a fact about this one action.
                lo, hi = self._bounds.get(i, (-_MAX_WIND, _MAX_WIND))
                self._bounds[i] = (state[i], hi) if side else (lo, state[i])
                self._blocked.add((state, key))
                self._state, self._pos = state, pos
                self._path, self._path_at = [], None
                return
            # The board moved but no marker did. ⛔ That does NOT make the control useless, and
            # it does NOT mean the action was rejected: what it drives is part of the same
            # linkage, the winding really did advance, and moving it is how a control that DOES
            # carry a marker is freed to go further. MEASURED on a board where one control raises
            # the marker and stops after five notches — the four that move no marker at all are
            # what unstick it. Recording a zero vector keeps the control in the plan as a
            # dimension that costs an action and changes what is reachable.
            self._vec.setdefault(i, tuple((0, 0) for _ in pos))
            self._state, self._pos = after, pos
            if probe:
                self._learn_shape(i, side, g)
                self._undo = (i, 1 - side)
            return

        self._state = after
        self._pos = now
        if i not in self._vec:
            self._vec[i] = delta if side == 0 else tuple((-d[0], -d[1]) for d in delta)
        if probe:
            self._learn_shape(i, side, g)
            self._undo = (i, 1 - side)

    def _learn_shape(self, i: int, side: int, g: np.ndarray) -> None:
        """Read off what one notch of this control did to every piece of structure on the board.

        This is the whole difference between a tool that finishes these boards and one that does
        not. What the engine refuses is an OVERLAP, and an overlap is a fact about the shapes, not
        about the marker — so a tool that learns only where the marker went has to buy every
        refusal with an action. MEASURED on one board: of the 156 windings that put the marker on
        its target, exactly TWO are overlap-free, and the shortest route to one of them is 26
        moves. Discovering that by being refused is not a search, it is the budget.

        ⛔ Every probe is taken from the SAME configuration, and the notch is given back before
        the next one. Without that the pieces have to be re-identified across a board that has
        already moved twice, and one mis-pairing writes a law that no linkage has. Giving the
        notch back costs one action per control and makes every reading a difference against the
        board this decomposition was cut from.
        """
        seen = _pair_pieces(self._pieces, self._read_pieces(g))
        turn = 1 if side == 0 else -1
        for bi, p in enumerate(self._pieces):
            box = seen.get(bi)
            if box is None:
                self._unread.add(bi)
                continue
            edge = tuple((b - a) * turn for a, b in zip(p.rect, box))
            if _sane(edge):  # type: ignore[arg-type]
                p.law[i] = edge  # type: ignore[assignment]
            else:
                self._unread.add(bi)

    def _build_geometry(self) -> None:
        """Split the structure into what moves and what does not, and self-test the split.

        The test is not a formality. A control whose probe was refused teaches nothing, so the
        pieces it drives are filed as scenery and the model then forbids the very moves that
        board needs. Checking that the board AS IT STANDS reads as overlap-free catches that,
        and a model that cannot pass its own check is switched off rather than believed.
        """
        known = [p for i, p in enumerate(self._pieces) if i not in self._unread]
        movers = [p for p in known if any(any(d) for d in p.law.values())]
        static = np.zeros((64, 64), dtype=bool)
        for p in known:
            if p in movers:
                continue
            for y, x in p.cells:
                static[y, x] = True
        # A prefix sum over the immovable cells turns "is there scenery inside this box" into
        # four integer lookups. The planner asks it tens of thousands of times per plan, and a
        # numpy slice per ask is what made a plan take longer than the game.
        rows = static.tolist()
        total = [[0] * 65 for _ in range(65)]
        for y in range(64):
            run = 0
            for x in range(64):
                run += 1 if rows[y][x] else 0
                total[y + 1][x + 1] = total[y][x + 1] + run
        self._movers, self._static, self._sum, self._overlap = movers, static, total, {}
        self._geometry = bool(movers) and not self._collides(self._state)
        if not self._geometry:
            self._movers = []
        self._overlap[()] = True

    def _collides(self, counts: tuple[int, ...]) -> bool:
        """Does the structure overlap itself at this winding — the thing the engine refuses."""
        hit = self._overlap.get(counts)
        if hit is not None:
            return hit
        rects = [p.at(counts) for p in self._movers]
        bad = False
        total = self._sum
        for y0, x0, y1, x1 in rects:
            a, b = max(0, y0), min(63, y1)
            c, d = max(0, x0), min(63, x1)
            if a > b or c > d:
                continue
            if total[b + 1][d + 1] - total[a][d + 1] - total[b + 1][c] + total[a][c]:
                bad = True
                break
        if not bad:
            for j, (y0, x0, y1, x1) in enumerate(rects):
                for a0, b0, a1, b1 in rects[j + 1:]:
                    if y0 <= a1 and a0 <= y1 and x0 <= b1 and b0 <= x1:
                        bad = True
                        break
                if bad:
                    break
        self._overlap[counts] = bad
        return bad

    def _reseat(self) -> None:
        """Keep the model's origin on the board the frame is actually showing.

        The winding is a coordinate; the positions are what the frame shows. Re-deriving the
        origin from the two costs nothing and keeps every banked refusal meaningful, because a
        refusal is indexed by the winding and not by the cell.
        """
        if not self._pos:
            return
        units = self._units()
        base = []
        for mi, p in enumerate(self._pos):
            y, x = p
            for i, n in enumerate(self._state):
                if n:
                    y -= n * units[i][mi][0]
                    x -= n * units[i][mi][1]
            base.append((y, x))
        seat = tuple(base)
        if seat != self._base:
            self._base = seat
            self._path, self._path_at = [], None

    def _known(self) -> int:
        """How much this tool has learnt about the board, counted in facts."""
        return (len(self._vec) + len(self._bounds) + len(self._forbidden)
                + len(self._blocked) + len(self._caps))

    def _next_probe(self) -> Key | None:
        """The cheapest unanswered question: what does this control do to the markers?"""
        for i in range(len(self._controls)):
            if i in self._vec:
                continue
            if self._probes.get(i, 0) >= _MAX_PROBES:
                continue
            lo, hi = self._bounds.get(i, (-_MAX_WIND, _MAX_WIND))
            for side in (0, 1):
                if (self._state, (i, side)) in self._blocked:
                    continue
                n = self._state[i] + (1 if side == 0 else -1)
                if not lo <= n <= hi:
                    continue
                if _wind(self._state, (i, side)) in self._forbidden:
                    continue
                return (i, side)
        return None

    def _next_turn(self) -> Cell | None:
        """The next one-way control to fire, or None once they have all been round once."""
        if not self._buttons or self._turns >= 4 * len(self._buttons):
            return None
        return self._buttons[self._turns % len(self._buttons)]
