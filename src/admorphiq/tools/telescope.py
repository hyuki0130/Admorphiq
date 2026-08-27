"""Telescope tool — drive markers onto their sockets by lengthening jointed bars.

The mechanic, stated in frame terms only, recovered from the game's own source and then
re-derived from pixels because a tool may only read pixels:

  * one rare colour carries two kinds of small marker — a LONE CELL that travels and a
    DIAMOND of four cells around an empty centre that is where a lone cell must come to rest;
  * the board is furnished with BARS: solid rectangles three cells across whose far end is
    capped by a three-cell stripe. The stripe is the anchored end; the bar telescopes away
    from it in whole three-cell units and the anchored end never moves;
  * beside the board sit FRAMED WIDGETS, rectangles whose border is exactly the perimeter of
    their own bounding box. A widget cut in half by ONE uniform line that appears nowhere else
    inside it is a two-way control: clicking one half lengthens every bar it owns by one unit,
    clicking the other half shortens them. A widget with no such line is a one-way control and
    RE-AIMS its bars instead of lengthening them;
  * a bar carries whatever hangs off its far end — another bar, a marker, a plain blocker —
    and everything carried is TRANSLATED by exactly the length that was added;
  * a click whose result would make two bars overlap is applied, tested and then UNDONE. The
    budget is still spent. So the expensive thing on these boards is not finding the marker's
    route, it is knowing in advance which routes the furniture forbids.

⛔ That last line is the whole reason this tool exists next to a probing planner. Because the
carried translation is rigid and the growth is a rectangle, EVERY board position at every
winding is a closed-form function of the winding — so the overlap the engine is about to test
can be computed instead of discovered. A planner that learns its walls by walking into them
pays one action per wall out of a budget of fifty to two hundred, and these boards have more
walls than that. This one probes each control ONCE to measure what it moves, and from then on
predicts refusals rather than collecting them.

⛔ SCOPE, DELIBERATELY NARROW. One-way controls re-aim a bar about its anchor, which changes
every carried translation and therefore invalidates the linear model this tool is built on. A
board carrying ANY one-way control gets a bid of exactly zero — not a reduced bid — so the
board stays with a tool that treats re-aiming honestly. Measured: five of this family's eight
boards carry no one-way control, and they are the five this tool claims.

⛔ THE FIRST RENDER AFTER A REFUSED CLICK IS NOT THE BOARD. The engine draws the move, tests
it, and draws the board it put back, handing both renders back inside one observation. Reading
render zero teaches translations no control can produce. The LAST render is the board that now
exists, and an observation carrying more than one render is itself the refusal signal.

⛔ NO CONSOLATION BID. detect() returns zero the moment the model is contradicted by a frame,
and stays zero for that board. A tool that keeps bidding on a board it has stopped
understanding spends a budget that ENDS THE GAME when it runs out.
"""

from __future__ import annotations

import heapq
from collections import Counter, deque
from dataclasses import dataclass, field
from itertools import permutations
from typing import Any

import numpy as np

from admorphiq.tools.base import Step, availability, has_frame, levels_completed

__all__ = [
    "TelescopeArmTool",
    "Widget",
    "Piece",
    "read_widgets",
    "marker_colour",
    "read_markers",
    "read_pieces",
    "indicator_lines",
]

Cell = tuple[int, int]
Vec = tuple[int, int]

# A framed control is furniture beside the board, never the board itself.
_MIN_WIDGET = 5
_MAX_WIDGET = 26
# The travelling markers are a handful; a colour with more of them is painting something.
_MAX_MARKER_CELLS = 60
# A bar telescopes in units of its own width. Derived per board, but a board 64 cells wide
# cannot want more units than this, and the cap keeps the lattice search finite.
_MAX_WIND = 24
# A* refuses to grind. These boards resolve in tens of clicks or the model is wrong.
_MAX_EXPAND = 60_000
# Planning is affordable a few dozen times per level, not once per action forever.
_MAX_PLANS = 40


# --- frame readers -----------------------------------------------------------


