"""Slot-launch tool — park every loose piece inside the outline cut for it.

The mechanic, recovered from the frames and confirmed against the engine's own dispatch:

* The board carries **outlines** — closed rings of one colour whose hollow interior is exactly the
  shape of one piece, inset by a single cell. A level clears when EVERY outline holds its piece.
* One piece at a time is **held**. A click on a piece takes the hold; the four simple actions move
  the held piece by one lattice cell.
* A move into a wall or into the **glide field** does nothing at all. A move into another piece does
  not move the holder — it **launches** the piece it touched, which then slides on its own for a
  fixed run of cells and keeps going for as long as it is over the glide field, stopping when a wall
  or a jammed chain refuses it. That is the whole puzzle: the holder cannot cross the glide field,
  so anything on the far side has to arrive by launch, and the launch length is what has to be
  aimed with.

⛔ Why this plans instead of searching blind. The launch is not a nudge: one press throws a piece
five cells or further, so a piece's reachable set is a handful of landing squares and the ordinary
"walk toward the goal" gradient points the wrong way for most of them. The tool builds a faithful
model of the launch and searches THAT, guided by a per-piece relaxed distance that already knows
what a launch costs.

⛔ Frame-only. Nothing here knows which game it is. The lattice step, the wall colour, the glide
field, the outlines, the pieces and which piece is a click target are all derived from the frame:
an outline is a component whose enclosed hole is its own bounding box inset by one, a piece is a
component whose shape matches some outline's hole, a click target is a piece carrying a marker of
a second colour, and the wall colour is the one that fills a whole outer line of the frame.
"""

from __future__ import annotations

import heapq
import time
from collections import Counter, deque
from math import gcd
from typing import Any

import numpy as np

from admorphiq.tools.base import Step, availability, has_frame, levels_completed
from admorphiq.tools.segment import background, components

__all__ = ["SlotLaunchTool", "read_board", "Board", "Piece", "volatile"]

Cell = tuple[int, int]
_DIRS: dict[int, Cell] = {1: (-1, 0), 2: (1, 0), 3: (0, -1), 4: (0, 1)}
# The launch runs this many cells before it is allowed to settle. MEASURED, not chosen: a piece
# thrown across an empty board lands exactly five cells on, on every board that has one.
_RUN = 5
_MAX_SLIDE = 60
_NODE_CAP = 900_000
_TIME_CAP = 30.0
# The guide never charges for the piece that has to come and do the launching, so it reads far too
# low on crowded boards. Leaning on it is what makes a four-piece board finish at all; the cost is
# a few extra presses, which is cheaper than not clearing the level.
_LEAN = 3
# How long to hold one waiting square before trying the next. The board's own clock is unknown, so
# this is a small fixed count rather than anything derived.
_HOLD = 8
# ⛔ Waiting has to END. Loitering changes the board, so the harness's own stall detector never fires
# and a tool that waits forever holds a game it is not going to finish. After this many presses with
# no route to the goal, withdraw and let the next tool have the board.
_ROAM_CAP = 80


class Piece:
    """One loose object on the board: its shape, where it sits, and whether it can be held."""

    __slots__ = ("mask", "pos", "marks", "h", "w")

    def __init__(self, mask: frozenset[Cell], pos: Cell, marks: frozenset[int], h: int, w: int) -> None:
        self.mask = mask
        self.pos = pos
        self.marks = marks
        self.h = h
        self.w = w

    @property
    def clickable(self) -> bool:
        """A piece carrying a marker of a second colour is one the board lets you take hold of."""
        return bool(self.marks)


class Board:
    """Everything the planner needs, all of it read off one frame."""

    __slots__ = ("step", "pieces", "targets", "shapes", "walk_ok", "slide_ok", "on_glide",
                 "rows", "held", "walls", "glide", "rings", "phase", "floor")

    def __init__(self) -> None:
        self.step = 0
        self.pieces: list[Piece] = []
        self.targets: list[Cell] = []
        self.shapes: list[frozenset[Cell]] = []
        self.rings: list[tuple[int, frozenset[Cell]]] = []
        self.phase: Cell = (0, 0)
        self.floor = 0
        self.walk_ok: list[np.ndarray] = []
        self.slide_ok: list[np.ndarray] = []
        self.on_glide: list[np.ndarray] = []
        self.rows = 0
        self.held: int | None = None


# --- perception -------------------------------------------------------------

def _counter_rows(g: np.ndarray) -> int:
    """How many rows of the frame are board — the bottom bar is a gauge, never content.

    An edge-pinned line of at most two colours split into a run and a remainder is a progress
    gauge; it marches one cell per action and reading it as board content invents a moving object.
    """
    n = g.shape[0]
    row = [int(v) for v in g[n - 1]]
    if len(set(row)) <= 2:
        head = row[0]
        cut = next((i for i, v in enumerate(row) if v != head), len(row))
        if all(v == row[cut] for v in row[cut:]):
            return n - 1
    return n


