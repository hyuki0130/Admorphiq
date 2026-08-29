"""Peg-jump tool — solitaire capture on a lattice of sockets, with rail-borne carriers.

The mechanic, recovered from the game's own source and then re-derived from frames so that
nothing game-specific is written down:

  * the board is a lattice of equal cells at a constant pitch; a cell is a SOCKET (a hole a
    piece may rest in), a RAIL (a track segment), or nothing;
  * a socket carries at most one occupant: a PIECE (a disc drawn inside it, in one of several
    colours) or a BLOCKER (art that fills the socket and never moves on its own);
  * a piece MOVES only by jumping: over an adjacent OCCUPIED cell, landing two cells away in a
    socket that is empty. Every other landing is refused;
  * a jump CAPTURES the cell it passed over only when that cell holds a piece of the SAME
    colour. Jumping a blocker, or a piece of another colour, moves the jumper and leaves the
    jumped cell standing — so blockers and foreign pieces are permanent stepping stones;
  * a minority of sockets are CARRIERS sitting on the rail network. Each simple action shifts
    every carrier one cell along the rails, carrying whatever rests on it. A carrier is also a
    legal LANDING, which is how a piece crosses a gap the lattice does not bridge;
  * the level is won when every capturable colour is down to a single piece.

⛔ The carrier is the part a black-box prober cannot find, and it is what stops the generic
searcher four levels in. A carrier's cell is the only landing that exists across a rail gap, and
it only becomes a landing once the carrier has been DRIVEN there — so the plan reads "drive the
carrier under the jump, then jump", a two-mechanism composition no single-action probe reaches.

⛔ THE FRAME LAGS THE BOARD, and reading it as truth is what broke the first version. A jump is
ANIMATED: the engine returns the first frame of the animation, so the board that comes back after
a capture still shows the captured piece standing where it was. The first version re-planned off
that frame, "confirmed" its own stale expectation, and played the second half of a plan into a
board that had already moved on. The fix is that the SIMULATION is the belief and the frame is
only evidence: a frame that reproduces a state this tool has already left is recognised as stale
and ignored, a frame that matches nothing it predicted means the model is wrong and is adopted
wholesale, and the frame's only other job is to say where the lattice currently sits on screen.

⛔ The lattice MOVES. Several boards are wider than the screen and pan when a piece reaches a
particular cell, so pixel coordinates computed one action ago can be wrong. Geometry is therefore
re-anchored every turn by aligning the fixed part of the board — sockets and rails, which no move
changes — against the map built so far, and the offset that alignment returns also folds newly
revealed territory into the map. When no whole-cell alignment exists the board is mid-pan and the
tool spends an inert click — bounded, then it withdraws — rather than clicking into a frame whose
cells it cannot place.

⛔ Nothing here is a constant. The pitch, the lattice phase, which colour is a socket, which is a
piece, which is a rail, and which action id points which way are all derived or learned. Two of
them cost a measurement first:

  * the four action ids are NOT assumed to be up/down/left/right in any order that could be
    written down — the tool drives one untried action and reads the carriers' displacement out
    of the next frame. That is one action, once per game, and only when a plan needs a carrier;
  * one colour of piece cannot be captured at all. No frame distinguishes it, so it is LEARNED:
    a jump the model says should capture, which leaves the piece count unchanged, retires that
    colour from the goal.

⛔ Planning is THREE TIERS, in this order, and the order is the point. (1) Uniform-cost search
for the whole level, or failing that for the next capture — a capture is irreversible, so the
shortest route to one is always worth taking. (2) When no capture is reachable, the map is
INCOMPLETE, not the board unsolvable: put a piece where the map runs out, because a board wider
than the screen only shows its far side once something is carried there. (3) When even that
cannot improve, move a piece somewhere it has never stood, because some boards open only on a
particular cell being reached. Tier 2 is allowed to run only while looking still finds board;
three barren sweeps and this tool bids ZERO and hands the level to whatever comes next, which is
how it takes the levels it can solve without holding the ones it cannot.

⛔ Selectivity. `detect` runs the whole planner and returns 0.0 unless the search actually finds
a capture or a full solution on THIS board. A lattice of sockets with pieces in it is not enough
evidence — several sample games draw one. Measured over 1,920 frames of the other 24 sample
games (80 frames each, random play): ZERO non-zero bids.
"""

from __future__ import annotations

import heapq
from collections import Counter
from typing import Any

import numpy as np

from admorphiq.tools.base import Step, availability, frame_2d, has_frame

__all__ = ["PegJumpTool", "Board", "read_board", "plan_moves", "railhead_moves",
           "runs_offscreen", "capture_reachable"]

Cell = tuple[int, int]          # (row, col) on the lattice
Delta = tuple[int, int]

DIRS: tuple[Delta, ...] = ((-1, 0), (1, 0), (0, -1), (0, 1))

# A socket is a flat square ringed by another colour; a piece is a disc inside it. Four pixels is
# the smallest square that carries a disc with corners still showing.
_INNER = 4
_MIN_PITCH = _INNER + 1
_MAX_PITCH = 16
_MIN_CELLS = 8
_NODE_CAP = 120_000
_HISTORY = 8
_LOOKAHEAD = 8
_REACH_CAP = 25_000


# --------------------------------------------------------------------------- perception

def _ring_and_inner(g: np.ndarray, y: int, x: int) -> tuple[np.ndarray, np.ndarray]:
    """A cell's inner square and the band of pixels immediately around it."""
    inner = g[y:y + _INNER, x:x + _INNER]
    outer = g[y - 1:y + _INNER + 1, x - 1:x + _INNER + 1]
    mask = np.ones(outer.shape, dtype=bool)
    mask[1:1 + _INNER, 1:1 + _INNER] = False
    return inner, outer[mask]


