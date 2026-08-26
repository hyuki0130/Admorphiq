"""Reach a ring marker with a dot marker by driving framed two-way controls.

The mechanic this recovers, stated in frame terms only. A board carries two kinds of small
marker in one rare colour: a LONE CELL (the thing that moves) and a DIAMOND of four cells
around an empty centre (the place it must reach). Elsewhere sit framed widgets — a rectangle
whose border is exactly the perimeter of its own bounding box — and a widget split by a single
line down its middle is a TWO-WAY control: clicking one side of the line translates some
subset of the lone cells by a fixed vector, clicking the other side translates them back. The
level is won when every diamond has a marker cell at its centre.

Nothing about which control moves which marker is assumed. Each control is probed once, the
observed displacement IS the model, and the plan is an A* over how far each DIRECTION has been
wound out, using those learnt vectors. When a click leaves a marker where it was — the thing it
drives is at its stop, or the move would have overlapped and was undone — that (winding, click)
pair is banked as refused and the plan is recomputed from where the board actually is, so a
wrong model costs one action rather than a level.

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

__all__ = ["LinkageReachTool", "Markers", "marker_colour", "read_markers", "read_controls", "read_walls"]

Cell = tuple[int, int]

# A framed control is furniture, not the board: everything found is small.
_MAX_WIDGET = 24
_MIN_WIDGET = 4
# Boards in this family carry a handful of markers; a colour with more is painting something.
_MAX_MARKERS = 12
# A* refuses to grind: these boards resolve in tens of clicks or the model is wrong.
_MAX_EXPAND = 60_000
_MAX_DEPTH = 80
# How far a single control may be wound from where the level started it.
_MAX_WIND = 24
# Actions to spend without getting closer before handing the turn back.
_GIVE_UP = 40
_UNREACHABLE = 1 << 20
# What a step into scenery costs, in moves. Big enough to prefer a detour around a wall, small
# enough that a mover which must finish inside scenery can still get there.
_WALL_COST = 20


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


def read_walls(g: np.ndarray, colour: int) -> set[Cell]:
    """Structure the movers have to go around: a region carrying no marker of its own.

    A mover sits INSIDE the thing that carries it, so the carrier's region contains a marker
    cell and is excluded; so are the places, which are made of marker cells; so are the framed
    controls, which are not board at all. What is left is scenery. This is a PRIOR, not a fact —
    the planner pays to cross it rather than being forbidden to, because what a refused move
    really collides with is the carrier's far end, which no still frame shows.
    """
    bg = segment.background(g)
    marks = {(int(y), int(x)) for y, x in np.argwhere(g == colour)}
    boxes = [c["box"] for c in read_controls(g)]
    walls: set[Cell] = set()
    for cells in segment.components(g.tolist(), bg):
        if any(c in marks for c in cells):
            continue
        if any(y0 <= y <= y1 and x0 <= x <= x1 for y, x in cells for y0, x0, y1, x1 in boxes):
            continue
        walls.update(cells)
    return walls


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


def _at(base: tuple[Cell, ...], units: list[tuple[Cell, ...]], counts: tuple[int, ...]) -> tuple[Cell, ...]:
    """Where the movers sit when each DIRECTION has been wound to its count."""
    out = []
    for m, start in enumerate(base):
        y, x = start
        for n, unit in zip(counts, units):
            if n:
                y += n * unit[m][0]
                x += n * unit[m][1]
        out.append((y, x))
    return tuple(out)


def _plan(
    base: tuple[Cell, ...],
    groups: list[tuple[tuple[Cell, ...], list[tuple[int, int]]]],
    counts: tuple[int, ...],
    goals: tuple[Cell, ...],
    free: Any,
    walls: set[Cell] = frozenset(),  # type: ignore[assignment]
) -> list[tuple[int, int]] | None:
    """A* over how far each control is WOUND OUT, not over where the markers are.

    The coordinate is one count per DISTINCT DIRECTION a marker can be driven, not one per
    control. ⛔ Per-control counts have a null space whenever two controls move a marker the same
    way: wind one out and the other in and the search is at a state it has never seen with the
    marker exactly where it was, so it re-picks the move it just learnt is refused and drifts
    sideways until the budget ends — MEASURED, twelve notches of drift and no progress at all.

    ⛔ The marker's cell is not the state either, and treating it as one is what a first version
    of this got wrong. MEASURED: the same cell was reached two ways — with the base arm wound out, and
    with it wound in — and only one of them could then be lifted, because the wound-out base
    parks the next joint directly beneath a wall. A planner keyed on the cell banks "cannot go up
    from here", carries that to the other configuration where up is fine, and walls itself in.
    The extension vector distinguishes them and every refusal it banks is about a real arm.

    Crossing scenery is priced, not banned. With every move costing the same the search crawls
    along a wall a row at a time, spending actions to learn each row is shut; pricing a step into
    scenery sends it out of the wall's span first.
    """
    units = [u for u, _ in groups]
    live = [i for i, u in enumerate(units) if any(d != (0, 0) for d in u)]
    if not live or not goals:
        return None
    step = max(1, max(abs(d[0]) + abs(d[1]) for i in live for d in units[i]))
    here = _at(base, units, counts)
    seen: dict[tuple[int, ...], int] = {counts: 0}
    heap = [(_assign_cost(here, goals) // step, 0, counts, ())]
    expanded = 0
    while heap and expanded < _MAX_EXPAND:
        _, g_cost, state, path = heapq.heappop(heap)
        pos = _at(base, units, state)
        if _assign_cost(pos, goals) == 0:
            return list(path)
        if g_cost > seen.get(state, _UNREACHABLE) or len(path) >= _MAX_DEPTH:
            continue
        expanded += 1
        for i in live:
            for side, turn in ((0, 1), (1, -1)):
                key = (i, side)
                if not free(state, key):
                    continue
                nxt = state[:i] + (state[i] + turn,) + state[i + 1:]
                if abs(nxt[i]) > _MAX_WIND:
                    continue
                where = _at(base, units, nxt)
                if any(not (0 <= a < 64 and 0 <= b < 64) for a, b in where):
                    continue
                ng = g_cost + 1 + _WALL_COST * sum(1 for c in where if c in walls)
                if ng >= seen.get(nxt, _UNREACHABLE):
                    continue
                seen[nxt] = ng
                heapq.heappush(heap, (ng + _assign_cost(where, goals) // step, ng, nxt, path + (key,)))
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


def _wind(counts: tuple[int, ...], key: tuple[int, int]) -> tuple[int, ...]:
    """The winding after turning one control one notch the way that key turns it."""
    i, side = key
    return counts[:i] + (counts[i] + (1 if side == 0 else -1),) + counts[i + 1:]


# --- the tool ----------------------------------------------------------------


class LinkageReachTool:
    """Probe each framed control once, then wind the controls until every place is filled.

    ⛔ THE FRAME AFTER A REFUSED MOVE IS A LIE, and everything below is shaped by it. MEASURED on
    a live board: a click whose move would overlap scenery is applied, tested, and undone inside
    one action — but the frame handed back was rendered BEFORE the undo, so it shows the marker
    three cells INSIDE the wall while the engine's own sprite sits where it started. Two such
    frames in a row are identical, so "did the board change" cannot see it either; a model built
    by differencing consecutive frames therefore learns diagonal displacements that no single
    control can produce, and that is what a first version of this tool learnt.

    The algebra that recovers from it needs no extra actions. Every frame satisfies
    ``frame(k) = truth(k-1) + delta(k)`` whether the move was kept or refused, so the frame after
    the NEXT action pins the truth exactly: ``truth(k) = frame(k+1) - delta(k+1)``. Acceptance is
    therefore known one action late, at no cost — and if that arithmetic lands on none of the
    states it could be, one click on empty background (delta zero) renders the truth outright.
    """

    name = "linkage"

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._controls: list[dict[str, Any]] = []
        self._colour: int | None = None
        self._places: tuple[Cell, ...] = ()
        self._base: tuple[Cell, ...] = ()
        self._groups: list[tuple[tuple[Cell, ...], list[tuple[int, int]]]] = []
        self._counts: tuple[int, ...] = ()
        self._truth: tuple[Cell, ...] | None = None
        self._shown: tuple[Cell, ...] = ()
        self._queue: list[tuple[Any, ...]] = []
        self._delta: dict[tuple[int, int], tuple[Cell, ...]] = {}
        self._inert: set[tuple[int, int]] = set()
        self._blocked: set[tuple[tuple[int, ...], tuple[int, int]]] = set()
        self._walls: set[Cell] = set()
        self._path: list[tuple[int, int]] = []
        self._path_at: tuple[int, ...] | None = None
        self._null: Cell = (0, 0)
        self._resyncing = False
        self._resyncs = 0
        self._idle = 0
        self._best = _UNREACHABLE
        self._stale = 0

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
            # A mover is momentarily unreadable — passing alongside a place, or hidden under a
            # panel. The model still says where it should be, so carry on from the prediction
            # rather than stalling; the next frame that shows it corrects the record.
            shown = list(self._predicted())
        self._shown = tuple(shown)

        if self._resyncing:
            # The click just taken moved nothing, so this frame IS the board. Start clean.
            self._resyncing = False
            self._queue = []
            self._truth = self._shown
        elif not self._absorb(self._shown):
            return self._resync()
        self._anchor()

        counts, here = self._believed()
        if not set(places) - set(here):
            # The board is solved; the frame shown after a level-up is still the old one, so one
            # harmless click is what advances it. Proposing nothing is what stalls the game here.
            self._idle += 1
            return [] if self._idle > 2 else [(6, self._null)]
        self._idle = 0

        gap = _assign_cost(here, places)
        if gap < self._best:
            self._best, self._stale = gap, 0
        else:
            self._stale += 1
            if self._stale > _GIVE_UP:
                # Closer is the only evidence this tool is the right one for the board. Once it
                # has stopped getting closer it is spending a budget that ENDS THE GAME on two
                # of the sample games, so it hands the turn back rather than grinding it away.
                return []

        probe = self._next_probe()
        if probe is not None:
            key, xy = probe
            self._queue.append((counts, here, None, key, None))
            return [(6, xy)]
        if not self._groups:
            # The last probe's acceptance is still one frame away. Take it as kept and start the
            # winding here; if it was refused instead, the next frame re-seats the origin.
            self._truth, self._queue = here, []
            self._group_directions()
            counts = self._counts

        if self._path_at != counts:
            # ⛔ Replanning every action makes the tool oscillate. The state it plans from is the
            # optimistic one, so a move whose acceptance is still unknown looks taken, the next
            # plan starts by undoing it, and the pair cancels. Following one committed path until
            # the board contradicts it removes that entirely.
            self._path = _plan(self._base, self._groups, counts, places, self._free, self._walls) or []
        if not self._path:
            self._path_at = None
            return []
        gkey = self._path.pop(0)
        ckey = self._pick(counts, gkey)
        if ckey is None:
            self._path, self._path_at = [], None
            return []
        self._path_at = _wind(counts, gkey)
        self._queue.append((counts, here, gkey, ckey, self._delta[ckey]))
        return [(6, self._controls[ckey[0]]["clicks"][ckey[1]])]

    # -- state keeping -------------------------------------------------------

    def _start(self, g: np.ndarray, colour: int, places: tuple[Cell, ...], m: Markers) -> None:
        """A different set of places means a different board: everything learnt is stale."""
        self.reset()
        self._colour = colour
        self._places = places
        self._controls = read_controls(g)
        self._truth = tuple(sorted(m.movers))
        self._shown = self._truth
        self._base = self._truth
        self._counts = ()
        panels = {(y, x) for y0, x0, y1, x1 in (c["box"] for c in self._controls)
                  for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)}
        # A control panel is drawn OVER the board, so a mover driven under one disappears from
        # the frame entirely. Pricing the panels like scenery keeps the planner off them.
        self._walls = (read_walls(g, colour) | panels) - set(places)
        self._null = self._quiet_cell(g)

    def _group_directions(self) -> None:
        """One count per direction, with every control that drives it listed behind it.

        Which control to use is an EXECUTION choice, not a planning one: two controls that move
        a marker the same way are the same move as far as the plan is concerned, and are only
        told apart when one of them turns out to be refused where the other is not.
        """
        assert self._truth is not None
        order: dict[tuple[Cell, ...], list[tuple[int, int]]] = {}
        for i, _ in enumerate(self._controls):
            vec = self._delta.get((i, 0))
            if vec is None or all(d == (0, 0) for d in vec):
                continue
            flipped = tuple((-d[0], -d[1]) for d in vec)
            # A control that drives a marker the way another drives it BACKWARDS is the same
            # axis, not a second one. Folding the sign is what keeps the winding free of a null
            # space; leaving the two as separate counts reproduces the drift exactly.
            canon = max(vec, flipped)
            order.setdefault(canon, []).append((i, 1 if vec == canon else -1))
        self._groups = [(vec, members) for vec, members in order.items()]
        self._base = self._truth
        self._counts = tuple(0 for _ in self._groups)

    def _free(self, counts: tuple[int, ...], gkey: tuple[int, int]) -> bool:
        """Is this direction still worth trying here — has any control behind it gone untried?"""
        return self._pick(counts, gkey) is not None

    def _pick(self, counts: tuple[int, ...], gkey: tuple[int, int]) -> tuple[int, int] | None:
        """The control to work this direction with, skipping any refused at this winding."""
        group, side = gkey
        turn = 1 if side == 0 else -1
        for i, sign in self._groups[group][1]:
            key = (i, 0 if sign * turn > 0 else 1)
            if key in self._delta and (counts, key) not in self._blocked:
                return key
        return None

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

    def _predicted(self) -> tuple[Cell, ...]:
        """What the frame should be showing: previous truth plus the last action's delta."""
        assert self._truth is not None
        if not self._queue:
            return self._truth
        pos, vec = self._queue[-1][1], self._queue[-1][4]
        return pos if vec is None else _shift(pos, vec)

    def _believed(self) -> tuple[tuple[int, ...], tuple[Cell, ...]]:
        """The winding and the positions, taking the newest unresolved move to have been kept."""
        assert self._truth is not None
        if not self._queue:
            return self._counts, self._truth
        counts, pos, gkey, ckey, vec = self._queue[-1]
        if vec is None or (counts, ckey) in self._blocked:
            # Optimism is only for moves not already KNOWN to be refused here. Believing the
            # phantom of a move already banked as blocked replans from a place the board is not,
            # picks the same refused move again, and loops until the budget ends.
            return counts, pos
        return (_wind(counts, gkey) if gkey is not None else counts), _shift(pos, vec)

    def _absorb(self, shown: tuple[Cell, ...]) -> bool:
        """Fold this frame into the model. False when the arithmetic does not close.

        A click has three possible outcomes and the frame alone shows only two of them apart.
        It can be KEPT, it can be REFUSED (drawn, then undone behind the frame), and it can be
        INERT — the control is already at its stop, so nothing is drawn at all. Inert is the one
        that must not be mistaken: it makes the frame equal the state BEFORE the click, which no
        "previous truth plus this delta" reading can explain, and a tool that only knows
        kept-or-refused answers it by clicking the same dead control forever.
        """
        assert self._truth is not None
        zero = tuple((0, 0) for _ in shown)
        if self._queue and self._queue[-1][4] is None:
            counts, pos, gkey, key, _ = self._queue[-1]
            vec = tuple((a[0] - b[0], a[1] - b[1]) for a, b in zip(shown, pos))
            if vec == zero:
                self._inert.add(key)
                self._blocked.add((counts, key))
                self._queue.pop()
                self._truth, self._counts = pos, counts
                return True
            self._learn(key, vec)
            self._queue[-1] = (counts, pos, gkey, key, vec)

        if len(self._queue) < 2:
            return True
        (c0, p0, g0, k0, v0), (_, _, g1, k1, v1) = self._queue[0], self._queue[1]
        if v0 is None or v1 is None:
            return True
        kept_pos = _shift(p0, v0)
        kept_counts = _wind(c0, g0) if g0 is not None else c0
        for pos, counts, effect in ((kept_pos, kept_counts, v1), (p0, c0, v1),
                                    (kept_pos, kept_counts, zero), (p0, c0, zero)):
            if _shift(pos, effect) == shown:
                break
        else:
            return False
        if counts == c0 and kept_counts != c0:
            self._blocked.add((c0, k0))
            # ⛔ Banking the refusal against this winding ALONE is not enough. Two controls that
            # move a marker the same way give the winding a null space: wind one out, wind the
            # other in, and the planner is at a state it has never seen with the marker exactly
            # where it was — so it re-picks the refused move and drifts sideways forever, which
            # is MEASURED behaviour, not a worry. Pricing the cell the move was reaching for
            # closes that door while leaving the cell reachable by a genuinely different route.
            self._walls |= set(kept_pos) - set(self._places)
        if effect == zero:
            self._blocked.add((counts, k1))
        self._truth, self._counts = pos, counts
        self._queue = [(counts, pos, g1, k1, effect)]
        return True

    def _anchor(self) -> None:
        """Keep the planner's arithmetic tied to the board it is actually looking at.

        The winding is a coordinate for the ARM; the positions are what the frame shows. A
        resync throws away the queue without knowing which pending clicks were kept, so the two
        can part company — and a planner working in a frame shifted from the board plans moves
        that land somewhere else entirely. Re-seating the origin costs nothing and keeps every
        banked refusal meaningful, because a refusal is indexed by the winding, not the cell.
        """
        assert self._truth is not None
        if not self._groups or not self._base:
            return
        units = [u for u, _ in self._groups]
        drift = tuple((t[0] - w[0], t[1] - w[1])
                      for t, w in zip(self._truth, _at(self._base, units, self._counts)))
        if any(d != (0, 0) for d in drift):
            self._base = _shift(self._base, drift)
            self._path, self._path_at = [], None

    def _learn(self, key: tuple[int, int], vec: tuple[Cell, ...]) -> None:
        """One probe fixes both halves of a control: the other side is the same move, reversed."""
        self._delta[key] = vec
        other = (key[0], 1 - key[1])
        if len(self._controls[key[0]]["clicks"]) == 2 and other not in self._delta:
            self._delta[other] = tuple((-d[0], -d[1]) for d in vec)

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
