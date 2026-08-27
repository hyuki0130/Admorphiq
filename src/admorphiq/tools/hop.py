"""Hop tool — a board of holes where a piece LEAPS a neighbour and takes it off.

Recovered from frames alone. The mechanic, in the order the tool has to derive it:

  * the board is a lattice of equal square holes at a constant pitch, and a hole either stands
    empty or carries one piece drawn as a glyph in its middle;
  * a piece is moved in TWO clicks — the first names the piece, and the board answers by marking
    every square it may land on; the second names one of those marks and the leap happens;
  * a leap is over ONE neighbour into the hole DIRECTLY BEYOND it, and only into a hole that is
    empty. The neighbour must be occupied; leaping into open board is refused;
  * a leap TAKES the neighbour off the board when the two pieces are of the same kind, and merely
    passes over it when they are not. Kind is the glyph's colour, and both cases exist on the
    same board, so the difference is measured rather than assumed;
  * the board is finished when ONE piece of the leading kind remains — so every leap that takes
    nothing is a leap wasted, and the plan is searched whole before the first click;
  * some boards add a TRACK: a line drawn between hole middles, and one carriage sitting on it.
    The carriage is a landable square that MOVES under the four plain actions, and it carries
    whatever piece stands on it. That is how a piece crosses a gap no leap can span.

⛔ Nothing here is written down: not the pitch, not the lattice origin, not which colour is hole,
piece, track or carriage, and not which action drives the carriage which way. Each is derived,
because a constant recovered by hand does not transfer to a board whose source we will never see.

Four derivations that are easy to get wrong, and what each cost:

  * the LANDING MARK is drawn exactly like a piece — a glyph in the middle of a hole. Reading the
    board while a piece is selected therefore invents pieces that are not there. The tool reads
    only at rest, between whole leaps, and plans from that.
  * the leading kind is the COMMONEST glyph colour, not every glyph colour. A board can carry
    pieces that are leapt over but never taken and never counted; treating them as targets makes
    the goal unreachable and the search returns nothing.
  * the carriage BREAKS the track line where it stands, so a connectivity test run on the track
    colour alone reports the track as two pieces and the carriage as stranded. The carriage's own
    pixels have to be admitted into the line before the graph is built.
  * which plain action drives the carriage which way is NOT assumed. It is learnt by taking one
    and measuring where the carriage went; an action that moves nothing teaches nothing and is
    simply not repeated at that spot.
"""

from __future__ import annotations

import heapq
from collections import deque
from typing import Any

import numpy as np

from admorphiq.tools import segment
from admorphiq.tools.base import Step, has_frame

__all__ = ["HopTool"]

Cell = tuple[int, int]


def settled(obs: Any) -> np.ndarray:
    """The LAST layer of the observation — the board once the leap has finished playing.

    Layer zero is the board BEFORE the action, so planning from it plans against a state the
    board has already left: measured, the tool re-issued the leap it had just made.
    """
    arr = np.asarray(getattr(obs, "frame", None))
    while arr.ndim > 2:
        arr = arr[-1]
    return arr.astype(np.int64)


# The four leaps, and the four ways a carriage can be driven.
_DIRS: tuple[Cell, ...] = ((0, -1), (1, 0), (0, 1), (-1, 0))

# Candidate hole sizes, widest first: the widest square that tiles at a pitch of its own is the
# board, and a narrower one is a fragment of the same tile.
_SIDES = (6, 5, 4, 3)

_MIN_HOLES = 8
_MIN_PIECES = 3
_NODE_CAP = 400_000


class _Board:
    """One reading of the board: where the holes, pieces, track and carriage are."""

    def __init__(
        self,
        origin: tuple[int, int],
        pitch: int,
        side: int,
        hole: int,
        holes: set[Cell],
        pieces: dict[Cell, int],
        track: set[Cell],
        edges: dict[Cell, set[Cell]],
        carriage: Cell | None,
        carriages: set[Cell] | None = None,
    ) -> None:
        self.origin = origin
        self.pitch = pitch
        self.side = side
        self.hole = hole
        self.holes = holes
        self.pieces = pieces
        self.track = track
        self.edges = edges
        self.carriage = carriage
        # A board may run SEVERAL carriages, and one plain action drives every one of them.
        self.carriages = set(carriages) if carriages else ({carriage} if carriage else set())

    @property
    def lead(self) -> int:
        """The commonest glyph colour — the kind whose count the board is scored on."""
        if not self.pieces:
            return -1
        tally: dict[int, int] = {}
        for colour in self.pieces.values():
            tally[colour] = tally.get(colour, 0) + 1
        return max(tally, key=lambda c: (tally[c], -c))

    def pixel(self, cell: Cell) -> tuple[int, int]:
        """The middle of a hole, which is where a click has to land."""
        x0, y0 = self.origin
        c, r = cell
        half = self.side // 2
        return x0 + self.pitch * c + half, y0 + self.pitch * r + half

    def key(self) -> tuple[Any, ...]:
        return (
            tuple(sorted(self.pieces.items())),
            self.carriage,
            tuple(sorted(self.holes)),
        )


