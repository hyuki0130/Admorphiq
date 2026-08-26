"""Haul tool — take hold of a cargo piece, drag it into its bay, and let go.

The mechanic, recovered from the frames: one carrier under the four move keys walks a lattice; a
fifth key LATCHES whatever sits in the cell the carrier faces and LETS GO of it again. A latched
piece keeps its offset from the carrier, so it is towed rather than pushed, and it may be towed in
any direction including backwards. The level clears when every cargo piece is standing inside the
bay — a framed rectangle drawn under everything — and nothing is holding it.

⛔ Why plan rather than search. Measured on the board this was built for: the searching generic path
opens 209 states in 1500 actions and clears NOTHING, because the win condition is a JOINT property
of several pieces and the carrier can only affect one of them at a time. Reading the mechanic and
planning the haul clears the first level well inside the human action count.

⛔ Why a plan, not exploration, is compulsory here. This board DECLARES a per-level action budget
and ENDS the game when it is exceeded — the bar pinned to the frame's edge is that budget draining.
Wandering does not merely score badly, it loses the run.

⛔ Frame-only. The lattice step, the carrier, which direction it faces, what counts as cargo, what
counts as a bay and what blocks a move are all DERIVED from one frame:

  * a cargo piece is a square of one colour ringed by another — and the RING RECOLOURS to say who
    is holding it, which is why the piece is keyed on its CORE and never on its ring;
  * the carrier is a square that is flat except for one edge line, and THAT LINE IS THE FACING —
    it moves to whichever side was last pressed, so the frame states the facing outright;
  * a bay is a filled rectangle whose 1-pixel frame is a different colour from its fill. A solid
    block is not one. A rectangle SMALL enough to be a piece counts only when a rectangle too big
    to be a piece shares its exact frame-and-fill colours, because the small ones are otherwise
    indistinguishable from another actor being looked at — and dropping them outright leaves a
    board with fewer bays than pieces, which this tool then refuses.

⛔ A bay is remembered, never re-derived alone. Cargo is drawn OVER the bay, so the moment a piece
is delivered the bay stops looking like a filled rectangle. Bays therefore accumulate across the
level and are only ever added to; so does the furniture, for the same reason.

⛔ A move the board refuses is learned. Furniture a piece is standing on is invisible from the
level's first frame onward, so the only evidence it exists is the press that bounced — the tool
records the refusal and stops offering that move.

⚠️ Chrome is masked at ONE pixel, not at `segment.edge_band`'s sixteenth of the frame: this board
puts real furniture in the outermost cells, and a generous margin walls the carrier out of them.

⛔ Not everything on the board is furniture — some of it WALKS, and the two must not be
remembered alike. A cell that reads bare is a cell nothing was ever built on, which is how a
mover's trail is unlearned while a barrier hidden under a piece is kept. Some of those movers are
carrying pieces to the bays and are doing the work FOR the carrier; others carry them to a second
destination, painted in the bays' own fill colour but unframed, and undo it. Facing one settles
which: the kind that can be removed is redrawn with a ring the moment it is looked at, and the
latch — aimed at an actor rather than at a piece — removes it.

⛔ A bay holds ONE piece, so each loose piece is promised one, nearest pairing first. Sending every
piece to the bay nearest IT sends them all to the same side of the board.

⛔ Some furniture stops the carrier but not the cargo. It is drawn with holes in it — background
showing through pixels that are enclosed by the furniture's own colour — and a towed piece passes
straight through it while the carrier cannot follow. That is what makes a hand-off possible on
boards where the bay sits on the far side of a barrier, so the porous test is a capability, not a
detail: when no bay can be reached, the tool parks each piece as close to the bay as it can and
waits, which is the only move available when the carrier is walled off from the destination.
"""

from __future__ import annotations

from collections import Counter, deque
from typing import Any

import numpy as np

from admorphiq.tools.base import Step, availability, frame_2d, has_frame, levels_completed
from admorphiq.tools.segment import background

__all__ = ["HaulDeliveryTool"]

Cell = tuple[int, int]

# action id -> step on the lattice, in (row, col)
_DELTA: dict[int, Cell] = {1: (-1, 0), 2: (1, 0), 3: (0, -1), 4: (0, 1)}
_MOVES = tuple(_DELTA)
_LATCH = 5
_SIDES = range(3, 9)
_MAX_GLYPHS = 240
_MAX_WAIT = 80
_MAX_CHASE = 40


# --- glyph readers ----------------------------------------------------------

