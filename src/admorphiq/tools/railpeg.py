"""Rail-cart peg solitaire — jump-capture on a socket lattice served by carts on rails.

The mechanic, read out of the game's own source and then re-derived from pixels so that nothing
game-specific is written down here:

  * the board is a lattice of equal cells at a constant pitch. A cell is a SOCKET (a shallow hole
    a piece may rest in), a RAIL (a track segment), or nothing;
  * a socket holds at most one occupant: a PIECE (a disc drawn inside it, in one of several
    colours) or an OBSTACLE (art that fills the socket and never moves on its own);
  * a piece MOVES only by jumping: over an adjacent OCCUPIED cell, landing two cells away in a
    hole that is free. Every other landing is refused;
  * a jump CAPTURES what it passed over ONLY when that is a piece of the SAME colour. Jumping an
    obstacle, or a piece of another colour, moves the jumper and leaves the jumped cell standing —
    so obstacles and foreign pieces are permanent stepping stones;
  * CARTS ride the rail network. Each simple action shifts every cart one cell along the rails,
    and a cart takes its passenger with it. A cart is also a legal LANDING, which is how a piece
    crosses a gap the lattice does not bridge;
  * the level is won when every capturable colour is down to a single piece.

⛔ A CART IS NOT ALWAYS EMPTY, and reading it as if it were is what stops a solver four levels in.
A cart may carry an OBSTACLE, and that changes the cart's role completely: an empty cart is a
LANDING and never a stepping stone, a loaded cart is a stepping stone and never a landing. The
deep boards are built around exactly that difference — the shortest route to the first capture on
the first board that needs it is `drive the loaded cart under the gap, jump the gap it now
bridges, drive it away again, then capture across the hole it leaves`. A loaded cart is also the
one cart a naive reading MISSES, because its cargo is drawn over the top edge of its own frame, so
the "is the frame around this cell one flat colour?" test that finds an empty cart fails on it.
The test here is a MAJORITY of that frame instead, which the cargo cannot outvote.

⛔ THE CAMERA IS DRIVEN BY THE BOARD, not by the tool. Several boards are far wider than the
screen and only scroll when the game decides to: when a piece lands on a particular cell, and —
the one that matters — whenever a cart with a PIECE ABOARD moves sideways, so that the view
follows the passenger. That is the only way the far side of those boards is ever seen, which makes
"put a piece on a cart and ride it" a real move with a real purpose, not a wasted action. Geometry
is therefore re-anchored every turn by aligning the part of the board no move can change against
the map built so far, and the offset that alignment returns folds the newly revealed strip into
the map.

⛔ THE FRAME LAGS THE BOARD. A jump is animated: the engine returns the first frame of the
animation, so the board that comes back after a capture still shows the captured piece standing.
The SIMULATION is the belief and the frame is only evidence — a frame reproducing a state this
tool has already left is stale and ignored, a frame that matches nothing predicted is adopted only
once it stops moving or has persisted, and the frame's other job is to say where the lattice
currently sits on screen.

⛔ Nothing here is a constant. The pitch, the lattice phase, which colour is a socket, which is a
piece, which is a rail, which is a cart's livery, and which action id points which way are all
derived or learned. Two cost a measurement:

  * the four action ids are NOT assumed to be up/down/left/right in any order — the tool drives one
    untried action and reads the carts' displacement out of the next frame. One action, once per
    game, and only when a plan needs a cart;
  * one colour of piece cannot be captured at all. No frame distinguishes it, so it is LEARNED: a
    jump the model says should capture, which leaves the piece count unchanged, retires that colour
    from the goal.

⛔ Planning is FOUR TIERS and the order is the point. (1) Search the whole level, keeping the first
capture found along the way — a capture is irreversible, so the shortest route to one is always
worth taking. (2) When no capture is reachable, close the distance between two pieces of a colour;
that is what the board is asking for and it stays well defined on a map this tool can only half
see. (3) Failing that, RIDE A CART SOMEWHERE NO PIECE HAS BEEN — a rail leaving the region you can
see is itself the evidence that there is a region to go to, and a board wider than the screen only
shows its far side once a piece is carried there. (4) Failing that, put a piece somewhere it has
never stood. Three barren sweeps and this tool bids ZERO and hands the level on, which is how it
takes the levels it can solve without holding the ones it cannot.

⛔ Selectivity. `detect` runs the planner and returns 0.0 unless the search finds a capture, a full
solution, or a reveal worth an action on THIS board. A lattice with pieces in it is not evidence —
several sample games draw one.
"""

from __future__ import annotations

import heapq
from collections import Counter, deque
from typing import Any

import numpy as np

from admorphiq.tools.base import Step, availability, frame_2d, has_frame

__all__ = ["RailPegTool", "Board", "read_board", "plan_level", "travel_moves"]

Cell = tuple[int, int]           # (row, col) on the lattice
Delta = tuple[int, int]

DIRS: tuple[Delta, ...] = ((-1, 0), (1, 0), (0, -1), (0, 1))

# A socket is a flat square inside a gap of another colour; a piece is a disc drawn in it. Four
# pixels is the smallest square that carries a disc with its corners still showing.
_INNER = 4
_MIN_PITCH = _INNER + 1
_MAX_PITCH = 16
# ⛔ Two different thresholds, because they answer two different questions. Discovering the
# lattice needs only enough cells to fix a pitch and a phase, and a board that has SCROLLED shows
# very few whole ones — its region is cut by the screen edge and most of what is left is track. A
# floor of eight cost a level: the tool solved the first capture, rode a cart to the far side, and
# then could not read the board it had arrived at, so it went silent with the level half done.
# Recognising a board it has ALREADY MAPPED is a different matter — that offset is chosen from many
# candidates and a weak match re-anchors the whole coordinate system, so it keeps the higher bar.
_MIN_CELLS = 5
_MIN_MATCH = 8
# The frame around a cell is 20 pixels. A cart's livery must hold most of it; its cargo overhangs
# the top edge and takes four of them, so the threshold has to sit at or below 16 and well above
# half.
_LIVERY = 14
_HISTORY = 8
_NODE_CAP = 90_000
# How many candidate captures to weigh before committing to one. Eight is what the deepest sample
# board needs: its first seven cheapest captures are all dead ends.
_LOOKAHEAD = 8
# Plans in a row that take nothing before a board known to extend past the screen is treated as
# locally finished and travel outranks another local plan.
_LOCAL_PATIENCE = 3
# Frames a cart may spend visibly between two cells after it is told to move.
_SLIDE = 3


