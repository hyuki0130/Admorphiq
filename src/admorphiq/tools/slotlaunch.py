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

__all__ = ["SlotLaunchTool", "read_board", "Board", "Piece"]

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

    __slots__ = ("step", "pieces", "targets", "shapes", "walk_ok", "slide_ok", "on_glide", "rows", "held")

    def __init__(self) -> None:
        self.step = 0
        self.pieces: list[Piece] = []
        self.targets: list[Cell] = []
        self.shapes: list[frozenset[Cell]] = []
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


def _hole(cells: list[Cell]) -> set[Cell]:
    """The part of a component's bounding box that its own outline seals off from the outside."""
    own = set(cells)
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
    rest: list[tuple[int, list[Cell], set[Cell]]] = []
    fringe: Counter[int] = Counter()
    for colour, cells in comps:
        hole = _hole(cells)
        y0 = min(c[0] for c in cells)
        x0 = min(c[1] for c in cells)
        y1 = max(c[0] for c in cells)
        x1 = max(c[1] for c in cells)
        if len(hole) >= 4:
            hmask, hpos, hh, hw = _norm(hole)
            if hpos == (y0 + 1, x0 + 1) and hh == y1 - y0 - 1 and hw == x1 - x0 - 1:
                outlines.append((hmask, hpos, hh, hw))
                own = set(cells)
                for y in range(y0 - 1, y1 + 2):
                    for x in range(x0 - 1, x1 + 2):
                        edge = y in (y0 - 1, y1 + 1) or x in (x0 - 1, x1 + 1)
                        if edge and 0 <= y < rows and 0 <= x < width and (y, x) not in own:
                            fringe[int(g[y][x])] += 1
                continue
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

    walls = np.zeros((rows, width), dtype=bool)
    glide = np.zeros((rows, width), dtype=bool)
    pieces: list[Piece] = []
    filled: set[Cell] = set()
    for _, hp, hh, hw in outlines:
        filled.update((hp[0] + y, hp[1] + x) for y in range(hh) for x in range(hw))
    loose: list[list[Cell]] = []
    for colour, cells, hole in rest:
        if colour == bg:
            continue
        if colour == wall:
            for y, x in cells:
                walls[y][x] = True
            continue
        if colour in terrain:
            for y, x in cells:
                glide[y][x] = True
            continue
        mask, pos, hh, hw = _norm(set(cells))
        solid = frozenset(set(mask) | {(y - pos[0], x - pos[1]) for y, x in hole})
        if solid in shapes:
            pieces.append(Piece(solid, pos, frozenset(int(g[y][x]) for y, x in hole), hh, hw))
            filled.update(hole)
            continue
        loose.append(cells)
    if not pieces:
        return None
    # ⛔ Refuse the board rather than pretend. Anything left over that is not a marker sitting inside
    # a piece or an outline is an object this model has no rule for — on the boards where one shows
    # up it moves on its own, and planning around it as bare floor spends the whole budget on a
    # sequence the board stopped obeying at the first press.
    if any(not set(cells) <= filled for cells in loose):
        return None

    board = Board()
    board.rows = rows
    board.step = step
    board.pieces = pieces
    board.targets = [hp for _, hp, _, _ in outlines]
    board.shapes = [m for m, _, _, _ in outlines]
    board.held = _held(pieces)
    _tables(board, walls, glide, width)
    return board


def _held(pieces: list[Piece]) -> int | None:
    """Which piece the board is currently holding, when the markers say so without ambiguity.

    Purpose: saves the opening click. The held piece wears a marker colour of its own; with only two
    click targets both markers are unique and the question has no answer, so it returns None and the
    plan pays for an explicit click rather than guessing.
    """
    live = [i for i, p in enumerate(pieces) if p.clickable]
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


def _assign(board: Board) -> list[int] | None:
    """Which outline each piece is cut for. None when the board is not this family after all."""
    shapes = board.shapes
    used = [False] * len(shapes)
    out: list[int] = []
    for p in board.pieces:
        pick = next((k for k, sh in enumerate(shapes) if not used[k] and sh == p.mask), None)
        if pick is None:
            return None
        used[pick] = True
        out.append(pick)
    if not all(used):
        return None
    return out


def plan(board: Board, cap: int = _NODE_CAP) -> list[Step] | None:
    """Search the model for a press sequence that fills every outline."""
    order = _assign(board)
    if order is None:
        return None
    model = _Model(board)
    goal = [board.targets[k] for k in order]
    costs = [_relaxed_costs(model, goal[i], i) for i in range(model.n)]
    big = 1 << 20

    def heur(pos: tuple[Cell, ...]) -> int:
        total = 0
        for i, p in enumerate(pos):
            if p == goal[i]:
                continue
            d = costs[i].get(p)
            if d is None:
                return big
            total += d
        return total

    start = tuple(model.base)
    if all(start[i] == goal[i] for i in range(model.n)):
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
    stop = time.monotonic() + _TIME_CAP
    while heap and popped < cap:
        f, _, pos, held, acts = heapq.heappop(heap)
        popped += 1
        if not popped % 4096 and time.monotonic() > stop:
            return None
        g = len(acts)
        if seen.get((pos, held), big) < g:
            continue
        if all(pos[i] == goal[i] for i in range(model.n)):
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

    def detect(self, frames: list[Any], obs: Any) -> float:
        """Confidence, which is zero unless the board really parses into outlines and their pieces."""
        if not has_frame(obs):
            return 0.0
        simple, click = availability(obs)
        if not click or len(simple) < 4:
            return 0.0
        board = read_board(current_frame(obs))
        if board is None or _assign(board) is None:
            return 0.0
        if not any(p.clickable for p in board.pieces):
            return 0.0
        return 0.9

    def reset(self) -> None:
        self._plan = None
        self._issued = False

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
        board = read_board(current_frame(obs))
        if board is None:
            return []
        steps = plan(board)
        # Only a plan that was actually handed over counts as issued. An empty one means the board
        # read as already solved, which on the turn a level clears means the frame has not caught up.
        if steps:
            self._issued = True
        return steps or []