def _layers(obs: Any) -> list[np.ndarray]:
    """Every render the engine produced for one action, oldest first.

    A click simply taken renders once. A click the engine tests and UNDOES renders twice — the
    attempt, then the board put back. In both cases the last render is the board that exists.
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


def _background(g: np.ndarray) -> int:
    return int(Counter(int(v) for v in g.ravel()).most_common(1)[0][0])


def indicator_lines(g: np.ndarray) -> tuple[set[int], set[int]]:
    """Edge-pinned rows/columns that read as a gauge rather than as board content.

    ⛔ Masking a fixed margin is not an option here: one board's live bar starts three cells
    from the top edge, so a generous margin deletes the piece the level turns on. A gauge has a
    shape instead of a position — it spans its whole edge and is a run of one colour followed by
    a run of another, which is what a bar that drains looks like at every stage of draining.
    """
    h, w = g.shape
    rows: set[int] = set()
    cols: set[int] = set()
    for r in (0, h - 1):
        if _is_gauge(list(int(v) for v in g[r])):
            rows.add(r)
    for c in (0, w - 1):
        if _is_gauge(list(int(v) for v in g[:, c])):
            cols.add(c)
    return rows, cols


def _is_gauge(line: list[int]) -> bool:
    runs: list[int] = []
    for v in line:
        if not runs or runs[-1] != v:
            runs.append(v)
    return len(runs) <= 2


def _perimeter(y0: int, x0: int, y1: int, x1: int) -> set[Cell]:
    out = {(y0, x) for x in range(x0, x1 + 1)} | {(y1, x) for x in range(x0, x1 + 1)}
    out |= {(y, x0) for y in range(y0, y1 + 1)} | {(y, x1) for y in range(y0, y1 + 1)}
    return out


def _components(mask: np.ndarray) -> list[list[Cell]]:
    h, w = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    out: list[list[Cell]] = []
    for y in range(h):
        for x in range(w):
            if not mask[y, x] or seen[y, x]:
                continue
            seen[y, x] = True
            q: deque[Cell] = deque([(y, x)])
            cells: list[Cell] = []
            while q:
                cy, cx = q.popleft()
                cells.append((cy, cx))
                for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        q.append((ny, nx))
            out.append(cells)
    return out


@dataclass(frozen=True)
class Widget:
    """A framed control beside the board."""

    box: tuple[int, int, int, int]
    two_way: bool
    plus: Cell = (0, 0)
    minus: Cell = (0, 0)


def read_widgets(g: np.ndarray) -> list[Widget]:
    """Every framed rectangle on screen, each labelled two-way or one-way.

    ⛔ The divider is identified by EXCLUSIVITY, not by being a full line. A one-way control is
    drawn as a cross, and the smallest one is five cells square — so its middle row and its
    middle column are BOTH full lines and a "is there a full line" test calls it a slider. A
    real divider's colour appears nowhere else inside the frame; a cross's colour appears in
    both arms. Measured across this family's eight boards, that separates them with no
    reference to the widget's size or shape.
    """
    bg = _background(g)
    out: list[Widget] = []
    for colour in sorted({int(v) for v in g.ravel()} - {bg}):
        for cells in _components(g == colour):
            ys = [c[0] for c in cells]
            xs = [c[1] for c in cells]
            y0, y1, x0, x1 = min(ys), max(ys), min(xs), max(xs)
            h, w = y1 - y0 + 1, x1 - x0 + 1
            if not (_MIN_WIDGET <= h <= _MAX_WIDGET and _MIN_WIDGET <= w <= _MAX_WIDGET):
                continue
            if set(cells) != _perimeter(y0, x0, y1, x1):
                continue
            out.append(_classify_widget(g, y0, x0, y1, x1))
    return out


def _classify_widget(g: np.ndarray, y0: int, x0: int, y1: int, x1: int) -> Widget:
    inner = g[y0 + 1:y1, x0 + 1:x1]
    split = _divider(inner, axis=1)
    if split is not None:
        col = x0 + 1 + split
        mid = (y0 + y1) // 2
        return Widget((y0, x0, y1, x1), True,
                      plus=(mid, (col + x1) // 2), minus=(mid, (x0 + col) // 2))
    split = _divider(inner, axis=0)
    if split is not None:
        row = y0 + 1 + split
        mid = (x0 + x1) // 2
        return Widget((y0, x0, y1, x1), True,
                      plus=((row + y1) // 2, mid), minus=((y0 + row) // 2, mid))
    return Widget((y0, x0, y1, x1), False)


def _divider(inner: np.ndarray, axis: int) -> int | None:
    """Index of the one uniform line whose colour appears nowhere else inside the frame."""
    n = inner.shape[axis]
    if n < 3:
        return None
    found: list[int] = []
    for i in range(1, n - 1):
        line = inner[:, i] if axis == 1 else inner[i, :]
        colour = int(line[0])
        if not all(int(v) == colour for v in line):
            continue
        elsewhere = int((inner == colour).sum()) - len(line)
        if elsewhere == 0:
            found.append(i)
    return found[0] if len(found) == 1 else None


@dataclass(frozen=True)
class Markers:
    colour: int
    movers: tuple[Cell, ...]
    places: tuple[Cell, ...]


def marker_colour(g: np.ndarray, banned: set[int]) -> int | None:
    """The colour that reads as lone cells plus four-cell diamonds, or None."""
    bg = _background(g)
    counts = Counter(int(v) for v in g.ravel())
    best: int | None = None
    for colour, n in counts.items():
        if colour == bg or colour in banned or not (4 <= n <= _MAX_MARKER_CELLS):
            continue
        if read_markers(g, colour) is not None:
            best = colour if best is None else best
    return best


def read_markers(g: np.ndarray, colour: int) -> Markers | None:
    """Split one colour's cells into diamonds (places) and lone cells (movers), or reject it.

    ⛔ A mover is found by SUBTRACTING the diamonds, not by testing isolation. A mover that has
    arrived stops being a lone cell — it becomes the centre of a five-cell plus — so an
    isolation test loses movers exactly when the board is closest to solved.
    """
    h, w = g.shape
    cells = {(int(y), int(x)) for y, x in zip(*np.where(g == colour))}
    if not cells:
        return None
    places: list[Cell] = []
    ring: set[Cell] = set()
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            if all((y + dy, x + dx) in cells for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1))):
                places.append((y, x))
                ring |= {(y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)}
    movers = sorted(cells - ring)
    if not places or not movers:
        return None
    if len(cells) != len(ring) + len(movers):
        return None
    at_place = set(places)
    for y, x in movers:
        if (y, x) in at_place:
            continue
        if any((y + dy, x + dx) in cells for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1))):
            return None
    return Markers(colour, tuple(movers), tuple(sorted(places)))


@dataclass(frozen=True)
class Piece:
    """One rigid lump of board furniture, as it renders at some winding."""

    colour: int
    cells: frozenset[Cell]
    box: tuple[int, int, int, int]
    rect: bool

    def shape(self) -> frozenset[Cell]:
        """The piece's outline with its position taken away — its identity across a step."""
        y0, x0 = self.box[0], self.box[1]
        return frozenset((y - y0, x - x0) for y, x in self.cells)


