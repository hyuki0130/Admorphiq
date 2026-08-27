"""Clone-walk tool — solve a gated maze whose only extra verb parks a REPLAY CLONE.

The board family this reads is a walled maze with one body, one marked exit, and furniture that
is wired together in plain sight. Everything below is recovered from pixels; nothing here knows
a title, an identifier, a sprite tag or a coordinate.

THE GRAMMAR, and why each piece is safe to key on:

  * BODY — a solid square block of one colour whose single centre pixel shows the floor through
    it. The hole is not decoration: the engine tests exactly ONE point, the body's centre, so the
    hole marks the cell that has to be walkable and fixes the lattice the walk is planned on.
  * EXIT — a hollow ring with a LOOSE single cell of the same colour at its middle. The ring's
    colour is the body's colour, which ties the two together and makes the pair specific enough
    to bid on.
  * WALL — the commonest colour that is not the floor. Taking the commonest colour outright
    inverts the two the moment a board's floor is larger than its surround, and then every wall
    is a road and every road a wall.
  * FURNITURE is classified by the shape of its own colour in the window centred on a lattice
    cell, never by which colour that is:
      - a filled 3x3 with little else around it    -> a BUTTON (an input, held while stood on)
      - a filled 3x3 inside an almost-filled 5x5   -> a DOOR (blocks the cell it stands on)
      - a hollow ring around a floor centre        -> a PAD (an endpoint of a swap)
    A door drawn COMPLETELY filled latches — each press flips it and it stays; one whose edge row
    is gapped is momentary and follows its button. That gap is the only difference between the
    two and it is drawn, so the distinction costs no probe.
  * A CIRCUIT is one connected region of a single colour. The wire joining a button to its door
    is drawn in the same colour and touches both ends, so connectivity IS the wiring diagram —
    no probing required, and two circuits that happen to share a colour stay separate because
    they are not connected to each other.

⛔ THE TRAP THIS FAMILY IS BUILT ON: a button is RELEASED the instant the body steps off it.
Walking to the button and then to its door is not a solution and never can be. The extra verb
rewinds the whole path just walked and leaves a CLONE behind that replays it move for move — so
the way to hold a button down is to spend a clone on it. Clones advance one step per move the
body makes, which is why WHEN a door opens is part of the answer and a plain distance map cannot
express it. The plan is therefore searched inside a full forward model of the rules.

⛔ AND: colour alone never identifies the moving body. Two blocks of the SAME colour exist here —
the body and the exit ring — and an earlier reading of this family tracked the extreme row of
that colour, which silently mixed the two together. The body is the block with the hole; the
exit is the ring with the loose dot.

A SECOND body may be moving on the board without being steered by anything. It is modelled
too: it keeps its heading, prefers a turn when the heading is closed and takes the reverse
last, and it presses the inputs it stands on exactly as the body does — which on one of these
boards is the ONLY way a door on the way out ever opens, because the button that opens it sits
in a region the body can never reach. Where the stranger may go is bounded by an INVISIBLE
sprite, so the walk map stands in for it; that substitution is MEASURED against the engine
rather than assumed. Touching it ends the level, and so does standing under a door as it
shuts, so no route is allowed to contain either move.

⛔ HOW THIS MODEL IS KEPT HONEST, and it is the only reason the deep boards work: it is
differentially tested against the engine over random scripts that INCLUDE REWINDS, rather than
judged by whether some plan happened to work. Four defects surfaced that way and not one was
visible from a working plan — a stranger's REFUSED step recorded as a move (putting every later
undo one entry out), clones stacking past the tally instead of wrapping, a closing door not
killing what stood under it, and a swap resolving at the wrong MOMENT of a rewind. The last of
those was the whole of the hardest board: the plan was right and the model was wrong, which
from outside the tool is indistinguishable from a planning failure.

Execution is one action per call, each checked against where the body actually ended up. A
disagreement retires the plan and falls back to a route drawn on the board as it is right now,
rather than continuing to steer from a fiction. The board is read off the SETTLED frame — one
command plays out as an animation and the observation carries every tick of it, so the first
tick shows a board the body has already left. That reading is done HERE and not by widening the
shared reader: switching the shared one to the last tick was measured to cost three games.
"""

from __future__ import annotations

from collections import Counter, deque
from itertools import permutations, product
from typing import Any

import numpy as np

from admorphiq.tools.base import Step, availability, has_frame, levels_completed
from admorphiq.tools.segment import components

__all__ = ["CloneWalkTool", "read_scene", "read_board", "settled_grid"]

Cell = tuple[int, int]

_SIMPLE = (1, 2, 3, 4, 5, 7)
# These boards end on their own timer at a low action count, so a route longer than this could
# not be spent even if one existed.
_MAX_ROUTE = 70
_MAX_STATES = 60_000
# Total forward-model expansions one BOARD may cost, across every ordering, heading and retry.
# Planning happens once per board, but a board the tool cannot solve must not be allowed to
# spend minutes discovering that — measured at two minutes on the one board that defeats it.
_MAX_PLAN_STATES = 1_500_000
_MAX_PROBES = 30
# How many inputs a plan may consider parking a clone on, nearest to the start first — the cut
# falls on the furthest, least likely candidates.
_MAX_TARGETS = 6
# Extra moves a recording leg may be padded by when the plain search comes up empty.
_MAX_STRETCH = 4
# Wall pixels tolerated inside a body-sized tile before the cell counts as rock.
_TILE_SLACK = 2
_AXES: tuple[Cell, ...] = ((1, 0), (-1, 0), (0, 1), (0, -1))
# A heading, and the two quarter-turns either side of it, in the order an unsteered body on
# these boards was measured to prefer them. The cycle order is what makes "a turn, then the
# reverse" expressible as arithmetic; only the ORDER matters, not which end is called zero.
_HEADINGS: tuple[Cell, ...] = ((1, 0), (0, 1), (-1, 0), (0, -1))
# The heading such a body starts with is not drawn, so a plan is checked against all of them.
_FACINGS = (0, 1, 2, 3)


class _Door:
    """One sliding blocker: where it rests, which way it slides, and how it answers a press."""

    __slots__ = ("home", "slide", "latch", "circuit")

    def __init__(self, home: Cell, slide: Cell, latch: bool, circuit: int) -> None:
        self.home = home
        self.slide = slide
        self.latch = latch
        self.circuit = circuit


class _Board:
    """Everything static about one board, read from a single frame."""

    __slots__ = ("stride", "home", "exit", "walk", "doors", "buttons", "pads",
                 "circuit_doors", "circuit_swaps", "slots", "strangers")

    def __init__(self) -> None:
        self.stride = 1
        self.home: Cell = (0, 0)
        self.exit: Cell = (0, 0)
        self.walk: set[Cell] = set()
        self.doors: list[_Door] = []
        self.buttons: dict[Cell, int] = {}
        self.pads: dict[Cell, int] = {}
        self.circuit_doors: dict[int, list[int]] = {}
        self.circuit_swaps: dict[int, list[tuple[Cell, Cell]]] = {}
        self.slots = 1
        self.strangers: list[Cell] = []


