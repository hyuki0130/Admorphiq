"""Reach a ring marker with a dot marker by driving framed two-way controls.

The mechanic this recovers, stated in frame terms only. A board carries two kinds of small
marker in one rare colour: a LONE CELL (the thing that moves) and a DIAMOND of four cells
around an empty centre (the place it must reach). Elsewhere sit framed widgets — a rectangle
whose border is exactly the perimeter of its own bounding box — and a widget split by a single
line down its middle is a TWO-WAY control: clicking one side of the line translates some
subset of the lone cells by a fixed vector, clicking the other side translates them back. The
level is won when every diamond has a marker cell at its centre.

Nothing about which control moves which marker is assumed. Each control is probed once, the
observed displacement IS the model, and the plan is an A* over the joint marker positions using
those learnt vectors. When an action produces no displacement — the arm it drives is at its
limit, or the move would collide — that (position, action) pair is banked as blocked and the
plan is recomputed from where the board actually is, so a wrong model costs one action.

⛔ Why the model is learnt rather than read off the glyphs. The widget's two halves carry
different pictograms and it is tempting to call the right-hand one "grow". Which half grows is
not the useful question: the useful quantity is the SIGNED VECTOR a click applies to a specific
marker, and that depends on the orientation of a linkage the frame does not show. One probe per
control answers it exactly; reading the pictogram answers a question we do not need.

⛔ Why a mover is found by SUBTRACTING the rings rather than by isolation. A mover that comes to
rest on its ring stops being a lone cell — it becomes the centre of a five-cell plus — and a
mover that merely passes next to a ring stops being lone for one frame. Counting isolated cells
therefore loses movers exactly when the board is closest to solved. Ring cells are identified
first and every remaining marker cell is a mover, which survives both cases.
"""

from __future__ import annotations

import heapq
import math
from itertools import permutations
from typing import Any

import numpy as np

from admorphiq.tools import segment
from admorphiq.tools.base import Step, availability, frame_2d, has_frame

__all__ = ["LinkageReachTool", "Markers", "marker_colour", "read_markers", "read_controls"]

Cell = tuple[int, int]

# A framed control is furniture, not the board: everything found is small.
_MAX_WIDGET = 24
_MIN_WIDGET = 4
# Boards in this family carry a handful of markers; a colour with more is painting something.
_MAX_MARKERS = 12
# A* refuses to grind: these boards resolve in tens of clicks or the model is wrong.
_MAX_EXPAND = 60_000
_MAX_DEPTH = 64
_UNREACHABLE = 1 << 20


# --- perception --------------------------------------------------------------


class Markers:
    """What one colour's cells say: where the places are, and what is on the move."""

    __slots__ = ("movers", "places", "occupied", "sound")

    def __init__(self, movers: list[Cell], places: list[Cell], occupied: list[Cell], sound: bool) -> None:
        self.movers = movers
        self.places = places
        self.occupied = occupied
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
    return Markers(sorted(movers + occupied), sorted(places), sorted(occupied), sound)


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