def _off_board(g: np.ndarray, boxes: list[tuple[int, int, int, int]]) -> np.ndarray:
    """Cells that are furniture rather than board: the widgets and the edge gauge."""
    off = np.zeros(g.shape, dtype=bool)
    rows, cols = indicator_lines(g)
    for r in rows:
        off[r, :] = True
    for c in cols:
        off[:, c] = True
    for y0, x0, y1, x1 in boxes:
        off[y0:y1 + 1, x0:x1 + 1] = True
    return off


def solid_cells(g: np.ndarray, marker: int,
                boxes: list[tuple[int, int, int, int]]) -> tuple[set[Cell], set[Cell]]:
    """(everything that is a bar, everything that is a marker) — the whole live board."""
    bg = _background(g)
    off = _off_board(g, boxes)
    solid = (g != bg) & (g != marker) & ~off
    marks = (g == marker) & ~off
    return ({(int(y), int(x)) for y, x in zip(*np.where(solid))},
            {(int(y), int(x)) for y, x in zip(*np.where(marks))})


def read_pieces(g: np.ndarray, marker: int, boxes: list[tuple[int, int, int, int]]) -> list[Piece]:
    """Every lump of board furniture: same-colour regions outside the widgets and the gauge.

    ⛔ Markers are drawn ON TOP of the bar that carries them, so a bar reads as a rectangle
    with holes punched in it and can even read as two regions. Marker cells are therefore
    passable when deciding what is connected, and a region whose bounding box is solid once its
    marker holes are filled IS that rectangle — which is also what the engine collides with,
    because the sprite underneath was never punctured.
    """
    bg = _background(g)
    off = _off_board(g, boxes)
    marks = (g == marker) & ~off
    out: list[Piece] = []
    for colour in sorted({int(v) for v in g.ravel()} - {bg, marker}):
        own = (g == colour) & ~off
        if not own.any():
            continue
        for cells in _components(own | marks):
            here = [c for c in cells if own[c]]
            if not here:
                continue
            ys = [c[0] for c in here]
            xs = [c[1] for c in here]
            box = (min(ys), min(xs), max(ys), max(xs))
            full = {(y, x) for y in range(box[0], box[2] + 1) for x in range(box[1], box[3] + 1)}
            holes = full - set(here)
            solid = bool(holes) is False or all(marks[c] for c in holes)
            out.append(Piece(colour, frozenset(full if solid else here), box, solid))
    return out


# --- matching one frame's pieces onto the previous frame's ---------------------

# What one control's click did to one piece: a rigid shift, or a rectangle that grew.
_SHIFT = "shift"
_GROW = "grow"


def _match(before: list[Piece], after: list[Piece]
           ) -> tuple[list[tuple[str, Vec]], list[Piece]] | None:
    """How each piece of `before` became a piece of `after`, and `after` PUT BACK IN THAT ORDER.

    Exact-shape pieces are paired first and by nearest, so identical twins cannot swap
    identities across a three-cell step. Whatever is left over must be a rectangle that gained
    or lost length at ONE end, which is the only non-rigid thing these boards do.

    ⛔ The re-ordering is not tidiness. Regions come out of a frame in raster order, so a piece
    that moves changes its own index, and a model keyed on that index quietly re-attaches one
    bar's behaviour to another. MEASURED on the fourth board: two identical three-cell anchors
    forty cells apart swapped places between two probes, and the control that lifts one arm was
    recorded as lifting the other — the planner then had no legal first move at all.
    """
    unused = list(range(len(after)))
    order: list[int | None] = [None] * len(before)
    result: list[tuple[str, Vec] | None] = [None] * len(before)
    by_shape: dict[tuple[int, frozenset[Cell]], list[int]] = {}
    for j in unused:
        by_shape.setdefault((after[j].colour, after[j].shape()), []).append(j)
    for i, b in enumerate(before):
        pool = by_shape.get((b.colour, b.shape()), [])
        pool = [j for j in pool if j in unused]
        if not pool:
            continue
        j = min(pool, key=lambda k: abs(after[k].box[0] - b.box[0]) + abs(after[k].box[1] - b.box[1]))
        unused.remove(j)
        order[i] = j
        result[i] = (_SHIFT, (after[j].box[0] - b.box[0], after[j].box[1] - b.box[1]))
    for i, b in enumerate(before):
        if result[i] is not None:
            continue
        pick = None
        for j in unused:
            a = after[j]
            if a.colour != b.colour or not (a.rect and b.rect):
                continue
            same = [a.box[k] == b.box[k] for k in range(4)]
            if sum(same) != 3:
                continue
            k = same.index(False)
            step = a.box[k] - b.box[k]
            if step == 0:
                continue
            pick = (j, k, step)
            break
        if pick is None:
            return None
        j, k, step = pick
        unused.remove(j)
        order[i] = j
        # ⛔ Report WHICH EDGE moved and by how much, not "it got longer by three". Folding the
        # edge into a signed length loses the anchor, and a bar that telescopes upward is then
        # rebuilt downward — measured, it put every bar on this family's second board through
        # the furniture and made every winding read as a refusal.
        result[i] = (_GROW, (k, step))
    if unused or any(r is None for r in result) or any(o is None for o in order):
        return None
    return ([r for r in result if r is not None],
            [after[o] for o in order if o is not None])


# --- the model ----------------------------------------------------------------


