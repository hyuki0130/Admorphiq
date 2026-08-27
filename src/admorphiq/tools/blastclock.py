"""Blast-clock tool — park every loose piece in its outline, using the board's own timed charges.

The mechanic, recovered from the frames and then read off the engine's own dispatch to fix the
numbers:

* The board carries **outlines** — closed rings whose hollow interior is exactly one piece's shape,
  inset by a single cell. The level clears when every outline holds a piece cut to it.
* One piece is **held**; a click takes the hold, the four simple actions move the held piece by one
  lattice cell. A move into a wall or into the **glide field** is refused. A move into another piece
  does not move the holder — it **launches** what it touched, which slides five cells on its own and
  keeps going for as long as it is over the glide field.
* And the part this tool exists for: some pieces are **charges**. A charge carries a fuse that burns
  one line per move press, and when the last line burns it fires a **beam** — a rectangle of its own
  cross-section reaching three, then six, then nine cells out of its head, shoving everything it
  touches one lattice cell per stage. Then it re-arms and the countdown starts again. A charge is
  the only thing that crosses a glide field that spans the board, and on the boards that have one
  the held piece is on the wrong side of it: there is no route at all until the beam is in the plan.

⛔ **A fuse turns a refused press into a move.** Everywhere else on these boards a press the board
refuses is a wasted action and worth pruning from the search. With a charge on the board it is the
cheapest thing there is: it spends one action, changes nothing else, and advances every fuse by one
line. That is how the plan gets to arrive on the beat instead of near it, and pruning it — the
obvious thing to do, and what a launch-only model does — removes the only solutions these boards
have.

⛔ **The fuse's own burn says which way the beam goes**, and nothing else in a still frame does. The
burnt lines pile up behind the front, so the front advances in the firing direction and the burnt
band sits at the tail. A charge that has just re-armed is one flat colour and says nothing at all —
so when a charge is needed and unread, this tool spends ONE press the board refuses and reads the
line that appears. Guessing the direction is not available: half the charges on these boards are
square, and a square charge pointing up and one pointing down are the same pixels.

⛔ Frame-only. Nothing here knows which game it is. The lattice, the walls, the glide field, the
outlines, the pieces and which piece can be held all come from the shared read in
`tools/slotlaunch.py`; a charge is then any piece belonging to no outline whose body is a solid
rectangle split into a band of whole lines against one edge and a remainder — plus the observation
that the band grew on the last press.

Provenance: `environment_files/*/…` — the dispatch that resolves a press was read to get the four
numbers a search cannot guess: the launch runs FIVE cells, the beam reaches 3/6/9 in THREE stages,
the fuse burns on every move press and on none of the clicks, and a piece stranded on the glide
field keeps the velocity that put it there and is carried on by the next beam that touches it.
"""

from __future__ import annotations

import heapq
import time
from collections import deque
from typing import Any

import numpy as np

from admorphiq.tools.base import Step, availability, has_frame, levels_completed
from admorphiq.tools.slotlaunch import Board, current_frame, read_board, reread

__all__ = ["BlastClockTool", "Charge", "charges_of", "Sim", "plan_blast"]

Cell = tuple[int, int]
_DIRS: dict[int, Cell] = {1: (-1, 0), 2: (1, 0), 3: (0, -1), 4: (0, 1)}

# MEASURED off the dispatch, not tuned: a launched piece is carried for five lattice cells before it
# is allowed to settle, and the beam grows in three stages of one lattice cell each.
_RUN = 5
_STAGES = 3
_MAX_SLIDE = 60

# Search bounds. The board evolves on its own between presses, so every press is a distinct state and
# the frontier grows faster than it does for a board that only moves when pushed.
_NODE_CAP = 400_000
_TIME_CAP = 25.0
# The guide never charges for the piece that has to come and do the launching, nor for the presses
# spent waiting on a fuse, so it reads low on a crowded board. Leaning on it is what makes these
# finish; the cost is a few extra presses.
_LEAN = 3
# Seconds of search one level may cost. The harness allows a thousand for the whole game, so a
# seven-level board can afford this and still finish; a level that is still searching when it runs
# out withdraws rather than eating the game's clock.
_PLAN_BUDGET = 60.0
# Presses spent watching an unread charge before giving up on reading it.
_PROBE_CAP = 12