class _Scene:
    """What one frame says right now: the body, the exit, and what floor and wall mean."""

    __slots__ = ("body", "exit", "floor", "wall", "span", "others")

    def __init__(self, body: Cell, exit_: Cell, floor: int, wall: int,
                 span: int, others: list[Cell]) -> None:
        self.body = body
        self.exit = exit_
        self.floor = floor
        self.wall = wall
        self.span = span
        self.others = others


# --- reading a frame --------------------------------------------------------


def _bbox(group: list[Cell]) -> tuple[int, int, int, int]:
    ys = [c[0] for c in group]
    xs = [c[1] for c in group]
    return min(ys), min(xs), max(ys), max(xs)


def _blobs(grid: np.ndarray, colour: int) -> list[list[Cell]]:
    """4-connected regions of exactly one colour, via the shared segmentation."""
    return components((grid != colour).astype(np.int16).tolist(), {1})


def settled_grid(obs: Any) -> np.ndarray | None:
    """The board AFTER the last command finished playing out.

    ⛔ Measured on this family: one command plays out as an animation and the observation carries
    every tick of it, oldest first. Reading the first tick steers from a board the body has
    already left — the tool then re-issues moves it has made and blames the refusal on whichever
    cell it believed it was standing on. The settled board is the LAST tick. A stack whose last
    entry does not parse as a board is not a run of ticks at all (it is a stack of overlays), so
    the reading falls back to the first entry rather than inventing one.
    """
    raw = getattr(obs, "frame", None)
    if raw is None or len(raw) == 0:
        return None
    arr = np.asarray(raw)
    if arr.ndim < 3:
        return arr.astype(np.int64)
    last = arr[-1].astype(np.int64)
    if read_scene(last) is not None:
        return last
    return arr[0].astype(np.int64)