@dataclass
class _Model:
    """Everything the board does, as a linear function of how far each control is wound."""

    pieces: list[Piece]
    movers: list[Cell]
    places: list[Cell]
    shift: dict[tuple[int, int], Vec] = field(default_factory=dict)      # (piece, ctrl) -> per-click shift
    mover_shift: dict[tuple[int, int], Vec] = field(default_factory=dict)
    grow: dict[int, tuple[int, int, int]] = field(default_factory=dict)  # piece -> (ctrl, edge, step)
    lo: list[int] = field(default_factory=list)
    hi: list[int] = field(default_factory=list)

    def mover_at(self, i: int, w: tuple[int, ...]) -> Cell:
        y, x = self.movers[i]
        for c, n in enumerate(w):
            v = self.mover_shift.get((i, c))
            if v and n:
                y += v[0] * n
                x += v[1] * n
        return (y, x)

    def piece_box(self, i: int, w: tuple[int, ...]) -> tuple[int, int, int, int] | None:
        p = self.pieces[i]
        dy = dx = 0
        for c, n in enumerate(w):
            v = self.shift.get((i, c))
            if v and n:
                dy += v[0] * n
                dx += v[1] * n
        box = [p.box[0] + dy, p.box[1] + dx, p.box[2] + dy, p.box[3] + dx]
        g = self.grow.get(i)
        if g is not None:
            c, edge, step = g
            box[edge] += step * w[c]
            if box[2] - box[0] < 1 or box[3] - box[1] < 1:
                return None
        return (box[0], box[1], box[2], box[3])

    def piece_cells(self, i: int, w: tuple[int, ...]) -> frozenset[Cell] | None:
        p = self.pieces[i]
        box = self.piece_box(i, w)
        if box is None:
            return None
        if p.rect or self.grow.get(i) is not None:
            y0, x0, y1, x1 = box
            return frozenset((y, x) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1))
        dy, dx = box[0] - p.box[0], box[1] - p.box[1]
        return frozenset((y + dy, x + dx) for y, x in p.cells)


def _static(model: _Model) -> set[int]:
    moving = set(model.grow)
    for (i, _c) in model.shift:
        moving.add(i)
    return {i for i in range(len(model.pieces)) if i not in moving}


class _Board:
    """Occupancy at an arbitrary winding, with the immovable furniture precomputed once.

    ⛔ Built out of RECTANGLES, not cell sets. The route search asks this question tens of
    thousands of times per level and a bar is a rectangle by construction — comparing corners
    instead of building two hundred cells per piece is what makes the search finish inside the
    turn rather than inside the level.
    """

    _PAD = 72

    def __init__(self, model: _Model) -> None:
        self.model = model
        fixed = _static(model)
        n = 2 * self._PAD + 64
        self.wall = np.zeros((n, n), dtype=bool)
        for i in fixed:
            for y, x in model.pieces[i].cells:
                if -self._PAD <= y < n - self._PAD and -self._PAD <= x < n - self._PAD:
                    self.wall[y + self._PAD, x + self._PAD] = True
        self.loose = [i for i in range(len(model.pieces)) if i not in fixed]
        self._cache: dict[tuple[int, ...], bool] = {}

    def legal(self, w: tuple[int, ...]) -> bool:
        hit = self._cache.get(w)
        if hit is not None:
            return hit
        ok = True
        boxes: list[tuple[int, int, int, int]] = []
        odd: list[frozenset[Cell]] = []
        for i in self.loose:
            piece = self.model.pieces[i]
            if piece.rect:
                box = self.model.piece_box(i, w)
                if box is None or self._walled(box):
                    ok = False
                    break
                if any(_overlap(box, other) for other in boxes):
                    ok = False
                    break
                boxes.append(box)
            else:
                cells = self.model.piece_cells(i, w)
                if cells is None or any(self._walled((y, x, y, x)) for y, x in cells):
                    ok = False
                    break
                odd.append(cells)
        if ok and odd:
            seen: set[Cell] = set()
            for cells in odd:
                if seen & cells:
                    ok = False
                    break
                seen |= cells
            if ok:
                for box in boxes:
                    for y in range(box[0], box[2] + 1):
                        if any((y, x) in seen for x in range(box[1], box[3] + 1)):
                            ok = False
                            break
                    if not ok:
                        break
        self._cache[w] = ok
        return ok

    def _walled(self, box: tuple[int, int, int, int]) -> bool:
        p = self._PAD
        y0, x0, y1, x1 = box
        if y1 + p < 0 or x1 + p < 0 or y0 + p >= self.wall.shape[0] or x0 + p >= self.wall.shape[1]:
            return False
        return bool(self.wall[max(0, y0 + p):y1 + p + 1, max(0, x0 + p):x1 + p + 1].any())