class Charge:
    """One timed blaster: which way it fires, how long its fuse is, and how much has burnt."""

    __slots__ = ("idx", "direction", "period", "burnt", "soonest")

    def __init__(self, idx: int, direction: Cell | None, period: int, burnt: int,
                 soonest: int | None = None) -> None:
        self.idx = idx
        self.direction = direction
        self.period = period
        self.burnt = burnt
        # Presses until this could fire at the EARLIEST. For a charge whose heading is still
        # unknown the two readings of its band disagree about how much has burnt, so the earliest
        # of them is the only honest answer — and it is what bounds how much plan may be handed
        # over before the board has to be looked at again.
        self.soonest = period - burnt if soonest is None else soonest

    @property
    def ready(self) -> bool:
        """Can this charge be planned around? Only once its firing direction is known."""
        return self.direction is not None

    def fires_at(self, tick: int) -> bool:
        """Does the fuse run out on the `tick`-th move press from now?"""
        return tick >= 1 and (self.burnt + tick) % self.period == 0


# --- perception -------------------------------------------------------------

def _rect(piece: Any) -> bool:
    """Is this piece a solid rectangle — the shape every charge on these boards is cut to?"""
    return len(piece.mask) == piece.h * piece.w


def _readings(block: np.ndarray) -> list[tuple[Cell, int, int]]:
    """Every (direction, period, burnt) a two-tone rectangle can support.

    One entry means the frame settles it. Two means the split sits at the exact middle and only
    watching the band grow can say which colour is the burn.
    """
    h, w = block.shape
    out: list[tuple[Cell, int, int]] = []
    for axis in (0, 1):
        lines = [tuple(int(v) for v in (block[i] if axis == 0 else block[:, i]))
                 for i in range(h if axis == 0 else w)]
        if any(len(set(line)) != 1 for line in lines):
            continue
        vals = [line[0] for line in lines]
        n = len(vals)
        if len(set(vals)) != 2:
            continue
        head = vals[0]
        cut = next(i for i, v in enumerate(vals) if v != head)
        if any(v != vals[cut] for v in vals[cut:]):
            continue  # more than one flip along the axis: not a fuse
        # band of `cut` lines pinned to the low edge, remainder pinned to the high edge
        low = (1, 0) if axis == 0 else (0, 1)
        high = (-1, 0) if axis == 0 else (0, -1)
        out.append((low, n, cut))          # low band burnt -> beam leaves the high edge
        out.append((high, n, n - cut))     # high band burnt -> beam leaves the low edge
    return out


def _block_of(g: np.ndarray, piece: Any) -> np.ndarray:
    """The colours a piece is painted in, lifted off the frame as its own little grid."""
    y, x = piece.pos
    return g[y:y + piece.h, x:x + piece.w].astype(np.int64)


def charges_of(board: Board, g: np.ndarray) -> dict[int, Charge]:
    """Every piece the frame says is a charge, with as much of its fuse as the frame can settle.

    Two kinds qualify, and the difference matters:

    * a solid rectangle painted in TWO edge-pinned bands is a burning fuse and is a charge whatever
      its shape. ⛔ Requiring it to belong to no outline looked safer and lost a whole board: one
      charge is cut to exactly the same square as the pieces, so it was filed as a piece, its beam
      never entered the model, and the model then mispredicted the board on the first press. A piece
      that belongs in an outline is rimmed and has its middle marked, so it is never two flat bands.
    * a flat rectangle belonging to no outline is a charge that has just re-armed. Flat says nothing
      about where it points, so it is carried with no heading until it burns.
    """
    slotted = set(board.shapes)
    out: dict[int, Charge] = {}
    for i, p in enumerate(board.pieces):
        if not _rect(p):
            continue
        reads = _readings(_block_of(g, p))
        if len(reads) == 1:
            d, period, burnt = reads[0]
            out[i] = Charge(i, d, period, burnt)
        elif reads:
            # Ambiguous: the fuse length is settled, the heading is not.
            period = reads[0][1]
            out[i] = Charge(i, None, period, 0, soonest=min((b for _, _, b in reads if b), default=period))
        elif p.mask not in slotted:
            out[i] = Charge(i, None, max(p.h, p.w), 0)
    return out