def _divider(box: np.ndarray) -> tuple[str, int] | None:
    """The middle line that splits a widget in two, or None if the widget is one-way.

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
        return axis, mid
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
                found.append({"box": (y0, x0, y1, x1), "clicks": [(x0 + w // 2, y0 + h // 2)]})
                continue
            axis, mid = split
            if axis == "v":
                cy = y0 + h // 2
                clicks = [(x0 + mid + 1, cy), (x0 + mid - 1, cy)]
            else:
                cx = x0 + w // 2
                clicks = [(cx, y0 + mid + 1), (cx, y0 + mid - 1)]
            found.append({"box": (y0, x0, y1, x1), "clicks": clicks})
    return found


# --- planning ----------------------------------------------------------------


def _assign_cost(pos: tuple[Cell, ...], goals: tuple[Cell, ...]) -> int:
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


def _plan(
    start: tuple[Cell, ...],
    goals: tuple[Cell, ...],
    moves: list[tuple[tuple[int, int], tuple[Cell, ...]]],
    blocked: set[tuple[tuple[Cell, ...], tuple[int, int]]],
) -> list[tuple[int, int]] | None:
    """A* over the joint marker positions under the learnt translations."""
    if not moves or not goals:
        return None
    step = max(1, max(abs(d[0]) + abs(d[1]) for _, vec in moves for d in vec))
    seen: dict[tuple[Cell, ...], int] = {start: 0}
    heap = [(_assign_cost(start, goals) // step, 0, start, ())]
    expanded = 0
    while heap and expanded < _MAX_EXPAND:
        _, g_cost, pos, path = heapq.heappop(heap)
        if _assign_cost(pos, goals) == 0:
            return list(path)
        if g_cost > seen.get(pos, _UNREACHABLE) or g_cost >= _MAX_DEPTH:
            continue
        expanded += 1
        for key, vec in moves:
            if (pos, key) in blocked:
                continue
            nxt = tuple((p[0] + d[0], p[1] + d[1]) for p, d in zip(pos, vec))
            if any(not (0 <= a < 64 and 0 <= b < 64) for a, b in nxt):
                continue
            ng = g_cost + 1
            if ng >= seen.get(nxt, _UNREACHABLE):
                continue
            seen[nxt] = ng
            heapq.heappush(heap, (ng + _assign_cost(nxt, goals) // step, ng, nxt, path + (key,)))
    return None


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




def _shift(pos: tuple[Cell, ...], vec: tuple[Cell, ...]) -> tuple[Cell, ...]:
    return tuple((p[0] + d[0], p[1] + d[1]) for p, d in zip(pos, vec))


def _unshift(pos: tuple[Cell, ...], vec: tuple[Cell, ...]) -> tuple[Cell, ...]:
    return tuple((p[0] - d[0], p[1] - d[1]) for p, d in zip(pos, vec))


# --- the tool ----------------------------------------------------------------


class LinkageReachTool:
    """Probe each framed control once, then plan the markers onto their rings.

    ⛔ THE FRAME AFTER A REFUSED MOVE IS A LIE, and everything below is shaped by it. MEASURED on
    a live board: a click whose move would overlap a wall is applied, tested, and undone inside
    one action — but the frame handed back was rendered BEFORE the undo, so it shows the marker
    three cells INSIDE the wall while the engine's own sprite sits where it started. Two such
    frames in a row are identical, so "did the board change" cannot see it either; a model built
    by differencing consecutive frames therefore learns diagonal displacements that no single
    control can produce, and that is what a first version of this tool learnt.

    The algebra that recovers from it needs no extra actions. Every frame satisfies
    ``frame(k) = truth(k-1) + delta(k)`` whether the move was kept or refused, so the frame after
    the NEXT action pins the truth exactly: ``truth(k) = frame(k+1) - delta(k+1)``. Acceptance is
    therefore known one action late, at no cost — and if that arithmetic lands on neither of the
    two states it must be, one click on empty background (delta zero) renders the truth outright.
    """

    name = "linkage"

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._controls: list[dict[str, Any]] = []
        self._colour: int | None = None
        self._places: tuple[Cell, ...] = ()
        self._truth: tuple[Cell, ...] | None = None
        self._shown: tuple[Cell, ...] = ()
        self._queue: list[tuple[tuple[Cell, ...], tuple[int, int], tuple[Cell, ...] | None]] = []
        self._delta: dict[tuple[int, int], tuple[Cell, ...]] = {}
        self._inert: set[tuple[int, int]] = set()
        self._blocked: set[tuple[tuple[Cell, ...], tuple[int, int]]] = set()
        self._path: list[tuple[int, int]] = []
        self._path_at: tuple[Cell, ...] | None = None
        self._null: Cell = (0, 0)
        self._resyncing = False
        self._resyncs = 0
        self._idle = 0

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """No-op: every transition is read back off the frame in ``propose``."""

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
        g = np.asarray(frame_2d(obs))
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
        g = np.asarray(frame_2d(obs))
        colour = self._colour if self._colour is not None else marker_colour(g)
        if colour is None:
            return []
        m = read_markers(g, colour)
        places = tuple(m.places)
        if places != self._places or self._truth is None:
            self._start(g, colour, places, m)
        if not places:
            return []

        shown = _rematch(list(self._shown), sorted(m.movers))
        if len(shown) != len(self._places):
            # A marker is momentarily unreadable (a mover passing alongside a ring). One click
            # on empty background re-renders the board without changing it.
            return [(6, self._null)]
        self._shown = tuple(shown)

        if self._resyncing:
            # The click just taken moved nothing, so this frame IS the board. Start clean.
            self._resyncing = False
            self._queue = []
            self._truth = self._shown
        elif not self._absorb(self._shown):
            return self._resync()

        here = self._believed()
        if not set(places) - set(here):
            # The board is solved; the frame shown after a level-up is still the old one, so one
            # harmless click is what advances it. Proposing nothing is what stalls the game here.
            self._idle += 1
            return [] if self._idle > 2 else [(6, self._null)]
        self._idle = 0

        probe = self._next_probe()
        if probe is not None:
            key, xy = probe
            self._queue.append((here, key, None))
            return [(6, xy)]

        if self._path_at != here:
            # ⛔ Replanning every action makes the tool oscillate. The state it plans from is the
            # optimistic one, so a move whose acceptance is still unknown looks taken, the next
            # plan starts by undoing it, and the pair cancels. Following one committed path until
            # the board contradicts it removes that entirely.
            moves = [(k, v) for k, v in self._delta.items() if any(d != (0, 0) for d in v)]
            self._path = _plan(here, places, moves, self._blocked) or []
        if not self._path:
            self._path_at = None
            return []
        key = self._path.pop(0)
        self._path_at = _shift(here, self._delta[key])
        self._queue.append((here, key, self._delta[key]))
        return [(6, self._controls[key[0]]["clicks"][key[1]])]

    # -- state keeping -------------------------------------------------------

    def _start(self, g: np.ndarray, colour: int, places: tuple[Cell, ...], m: Markers) -> None:
        """A different set of places means a different board: everything learnt is stale."""
        self.reset()
        self._colour = colour
        self._places = places
        self._controls = read_controls(g)
        self._truth = tuple(sorted(m.movers))
        self._shown = self._truth
        self._null = self._quiet_cell(g)

    def _quiet_cell(self, g: np.ndarray) -> Cell:
        """A background cell outside every widget — clicking it costs an action and nothing else."""
        bg = segment.background(g)
        boxes = [c["box"] for c in self._controls]
        for y, x in ((0, 0), (0, 63), (63, 0), (31, 0), (0, 31)):
            if int(g[y, x]) not in bg:
                continue
            if any(y0 <= y <= y1 and x0 <= x <= x1 for y0, x0, y1, x1 in boxes):
                continue
            return (x, y)
        return (0, 0)

    def _believed(self) -> tuple[Cell, ...]:
        """Where the movers are, taking the newest unresolved action to have been kept."""
        assert self._truth is not None
        if not self._queue:
            return self._truth
        base, key, vec = self._queue[-1]
        if vec is None or (base, key) in self._blocked:
            # Optimism is only for moves not already KNOWN to be refused here. Believing the
            # phantom of a move we have already banked as blocked replans from a place the
            # board is not, picks the same refused move again, and loops until the budget ends.
            return base
        return _shift(base, vec)

    def _absorb(self, shown: tuple[Cell, ...]) -> bool:
        """Fold this frame into the model. False when the arithmetic does not close."""
        assert self._truth is not None
        if self._queue and self._queue[-1][2] is None:
            base, key, _ = self._queue[-1]
            vec = tuple((a[0] - b[0], a[1] - b[1]) for a, b in zip(shown, base))
            if all(d == (0, 0) for d in vec):
                # The frame shows the move even when it is refused, so a still frame means the
                # control drives nothing reachable from here at all.
                self._inert.add(key)
                self._blocked.add((base, key))
                self._queue.pop()
                self._truth = base
                return True
            self._delta[key] = vec
            other = (key[0], 1 - key[1])
            if len(self._controls[key[0]]["clicks"]) == 2 and other not in self._delta:
                self._delta[other] = tuple((-d[0], -d[1]) for d in vec)
            self._queue[-1] = (base, key, vec)

        if len(self._queue) < 2:
            return True
        first, second = self._queue[0], self._queue[1]
        vec1 = second[2]
        if vec1 is None:
            return True
        settled = _unshift(shown, vec1)
        kept = _shift(first[0], first[2]) if first[2] is not None else first[0]
        if settled == first[0] and settled != kept:
            self._blocked.add((first[0], first[1]))
        elif settled != kept:
            return False
        self._truth = settled
        self._queue = [(settled, second[1], vec1)]
        return True

    def _resync(self) -> list[Step]:
        """Read the truth outright: a click that moves nothing renders exactly what is there."""
        self._resyncs += 1
        if self._resyncs > 6:
            return []
        self._resyncing = True
        self._queue = []
        return [(6, self._null)]

    def _next_probe(self) -> tuple[tuple[int, int], Cell] | None:
        """The cheapest unanswered question: one click per control, second side only if needed."""
        for side in (0, 1):
            for i, control in enumerate(self._controls):
                if len(control["clicks"]) != 2:
                    continue
                if (i, side) not in self._delta and (i, side) not in self._inert:
                    return (i, side), control["clicks"][side]
        return None