def _wall_colour(g: np.ndarray, rows: int, bg: int) -> int | None:
    """The colour that fills a whole outer line of the frame — the out-of-bounds paint."""
    n = g.shape[1]
    lines = [
        [int(v) for v in g[0]],
        [int(g[y][0]) for y in range(rows)],
        [int(g[y][n - 1]) for y in range(rows)],
        [int(v) for v in g[rows - 1]],
    ]
    tally: Counter[int] = Counter()
    for line in lines:
        vals = set(line)
        if len(vals) == 1:
            c = vals.pop()
            if c != bg:
                tally[c] += 1
    if not tally:
        return None
    return tally.most_common(1)[0][0]


def _colour_components(g: np.ndarray, rows: int, palette: set[int]) -> list[tuple[int, list[Cell]]]:
    """The board's objects: 4-connected runs of ONE colour, so two pieces that touch stay two."""
    view = g[:rows]
    out: list[tuple[int, list[Cell]]] = []
    for c in sorted(palette):
        for cells in components(view, palette - {c}):
            out.append((c, cells))
    return out


def _hole(cells: list[Cell], solid: set[Cell] | None = None) -> set[Cell]:
    """The part of a component's bounding box that its own outline seals off from the outside.

    ⛔ `solid` lets other objects help hold the seal, and it is not a nicety. MEASURED: on one board
    a bomb is drawn over three cells of an outline's rim, the ring reads as broken, its interior
    leaks out through the gap and the only goal on the board disappears. A piece standing in a gap
    blocks sight exactly as the rim does.
    """
    own = set(cells) | (solid or set())
    y0 = min(c[0] for c in cells)
    y1 = max(c[0] for c in cells)
    x0 = min(c[1] for c in cells)
    x1 = max(c[1] for c in cells)
    free = {
        (y, x)
        for y in range(y0 - 1, y1 + 2)
        for x in range(x0 - 1, x1 + 2)
        if (y, x) not in own
    }
    outside: set[Cell] = set()
    q = deque(c for c in free if c[0] in (y0 - 1, y1 + 1) or c[1] in (x0 - 1, x1 + 1))
    outside.update(q)
    while q:
        cy, cx = q.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nb = (cy + dy, cx + dx)
            if nb in free and nb not in outside:
                outside.add(nb)
                q.append(nb)
    return free - outside


def _norm(cells: set[Cell]) -> tuple[frozenset[Cell], Cell, int, int]:
    """A shape, lifted off the board: its mask, its corner and its extent."""
    y0 = min(c[0] for c in cells)
    x0 = min(c[1] for c in cells)
    y1 = max(c[0] for c in cells)
    x1 = max(c[1] for c in cells)
    return (
        frozenset((y - y0, x - x0) for y, x in cells),
        (y0, x0),
        y1 - y0 + 1,
        x1 - x0 + 1,
    )