def read_growth(before: np.ndarray, after: np.ndarray, board: Board,
                known: dict[int, Charge]) -> dict[int, Charge]:
    """Settle a charge's heading by watching which lines of it darkened over one press.

    Purpose: this is the only evidence a square charge ever offers. Comparing the two frames' own
    readings is NOT enough — against a charge that has just re-armed the old frame is one flat colour
    and supports no reading, so both headings look equally new.

    What settles it is WHERE the change is. The lines that repainted are the ones the fuse has just
    eaten; they lie at the FRONT of the burnt band, which is pinned to the tail. So for a candidate
    heading, the changed lines must fall inside that heading's burnt band and must include its
    leading line. Exactly one heading survives that on every board measured, including the one where
    the front sits in the middle of the body and touches no edge at all.
    """
    fixed = dict(known)
    for i, p in enumerate(board.pieces):
        if i in fixed and fixed[i].ready:
            continue
        if not _rect(p):
            continue
        y, x = p.pos
        if (y + p.h > min(before.shape[0], after.shape[0])
                or x + p.w > min(before.shape[1], after.shape[1])):
            continue
        was = before[y:y + p.h, x:x + p.w].astype(np.int64)
        now = after[y:y + p.h, x:x + p.w].astype(np.int64)
        if was.shape != now.shape or (was == now).all():
            continue
        rows = {r for r in range(p.h) if (was[r] != now[r]).any()}
        cols = {c for c in range(p.w) if (was[:, c] != now[:, c]).any()}
        good: list[tuple[Cell, int, int]] = []
        for d, period, burnt in _readings(now):
            if not burnt:
                continue
            axis = 0 if d[0] else 1
            changed = rows if axis == 0 else cols
            n = p.h if axis == 0 else p.w
            # The burnt band sits against the tail — the edge the beam does NOT leave from.
            band = set(range(burnt)) if (d[0] > 0 or d[1] > 0) else set(range(n - burnt, n))
            lead = burnt - 1 if (d[0] > 0 or d[1] > 0) else n - burnt
            if changed and changed <= band and lead in changed:
                good.append((d, period, burnt))
        if len(good) == 1:
            d, period, burnt = good[0]
            fixed[i] = Charge(i, d, period, burnt)
    return fixed


def _flat_rect(g: np.ndarray, piece: Any) -> int | None:
    """The single colour a solid rectangular piece is painted in, or None if it is not one.

    A charge and each of its two burnt/unburnt halves are flat rectangles. A piece that belongs in an
    outline is not: the board paints it a rim and marks its middle.
    """
    if not _rect(piece):
        return None
    block = _block_of(g, piece)
    vals = {int(v) for row in block for v in row}
    return vals.pop() if len(vals) == 1 else None