def _disc(inner: np.ndarray) -> tuple[int, int] | None:
    """(piece colour, socket colour) when the square holds a disc, else None.

    A disc leaves the four corners of the socket showing and fills the other twelve cells, which
    is what "round thing drawn inside a square hole" looks like at this size. Read as a shape,
    never as a colour.
    """
    corners = {int(inner[0, 0]), int(inner[0, -1]), int(inner[-1, 0]), int(inner[-1, -1])}
    if len(corners) != 1:
        return None
    body = inner.astype(int).copy()
    body[0, 0] = body[0, -1] = body[-1, 0] = body[-1, -1] = -1
    vals = {int(v) for v in body.ravel() if v >= 0}
    if len(vals) != 1:
        return None
    c = vals.pop()
    h = corners.pop()
    return (c, h) if c != h else None


def _anchors(g: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Every socket-shaped square: (y, x, socket colour, piece colour or -1)."""
    h, w = g.shape
    out: list[tuple[int, int, int, int]] = []
    for y in range(1, h - _INNER):
        for x in range(1, w - _INNER):
            inner, ring = _ring_and_inner(g, y, x)
            rv = {int(v) for v in ring}
            if len(rv) != 1:
                continue
            border = rv.pop()
            flat = {int(v) for v in inner.ravel()}
            if len(flat) == 1:
                c = flat.pop()
                if c != border:
                    out.append((y, x, c, -1))
                continue
            d = _disc(inner)
            if d is not None and d[1] != border:
                out.append((y, x, d[1], d[0]))
    return out


def _lattice(anchors: list[tuple[int, int, int, int]]) -> tuple[int, int, int] | None:
    """(pitch, y phase, x phase) — the step is the COMMONEST gap, never the smallest."""
    gaps: Counter[int] = Counter()
    for axis in (0, 1):
        vals = sorted({a[axis] for a in anchors})
        for p, q in zip(vals, vals[1:]):
            if _MIN_PITCH <= q - p <= _MAX_PITCH:
                gaps[q - p] += 1
    if not gaps:
        return None
    pitch = gaps.most_common(1)[0][0]
    ph_y = Counter(a[0] % pitch for a in anchors).most_common(1)[0][0]
    ph_x = Counter(a[1] % pitch for a in anchors).most_common(1)[0][0]
    return pitch, ph_y, ph_x


class Board:
    """One frame's reading of the lattice — sockets, carriers, rails, pieces, blockers."""

    def __init__(self, pitch: int, oy: int, ox: int) -> None:
        self.pitch = pitch
        self.oy = oy                 # pixel row of cell (0, 0)'s inner square
        self.ox = ox
        self.sockets: set[Cell] = set()
        self.carriers: set[Cell] = set()
        self.rails: set[Cell] = set()
        self.pieces: dict[Cell, int] = {}
        self.blockers: set[Cell] = set()
        # Pieces caught between lattice cells — the board is still animating.
        self.moving = 0
        # Every cell the frame could show. Anything outside it is not absent, only off screen.
        self.window: set[Cell] = set()

    def fixed(self) -> set[Cell]:
        """The part of the board no move can change — what alignment is matched on."""
        return self.sockets | self.rails


def read_board(g: np.ndarray) -> Board | None:
    """Recover a board from one frame, or None when this is not that kind of board."""
    anchors = _anchors(g)
    if len(anchors) < _MIN_CELLS:
        return None
    lat = _lattice(anchors)
    if lat is None:
        return None
    pitch, ph_y, ph_x = lat
    on_phase = [a for a in anchors if a[0] % pitch == ph_y and a[1] % pitch == ph_x]
    # ⛔ A piece in flight is drawn BETWEEN cells, so it lands off the lattice phase. Counting
    # those is the only reliable "the board has not settled yet" signal: the piece count, the
    # frame hash and the changed flag all read as a perfectly ordinary board mid-animation, and
    # believing one cost this tool its whole plan on the first level.
    off_phase = sum(1 for a in anchors if a[3] >= 0 and a not in on_phase)
    anchors = on_phase
    if len(anchors) < _MIN_CELLS:
        return None

    socket_counts = Counter(a[2] for a in anchors)
    piece_colours = {a[3] for a in anchors if a[3] >= 0} - set(socket_counts)
    if not socket_counts:
        return None
    # The commonest socket colour is the fixed board; a socket drawn any other way rides.
    fixed_colour = socket_counts.most_common(1)[0][0]

    h, w = g.shape
    bg = int(Counter(int(v) for v in g.ravel()).most_common(1)[0][0])
    y0 = min(a[0] for a in anchors)
    x0 = min(a[1] for a in anchors)
    base_y = y0 - ((y0 - 1) // pitch) * pitch
    base_x = x0 - ((x0 - 1) // pitch) * pitch
    board = Board(pitch, base_y, base_x)
    board.moving = off_phase

    raw: dict[Cell, tuple[np.ndarray, np.ndarray]] = {}
    r = 0
    while base_y + r * pitch + _INNER <= h - 1:
        c = 0
        while base_x + c * pitch + _INNER <= w - 1:
            raw[(r, c)] = _ring_and_inner(g, base_y + r * pitch, base_x + c * pitch)
            c += 1
        r += 1

    board.window = set(raw)
    rail_votes: Counter[int] = Counter()
    for cell, (inner, ring) in raw.items():
        rv = {int(v) for v in ring}
        flat = {int(v) for v in inner.ravel()}
        if len(rv) == 1 and len(flat) == 1 and flat != rv:
            colour = flat.pop()
            if colour in socket_counts:
                (board.sockets if colour == fixed_colour else board.carriers).add(cell)
                continue
        if len(rv) == 1:
            d = _disc(inner)
            if d is not None and d[1] in socket_counts and d[0] in piece_colours:
                (board.sockets if d[1] == fixed_colour else board.carriers).add(cell)
                board.pieces[cell] = d[0]
                continue
        mid = {int(v) for v in inner[1:3, 1:3].ravel()}
        if len(mid) == 1:
            colour = mid.pop()
            if colour != bg and colour not in socket_counts and colour not in piece_colours:
                rail_votes[colour] += 1
        if int((inner != bg).sum()) >= _INNER * _INNER - 2:
            board.blockers.add(cell)

    if rail_votes:
        rail_colour = rail_votes.most_common(1)[0][0]
        for cell, (inner, _ring) in raw.items():
            if {int(v) for v in inner[1:3, 1:3].ravel()} == {rail_colour}:
                board.rails.add(cell)
                board.blockers.discard(cell)
    # A carrier reached its cell along the rails, so its cell carries one.
    board.rails |= board.carriers
    board.blockers -= set(board.pieces)
    board.blockers -= board.sockets
    if len(board.sockets) + len(board.carriers) < _MIN_CELLS:
        return None
    return board


# --------------------------------------------------------------------------- the model

class Model:
    """The board as the planner believes it to be, in coordinates fixed at the level's start."""

    def __init__(self) -> None:
        self.sockets: set[Cell] = set()
        self.rails: set[Cell] = set()
        self.pieces: dict[Cell, int] = {}
        self.carriers: set[Cell] = set()
        self.blockers: set[Cell] = set()
        self.pitch = 0
        self.oy = 0                  # pixel of world cell (0, 0), refreshed on every alignment
        self.ox = 0
        # The part of the world the screen is showing right now.
        self.window: set[Cell] = set()

    def state(self) -> tuple[Any, ...]:
        return (tuple(sorted(self.pieces.items())), tuple(sorted(self.carriers)),
                tuple(sorted(self.blockers)))

    def pixel(self, cell: Cell) -> tuple[int, int]:
        off = _INNER // 2
        return (self.ox + cell[1] * self.pitch + off, self.oy + cell[0] * self.pitch + off)


def _restrict(state: tuple[Any, ...], window: set[Cell]) -> tuple[Any, ...]:
    """The part of a state the screen can currently see — the only part a frame can confirm."""
    return (tuple((c, v) for c, v in state[0] if c in window),
            tuple(c for c in state[1] if c in window),
            tuple(c for c in state[2] if c in window))


def _align(model: Model, board: Board) -> Delta | None:
    """Offset that maps the board's cells into the model's coordinates, or None.

    Matched on the FIXED part only — sockets and rails — because pieces move between frames and
    a stale frame's pieces would drag the alignment onto the wrong cell.

    ⛔ Agreement is scored inside the STRIP THAT WAS VISIBLE BOTH BEFORE AND AFTER, not over the
    whole screen. A pan reveals territory that is legitimately absent from the map, so demanding
    that most of the screen be already known rejected every correct offset the moment the board
    scrolled, and the tool then re-anchored to a fresh coordinate system and forgot the board it
    had spent forty actions mapping.
    """
    obs = board.fixed()
    known = model.sockets | model.rails
    if not obs or not known:
        return (0, 0)
    prev = model.window or known
    best: tuple[int, int, Delta] | None = None
    seeds = sorted(obs)[:12]
    candidates = {(k[0] - o[0], k[1] - o[1]) for o in seeds for k in known}
    candidates.add((0, 0))
    for off in candidates:
        shifted = {(c[0] + off[0], c[1] + off[1]) for c in obs}
        win = {(c[0] + off[0], c[1] + off[1]) for c in board.window}
        overlap = win & prev
        hits = len(shifted & known & overlap)
        miss = len((shifted & overlap) - known) + len((known & overlap) - shifted)
        score = hits - 2 * miss
        if best is None or (score, hits) > (best[0], best[1]):
            best = (score, hits, off)
    if best is None or best[1] < _MIN_CELLS or best[0] <= 0:
        return None
    return best[2]


# --------------------------------------------------------------------------- planning

# A move is ("jump", from_cell, direction) or ("drive", None, direction).
Move = tuple[str, Any, Delta]


def _drive(carriers: tuple[Cell, ...], pieces: dict[Cell, int], blockers: frozenset[Cell],
           rails: set[Cell], d: Delta,
           ) -> tuple[tuple[Cell, ...], dict[Cell, int], frozenset[Cell]] | None:
    """Shift every carrier one cell along the rails, each taking its passenger with it.

    The leading carrier resolves first so a train shifts together, and one blocked by another
    simply stays — which is what the engine does.
    """
    order = sorted(carriers, key=lambda c: -(c[0] * d[0] + c[1] * d[1]))
    live = set(carriers)
    moved: dict[Cell, Cell] = {}
    for c in order:
        n = (c[0] + d[0], c[1] + d[1])
        if n in live or n not in rails:
            continue
        live.discard(c)
        live.add(n)
        moved[c] = n
    if not moved:
        return None
    return (tuple(sorted(live)),
            {moved.get(c, c): v for c, v in pieces.items()},
            frozenset(moved.get(c, c) for c in blockers))


def _successors(state: Any, sockets: set[Cell], rails: set[Cell],
                noncapture: frozenset[int]):
    """Every legal (next state, move, action cost) from a state — jumps then carrier drives.

    ⛔ Planning is done over the whole map, NOT over what is on screen. The camera follows the
    carriers, so a jump that is off screen now is on screen by the time the drives before it have
    run — filtering the search by the current window deleted the only route back across a board
    and left the tool with a piece parked at the far end and no plan.
    """
    pieces = dict(state[0])
    carriers, blockers = state[1], state[2]
    occupied = set(pieces) | set(blockers)
    holes = sockets | set(carriers)
    for cell, colour in pieces.items():
        for d in DIRS:
            mid = (cell[0] + d[0], cell[1] + d[1])
            if mid not in occupied:
                continue
            land = (cell[0] + 2 * d[0], cell[1] + 2 * d[1])
            if land not in holes or land in occupied:
                continue
            nxt = dict(pieces)
            del nxt[cell]
            if pieces.get(mid) == colour and colour not in noncapture:
                del nxt[mid]
            nxt[land] = colour
            yield (tuple(sorted(nxt.items())), carriers, blockers), ("jump", cell, d), 2
    if carriers:
        for d in DIRS:
            res = _drive(carriers, pieces, frozenset(blockers), rails, d)
            if res is None:
                continue
            nl, np_, nb = res
            yield ((tuple(sorted(np_.items())), nl, tuple(sorted(nb))),
                   ("drive", None, d), 1)


def railhead_moves(model: Model, noncapture: frozenset[int],
                   cost_cap: int = 16, node_cap: int = 40_000) -> list[Move]:
    """Put a piece on a carrier and ride it toward the side where the track leaves the screen.

    ⛔ THE ONLY MOVE THAT WIDENS THE MAP ON A BOARD WIDER THAN THE FRAME, and neither of the tiers
    below it can propose one. The frontier tier maximises how much unknown territory sits next to a
    piece — a quantity computed in MODEL coordinates, where nothing a simulated move does ever
    changes what is knowable, because the simulation has no camera in it. Measured on the widest
    board: eleven consecutive planning decisions, the known map fixed at 26 cells at every one of
    them, and the tool then bid zero and handed a board it could still have opened to a blind
    searcher that spent 193 actions and made the losing capture anyway.

    ⛔ A PASSENGER IS REQUIRED. The camera follows a PIECE; an empty carrier driven off the map
    reveals nothing and the tool would never see what it had done. So this is two mechanisms, not
    one — board, then ride — which is exactly the composition no single-action probe reaches.

    ⛔ THE OPEN END BELONGS TO THE TRACK, NOT TO THE CARRIER, and reading it the other way made this
    tier silent on the board it was written for: its carriers sat in the middle of the visible
    strip while the rails ran off both sides, so "a carrier at an open end" existed nowhere and
    nothing was ever proposed. What matters is the DIRECTION the track leaves the screen in; a
    carrier riding that way arrives at the edge in as many actions as it takes.

    ⛔ AND THE END MUST LEAVE THE SCREEN, not merely the map. A run of track that stops in plain
    view is a buffer stop the tool can see is a buffer stop, and driving at it teaches nothing.

    ⛔ THE RIDE IS NOT SIMULATED, AND THAT IS THE WHOLE POINT OF A SEPARATE TIER. The drive model
    rolls a carrier only onto a cell the map ALREADY calls track, so at the edge of the known map
    every ride is one cell short of the only place worth going, and the search reports — correctly,
    on the map it has — that nothing gains. So the ride is emitted raw. That is safe because a
    drive the engine refuses is read off the next frame like any other, and the barren counter
    bounds how many times this tier may be wrong; a ride that is right scrolls the camera and hands
    back a strip of board nobody had seen.
    """
    track = model.rails | model.carriers
    known = model.sockets | track | model.blockers
    ends: Counter[Delta] = Counter()
    for d in DIRS:
        for c in track:
            n = (c[0] + d[0], c[1] + d[1])
            back = (c[0] - d[0], c[1] - d[1])
            if back in track and n not in known and n not in model.window:
                ends[d] += 1
    if not ends or not model.carriers:
        return []
    # The side with the most open track is the likeliest continuation; DIRS order breaks a tie.
    ride = min(ends, key=lambda d: (-ends[d], DIRS.index(d)))
    carriers = tuple(sorted(model.carriers))
    if any(c in model.pieces for c in model.carriers):
        return [("drive", None, ride)]

    start = (tuple(sorted(model.pieces.items())), carriers, tuple(sorted(model.blockers)))
    cost_of: dict[Any, int] = {start: 0}
    parent: dict[Any, tuple[Any, Move]] = {}
    heap: list[tuple[int, int, Any]] = [(0, 0, start)]
    tie = 0
    while heap:
        cost, _t, state = heapq.heappop(heap)
        if cost > cost_of.get(state, cost) or cost > cost_cap:
            continue
        aboard = set(state[1]) & {c for c, _v in state[0]}
        if aboard and state != start:
            out: list[Move] = []
            node = state
            while node in parent:
                node, mv = parent[node]
                out.append(mv)
            out.reverse()
            out.append(("drive", None, ride))
            return out
        if len(cost_of) > node_cap:
            break
        for ns, mv, step_cost in _successors(state, model.sockets, model.rails, noncapture):
            nc = cost + step_cost
            if nc <= cost_cap and nc < cost_of.get(ns, 1 << 30):
                cost_of[ns] = nc
                parent[ns] = (state, mv)
                tie += 1
                heapq.heappush(heap, (nc, tie, ns))
    return []


def explore_moves(model: Model, noncapture: frozenset[int], visited: set[Any],
                  cost_cap: int = 30, node_cap: int = 40_000) -> list[Move]:
    """Cheapest way to put a piece where the map runs out, when no capture is reachable.

    A board wider than the screen only reveals its far side once a piece is carried to the
    edge, so "no plan" on a partial map means "go and look", not "give up". The objective is
    generic: maximise how much UNKNOWN territory sits next to some piece.
    """
    known = model.sockets | model.rails | model.blockers
    if not known:
        return []

    def frontier(state: Any) -> int:
        best = 0
        for cell, _v in state[0]:
            near = sum(1 for dy in range(-2, 3) for dx in range(-2, 3)
                       if (cell[0] + dy, cell[1] + dx) not in known)
            best = max(best, near)
        return best

    start = (tuple(sorted(model.pieces.items())), tuple(sorted(model.carriers)),
             tuple(sorted(model.blockers)))
    cost_of: dict[Any, int] = {start: 0}
    parent: dict[Any, tuple[Any, Move]] = {}
    heap: list[tuple[int, int, Any]] = [(0, 0, start)]
    tie = 0
    best: tuple[int, int, Any] | None = None
    while heap:
        cost, _t, state = heapq.heappop(heap)
        if cost > cost_of.get(state, cost) or cost > cost_cap:
            continue
        if state not in visited and state != start:
            score = frontier(state)
            if best is None or (score, -cost) > (best[0], -best[1]):
                best = (score, cost, state)
        if len(cost_of) > node_cap:
            break
        for ns, mv, step_cost in _successors(state, model.sockets, model.rails, noncapture):
            nc = cost + step_cost
            if nc <= cost_cap and nc < cost_of.get(ns, 1 << 30):
                cost_of[ns] = nc
                parent[ns] = (state, mv)
                tie += 1
                heapq.heappush(heap, (nc, tie, ns))
    if best is None or best[0] <= frontier(start):
        return []
    out: list[Move] = []
    node = best[2]
    while node in parent:
        node, mv = parent[node]
        out.append(mv)
    out.reverse()
    return out


def probe_moves(model: Model, noncapture: frozenset[int], touched: set[Cell],
                visited: set[Any], cost_cap: int = 12, node_cap: int = 20_000) -> list[Move]:
    """Cheapest way to put a piece somewhere it has never stood on this level.

    The last tier. Some boards reveal their far side only when a piece reaches a particular
    cell, which no amount of looking at the current map predicts — so when neither a capture
    nor the frontier can be improved, the move worth making is the one that changes something
    the board has not seen yet.
    """
    start = (tuple(sorted(model.pieces.items())), tuple(sorted(model.carriers)),
             tuple(sorted(model.blockers)))
    cost_of: dict[Any, int] = {start: 0}
    parent: dict[Any, tuple[Any, Move]] = {}
    heap: list[tuple[int, int, Any]] = [(0, 0, start)]
    tie = 0
    while heap:
        cost, _t, state = heapq.heappop(heap)
        if cost > cost_of.get(state, cost) or cost > cost_cap:
            continue
        if (state != start and state not in visited
                and any(c not in touched for c, _v in state[0])):
            out: list[Move] = []
            node = state
            while node in parent:
                node, mv = parent[node]
                out.append(mv)
            out.reverse()
            return out
        if len(cost_of) > node_cap:
            break
        for ns, mv, step_cost in _successors(state, model.sockets, model.rails, noncapture):
            nc = cost + step_cost
            if nc <= cost_cap and nc < cost_of.get(ns, 1 << 30):
                cost_of[ns] = nc
                parent[ns] = (state, mv)
                tie += 1
                heapq.heappush(heap, (nc, tie, ns))
    return []


def runs_offscreen(model: Model) -> bool:
    """Does the board's own structure CONTINUE past the edge of the screen?

    ⛔ THE SIGNAL A PLANNER NEEDS BEFORE ITS FIRST CLAIM, not after a refuted one. A board wider
    than the frame is the normal case here, and the model is then a strip of it — so a state in
    which every piece this tool can SEE has been reduced to one is not a solved level, it is a
    solved window. The sister tool learns this by playing a win that does not win and remembering
    it; that route cannot help a tool whose very first claim is the losing move, which is what was
    measured on the widest board: ONE win claim in the whole level, and it is the capture that
    kills it.

    Three conditions, and each one is load-bearing (the same shape the sister tool's travel tier
    uses). The cell beyond must be UNKNOWN, or there is nothing out there to learn; it must also be
    outside the WINDOW, because a cell in plain view with no track on it is a buffer stop the tool
    can see is a buffer stop; and the track must be coming FROM the opposite side, or every cell
    against the frame edge counts as heading out of it in all four directions.
    """
    track = model.rails | model.carriers
    known = model.sockets | track | model.blockers
    for cell in model.sockets | track:
        for d in DIRS:
            n = (cell[0] + d[0], cell[1] + d[1])
            back = (cell[0] - d[0], cell[1] - d[1])
            if back in track and n not in known and n not in model.window:
                return True
    return False


def capture_reachable(state: Any, sockets: set[Cell], rails: set[Cell],
                      noncapture: frozenset[int], node_cap: int = _REACH_CAP) -> bool:
    """Can ANOTHER capture still be reached from here? Bounded, so False means "not cheaply"."""
    total = len(state[0])
    cost_of: dict[Any, int] = {state: 0}
    heap: list[tuple[int, int, Any]] = [(0, 0, state)]
    tie = 0
    while heap:
        cost, _t, st = heapq.heappop(heap)
        if cost > cost_of.get(st, cost):
            continue
        if len(st[0]) < total:
            return True
        if len(cost_of) > node_cap:
            return False
        for ns, _mv, step in _successors(st, sockets, rails, noncapture):
            nc = cost + step
            if nc < cost_of.get(ns, 1 << 30):
                cost_of[ns] = nc
                tie += 1
                heapq.heappush(heap, (nc, tie, ns))
    return False


def plan_moves(model: Model, noncapture: frozenset[int], node_cap: int = _NODE_CAP,
               partial: bool = False, lookahead: int = _LOOKAHEAD,
               ) -> tuple[list[Move], bool] | None:
    """Cheapest action sequence to the next capture, or to the whole level when it fits.

    Returns (moves, solved). `solved` is True when the sequence takes every capturable colour
    down to a single piece; otherwise it is the shortest route to one more capture.

    ⛔ `partial` SAYS THE MAP IS A WINDOW ONTO A BIGGER BOARD, and it changes two things that are
    both wrong without it. First, a solved state is no longer a SOLUTION — reducing every piece on
    screen to one says nothing about the pieces scrolled away — though it stays worth playing
    toward, because it is still the cheapest route to a real capture. Second, a capture cannot be
    undone, so on a partial map the cheapest one is not automatically the move: the distinct
    capture OUTCOMES are collected and the cheapest one FROM WHICH ANOTHER CAPTURE IS STILL
    REACHABLE is taken. When none of them is, this returns None so the caller goes and LOOKS
    instead — which is only safe because a partial map has somewhere to look, and looking is
    reversible where a capture is not.

    ⛔ COUNT OUTCOMES, NOT PATHS. One action drives every carrier at once, so many different drive
    orders arrive at the same board with the carriers parked differently, and a cost-ordered search
    enumerates them one after another. Keyed by the pieces, a window of eight holds eight real
    choices instead of one repeated eight times.
    """
    sockets, rails = model.sockets, model.rails
    if not model.pieces:
        return None
    counts = Counter(model.pieces.values())
    targets = {c for c, n in counts.items() if n >= 2 and c not in noncapture}
    if not targets:
        return None
    total = len(model.pieces)

    def is_solved(pieces: dict[Cell, int]) -> bool:
        seen = Counter(pieces.values())
        return all(seen[c] <= 1 for c in targets)

    start = (tuple(sorted(model.pieces.items())), tuple(sorted(model.carriers)),
             tuple(sorted(model.blockers)))
    cost_of: dict[Any, int] = {start: 0}
    parent: dict[Any, tuple[Any, Move]] = {}
    heap: list[tuple[int, int, Any]] = [(0, 0, start)]
    tie = 0
    capture_state: Any = None
    outcomes: list[Any] = []
    seen_outcomes: set[Any] = set()
    expanded = 0

    def path(state: Any) -> list[Move]:
        out: list[Move] = []
        while state in parent:
            state, mv = parent[state]
            out.append(mv)
        out.reverse()
        return out

    while heap:
        cost, _t, state = heapq.heappop(heap)
        if cost > cost_of.get(state, cost):
            continue
        pieces = dict(state[0])
        if is_solved(pieces) and not partial:
            return path(state), True
        if len(pieces) < total:
            if capture_state is None:
                capture_state = state
            if partial and len(outcomes) < lookahead and state[0] not in seen_outcomes:
                seen_outcomes.add(state[0])
                outcomes.append(state)
        expanded += 1
        if expanded > node_cap:
            break

        for ns, mv, step_cost in _successors(state, sockets, rails, noncapture):
            nc = cost + step_cost
            if nc < cost_of.get(ns, 1 << 30):
                cost_of[ns] = nc
                parent[ns] = (state, mv)
                tie += 1
                heapq.heappush(heap, (nc, tie, ns))

    if partial:
        for st in outcomes:
            if capture_reachable(st, sockets, rails, noncapture):
                return path(st), False
        return None
    if capture_state is not None:
        return path(capture_state), False
    return None


# --------------------------------------------------------------------------- the tool

class PegJumpTool:
    """Solve a peg-solitaire board, driving rail carriers when the lattice does not connect."""

    name = "pegjump"

    def __init__(self) -> None:
        self._dirmap: dict[Delta, int] = {}      # lattice direction -> simple action id
        self._excluded: dict[Delta, set[int]] = {}
        self._noncapture: frozenset[int] = frozenset()
        self.reset()

    # -- lifecycle ---------------------------------------------------------
    def reset(self) -> None:
        self._model: Model | None = None
        self._plan: list[Move] = []
        self._history: list[tuple[Any, ...]] = []
        self._pending_drive: tuple[int, tuple[Cell, ...], int, Delta] | None = None
        self._alt: tuple[tuple[Any, ...], int] | None = None
        self._doubt = 0
        self._misaligned = 0
        self._explored: set[Any] = set()
        self._ncarriers = 0
        self._barren = 0
        self._known = 0
        self._touched: set[Cell] = set()
        self._peaked = 0
        self._prev_seen: tuple[Any, ...] | None = None
        self._settles = 0
        self._retried = False
        self._read_key: bytes | None = None
        self._read: Board | None = None
        self._sync_key: bytes | None = None
        self._sync_res: tuple[Model, bool] | None = None

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """Nothing is learned from the flag alone — a carrier's displacement and a refused
        capture are both positional, so both are read off the NEXT board in `propose`."""

    # -- frame -------------------------------------------------------------
    def _board(self, g: np.ndarray) -> Board | None:
        """One reading per distinct frame — `detect` and `propose` both want the same answer."""
        key = g.tobytes()
        if key != self._read_key:
            self._read_key = key
            self._read = read_board(g)
        return self._read

    @staticmethod
    def _grid(frames: list[Any], obs: Any) -> np.ndarray | None:
        if obs is not None and has_frame(obs):
            return frame_2d(obs).astype(np.int16)
        for f in reversed(frames or []):
            if isinstance(f, np.ndarray):
                return f.astype(np.int16)
        return None

    def _adopt(self, board: Board) -> Model:
        m = Model()
        m.sockets = set(board.sockets)
        m.rails = set(board.rails)
        m.pieces = dict(board.pieces)
        m.carriers = set(board.carriers)
        m.blockers = set(board.blockers)
        m.pitch, m.oy, m.ox = board.pitch, board.oy, board.ox
        m.window = set(board.window)
        self._touched = set(m.pieces)
        return m

    def _sync(self, g: np.ndarray) -> tuple[Model, bool] | None:
        """Fold this frame into the model, and learn from it.

        Returns (model, placed) — `placed` is False when the board could not be located on
        screen at whole-cell precision, which means it is mid-pan and nothing may be clicked.
        """
        key = g.tobytes()
        if key == self._sync_key:
            # ⛔ Idempotent per frame. The harness asks `detect` and then `propose` about the SAME
            # board, and this method LEARNS — running it twice made a frame look like it had
            # settled (it equalled the reading this method itself had just stored) and installed
            # a stale board over a correct model.
            return self._sync_res
        board = self._board(g)
        if board is None:
            self._sync_key, self._sync_res = key, None
            return None
        if self._model is None:
            self._model = self._adopt(board)
            self._ncarriers = len(self._model.carriers)
            self._history = [self._model.state()]
            self._plan = []
            self._sync_key, self._sync_res = key, (self._model, True)
            return self._sync_res
        m = self._model
        self._sync_key = key
        off = _align(m, board) if board.pitch == m.pitch else None
        if off is None:
            # ⛔ A board that cannot be placed for several frames running is not a board that is
            # panning, it is a DIFFERENT board. The harness hands over on the transitional frame
            # of a level-up, so the first board this tool ever sees on a new level can be the
            # last board of the old one; anchoring to it and then refusing every frame after was
            # measured as a tool that solves a level alone and stalls out inside the harness.
            self._misaligned += 1
            if self._misaligned < 6:
                self._sync_res = (m, False)
                return self._sync_res
            self._misaligned = 0
            self._model = self._adopt(board)
            self._ncarriers = len(self._model.carriers)
            self._history = [self._model.state()]
            self._plan = []
            self._prev_seen = None
            self._alt = None
            self._sync_res = (self._model, True)
            return self._sync_res
        self._misaligned = 0

        def shift(c: Cell) -> Cell:
            return (c[0] + off[0], c[1] + off[1])
        m.pitch = board.pitch
        # world cell = board cell + off, so the pixel of world (0, 0) sits back by that offset.
        m.oy = board.oy - off[0] * board.pitch
        m.ox = board.ox - off[1] * board.pitch
        m.window = {shift(c) for c in board.window}
        seen_carriers = {shift(c) for c in board.carriers}
        m.sockets |= {shift(c) for c in board.sockets}
        m.rails |= {shift(c) for c in board.rails}
        m.sockets -= seen_carriers
        # ⛔ A piece in flight is drawn across two cells and fills the socket it is passing over,
        # which reads exactly like a blocker. Furniture never appears on a socket the board has
        # already shown to be plain, so a "blocker" there is the animation, not the board.
        seen_blockers = {shift(c) for c in board.blockers} - m.sockets
        m.blockers |= {c for c in seen_blockers if c not in m.rails}
        seen = (tuple(sorted((shift(c), v) for c, v in board.pieces.items())),
                tuple(sorted(seen_carriers)),
                tuple(sorted(seen_blockers)))
        # ⛔ Settled-ness has to be decided BEFORE the state is compared, and neither the frame
        # hash nor the changed flag can decide it. A carrier mid-slide straddles two cells and
        # is read as two blockers with no carrier at all — a perfectly well-formed board that
        # happens to be false. Two conservation laws catch it: furniture never vanishes, and
        # furniture never lands on a socket the board has already shown to be plain.
        here = _restrict(m.state(), m.window)
        merged = len(seen_carriers) + len([c for c in m.carriers if c not in m.window])
        # ⛔ Carriers are conserved. One that is neither on screen nor remembered off it has not
        # been removed from the board, it is mid-slide — and losing it deletes the only route
        # between two halves of a board that the lattice does not otherwise connect.
        unsettled = (board.moving > 0
                     or len(seen_carriers) < len(here[1])
                     or merged < self._ncarriers
                     or bool({shift(c) for c in board.blockers} & m.sockets))
        self._learn_drive(seen[1], settled=not unsettled)
        if unsettled:
            return self._placed(m)
        if (not board.moving and self._alt is not None
                and seen == _restrict(self._alt[0], m.window)):
            # The capture the model predicted did not happen: this colour cannot be taken.
            self._noncapture = self._noncapture | {self._alt[1]}
            self._alt = None
            self._install(m, seen)
            return m, True
        if seen == here or any(seen == _restrict(h, m.window) for h in self._history):
            # Either the frame agrees, or it reproduces a state this tool has already left — an
            # animation one action behind. The simulation stays the belief either way.
            self._alt = None if seen == here else self._alt
            self._doubt = 0
            self._prev_seen = seen
            self._sync_res = (m, True)
            return self._sync_res
        # A frame that agrees with nothing predicted. It is far likelier to be mid-animation
        # than to be a genuine divergence, so it is only believed once it stops moving — the
        # board reading twice the same — or after it has persisted.
        self._doubt += 1
        settled = seen == self._prev_seen and not board.moving
        self._prev_seen = seen
        if settled or self._doubt >= 3:
            self._alt = None
            self._doubt = 0
            self._install(m, seen)
            self._sync_res = (m, True)
            return self._sync_res
        self._sync_res = (m, bool(self._plan))
        return self._sync_res


    def _install(self, m: Model, seen: tuple[Any, ...]) -> None:
        """Take the frame's word for what it can SEE, and keep what it cannot.

        ⛔ Off screen is not gone. Overwriting the whole board from a frame that shows a third of
        it made the planner declare a level solved with most of its pieces still standing, just
        scrolled away.
        """
        w = m.window
        m.pieces = {c: v for c, v in m.pieces.items() if c not in w} | dict(seen[0])
        m.carriers = {c for c in m.carriers if c not in w} | set(seen[1])
        m.blockers = ({b for b in m.blockers if b not in w or b not in m.rails}
                      | set(seen[2]))
        self._touched |= set(m.pieces)
        self._history = [m.state()]
        self._plan = []

    def _placed(self, m: Model) -> tuple[Model, bool]:
        """A board that has not settled may still be played THROUGH, as long as a plan is in
        flight — the simulation, not the frame, is what the next click is computed from."""
        self._sync_res = (m, bool(self._plan))
        return self._sync_res


    def _learn_drive(self, carriers: tuple[Cell, ...], settled: bool) -> None:
        """Read which way the one probed action pointed, out of the carriers' displacement.

        Held open for a few frames: the probe's own frame can be one animation behind, and a
        mapping abandoned too early costs another action to re-probe.
        """
        if self._pending_drive is None:
            return
        aid, before, age, want = self._pending_drive
        if len(carriers) == len(before) and carriers:
            deltas = {(b[0] - a[0], b[1] - a[1]) for a, b in zip(before, carriers)}
            deltas.discard((0, 0))
            if len(deltas) == 1:
                d = deltas.pop()
                if d in DIRS:
                    self._dirmap[d] = aid
                self._pending_drive = None
                return
            if not deltas and settled:
                # A drive that works leaves the board mid-slide; a settled board with every
                # carrier where it was is the action saying it does not point that way.
                self._excluded.setdefault(want, set()).add(aid)
                self._pending_drive = None
                return
        if age >= 3:
            # It was asked for a direction the carriers COULD have taken and they did not move,
            # so this action is not that direction. Recording the negative is what keeps the
            # calibration to one probe per direction instead of one per pair.
            self._excluded.setdefault(want, set()).add(aid)
            self._pending_drive = None
            return
        self._pending_drive = (aid, before, age + 1, want)

    # -- planning ----------------------------------------------------------
    def _ensure_plan(self, m: Model) -> float:
        """Fill the queue of moves and report how strong the claim on this board is."""
        if self._plan:
            return 0.9
        # ⛔ A WIN OVER A WINDOW IS NOT A WIN, and this is the only place that can say so before the
        # move is made. Measured on the widest board: the model held two of the board's six pieces
        # — every one of the other four simply scrolled off, with no filter dropping anything and
        # nothing forgotten — so jumping one over the other left ONE and the search returned it as
        # a solved level. That single claim is the capture that makes the level unwinnable, and it
        # is the ONLY claim the tool makes there, so no amount of learning-from-refutation reaches
        # it. Handed the true six pieces the same search stops calling it a win and STILL takes it,
        # because it is the cheapest capture — which is why the survivability half is not optional.
        partial = runs_offscreen(m)
        found = plan_moves(m, self._noncapture, partial=partial)
        if found is not None and found[0]:
            self._plan = list(found[0])
            return 0.95 if found[1] else 0.9
        # Exploring is only worth an action while looking still finds board. Three barren
        # sweeps and this tool has nothing left to offer THIS level, and says so with a zero
        # bid so the harness can hand the board to something else.
        known = len(m.sockets) + len(m.rails)
        if known > self._known:
            self._known, self._barren = known, 0
        if self._barren >= 3:
            return 0.0
        # ⛔ ORDER MATTERS AND IT IS MEASURED. On a map known to be a window, opening it is worth
        # more than any move computed inside it, because the frontier objective is blind to the
        # camera and cannot grow the map at all — so it goes FIRST when the board runs off screen,
        # and is not offered at all when the board fits.
        moves = railhead_moves(m, self._noncapture) if partial else []
        if not moves:
            moves = explore_moves(m, self._noncapture, self._explored)
        if not moves:
            moves = probe_moves(m, self._noncapture, self._touched, self._explored)
        if not moves:
            return 0.0
        self._barren += 1
        state = (tuple(sorted(m.pieces.items())), tuple(sorted(m.carriers)),
                 tuple(sorted(m.blockers)))
        for mv in moves:
            state = self._apply(m, state, mv)
        self._explored.add(state)
        self._plan = list(moves)
        return 0.75

    @staticmethod
    def _apply(m: Model, state: Any, move: Move) -> Any:
        """The state a move leads to, without touching the model — used to mark a target."""
        for ns, mv, _c in _successors(state, m.sockets, m.rails, frozenset()):
            if mv == move:
                return ns
        return state

    def _advance(self, m: Model, move: Move) -> None:
        kind, cell, d = move
        if kind == "jump":
            colour = m.pieces.pop(cell)
            mid = (cell[0] + d[0], cell[1] + d[1])
            land = (cell[0] + 2 * d[0], cell[1] + 2 * d[1])
            taken = m.pieces.get(mid) == colour and colour not in self._noncapture
            if taken:
                del m.pieces[mid]
            m.pieces[land] = colour
            if taken:
                # What the board would look like had the capture been refused — the only
                # evidence that separates an uncapturable colour from a lagging frame.
                refused = dict(m.pieces)
                refused[mid] = colour
                self._alt = ((tuple(sorted(refused.items())), tuple(sorted(m.carriers)),
                              tuple(sorted(m.blockers))), colour)
        else:
            res = _drive(tuple(sorted(m.carriers)), m.pieces, frozenset(m.blockers), m.rails, d)
            if res is not None:
                carriers, pieces, blockers = res
                m.carriers, m.pieces, m.blockers = set(carriers), pieces, set(blockers)
        self._touched |= set(m.pieces)
        self._history.append(m.state())
        self._history = self._history[-_HISTORY:]

    @staticmethod
    def _settle_click(g: np.ndarray) -> Step:
        """One inert click, used only to let an animation drain. Kept away from the frame's
        edges, where every board of this kind draws its counters and its controls."""
        bg = int(Counter(int(v) for v in g.ravel()).most_common(1)[0][0])
        h, w = g.shape
        for y in range(h // 4, h - h // 8):
            for x in range(w // 3, w - 2):
                if int(g[y, x]) == bg:
                    return (6, (x, y))
        return (6, (w - 2, h - 2))

    # -- contract ----------------------------------------------------------
    def detect(self, frames: list[Any], obs: Any) -> float:
        g = self._grid(frames, obs)
        if g is None:
            return 0.0
        synced = self._sync(g)
        if synced is None:
            return 0.0
        m, _placed = synced
        if len(m.pieces) < 2:
            return 0.0
        return self._ensure_plan(m)

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        g = self._grid(frames, obs)
        if g is None:
            return []
        synced = self._sync(g)
        if synced is None:
            return []
        m, placed = synced
        if not placed:
            # The board is between lattice positions: pay one inert click and read again.
            self._settles += 1
            if self._settles > 8:
                return []
            return [self._settle_click(g)]
        self._settles = 0
        # ⛔ A board this tool has never seen two pieces on is not its board — that is the
        # transitional frame of a level-up, showing the level it has just finished. Refusing it
        # is NOT the same as refusing a one-piece board later on: mid-level a single visible
        # piece usually means the rest of them are simply scrolled off, which is exactly when
        # going to look is the right move.
        self._peaked = max(self._peaked, len(m.pieces))
        if self._peaked < 2 or not self._ensure_plan(m):
            return []
        move = self._plan.pop(0)
        kind, cell, d = move
        if kind == "jump":
            colour = m.pieces.get(cell)
            land = (cell[0] + 2 * d[0], cell[1] + 2 * d[1])
            if colour is None or land not in (m.sockets | m.carriers):
                self._plan = []
                return []
            steps = [(6, m.pixel(cell)), (6, m.pixel(land))]
            if any(not (0 <= x < g.shape[1] and 0 <= y < g.shape[0]) for _a, (x, y) in steps):
                # The camera has not caught up with the plan; go and move something instead of
                # clicking at a cell that is not on the screen.
                self._plan = []
                if self._retried:
                    return []
                moves = explore_moves(m, self._noncapture, self._explored)
                if not moves:
                    return []
                self._plan = list(moves)
                self._retried = True
                try:
                    return self.propose(frames, obs)
                finally:
                    self._retried = False
            self._advance(m, move)
            return steps
        aid = self._dirmap.get(d)
        if aid is None:
            simple, _six = availability(obs)
            taken = set(self._dirmap.values()) | self._excluded.get(d, set())
            untried = [a for a in simple if a != 7 and a not in taken]
            if not untried:
                self._plan = []
                return []
            aid = untried[0]
            self._plan = []          # the probe may point anywhere; re-plan from what happens
            self._pending_drive = (aid, tuple(sorted(m.carriers)), 0, d)
            return [(aid, None)]
        self._advance(m, move)
        return [(aid, None)]