def _uniform(block: np.ndarray) -> int | None:
    """The block's single colour, or None if it carries more than one."""
    first = int(block.flat[0])
    return first if bool((block == first).all()) else None


def _lattice(g: np.ndarray) -> tuple[int, int, int, int, int, list[Cell]] | None:
    """(x0, y0, pitch, side, hole colour, origins) of the widest square lattice in the frame."""
    grid = g.tolist()
    ignore = segment.background(grid, 1)
    for side in _SIDES:
        blocks = segment.uniform_blocks(grid, side, ignore=ignore)
        by_colour: dict[int, list[Cell]] = {}
        for origin, colour in blocks.items():
            by_colour.setdefault(colour, []).append(origin)
        best: tuple[int, int, list[Cell]] | None = None
        for colour, origins in by_colour.items():
            if len(origins) < _MIN_HOLES:
                continue
            pitch = segment.modal_pitch(origins, side)
            if pitch <= side:
                continue
            aligned = [
                o for o in origins
                if (o[0] - min(q[0] for q in origins)) % pitch == 0
                and (o[1] - min(q[1] for q in origins)) % pitch == 0
            ]
            if len(aligned) < _MIN_HOLES:
                continue
            if best is None or len(aligned) > len(best[2]):
                best = (colour, pitch, aligned)
        if best is not None:
            colour, pitch, aligned = best
            y0 = min(o[0] for o in aligned)
            x0 = min(o[1] for o in aligned)
            return x0, y0, pitch, side, colour, aligned
    return None