def fuse_pieces(board: Board, g: np.ndarray) -> Board:
    """Put a half-burnt charge back together.

    ⛔ MEASURED against the engine on the first press of the level this tool exists for: a charge
    burnt exactly halfway is two flat bands of equal size, both of them whole lattice cells, and the
    shared read hands them back as TWO pieces. Every number after that is wrong — the beam is aimed
    from the wrong corner, the launch geometry doubles, and on one board each half is cut to the same
    shape as a real piece, so the search cheerfully plans to shove half a bomb into an outline.

    The join is keyed on the mechanic, not on a size: two flat rectangles of DIFFERENT colours that
    abut into a rectangle matching no outline. A piece with a slot never qualifies — the board rims it
    and marks its middle, so it is not flat.
    """
    from admorphiq.tools.slotlaunch import Piece

    shapes = set(board.shapes)
    pieces = list(board.pieces)
    flat = {i: _flat_rect(g, p) for i, p in enumerate(pieces)}
    merged = True
    while merged:
        merged = False
        for a in range(len(pieces)):
            for b in range(a + 1, len(pieces)):
                pa, pb = pieces[a], pieces[b]
                ca, cb = flat.get(a), flat.get(b)
                if ca is None or cb is None or ca == cb:
                    continue
                y0 = min(pa.pos[0], pb.pos[0])
                x0 = min(pa.pos[1], pb.pos[1])
                y1 = max(pa.pos[0] + pa.h, pb.pos[0] + pb.h)
                x1 = max(pa.pos[1] + pa.w, pb.pos[1] + pb.w)
                if (y1 - y0) * (x1 - x0) != pa.h * pa.w + pb.h * pb.w:
                    continue
                mask = frozenset((y, x) for y in range(y1 - y0) for x in range(x1 - x0))
                if mask in shapes:
                    continue
                whole = Piece(mask, (y0, x0), frozenset(), y1 - y0, x1 - x0)
                keep = [p for k, p in enumerate(pieces) if k not in (a, b)]
                held_piece = pieces[board.held] if board.held is not None else None
                pieces = keep + [whole]
                flat = {i: _flat_rect(g, p) for i, p in enumerate(pieces)}
                if held_piece is not None:
                    board.held = next(
                        (i for i, p in enumerate(pieces)
                         if p.pos == held_piece.pos and p.mask == held_piece.mask), None)
                merged = True
                break
            if merged:
                break
    if len(pieces) == len(board.pieces):
        return board
    board.pieces = pieces
    board.walk_ok = []
    board.slide_ok = []
    board.on_glide = []
    _tables(board)
    return board


def _tables(board: Board) -> None:
    """Per piece and per lattice square, whether it may stand there.

    Two different answers, and conflating them eats the level: the held piece is refused by the glide
    field, a launched or blasted one rides straight over it.
    """
    rows = board.rows
    width = board.walls.shape[1]
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
                    if not (0 <= y < rows and 0 <= x < width) or board.walls[y][x]:
                        ok_slide = ok_walk = False
                        break
                    if board.glide[y][x]:
                        ok_walk = False
                        ice = True
                slide[iy][ix] = ok_slide
                walk[iy][ix] = ok_walk and ok_slide
                onice[iy][ix] = ice
        board.walk_ok.append(walk)
        board.slide_ok.append(slide)
        board.on_glide.append(onice)


# --- the model the planner searches ----------------------------------------