def _ring_core(g: np.ndarray, side: int) -> dict[Cell, tuple[int, int]]:
    """Every `side`x`side` window that is a flat core inside a flat ring of another colour."""
    h, w = g.shape
    if side < 3 or h < side or w < side:
        return {}
    win = np.lib.stride_tricks.sliding_window_view(g, (side, side))
    mask = np.zeros((side, side), dtype=bool)
    mask[0, :] = mask[-1, :] = True
    mask[:, 0] = mask[:, -1] = True
    ring = win[:, :, mask]
    core = win[:, :, ~mask]
    ok = (
        (ring == ring[:, :, :1]).all(-1)
        & (core == core[:, :, :1]).all(-1)
        & (ring[:, :, 0] != core[:, :, 0])
    )
    ys, xs = np.nonzero(ok)
    if len(ys) > _MAX_GLYPHS:
        return {}
    return {(int(y), int(x)): (int(ring[y, x, 0]), int(core[y, x, 0])) for y, x in zip(ys, xs)}


def _thin_out(found: dict[Cell, tuple[int, int]], side: int) -> dict[Cell, tuple[int, int]]:
    """One glyph per cluster — a sliding scan reports the same piece at neighbouring offsets."""
    kept: dict[Cell, tuple[int, int]] = {}
    for origin in sorted(found):
        if any(abs(origin[0] - k[0]) < side and abs(origin[1] - k[1]) < side for k in kept):
            continue
        kept[origin] = found[origin]
    return kept


def _facing_of(tile: np.ndarray) -> tuple[int, int] | None:
    """(action id this glyph points at, its body colour): one edge line over a flat body."""
    edges = {1: tile[0, :], 2: tile[-1, :], 3: tile[:, 0], 4: tile[:, -1]}
    bodies = {1: tile[1:, :], 2: tile[:-1, :], 3: tile[:, 1:], 4: tile[:, :-1]}
    for act, line in edges.items():
        line_v = set(line.tolist())
        body_v = set(bodies[act].ravel().tolist())
        if len(line_v) == 1 and len(body_v) == 1 and line_v != body_v:
            return act, body_v.pop()
    return None


def _regions(mask: np.ndarray) -> list[list[Cell]]:
    """4-connected regions of a boolean pixel mask."""
    h, w = mask.shape
    seen = np.zeros_like(mask)
    out: list[list[Cell]] = []
    for y in range(h):
        for x in range(w):
            if not mask[y, x] or seen[y, x]:
                continue
            seen[y, x] = True
            stack = [(y, x)]
            cells: list[Cell] = []
            while stack:
                cy, cx = stack.pop()
                cells.append((cy, cx))
                for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            out.append(cells)
    return out


def _framed_rect(g: np.ndarray, cells: list[Cell]) -> tuple[tuple[int, int, int, int], int, int] | None:
    """(box, frame colour, fill colour) if the region is a filled rectangle framed in a second
    colour, else None."""
    ys = [c[0] for c in cells]
    xs = [c[1] for c in cells]
    y0, y1, x0, x1 = min(ys), max(ys), min(xs), max(xs)
    h, w = y1 - y0 + 1, x1 - x0 + 1
    if h < 3 or w < 3 or len(cells) != h * w:
        return None
    block = g[y0:y1 + 1, x0:x1 + 1]
    mask = np.zeros((h, w), dtype=bool)
    mask[0, :] = mask[-1, :] = True
    mask[:, 0] = mask[:, -1] = True
    frame_v = set(block[mask].tolist())
    fill_v = set(block[~mask].tolist())
    if len(frame_v) != 1 or len(fill_v) != 1 or frame_v == fill_v:
        return None
    return (y0, x0, y1, x1), frame_v.pop(), fill_v.pop()


def _has_enclosed_gap(mask: np.ndarray, cells: list[Cell]) -> bool:
    """Does this region hold a pocket of background its own colour closes off?"""
    ys = [c[0] for c in cells]
    xs = [c[1] for c in cells]
    y0, y1, x0, x1 = min(ys), max(ys), min(xs), max(xs)
    sub = mask[y0:y1 + 1, x0:x1 + 1]
    gap = ~sub
    if not gap.any():
        return False
    h, w = gap.shape
    seen = np.zeros_like(gap)
    stack = [(y, x) for y in range(h) for x in range(w)
             if gap[y, x] and (y in (0, h - 1) or x in (0, w - 1))]
    for s in stack:
        seen[s] = True
    while stack:
        cy, cx = stack.pop()
        for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
            if 0 <= ny < h and 0 <= nx < w and gap[ny, nx] and not seen[ny, nx]:
                seen[ny, nx] = True
                stack.append((ny, nx))
    return bool((gap & ~seen).any())


def _ground(tiles: dict[Cell, np.ndarray], standing: set[Cell]) -> Counter[int]:
    """The floor colour: what surrounds the things that stand on the board.

    ⚠️ One frame is not enough and the votes are kept: measured, a carrier standing in a one-cell
    gap through a wall has nothing but WALL beside it, and that single frame read the wall as the
    floor and every open cell on the board as an obstacle.

    ⛔ NOT the commonest colour in the frame. Measured: one board draws a wall across the whole
    top of the frame and another across the whole bottom, and between them they outnumber the
    floor — so the commonest colour is a WALL, every empty cell then reads as an obstacle, and the
    tool cannot find a single move. The pieces and the carrier are the one thing known to be
    standing ON the floor, so the floor is what is next to them.
    """
    seen: Counter[int] = Counter()
    for cell in standing:
        for d in _DELTA.values():
            tile = tiles.get((cell[0] + d[0], cell[1] + d[1]))
            if tile is None:
                continue
            shades = set(tile.ravel().tolist())
            if len(shades) == 1:
                seen[int(next(iter(shades)))] += 1
    return seen