def _centre_span(side: int) -> tuple[int, int]:
    """(offset, width) of the middle band of a hole — 2 pixels wide when the hole is even."""
    return (side // 2 - 1, 2) if side % 2 == 0 else (side // 2, 1)


def read_board(g: np.ndarray) -> _Board | None:
    """Everything the tool knows about the board, derived from one settled frame."""
    found = _lattice(g)
    if found is None:
        return None
    x0, y0, pitch, side, hole, _ = found
    height, width = g.shape
    ignore = segment.background(g.tolist(), 1)
    off, span = _centre_span(side)

    holes: set[Cell] = set()
    pieces: dict[Cell, int] = {}
    middles: dict[Cell, int] = {}
    c_lo, c_hi = -(x0 // pitch), (width - 1 - x0) // pitch
    r_lo, r_hi = -(y0 // pitch), (height - 1 - y0) // pitch
    for r in range(r_lo, r_hi + 1):
        for c in range(c_lo, c_hi + 1):
            x, y = x0 + pitch * c, y0 + pitch * r
            if x < 0 or y < 0 or x + side > width or y + side > height:
                continue
            core = g[y:y + side, x:x + side]
            flat = _uniform(core)
            if flat == hole:
                holes.add((c, r))
                continue
            middle = _uniform(core[off:off + span, off:off + span])
            if middle is not None and middle not in ignore:
                middles[(c, r)] = middle
            colours = {int(v) for v in core.ravel()}
            if hole in colours and len(colours) == 2:
                glyph = int(next(iter(colours - {hole})))
                # ⛔ An edge-pinned COUNTER is not board content. This frame draws a step counter
                # along its top row in the HOLE's own colour, so a lattice position straddling it
                # reads as {hole, background} — two colours, exactly like a piece — and invents a
                # hole and a piece off the top of the board. It dragged the unexplored frontier
                # upward and sent the tool driving at a wall. A piece's glyph is never the
                # background, which is the difference an edge margin cannot express: the real
                # board reaches the frame edge on this family, so masking the band loses a column.
                if glyph not in ignore:
                    holes.add((c, r))
                    pieces[(c, r)] = glyph

    if len(holes) < _MIN_HOLES:
        return None

    track_colour = _track_colour(middles, holes, hole)
    track = {cell for cell, colour in middles.items() if colour == track_colour} if track_colour is not None else set()
    carriages = _carriages(middles, track, holes, track_colour)
    carriage = carriages[0] if carriages else None
    passable = (g == track_colour) if track_colour is not None else np.zeros(g.shape, dtype=bool)
    if carriages:
        track = track | set(carriages)
        blocked = ignore | {hole}
        if track_colour is not None:
            blocked = blocked | {track_colour}
        for one in carriages:
            cx, cy = (x0 + pitch * one[0] + off, y0 + pitch * one[1] + off)
            passable = passable | _carriage_mask(g, blocked, (cy, cx))
    edges = _track_edges(g, (x0, y0), pitch, side, track, passable)
    for one in carriages:
        rider = _rider(g, (x0, y0), pitch, side, one, set(pieces.values()))
        if rider is not None:
            pieces[one] = rider
    return _Board((x0, y0), pitch, side, hole, holes, pieces, track, edges, carriage, set(carriages))


def _rider(
    g: np.ndarray,
    origin: tuple[int, int],
    pitch: int,
    side: int,
    carriage: Cell,
    kinds: set[int],
) -> int | None:
    """The piece standing ON the carriage, which no hole shows because the carriage is not one."""
    if not kinds:
        return None
    x0, y0 = origin
    x, y = x0 + pitch * carriage[0], y0 + pitch * carriage[1]
    if y < 0 or x < 0 or y + side > g.shape[0] or x + side > g.shape[1]:
        return None
    core = g[y:y + side, x:x + side]
    present = {c: int((core == c).sum()) for c in kinds}
    best = max(present, key=lambda c: present[c])
    return best if present[best] >= side else None


def _track_colour(middles: dict[Cell, int], holes: set[Cell], hole: int) -> int | None:
    """The line's colour: the commonest middle among squares that are not holes."""
    tally: dict[int, int] = {}
    for cell, colour in middles.items():
        if cell in holes or colour == hole:
            continue
        tally[colour] = tally.get(colour, 0) + 1
    if not tally:
        return None
    colour = max(tally, key=lambda c: (tally[c], -c))
    return colour if tally[colour] >= 3 else None


def _carriages(
    middles: dict[Cell, int], track: set[Cell], holes: set[Cell], track_colour: int | None
) -> list[Cell]:
    """The one square standing ON the line whose middle is neither line nor hole.

    Scored by how much line it touches, so a stray square that merely brushes the track cannot
    be mistaken for the carriage that sits in the middle of it.
    """
    if track_colour is None:
        return []
    found: list[tuple[int, Cell]] = []
    for cell, colour in sorted(middles.items()):
        if cell in track or cell in holes or colour == track_colour:
            continue
        touching = sum(1 for d in _DIRS if (cell[0] + d[0], cell[1] + d[1]) in track)
        if touching:
            found.append((touching, cell))
    return [cell for _, cell in sorted(found, key=lambda t: (-t[0], t[1]))]


def _carriage_mask(g: np.ndarray, board_colours: set[int], seed: tuple[int, int]) -> np.ndarray:
    """The carriage's own pixels, flooded from its middle.

    The carriage BREAKS the line where it stands: a band test run on the line colour alone finds
    the two halves of the track unreachable from each other and the carriage stranded on neither.
    """
    height, width = g.shape
    mask = np.zeros(g.shape, dtype=bool)
    sy, sx = seed
    if not (0 <= sy < height and 0 <= sx < width) or int(g[sy, sx]) in board_colours:
        return mask
    stack = [(sy, sx)]
    mask[sy, sx] = True
    while stack:
        y, x = stack.pop()
        for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
            if 0 <= ny < height and 0 <= nx < width and not mask[ny, nx] \
                    and int(g[ny, nx]) not in board_colours:
                mask[ny, nx] = True
                stack.append((ny, nx))
    return mask


def _track_edges(
    g: np.ndarray,
    origin: tuple[int, int],
    pitch: int,
    side: int,
    track: set[Cell],
    passable: np.ndarray,
) -> dict[Cell, set[Cell]]:
    """Which line squares the carriage can roll between — the band between middles must be line."""
    edges: dict[Cell, set[Cell]] = {cell: set() for cell in track}
    x0, y0 = origin
    off, span = _centre_span(side)
    for cell in sorted(track):
        for d in ((1, 0), (0, 1)):
            other = (cell[0] + d[0], cell[1] + d[1])
            if other not in track:
                continue
            ax = x0 + pitch * cell[0] + off
            ay = y0 + pitch * cell[1] + off
            bx = x0 + pitch * other[0] + off
            by = y0 + pitch * other[1] + off
            band = passable[ay:by + span, ax:bx + span]
            if band.size and bool(band.all()):
                edges[cell].add(other)
                edges[other].add(cell)
    return edges


# --- boards larger than the window -----------------------------------------
#
# Measured: only the first two boards of this family fit inside the frame. Every later one is
# wider or taller than 64 pixels (one is 168 wide), and the view is moved ONLY as a side effect
# of driving a carriage that carries a piece. So from the third board on the tool is looking
# through a moving window at something it has never seen whole, and a plan computed on what is
# visible is a plan for a different position.
#
# The answer is a WORLD map in pixels. The scroll step is 8 pixels on a 6-pixel lattice, so a
# scroll is not a whole number of cells and cell identity survives only by carrying the offset
# in pixels and converting at the edges.


def scroll_offset(prev: np.ndarray, cur: np.ndarray, span: int = 48) -> tuple[int, int]:
    """How far the view moved between two settled frames, by pixel agreement.

    Axis-aligned only, and the score is penalised by distance so a still frame reads as no
    movement rather than as a large shift that happens to align a repetitive lattice.
    """
    best, best_score = (0, 0), -1
    for dx in range(-span, span + 1):
        for dy in ((0,) if dx else range(-span, span + 1)):
            a = prev[max(0, dy):prev.shape[0] + min(0, dy), max(0, dx):prev.shape[1] + min(0, dx)]
            b = cur[max(0, -dy):cur.shape[0] + min(0, -dy), max(0, -dx):cur.shape[1] + min(0, -dx)]
            if a.size < prev.size // 3 or a.shape != b.shape:
                continue
            score = int((a == b).sum()) - abs(dx) - abs(dy)
            if score > best_score:
                best_score, best = score, (dx, dy)
    return best


def truncated(board: _Board, shape: tuple[int, int]) -> bool:
    """Does the board run off the edge of the frame?

    A hole whose lattice NEIGHBOUR would fall outside the frame proves nothing about what is
    beyond it — the board may continue or may not. Only a board ringed by in-frame lattice
    positions has been seen whole.
    """
    height, width = shape
    x0, y0 = board.origin
    for c, r in board.holes:
        for d in _DIRS:
            x = x0 + board.pitch * (c + d[0])
            y = y0 + board.pitch * (r + d[1])
            if x < 0 or y < 0 or x + board.side > width or y + board.side > height:
                return True
    return False


class _World:
    """Everything seen so far, in world cells, with the window's offset carried in pixels."""

    def __init__(self, board: _Board, shape: tuple[int, int]) -> None:
        self.origin = board.origin
        self.pitch = board.pitch
        self.side = board.side
        self.shape = shape
        self.holes: set[Cell] = set()
        self.rail: set[Cell] = set()
        self.seen: set[Cell] = set()
        self.pieces: dict[Cell, int] = {}
        self.carriages: set[Cell] = set()
        self.cam: tuple[int, int] = (0, 0)
        self.pan: tuple[int, int] | None = None
        self.merge(board)

    # -- geometry -------------------------------------------------------------

    def screen(self, cell: Cell, cam: tuple[int, int] | None = None) -> tuple[int, int]:
        cx, cy = self.cam if cam is None else cam
        return self.origin[0] + self.pitch * cell[0] - cx, self.origin[1] + self.pitch * cell[1] - cy

    def visible(self, cell: Cell, cam: tuple[int, int] | None = None) -> bool:
        x, y = self.screen(cell, cam)
        return x >= 0 and y >= 0 and x + self.side <= self.shape[1] and y + self.side <= self.shape[0]

    def pixel(self, cell: Cell) -> tuple[int, int]:
        x, y = self.screen(cell)
        return x + self.side // 2, y + self.side // 2

    def _to_world(self, cell: Cell) -> Cell:
        """A cell index read off the current frame, expressed in the world's own indices."""
        return (cell[0] + self.cam[0] // self.pitch, cell[1] + self.cam[1] // self.pitch)

    # -- accumulation ---------------------------------------------------------

    def merge(self, board: _Board) -> None:
        """Fold one reading in. Terrain accumulates; pieces are only trusted where visible."""
        shift = ((self.cam[0] - (self.origin[0] - board.origin[0])) // self.pitch,
                 (self.cam[1] - (self.origin[1] - board.origin[1])) // self.pitch)
        def w(cell: Cell) -> Cell:
            return (cell[0] + shift[0], cell[1] + shift[1])

        for cell in board.holes:
            self.holes.add(w(cell))
        for cell in board.track:
            self.rail.add(w(cell))
        # SEEN is every lattice position the window covers, not merely the occupied ones: an
        # empty position that has been looked at is knowledge, and counting only occupied ones
        # leaves every blank inside the window permanently "unexplored", which satisfies the
        # frontier where it stands and asks for no scroll at all.
        window = self.covered()
        self.seen |= window
        for cell in window:
            self.pieces.pop(cell, None)
        for cell, colour in board.pieces.items():
            self.pieces[w(cell)] = colour
        if board.carriages:
            self.carriages = {c for c in self.carriages if not self.visible(c)}
            self.carriages |= {w(c) for c in board.carriages}

    def advance(self, offset: tuple[int, int]) -> None:
        self.cam = (self.cam[0] + offset[0], self.cam[1] + offset[1])

    @property
    def lead(self) -> int:
        if not self.pieces:
            return -1
        tally: dict[int, int] = {}
        for colour in self.pieces.values():
            tally[colour] = tally.get(colour, 0) + 1
        return max(tally, key=lambda c: (tally[c], -c))

    def covered(self, cam: tuple[int, int] | None = None) -> set[Cell]:
        """Every lattice position wholly inside the window at this scroll."""
        cx, cy = self.cam if cam is None else cam
        x0, y0 = self.origin
        height, width = self.shape
        c_lo = -((x0 - cx) // self.pitch)
        r_lo = -((y0 - cy) // self.pitch)
        out: set[Cell] = set()
        for c in range(c_lo - 1, c_lo + width // self.pitch + 2):
            for r in range(r_lo - 1, r_lo + height // self.pitch + 2):
                if self.visible((c, r), (cx, cy)):
                    out.add((c, r))
        return out

    def frontier(self) -> set[Cell]:
        """Lattice positions touching known board that the window has never covered."""
        edge: set[Cell] = set()
        for cell in self.holes | self.rail:
            for d in _DIRS:
                other = (cell[0] + d[0], cell[1] + d[1])
                if other not in self.seen:
                    edge.add(other)
        return edge


# --- the plan ---------------------------------------------------------------

# A primitive is either ("leap", from_cell, direction) or ("roll", direction).
Move = tuple[str, Any, Cell]


def _leaps(pieces: dict[Cell, int], holes: set[Cell], carriage: Cell | None) -> list[Move]:
    out: list[Move] = []
    for cell, colour in pieces.items():
        for d in _DIRS:
            mid = (cell[0] + d[0], cell[1] + d[1])
            land = (mid[0] + d[0], mid[1] + d[1])
            if mid not in pieces or land in pieces:
                continue
            if land not in holes and land != carriage:
                continue
            out.append(("leap", cell, d))
    return out


def _after_leap(
    pieces: dict[Cell, int], cell: Cell, d: Cell
) -> dict[Cell, int]:
    mid = (cell[0] + d[0], cell[1] + d[1])
    land = (mid[0] + d[0], mid[1] + d[1])
    colour = pieces[cell]
    out = dict(pieces)
    del out[cell]
    if out.get(mid) == colour:
        del out[mid]
    out[land] = colour
    return out


def _rolls(carriage: Cell | None, edges: dict[Cell, set[Cell]]) -> list[Move]:
    if carriage is None:
        return []
    return [
        ("roll", None, d)
        for d in _DIRS
        if (carriage[0] + d[0], carriage[1] + d[1]) in edges.get(carriage, set())
    ]


def solve(board: _Board, node_cap: int = _NODE_CAP) -> list[Move] | None:
    """Cheapest run of leaps and rolls that leaves ONE piece of the leading kind."""
    lead = board.lead
    if lead < 0:
        return None
    start_pieces = dict(board.pieces)
    if sum(1 for c in start_pieces.values() if c == lead) <= 1:
        return []

    def state_of(pieces: dict[Cell, int], carriage: Cell | None) -> tuple[Any, ...]:
        return (tuple(sorted(pieces.items())), carriage)

    def heuristic(pieces: dict[Cell, int]) -> int:
        return 2 * max(0, sum(1 for c in pieces.values() if c == lead) - 1)

    start = state_of(start_pieces, board.carriage)
    seen: dict[tuple[Any, ...], int] = {start: 0}
    came: dict[tuple[Any, ...], tuple[tuple[Any, ...], Move]] = {}
    heap: list[tuple[int, int, tuple[Any, ...], dict[Cell, int], Cell | None]] = [
        (heuristic(start_pieces), 0, start, start_pieces, board.carriage)
    ]
    expanded = 0
    while heap and expanded < node_cap:
        _, cost, state, pieces, carriage = heapq.heappop(heap)
        if cost > seen.get(state, cost):
            continue
        expanded += 1
        if sum(1 for c in pieces.values() if c == lead) == 1:
            plan: list[Move] = []
            while state in came:
                state, move = came[state]
                plan.append(move)
            return plan[::-1]
        for move in _leaps(pieces, board.holes, carriage):
            nxt = _after_leap(pieces, move[1], move[2])
            key = state_of(nxt, carriage)
            if cost + 2 < seen.get(key, 1 << 30):
                seen[key] = cost + 2
                came[key] = (state, move)
                heapq.heappush(heap, (cost + 2 + heuristic(nxt), cost + 2, key, nxt, carriage))
        for move in _rolls(carriage, board.edges):
            assert carriage is not None
            d = move[2]
            landed = (carriage[0] + d[0], carriage[1] + d[1])
            nxt = dict(pieces)
            if carriage in nxt:
                nxt[landed] = nxt.pop(carriage)
            key = state_of(nxt, landed)
            if cost + 1 < seen.get(key, 1 << 30):
                seen[key] = cost + 1
                came[key] = (state, move)
                heapq.heappush(heap, (cost + 1 + heuristic(nxt), cost + 1, key, nxt, landed))
    return None


def reachable_track(board: _Board) -> set[Cell]:
    """Which line squares the carriage can actually get to — used only for reporting."""
    if board.carriage is None:
        return set()
    seen = {board.carriage}
    queue = deque([board.carriage])
    while queue:
        cell = queue.popleft()
        for other in board.edges.get(cell, ()):
            if other not in seen:
                seen.add(other)
                queue.append(other)
    return seen


def _world_steps(w: "_World", pieces: dict[Cell, int], carts: frozenset[Cell],
                 cam: tuple[int, int]) -> list[tuple[int, dict[Cell, int], frozenset[Cell],
                                                     tuple[int, int], Move]]:
    """Every legal action from a world state, with the window and the scroll obeyed."""
    out = []
    for a, colour in pieces.items():
        if not w.visible(a, cam):
            continue                      # a piece off the window cannot be clicked
        for d in _DIRS:
            mid = (a[0] + d[0], a[1] + d[1])
            land = (mid[0] + d[0], mid[1] + d[1])
            if mid not in pieces or land in pieces:
                continue
            if land not in w.holes and land not in carts:
                continue
            if not w.visible(land, cam):
                continue                  # nor can its landing mark be clicked
            nxt = dict(pieces)
            del nxt[a]
            if nxt.get(mid) == colour:
                del nxt[mid]
            nxt[land] = colour
            out.append((2, nxt, carts, cam, ("leap", a, d)))
    lead = w.lead
    for d in _DIRS:
        nxt, seats, moved, panned = dict(pieces), set(carts), False, False
        order = sorted(carts, key=lambda c: c[0] * d[0] + c[1] * d[1], reverse=True)
        ncam = cam
        for cart in order:
            tgt = (cart[0] + d[0], cart[1] + d[1])
            if tgt in seats or tgt not in w.rail:
                continue
            laden = nxt.get(cart) == lead
            seats.discard(cart)
            seats.add(tgt)
            moved = True
            if cart in nxt:
                nxt[tgt] = nxt.pop(cart)
            if laden and not panned and w.pan is not None:
                panned = True
                step = (ncam[0] + w.pan[0] * d[0], ncam[1] + w.pan[1] * d[1])
                if step[0] < 0 or step[1] < 0:
                    # The view is already home; the engine moves THIS carriage, refuses the
                    # scroll and abandons the rest of the action.
                    break
                ncam = step
        if moved:
            out.append((1, nxt, frozenset(seats), ncam, ("roll", None, d)))
    return out


def solve_world(w: "_World", goal: str, node_cap: int = 200_000) -> list[Move] | None:
    """Cheapest run of actions that either finishes the board or shows it something new."""
    lead = w.lead
    if lead < 0:
        return None
    edge = w.frontier() if goal == "reveal" else set()
    if goal == "reveal" and not edge:
        return None
    if goal == "laden" and not w.carriages:
        return None

    def done(pieces: dict[Cell, int], carts: frozenset[Cell], cam: tuple[int, int]) -> bool:
        if goal == "win":
            return sum(1 for c in pieces.values() if c == lead) == 1
        if goal == "laden":
            return any(pieces.get(seat) == lead for seat in carts)
        return any(w.visible(cell, cam) for cell in edge)

    def hint(pieces: dict[Cell, int]) -> int:
        if goal != "win":
            return 0
        return 2 * max(0, sum(1 for c in pieces.values() if c == lead) - 1)

    start_pieces, start_carts, start_cam = dict(w.pieces), frozenset(w.carriages), w.cam
    if done(start_pieces, start_carts, start_cam):
        return []
    start = (tuple(sorted(start_pieces.items())), start_carts, start_cam)
    seen: dict[Any, int] = {start: 0}
    came: dict[Any, tuple[Any, Move]] = {}
    heap = [(hint(start_pieces), 0, start, start_pieces, start_carts, start_cam)]
    expanded = 0
    while heap and expanded < node_cap:
        _, cost, state, pieces, carts, cam = heapq.heappop(heap)
        if cost > seen.get(state, cost):
            continue
        expanded += 1
        if done(pieces, carts, cam):
            plan: list[Move] = []
            while state in came:
                state, move = came[state]
                plan.append(move)
            return plan[::-1]
        for step, nxt, seats, ncam, move in _world_steps(w, pieces, carts, cam):
            key = (tuple(sorted(nxt.items())), seats, ncam)
            if cost + step < seen.get(key, 1 << 30):
                seen[key] = cost + step
                came[key] = (state, move)
                heapq.heappush(heap, (cost + step + hint(nxt), cost + step, key, nxt, seats, ncam))
    return None


def _toward(w: "_World") -> Cell | None:
    """The way the board continues: from what is known toward what has never been in view."""
    edge = w.frontier()
    known = w.holes | w.rail
    if not edge or not known:
        return None
    kc = sum(c for c, _ in known) / len(known), sum(r for _, r in known) / len(known)
    ec = sum(c for c, _ in edge) / len(edge), sum(r for _, r in edge) / len(edge)
    dx, dy = ec[0] - kc[0], ec[1] - kc[1]
    if abs(dx) >= abs(dy):
        return (1, 0) if dx > 0 else (-1, 0)
    return (0, 1) if dy > 0 else (0, -1)


class HopTool:
    """Plans a whole board of leaps before the first click, then drives the carriage."""

    name = "hop"

    def __init__(self) -> None:
        self._plan: list[Move] = []
        self._at: tuple[Any, ...] | None = None
        self._drive: dict[int, Cell] = {}
        self._tried: dict[Cell | None, set[int]] = {}
        self._probe: tuple[int, Cell | None] | None = None
        self._failed: set[tuple[Any, ...]] = set()
        self._world: _World | None = None
        self._prev: np.ndarray | None = None
        self._rolled: tuple[int, frozenset[Cell]] | None = None

    # --- lifecycle ---------------------------------------------------------

    def detect(self, frames: list[Any], obs: Any) -> float:
        """Bid only when the leap rule reads off the frame AND a whole plan exists."""
        if not has_frame(obs):
            return 0.0
        board = read_board(settled(obs))
        if board is None or len(board.pieces) < _MIN_PIECES:
            return 0.0
        if not _leaps(board.pieces, board.holes, board.carriage):
            return 0.0
        plan = solve(board, node_cap=60_000)
        if not plan:
            return 0.0
        return 0.88

    def reset(self) -> None:
        self._plan = []
        self._at = None
        self._tried = {}
        self._probe = None
        self._failed = set()
        self._world = None
        self._prev = None
        self._rolled = None

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """Nothing is learnt here.

        What the tool has to learn is which plain action rolls the carriage which way, and that
        is recorded where the action is ISSUED — in `propose` — so the lesson does not depend on
        a caller choosing to report the transition back.
        """

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        if not has_frame(obs):
            return []
        frame = settled(obs)
        board = read_board(frame)
        if board is None:
            return []
        if self._world is not None or truncated(board, frame.shape):
            return self._through_window(board, frame)
        self._learn_drive(board)

        key = board.key()
        if key in self._failed:
            return []
        if self._at != key or not self._plan:
            plan = solve(board)
            if not plan:
                # A board the search has exhausted stays exhausted; re-searching it every call
                # spends the caller's time for an answer already known.
                self._failed.add(key)
                return []
            self._plan = plan
            self._at = key

        move = self._plan[0]
        if move[0] == "leap":
            self._plan = self._plan[1:]
            cell, d = move[1], move[2]
            land = (cell[0] + 2 * d[0], cell[1] + 2 * d[1])
            self._at = None
            return [(6, board.pixel(cell)), (6, board.pixel(land))]

        action = self._action_for(move[2], board)
        if action is None:
            return []
        self._plan = self._plan[1:]
        self._at = None
        self._probe = (action, board.carriage)
        return [(action, None)]

    # --- boards larger than the window -------------------------------------

    def _through_window(self, board: _Board, frame: np.ndarray) -> list[Step]:
        """Carry a map across the scroll, because this board is never on screen whole."""
        if self._world is None:
            self._world = _World(board, frame.shape)
        else:
            assert self._prev is not None
            moved = scroll_offset(self._prev, frame)
            self._world.advance(moved)
            # Merge BEFORE reading the lesson: the carriages have to be where the frame says
            # they now are, or the comparison is the old set against itself and teaches nothing.
            self._world.merge(board)
            self._learn_scroll(moved)
        self._prev = frame

        w = self._world
        plan = solve_world(w, "win")
        if plan is None and w.pan is None:
            # The scroll cannot be planned before it has been SEEN. Put a piece on a carriage,
            # drive it at the unexplored side once, and measure what the view does.
            if any(w.pieces.get(seat) == w.lead for seat in w.carriages):
                d = _toward(w)
                action = self._roll_action(d) if d else None
                if action is not None:
                    self._rolled = (action, frozenset(w.carriages))
                    return [(action, None)]
            else:
                plan = solve_world(w, "laden")
        if plan is None:
            plan = solve_world(w, "reveal")
        if not plan:
            return []
        move = plan[0]
        if move[0] == "leap":
            cell, d = move[1], move[2]
            land = (cell[0] + 2 * d[0], cell[1] + 2 * d[1])
            return [(6, w.pixel(cell)), (6, w.pixel(land))]
        action = self._roll_action(move[2])
        if action is None:
            return []
        self._rolled = (action, frozenset(w.carriages))
        return [(action, None)]

    def _learn_scroll(self, moved: tuple[int, int]) -> None:
        """Name the direction the last plain action drove the carriages, and what it scrolled.

        Both lessons come from the SAME transition: how far the carriages stepped names the
        action's direction, and how far the view slid names the scroll that riding one costs.
        """
        assert self._world is not None
        if self._rolled is None:
            return
        action, before = self._rolled
        self._rolled = None
        after = self._world.carriages
        if len(before) != len(after) or before == after:
            self._tried.setdefault(None, set()).add(action)
            return
        shifts = {(b[0] - a[0], b[1] - a[1])
                  for a, b in zip(sorted(before), sorted(after), strict=False)}
        if len(shifts) != 1:
            return
        step = next(iter(shifts))
        if step not in _DIRS:
            return
        self._drive[action] = step
        if moved != (0, 0) and self._world.pan is None:
            self._world.pan = (moved[0] // step[0] if step[0] else 0,
                               moved[1] // step[1] if step[1] else 0)

    def _roll_action(self, d: Cell) -> int | None:
        for action, step in sorted(self._drive.items()):
            if step == d:
                return action
        spent = self._tried.get(None, set())
        for action in (1, 2, 3, 4):
            if action not in self._drive and action not in spent:
                return action
        return None

    # --- driving the carriage ---------------------------------------------

    def _learn_drive(self, board: _Board) -> None:
        """Name the direction of the action just taken by where the carriage ended up."""
        if self._probe is None:
            return
        action, before = self._probe
        self._probe = None
        after = board.carriage
        if before is None or after is None or before == after:
            self._tried.setdefault(before, set()).add(action)
            return
        step = (after[0] - before[0], after[1] - before[1])
        if step in _DIRS:
            self._drive[action] = step

    def _action_for(self, d: Cell, board: _Board) -> int | None:
        """The action known to roll the carriage this way, or one not yet ruled out here."""
        for action, step in sorted(self._drive.items()):
            if step == d:
                return action
        spent = self._tried.get(board.carriage, set())
        for action in (1, 2, 3, 4):
            if action not in self._drive and action not in spent:
                return action
        return None