class Sim:
    """A faithful replay of one press: move or launch, then burn the fuses, then fire and drain."""

    def __init__(self, board: Board, charges: dict[int, Charge]) -> None:
        self.b = board
        self.s = board.step
        self.n = len(board.pieces)
        self.base = [p.pos for p in board.pieces]
        self.masks = [p.mask for p in board.pieces]
        self.phase = [(p.pos[0] % self.s, p.pos[1] % self.s) for p in board.pieces]
        self.click = [i for i, p in enumerate(board.pieces) if p.clickable]
        self.live = [c for c in charges.values() if c.ready]
        self.period = 1
        for c in self.live:
            self.period = _lcm(self.period, c.period)
        self.depth = self.n + 2

    # -- tables -------------------------------------------------------------

    def _tab(self, tab: list[np.ndarray], i: int, pos: Cell) -> bool:
        iy = (pos[0] - self.phase[i][0]) // self.s
        ix = (pos[1] - self.phase[i][1]) // self.s
        if (pos[0] - self.phase[i][0]) % self.s or (pos[1] - self.phase[i][1]) % self.s:
            return False
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

    # -- geometry -----------------------------------------------------------

    def hits(self, i: int, pi: Cell, j: int, pj: Cell) -> bool:
        if abs(pi[0] - pj[0]) >= max(self.b.pieces[i].h, self.b.pieces[j].h):
            return False
        if abs(pi[1] - pj[1]) >= max(self.b.pieces[i].w, self.b.pieces[j].w):
            return False
        a = {(pi[0] + dy, pi[1] + dx) for dy, dx in self.masks[i]}
        return any((pj[0] + dy, pj[1] + dx) in a for dy, dx in self.masks[j])

    def beam(self, c: Charge, pos: Cell, stage: int) -> tuple[int, int, int, int]:
        """The rectangle the beam covers at stage 1..3, as (y0, x0, y1, x1) inclusive.

        It is the charge's own cross-section extruded out of its head, reaching `stage` lattice
        cells. Cumulative rather than a moving segment: a piece the beam has already passed has
        moved on with it, so the difference is not observable, and the cumulative form is the one
        the wider charges actually draw.
        """
        p = self.b.pieces[c.idx]
        y, x = pos
        reach = stage * self.s
        dy, dx = c.direction  # type: ignore[misc]
        if dy > 0:
            return (y + p.h, x, y + p.h - 1 + reach, x + p.w - 1)
        if dy < 0:
            return (y - reach, x, y - 1, x + p.w - 1)
        if dx > 0:
            return (y, x + p.w, y + p.h - 1, x + p.w - 1 + reach)
        return (y, x - reach, y + p.h - 1, x - 1)

    def in_beam(self, j: int, pos: Cell, box: tuple[int, int, int, int]) -> bool:
        y0, x0, y1, x1 = box
        py, px = pos
        p = self.b.pieces[j]
        if py > y1 or py + p.h - 1 < y0 or px > x1 or px + p.w - 1 < x0:
            return False
        return any(y0 <= py + dy <= y1 and x0 <= px + dx <= x1 for dy, dx in self.masks[j])

    # -- the shove ----------------------------------------------------------

    def shove(self, pos: list[Cell], i: int, d: Cell, depth: int = 0) -> bool:
        """Drive piece i one lattice cell along d, dragging what it meets. True means it jammed.

        ⛔ A jam reverts only the piece that jammed, exactly as the board does — the pieces already
        driven ahead of it in the same chain stay where they were put. Reverting the whole chain
        looked tidier and predicted the wrong board.
        """
        old = pos[i]
        new = (old[0] + d[0] * self.s, old[1] + d[1] * self.s)
        pos[i] = new
        if depth > self.depth or not self.slide_ok(i, new):
            pos[i] = old
            return True
        for j in range(self.n):
            if j != i and self.hits(i, new, j, pos[j]) and self.shove(pos, j, d, depth + 1):
                pos[i] = old
                return True
        return False

    # -- one press ----------------------------------------------------------

    def press(self, pos: tuple[Cell, ...], held: int, vel: tuple[int, ...], tick: int,
              act: Step) -> tuple[tuple[Cell, ...], int, tuple[int, ...], int]:
        """Resolve one action into the next state. Clicks do not burn the fuse; moves always do."""
        aid, _ = act
        if aid == 6:
            return pos, held, vel, tick
        cur = list(pos)
        vv = list(vel)
        d = _DIRS[aid]
        nxt = (cur[held][0] + d[0] * self.s, cur[held][1] + d[1] * self.s)
        if self.walk_ok(held, nxt):
            launched = [j for j in range(self.n) if j != held and self.hits(held, nxt, j, cur[j])]
            if not launched:
                cur[held] = nxt
            else:
                for j in launched:
                    vv[j] = aid
                run = 0
                while run <= _MAX_SLIDE:
                    settled = True
                    for j in launched:
                        if run >= _RUN and not self.on_glide(j, cur[j]):
                            continue
                        if self.shove(cur, j, d):
                            continue
                        settled = False
                    if settled:
                        break
                    run += 1
        tick += 1
        fired = [c for c in self.live if c.fires_at(tick)]
        if fired:
            self._fire(cur, vv, fired)
        return tuple(cur), held, tuple(vv), tick % self.period

    def _fire(self, pos: list[Cell], vel: list[int], fired: list[Charge]) -> None:
        """Three stages of beam, then carry away anything the blast left stranded on the glide."""
        for stage in range(1, _STAGES + 1):
            for c in fired:
                box = self.beam(c, pos[c.idx], stage)
                aid = next(a for a, d in _DIRS.items() if d == c.direction)
                for j in range(self.n):
                    if j == c.idx or not self.in_beam(j, pos[j], box):
                        continue
                    self.shove(pos, j, c.direction)  # type: ignore[arg-type]
                    vel[j] = aid
        moved = True
        guard = 0
        while moved and guard < _MAX_SLIDE:
            moved = False
            guard += 1
            for j in range(self.n):
                if vel[j] and self.on_glide(j, pos[j]) and not self.shove(pos, j, _DIRS[vel[j]]):
                    moved = True