# --------------------------------------------------------------------------- pixels

def _ring(g: np.ndarray, y: int, x: int) -> np.ndarray:
    """The 1-pixel frame immediately around a cell's inner square."""
    outer = g[y - 1:y + _INNER + 1, x - 1:x + _INNER + 1]
    mask = np.ones(outer.shape, dtype=bool)
    mask[1:1 + _INNER, 1:1 + _INNER] = False
    return outer[mask]


def _flat(a: np.ndarray) -> int | None:
    """The one colour filling this patch, or None when it holds more than one."""
    if a.size == 0:
        return None
    v = int(a.flat[0])
    return v if bool((a == v).all()) else None


def _disc(inner: np.ndarray) -> tuple[int, int] | None:
    """(piece colour, colour of the hole under it) when this square holds a disc, else None.

    A disc leaves the four corners of its hole showing and fills the other twelve pixels, which is
    what "round thing drawn inside a square" looks like at this size. Read as a shape, never as a
    colour — the hole under a piece is a socket on the lattice and a cart's deck on the rails, and
    both must read the same way.
    """
    if inner.shape != (_INNER, _INNER):
        return None
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
    """Every square that reads as a cell: (y, x, frame colour, colour of the hole)."""
    h, w = g.shape
    out: list[tuple[int, int, int, int]] = []
    for y in range(1, h - _INNER):
        for x in range(1, w - _INNER):
            rc = _flat(_ring(g, y, x))
            if rc is None:
                continue
            inner = g[y:y + _INNER, x:x + _INNER]
            ic = _flat(inner)
            if ic is not None:
                if ic != rc:
                    out.append((y, x, rc, ic))
                continue
            d = _disc(inner)
            if d is not None and d[1] != rc:
                out.append((y, x, rc, d[1]))
    return out


def _lattice(anchors: list[tuple[int, int, int, int]]) -> tuple[int, int, int] | None:
    """(pitch, y phase, x phase) — the step is the COMMONEST gap between cells, not the smallest."""
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


# --------------------------------------------------------------------------- the board

class Board:
    """One frame's reading of the lattice."""

    def __init__(self, pitch: int, oy: int, ox: int) -> None:
        self.pitch = pitch
        self.oy = oy                        # pixel row of cell (0, 0)'s inner square
        self.ox = ox
        self.sockets: set[Cell] = set()     # holes on the lattice (a piece may be standing in one)
        self.rails: set[Cell] = set()       # track, including every cell a cart is standing on
        self.carts: set[Cell] = set()
        self.cargo: set[Cell] = set()       # carts carrying an obstacle: stepping stone, no landing
        self.obstacles: set[Cell] = set()   # obstacles bolted to the lattice
        self.pieces: dict[Cell, int] = {}
        # Pieces caught between lattice cells — the board is still animating.
        self.moving = 0
        # Every cell the screen could show. Anything outside it is not absent, only out of view.
        self.window: set[Cell] = set()

    def fixed(self) -> set[Cell]:
        """The part of the board no move can change — what alignment is matched on."""
        return self.sockets | self.rails | self.obstacles