def _overlap(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


# --- planning ------------------------------------------------------------------

# How far a single drive is allowed to reach, and how deep the route search will go.
_MAX_DRIVE = 30
_MAX_DEPTH = 12
_MAX_DRIVES = 120_000
_MAX_EXPAND = 40_000


def _solved(model: _Model, w: tuple[int, ...]) -> bool:
    here = {model.mover_at(i, w) for i in range(len(model.movers))}
    return all(p in here for p in model.places)


def _carriers(model: _Model, i: int) -> frozenset[int]:
    return frozenset(c for (m, c) in model.mover_shift if m == i)


def _heuristic(model: _Model, w: tuple[int, ...], unit: int) -> int:
    """Clicks that must still happen, never more than the truth.

    One click shifts a marker by at most one unit along one axis, so a marker's own remaining
    L1 distance in units is a floor for it. The floors ADD only when no single control drives
    two markers at once — which the model can say — and otherwise only the largest is safe.
    """
    if not model.places:
        return 0
    pos = [model.mover_at(i, w) for i in range(len(model.movers))]
    best: int | None = None
    for pick in permutations(range(len(pos)), len(model.places)):
        costs = [(abs(p[0] - pos[m][0]) + abs(p[1] - pos[m][1]) + unit - 1) // unit
                 for p, m in zip(model.places, pick)]
        sets = [_carriers(model, m) for m in pick]
        disjoint = all(not (a & b) for k, a in enumerate(sets) for b in sets[k + 1:])
        total = sum(costs) if disjoint else (max(costs) if costs else 0)
        best = total if best is None else min(best, total)
    return best or 0


def plan(model: _Model, board: _Board, start: tuple[int, ...], unit: int,
         blocked: set[tuple[int, ...]]) -> list[tuple[int, int]] | None:
    """Shortest legal sequence of single clicks from `start` to a solved board, or None.

    Optimal, and the right answer whenever the winding lattice is small enough to walk. It
    stops being the right answer as soon as most of the lattice's axes move no marker at all:
    the estimate says nothing about them and the search spreads across a plateau. `route_plan`
    takes over there.
    """
    if _solved(model, start):
        return []
    n = len(start)
    seen = {start: 0}
    came: dict[tuple[int, ...], tuple[tuple[int, ...], tuple[int, int]]] = {}
    heap = [(_heuristic(model, start, unit), 0, start)]
    expand = 0
    while heap:
        _f, cost, node = heapq.heappop(heap)
        if cost > seen.get(node, 1 << 30):
            continue
        if _solved(model, node):
            out: list[tuple[int, int]] = []
            cur = node
            while cur != start:
                cur, mv = came[cur]
                out.append(mv)
            return out[::-1]
        expand += 1
        if expand > _MAX_EXPAND:
            return None
        for c in range(n):
            for d in (1, -1):
                nxt = list(node)
                nxt[c] += d
                if not (model.lo[c] <= nxt[c] <= model.hi[c]):
                    continue
                key = tuple(nxt)
                if key in blocked or not board.legal(key):
                    continue
                if cost + 1 >= seen.get(key, 1 << 30):
                    continue
                seen[key] = cost + 1
                came[key] = (node, (c, d))
                heapq.heappush(heap, (cost + 1 + _heuristic(model, key, unit), cost + 1, key))
    return None


# --- route search: drive a control, and move whatever stands in its way ---------


def _driven(model: _Model, ctrl: int) -> list[int]:
    """Every piece this control moves or lengthens."""
    out = {i for (i, c) in model.shift if c == ctrl}
    out |= {i for i, (c, _e, _s) in model.grow.items() if c == ctrl}
    return sorted(out)


def _drive(model: _Model, board: _Board, w: list[int], ctrl: int, goal: int,
           blocked: set[tuple[int, ...]]) -> list[tuple[int, int]]:
    """As many single clicks toward `goal` as the board actually allows — possibly none."""
    out: list[tuple[int, int]] = []
    d = 1 if goal > w[ctrl] else -1
    cur = list(w)
    for _ in range(_MAX_DRIVE):
        if cur[ctrl] == goal:
            break
        nxt = list(cur)
        nxt[ctrl] += d
        if not (model.lo[ctrl] <= nxt[ctrl] <= model.hi[ctrl]):
            break
        key = tuple(nxt)
        if key in blocked or not board.legal(key):
            break
        cur = nxt
        out.append((ctrl, d))
    return out


def _jam(model: _Model, board: _Board, w: list[int], ctrl: int, goal: int) -> list[int]:
    """The pieces that stop a drive, read off the first winding the board refuses.

    ⛔ Found by ASKING THE BOARD, not by sweeping the control's own pieces and looking for
    strangers in the way. On one of these boards a single control lengthens five bars at once
    and what stops it is two of its OWN bars meeting each other — a stranger-only test sees
    nothing in the way, reports the drive as clear, and the planner walks into the same wall
    every time it is asked.
    """
    d = 1 if goal > w[ctrl] else -1
    cur = list(w)
    for _ in range(_MAX_DRIVE):
        if cur[ctrl] == goal:
            return []
        nxt = list(cur)
        nxt[ctrl] += d
        if not (model.lo[ctrl] <= nxt[ctrl] <= model.hi[ctrl]):
            return []
        key = tuple(nxt)
        if not board.legal(key):
            return _clashing(model, key)
        cur = nxt
    return []


def _clashing(model: _Model, w: tuple[int, ...]) -> list[int]:
    """Which pieces are on top of each other at this winding."""
    boxes: list[tuple[int, tuple[int, int, int, int]]] = []
    hit: set[int] = set()
    for i in range(len(model.pieces)):
        box = model.piece_box(i, w)
        if box is None:
            hit.add(i)
            continue
        for j, other in boxes:
            if _overlap(box, other) and _cells_meet(model, i, j, w):
                hit.add(i)
                hit.add(j)
        boxes.append((i, box))
    return sorted(hit)


def _cells_meet(model: _Model, i: int, j: int, w: tuple[int, ...]) -> bool:
    a, b = model.pieces[i], model.pieces[j]
    if a.rect and b.rect:
        return True
    ca, cb = model.piece_cells(i, w), model.piece_cells(j, w)
    return bool(ca and cb and (ca & cb))


def _handles(model: _Model, piece: int) -> list[int]:
    """Every control that can move this piece at all."""
    out = {c for (i, c) in model.shift if i == piece}
    g = model.grow.get(piece)
    if g is not None:
        out.add(g[0])
    return sorted(out)


def _clashing_pairs(model: _Model, w: tuple[int, ...]) -> list[tuple[int, int]]:
    """Which pieces are on top of which, at this winding."""
    boxes: list[tuple[int, tuple[int, int, int, int]]] = []
    out: list[tuple[int, int]] = []
    for i in range(len(model.pieces)):
        box = model.piece_box(i, w)
        if box is None:
            continue
        for j, other in boxes:
            if _overlap(box, other) and _cells_meet(model, i, j, w):
                out.append((j, i))
        boxes.append((i, box))
    return out


def _choices(model: _Model, board: _Board, w: tuple[int, ...],
             want: dict[int, int]) -> list[tuple[int, int]]:
    """Every control-and-winding worth trying next, best first.

    ⛔ A jammed drive has TWO cures and a planner that knows only one deadlocks. Either the
    thing in the way moves, or the drive's own bar moves — a bar that cannot cross a wall at
    this height crosses it at another. Both come out of the same question, asked at the exact
    winding the board refused: which two pieces are on top of each other there, and what is the
    nearest setting of any control touching either of them that pulls them apart.

    ⛔ The candidate is kept for pulling the pair apart, NOT for making the jammed drive longer
    straight away. Requiring immediate progress looks disciplined and deadlocks: on the third
    board every single cure leaves the drive exactly where it was, and the one that works only
    pays off three moves later.
    """
    out: list[tuple[int, int]] = []
    for c, target in sorted(want.items()):
        if w[c] == target:
            continue
        steps = _drive(model, board, list(w), c, target, set())
        stop = list(w)
        for cc, dd in steps:
            stop[cc] += dd
        if stop[c] == target:
            out.append((c, target))
            continue
        stop[c] += 1 if target > w[c] else -1
        if not (model.lo[c] <= stop[c] <= model.hi[c]):
            continue
        jam = tuple(stop)
        for i, j in _clashing_pairs(model, jam):
            for piece in (i, j):
                for c2 in _handles(model, piece):
                    if c2 == c:
                        continue
                    kept = 0
                    for reach in range(1, _MAX_DRIVE + 1):
                        if kept >= 2:
                            break
                        for v in (w[c2] + reach, w[c2] - reach):
                            if not (model.lo[c2] <= v <= model.hi[c2]):
                                continue
                            trial = list(jam)
                            trial[c2] = v
                            key = tuple(trial)
                            bi, bj = model.piece_box(i, key), model.piece_box(j, key)
                            if bi is None or bj is None or _overlap(bi, bj):
                                continue
                            out.append((c2, v))
                            kept += 1
                            break
        out.append((c, target))
    for c in range(len(w)):
        if w[c] != model.lo[c]:
            out.append((c, model.lo[c]))
    seen: set[tuple[int, int]] = set()
    return [o for o in out if not (o in seen or seen.add(o))]


def route_plan(model: _Model, board: _Board, start: tuple[int, ...], unit: int,
               blocked: set[tuple[int, ...]]) -> list[tuple[int, int]] | None:
    """Plan by driving controls toward what the markers need and unjamming what stops them.

    ⛔ Why this exists next to the A*. The lattice has one axis per control and the boards that
    matter carry six, of which two move a marker — so the marker-distance estimate says nothing
    about the other four and an optimal search spreads across a plateau it cannot cross. This
    searches over WHOLE DRIVES instead of single clicks: seven drives solve the board that
    forty thousand single-click expansions could not reach.
    """
    # ⛔ Remember HOW MUCH DEPTH was left when a winding was first reached, not merely that it
    # was reached. A plain visited set plus a depth limit is not a smaller search, it is a
    # WRONGER one: a state first met at the bottom of one branch is then unreachable from the
    # top of another, and the third board's answer sits behind exactly that.
    seen: dict[tuple[int, ...], int] = {start: _MAX_DEPTH}
    budget = [_MAX_DRIVES]

    def walk(w: tuple[int, ...], depth: int) -> list[tuple[int, int]] | None:
        if _solved(model, w):
            return []
        if depth <= 0 or budget[0] <= 0:
            return None
        want = _targets(model, w, unit)
        if not want:
            return None
        for c, v in _choices(model, board, w, want):
            budget[0] -= 1
            if budget[0] <= 0:
                return None
            step = _drive(model, board, list(w), c, v, blocked)
            if not step:
                continue
            nxt = list(w)
            for cc, dd in step:
                nxt[cc] += dd
            key = tuple(nxt)
            if seen.get(key, -1) >= depth - 1:
                continue
            seen[key] = depth - 1
            rest = walk(key, depth - 1)
            if rest is not None:
                return step + rest
        return None

    return walk(start, _MAX_DEPTH)


def _assign(model: _Model, w: tuple[int, ...]) -> list[tuple[int, int]] | None:
    """Which marker is meant for which socket — the cheapest pairing, or None if none fits."""
    if len(model.movers) < len(model.places):
        return None
    pos = [model.mover_at(i, w) for i in range(len(model.movers))]
    best: tuple[int, list[tuple[int, int]]] | None = None
    for pick in permutations(range(len(pos)), len(model.places)):
        cost = sum(abs(p[0] - pos[m][0]) + abs(p[1] - pos[m][1])
                   for p, m in zip(model.places, pick))
        if best is None or cost < best[0]:
            best = (cost, list(zip(range(len(model.places)), pick)))
    return best[1] if best else None


def _targets(model: _Model, w: tuple[int, ...], unit: int) -> dict[int, int] | None:
    """Where every control has to end up for the markers to be home.

    A marker driven along one axis by exactly one control fixes that control outright. A marker
    two controls can drive along the same axis is under-determined, and the whole remaining
    distance is put on the first of them — an arbitrary choice, but a legal one, and the route
    search is free to find it cannot be walked and say so rather than guess again.
    """
    pair = _assign(model, w)
    if pair is None:
        return None
    want: dict[int, int] = {}
    for place_i, mover_i in pair:
        here = model.mover_at(mover_i, w)
        goal = model.places[place_i]
        for axis in (0, 1):
            gap = goal[axis] - here[axis]
            if gap == 0:
                continue
            drivers = [c for c in range(len(w))
                       if model.mover_shift.get((mover_i, c), (0, 0))[axis]]
            if not drivers:
                return None
            c = drivers[0]
            step = model.mover_shift[(mover_i, c)][axis]
            if gap % step:
                return None
            value = w[c] + gap // step
            if want.get(c, value) != value:
                return None
            want[c] = value
    return want


# --- the tool -----------------------------------------------------------------


class TelescopeArmTool:
    """Harness tool wrapping the telescoping-bar mechanic."""

    name = "telescope"

    def __init__(self) -> None:
        self._level: int | None = None
        self.reset()

    # -- lifecycle ---------------------------------------------------------

    def reset(self) -> None:
        self._model: _Model | None = None
        self._board: _Board | None = None
        self._controls: list[Widget] = []
        self._marker: int | None = None
        self._pieces: list[Piece] = []
        self._w: list[int] = []
        self._probe = 0
        self._tries: list[int] = []
        self._pending: tuple[int, int, bool] | None = None
        self._sig: int | None = None
        self._plan: list[tuple[int, int]] = []
        self._blocked: set[tuple[int, ...]] = set()
        self._plans = 0
        self._unit = 3
        self._dead = False

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """Stateless here: every transition is read off the frames inside propose()."""

    # -- bidding -----------------------------------------------------------

    def detect(self, frames: list[Any], obs: Any) -> float:
        """0.95 for a board of telescoping bars with somewhere left to send a marker, else 0.0.

        ⛔ NO middle ground. Everything below is a conjunction the mechanic cannot do without:
        clicks are the only input, every framed widget is two-way (a one-way one re-aims bars
        and breaks the linear model), and one colour reads cleanly as diamonds plus lone cells
        with at least one diamond still empty. A tool that softens any of these bids on a board
        it cannot plan, and takes the turn from the tool that could.
        """
        if self._dead or not has_frame(obs):
            return 0.0
        simple, action6 = availability(obs)
        if simple or not action6:
            return 0.0
        layers = _layers(obs)
        if not layers:
            return 0.0
        g = layers[-1]
        widgets = read_widgets(g)
        two = [wd for wd in widgets if wd.two_way]
        if not two or len(two) != len(widgets):
            return 0.0
        colour = marker_colour(g, _widget_colours(g, widgets))
        if colour is None:
            return 0.0
        m = read_markers(g, colour)
        if m is None or all(p in set(m.movers) for p in m.places):
            return 0.0
        return 0.95

    # -- acting ------------------------------------------------------------

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        if self._dead or not has_frame(obs):
            return []
        layers = _layers(obs)
        if not layers:
            return []
        g = layers[-1]
        level = levels_completed(obs)
        if level != self._level:
            self._level = level
            self.reset()
        if self._model is None:
            if not self._begin(g):
                self._dead = True
                return []
        elif self._pending is not None and not self._resolve(g, len(layers) > 1):
            self._dead = True
            return []
        return self._next()

    # -- building the model ------------------------------------------------

    def _begin(self, g: np.ndarray) -> bool:
        widgets = read_widgets(g)
        self._controls = [wd for wd in widgets if wd.two_way]
        if not self._controls or len(self._controls) != len(widgets):
            return False
        self._marker = marker_colour(g, _widget_colours(g, widgets))
        if self._marker is None:
            return False
        m = read_markers(g, self._marker)
        if m is None:
            return False
        self._pieces = read_pieces(g, self._marker, [wd.box for wd in self._controls])
        if not self._pieces:
            return False
        self._model = _Model(list(self._pieces), list(m.movers), list(m.places))
        self._w = [0] * len(self._controls)
        self._tries = [0] * len(self._controls)
        self._sig = self._stamp(g)
        return True

    def _stamp(self, g: np.ndarray) -> int:
        """A hash of the BOARD, with the gauge left out — it advances on every action."""
        rows, cols = indicator_lines(g)
        keep = np.ones(g.shape, dtype=bool)
        for r in rows:
            keep[r, :] = False
        for c in cols:
            keep[:, c] = False
        return hash(g[keep].tobytes())

    def _resolve(self, g: np.ndarray, refused: bool) -> bool:
        """Fold the result of the click just taken into the model. False means give up."""
        model = self._model
        assert model is not None and self._pending is not None
        ctrl, delta, learning = self._pending
        self._pending = None
        stamp = self._stamp(g)
        if refused or stamp == self._sig:
            want = list(self._w)
            want[ctrl] += delta
            self._blocked.add(tuple(want))
            self._plan = []
            return True
        marks = read_markers(g, self._marker or 0)
        if marks is None or len(marks.movers) != len(model.movers):
            return False
        if learning:
            seen = read_pieces(g, self._marker or 0, [wd.box for wd in self._controls])
            paired = _match(self._pieces, seen)
            if paired is None or not self._learn(ctrl, delta, paired[0], marks):
                return False
            self._pieces = paired[1]
            self._w[ctrl] += delta
            self._sig = stamp
            return True
        self._w[ctrl] += delta
        self._sig = stamp
        return self._agrees(g, marks)

    def _learn(self, ctrl: int, delta: int, moved: list[tuple[str, Vec]], marks: Markers) -> bool:
        """One probe of one control IS the model for that control.

        Nothing is assumed about which half of a control lengthens: the half clicked defines
        which way the winding counts, and the other half is its inverse.
        """
        model = self._model
        assert model is not None
        for i, (kind, vec) in enumerate(moved):
            if kind == _SHIFT:
                if vec != (0, 0):
                    model.shift[(i, ctrl)] = (vec[0] // delta, vec[1] // delta)
            else:
                edge, step = vec
                model.grow[i] = (ctrl, edge, step // delta)
        for i, m in enumerate(model.movers):
            here = model.mover_at(i, tuple(self._w))
            near = min(marks.movers, key=lambda q: abs(q[0] - here[0]) + abs(q[1] - here[1]))
            v = ((near[0] - here[0]) // delta, (near[1] - here[1]) // delta)
            if v != (0, 0):
                model.mover_shift[(i, ctrl)] = v
        return True

    def _agrees(self, g: np.ndarray, marks: Markers) -> bool:
        """The model must keep predicting the whole board, or this tool stops betting the budget.

        ⛔ Checked against the MODEL, never by segmenting the frame again. Two bars of the same
        colour that come to rest edge to edge read as one region, and a planner that re-derives
        its pieces every action loses one the moment its own plan parks them together —
        measured on the third board, at the first click of a plan that was correct.
        """
        model = self._model
        assert model is not None
        w = tuple(self._w)
        if {model.mover_at(i, w) for i in range(len(model.movers))} != set(marks.movers):
            return False
        boxes = [wd.box for wd in self._controls]
        hidden = _off_board(g, boxes)
        want: set[Cell] = set()
        for i in range(len(model.pieces)):
            cells = model.piece_cells(i, w)
            if cells is None:
                return False
            want |= {c for c in cells
                     if 0 <= c[0] < g.shape[0] and 0 <= c[1] < g.shape[1] and not hidden[c]}
        seen, marked = solid_cells(g, self._marker or 0, boxes)
        return seen <= want and (want - seen) <= marked

    # -- choosing the next click -------------------------------------------

    def _next(self) -> list[Step]:
        model = self._model
        assert model is not None
        while self._probe < len(self._controls):
            ctrl = self._probe
            if self._probed(ctrl) or self._tries[ctrl] >= 2:
                self._probe += 1
                continue
            delta = 1 if self._tries[ctrl] == 0 else -1
            self._tries[ctrl] += 1
            self._pending = (ctrl, delta, True)
            return [self._click(ctrl, delta)]
        if any(not self._probed(c) for c in range(len(self._controls))):
            self._dead = True                  # a control that answers nothing is not a model
            return []
        if self._board is None:
            self._bounds()
            self._board = _Board(model)
        if not self._plan:
            if self._plans >= _MAX_PLANS:
                self._dead = True
                return []
            self._plans += 1
            here = tuple(self._w)
            found = plan(model, self._board, here, self._unit, self._blocked)
            if found is None:
                found = route_plan(model, self._board, here, self._unit, self._blocked)
            if not found:
                self._dead = True
                return []
            self._plan = found
        ctrl, delta = self._plan.pop(0)
        self._pending = (ctrl, delta, False)
        return [self._click(ctrl, delta)]

    def _click(self, ctrl: int, delta: int) -> Step:
        wd = self._controls[ctrl]
        y, x = wd.plus if delta > 0 else wd.minus
        return (6, (x, y))

    def _probed(self, ctrl: int) -> bool:
        model = self._model
        assert model is not None
        return any(c == ctrl for (_i, c) in model.shift) \
            or any(c == ctrl for (c, _e, _s) in model.grow.values()) \
            or any(c == ctrl for (_i, c) in model.mover_shift)

    def _bounds(self) -> None:
        """How far a control may be wound back before one of its bars is shorter than a unit."""
        model = self._model
        assert model is not None
        steps = [abs(s) for (_c, _e, s) in model.grow.values()]
        self._unit = max(1, min(steps)) if steps else 3
        model.lo = [-_MAX_WIND] * len(self._controls)
        model.hi = [_MAX_WIND] * len(self._controls)
        for i, (ctrl, edge, step) in model.grow.items():
            box = model.pieces[i].box
            length = (box[2] - box[0] + 1) if edge in (0, 2) else (box[3] - box[1] + 1)
            # A low edge moving negatively lengthens the bar; a high edge moving positively does.
            outward = -step if edge in (0, 1) else step
            room = (length - self._unit + 1) // abs(outward)
            if outward > 0:
                model.lo[ctrl] = max(model.lo[ctrl], -room)
            else:
                model.hi[ctrl] = min(model.hi[ctrl], room)


def _widget_colours(g: np.ndarray, widgets: list[Widget]) -> set[int]:
    """Every colour a widget is drawn in — none of them is the marker colour."""
    out: set[int] = set()
    for wd in widgets:
        y0, x0, y1, x1 = wd.box
        out |= {int(v) for v in g[y0:y1 + 1, x0:x1 + 1].ravel()}
    return out