def _lcm(a: int, b: int) -> int:
    x, y = a, b
    while y:
        x, y = y, x % y
    return a * b // max(x, 1)


# --- planning ---------------------------------------------------------------

def _owners(board: Board) -> dict[int, list[int]]:
    """Which pieces may fill each outline — the ones you can take hold of, when the board offers any.

    ⛔ An obstacle can share an outline's shape and sit next to it, and shoving THAT in is not a state
    the board scores as a win. Prefer a piece the board lets you hold; fall back to shape alone only
    when no held piece is cut to that outline (the pieces that ride in on a beam are never clickable).
    """
    out: dict[int, list[int]] = {}
    for k, sh in enumerate(board.shapes):
        same = [i for i, p in enumerate(board.pieces) if p.mask == sh]
        steer = [i for i in same if board.pieces[i].clickable]
        out[k] = steer or same
    return out


def _fits(board: Board) -> bool:
    """Does every outline have at least one piece cut to its shape? The model's admission ticket."""
    return all(any(p.mask == sh for p in board.pieces) for sh in board.shapes)


def _blast_landing(sim: Sim, i: int, start: Cell, c: Charge) -> Cell:
    """Where a lone piece i standing at `start` ends up when charge c fires."""
    pos = [p for p in sim.base]
    pos[i] = start
    saved = pos[c.idx]
    for stage in range(1, _STAGES + 1):
        box = sim.beam(c, saved, stage)
        if i != c.idx and sim.in_beam(i, pos[i], box):
            here = pos[i]
            pos[i] = (here[0] + c.direction[0] * sim.s, here[1] + c.direction[1] * sim.s)  # type: ignore[index]
            if not sim.slide_ok(i, pos[i]):
                pos[i] = here
    guard = 0
    while sim.on_glide(i, pos[i]) and guard < _MAX_SLIDE:
        guard += 1
        here = pos[i]
        pos[i] = (here[0] + c.direction[0] * sim.s, here[1] + c.direction[1] * sim.s)  # type: ignore[index]
        if not sim.slide_ok(i, pos[i]):
            pos[i] = here
            break
    return pos[i]


def _relaxed(sim: Sim, board: Board, target: Cell, i: int) -> dict[Cell, int]:
    """Cheapest presses to bring piece i to its outline, other pieces wished away.

    Purpose: the search's guide, and on a board cut in two by a glide field it is also the only
    thing that knows a route EXISTS. It undercounts on purpose — it charges nothing for the piece
    that comes to launch, nor for the presses spent waiting on a fuse — so it never talks the
    search out of a real solution. ⛔ Without the beam edges it returns "unreachable" for every
    square on the far side of a glide field, which prunes the whole search to nothing: that is
    exactly what a launch-only model does on these boards, and why they read as impossible.
    """
    s = sim.s
    tab = board.slide_ok[i]
    ny, nx = tab.shape
    py, px = sim.base[i][0] % s, sim.base[i][1] % s
    back: dict[Cell, list[Cell]] = {}
    clickable = board.pieces[i].clickable
    for iy in range(ny):
        for ix in range(nx):
            if not tab[iy][ix]:
                continue
            here = (py + iy * s, px + ix * s)
            for d in _DIRS.values():
                step_to = (here[0] + d[0] * s, here[1] + d[1] * s)
                if clickable and sim.walk_ok(i, here) and sim.walk_ok(i, step_to):
                    back.setdefault(step_to, []).append(here)
                land = here
                run = 0
                while run <= _MAX_SLIDE:
                    if run >= _RUN and not sim.on_glide(i, land):
                        break
                    nb = (land[0] + d[0] * s, land[1] + d[1] * s)
                    if not sim.slide_ok(i, nb):
                        break
                    land = nb
                    run += 1
                if land != here:
                    back.setdefault(land, []).append(here)
            for c in sim.live:
                land = _blast_landing(sim, i, here, c)
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