def read_board(g: np.ndarray) -> Board | None:
    """Parse one frame into outlines, pieces and terrain, or give up.

    Purpose: this is the whole detection surface. Returning None here is what keeps the tool from
    bidding on a board it cannot model.

    ⛔ The floor colour is read from what RINGS the outlines, never from "the commonest colour".
    Measured: on the boards where the play area is small the letterbox outweighs the floor, the
    commonest colour comes back as out-of-bounds paint, and then every empty outline interior parses
    as a piece already in place.
    """
    rows = _counter_rows(g)
    width = g.shape[1]
    palette = {int(v) for row in g[:rows] for v in row}
    comps = _colour_components(g, rows, palette)

    outlines: list[tuple[frozenset[Cell], Cell, int, int]] = []
    rings: list[tuple[int, frozenset[Cell]]] = []
    rest: list[tuple[int, list[Cell], set[Cell]]] = []
    fringe: Counter[int] = Counter()
    skin: set[Cell] = set()
    floor = int(next(iter(background(g[:rows]))))
    occupied = {(y, x) for y in range(rows) for x in range(width) if int(g[y][x]) != floor}
    for colour, cells in comps:
        y0 = min(c[0] for c in cells)
        x0 = min(c[1] for c in cells)
        y1 = max(c[0] for c in cells)
        x1 = max(c[1] for c in cells)
        hole = _hole(cells)
        for cand in (hole, _hole(cells, occupied)):
            if len(cand) < 4:
                continue
            hmask, hpos, hh, hw = _norm(cand)
            if hpos == (y0 + 1, x0 + 1) and hh == y1 - y0 - 1 and hw == x1 - x0 - 1:
                outlines.append((hmask, hpos, hh, hw))
                own = set(cells)
                skin.update(own)
                rings.append((colour, frozenset(own)))
                for y in range(y0 - 1, y1 + 2):
                    for x in range(x0 - 1, x1 + 2):
                        edge = y in (y0 - 1, y1 + 1) or x in (x0 - 1, x1 + 1)
                        if edge and 0 <= y < rows and 0 <= x < width and (y, x) not in own:
                            fringe[int(g[y][x])] += 1
                break
        else:
            rest.append((colour, cells, hole))
    if not outlines:
        return None
    bg = fringe.most_common(1)[0][0] if fringe else int(next(iter(background(g[:rows]))))
    wall = _wall_colour(g, rows, bg)

    step = 0
    for _, _, hh, hw in outlines:
        step = gcd(gcd(step, hh), hw)
    if step < 2:
        return None

    bulk = max(max(len(m) for m, _, _, _ in outlines), 4 * step * step)
    shapes = {m for m, _, _, _ in outlines}

    # A colour with ONE component too big to be a piece is terrain wherever it appears. ⛔ Judging
    # each component on its own size instead let the small offcuts of a glide field — the parts a
    # wall happens to cut off — read as bare floor, and a plan that walks across a glide field is
    # a plan of moves the board silently refuses.
    terrain: set[int] = set()
    for colour, cells, hole in rest:
        if colour in (bg, wall) or len(cells) <= bulk:
            continue
        mask, pos, _, _ = _norm(set(cells))
        body = set(mask) | {(y - pos[0], x - pos[1]) for y, x in hole}
        if frozenset(body) not in shapes:
            terrain.add(colour)

    # ⛔ Terrain is painted from the COLOUR, not from the component list. The shared component pass
    # walks a square, and the frame is one column wider than it is tall once the gauge row is cut —
    # so the last column came back unowned and parsed as a 63-cell piece standing off the lattice.
    view = g[:rows]
    walls = view == wall if wall is not None else np.zeros((rows, width), dtype=bool)
    glide = np.isin(view, list(terrain)) if terrain else np.zeros((rows, width), dtype=bool)
    # ⛔ Objects are cut out COLOUR-BLIND. A burning fuse paints part of its own body a second
    # colour, and reading each colour as its own object splits one obstacle into two shapes that
    # match nothing — after which the planner walks a route straight through it.
    loose = np.zeros((rows, width), dtype=bool)
    for y in range(rows):
        for x in range(width):
            c = int(g[y][x])
            if c != bg and not walls[y][x] and not glide[y][x] and (y, x) not in skin:
                loose[y][x] = True

    phase = (outlines[0][1][0] % step, outlines[0][1][1] % step)
    pieces = _objects(g, rows, width, loose, step, phase)
    if not pieces:
        return None

    board = Board()
    board.rows = rows
    board.step = step
    board.phase = phase
    board.floor = bg
    board.walls = walls
    board.glide = glide
    board.rings = rings
    board.pieces = pieces
    board.targets = [hp for _, hp, _, _ in outlines]
    board.shapes = [m for m, _, _, _ in outlines]
    board.held = _held(pieces)
    _tables(board, walls, glide, width)
    return board


def reread(board: Board, g: np.ndarray) -> Board | None:
    """Re-read only what moves, keeping the level's static layer as first seen.

    ⛔ Both halves of this are MEASURED failures, not caution. An outline is scenery drawn UNDER the
    pieces: park a piece on its left rim while an obstacle covers its right and the ring is two
    disconnected arcs — the goal disappears from a board that is one press from being solved. A glide
    field is scenery too, and a piece standing on it hides the field underneath, after which the
    planner walks a route across ground the board refuses.
    """
    rows, width = board.rows, board.walls.shape[1]
    if g.shape[1] != width:
        return None
    skin = {c for colour, cells in board.rings for c in cells if int(g[c[0]][c[1]]) == colour}
    loose = np.zeros((rows, width), dtype=bool)
    for y in range(rows):
        for x in range(width):
            if (int(g[y][x]) != board.floor and not board.walls[y][x]
                    and not board.glide[y][x] and (y, x) not in skin):
                loose[y][x] = True
    pieces = _objects(g, rows, width, loose, board.step, board.phase)
    if not pieces:
        return None
    fresh = Board()
    fresh.rows = rows
    fresh.step = board.step
    fresh.phase = board.phase
    fresh.floor = board.floor
    fresh.walls = board.walls
    fresh.glide = board.glide
    fresh.rings = board.rings
    fresh.pieces = pieces
    fresh.targets = board.targets
    fresh.shapes = board.shapes
    fresh.held = _held(pieces)
    _tables(fresh, board.walls, board.glide, width)
    return fresh


def _aligned(pos: Cell, hh: int, hw: int, step: int, phase: Cell) -> bool:
    """Does this fragment sit on the board's own lattice, as a whole piece must?"""
    return (pos[0] % step == phase[0] and pos[1] % step == phase[1]
            and hh % step == 0 and hw % step == 0)