def _span(a: Cell, b: Cell) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


class _Board:
    """One frame, read as a lattice of pieces."""

    __slots__ = ("side", "origin", "rows", "cols", "carrier", "facing",
                 "cargo", "blocked", "porous", "bays", "movers", "marked", "hostile")

    def __init__(self) -> None:
        self.side = 0
        self.origin: Cell = (0, 0)
        self.rows = self.cols = 0
        self.carrier: Cell | None = None
        self.facing: int | None = None
        self.cargo: set[Cell] = set()
        self.blocked: set[Cell] = set()
        self.porous: set[Cell] = set()
        self.bays: set[Cell] = set()
        self.movers: dict[Cell, int] = {}
        self.marked: set[Cell] = set()
        self.hostile = False

    def inside(self, c: Cell) -> bool:
        return 0 <= c[0] < self.rows and 0 <= c[1] < self.cols


class HaulDeliveryTool:
    """Read the board, choose the cheapest haul, take one step of it, look again."""

    name = "haul"

    def __init__(self) -> None:
        self._level: int | None = None
        self._side = 0
        self._body: int | None = None
        self._origin: Cell = (0, 0)
        self._bays: set[Cell] = set()
        self._pairs: set[tuple[int, int]] = set()
        self._walls: set[Cell] = set()
        self._screens: set[Cell] = set()
        self._seen: dict[Cell, int] = {}
        self._key = b""
        self._zone: set[Cell] = set()
        self._votes: Counter[int] = Counter()
        self._aim: Cell | None = None
        self._roam: set[int] = set()
        self._friendly: set[int] = set()
        self._chase = 0
        self._refused: Counter[tuple[Cell, Cell | None, int]] = Counter()
        self._pending: tuple[Cell, Cell | None, int] | None = None
        self._offset: Cell | None = None          # cargo's offset while latched
        self._parked: set[Cell] = set()
        self._dropped: Counter[Cell] = Counter()
        self._waits = 0
        self._nudges = 0
        self._blinks = 0
        self._last_cargo: frozenset[Cell] = frozenset()

    # -- Tool protocol -------------------------------------------------------

    def reset(self) -> None:
        """A new level redraws the bay and every piece, so nothing learned carries over."""
        # ⛔ The carrier's colour and the lattice belong to the GAME, not to the level, and the
        # first frame of a new level is often the old board still drawn — re-deriving them there
        # is re-deriving them from a picture of a finished board.
        self._origin = (0, 0)
        self._bays = set()
        self._walls = set()
        self._screens = set()
        # ⛔ Which cells held something is a fact about THIS board; carrying it into the next
        # level makes every wall of the old board look like something that walked away.
        self._seen = {}
        self._key = b""
        self._zone = set()
        self._chase = 0
        self._aim = None
        self._refused = Counter()
        self._pending = None
        self._offset = None
        self._parked = set()
        self._dropped = Counter()
        self._waits = 0
        self._nudges = 0
        self._blinks = 0
        self._last_cargo = frozenset()

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """Nothing to accumulate: the plan is rebuilt from the board every turn."""

    def detect(self, frames: list[Any], obs: Any) -> float:
        if not has_frame(obs):
            return 0.0
        simple, action6 = availability(obs)
        # A towing mechanic is driven by the move keys plus one latch key. A pointing device
        # means a different game, so this tool has nothing to offer there.
        if action6 or not {1, 2, 3, 4, _LATCH} <= set(simple):
            return 0.0
        board = self._read(frame_2d(obs))
        if board is None:
            return 0.0
        # ⛔ Bid only on a real plan, and never on the shapes alone. Every piece has to end up in
        # a bay, so a board with fewer bays than pieces is not this mechanic however much it
        # looks like it — measured, that single test is what stops this tool taking a turn on a
        # board whose one framed glyph is not cargo at all.
        if not board.cargo or len(board.bays) < len(board.cargo):
            return 0.0
        walk = self._walk(board, board.carrier)
        loose = [c for c in board.cargo if c not in board.bays]
        if not loose:
            return 0.0
        grip = any((c[0] - d[0], c[1] - d[1]) in walk for c in loose for d in _DELTA.values())
        return 0.75 if grip else 0.0

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        if not has_frame(obs):
            return []
        level = levels_completed(obs)
        if level != self._level:
            stepped = self._level is not None
            self._level = level
            self.reset()
            # ⛔ The frame that REPORTS a level cleared still draws the level just finished, so
            # reading it learns the OLD board's furniture and its uncovered bays into the new
            # level. Measured: a barrier from the previous level ran down the middle of the next
            # one, sealing the carrier into a three-cell corridor for the rest of the game. One
            # key press buys the real frame, and one press per level is nothing against a budget
            # this tool finishes a level well inside.
            if stepped:
                return [(_MOVES[0], None)]
        board = self._read(frame_2d(obs))
        if board is None:
            return self._blind()
        self._blinks = 0
        self._judge(board)
        held = self._offset
        action = self._decide(board)
        if action is None:
            return []
        if action == _LATCH:
            self._offset = None if self._offset else self._grip(board)
        elif self._expected(board, held, action):
            self._pending = (board.carrier, held, action)
        return [(action, None)]

    def _expected(self, board: _Board, held: Cell | None, action: int) -> bool:
        """Was that key press supposed to walk the carrier, by this tool's own reading?"""
        d = _DELTA[action]
        nxt = (board.carrier[0] + d[0], board.carrier[1] + d[1])
        if not board.inside(nxt):
            return False
        if nxt not in board.blocked:
            return True
        return held is not None and nxt == (board.carrier[0] + held[0], board.carrier[1] + held[1])

    def _judge(self, board: _Board) -> None:
        """A move the board refused is a fact about the board; do not offer it twice more.

        ⛔ This is the only defence against furniture that a piece is STANDING ON and therefore
        hiding: the barrier is invisible from the first frame of the level onward, so it can be
        learned only from the move that bounced. Measured — without it the carrier pressed the
        same refused key for the remaining eighty actions of a level.

        ⚠️ Twice, not once. Some boards swallow a key while something is animating, and one
        bounce is not evidence.
        """
        if self._pending is None:
            return
        frm, off, act = self._pending
        self._pending = None
        if board.carrier != frm:
            return
        self._refused[(frm, off, act)] += 1

    def _blind(self) -> list[Step]:
        """A frame this tool cannot read: step a few times to get another, then stand down.

        The frame that announces a level cleared still draws the finished board, and a finished
        board can be unreadable — every bay covered by the pieces standing in it. Giving up there
        would cost the whole rest of the game for want of one key press.
        """
        self._blinks += 1
        return [] if self._blinks > 3 else [(_MOVES[0], None)]

    # -- reading -------------------------------------------------------------

    def _lattice(self, g: np.ndarray) -> tuple[int, Cell] | None:
        """The piece size and where the lattice starts, taken from the cargo pieces themselves."""
        if self._side:
            return self._side, self._origin
        best: tuple[int, int, Cell] | None = None
        for side in _SIDES:
            glyphs = _thin_out(_ring_core(g, side), side)
            if not glyphs:
                continue
            cores = Counter(c for _, c in glyphs.values())
            core = cores.most_common(1)[0][0]
            origins = [o for o, (_, c) in glyphs.items() if c == core]
            offs = {(o[0] % side, o[1] % side) for o in origins}
            if len(offs) != 1:
                continue
            if best is None or len(origins) > best[0]:
                best = (len(origins), side, offs.pop())
        if best is None:
            return None
        self._side, self._origin = best[1], best[2]
        return self._side, self._origin

    def _read(self, g: np.ndarray) -> _Board | None:
        lat = self._lattice(g)
        if lat is None:
            return None
        side, (oy, ox) = lat
        h, w = g.shape
        # ⛔ The budget bar is pinned to the frame's edge and marches one pixel per action. It is
        # chrome, not board, and reading it as content walls off the outermost row of cells. Paint
        # it out with the FLOOR — known from every frame read so far, since the floor colour is a
        # fact about the game and not about the frame.
        # ⚠️ Painted, not smeared with the line behind it. Measured: smearing made an outermost
        # tile UNIFORM, and a uniform tile cannot show which way the carrier is facing — so the
        # moment the carrier stepped into the top row the whole board became unreadable and the
        # tool gave the rest of the game up.
        gm = g.copy()
        gm[0, :] = gm[-1, :] = gm[:, 0] = gm[:, -1] = (
            self._votes.most_common(1)[0][0] if self._votes else next(iter(background(g)))
        )

        board = _Board()
        board.side = side
        board.origin = (oy, ox)
        board.rows = (h - oy) // side
        board.cols = (w - ox) // side
        tiles: dict[Cell, np.ndarray] = {}
        for r in range(board.rows):
            for c in range(board.cols):
                tiles[(r, c)] = gm[oy + r * side:oy + (r + 1) * side,
                                   ox + c * side:ox + (c + 1) * side]

        glyphs = {cell: _ring_core(t, side).get((0, 0)) for cell, t in tiles.items()}
        cores = Counter(v[1] for v in glyphs.values() if v)
        if not cores:
            return None
        cargo_core = cores.most_common(1)[0][0]
        board.cargo = {cell for cell, v in glyphs.items() if v and v[1] == cargo_core}

        # ⛔ A framed rectangle's edge cells LOOK like a glyph with one marked side — a line of
        # frame colour over flat fill is exactly the carrier's shape. What separates them is that
        # the carrier's body colour belongs to nothing else on the board, so it cannot cover more
        # than one piece's worth of the frame. Without this the bay reads as several carriers and
        # the board is refused outright.
        # ⛔ Once the carrier's colour is known, KEEP it. Measured: the rarity test is only
        # decisive while the bay is still fully drawn — as pieces cover it the fill dwindles to
        # less than one piece's worth of pixels and the bay's own edge starts qualifying, at
        # which point the board is refused mid-level and the rest of the run is lost.
        floor = int(gm.min())
        tally = np.bincount(gm.ravel().astype(np.int64) - floor)
        carriers = []
        for cell, tile in tiles.items():
            if glyphs[cell] is not None:
                continue
            mark = _facing_of(tile)
            if mark is None:
                continue
            if self._body is None:
                if tally[mark[1] - floor] > side * side:
                    continue
            elif mark[1] != self._body:
                continue
            carriers.append((cell, mark))
        if len(carriers) != 1:
            return None
        board.carrier, (board.facing, body) = carriers[0]
        self._body = body
        self._votes += _ground(tiles, board.cargo | {board.carrier})
        bg = self._votes.most_common(1)[0][0] if self._votes else next(iter(background(gm)))

        # Terrain is everything that is not a piece. Pieces are drawn OVER the bay, so a bay is
        # only ever recognised while nothing stands on it — hence the running union.
        # ⛔ "Furniture with background showing through" must be asked of the BARE frame, not of
        # one with the pieces cut out of it. Measured: a piece standing in a corner of a painted
        # region left a hole that the region's own colour closed off, and a solid wall thirty
        # cells long was declared porous — after which every plan towed pieces straight through it
        # and every one of those moves was refused.
        bare = gm != bg
        terrain = bare.copy()
        for cell in board.cargo | {board.carrier}:
            r, c = cell
            terrain[oy + r * side:oy + (r + 1) * side, ox + c * side:ox + (c + 1) * side] = False
        # ⛔ A one-cell framed rectangle is ambiguous: another actor on these boards is drawn
        # exactly that way while the carrier is looking at it. What settles it is that every bay
        # on a board is framed and filled in the SAME pair of colours, so a small rectangle is a
        # bay only when a rectangle too big to be an actor shares its colours. Without the small
        # ones a board's bay count comes up short of its piece count and the level is refused;
        # without the colour rule an actor becomes a destination.
        rects = []
        screens = np.zeros_like(terrain)
        fills = {f for _, f in self._pairs}
        for cells in _regions(terrain):
            found = _framed_rect(gm, cells)
            if found is not None:
                rects.append(found)
                continue
            if _has_enclosed_gap(bare, cells):
                for y, x in cells:
                    screens[y, x] = True
                continue
        for (y0, x0, y1, x1), edge, fill in rects:
            if (y1 - y0 + 1) * (x1 - x0 + 1) > side * side:
                self._pairs.add((edge, fill))
        boxes = [box for box, edge, fill in rects if (edge, fill) in self._pairs]
        for y0, x0, y1, x1 in boxes:
            for r in range(board.rows):
                for c in range(board.cols):
                    py, px = oy + r * side, ox + c * side
                    if y0 <= py <= y1 and x0 <= px <= x1:
                        self._bays.add((r, c))
        # ⛔ A bay is recognised only once nothing is standing on it, so on a board where a piece
        # starts ON the bay the cells around it are read as furniture for as long as that takes —
        # and furniture is remembered. Measured: the tool towed a piece to the very edge of the
        # bay and let go, because the bay itself was in its wall list. Learning a bay therefore
        # UNLEARNS the wall.
        self._walls -= self._bays
        self._screens -= self._bays
        board.bays = set(self._bays)

        # ⛔ Judge a cell against the REMEMBERED bay, never against this frame's rectangle.
        # Measured: one delivered piece splits the bay's drawing in two, each half then reads as
        # furniture, and the carrier is walled into the corner it just delivered from.
        # ⛔ Reading the same frame twice must not count as time passing. The harness asks a tool
        # for its confidence as well as for its move, and both questions read the board — so what
        # walked would appear to have stood still, and nothing would ever be learned to walk.
        fresh = self._key != gm.tobytes()
        prev = dict(self._seen)
        seen_now: dict[Cell, int] = {}
        flats: dict[Cell, int] = {}
        for cell, tile in tiles.items():
            if cell == board.carrier:
                continue
            # A delivered piece is still a piece: it blocks. Measured — exempting the bay from
            # the blocking test first exempted the piece standing IN it, and every route then
            # planned straight through a box the carrier cannot pass.
            if cell in board.cargo:
                board.blocked.add(cell)
                continue
            if cell in board.bays:
                continue
            r, c = cell
            sl = (slice(oy + r * side, oy + (r + 1) * side), slice(ox + c * side, ox + (c + 1) * side))
            solid = tile != bg
            if solid.any():
                shades = set(tile.ravel().tolist())
                flat = int(next(iter(shades))) if len(shades) == 1 else -1
                seen_now[cell] = flat
                flats[cell] = flat
                # ⛔ A second destination, painted in the bays' own FILL colour but with no frame
                # round it and standing where no bay stands, is where something on this board
                # takes the cargo that is NOT the bay — and it is the only warning, available
                # from the board's first frame, that one of the things that walks here is undoing
                # the work rather than doing it. Read it CELL BY CELL: measured, the one on this
                # board is drawn flush against a wall, and asked as a question about connected
                # regions it comes back as part of the wall and says nothing.
                # ⛔ It is FLOOR, exactly as a bay is floor — it is paint under everything, not a
                # thing standing on the board. Measured: read as furniture it walled the carrier
                # out of the corner holding the last piece, and the level could not be finished.
                if flat in fills or cell in self._zone:
                    self._zone.add(cell)
                    self._walls.discard(cell)
                    self._screens.discard(cell)
                    continue
                self._walls.add(cell)
                if screens[sl][solid].all():
                    self._screens.add(cell)
            else:
                # A cell that was covered and is now bare says what covered it WALKS. That is the
                # whole test: real furniture is drawn in every frame, so its colour never appears
                # here, and a colour that does is one this board moves around by itself.
                gone = prev.get(cell)
                if fresh and gone is not None and gone >= 0:
                    self._roam.add(gone)
                # ⛔ Remembering furniture forever is only right for furniture. Some of what
                # stands on these boards WALKS — measured, three of them, and every cell each one
                # crossed became a permanent wall until the board was a maze of places nothing
                # had ever been. An empty cell settles it: real furniture is drawn in every frame,
                # so a cell showing bare background never held any. A cell the carrier or a piece
                # is standing on is not empty and is left alone, which is what kept the rule that
                # a piece HIDES the furniture under it.
                self._walls.discard(cell)
                self._screens.discard(cell)
        # ⛔ Furniture is remembered, because a piece standing on it HIDES it. Measured: a piece
        # towed into a porous barrier covered the barrier, the cell then read as ordinary, and the
        # planner spent the rest of the level walking the carrier into a wall it could not enter.
        board.blocked |= self._walls
        board.porous |= self._screens
        # ⛔ Sticky, because the warning can be STOOD ON. Measured: the second destination here is
        # two cells, and with a piece dropped on one and the carrier standing on the other it
        # vanishes from the frame — so the flag flickered off on exactly the turns the carrier was
        # in position to act, and it walked away from a marked target three times.
        if fresh:
            self._seen = seen_now
            self._key = gm.tobytes()
        board.hostile = bool(self._zone)
        board.movers = {c: v for c, v in flats.items() if v in self._roam}
        # A glyph that is not cargo and not a bay is an actor the carrier is LOOKING AT: this
        # board redraws such an actor with a ring the moment it is faced, and that ring is the
        # only frame-visible confirmation that it is the kind which can be dealt with.
        board.marked = {c for c, v in glyphs.items()
                        if v and v[1] != cargo_core and c not in board.bays}
        return board

    # -- deciding ------------------------------------------------------------

    def _grip(self, board: _Board) -> Cell | None:
        """The offset of the piece the carrier is facing, if there is one."""
        if board.carrier is None or board.facing is None:
            return None
        d = _DELTA[board.facing]
        ahead = (board.carrier[0] + d[0], board.carrier[1] + d[1])
        return d if ahead in board.cargo else None

    def _walk(self, board: _Board, start: Cell) -> dict[Cell, list[int]]:
        """Shortest key sequence from `start` to every cell the carrier can stand on."""
        paths: dict[Cell, list[int]] = {start: []}
        queue: deque[Cell] = deque([start])
        while queue:
            cur = queue.popleft()
            for act in _MOVES:
                d = _DELTA[act]
                nxt = (cur[0] + d[0], cur[1] + d[1])
                if nxt in paths or not board.inside(nxt) or nxt in board.blocked:
                    continue
                if self._refused[(cur, None, act)] > 1:
                    continue
                paths[nxt] = paths[cur] + [act]
                queue.append(nxt)
        return paths

    def _tow(self, board: _Board, start: Cell, offset: Cell) -> dict[Cell, list[int]]:
        """Shortest key sequence for the carrier while a piece rides at a fixed offset."""
        paths: dict[Cell, list[int]] = {start: []}
        queue: deque[Cell] = deque([start])
        while queue:
            cur = queue.popleft()
            ride = (cur[0] + offset[0], cur[1] + offset[1])
            for act in _MOVES:
                d = _DELTA[act]
                nxt = (cur[0] + d[0], cur[1] + d[1])
                if nxt in paths or not board.inside(nxt):
                    continue
                if self._refused[(cur, offset, act)] > 1:
                    continue
                if nxt in board.blocked and (nxt != ride or nxt in self._walls):
                    continue
                lands = (ride[0] + d[0], ride[1] + d[1])
                if not board.inside(lands):
                    continue
                # The towed piece is stopped by other pieces but slips through porous furniture.
                if lands != cur and lands in board.blocked and lands not in board.porous:
                    continue
                paths[nxt] = paths[cur] + [act]
                queue.append(nxt)
        return paths

    @staticmethod
    def _near(cell: Cell, bays: set[Cell]) -> int:
        return min(_span(cell, b) for b in bays)

    def _targets(self, board: _Board) -> dict[Cell, Cell]:
        """One bay per loose piece, nearest pairing first.

        ⛔ Aiming every piece at the bay NEAREST it sends them all to the same side. Measured on a
        board whose bays sit in three pockets, each reachable by a different mover: six of seven
        pieces were delivered and the seventh was shoved into a pocket whose bays were already
        full, where the mover picked it up and then stood holding it for the rest of the level
        because it had nowhere to put it. A bay holds ONE piece, so it may be promised to one
        piece only, and the pocket a piece is sent to follows from that promise.
        """
        bays = self._open_bays(board, None)
        loose = [c for c in board.cargo if c not in board.bays]
        pairs = sorted((_span(p, b), p, b) for p in loose for b in bays)
        out: dict[Cell, Cell] = {}
        taken: set[Cell] = set()
        for _, piece, bay in pairs:
            if piece in out or bay in taken:
                continue
            out[piece] = bay
            taken.add(bay)
        return out

    def _open_bays(self, board: _Board, held: Cell | None) -> set[Cell]:
        return {b for b in board.bays if b not in board.cargo or b == held}

    def _decide(self, board: _Board) -> int | None:
        carrier = board.carrier
        if carrier is None or board.facing is None:
            return None
        # The latch is bookkeeping we own; the frame confirms it by where the piece sits.
        if self._offset is not None:
            ride = (carrier[0] + self._offset[0], carrier[1] + self._offset[1])
            if ride not in board.cargo:
                self._offset = None

        cargo_now = frozenset(board.cargo)
        if cargo_now != self._last_cargo:
            self._last_cargo = cargo_now
            self._parked = {p for p in self._parked if p in board.cargo}
            self._waits = self._nudges = 0

        # ⛔ The frame that reports a level cleared still DRAWS the level just finished, and a
        # finished board reads as "nothing to do". Nudging pulls the next frame; returning
        # nothing here strands the tool one action short of the whole rest of the game.
        if not board.bays:
            return self._nudge(board, carrier)
        targets = self._targets(board)
        if self._offset is not None:
            return self._deliver(board, carrier, self._offset, targets)
        if board.hostile:
            act = self._hunt(board, carrier)
            if act is not None:
                return act
        return self._collect(board, carrier, targets)

    def _deliver(self, board: _Board, carrier: Cell, offset: Cell,
                 targets: dict[Cell, Cell]) -> int | None:
        ride = (carrier[0] + offset[0], carrier[1] + offset[1])
        bays = self._open_bays(board, ride)
        if ride in bays:
            return _LATCH
        paths = self._tow(board, carrier, offset)
        reach = [(len(p), q) for q, p in paths.items()
                 if (q[0] + offset[0], q[1] + offset[1]) in bays]
        if reach:
            steps = paths[min(reach)[1]]
            return steps[0] if steps else _LATCH
        # Walled off from the bay this piece is promised: leave it as close to THAT bay as it can
        # be put, and let whatever else moves on this board take it from there.
        goal = targets.get(ride)
        if goal is None:
            return _LATCH
        best = min(paths, key=lambda q: (_span((q[0] + offset[0], q[1] + offset[1]), goal),
                                         len(paths[q])))
        if best == carrier:
            # ⛔ This grip is spent, which is NOT the same as the piece being as close as it can
            # get: taking hold of it from another side often reaches a cell this one cannot,
            # and on a hand-off board that cell is the difference between the other mover being
            # able to collect the piece and not. Let go, re-plan the grip, and only call the
            # piece parked once letting go has stopped helping.
            self._dropped[ride] += 1
            if self._dropped[ride] > 1:
                self._parked.add(ride)
            return _LATCH
        return paths[best][0]

    def _hunt(self, board: _Board, carrier: Cell) -> int | None:
        """Walk up to whatever is undoing the work and use the latch on it.

        ⛔ Delivering is not enough on a board that has a second destination: what carries pieces
        there takes them back OUT of the bays, so a board can be finished and unfinished forever.
        The latch, aimed at an actor rather than at a piece, removes it — but only some actors,
        and pressing it on the wrong one wastes the press. The board says which is which: face it,
        and the kind that CAN be removed is redrawn with a ring round it that turn. So the ring is
        the licence to press, and an actor that stays flat while being faced has its colour
        written off and is never chased again.

        ⚠️ Gated on there BEING a second destination, and on nothing else being worth doing.
        Chasing costs actions out of a declared budget, and on the boards where every mover is
        helping, that chase is the difference between finishing and running out.
        """
        if self._chase > _MAX_CHASE:
            return None
        prey = [c for c, kind in board.movers.items() if kind not in self._friendly]
        ahead = None
        if board.facing is not None:
            d = _DELTA[board.facing]
            ahead = (carrier[0] + d[0], carrier[1] + d[1])
            if ahead in board.marked:
                return _LATCH
            if ahead in board.movers:
                self._friendly.add(board.movers[ahead])
                self._aim = None
                return None
        if not prey:
            self._aim = None
            return None
        # ⛔ Do not follow it. Measured: both move in the same turn, so a carrier that turns to
        # where the thing IS is looking at where it WAS, and the two danced from cell to cell for
        # the rest of the level. Stand on the cell chosen and press the latch every turn instead:
        # the press is judged BEFORE anything else moves, so the turn the quarry steps into the
        # covered cell is the turn it is removed, and every other press costs nothing and — unlike
        # any movement key — leaves the carrier still pointing the same way.
        if (ahead is not None and self._aim == ahead and ahead not in board.cargo
                and min(_span(p, carrier) for p in prey) <= 2):
            self._chase += 1
            return _LATCH
        walk = self._walk(board, carrier)
        best: tuple[int, int, Cell, Cell] | None = None
        for cell in prey:
            for act in _MOVES:
                d = _DELTA[act]
                stance = (cell[0] - d[0], cell[1] - d[1])
                if stance not in walk:
                    continue
                cost = len(walk[stance])
                if best is None or cost < best[0]:
                    best = (cost, act, stance, cell)
        if best is None:
            return None
        self._chase += 1
        _, act, stance, cell = best
        if stance != carrier:
            return walk[stance][0]
        self._aim = cell
        return act if board.facing != act else _LATCH

    def _collect(self, board: _Board, carrier: Cell, targets: dict[Cell, Cell]) -> int | None:
        bays = self._open_bays(board, None)
        # A piece already standing in a bay is placed — judge that against EVERY bay, not the
        # open ones, or the piece just delivered reads as still wanted and the plan loops.
        wanted = [c for c in board.cargo if c not in board.bays and c not in self._parked]
        if not wanted:
            return self._wait(board, carrier)
        walk = self._walk(board, carrier)
        best: tuple[int, int, Cell] | None = None
        for piece in wanted:
            goal = targets.get(piece)
            if goal is None:
                continue
            for act in _MOVES:
                d = _DELTA[act]
                stance = (piece[0] - d[0], piece[1] - d[1])
                if stance not in walk:
                    continue
                tow = self._tow(board, stance, d)
                drop = [(len(p), q) for q, p in tow.items()
                        if (q[0] + d[0], q[1] + d[1]) in bays]
                if not drop:
                    if not board.porous:
                        continue
                    haul = min(_span((q[0] + d[0], q[1] + d[1]), goal) for q in tow)
                    if haul >= _span(piece, goal):
                        continue
                    cost = len(walk[stance]) + 200 + haul * 4
                else:
                    cost = len(walk[stance]) + 2 + min(drop)[0]
                cost += 0 if board.facing == act or stance != carrier else 1
                if best is None or cost < best[0]:
                    best = (cost, act, stance)
        if best is None:
            return self._wait(board, carrier)
        _, act, stance = best
        if stance != carrier:
            return walk[stance][0]
        if board.facing != act:
            return act
        return _LATCH

    def _wait(self, board: _Board, carrier: Cell) -> int | None:
        """Nothing left for this carrier to shift — hold station while the board moves itself.

        Some boards put a second mover on the far side of a barrier that only it can cross, and
        that mover only steps when the carrier does. Standing still is then the whole plan.
        """
        if not [c for c in board.cargo if c not in board.bays]:
            return self._nudge(board, carrier)
        self._waits += 1
        if self._waits > _MAX_WAIT:
            return None
        return self._hold(board, carrier)

    def _nudge(self, board: _Board, carrier: Cell) -> int | None:
        """A couple of turns to shake a fresh frame loose, then give the turn up."""
        self._nudges += 1
        if self._nudges > 3:
            return None
        return self._hold(board, carrier)

    @staticmethod
    def _hold(board: _Board, carrier: Cell) -> int:
        """A key press that cannot walk the carrier anywhere, if one is available."""
        for act in _MOVES:
            d = _DELTA[act]
            nxt = (carrier[0] + d[0], carrier[1] + d[1])
            if not board.inside(nxt) or nxt in board.blocked:
                return act
        return _MOVES[0]