def _click_at(board: Board, i: int, pos: tuple[Cell, ...]) -> Cell:
    """Where to click to take hold of piece i: the middle of its own body, as (x, y)."""
    p = board.pieces[i]
    y, x = pos[i]
    cy, cx = y + p.h // 2, x + p.w // 2
    if (p.h // 2, p.w // 2) not in p.mask:
        dy, dx = sorted(p.mask)[len(p.mask) // 2]
        cy, cx = y + dy, x + dx
    return (cx, cy)


def plan_blast(board: Board, charges: dict[int, Charge], cap: int = _NODE_CAP,
               limit: float = _TIME_CAP) -> list[Step] | None:
    """Search the model for a press sequence that fills every outline.

    ⛔ No piece is assigned to an outline up front, and a press the board REFUSES is a legal move
    whenever a fuse is running — it is the wait, and without it the beam is never caught on the beat.
    """
    if not _fits(board):
        return None
    sim = Sim(board, charges)
    if not sim.click:
        return None
    owners = _owners(board)
    slots = list(range(len(board.shapes)))
    goal = board.targets
    costs = {(i, k): _relaxed(sim, board, goal[k], i) for k in slots for i in owners[k]}
    big = 1 << 20
    ticking = bool(sim.live)

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

    start = tuple(sim.base)
    if done(start):
        return []
    zero = tuple(0 for _ in range(sim.n))
    seen: dict[tuple[tuple[Cell, ...], int, tuple[int, ...], int], int] = {}
    heap: list[tuple[int, int, tuple[Cell, ...], int, tuple[int, ...], int, tuple[Step, ...]]] = []
    tock = 0
    for h in sim.click:
        cost = 0 if h == board.held else 1
        acts: tuple[Step, ...] = () if h == board.held else ((6, _click_at(board, h, start)),)
        key = (start, h, zero, 0)
        if seen.get(key, big) <= cost:
            continue
        seen[key] = cost
        tock += 1
        heapq.heappush(heap, (cost + _LEAN * heur(start), tock, start, h, zero, 0, acts))
    popped = 0
    stop = time.monotonic() + limit
    while heap and popped < cap:
        _, _, pos, held, vel, tick, acts = heapq.heappop(heap)
        popped += 1
        if not popped % 2048 and time.monotonic() > stop:
            return None
        g = len(acts)
        if seen.get((pos, held, vel, tick), big) < g:
            continue
        if done(pos):
            return list(acts)
        moves: list[tuple[Step, tuple[tuple[Cell, ...], int, tuple[int, ...], int]]] = []
        for aid in _DIRS:
            nxt = sim.press(pos, held, vel, tick, (aid, None))
            # A press that leaves the board and every fuse exactly as they were is a wasted action.
            if not ticking and nxt[0] == pos:
                continue
            moves.append(((aid, None), nxt))
        for j in sim.click:
            if j != held:
                moves.append(((6, _click_at(board, j, pos)), (pos, j, vel, tick)))
        for act, (npos, nheld, nvel, ntick) in moves:
            ng = g + 1
            key = (npos, nheld, nvel, ntick)
            if seen.get(key, big) <= ng:
                continue
            h2 = heur(npos)
            if h2 >= big:
                continue
            seen[key] = ng
            tock += 1
            heapq.heappush(heap, (ng + _LEAN * h2, tock, npos, nheld, nvel, ntick, acts + (act,)))
    return None


def refused_press(board: Board, charges: dict[int, Charge]) -> Step | None:
    """A press the board will simply refuse — the free tick, and the probe that reads a fuse."""
    if board.held is None:
        return None
    sim = Sim(board, charges)
    start = tuple(sim.base)
    for aid, d in _DIRS.items():
        nxt = (start[board.held][0] + d[0] * sim.s, start[board.held][1] + d[1] * sim.s)
        if not sim.walk_ok(board.held, nxt):
            return (aid, None)
    return None


class BlastClockTool:
    """Read the outlines and the fuses, model the beam, and hand back the whole sequence."""

    name = "blastclock"

    def __init__(self) -> None:
        self._level = -1
        self._static: Board | None = None
        self._charges: dict[int, Charge] = {}
        self._prev: np.ndarray | None = None
        self._took: Cell | None = None
        self._known: dict[tuple[Cell, int, int], tuple[Cell, int]] = {}
        self._spent = 0.0
        self._probes = 0
        self._needs_beam: bool | None = None

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
        self._static = None
        self._charges = {}
        self._prev = None
        self._took = None
        self._known = {}
        self._spent = 0.0
        self._probes = 0
        self._needs_beam = None

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        return None

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        if not has_frame(obs):
            return []
        lvl = levels_completed(obs)
        if lvl != self._level:
            self._level = lvl
            self.reset()
        g = current_frame(obs)
        if self._static is None:
            self._static = read_board(g)
            board = self._static
        else:
            board = reread(self._static, g)
        if board is None:
            return []
        board = fuse_pieces(board, g)
        if self._took is not None:
            # ⛔ Remember what the last click took hold of. Taking hold of the only piece on the board
            # changes not one pixel, so a plan re-derived after it opens with the same click again.
            x, y = self._took
            for i, p in enumerate(board.pieces):
                if (y - p.pos[0], x - p.pos[1]) in p.mask:
                    board.held = i
                    break
        charges = self._charges_now(board, g)
        self._prev = g

        unread = [c for c in charges.values() if not c.ready]
        if unread and self._probes < _PROBE_CAP:
            probe = self._probe(board, charges)
            if probe is not None:
                self._probes += 1
                return [probe]
        steps = self._search(board, charges, _TIME_CAP)
        if not steps:
            return []
        for aid, xy in steps:
            if aid == 6 and xy is not None:
                self._took = xy
        if not unread:
            return steps
        # ⛔ A sequence handed over whole is only sound when every charge on the board is in the
        # model. With one still unread, hand over only as far as that charge could possibly fire and
        # then look again — the plan past that point was written about a board that will not exist.
        soon = max(1, min(c.soonest for c in unread))
        return steps[:soon]

    def _charges_now(self, board: Board, g: np.ndarray) -> dict[int, Charge]:
        """This frame's charges, with every heading the tool has ever established folded back in.

        A charge that fires goes flat again and forgets which way it points, so the heading is
        remembered against the square it stands on — re-learning it costs a press, and on a board
        with a charge every press is on a clock.
        """
        fresh = charges_of(board, g)
        if self._prev is not None:
            fresh = read_growth(self._prev, g, board, fresh)
        for i, c in fresh.items():
            key = (board.pieces[i].pos, board.pieces[i].h, board.pieces[i].w)
            if c.ready:
                self._known[key] = (c.direction, c.period)  # type: ignore[assignment]
            elif key in self._known:
                d, period = self._known[key]
                fresh[i] = Charge(i, d, period, c.burnt, soonest=c.soonest)
        return fresh

    def _search(self, board: Board, charges: dict[int, Charge], limit: float,
                cap: int = _NODE_CAP) -> list[Step] | None:
        """Plan, against a per-LEVEL time budget rather than a per-call one.

        ⛔ A per-call deadline does not bound the cost and the same mistake has been made one level
        down in this harness: no single search is slow, the cost is in their number. With a charge
        still unread the plan is re-derived every few presses, so what has to be capped is the sum.
        """
        left = _PLAN_BUDGET - self._spent
        if left <= 0.5:
            return None
        began = time.monotonic()
        out = plan_blast(board, charges, cap=cap, limit=min(limit, left))
        self._spent += time.monotonic() - began
        return out

    def _probe(self, board: Board, charges: dict[int, Charge]) -> Step | None:
        """One press whose only purpose is to make a fuse legible — refused if the board offers one.

        ⛔ Only probe when the board actually needs the beam. A route that already exists without it
        is worth more than a tidy reading of a charge nothing is waiting on.
        """
        if self._needs_beam is None:
            self._needs_beam = self._search(board, {}, 6.0, cap=40_000) is None
        if not self._needs_beam:
            return None
        probe = refused_press(board, charges)
        if probe is not None:
            return probe
        # Nothing is refused, so read the fuse off any legal press instead.
        if board.held is None:
            return None
        sim = Sim(board, charges)
        here = board.pieces[board.held].pos
        for aid, d in _DIRS.items():
            if sim.walk_ok(board.held, (here[0] + d[0] * sim.s, here[1] + d[1] * sim.s)):
                return (aid, None)
        return None