def _objects(g: np.ndarray, rows: int, width: int, loose: np.ndarray, step: int,
             phase: Cell) -> list[Piece]:
    """Cut the loose paint into the objects that actually move.

    ⛔ Neither colour alone nor connectivity alone gets this right, and both were measured failing on
    the same board. Split by colour and a burning fuse becomes two objects, neither of which sits on
    the lattice. Merge everything that touches and a piece pressed up against an obstacle becomes one
    blob matching no slot — the level's only steerable piece vanishes and the plan dies mid-level.

    The lattice settles it: a whole piece is lattice-aligned, so a fragment that is NOT aligned is
    part of its neighbour, and two aligned neighbours are two objects however hard they touch.
    """
    parts: list[set[Cell]] = []
    seen = np.zeros((rows, width), dtype=bool)
    for y in range(rows):
        for x in range(width):
            if not loose[y][x] or seen[y][x]:
                continue
            c = int(g[y][x])
            stack = [(y, x)]
            seen[y][x] = True
            cells: list[Cell] = []
            while stack:
                cy, cx = stack.pop()
                cells.append((cy, cx))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = cy + dy, cx + dx
                    if (0 <= ny < rows and 0 <= nx < width and loose[ny][nx]
                            and not seen[ny][nx] and int(g[ny][nx]) == c):
                        seen[ny][nx] = True
                        stack.append((ny, nx))
            body = set(cells)
            parts.append(body | _hole(cells))

    for _ in range(len(parts)):
        odd = next(
            (i for i, cs in enumerate(parts) if not _aligned(*_norm(cs)[1:], step, phase)), None
        )
        if odd is None:
            break
        cells = parts[odd]
        touch = {
            (cy + dy, cx + dx) for cy, cx in cells for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1))
        } - cells
        # ⛔ Merge into the SMALLEST neighbour that comes out aligned, not the one it touches most.
        # Measured: a held piece pressed against an obstacle paints the touching edge a third colour,
        # which splits it in two, and both the obstacle and the piece's own other half then share the
        # same length of border. Taking the larger swallowed the piece into the obstacle and the
        # board lost its only steerable object.
        best, rank = None, None
        for j, other in enumerate(parts):
            if j == odd or not (touch & other):
                continue
            union = cells | other
            _, upos, uh, uw = _norm(union)
            key = (0 if _aligned(upos, uh, uw, step, phase) else 1, uh * uw, -len(touch & other))
            if rank is None or key < rank:
                best, rank = j, key
        if best is None:
            return []
        parts[best] = parts[best] | cells
        parts.pop(odd)

    out: list[Piece] = []
    for cells in parts:
        mask, pos, hh, hw = _norm(cells)
        if not _aligned(pos, hh, hw, step, phase):
            return []
        out.append(Piece(mask, pos, _marker(g, pos, mask, hh, hw), hh, hw))
    return out