def read_board(g: np.ndarray) -> Board | None:
    """Recover a board from one frame, or None when this is not that kind of board."""
    anchors = _anchors(g)
    if len(anchors) < _MIN_CELLS:
        return None
    lat = _lattice(anchors)
    if lat is None:
        return None
    pitch, ph_y, ph_x = lat
    on = [a for a in anchors if a[0] % pitch == ph_y and a[1] % pitch == ph_x]
    if len(on) < _MIN_CELLS:
        return None
    # ⛔ A piece in flight is drawn BETWEEN cells, so it lands off the lattice phase. Counting those
    # is the only reliable "the board has not settled" signal — the piece count, the frame hash and
    # the changed flag all read as a perfectly ordinary board mid-animation.
    off_phase = sum(1 for a in anchors if a not in on)

    frames = Counter(a[2] for a in on)
    gap = frames.most_common(1)[0][0]
    holes = Counter(a[3] for a in on if a[2] == gap)
    if not holes:
        return None
    socket_col = holes.most_common(1)[0][0]

    h, w = g.shape
    bg = int(Counter(int(v) for v in g.ravel()).most_common(1)[0][0])
    y0 = min(a[0] for a in on)
    x0 = min(a[1] for a in on)
    base_y = y0 - ((y0 - 1) // pitch) * pitch
    base_x = x0 - ((x0 - 1) // pitch) * pitch

    raw: dict[Cell, tuple[np.ndarray, int, int]] = {}
    off = (_INNER - 2) // 2
    r = 0
    while base_y + r * pitch + _INNER <= h - 1:
        c = 0
        while base_x + c * pitch + _INNER <= w - 1:
            y, x = base_y + r * pitch, base_x + c * pitch
            counts = Counter(int(v) for v in _ring(g, y, x))
            colour, n = counts.most_common(1)[0]
            raw[(r, c)] = (g[y:y + _INNER, x:x + _INNER], colour, n)
            c += 1
        r += 1
    if not raw:
        return None

    def centre(inner: np.ndarray) -> int | None:
        return _flat(inner[off:off + 2, off:off + 2])

    # Pass 1 — the cells that read as a hole on their own terms, plain or with a disc in them.
    plain: set[Cell] = set()
    discs: dict[Cell, int] = {}
    for cell, (inner, _colour, _n) in raw.items():
        ic = _flat(inner)
        if ic == socket_col:
            plain.add(cell)
            continue
        d = _disc(inner)
        if d is not None and d[1] == socket_col:
            discs[cell] = d[0]

    # Pass 2 — the track. Rail is a LINE THROUGH THE MIDDLE of a cell that is neither hole nor
    # disc, so it is read off the two centre rows and columns only, never off a fill.
    centres: Counter[int] = Counter()
    mids: dict[Cell, int] = {}
    for cell, (inner, _colour, _n) in raw.items():
        if cell in plain or cell in discs:
            continue
        v = centre(inner)
        if v is None or v in (bg, gap, socket_col):
            continue
        mids[cell] = v
        centres[v] += 1
    rail_col = centres.most_common(1)[0][0] if centres else None

    def liveried(cell: Cell, colour: int) -> bool:
        """Does this cell wear a cart's livery — a frame in a colour nothing else on the board uses?

        Three conditions, and two of them were paid for. A cart's cargo overhangs its own frame, so
        a MAJORITY of that frame identifies it, never all of it — and a majority alone also matches
        a RAIL JUNCTION, where the track fans out far enough to fill the frame, and an EMPTY CELL
        BETWEEN TWO REGIONS, which is framed by the regions' own edges. What rules the junction out
        is the middle: a cart always has something else in it, its deck or its load, while a
        junction is track all the way through. What rules the region edge out is that a board draws
        its structure — its track, its region borders, its shadows — in ONE colour, and a cart has
        to be told apart from the track it rides on, so a cart's livery is never the track's colour.
        Both were measured as phantom loaded carts: routes the planner does not have, and holes the
        planner will not land in.
        """
        inner, _c, n = raw[cell]
        return (colour not in (gap, bg, socket_col) and colour != rail_col
                and n >= _LIVERY and centre(inner) != colour)

    livery = Counter(colour for cell, (_inner, colour, _n) in raw.items()
                     if liveried(cell, colour))
    cart_col = livery.most_common(1)[0][0] if livery else None

    board = Board(pitch, base_y, base_x)
    board.moving = off_phase
    board.window = set(raw)

    for cell, (inner, colour, _n) in raw.items():
        if cart_col is not None and colour == cart_col and liveried(cell, colour):
            board.carts.add(cell)
            board.rails.add(cell)
            d = _disc(inner)
            if d is not None:
                board.pieces[cell] = d[0]
            elif _flat(inner) is None:
                board.cargo.add(cell)
        elif cell in plain:
            board.sockets.add(cell)
        elif cell in discs:
            board.sockets.add(cell)
            board.pieces[cell] = discs[cell]
        elif rail_col is not None and mids.get(cell) == rail_col:
            board.rails.add(cell)
        elif int((inner != bg).sum()) >= _INNER * _INNER - 2:
            board.obstacles.add(cell)

    if len(board.sockets) + len(board.carts) < _MIN_CELLS:
        return None
    return board


# --------------------------------------------------------------------------- the model

class Model:
    """The board as the planner believes it, in coordinates fixed at the level's start."""

    def __init__(self) -> None:
        self.sockets: set[Cell] = set()
        self.rails: set[Cell] = set()
        self.obstacles: set[Cell] = set()
        self.pieces: dict[Cell, int] = {}
        self.carts: set[Cell] = set()
        self.cargo: set[Cell] = set()
        self.pitch = 0
        self.oy = 0                  # pixel of world cell (0, 0), refreshed on every alignment
        self.ox = 0
        self.window: set[Cell] = set()

    def known(self) -> set[Cell]:
        return self.sockets | self.rails | self.obstacles

    def state(self) -> tuple[Any, ...]:
        return (tuple(sorted(self.pieces.items())), tuple(sorted(self.carts)),
                tuple(sorted(self.cargo)))

    def pixel(self, cell: Cell) -> tuple[int, int]:
        off = _INNER // 2
        return (self.ox + cell[1] * self.pitch + off, self.oy + cell[0] * self.pitch + off)


def _seen(state: tuple[Any, ...], window: set[Cell]) -> tuple[Any, ...]:
    """The part of a state the screen can show — the only part a frame is able to confirm."""
    return (tuple((c, v) for c, v in state[0] if c in window),
            tuple(c for c in state[1] if c in window),
            tuple(c for c in state[2] if c in window))


def _align(model: Model, board: Board) -> Delta | None:
    """Offset mapping the board's cells into the model's coordinates, or None.

    Matched on the FIXED part only — holes, rails and bolted obstacles — because everything else
    moves between frames and a stale frame's pieces would drag the alignment onto the wrong cell.

    ⛔ Agreement is scored inside the strip that was visible BOTH BEFORE AND AFTER, not over the
    whole screen. A scroll reveals territory that is legitimately absent from the map, so demanding
    that most of the screen be already known rejects every correct offset the moment the board
    moves, and the tool then re-anchors to a fresh coordinate system and forgets the board it has
    spent forty actions mapping.
    """
    obs = board.fixed()
    known = model.known()
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
    if best is None or best[1] < min(_MIN_MATCH, len(known), len(obs)) or best[0] <= 0:
        return None
    return best[2]


# --------------------------------------------------------------------------- planning

# A move is ("jump", from_cell, direction) or ("drive", None, direction).
Move = tuple[str, Any, Delta]

# state = (pieces, carts, cargo); the lattice itself is carried alongside as `Ground`.
Ground = tuple[frozenset, frozenset, frozenset]      # sockets, rails, obstacles


def _shunt(carts: tuple[Cell, ...], cargo: tuple[Cell, ...], pieces: dict[Cell, int],
           rails: frozenset, d: Delta,
           ) -> tuple[tuple[Cell, ...], tuple[Cell, ...], dict[Cell, int]] | None:
    """Shift every cart one cell along the rails, each taking whatever rests on it.

    The leading cart resolves first so a train shifts together, and one blocked by another simply
    stays — which is what the engine does.
    """
    order = sorted(carts, key=lambda c: -(c[0] * d[0] + c[1] * d[1]))
    live = set(carts)
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
            tuple(sorted(moved.get(c, c) for c in cargo)),
            {moved.get(c, c): v for c, v in pieces.items()})


def _successors(state: Any, ground: Ground, noncapture: frozenset[int]):
    """Every legal (next state, move, action cost) — jumps first, then the four cart drives.

    ⛔ Planning runs over the whole map, NOT over what is on screen. The camera follows a piece
    that is riding a cart, so a jump off screen now is on screen by the time the drives before it
    have run; filtering the search by the current window deletes the only route back across a board
    and leaves a piece parked at the far end with no plan.
    """
    sockets, rails, obstacles = ground
    pieces = dict(state[0])
    carts, cargo = state[1], state[2]
    cart_set, cargo_set = set(carts), set(cargo)
    # A stepping stone is anything solid: a piece, a bolted obstacle, or a cart's cargo.
    solid = set(pieces) | obstacles | cargo_set
    for cell, colour in pieces.items():
        for d in DIRS:
            mid = (cell[0] + d[0], cell[1] + d[1])
            if mid not in solid:
                continue
            land = (cell[0] + 2 * d[0], cell[1] + 2 * d[1])
            if land in solid or land in pieces:
                continue
            # A free hole on the lattice, or the empty deck of a cart.
            if not ((land in sockets and land not in cart_set) or land in cart_set):
                continue
            nxt = dict(pieces)
            del nxt[cell]
            if pieces.get(mid) == colour and colour not in noncapture:
                del nxt[mid]
            nxt[land] = colour
            yield (tuple(sorted(nxt.items())), carts, cargo), ("jump", cell, d), 2
    if carts:
        for d in DIRS:
            res = _shunt(carts, cargo, pieces, rails, d)
            if res is None:
                continue
            nc, ng, np_ = res
            yield (tuple(sorted(np_.items())), nc, ng), ("drive", None, d), 1


def _ground(m: Model) -> Ground:
    return (frozenset(m.sockets), frozenset(m.rails), frozenset(m.obstacles))


def _path(parent: dict[Any, tuple[Any, Move]], node: Any) -> list[Move]:
    out: list[Move] = []
    while node in parent:
        node, mv = parent[node]
        out.append(mv)
    out.reverse()
    return out


def _won(state: Any, targets: set[int]) -> bool:
    seen = Counter(v for _c, v in state[0])
    return all(seen[c] <= 1 for c in targets)


def capture_reachable(state: Any, ground: Ground, noncapture: frozenset[int],
                      node_cap: int = 25_000) -> bool:
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
        for ns, _mv, step in _successors(st, ground, noncapture):
            nc = cost + step
            if nc < cost_of.get(ns, 1 << 30):
                cost_of[ns] = nc
                tie += 1
                heapq.heappush(heap, (nc, tie, ns))
    return False


def plan_level(m: Model, noncapture: frozenset[int], node_cap: int = _NODE_CAP,
               lookahead: int = _LOOKAHEAD,
               why: Counter | None = None) -> tuple[list[Move], bool] | None:
    """Cheapest action sequence to the whole level, or failing that to a SURVIVABLE next capture.

    Returns (moves, solved). `solved` is True when the sequence takes every capturable colour down
    to a single piece; otherwise it is a short route to one more capture.

    ⛔ "Shortest route to the next capture" is NOT safe, and this board proves it out of the game's
    own mouth. A capture cannot be undone, so a cheap one can leave a position from which nothing
    further can ever be taken — and the game SHIPS A DETECTOR for exactly that, greying the pieces
    out and offering a restart, which is how a designer says "this branch is lost". Chasing the
    cheapest capture walks a level with six of them into that detector after three, every time.
    Measured on the full board: at the third capture, the seven cheapest candidates are each a
    dead end and the eighth is not — taking it finishes the level in 87 actions against a human
    baseline of 148, where taking the cheapest strands it three captures in with nothing legal
    left but shunting empty carts.
    So the rule is: prefer the cheapest capture FROM WHICH ANOTHER IS STILL REACHABLE. Only prefer,
    never require — the map is partial, so "nothing further is reachable" is often just "the rest
    of the board has not been seen yet", and refusing to move at all is strictly worse than
    risking a wrong branch.
    """
    if not m.pieces:
        return None
    counts = Counter(m.pieces.values())
    targets = {c for c, n in counts.items() if n >= 2 and c not in noncapture}
    if not targets:
        if why is not None:
            why["plan:no-pair"] += 1
        return None
    ground = _ground(m)
    total = len(m.pieces)
    start = m.state()
    cost_of: dict[Any, int] = {start: 0}
    parent: dict[Any, tuple[Any, Move]] = {}
    heap: list[tuple[int, int, Any]] = [(0, 0, start)]
    tie = 0
    captures: list[Any] = []
    expanded = 0

    while heap:
        cost, _t, state = heapq.heappop(heap)
        if cost > cost_of.get(state, cost):
            continue
        if _won(state, targets):
            return _path(parent, state), True
        if len(state[0]) < total and len(captures) < lookahead:
            captures.append(state)
        expanded += 1
        if expanded > node_cap:
            break
        for ns, mv, step in _successors(state, ground, noncapture):
            nc = cost + step
            if nc < cost_of.get(ns, 1 << 30):
                cost_of[ns] = nc
                parent[ns] = (state, mv)
                tie += 1
                heapq.heappush(heap, (nc, tie, ns))

    if not captures:
        if why is not None:
            why["plan:no-capture-reachable"] += 1
        return None
    for state in captures:
        if _won(state, targets) or capture_reachable(state, ground, noncapture):
            return _path(parent, state), False
    return _path(parent, captures[0]), False


def _spread(state: Any, noncapture: frozenset[int]) -> int | None:
    """How far apart the closest capturable PAIR is, or None when no colour has two pieces left."""
    by_colour: dict[int, list[Cell]] = {}
    for cell, v in state[0]:
        by_colour.setdefault(v, []).append(cell)
    best: int | None = None
    for v, cells in by_colour.items():
        if v in noncapture or len(cells) < 2:
            continue
        for i, a in enumerate(cells):
            for b in cells[i + 1:]:
                d = abs(a[0] - b[0]) + abs(a[1] - b[1])
                best = d if best is None else min(best, d)
    return best


def approach_moves(m: Model, noncapture: frozenset[int], visited: set[Any],
                   cost_cap: int = 30, node_cap: int = 60_000,
                   why: Counter | None = None) -> list[Move]:
    """Cheapest sequence that brings two pieces of one colour closer together.

    ⛔ This tier exists because the obvious one is a TRAP. "Move a piece toward where the map runs
    out" sounds like the right thing to do on a board wider than the screen, and it is — right up
    until the piece reaches the end of a spur, where the count of unknown cells around it is at its
    highest and every move makes it lower. A dead end is a MAXIMUM of that objective, so the tool
    parks there and reports it has nothing left to do. Measured twice on the same board, at both
    ends of the same length of track.

    What the board is actually asking for is never in doubt: two pieces of a colour have to end up
    two cells apart. Distance between them is an objective a dead end cannot flatter, it is defined
    on a partial map, and closing it is what eventually produces a capture — so it is worth an
    action even when the capture itself is still out of reach.
    """
    start = m.state()
    base = _spread(start, noncapture)
    if base is None:
        if why is not None:
            why["approach:no-pair"] += 1
        return []
    ground = _ground(m)
    cost_of: dict[Any, int] = {start: 0}
    parent: dict[Any, tuple[Any, Move]] = {}
    heap: list[tuple[int, int, Any]] = [(0, 0, start)]
    tie = 0
    best: tuple[int, int, Any] | None = None
    while heap:
        cost, _t, state = heapq.heappop(heap)
        if cost > cost_of.get(state, cost) or cost > cost_cap:
            continue
        if state != start and state not in visited:
            d = _spread(state, noncapture)
            if d is not None and (best is None or (d, cost) < (best[0], best[1])):
                best = (d, cost, state)
        if len(cost_of) > node_cap:
            break
        for ns, mv, step in _successors(state, ground, noncapture):
            nc = cost + step
            if nc <= cost_cap and nc < cost_of.get(ns, 1 << 30):
                cost_of[ns] = nc
                parent[ns] = (state, mv)
                tie += 1
                heapq.heappush(heap, (nc, tie, ns))
    if best is None or best[0] >= base:
        if why is not None:
            why["approach:all-visited" if best is None else "approach:no-gain"] += 1
        return []
    return _path(parent, best[2])


def _novelty_field(m: Model, touched: set[Cell]) -> dict[Cell, int]:
    """Every known cell, labelled by how far it is from anywhere a piece has already stood."""
    known = m.known() | m.carts
    field: dict[Cell, int] = {c: 0 for c in touched if c in known}
    if not field:
        return {}
    queue = deque(field)
    while queue:
        c = queue.popleft()
        for d in DIRS:
            n = (c[0] + d[0], c[1] + d[1])
            if n in known and n not in field:
                field[n] = field[c] + 1
                queue.append(n)
    return field


def travel_moves(m: Model, noncapture: frozenset[int], touched: set[Cell], visited: set[Any],
                 cost_cap: int = 40, node_cap: int = 60_000,
                 why: Counter | None = None) -> list[Move]:
    """Ride a cart to somewhere no piece has been.

    ⛔ The objective here was WRONG for two rounds and the wrong version is instructive, because it
    is the obvious one: "move a piece toward where the map runs out", scored as unknown cells near
    a piece. That has its MAXIMUM AT A DEAD END — the tip of a spur is surrounded by nothing, so
    every move away from it scores lower and the tool parks there and reports it has nothing left
    to do. Measured at both ends of the same length of track, on two different boards.

    What the board is really offering is a RAIL THAT LEAVES THE REGION YOU CAN SEE, and a rail
    going somewhere is itself the evidence that there is a somewhere to go. So the objective is
    distance from the cells pieces have ALREADY occupied, measured along the known lattice. A dead
    end far from home scores above a dead end next to it, which is the ordering the previous metric
    got backwards, and driving a cart with a piece aboard is the cheapest way to climb it — which
    is exactly the move the camera follows, so it pays twice.

    The budget is deliberately loose. A journey between regions is only expensive if the
    alternative pays something; when the visible region is exhausted the alternative pays zero,
    and forty drives against a six-hundred-action level is noise.
    """
    field = _novelty_field(m, touched)
    if not field:
        if why is not None:
            why["travel:no-field"] += 1
        return []
    ground = _ground(m)

    def novelty(state: Any) -> int:
        return max((field.get(cell, 0) for cell, _v in state[0]), default=0)

    start = m.state()
    base = novelty(start)
    cost_of: dict[Any, int] = {start: 0}
    parent: dict[Any, tuple[Any, Move]] = {}
    heap: list[tuple[int, int, Any]] = [(0, 0, start)]
    tie = 0
    best: tuple[int, int, Any] | None = None
    while heap:
        cost, _t, state = heapq.heappop(heap)
        if cost > cost_of.get(state, cost) or cost > cost_cap:
            continue
        if state != start and state not in visited:
            score = novelty(state)
            if best is None or (score, -cost) > (best[0], -best[1]):
                best = (score, cost, state)
        if len(cost_of) > node_cap:
            break
        for ns, mv, step in _successors(state, ground, noncapture):
            nc = cost + step
            if nc <= cost_cap and nc < cost_of.get(ns, 1 << 30):
                cost_of[ns] = nc
                parent[ns] = (state, mv)
                tie += 1
                heapq.heappush(heap, (nc, tie, ns))
    if best is None or best[0] <= base:
        if why is not None:
            why["travel:all-visited" if best is None else "travel:no-gain"] += 1
        return []
    return _path(parent, best[2])


def probe_moves(m: Model, noncapture: frozenset[int], touched: set[Cell], visited: set[Any],
                cost_cap: int = 12, node_cap: int = 20_000,
                why: Counter | None = None) -> list[Move]:
    """Cheapest way to put a piece somewhere it has never stood on this level.

    The last tier. Some boards open only when a piece reaches a particular cell, which no amount of
    looking at the current map predicts — so when neither a capture nor the frontier can be
    improved, the move worth making is the one that changes something the board has not seen yet.
    """
    ground = _ground(m)
    start = m.state()
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
            return _path(parent, state)
        if len(cost_of) > node_cap:
            break
        for ns, mv, step in _successors(state, ground, noncapture):
            nc = cost + step
            if nc <= cost_cap and nc < cost_of.get(ns, 1 << 30):
                cost_of[ns] = nc
                parent[ns] = (state, mv)
                tie += 1
                heapq.heappush(heap, (nc, tie, ns))
    if why is not None:
        why["probe:nowhere-new"] += 1
    return []


# --------------------------------------------------------------------------- the tool

class RailPegTool:
    """Solve a peg board served by rail carts, loaded or empty."""

    name = "railpeg"

    def __init__(self) -> None:
        self._tiers: Counter[str] = Counter()
        self._why: Counter[str] = Counter()
        self._dirmap: dict[Delta, int] = {}       # lattice direction -> simple action id
        self._excluded: dict[Delta, set[int]] = {}
        self._noncapture: frozenset[int] = frozenset()
        self.reset()

    # -- lifecycle ---------------------------------------------------------
    def reset(self) -> None:
        self._model: Model | None = None
        self._plan: list[Move] = []
        self._history: list[tuple[Any, ...]] = []
        self._pending: tuple[int, tuple[Cell, ...], int, Delta] | None = None
        self._refused: tuple[tuple[Any, ...], int] | None = None
        self._doubt = 0
        self._misaligned = 0
        # Frames still owed to a cart that was just told to move; only a drive moves one.
        self._driving = 0
        self._visited: set[Any] = set()
        self._ncarts = 0
        self._barren = 0
        self._known = 0
        self._closest: int | None = None
        self._claiming = False
        self._elsewhere = False
        self._npieces = 0
        self._sincecapture = 0
        self._touched: set[Cell] = set()
        self._ntouched = 0
        self._peaked = 0
        self._prev_seen: tuple[Any, ...] | None = None
        self._settles = 0
        self._retried = False
        self._read_key: bytes | None = None
        self._read: Board | None = None
        self._sync_key: bytes | None = None
        self._sync_res: tuple[Model, bool] | None = None

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """Nothing is learned from the flag alone — a cart's displacement and a refused capture are
        both positional, so both are read off the NEXT board in `propose`."""

    # -- frame -------------------------------------------------------------
    def _board(self, g: np.ndarray) -> Board | None:
        """One reading per distinct frame — `detect` and `propose` want the same answer."""
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
        m.obstacles = set(board.obstacles)
        m.pieces = dict(board.pieces)
        m.carts = set(board.carts)
        m.cargo = set(board.cargo)
        m.pitch, m.oy, m.ox = board.pitch, board.oy, board.ox
        m.window = set(board.window)
        self._touched = set(m.pieces)
        return m

    def _restart(self, board: Board) -> tuple[Model, bool]:
        self._model = self._adopt(board)
        self._ncarts = len(self._model.carts)
        self._history = [self._model.state()]
        self._plan = []
        self._prev_seen = None
        self._refused = None
        self._sync_res = (self._model, True)
        return self._sync_res

    def _sync(self, g: np.ndarray) -> tuple[Model, bool] | None:
        """Fold this frame into the model, and learn from it.

        Returns (model, placed) — `placed` is False when the board could not be located on screen
        at whole-cell precision, which means it is mid-scroll and nothing may be clicked.
        """
        key = g.tobytes()
        if key == self._sync_key:
            # ⛔ Idempotent per frame. The harness asks `detect` and then `propose` about the SAME
            # board, and this method LEARNS — running it twice makes a frame look as if it had
            # settled (it equals the reading this method itself just stored) and installs a stale
            # board over a correct model.
            return self._sync_res
        board = self._board(g)
        if board is None:
            self._sync_key, self._sync_res = key, None
            return None
        self._sync_key = key
        self._driving = max(0, self._driving - 1)
        if self._model is None:
            return self._restart(board)
        m = self._model
        off = _align(m, board) if board.pitch == m.pitch else None
        if off is None:
            # ⛔ A board that cannot be placed for several frames running is not a board that is
            # scrolling, it is a DIFFERENT board. The harness hands over on the transitional frame
            # of a level-up, so the first board this tool sees on a new level can be the last board
            # of the old one; anchoring to that and then refusing every frame after it reads as a
            # tool that solves a level alone and stalls inside the harness.
            self._misaligned += 1
            if self._misaligned < 6:
                self._sync_res = (m, False)
                return self._sync_res
            self._misaligned = 0
            return self._restart(board)
        self._misaligned = 0

        def shift(c: Cell) -> Cell:
            return (c[0] + off[0], c[1] + off[1])

        m.pitch = board.pitch
        # world cell = board cell + off, so the pixel of world (0, 0) sits back by that offset.
        m.oy = board.oy - off[0] * board.pitch
        m.ox = board.ox - off[1] * board.pitch
        m.window = {shift(c) for c in board.window}
        carts = {shift(c) for c in board.carts}
        cargo = {shift(c) for c in board.cargo}
        m.sockets |= {shift(c) for c in board.sockets}
        m.rails |= {shift(c) for c in board.rails}
        m.sockets -= carts
        seen = (tuple(sorted((shift(c), v) for c, v in board.pieces.items())),
                tuple(sorted(carts)), tuple(sorted(cargo)))

        here = _seen(m.state(), m.window)
        # ⛔ Settled-ness is decided BEFORE the state is compared, and neither the frame hash nor
        # the changed flag can decide it. A cart mid-slide straddles two cells and reads as no cart
        # at all — a perfectly well-formed board that happens to be false. Carts are CONSERVED: one
        # neither on screen nor remembered off it has not left the board, it is mid-slide, and
        # losing it deletes the only route between two halves of a board the lattice does not
        # otherwise connect.
        #
        # ⛔ But that conservation law is a statement about the MODEL, so a model that is simply
        # WRONG about a cart makes it true FOREVER — measured as a tool holding a winning plan and
        # spending inert clicks waiting for a board that had already settled. The rule is narrowed
        # by the mechanic instead of by patience: ONLY A DRIVE MOVES A CART. After a jump, or after
        # an inert click, a cart the frame does not show is not mid-slide — it is a cart the model
        # should never have believed in, and the frame is right. Bounding the wait by a frame count
        # instead was measured and REJECTED: it cost ~55 actions across levels 2-5 and unlocked
        # nothing, because it also overrode the honest mid-slide readings the law is there for.
        merged = len(carts) + len([c for c in m.carts if c not in m.window])
        slipping = self._driving > 0 and (len(carts) < len(here[1]) or merged < self._ncarts)
        unsettled = (board.moving > 0
                     or slipping
                     or bool({shift(c) for c in board.obstacles} & m.sockets))
        self._calibrate(seen[1], settled=not unsettled)
        if not unsettled:
            # ⛔ An obstacle is the ONLY thing on this board that an animation can invent, and it
            # is therefore the only claim that is both DEFERRED and RETRACTABLE.
            #   Deferred: a piece in flight is drawn across two cells and fills whatever it passes
            #   over, which reads exactly like bolted furniture. So obstacles are read off SETTLED
            #   frames only — the same test that already knows a piece is in the air. Believing
            #   them from any frame put a phantom obstacle on a plain hole, and a phantom obstacle
            #   is a phantom STEPPING STONE: the planner keeps proposing a jump across it, the
            #   engine refuses the jump because there is nothing to jump over, the board does not
            #   change, and the tool re-plans the same move forever.
            #   Retractable: furniture is mutually exclusive with both a hole and a track, so any
            #   cell the board has since shown to be either is struck off retrospectively, not
            #   merely at the moment it is added. One frame of a piece flying over a CART left that
            #   cart marked solid for the rest of the level, and a solid cart is not a landing, so
            #   the level's only capture became unreachable.
            m.obstacles |= {shift(c) for c in board.obstacles}
        m.obstacles -= m.sockets | m.rails
        if unsettled:
            # ⛔ Do NOT play on through this. It looks as though an unsettled frame should only
            # stop the model being BELIEVED, not stop the tool ACTING — the lattice does not move
            # while a cart slides, so the click coordinates are still good. Measured: acting
            # anyway takes this game from five levels to ONE. Clicking into a board that has not
            # finished resolving the last action is how a plan gets played into a position that no
            # longer exists, and every level after the first is lost to it. The wait is the tool's
            # only synchronisation with the engine and it is load-bearing.
            self._sync_res = (m, bool(self._plan))
            return self._sync_res
        if self._refused is not None and seen == _seen(self._refused[0], m.window):
            # The capture the model predicted did not happen: this colour cannot be taken.
            self._noncapture = self._noncapture | {self._refused[1]}
            self._refused = None
            self._install(m, seen)
            self._sync_res = (m, True)
            return self._sync_res
        if seen == here or any(seen == _seen(h, m.window) for h in self._history):
            # Either the frame agrees, or it reproduces a state this tool has already left — an
            # animation one action behind. The simulation stays the belief either way.
            self._refused = None if seen == here else self._refused
            self._doubt = 0
            self._prev_seen = seen
            self._sync_res = (m, True)
            return self._sync_res
        # A frame agreeing with nothing predicted is far likelier to be mid-animation than a true
        # divergence, so it is believed only once it stops moving or has persisted.
        self._doubt += 1
        settled = seen == self._prev_seen and not board.moving
        self._prev_seen = seen
        if settled or self._doubt >= 3:
            self._refused = None
            self._doubt = 0
            self._install(m, seen)
            self._sync_res = (m, True)
            return self._sync_res
        self._sync_res = (m, bool(self._plan))
        return self._sync_res

    def _install(self, m: Model, seen: tuple[Any, ...]) -> None:
        """Take the frame's word for what it can SEE, and keep what it cannot.

        ⛔ Off screen is not gone. Overwriting the whole board from a frame showing a third of it
        makes the planner declare a level solved with most of its pieces still standing, just
        scrolled away.
        """
        w = m.window
        m.pieces = {c: v for c, v in m.pieces.items() if c not in w} | dict(seen[0])
        m.carts = {c for c in m.carts if c not in w} | set(seen[1])
        m.cargo = {c for c in m.cargo if c not in w} | set(seen[2])
        self._touched |= set(m.pieces)
        # The conservation count is only as good as the model it was taken from; adopting a board
        # replaces the model, so it has to replace the count too or the old one latches.
        self._ncarts = len(m.carts)
        self._history = [m.state()]
        self._plan = []

    def _calibrate(self, carts: tuple[Cell, ...], settled: bool) -> None:
        """Read which way the one probed action pointed, out of the carts' displacement.

        Held open for a few frames: the probe's own frame can be an animation behind, and a mapping
        abandoned too early costs another action to re-probe.
        """
        if self._pending is None:
            return
        aid, before, age, want = self._pending
        if carts and len(carts) == len(before):
            deltas = {(b[0] - a[0], b[1] - a[1]) for a, b in zip(before, carts)}
            deltas.discard((0, 0))
            if len(deltas) == 1:
                d = deltas.pop()
                if d in DIRS:
                    self._dirmap[d] = aid
                self._pending = None
                return
            if not deltas and settled:
                # A drive that works leaves the board mid-slide; a settled board with every cart
                # where it was is the action saying it does not point that way.
                self._excluded.setdefault(want, set()).add(aid)
                self._pending = None
                return
        if age >= 3:
            self._excluded.setdefault(want, set()).add(aid)
            self._pending = None
            return
        self._pending = (aid, before, age + 1, want)

    # -- planning ----------------------------------------------------------
    def _ensure_plan(self, m: Model) -> float:
        """Fill the queue of moves and report how strong the claim on this board is."""
        if self._plan:
            return 0.9
        # ⛔ A WIN THAT DID NOT WIN IS PROOF THE BOARD HAS PIECES THIS TOOL CANNOT SEE, and it is
        # the only such proof available on a partial map. "Two captures remain and both are here"
        # and "six remain and four are elsewhere" are the SAME OBSERVATION to a planner that counts
        # what is on screen, so the planner declares a win, plays it, the level does not end, and
        # it declares the same win again. Measured on the widest board: 728 planning decisions in a
        # row, every one of them a claimed win, and the tier that would have gone looking never ran
        # once — it sits behind "no capture is reachable", and a local win is always reachable.
        # The harness resets this tool on a level-up, so still being here with the plan played out
        # IS the refutation.
        if self._claiming:
            self._elsewhere = True
            self._claiming = False
        pieces = len(m.pieces)
        if pieces < self._npieces:
            self._sincecapture = 0
        self._npieces = pieces
        # Once the board is known to extend past the screen, a run of plans that takes nothing is
        # not bad luck, it is the visible region being finished. Then travel outranks it.
        stuck = self._elsewhere and self._sincecapture >= _LOCAL_PATIENCE
        if stuck:
            self._why['plan:skipped-region-finished'] += 1
        found = None if stuck else plan_level(m, self._noncapture, why=self._why)
        if found is not None and found[0]:
            self._plan = list(found[0])
            self._claiming = found[1]
            self._sincecapture += 1
            self._tiers["win" if found[1] else "capture"] += 1
            return 0.95 if found[1] else 0.9
        # ⛔ Barren means NOTHING GOT BETTER, and there are two ways for something to get better on
        # a board this tool can only half see: it can learn more board, or it can bring a pair
        # closer to a capture. Counting only the first retires the tool in the middle of a long
        # haul across the map, where nothing new is on screen for a dozen actions at a time.
        known = len(m.known())
        near = _spread(m.state(), self._noncapture)
        gained = known > self._known
        closed = near is not None and (self._closest is None or near < self._closest)
        # ⛔ And a THIRD way, which is the one a long haul across a wide board actually shows:
        # a piece standing where no piece has stood before. Learning board and closing a pair are
        # both invisible for the dozen actions it takes to ride a cart from one region to the next,
        # so counting only those retires the tool MID-RIDE — measured twice, bidding zero with a
        # perfectly good eight-drive plan already in hand.
        stepped = len(self._touched) > self._ntouched
        if gained or closed or stepped:
            self._known = max(known, self._known)
            self._ntouched = max(self._ntouched, len(self._touched))
            if near is not None:
                self._closest = near if self._closest is None else min(self._closest, near)
            self._barren = 0
        # ⛔ The barren cap exists so this tool hands a level it cannot solve to whatever comes
        # next. That is the right instinct on a board it has SEEN ALL OF — and the wrong one on a
        # board it has PROVED extends past the screen, where "nothing got better" describes the
        # journey, not the position. Giving up there is giving up on pieces known to exist.
        if self._barren >= 3 and not self._elsewhere:
            self._why['barren-cap'] += 1
            return 0.0
        # ⛔ ORDER, not just membership. Closing the distance between two pieces is a LOCAL
        # objective, and once the board is known to extend past the screen a local objective is
        # not evidence of progress — it is the tool tidying a region it has already finished.
        # Measured: approach kept producing drive-only plans that moved no piece anywhere new,
        # spending the whole barren budget, so travel was reached ONCE in a thousand actions and
        # the four pieces off screen were never looked for. When the visible region is known to be
        # insufficient, going to look outranks rearranging what is already here.
        order = ["travel", "approach"] if self._elsewhere else ["approach", "travel"]
        moves: list[Move] = []
        tier = ""
        for tier in order:
            moves = (travel_moves(m, self._noncapture, self._touched, self._visited,
                                  why=self._why)
                     if tier == "travel"
                     else approach_moves(m, self._noncapture, self._visited, why=self._why))
            if moves:
                break
        if not moves:
            moves = probe_moves(m, self._noncapture, self._touched, self._visited,
                                why=self._why)
            tier = "probe"
        if not moves:
            self._tiers["none"] += 1
            return 0.0
        self._tiers[tier] += 1
        self._barren += 1
        state = m.state()
        ground = _ground(m)
        for mv in moves:
            state = self._step(state, ground, mv)
        self._visited.add(state)
        self._plan = list(moves)
        return 0.75

    @staticmethod
    def _step(state: Any, ground: Ground, move: Move) -> Any:
        """The state a move leads to, without touching the model — used to mark a target."""
        for ns, mv, _c in _successors(state, ground, frozenset()):
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
                # What the board would look like had the capture been refused — the only evidence
                # separating an uncapturable colour from a lagging frame.
                refused = dict(m.pieces)
                refused[mid] = colour
                self._refused = ((tuple(sorted(refused.items())), tuple(sorted(m.carts)),
                                  tuple(sorted(m.cargo))), colour)
        else:
            res = _shunt(tuple(sorted(m.carts)), tuple(sorted(m.cargo)), m.pieces,
                         frozenset(m.rails), d)
            if res is not None:
                carts, cargo, pieces = res
                m.carts, m.cargo, m.pieces = set(carts), set(cargo), pieces
        self._touched |= set(m.pieces)
        self._history.append(m.state())
        self._history = self._history[-_HISTORY:]

    @staticmethod
    def _settle_click(g: np.ndarray) -> Step:
        """One inert click, used only to let an animation drain. Kept away from the frame's edges,
        where boards of this kind draw their counters and their controls."""
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
        # ⛔ Two pieces EVER, not two pieces NOW. Past the first capture a wide board often shows a
        # single piece with the rest scrolled off, and that is exactly the moment going to look is
        # the right move — refusing it strands the tool one capture into a level it can finish.
        self._peaked = max(self._peaked, len(m.pieces))
        if self._peaked < 2:
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
        # transitional frame of a level-up, showing the level just finished. Refusing it is NOT the
        # same as refusing a one-piece board later on: mid-level a single visible piece usually
        # means the rest are scrolled off, which is exactly when going to look is the right move.
        self._peaked = max(self._peaked, len(m.pieces))
        if self._peaked < 2 or not self._ensure_plan(m):
            return []
        move = self._plan.pop(0)
        kind, cell, d = move
        if kind == "jump":
            colour = m.pieces.get(cell)
            land = (cell[0] + 2 * d[0], cell[1] + 2 * d[1])
            if colour is None or not (land in m.sockets or land in m.carts):
                self._plan = []
                return []
            steps = [(6, m.pixel(cell)), (6, m.pixel(land))]
            if any(not (0 <= x < g.shape[1] and 0 <= y < g.shape[0]) for _a, (x, y) in steps):
                # The camera has not caught up with the plan; go and move something rather than
                # click at a cell that is not on the screen.
                self._plan = []
                if self._retried:
                    return []
                moves = travel_moves(m, self._noncapture, self._touched, self._visited)
                if not moves:
                    return []
                self._plan = list(moves)
                self._retried = True
                try:
                    return self.propose(frames, obs)
                finally:
                    self._retried = False
            self._advance(m, move)
            self._driving = 0
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
            self._pending = (aid, tuple(sorted(m.carts)), 0, d)
            self._driving = _SLIDE
            return [(aid, None)]
        self._advance(m, move)
        self._driving = _SLIDE
        return [(aid, None)]