def _holed_squares(grid: np.ndarray, colour: int) -> list[tuple[Cell, int]]:
    """Every isolated solid square of ``colour`` with exactly one hole, at its centre.

    Written as window sums rather than a flood because ``detect`` runs on every frame of every
    game: the flood over all sixteen colours cost about seven milliseconds a call on boards this
    tool does not even claim, and this is the test that rejects them.
    """
    mask = (grid == colour).astype(np.int32)
    total = np.zeros((mask.shape[0] + 1, mask.shape[1] + 1), dtype=np.int32)
    total[1:, 1:] = mask.cumsum(0).cumsum(1)

    def block(y0: int, x0: int, side: int) -> np.ndarray:
        return (total[y0 + side:, x0 + side:][:mask.shape[0] - side - y0 + 1,
                                              :mask.shape[1] - side - x0 + 1]
                - total[y0:, x0 + side:][:mask.shape[0] - side - y0 + 1,
                                         :mask.shape[1] - side - x0 + 1]
                - total[y0 + side:, x0:][:mask.shape[0] - side - y0 + 1,
                                         :mask.shape[1] - side - x0 + 1]
                + total[y0:, x0:][:mask.shape[0] - side - y0 + 1,
                                  :mask.shape[1] - side - x0 + 1])

    out: list[tuple[Cell, int]] = []
    n = mask.shape[0]
    for side in range(5, min(n // 4, 11) + 1, 2):
        inner = block(0, 0, side)
        ys, xs = np.where(inner == side * side - 1)
        for y, x in zip(ys.tolist(), xs.tolist()):
            mid = (y + side // 2, x + side // 2)
            if int(grid[mid]) == colour:
                continue
            # A body is drawn standing alone: nothing of its colour TOUCHES it, which is what
            # separates it from a corner of some larger shape of the same colour.
            #
            # ⛔ Touching means edge-adjacent, and the four edges are tested one at a time. An
            # earlier version tested the whole surrounding box instead, which also catches
            # anything sitting DIAGONALLY outside a corner — and the exit marker sits exactly
            # there when the body is one cell short of it. The body then went unread on the last
            # two steps of every single level, and only a fallback path hid it.
            if ((y and mask[y - 1, x:x + side].any())
                    or (y + side < n and mask[y + side, x:x + side].any())
                    or (x and mask[y:y + side, x - 1].any())
                    or (x + side < n and mask[y:y + side, x + side].any())):
                continue
            out.append((mid, side))
    return out


def read_scene(grid: np.ndarray) -> _Scene | None:
    """Recover the body and the exit, or nothing when this grammar is absent.

    Nothing is guessed: a board without a holed block AND a dotted ring of the same colour is
    not this family, and claiming it would take the turn from a tool that can solve it.
    """
    if grid.ndim != 2 or grid.shape[0] != grid.shape[1] or grid.shape[0] < 24:
        return None
    counts = Counter(int(v) for v in grid.ravel().tolist())
    if len(counts) < 3:
        return None
    bodies: dict[int, list[tuple[Cell, int]]] = {}
    for colour in counts:
        found = _holed_squares(grid, colour)
        if found:
            bodies[colour] = found
    for colour, found in sorted(bodies.items()):
        if len(found) != 1:
            continue
        rings = [
            mid for group in _blobs(grid, colour)
            for mid in [((min(c[0] for c in group) + max(c[0] for c in group)) // 2,
                         (min(c[1] for c in group) + max(c[1] for c in group)) // 2)]
            if _is_ring(grid, group, mid, colour)
        ]
        if len(rings) != 1:
            continue
        body, span = found[0]
        floor = int(grid[body])
        wall = next((c for c, _ in counts.most_common() if c != floor), floor)
        if wall == floor:
            return None
        # A block drawn the same way in ANOTHER colour is something else moving on this board,
        # not the thing being steered.
        others = [m for c, fs in bodies.items() if c != colour for m, _ in fs]
        return _Scene(body, rings[0], floor, wall, span, others)
    return None


def _is_ring(grid: np.ndarray, group: list[Cell], mid: Cell, colour: int) -> bool:
    """A hollow shape with a LOOSE cell of its own colour at the middle — the exit marker."""
    y0, x0, y1, x1 = _bbox(group)
    h, w = y1 - y0 + 1, x1 - x0 + 1
    if h != w or h < 7 or h % 2 == 0 or not 8 <= len(group) < h * w - 1:
        return False
    if int(grid[mid]) != colour:
        return False
    return all(int(grid[mid[0] + dy, mid[1] + dx]) != colour
               for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)))


def _circuit_map(grid: np.ndarray, floor: int, wall: int) -> dict[Cell, int]:
    """Label every non-floor, non-wall pixel with the id of its connected colour region."""
    label: dict[Cell, int] = {}
    nid = 0
    for colour in sorted({int(v) for v in grid.ravel().tolist()} - {floor, wall}):
        for group in _blobs(grid, colour):
            for cell in group:
                label[cell] = nid
            nid += 1
    return label


def tally_patch(grid: np.ndarray) -> bytes:
    """The corner strip carrying the board's clone tally, as a comparable stamp.

    ⛔ This is how the rewind is told apart from a move, and nothing else can do it: rewinding a
    ONE-move path puts the body exactly one cell from where it stood, which reads as an ordinary
    step and was measured being learned as "up". The tally is the only thing on the board that
    answers to the rewind and to nothing else.
    """
    n = grid.shape[0]
    return np.ascontiguousarray(grid[:max(4, n // 10), :max(8, n // 4)]).tobytes()


def _count_slots(grid: np.ndarray, wall: int, floor: int) -> int:
    """How many replay clones the board offers, counted off its own tally marks.

    The marks are a ROW OF EQUAL SQUARES pinned in a corner outside the play area. The count is
    load-bearing: spending one clone MORE than the board has resets every clone already parked,
    so a plan that miscounts throws away the work it just did.

    ⛔ They are NOT counted per colour. The mark for the clone currently being recorded is drawn
    differently from the rest, so counting the commonest colour's squares returns one on a board
    that offers two. What identifies a tally is that the marks are the same SIZE and sit on the
    same ROW; the row with the most such squares is the tally.
    """
    n = grid.shape[0]
    depth, width = max(4, n // 10), max(8, n // 4)
    # The shared segmentation walks a SQUARE grid, so the strip is padded out with wall — which
    # is inert here, because wall is never one of the colours counted.
    patch = np.full((width, width), wall, dtype=np.int64)
    patch[:depth, :width] = grid[:depth, :width]
    rows: Counter[tuple[int, int]] = Counter()
    for colour in sorted({int(v) for v in patch.ravel().tolist()} - {wall, floor}):
        for group in _blobs(patch, colour):
            y0, x0, y1, x1 = _bbox(group)
            side = y1 - y0 + 1
            if side != x1 - x0 + 1 or side < 3 or len(group) < side * side - 1:
                continue
            rows[(side, y0)] += 1
    return max(1, max(rows.values(), default=1))


def _pad_ring(grid: np.ndarray, cell: Cell, half: int, scene: _Scene) -> Cell | None:
    """A ring of one colour drawn around a floor centre marks a swap endpoint."""
    y, x = cell
    win = grid[y - half:y + half + 1, x - half:x + half + 1]
    if win.shape[0] != 2 * half + 1 or win.shape[1] != 2 * half + 1:
        return None
    ring = np.concatenate([win[0, :], win[-1, :], win[1:-1, 0], win[1:-1, -1]])
    colour, hits = Counter(int(v) for v in ring.tolist()).most_common(1)[0]
    if colour in (scene.floor, scene.wall) or hits < ring.size - 2:
        return None
    if int((win[1:-1, 1:-1] == colour).sum()):
        return None
    return (y - half, x - half)


def _slide(grid: np.ndarray, cell: Cell, half: int, colour: int) -> Cell | None:
    """Which way this blocker moves: toward the single tab that sticks out of its body.

    The tab is where the wire lands, so it is drawn on every one of these and reading it is
    free. Without it the blocker's destination is unknown, and a plan can route the body
    straight into the cell the blocker slid into.
    """
    y, x = cell
    for dy, dx in ((half, 0), (-half, 0), (0, half), (0, -half)):
        if int(grid[y + dy, x + dx]) == colour:
            return (dy // half, dx // half)
    return None


def read_board(grid: np.ndarray, scene: _Scene, stride: int) -> _Board | None:
    """Cut the frame into cells and name every piece of furniture standing on one."""
    n = grid.shape[0]
    if stride < 3 or stride > n // 4:
        return None
    if (scene.exit[0] - scene.body[0]) % stride or (scene.exit[1] - scene.body[1]) % stride:
        return None
    board = _Board()
    board.stride = stride
    board.home = scene.body
    board.exit = scene.exit
    circuits = _circuit_map(grid, scene.floor, scene.wall)
    half = stride // 2
    span = max(1, (scene.span - 1) // 2)
    for y in range(scene.body[0] % stride, n, stride):
        for x in range(scene.body[1] % stride, n, stride):
            if not (half <= y < n - half and half <= x < n - half):
                continue
            colour = int(grid[y, x])
            if colour == scene.wall:
                continue
            # ⛔ ONE pixel is not enough to call a cell a road. The wire joining a button to its
            # door is drawn straight ACROSS walls, so the cell under it reads as furniture and a
            # route was planned through solid rock — measured, the body simply refused to move.
            # The body's own drawing is the footprint that has to fit, so the whole tile is what
            # gets tested. Against the engine's own mask this is EXACT on every board seen.
            tile = grid[y - span:y + span + 1, x - span:x + span + 1]
            if int((tile == scene.wall).sum()) > _TILE_SLACK:
                continue
            board.walk.add((y, x))
            if colour == scene.floor:
                anchor = _pad_ring(grid, (y, x), half, scene)
                if anchor is not None:
                    board.pads[(y, x)] = circuits.get(anchor, -1)
                continue
            if not bool((grid[y - 1:y + 2, x - 1:x + 2] == colour).all()):
                continue
            win = grid[y - half + 1:y + half, x - half + 1:x + half]
            filled, area = int((win == colour).sum()), win.size
            cid = circuits.get((y, x), -1)
            if filled >= area - 4:
                slide = _slide(grid, (y, x), half, colour)
                if slide is None:
                    continue
                board.circuit_doors.setdefault(cid, []).append(len(board.doors))
                board.doors.append(_Door((y, x), slide, filled >= area, cid))
            elif filled <= area // 2:
                board.buttons[(y, x)] = cid
    _pair_pads(board)
    board.slots = _count_slots(grid, scene.wall, scene.floor)
    board.strangers = [c for c in scene.others if c in board.walk]
    return board


def _pair_pads(board: _Board) -> None:
    """Join swap endpoints two by two — nearest first, inside the circuit that feeds them."""
    by_circuit: dict[int, list[Cell]] = {}
    for cell, cid in board.pads.items():
        by_circuit.setdefault(cid, []).append(cell)
    for cid, cells in by_circuit.items():
        left = sorted(cells)
        while len(left) >= 2:
            a = left.pop(0)
            b = min(left, key=lambda c: abs(c[0] - a[0]) + abs(c[1] - a[1]))
            left.remove(b)
            board.circuit_swaps.setdefault(cid, []).append((a, b))


# --- the forward model ------------------------------------------------------


class _World:
    """An exact forward model of the board's rules — the thing the plan is searched inside."""

    def __init__(self, board: _Board, facing: int = 0, meter: list[int] | None = None) -> None:
        self.b = board
        # A shared tally of forward steps taken across every world one board's planning builds,
        # so the whole search can be stopped rather than each attempt separately.
        self.meter = meter if meter is not None else [0]
        self.open = [False] * len(board.doors)
        self.ghosts: list[list[Cell]] = []
        self.expansions = 0
        self.t = 0
        self.pos = board.home
        self.gpos: list[Cell] = []
        self.spos = list(board.strangers)
        self.face = [facing] * len(board.strangers)
        self.slog: list[list[Cell]] = [[] for _ in board.strangers]
        self.path: list[Cell] = []
        # ⛔ Who is standing on which input is CARRIED, not re-derived from positions each
        # tick. The board keeps a set per input and only an arrival or a departure changes it;
        # a swap moves bodies WITHOUT either, so a derived version drifts the moment one fires
        # — measured as a rewind that left the unsteered body stranded mid-board.
        self.held: dict[Cell, set[str]] = {}
        self.dead = [False] * len(board.strangers)
        self._squashed = False
        self.spent = 0
        self._settle(False)

    # -- state ---------------------------------------------------------------

    def key(self) -> tuple:
        """What makes two states the same for search purposes.

        ⛔ The move COUNT belongs in the key only while a clone is replaying, because that is the
        only thing it indexes. Carrying it unconditionally multiplies the state space by the
        route length, and the one board whose route has to WAIT for an unsteered body to arrive
        then exhausts the search before it finds the wait.
        """
        base = (self.pos, tuple(self.gpos), tuple(self.open), tuple(self.spos),
                tuple(self.face), tuple(self.dead))
        return (self.t, *base) if self.ghosts else base

    def snapshot(self) -> tuple:
        return (self.t, self.pos, tuple(self.gpos), tuple(self.open), tuple(self.path),
                tuple(self.spos), tuple(self.face), tuple(tuple(g) for g in self.slog),
                tuple(sorted((c, tuple(sorted(v))) for c, v in self.held.items() if v)),
                self.spent, tuple(self.dead))

    def restore(self, snap: tuple) -> None:
        (self.t, self.pos, gpos, opened, path, spos, face, slog, held,
         self.spent, dead) = snap
        self.dead = list(dead)
        self.gpos = list(gpos)
        self.open = list(opened)
        self.path = list(path)
        self.spos = list(spos)
        self.face = list(face)
        self.slog = [list(g) for g in slog]
        self.held = {c: set(v) for c, v in held}

    # -- rules ---------------------------------------------------------------

    def _door_cell(self, i: int) -> Cell:
        door = self.b.doors[i]
        if not self.open[i]:
            return door.home
        return (door.home[0] + door.slide[0] * self.b.stride,
                door.home[1] + door.slide[1] * self.b.stride)

    def _shadow(self) -> frozenset[Cell]:
        """Where the doors physically ARE — which is where they were when the tick began.

        ⛔ A door's state flips the instant its button is released, but the door itself takes
        six frames to arrive, and every body that moves in that tick moves against the door's
        OLD footprint. Measured: the unsteered body walks into a doorway that has already
        logically shut, and is then crushed when the door lands on it. Judging the tick against
        the new state instead turns that into a body that simply bounces — alive, in the wrong
        place, and pressing nothing.
        """
        return frozenset(self._door_cell(i) for i in range(len(self.b.doors)))

    def _passable(self, cell: Cell, shadow: frozenset[Cell] | None = None) -> bool:
        if cell not in self.b.walk:
            return False
        return cell not in (self._shadow() if shadow is None else shadow)

    def _stranger_step(self, i: int, shadow: frozenset[Cell]) -> Cell | None:
        """One step of a body this tool does not steer, by the rule its own motion shows.

        It keeps the heading it has, and when the heading is not available it prefers a turn,
        then the reverse. Where it may go at all is not drawn anywhere on the board — the region
        that confines it is an INVISIBLE sprite — so the walk map stands in for it. That
        substitution is measured, not assumed: against the engine it reproduces the body's cell
        exactly for forty consecutive moves on both boards that carry one.
        """
        cell, facing = self.spos[i], self.face[i]
        for _ in range(4):
            chosen = None
            for turn in (facing, (facing - 1) % 4, (facing + 1) % 4, (facing + 2) % 4):
                dy, dx = _HEADINGS[turn]
                nxt = (cell[0] + dy * self.b.stride, cell[1] + dx * self.b.stride)
                if nxt in self.b.walk:
                    chosen, facing = turn, turn
                    break
            if chosen is None:
                self.face[i] = facing
                return None
            dy, dx = _HEADINGS[chosen]
            nxt = (cell[0] + dy * self.b.stride, cell[1] + dx * self.b.stride)
            if self._passable(nxt, shadow):
                self.face[i] = facing
                return nxt
            facing = (facing + 2) % 4
        self.face[i] = facing
        return None

    def _fire(self, cell: Cell, body: str, value: bool,
              swaps: list[tuple[Cell, Cell]], rewinding: bool) -> None:
        """One body arriving at or leaving one cell, plus whatever edge that creates."""
        here = self.held.setdefault(cell, set())
        was = bool(here)
        if value:
            here.add(body)
        else:
            here.discard(body)
        cid = self.b.buttons.get(cell)
        if cid is None or bool(here) == was:
            return
        for idx in self.b.circuit_doors.get(cid, ()):
            if self.b.doors[idx].latch:
                if value:
                    self.open[idx] = not self.open[idx]
            else:
                self.open[idx] = value
        # A swap fires on the press while playing and on the release while rewinding — the board
        # runs its wiring backwards along with everything else.
        #
        # ⛔ AND THE TWO RESOLVE AT DIFFERENT MOMENTS. Playing, the swap is an animation that
        # lands once everything has moved. REWINDING, it happens THERE AND THEN, inside the
        # release — so a body already relocated by it takes its own next backward step from the
        # new place. Deferring it to the end of the step like the forward case leaves the body
        # stepping back from where it no longer is: measured, the retrace stalled against a wall
        # twice, the button that reopens a latch was never crossed, and the unsteered body spent
        # the rest of the rewind shut behind that latch.
        pairs = self.b.circuit_swaps.get(cid, ())
        if value != rewinding:
            if rewinding:
                self._apply_swaps(list(pairs))
            else:
                swaps.extend(pairs)

    def _settle(self, rewinding: bool) -> None:
        swaps: list[tuple[Cell, Cell]] = []
        self._press_all(swaps, rewinding)
        self._apply_swaps(swaps)

    def _press_all(self, swaps: list[tuple[Cell, Cell]], rewinding: bool) -> None:
        """Everything standing on an input presses it, in the order the board resolves them."""
        self._fire(self.pos, "P", True, swaps, rewinding)
        for i, c in enumerate(self.spos):
            self._fire(c, f"S{i}", True, swaps, rewinding)
        for i, g in enumerate(self.gpos):
            self._fire(g, f"G{i}", True, swaps, rewinding)

    def _apply_swaps(self, swaps: list[tuple[Cell, Cell]]) -> None:
        """Exchange whatever stands on the two endpoints — sets and positions together."""
        for a, b in swaps:
            on_a, on_b = self._names_at(a), self._names_at(b)
            self.held[a] = set(on_b)
            self.held[b] = set(on_a)
            for name in on_a:
                self._place(name, b)
            for name in on_b:
                self._place(name, a)

    def _names_at(self, cell: Cell) -> list[str]:
        out = ["P"] if self.pos == cell else []
        out += [f"G{i}" for i, g in enumerate(self.gpos) if g == cell]
        return out + [f"S{i}" for i, c in enumerate(self.spos) if c == cell]

    def _place(self, name: str, cell: Cell) -> None:
        if name == "P":
            self.pos = cell
        elif name[0] == "G":
            self.gpos[int(name[1:])] = cell
        else:
            self.spos[int(name[1:])] = cell

    def move(self, step: Cell) -> bool:
        """One command. False when the board refuses it — and then NOTHING advances."""
        self.expansions += 1
        self.meter[0] += 1
        shadow = self._shadow()
        dest = (self.pos[0] + step[0] * self.b.stride, self.pos[1] + step[1] * self.b.stride)
        if not self._passable(dest, shadow):
            return False
        before = self.snapshot()
        shut = list(self.open)
        swaps: list[tuple[Cell, Cell]] = []
        self._fire(self.pos, "P", False, swaps, False)
        self.pos = dest
        for i, ghost in enumerate(self.ghosts):
            if self.t >= len(ghost):
                continue
            gstep = ghost[self.t]
            gdest = (self.gpos[i][0] + gstep[0] * self.b.stride,
                     self.gpos[i][1] + gstep[1] * self.b.stride)
            if not self._passable(gdest, shadow):
                continue
            self._fire(self.gpos[i], f"G{i}", False, swaps, False)
            self.gpos[i] = gdest
        for i in range(len(self.spos)):
            nxt = None if self.dead[i] else self._stranger_step(i, shadow)
            if nxt is None:
                # ⛔ A step it could not take is NOT recorded. The board logs only the moves an
                # unsteered body actually made, and the rewind walks that log back one entry per
                # undo — so recording a refusal as a zero-move puts every later undo one entry
                # out and the body ends the rewind somewhere it never was.
                continue
            self._fire(self.spos[i], f"S{i}", False, swaps, False)
            self.slog[i].append(((nxt[0] - self.spos[i][0]) // self.b.stride,
                                 (nxt[1] - self.spos[i][1]) // self.b.stride))
            self.spos[i] = nxt
        self._press_all(swaps, False)
        self._apply_swaps(swaps)
        self._crush(shut)
        self.path.append(step)
        self.t += 1
        # ⛔ Touching an unsteered body ends the level, and so does standing under a door as it
        # shuts. A plan must never contain the move that does either, so the move is refused
        # here rather than discovered once the body is already dead.
        if self.pos in self.spos or self._squashed:
            self.restore(before)
            return False
        return True

    def _crush(self, shut: list[bool]) -> None:
        """A door that has just closed kills whatever is standing where it landed.

        The unsteered body does not merely stop — it is GONE, and every later pass that was
        counting on it to press something is counting on nothing.
        """
        self._squashed = False
        for idx, door in enumerate(self.b.doors):
            if not shut[idx] or self.open[idx]:
                continue
            if self.pos == door.home:
                self._squashed = True
            for i, cell in enumerate(self.spos):
                if cell == door.home:
                    self.dead[i] = True

    def rewind(self) -> None:
        """Retrace the path backwards, leave a clone replaying it, and start the pass over.

        The retrace is simulated rather than assumed away: the body crosses every cell of the
        path a second time on the way back, and a LATCHING door counts each of those crossings.
        """
        if not self.path:
            return
        recorded = list(self.path)
        while self.path:
            step = self.path.pop()
            idx = len(self.path)
            shadow = self._shadow()
            swaps: list[tuple[Cell, Cell]] = []
            for i in range(len(self.spos)):
                if idx >= len(self.slog[i]):
                    continue
                sstep = self.slog[i].pop()
                sdest = (self.spos[i][0] - sstep[0] * self.b.stride,
                         self.spos[i][1] - sstep[1] * self.b.stride)
                if not self._passable(sdest, shadow):
                    continue
                self._fire(self.spos[i], f"S{i}", False, swaps, True)
                self.spos[i] = sdest
            for i, ghost in enumerate(self.ghosts):
                if idx >= len(ghost):
                    continue
                gstep = ghost[idx]
                gdest = (self.gpos[i][0] - gstep[0] * self.b.stride,
                         self.gpos[i][1] - gstep[1] * self.b.stride)
                if not self._passable(gdest, shadow):
                    continue
                self._fire(self.gpos[i], f"G{i}", False, swaps, True)
                self.gpos[i] = gdest
            back = (self.pos[0] - step[0] * self.b.stride,
                    self.pos[1] - step[1] * self.b.stride)
            if self._passable(back, shadow):
                self._fire(self.pos, "P", False, swaps, True)
                self.pos = back
            self.t -= 1
            shut = list(self.open)
            self._press_all(swaps, True)
            self._apply_swaps(swaps)
            self._crush(shut)
        # ⛔ Spending the LAST tally mark does not add a clone — it clears every clone already
        # parked and puts the tally back to full. A model that keeps stacking them believes in
        # help that is no longer on the board.
        self.spent += 1
        if self.spent == self.b.slots:
            for i in range(len(self.ghosts)):
                for standing in self.held.values():
                    standing.discard(f"G{i}")
            self.ghosts = []
            self.spent = 0
        else:
            self.ghosts.append(recorded)
        self.t = 0
        self.pos = self.b.home
        self.gpos = [self.b.home] * len(self.ghosts)
        self.slog = [[] for _ in self.spos]
        self.path = []

    # -- searching -----------------------------------------------------------

    def route(self, target: Cell, moves: list[Cell],
              shun: frozenset[Cell] = frozenset(), at_least: int = 0) -> list[Cell] | None:
        """Shortest command sequence from HERE that lands the body on ``target``.

        ``shun`` names cells the route may not step on. It exists for one measured reason: a
        clone replays every step of the route it was recorded on, so a route that crosses an
        input it did not come for goes on pressing that input FOREVER, in every later pass. On
        one board the second clone's route wandered over the first clone's latch four moves
        after the first clone had opened it, shut it again, and locked out the third party whose
        help the whole plan depended on.
        """
        if self.pos == target and not at_least:
            return []
        start = self.snapshot()
        seen = {self.key()}
        queue: deque[tuple[tuple, list[Cell]]] = deque([(start, [])])
        found: list[Cell] | None = None
        states = 0
        while queue and found is None:
            snap, taken = queue.popleft()
            if len(taken) >= _MAX_ROUTE:
                continue
            for step in moves:
                self.restore(snap)
                if not self.move(step):
                    continue
                if self.pos in shun:
                    continue
                states += 1
                if states > _MAX_STATES or self.meter[0] > _MAX_PLAN_STATES:
                    queue.clear()
                    break
                if self.pos == target and len(taken) + 1 >= at_least:
                    found = taken + [step]
                    break
                k = self.key()
                if k in seen:
                    continue
                seen.add(k)
                queue.append((self.snapshot(), taken + [step]))
        self.restore(start)
        return found


def _reach(board: _Board, start: Cell, blocked: set[Cell],
           bridges: bool = False) -> dict[Cell, Cell | None]:
    """Plain flood over the lattice — used only to decide WHICH inputs are worth a clone.

    ⛔ With ``bridges`` the swap pads are treated as one step apart. They have to be: on several
    of these boards the exit sits in a region the walk CANNOT reach at all, joined to the rest
    only by a swap, and a flood that ignores that reports the board unsolvable and asks for no
    clone at all — so the button that opens the door on the way was never even considered.
    """
    seen: dict[Cell, Cell | None] = {start: None}
    queue = deque([start])
    partner: dict[Cell, Cell] = {}
    if bridges:
        for pairs in board.circuit_swaps.values():
            for a, b in pairs:
                partner[a] = b
                partner[b] = a
    while queue:
        cell = queue.popleft()
        nexts = [(cell[0] + dy * board.stride, cell[1] + dx * board.stride)
                 for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1))]
        if cell in partner:
            nexts.append(partner[cell])
        for nxt in nexts:
            if nxt in seen or nxt not in board.walk or nxt in blocked:
                continue
            seen[nxt] = cell
            queue.append(nxt)
    return seen


# --- the tool ---------------------------------------------------------------


class CloneWalkTool:
    """Walk the body to the marked exit, parking a replay clone on every button that gates it."""

    name = "clonewalk"

    def __init__(self) -> None:
        # What each command means outlives a board; only the board itself is redrawn.
        self._delta: dict[int, Cell] = {}
        self._rewind: int | None = None
        self._span = 0
        self._probes = 0
        self._board_key: tuple | None = None
        self._cache: tuple[bytes, float] | None = None
        self._meter = [0]
        self.reset()

    def reset(self) -> None:
        self._board: _Board | None = None
        self._plan: list[int] | None = None
        self._expect: list[Cell] | None = None
        self._cursor = 0
        self._pending: tuple[int, Cell, bytes] | None = None
        self._tally = b""
        self._tally0 = b""
        self._recover = 0
        self._refused: set[tuple[int, Cell]] = set()
        self._was: Cell | None = None
        self._sent: int | None = None
        self._seen_at: Cell | None = None
        self._trail = 0
        self._dead = False

    # -- protocol ------------------------------------------------------------

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """Learning runs off the body's measured displacement, taken in propose()."""

    def detect(self, frames: list[Any], obs: Any) -> float:
        """Bid only on a board showing the whole grammar, and never once this one is given up.

        ⛔ A tool with no plan must bid ZERO. A consolation bid is not free — it takes the turn
        from whichever tool could have solved the board, measured elsewhere as a 10x loss on a
        game the bidder never fitted.
        """
        if self._dead or not has_frame(obs):
            return 0.0
        simple, action6 = availability(obs)
        if action6 or len({1, 2, 3, 4} & set(simple)) < 4 or 5 not in simple:
            return 0.0
        grid = settled_grid(obs)
        if grid is None:
            return 0.0
        if self._board is not None and self._plan is not None:
            # Already holding a plan for this board — and the clones this tool parks are drawn
            # exactly like the body, so re-reading the board mid-plan would see its own work as
            # a stranger and hand the board away in the middle of a route.
            return 0.75
        stamp = grid.tobytes()
        if self._cache is not None and self._cache[0] == stamp:
            return self._cache[1]
        scene = read_scene(grid)
        score = 0.0
        if scene is not None:
            board = read_board(grid, scene, self._span or scene.span + 1)
            if board is not None and board.doors and board.exit in board.walk:
                score = 0.75
        self._cache = (stamp, score)
        return score

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        if not has_frame(obs):
            return []
        grid = settled_grid(obs)
        if grid is None:
            return []
        scene = read_scene(grid)
        if scene is None:
            return []
        simple, _ = availability(obs)
        legal = [a for a in _SIMPLE if a in simple]
        if len({1, 2, 3, 4} & set(simple)) < 4:
            return []
        key = (levels_completed(obs), scene.exit, scene.span)
        if key != self._board_key:
            self._board_key = key
            self.reset()
            self._tally0 = tally_patch(grid)
        self._tally = tally_patch(grid)
        self._track(scene)
        self._learn(scene)
        self._settle_controls(legal)
        if self._dead:
            return []
        if len(self._delta) < 4 or self._rewind is None:
            return self._probe_step(scene, legal)
        if self._board is None and (self._tally != self._tally0 or self._trail):
            # ⛔ Naming the commands cost a tally mark. A plan is computed for a board with all
            # its clones in hand, so the marks are wound back BEFORE planning: spending the rest
            # wraps the tally and clears every clone, which is exactly what is wanted.
            #
            # ⛔ And only before planning. Left ungated this fires on the plan's OWN rewind — the
            # tally has legitimately moved — and the extra rewind wrapped the tally, deleted the
            # clone the plan had just parked, and left the body standing at a door that never
            # opened again. Measured: the level was lost from a winning position.
            spent = self._spend_marks(grid, scene)
            if spent is not None:
                return spent
        if self._board is None and not self._build(grid, scene):
            return []
        return self._advance(grid, scene)

    def _emit(self, action: int, body: Cell) -> list[Step]:
        """Every command leaves through here, so the recorded path is never guessed at."""
        self._sent = action
        self._seen_at = body
        return [(action, None)]

    def _track(self, scene: _Scene) -> None:
        """Keep the length of the path the next rewind would replay.

        ⛔ This is not bookkeeping. A plan is computed for a body standing at the start with
        NOTHING recorded, and the commands spent naming the controls are recorded moves like any
        other — so the clone spent on a button replayed those first and arrived four moves late,
        at a door the body had already been refused by. Measured: a level lost from a plan that
        was correct for the board it assumed.
        """
        if self._sent is None:
            return
        if self._sent == self._rewind:
            self._trail = 0
        elif self._seen_at is not None and scene.body != self._seen_at:
            self._trail += 1

    # -- learning the commands ------------------------------------------------

    def _settle_controls(self, legal: list[int]) -> None:
        """Fill in whatever the probes have already made inevitable.

        ⛔ Two commands never need probing and both were measured costing real actions. The
        LAST direction is settled by elimination — four movement commands mean the four
        directions, and probing the fourth from a cell whose remaining side is a wall repeats
        forever (thirty refusals of the same command from the same cell). The REWIND is settled
        the same way, and must be: probing it while a path exists spends a clone the plan needs.
        """
        unnamed = [a for a in legal if a not in self._delta and a != self._rewind]
        fresh = [d for d in _AXES if d not in self._delta.values()]
        if len(unnamed) == 1 and len(fresh) == 1:
            self._delta[unnamed[0]] = fresh.pop()
            unnamed = []
        if self._rewind is None and len(self._delta) == 4:
            spare = [a for a in legal if a not in self._delta]
            if len(spare) != 1:
                self._dead = True
                return
            self._rewind = spare[0]

    def _probe_step(self, scene: _Scene, legal: list[int]) -> list[Step]:
        """Try an unnamed command and watch what the body does."""
        self._probes += 1
        if self._probes > _MAX_PROBES:
            self._dead = True
            return []
        unnamed = [a for a in legal if a not in self._delta and a != self._rewind]
        untried = [a for a in unnamed if (a, scene.body) not in self._refused]
        if untried:
            action = untried[0]
            self._pending = (action, scene.body, self._tally)
            return self._emit(action, scene.body)
        if not unnamed:
            self._dead = True
            return []
        # Every unnamed command has already been refused HERE, so a probe only says something
        # somewhere else: take a named step first.
        stride = self._span or scene.span + 1
        for action, step in sorted(self._delta.items()):
            dest = (scene.body[0] + step[0] * stride, scene.body[1] + step[1] * stride)
            if dest == self._was:
                continue
            self._was = scene.body
            return self._emit(action, scene.body)
        self._dead = True
        return []

    def _learn(self, scene: _Scene) -> None:
        """Name the command just issued by the displacement it produced."""
        if self._pending is None:
            return
        action, before, marks = self._pending
        self._pending = None
        if marks != self._tally:
            # Only the rewind spends a tally mark.
            self._rewind = action
            return
        dy, dx = scene.body[0] - before[0], scene.body[1] - before[1]
        if dy == 0 and dx == 0:
            self._refused.add((action, before))
            return
        if (dy and dx) or (self._span and max(abs(dy), abs(dx)) != self._span):
            self._rewind = action
            return
        span = max(abs(dy), abs(dx))
        self._span = span
        self._delta[action] = (dy // span if dy else 0, dx // span if dx else 0)

    def _spend_marks(self, grid: np.ndarray, scene: _Scene) -> list[Step] | None:
        """Burn the remaining clones so the tally wraps back to a full board."""
        self._recover += 1
        if self._recover > 4 * _MAX_PROBES:
            self._dead = True
            return []
        board = read_board(grid, scene, self._span or scene.span + 1)
        if board is None:
            self._dead = True
            return []
        if self._trail == 0:
            for action, step in sorted(self._delta.items()):
                dest = (scene.body[0] + step[0] * board.stride,
                        scene.body[1] + step[1] * board.stride)
                if dest in board.walk:
                    return self._emit(action, scene.body)
            self._dead = True
            return []
        return self._emit(self._rewind or 0, scene.body)

    # -- planning -------------------------------------------------------------

    def _moves(self) -> list[Cell]:
        return [self._delta[a] for a in sorted(self._delta)]

    def _action_of(self, step: Cell) -> int:
        return next(a for a, d in self._delta.items() if d == step)

    def _build(self, grid: np.ndarray, scene: _Scene) -> bool:
        board = read_board(grid, scene, self._span or scene.span + 1)
        if board is None or not board.doors or board.exit not in board.walk:
            self._dead = True
            return False
        self._board = board
        plan = self._solve(board)
        if plan is None:
            self._dead = True
            return False
        self._plan, self._expect = plan
        self._cursor = 0
        return True

    def _gating(self, board: _Board) -> list[Cell]:
        """The inputs a clone is worth spending on: those wired to something in the way.

        ⛔ Not simply "every input the body walks past". A board with inputs that gate nothing on
        the way out will happily take every clone and leave none for the one that matters, so the
        dependency is chased instead: route out with every door imagined open and every swap
        imagined usable, take the doors and swaps that route needs, take THEIR buttons, then
        route to those and repeat.
        """
        wanted: list[Cell] = []
        seen: set[Cell] = set()
        pending = [board.exit]
        guard = 0
        while pending and guard < 12:
            guard += 1
            goal = pending.pop()
            if goal in seen:
                continue
            seen.add(goal)
            tree = _reach(board, board.home, set(), bridges=True)
            if goal not in tree:
                continue
            cell: Cell | None = goal
            while cell is not None:
                for circuit in self._circuits_at(board, cell):
                    for button in sorted(board.buttons):
                        if board.buttons[button] == circuit and button not in wanted:
                            wanted.append(button)
                            pending.append(button)
                if cell in board.pads and cell not in wanted:
                    wanted.append(cell)
                    pending.append(cell)
                cell = tree[cell]
        # ⛔ The chase alone is not the candidate set. Measured: a board whose exit needs a door
        # whose button sits behind ANOTHER door returns only the buttons it cannot reach, and
        # every plan starts with a leg that cannot be walked. The inputs the body CAN reach are
        # always candidates too — that is where a first clone has to come from.
        rest = [c for c in list(board.buttons) + list(board.pads) if c not in wanted]
        rest.sort(key=lambda c: abs(c[0] - board.home[0]) + abs(c[1] - board.home[1]))
        return (wanted + rest)[:_MAX_TARGETS]

    @staticmethod
    def _circuits_at(board: _Board, cell: Cell) -> list[int]:
        """Which wiring a cell depends on: a door's own circuit, or a pad's swap circuit."""
        out = [door.circuit for door in board.doors if door.home == cell]
        if cell in board.pads:
            out.append(board.pads[cell])
        return out

    def _solve(self, board: _Board) -> tuple[list[int], list[Cell]] | None:
        """Find a plan, and prefer one that holds however the unsteered bodies are facing.

        ⛔ A body this tool does not steer starts pointing SOMEWHERE, and which way is not drawn
        — the sprite is symmetric and it has not moved yet. So the plan is searched under each
        heading in turn and then REPLAYED under all of them; one that still wins under every
        heading is taken over a shorter one that only wins under the assumed one. Where no such
        plan exists the shortest is kept and the execution check catches the disagreement.
        """
        moves = self._moves()
        if len(moves) < 4:
            return None
        targets = self._gating(board)
        self._meter = [0]
        fallback: tuple[list[int], list[Cell]] | None = None
        for facing in _FACINGS:
            got = self._search(board, targets, moves, facing)
            if got is None:
                continue
            if not board.strangers:
                return got
            if all(self._replay(board, got[0], f) is not None for f in _FACINGS):
                return got
            if fallback is None or len(got[0]) < len(fallback[0]):
                fallback = got
        return fallback

    def _search(self, board: _Board, targets: list[Cell], moves: list[Cell],
                facing: int) -> tuple[list[int], list[Cell]] | None:
        """Shortest plan under ONE heading: park k clones on gating inputs, then walk out."""
        budget = max(0, board.slots - 1)
        # A plan whose FIRST leg cannot be walked is not a plan; testing that once per target
        # rather than once per ordering is what keeps the search affordable.
        opener = {t: self._leg(_World(board, facing, self._meter), t, moves, board)
                  for t in targets}
        near: list[tuple[Cell, ...]] = []
        for k in range(0, budget + 1):
            best: tuple[list[int], list[Cell]] | None = None
            for order in permutations(targets, k):
                if order and opener[order[0]] is None:
                    continue
                got, parked = self._attempt(board, order, moves, facing, (0,) * k)
                if got is None:
                    if k and parked:
                        near.append(order)
                    continue
                if best is None or len(got[0]) < len(best[0]):
                    best = got
            if best is not None:
                return best
        return self._stretched(board, moves, facing, near)

    def _stretched(self, board: _Board, moves: list[Cell], facing: int,
                   near: list[tuple[Cell, ...]]) -> tuple[list[int], list[Cell]] | None:
        """Retry the orderings that got all their clones parked and then could not walk out.

        ⛔ Why a leg is ever made LONGER than it needs to be. A clone replays its route in every
        later pass, so the route's LENGTH is when its arrival lands — and, where a route crosses
        a latching input, its length also decides the PARITY that input ends the pass on. One
        board's whole chain turns on that: the shortest first leg leaves the latch open, the
        first clone's replay then shuts it, and the third party the plan depends on is locked
        out. Three extra moves in the first leg invert it and the level falls out. This is only
        reached when the plain search has already failed, so it costs nothing elsewhere.
        """
        best: tuple[list[int], list[Cell]] | None = None
        for order in near:
            for stretch in product(range(_MAX_STRETCH + 1), repeat=len(order)):
                if not any(stretch) or self._meter[0] > _MAX_PLAN_STATES:
                    continue
                got, _ = self._attempt(board, order, moves, facing, stretch)
                if got is not None and (best is None or len(got[0]) < len(best[0])):
                    best = got
            if best is not None:
                return best
        return best

    def _run_legs(self, board: _Board, order: tuple[Cell, ...], moves: list[Cell],
                  facing: int, stretch: tuple[int, ...]
                  ) -> tuple[_World, list[int], list[Cell]] | None:
        """Park every clone of an ordering; the world it leaves behind, or None if a leg fails."""
        world = _World(board, facing, self._meter)
        actions: list[int] = []
        expect: list[Cell] = []
        for target, extra in zip(order, stretch):
            leg = self._leg(world, target, moves, board)
            if leg is None:
                return None
            if extra:
                leg = self._leg(world, target, moves, board, len(leg) + extra)
                if leg is None:
                    return None
            for step in leg:
                world.move(step)
                actions.append(self._action_of(step))
                expect.append(world.pos)
            world.rewind()
            actions.append(self._rewind or 0)
            expect.append(world.pos)
        return world, actions, expect

    def _replay(self, board: _Board, actions: list[int], facing: int) -> list[Cell] | None:
        """Run a finished plan under one heading; the positions it visits, or None if it loses."""
        world = _World(board, facing, self._meter)
        seen: list[Cell] = []
        for action in actions:
            if action == self._rewind:
                world.rewind()
            else:
                step = self._delta.get(action)
                if step is None or not world.move(step):
                    return None
            seen.append(world.pos)
        return seen if world.pos == board.exit else None

    def _attempt(self, board: _Board, order: tuple[Cell, ...], moves: list[Cell],
                 facing: int, stretch: tuple[int, ...]
                 ) -> tuple[tuple[list[int], list[Cell]] | None, bool]:
        """(plan, every-clone-parked). The second half says whether stretching is worth trying."""
        if self._meter[0] > _MAX_PLAN_STATES:
            return None, False
        got = self._run_legs(board, order, moves, facing, stretch)
        if got is None:
            return None, False
        world, actions, expect = got
        leg = self._leg(world, board.exit, moves, board)
        if leg is None:
            return None, True
        for step in leg:
            world.move(step)
            actions.append(self._action_of(step))
            expect.append(world.pos)
        return (actions, expect), True

    @staticmethod
    def _leg(world: _World, target: Cell, moves: list[Cell], board: _Board,
             at_least: int = 0) -> list[Cell] | None:
        """One leg, preferring a route that touches no input it did not come for."""
        shun = frozenset(board.buttons) - {target}
        clean = world.route(target, moves, shun, at_least)
        if clean is None:
            clean = world.route(target, moves, frozenset(), at_least)
        return clean

    # -- execution -------------------------------------------------------------

    def _advance(self, grid: np.ndarray, scene: _Scene) -> list[Step]:
        """Issue the next command, having checked the last one landed where it was meant to."""
        assert self._board is not None
        if self._plan is not None and self._expect is not None:
            if self._cursor and scene.body != self._expect[self._cursor - 1]:
                self._plan = None
            elif self._cursor < len(self._plan):
                action = self._plan[self._cursor]
                self._cursor += 1
                return self._emit(action, scene.body)
            else:
                self._plan = None
        return self._walk_out(grid, scene)

    def _walk_out(self, grid: np.ndarray, scene: _Scene) -> list[Step]:
        """The board is not where the plan said: route on the board as it is drawn right now."""
        board = read_board(grid, scene, self._span or scene.span + 1)
        if board is None:
            self._dead = True
            return []
        blocked = {door.home for door in board.doors}
        tree = _reach(board, scene.body, blocked)
        if board.exit not in tree:
            self._dead = True
            return []
        cell, route = board.exit, []
        while tree[cell] is not None:
            route.append(cell)
            cell = tree[cell]
        step = route[-1]
        delta = ((step[0] - scene.body[0]) // board.stride,
                 (step[1] - scene.body[1]) // board.stride)
        try:
            return self._emit(self._action_of(delta), scene.body)
        except StopIteration:
            self._dead = True
            return []