def _marker(g: np.ndarray, pos: Cell, mask: frozenset[Cell], hh: int, hw: int) -> frozenset[int]:
    """The colour a piece wears at its own MIDDLE, when that is not the colour it is made of.

    A board marks the piece it is holding, and the mark is painted dead centre. ⛔ "A colour that
    never reaches the object's outer skin" looked equivalent and is not: when a held piece is pressed
    against another object the board repaints the touching edge in that very colour, the mark reaches
    the skin, and the only steerable piece on the board stops looking steerable. The middle does not
    move.
    """
    mid = [
        (y, x)
        for y in range((hh - 1) // 2, hh // 2 + 1)
        for x in range((hw - 1) // 2, hw // 2 + 1)
        if (y, x) in mask
    ]
    if not mid:
        return frozenset()
    tally = Counter(int(g[pos[0] + y][pos[1] + x]) for y, x in mask)
    core = {int(g[pos[0] + y][pos[1] + x]) for y, x in mid}
    return frozenset(core) if len(core) == 1 and tally.most_common(1)[0][0] not in core else frozenset()


def _held(pieces: list[Piece]) -> int | None:
    """Which piece the board is currently holding, when the markers say so without ambiguity.

    Purpose: saves the opening click. The held piece wears a marker colour of its own; with only two
    click targets both markers are unique and the question has no answer, so it returns None and the
    plan pays for an explicit click rather than guessing.
    """
    live = [i for i, p in enumerate(pieces) if p.clickable]
    if len(live) == 1:
        # One click target means the board is already holding it — there is nothing else to hold.
        return live[0]
    if len(live) < 3:
        return None
    tally: Counter[frozenset[int]] = Counter(pieces[i].marks for i in live)
    odd = [i for i in live if tally[pieces[i].marks] == 1]
    return odd[0] if len(odd) == 1 else None


def _tables(board: Board, walls: np.ndarray, glide: np.ndarray, width: int) -> None:
    """Precompute, per piece and per lattice square, whether it may stand there.

    Two different answers are needed and conflating them is the bug that eats the level: a held
    piece is refused by the glide field, a launched one rides straight over it.
    """
    rows = board.rows
    s = board.step
    for p in board.pieces:
        py, px = p.pos[0] % s, p.pos[1] % s
        ny = (rows - py + s - 1) // s
        nx = (width - px + s - 1) // s
        walk = np.zeros((ny, nx), dtype=bool)
        slide = np.zeros((ny, nx), dtype=bool)
        onice = np.zeros((ny, nx), dtype=bool)
        for iy in range(ny):
            for ix in range(nx):
                y0, x0 = py + iy * s, px + ix * s
                ok_slide = True
                ok_walk = True
                ice = False
                for dy, dx in p.mask:
                    y, x = y0 + dy, x0 + dx
                    if not (0 <= y < rows and 0 <= x < width) or walls[y][x]:
                        ok_slide = ok_walk = False
                        break
                    if glide[y][x]:
                        ok_walk = False
                        ice = True
                slide[iy][ix] = ok_slide
                walk[iy][ix] = ok_walk and ok_slide
                onice[iy][ix] = ice
        board.walk_ok.append(walk)
        board.slide_ok.append(slide)
        board.on_glide.append(onice)


# --- the model the planner searches ----------------------------------------

class _Model:
    """A faithful replay of the board's own move, launch and settle rules."""

    def __init__(self, board: Board) -> None:
        self.b = board
        self.s = board.step
        self.n = len(board.pieces)
        self.base = [p.pos for p in board.pieces]
        # The lattice a piece lives on is fixed by where it started, so its table is indexed from
        # that phase — not from the piece's own corner, which sits partway along it.
        self.phase = [(p.pos[0] % self.s, p.pos[1] % self.s) for p in board.pieces]
        self.masks = [p.mask for p in board.pieces]
        self.click = [i for i, p in enumerate(board.pieces) if p.clickable]

    def idx(self, i: int, pos: Cell) -> Cell:
        return ((pos[0] - self.phase[i][0]) // self.s, (pos[1] - self.phase[i][1]) // self.s)

    def _tab(self, tab: list[np.ndarray], i: int, pos: Cell) -> bool:
        iy, ix = self.idx(i, pos)
        t = tab[i]
        if not (0 <= iy < t.shape[0] and 0 <= ix < t.shape[1]):
            return False
        return bool(t[iy][ix])

    def walk_ok(self, i: int, pos: Cell) -> bool:
        return self._tab(self.b.walk_ok, i, pos)

    def slide_ok(self, i: int, pos: Cell) -> bool:
        return self._tab(self.b.slide_ok, i, pos)

    def on_glide(self, i: int, pos: Cell) -> bool:
        return self._tab(self.b.on_glide, i, pos)

    def hits(self, i: int, pi: Cell, j: int, pj: Cell) -> bool:
        if abs(pi[0] - pj[0]) >= max(self.b.pieces[i].h, self.b.pieces[j].h):
            return False
        if abs(pi[1] - pj[1]) >= max(self.b.pieces[i].w, self.b.pieces[j].w):
            return False
        a = {(pi[0] + dy, pi[1] + dx) for dy, dx in self.masks[i]}
        return any((pj[0] + dy, pj[1] + dx) in a for dy, dx in self.masks[j])

    def _shove(self, pos: list[Cell], i: int, d: Cell, depth: int = 0) -> bool:
        """Move a piece one cell along the launch, dragging what it meets. True means it jammed."""
        old = pos[i]
        new = (old[0] + d[0] * self.s, old[1] + d[1] * self.s)
        pos[i] = new
        if depth > 8 or not self.slide_ok(i, new):
            pos[i] = old
            return True
        touched = [j for j in range(self.n) if j != i and self.hits(i, new, j, pos[j])]
        for j in touched:
            if self._shove(pos, j, d, depth + 1):
                pos[i] = old
                return True
        return False

    def move(self, pos: tuple[Cell, ...], held: int, d: Cell) -> tuple[Cell, ...] | None:
        """One press. None means the board would not change, so the action is not worth an act."""
        cur = list(pos)
        h = cur[held]
        nxt = (h[0] + d[0] * self.s, h[1] + d[1] * self.s)
        if not self.walk_ok(held, nxt):
            return None
        launched = [j for j in range(self.n) if j != held and self.hits(held, nxt, j, cur[j])]
        if not launched:
            cur[held] = nxt
            return tuple(cur)
        run = 0
        while run <= _MAX_SLIDE:
            settled = True
            for i in launched:
                if run >= _RUN and not self.on_glide(i, cur[i]):
                    continue
                if self._shove(cur, i, d):
                    continue
                settled = False
            if settled:
                break
            run += 1
        return tuple(cur) if tuple(cur) != pos else None


# --- planning ---------------------------------------------------------------

def _relaxed_costs(model: _Model, target: Cell, i: int) -> dict[Cell, int]:
    """Cheapest number of presses to bring piece i to its outline, other pieces wished away.

    Purpose: the search's guide. It undercounts on purpose — it never charges for the piece that
    has to come and do the launching — so it never talks the search out of a real solution.
    """
    b = model.b
    s = model.s
    tab = b.slide_ok[i]
    ny, nx = tab.shape
    py, px = model.base[i][0] % s, model.base[i][1] % s
    back: dict[Cell, list[Cell]] = {}
    nodes: list[Cell] = []
    for iy in range(ny):
        for ix in range(nx):
            if not tab[iy][ix]:
                continue
            here = (py + iy * s, px + ix * s)
            nodes.append(here)
            for d in _DIRS.values():
                step_to = (here[0] + d[0] * s, here[1] + d[1] * s)
                if b.pieces[i].clickable and model.walk_ok(i, here) and model.walk_ok(i, step_to):
                    back.setdefault(step_to, []).append(here)
                land = here
                run = 0
                while run <= _MAX_SLIDE:
                    if run >= _RUN and not model.on_glide(i, land):
                        break
                    nb = (land[0] + d[0] * s, land[1] + d[1] * s)
                    if not model.slide_ok(i, nb):
                        break
                    land = nb
                    run += 1
                if land != here:
                    back.setdefault(land, []).append(here)
    dist = {target: 0}
    q = deque([target])
    while q:
        cur = q.popleft()
        for prev in back.get(cur, ()):
            if prev not in dist:
                dist[prev] = dist[cur] + 1
                q.append(prev)
    return dist


def _fits(board: Board) -> bool:
    """Does every outline have at least one piece cut to its shape?

    Purpose: the model's own admission ticket. An outline with no piece anywhere on the board is a
    goal this tool cannot reach, and bidding on it would spend the game.
    """
    return all(any(p.mask == sh for p in board.pieces) for sh in board.shapes)


def drift(board: Board, tried: set[Cell]) -> tuple[Cell | None, Step | None]:
    """No route to the goal exists — so close on it as far as the board allows, and loiter there.

    Purpose: the only move left when a board's own moving parts are the crossing. A glide field can
    cut the board in two with the goal on the far side and nothing the held piece can push; what
    carries it over is an object acting on its own, and being in the right place when that happens
    is something a plan cannot ask for but a position can. Loitering at the closest reachable square
    costs nothing, because the alternative is no action at all.
    """
    if board.held is None:
        return (None, None)
    model = _Model(board)
    start = tuple(model.base)
    want = [t for k, t in enumerate(board.targets)
            if not any(start[i] == t for i in range(model.n) if board.pieces[i].mask == board.shapes[k])]
    if not want:
        return (None, None)
    seen = {start[board.held]: None}
    order = [start[board.held]]
    first: dict[Cell, Step] = {}
    head = 0
    while head < len(order):
        cur = order[head]
        head += 1
        for aid, d in _DIRS.items():
            pos = list(start)
            pos[board.held] = cur
            nxt = model.move(tuple(pos), board.held, d)
            if nxt is None or nxt[board.held] == cur or nxt[board.held] in seen:
                continue
            seen[nxt[board.held]] = cur
            first[nxt[board.held]] = first.get(cur, (aid, None))
            order.append(nxt[board.held])
    # ⛔ Sweep the near-goal squares, closest first, and do not sit on one. MEASURED: parking on the
    # single closest square pressed the same refused direction for the rest of the budget — the ride
    # across leaves from a square three cells to the side, and standing still never reaches it.
    fresh = [c for c in order if c not in tried] or order
    best = min(fresh, key=lambda c: min(abs(c[0] - t[0]) + abs(c[1] - t[1]) for t in want))
    return (best, first.get(best))


def refused(board: Board) -> Step | None:
    """A press the board will simply refuse — one action spent, nothing on the board moved."""
    if board.held is None:
        return None
    model = _Model(board)
    start = tuple(model.base)
    for aid, d in _DIRS.items():
        if model.move(start, board.held, d) is None:
            return (aid, None)
    return None


def perturb(board: Board, avoid: int) -> Step | None:
    """A press that changes WHEN we arrive rather than where.

    Purpose: breaking a loop the plan cannot see. On a board carrying objects that act on their own
    clock, a route that is right in space can be wrong in time forever — the piece is swept off the
    goal square, walks back in the same number of presses, and is swept again. Spending a press
    somewhere else slips our arrival against that clock, and two arrivals in three then land.

    ⛔ A press the board REFUSES is the cheap version and it is not always available: the loop
    measured here ran down an open corridor where every direction was legal, so the refused-press
    version never fired once in a hundred presses. Any legal press off the plan does the job.
    """
    if board.held is None:
        return None
    model = _Model(board)
    start = tuple(model.base)
    for aid, d in _DIRS.items():
        if model.move(start, board.held, d) is None:
            return (aid, None)
    for aid, d in _DIRS.items():
        if aid != avoid and model.move(start, board.held, d) is not None:
            return (aid, None)
    return None


def volatile(board: Board) -> bool:
    """Is anything on this board outside the model — an object that belongs in no slot?

    Purpose: decides whether a plan can be handed over whole. A board of nothing but pieces and
    their slots is fully modelled, so the search's sequence is the board's own future and issuing it
    in one go is exact. An object with no slot moves for reasons this model does not carry, so the
    plan is re-derived from the frame after every single press instead.
    """
    owned = {
        i for k in range(len(board.shapes))
        for i, p in enumerate(board.pieces) if p.mask == board.shapes[k]
    }
    return len(owned) < len(board.pieces)


def plan(board: Board, cap: int = _NODE_CAP, limit: float = _TIME_CAP) -> list[Step] | None:
    """Search the model for a press sequence that fills every outline.

    ⛔ No piece is assigned to an outline up front. Two boards here carry interchangeable pieces, and
    a board with obstacles carries pieces that belong in no outline at all; fixing the pairing first
    threw away the solution on both.
    """
    if not _fits(board):
        return None
    model = _Model(board)
    slots = list(range(len(board.shapes)))
    # ⛔ A slot is filled by a piece you can take hold of whenever the board offers one. MEASURED on
    # the first board with obstacles: an obstacle happened to share the goal shape and sat one cell
    # from the slot, so the cheapest "solution" was to shove IT in — a state the board does not score
    # as a win, and the plan would have spent the level arriving at it.
    owners: dict[int, list[int]] = {}
    for k in slots:
        same = [i for i, p in enumerate(board.pieces) if p.mask == board.shapes[k]]
        steer = [i for i in same if board.pieces[i].clickable]
        owners[k] = steer or same
    goal = board.targets
    costs = {
        (i, k): _relaxed_costs(model, goal[k], i)
        for k in slots for i in owners[k]
    }
    big = 1 << 20

    def done(pos: tuple[Cell, ...]) -> bool:
        return all(any(pos[i] == goal[k] for i in owners[k]) for k in slots)

    def heur(pos: tuple[Cell, ...]) -> int:
        total = 0
        for k in slots:
            best = min((costs[(i, k)].get(pos[i], big) for i in owners[k]), default=big)
            if best >= big:
                return big
            total += best
        return total

    start = tuple(model.base)
    if done(start):
        return []
    holds = model.click
    if not holds:
        return None
    first = board.held  # None when the markers cannot say, and then every start pays a click
    seen: dict[tuple[tuple[Cell, ...], int], int] = {}
    heap: list[tuple[int, int, tuple[Cell, ...], int, tuple[Step, ...]]] = []
    tick = 0
    for h in holds:
        cost = 0 if h == first else 1
        acts: tuple[Step, ...] = () if h == first else ((6, _click_at_pos(board, h, start)),)
        key = (start, h)
        if seen.get(key, big) <= cost:
            continue
        seen[key] = cost
        tick += 1
        heapq.heappush(heap, (cost + _LEAN * heur(start), tick, start, h, acts))
    popped = 0
    stop = time.monotonic() + limit
    while heap and popped < cap:
        f, _, pos, held, acts = heapq.heappop(heap)
        popped += 1
        if not popped % 4096 and time.monotonic() > stop:
            return None
        g = len(acts)
        if seen.get((pos, held), big) < g:
            continue
        if done(pos):
            return list(acts)
        for aid, d in _DIRS.items():
            nxt = model.move(pos, held, d)
            if nxt is None:
                continue
            ng = g + 1
            if seen.get((nxt, held), big) <= ng:
                continue
            seen[(nxt, held)] = ng
            h2 = heur(nxt)
            if h2 >= big:
                continue
            tick += 1
            heapq.heappush(heap, (ng + _LEAN * h2, tick, nxt, held, acts + ((aid, None),)))
        for j in holds:
            if j == held:
                continue
            ng = g + 1
            if seen.get((pos, j), big) <= ng:
                continue
            seen[(pos, j)] = ng
            h2 = heur(pos)
            if h2 >= big:
                continue
            tick += 1
            heapq.heappush(heap, (ng + _LEAN * h2, tick, pos, j, acts + ((6, _click_at_pos(board, j, pos)),)))
    return None


def _click_at_pos(board: Board, i: int, pos: tuple[Cell, ...]) -> Cell:
    """Where to click to take hold of a piece: the middle of its own body, as (x, y)."""
    p = board.pieces[i]
    y, x = pos[i]
    cy, cx = y + p.h // 2, x + p.w // 2
    if (p.h // 2, p.w // 2) not in p.mask:
        dy, dx = sorted(p.mask)[len(p.mask) // 2]
        cy, cx = y + dy, x + dx
    return (cx, cy)


def current_frame(obs: Any) -> np.ndarray:
    """The board as it stands NOW — the LAST layer, never the first.

    ⛔ MEASURED, and it cost the level after the first: on the turn a level clears, the observation
    carries two layers, layer 0 being the board just finished with every outline already filled.
    Reading layer 0 there says "solved, nothing to do" about a board that has been replaced.
    """
    arr = np.asarray(getattr(obs, "frame", None))
    while arr.ndim > 2:
        arr = arr[-1]
    return arr.astype(np.int64)


class SlotLaunchTool:
    """Read the outlines, model the launch, and hand back the whole sequence."""

    name = "slotlaunch"

    def __init__(self) -> None:
        self._level = -1
        self._plan: list[Step] | None = None
        self._issued = False
        self._took: Cell | None = None
        self._static: Board | None = None
        self._seen: Counter[tuple[Cell, ...]] = Counter()
        self._roamed: set[Cell] = set()
        self._wait = 0
        self._wandered = 0

    def _loiter(self, board: Board) -> list[Step]:
        """Stand where the crossing leaves from, and HOLD there long enough to catch it.

        ⛔ Both halves are measured. Parking on one square and pressing into the wall forever missed
        the ride by three cells; roaming instead of standing crossed the right square twice and was
        moving on again before the thing that carries you fired. So: take the closest square that can
        be HELD — one with a refused press available — hold it for a spell, then strike it off and
        take the next. The board's own clock is unknown, so the spell is a small fixed count.
        """
        if self._wandered >= _ROAM_CAP:
            return []
        self._wandered += 1
        spot, step = drift(board, self._roamed)
        if spot is None:
            return []
        if step is None:
            hold = refused(board)
            if hold is not None and self._wait < _HOLD:
                self._wait += 1
                return [hold]
            self._roamed.add(spot)
            self._wait = 0
            spot, step = drift(board, self._roamed)
        return [step] if step is not None else []

    def detect(self, frames: list[Any], obs: Any) -> float:
        """Confidence, which is zero unless the board really parses into outlines and their pieces."""
        if not has_frame(obs):
            return 0.0
        simple, click = availability(obs)
        if not click or len(simple) < 4:
            return 0.0
        board = read_board(current_frame(obs))
        if board is None or not _fits(board):
            return 0.0
        if not any(p.clickable for p in board.pieces):
            return 0.0
        return 0.9

    def reset(self) -> None:
        self._plan = None
        self._issued = False
        self._took = None
        self._static = None
        self._seen = Counter()
        self._roamed = set()
        self._wait = 0
        self._wandered = 0

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        return None

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        if not has_frame(obs):
            return []
        lvl = levels_completed(obs)
        if lvl != self._level:
            self._level = lvl
            self.reset()
        if self._issued:
            return []
        g = current_frame(obs)
        if self._static is None:
            self._static = read_board(g)
            board = self._static
        else:
            board = reread(self._static, g)
        if board is None:
            return []
        if self._took is not None:
            # ⛔ Remember what the last click took hold of. Taking hold of the ONLY piece on the board
            # changes not one pixel, so a plan re-derived after it opens with the same click again,
            # and the level is spent clicking. Measured: 100 presses, board untouched.
            x, y = self._took
            for i, p in enumerate(board.pieces):
                if (y - p.pos[0], x - p.pos[1]) in p.mask:
                    board.held = i
                    break
        steps = plan(board)
        if steps is None and volatile(board):
            steps = self._loiter(board)
        if not steps:
            return []
        if volatile(board):
            # Hand over ONE press and look again. The board still moves on its own here.
            here = tuple(p.pos for p in board.pieces)
            n = self._seen[here]
            self._seen[here] = n + 1
            if n % 2:
                # ⛔ Seen this exact board before, so the plan that leaves it leads back to it.
                # MEASURED: an obstacle that fires every third press sweeps the held piece off the
                # goal square, the piece walks back in the same number of presses, and it is swept
                # again — for the whole budget. One refused press slips the phase and it lands.
                nudge = perturb(board, steps[0][0])
                if nudge is not None:
                    return [nudge]
            if steps[0][0] == 6 and steps[0][1] is not None:
                self._took = steps[0][1]
            return steps[:1]
        for aid, xy in steps:
            if aid == 6 and xy is not None:
                self._took = xy
        # Only a plan that was actually handed over counts as issued. An empty one means the board
        # read as already solved, which on the turn a level clears means the frame has not caught up.
        self._issued = True
        return steps
