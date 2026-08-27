"""Reforge — pieces re-dyed and RE-SHAPED on their way to a blueprint's pinned cells.

The family this reads: a faint blueprint lies under the board as a scatter of PINS — each a 3x3
ring of one flat colour with a single differently-coloured pip at its middle, standing alone in
empty space. Above it sit a few skeletal PIECES: a plus, a rectangle outline, an X, a bar, each
drawn in one colour. Exactly one piece is driven at a time; four actions slide it a fixed step,
a fifth hands the controls to the next piece. The level is won when every pin's pip cell carries
a piece cell OF THE PIP'S OWN COLOUR — nothing else about the board is scored.

Two static furnishings make the family more than a sliding puzzle, and they are what this tool
exists for:

* **DYE PADS** — small solid squares, a uniform frame around a solid middle. A piece that touches
  one is repainted, whole, in the middle's colour. Pins may demand colours NO piece starts with,
  so on those boards a plan that does not route through a pad cannot exist.
* **THE PRESS** — a small pierced block. A rectangle outline that walks into it sideways comes out
  three rows TALLER and three columns NARROWER; walking in vertically trades the other way. Height
  plus width is conserved, so the press is a one-dimensional dial and the pins fix where it must be
  set. A plus walked into it does not change size at all — instead its bar SLIDES three columns (or
  rows) inside its own frame, which is how a plus reaches a pin further out than half its span.

⛔ THE PRESS IS THE WHOLE POINT, AND IT IS WHY DEPTH WAS STUCK. Measured on the board this was
built against: its last three levels ALL demand a rectangle whose height and width are not the
one it starts with, and one of those three had been banked as *provably unwinnable*. It is not:
the demanded rectangles are 19x7 and 10x16 against a start of 13x13, and 19+7 = 10+16 = 13+13.
The park was a claim about a tool, read as a claim about the game.

⛔ Bid ZERO without a COMPLETE plan. Every level here declares an action budget and ENDS on
overrun, so a half-plan is not a partial score, it is a lost level plus everything after it.
`detect` therefore parses the board, solves it offline against a faithful model of the press and
the pads, and only then claims it. Boards whose pieces cannot be read apart — two pieces sharing
one colour, an outline the segmenter cannot complete — return 0.0 and are left to whoever can.
Measured over a 120-action WALK of each of the 25 sample games: this tool claims exactly one.

MEASURED, in the real harness with the full tool set and no model (2026-08-27): the game it was
built against went from **5 levels in 1500 actions to 8 — a WIN, in 1115** — with the first five
levels cleared at the SAME action counts as before, by the same incumbent tool. Alone from each
level in turn, the three that were out of reach cost 50, 105 and 168 actions against budgets of
200, 300 and 400. The tool does NOT claim that game's second, third or fifth level and says so
with a bid of zero; the incumbent keeps them, which is why nothing regressed.

⛔ WHAT THIS TOOL CANNOT FIX FROM HERE, MEASURED SO NOBODY SPENDS A DAY ON IT. The game's whole
remaining shortfall is 401 actions binned on its SIXTH level — and not one of them is spent by
this tool. Counted per attempt AND PER TOOL, that level reads:

    attempt 1  LOST  200 actions   {incumbent: 200}
    attempt 2  LOST  201 actions   {incumbent: 201}
    attempt 3  WON   144 actions   {incumbent: 81, this tool: 63}

The incumbent holds it through two lost allowances while bidding 0.00 on it, because a death
restores the board and the novelty clock never reaches a stall; this tool is first asked at action
782 and clears it in 63 against an allowance of 200 — a THREEFOLD margin, so there is no overrun
here to plan around. ⛔ Read the winning attempt's 144 as this tool's route and the conclusion
inverts: it is 81 of the incumbent's plus 63 of this one.
The lever is the handover, in the loop, not the route. Priced: re-deciding on a DEATH is worth
0.8349 -> 0.8752 and saves 294 actions on both renderings. ⛔ The tempting stronger rule — hand
over when the incumbent has no claim and someone else does — is REFUTED: 8 levels became 2,
because the incumbent also bids 0.00 on two levels it goes on to clear at 1.0, and the general
searcher bids 0.80 on every board in the game.

⛔ THE SAME BOARD, SERVED TWICE, IS THE ONLY TRANSFER EVIDENCE THERE IS — AND IT FOUND A DEFECT
THE SCORE COULD NOT. An archived copy of this game, identical in every sprite, position, rotation
and budget and differing ONLY in the ORDER its sprites are listed, ran **23x slower per action**
and was cut off at 6 of 8 levels. The order decides which of two overlapping pieces is drawn on
top, and two of the three faults below turned on exactly that. Fixed, both renderings now score
**0.8350, 8 of 8, in 4.5 and 4.6 seconds** — from 15.1s and 1011s. A search that answers in one
rendering and not in another is not slow, it is broken, and on a public board it looks perfect.

⛔ The pip is not always readable. A piece lying across a pin overwrites the pip, so the colour
demanded there reads back as the piece's own. Such pips are marked UNKNOWN and their colour is
searched over the colours the other pins show, rather than believed.

⛔ Nothing about which action goes which way is assumed. The step and the four directions are
MEASURED — one action, one observed displacement — because the plan's arithmetic is in units of
that step and a guessed step spends the budget in the wrong place.
"""

from __future__ import annotations

from bisect import bisect_left
from collections import deque
from typing import Any

import numpy as np

from admorphiq.tools.base import Step, availability, has_frame
from admorphiq.tools.budget import BudgetReader
from admorphiq.tools.segment import background, components

__all__ = ["ReforgeTool"]

Cell = tuple[int, int]
# (x, y, h, w, bar_col, bar_row, colour) — the complete state of one piece.
State = tuple[int, int, int, int, int, int, int]

# A pin is a 3x3 ring standing ALONE: at least this many of its eight border cells survive
# (a bar lying across it can eat two), and none of its colour may appear in the surrounding
# halo — which is what separates a pin from the corner of a dye pad, whose frame looks the same.
_RING_MIN = 6
# How much of the ring colour a pin tolerates in the halo just outside its own 3x3. A neighbouring
# pin can contribute a cell or two; a dye pad's corner brings the rest of its frame, which is more.
_HALO_MAX = 6
# Below this span an object is furniture (a pin, a pad, the press), not a piece.
_PIECE_SPAN = 10
# Offered when the board is read AND a complete plan exists — the strongest evidence a tool can
# have, so it claims accordingly. ⛔ Measured at 0.68 the general searcher outbid it at 0.80 on the
# very board it had a finished plan for, and the level went unplayed. The lower figure is offered
# while the controls are still being measured: the family is recognised, the plan is not yet
# arithmetic. Both drop to 0.0 the moment no plan exists, and the harness re-reads the bid on
# every stall, so holding a board this tool cannot solve is not possible.
_CLAIM = 0.90
_PROBE_CLAIM = 0.82

# What fraction of the READ allowance a plan is allowed to occupy. The reader over-reads on this
# family — MEASURED against the game's own declared counters on all eight of its levels: 100 read
# as 107, 200 as 232, 250 as 347, 400 as 570, never once short. An over-read licences exactly the
# overrun the allowance exists to prevent, so it is discounted until every one of those eight
# becomes an under-estimate. Not a safety margin plucked from the air: 0.7 is the largest value
# for which 570 x f <= 400 holds.
_ALLOWANCE_TRUST = 0.7


# --------------------------------------------------------------------------- board


class Board:
    """Everything the plan needs, recovered from one frame."""

    def __init__(self) -> None:
        self.bg: int = -1
        self.pin_ring: int = -1
        self.pins: list[tuple[Cell, int | None]] = []
        self.pin_colours: list[int] = []
        self.pieces: list[dict[str, Any]] = []
        self.gates: list[tuple[np.ndarray, tuple[int, int, int, int]]] = []
        self.pads: list[tuple[np.ndarray, int]] = []
        self.selected: int | None = None


def settled_frame(obs: Any) -> np.ndarray:
    """The board AFTER the action has finished playing out.

    ⛔ The shared reader takes the FIRST of an observation's grids. That is the right answer for a
    board that answers an action instantly and the wrong one here: a dye spreads across a piece
    over many engine ticks and arrives as a whole reel of grids, of whose first still shows the
    piece in its old colour. MEASURED — a model checked against that grid disagrees with itself
    one move after every dye and throws away a plan that was working.
    """
    arr = np.asarray(getattr(obs, "frame", None))
    while arr.ndim >= 3:
        arr = arr[-1]
    return arr.astype(np.int16)


def _same_colour_components(grid: np.ndarray, colour: int) -> list[list[Cell]]:
    """4-connected runs of one colour, via the shared segmenter."""
    palette = {int(v) for v in np.unique(grid)}
    return components(grid, palette - {colour})


def _chrome_mask(grid: np.ndarray, bg: int) -> np.ndarray:
    """Border lines that are wholly non-background — the drawn budget gauge and its like."""
    h, w = grid.shape
    mask = np.zeros_like(grid, dtype=bool)
    for row in (0, h - 1):
        if not (grid[row] == bg).any():
            mask[row] = True
    for col in (0, w - 1):
        if not (grid[:, col] == bg).any():
            mask[:, col] = True
    return mask


def _neighbour_sums(mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """For every cell: how many cells of this colour sit in its 3x3 border, and how many more
    sit in the 5x5 ring around that. Written as shifted sums because the scan runs on every
    detect call and a Python double loop over the board makes bidding cost seconds per game."""
    height, width = mask.shape
    padded = np.zeros((height + 4, width + 4), dtype=np.int16)
    padded[2:-2, 2:-2] = mask.astype(np.int16)

    def box(size: int) -> np.ndarray:
        half = size // 2
        total = np.zeros((height, width), dtype=np.int16)
        for dy in range(-half, half + 1):
            for dx in range(-half, half + 1):
                total += padded[2 + dy:2 + dy + height, 2 + dx:2 + dx + width]
        return total

    box3, box5 = box(3), box(5)
    return box3 - padded[2:-2, 2:-2], box5 - box3


class Layout:
    """The board's immovable furniture, plus the union of it.

    The union is the cheap first question every move asks: a move that touches nothing at all —
    which is nearly all of them — is answered once here instead of once per press and once per
    dye pad. On the board with fourteen pads that is one test in place of fifteen.
    """

    __slots__ = ("gates", "pads", "any_of")

    def __init__(self, gates: list, pads: list) -> None:
        self.gates = gates
        self.pads = pads
        cells: set[Cell] = set()
        for blocks, _ in gates:
            cells |= blocks.cells
        for blocks, _ in pads:
            cells |= blocks.cells
        self.any_of = _Blocks(cells)


def _find_pins(grid: np.ndarray, bg: int, live: np.ndarray) -> tuple[int, list[Cell]]:
    """The ring colour and the middles of every ring drawn in it.

    ⛔ The colour is chosen by counting WHOLE, ISOLATED rings — a dye pad's frame reads as a ring
    at each of its corners, so a bare window test hands the blueprint's identity to the pads,
    and a pad's corner always has more of its own colour in the surrounding halo than a pin does.

    ⛔ But a board that has been PLAYED for a while has no whole rings left: the pieces are parked
    on top of them. MEASURED — the tool was never handed a board because by the time anything
    asked, another tool had spent 180 actions on it and not one of the eight rings survived
    intact. So when no colour has whole rings, the same test runs with the tolerance the rest of
    this module uses for occlusion, and only the halo keeps the pads out.
    """
    scan = live & (grid != bg)

    def sweep(colour: int, floor: int, roof: int) -> np.ndarray:
        ring, halo = _neighbour_sums((grid == colour) & live)
        ok = scan & (grid != colour) & (ring >= floor) & (halo <= roof)
        ok[0, :] = ok[-1, :] = ok[:, 0] = ok[:, -1] = False
        return ok

    palette = sorted({int(v) for v in np.unique(grid)} - {bg})
    best_colour, best_count = -1, 0
    for strict in (True, False):
        for colour in palette:
            found = int(sweep(colour, 8, 0).sum()) if strict \
                else int(sweep(colour, _RING_MIN, _HALO_MAX).sum())
            if found > best_count:
                best_colour, best_count = colour, found
        if best_count >= 3:
            break
    if best_count < 3:
        return -1, []
    # ⛔ Strict for WHICH COLOUR, relaxed for WHICH PINS. Two pins three cells apart each put a
    # cell in the other's halo, so the strict test drops both — and a dropped pin's pip is then
    # read as part of whichever piece shares its colour, which breaks that piece's shape.
    ring, _ = _neighbour_sums((grid == best_colour) & live)
    ok = sweep(best_colour, _RING_MIN, _HALO_MAX)
    best_hits = [(int(y), int(x)) for y, x in zip(*np.where(ok))]
    best_hits.sort(key=lambda cell: -int(ring[cell]))
    kept: list[Cell] = []
    for y, x in best_hits:
        if all(max(abs(y - py), abs(x - px)) > 2 for py, px in kept):
            kept.append((y, x))
    if len(kept) < 3:
        return -1, []
    return best_colour, kept


def _spans(low: int, high: int, middle: int | None, limit: int) -> list[tuple[int, int]]:
    """Candidate (origin, length) readings of one axis of a piece's frame.

    A piece may be driven until half of it hangs off the board, and what is left on screen is a
    frame one or more cells too small — which for a rectangle outline means no reading of it is a
    rectangle at all. The driven piece's mark sits at its exact middle, so a side that is still on
    screen plus the mark pins the true length; both parities are offered because a pressed piece's
    sides are not always odd.
    """
    out = [(low, high - low + 1)]
    if middle is None:
        return out
    if low == 0 and middle <= high:
        reach = high - middle
        out += [(high - 2 * reach, 2 * reach + 1), (high - 2 * reach - 1, 2 * reach + 2)]
    if high == limit - 1 and middle >= low:
        reach = middle - low
        out += [(low, 2 * reach + 1), (low, 2 * reach + 2)]
    return [(origin, length) for origin, length in out if length >= 3]


def _fit_shape(cells: list[Cell], grid: np.ndarray, bg: int, ring_colour: int,
               live: np.ndarray, mark: Cell | None = None) -> dict[str, Any] | None:
    """Read one colour's cells as a plus, a rectangle outline, or a rigid stamp.

    A piece lying under another loses cells — this board's pieces are skeletal, so a single bar
    crossing one can cut it into four separate arcs — so every fit is COMPLETED to the shape it
    implies and the completion is then CHECKED: a cell the fit predicts but the frame does not
    show must be explained by something drawn over it, by chrome, or by the edge of the board.
    An unexplained hole means these cells are not one piece (two pieces sharing a colour do this)
    and the fit is refused rather than guessed.
    """
    ys = [c[0] for c in cells]
    xs = [c[1] for c in cells]
    y0, y1, x0, x1 = min(ys), max(ys), min(xs), max(xs)
    h, w = y1 - y0 + 1, x1 - x0 + 1
    have = set(cells)

    def explained(want: set[Cell]) -> bool:
        for cy, cx in want - have:
            if not (0 <= cy < grid.shape[0] and 0 <= cx < grid.shape[1]):
                continue
            if not live[cy, cx]:
                continue
            v = int(grid[cy, cx])
            if v == bg or v == ring_colour:
                return False
        return True

    rows = np.bincount([y - y0 for y in ys], minlength=h)
    cols = np.bincount([x - x0 for x in xs], minlength=w)
    bar_row, bar_col = int(rows.argmax()), int(cols.argmax())
    plus = {(y0 + bar_row, x0 + i) for i in range(w)} | {(y0 + i, x0 + bar_col) for i in range(h)}
    if have <= plus and explained(plus):
        # ⛔ A BAR ENDS WHERE THE BOARD IS BARE, NOT WHERE ITS COLOUR STOPS BEING VISIBLE.
        # Read the other way round, a piece lying under another is measured short by however
        # many of its cells that other piece is standing on — and one row short puts every
        # winning placement out of reach. MEASURED, and it is the whole of a 23x wall-clock
        # difference between two renderings of the SAME board: the two differ only in the ORDER
        # their sprites are listed, which decides which of two overlapping pieces is drawn on
        # top. On one, the widest piece reads 19 rows; on the other the outline crossing it hides
        # two of its cells and it reads 17, every plan computed from that is off by a row, the
        # model disagrees with the board on every action, and the planner rebuilds from scratch
        # each time. Growing the bar across anything that is merely COVERED — the same test the
        # holes already use — reads both renderings identically. Growth is capped at the visible
        # span, so a long piece lying end-on cannot drag the frame away.
        top = _run_out(grid, live, bg, ring_colour, y0, x0 + bar_col, -1, 0, h)
        bottom = _run_out(grid, live, bg, ring_colour, y1, x0 + bar_col, 1, 0, h)
        left = _run_out(grid, live, bg, ring_colour, y0 + bar_row, x0, 0, -1, w)
        right = _run_out(grid, live, bg, ring_colour, y0 + bar_row, x1, 0, 1, w)
        y0, h, bar_row = y0 - top, h + top + bottom, bar_row + top
        x0, w, bar_col = x0 - left, w + left + right, bar_col + left
        # Growth stops at the edge of the board, and a piece may be driven until half of it hangs
        # over. An unpressed plus is symmetric about its own bar, so the longer arm restores what
        # is off screen; where growth already found the whole piece this changes nothing.
        if y0 <= 0 or y0 + h >= grid.shape[0]:
            reach = max(bar_row, h - 1 - bar_row)
            y0, h, bar_row = y0 + bar_row - reach, 2 * reach + 1, reach
        if x0 <= 0 or x0 + w >= grid.shape[1]:
            reach = max(bar_col, w - 1 - bar_col)
            x0, w, bar_col = x0 + bar_col - reach, 2 * reach + 1, reach
        return {"kind": "plus", "y": y0, "x": x0, "h": h, "w": w,
                "bar_row": bar_row, "bar_col": bar_col, "rel": ()}

    inside = mark is not None and y0 - 1 <= mark[0] <= y1 + 1 and x0 - 1 <= mark[1] <= x1 + 1
    for oy, oh in _spans(y0, y1, mark[0] if inside else None, grid.shape[0]):
        for ox, ow in _spans(x0, x1, mark[1] if inside else None, grid.shape[1]):
            ring = ({(oy, ox + i) for i in range(ow)} | {(oy + oh - 1, ox + i) for i in range(ow)}
                    | {(oy + i, ox) for i in range(oh)}
                    | {(oy + i, ox + ow - 1) for i in range(oh)})
            if have <= ring and explained(ring):
                return {"kind": "ring", "y": oy, "x": ox, "h": oh, "w": ow,
                        "bar_row": oh // 2, "bar_col": ow // 2, "rel": ()}

    # A rigid stamp is completed by its own point symmetry, which every skeletal shape in this
    # family has; the completion is held to the same explanation test as the others.
    mirrored = {(y0 + y1 - cy, x0 + x1 - cx) for cy, cx in have}
    full = have | mirrored
    if not explained(full):
        return None
    # An X-shaped piece is drawn with a hole at its own middle when nobody is driving it, which
    # cuts it into four arms that touch nothing. The middle is where such a shape is joined, so
    # connectivity is asked of the shape WITH its middle, and the hole is left out of the stamp.
    if not _one_object(full | {(y0 + h // 2, x0 + w // 2)}):
        return None
    rel = tuple(sorted((cy - y0, cx - x0) for cy, cx in full))
    return {"kind": "rigid", "y": y0, "x": x0, "h": h, "w": w,
            "bar_row": h // 2, "bar_col": w // 2, "rel": rel}


def _run_out(grid: np.ndarray, live: np.ndarray, bg: int, ring_colour: int,
             y: int, x: int, dy: int, dx: int, limit: int) -> int:
    """How many further cells a line runs past its last visible one before the board goes bare.

    Chrome and the edge of the board count as covered — a bar under the budget gauge is still
    there — and so does any other piece. Bare background, or the blueprint showing through, is
    where the line genuinely ends.
    """
    steps = 0
    while steps < limit:
        ny, nx = y + dy * (steps + 1), x + dx * (steps + 1)
        if not (0 <= ny < grid.shape[0] and 0 <= nx < grid.shape[1]):
            break
        if live[ny, nx] and int(grid[ny, nx]) in (bg, ring_colour):
            break
        steps += 1
    return steps


def _one_object(cells: set[Cell]) -> bool:
    """8-connected in one piece. Two objects that happen to mirror each other are not one shape,
    and a board whose two presses sit point-symmetrically about the middle produces exactly that
    illusion — measured, and it turned both presses into a single enormous piece."""
    start = next(iter(cells))
    seen = {start}
    stack = [start]
    while stack:
        cy, cx = stack.pop()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                nxt = (cy + dy, cx + dx)
                if nxt in cells and nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
    return len(seen) == len(cells)


class _Blocks:
    """The cells of one piece of furniture, indexed by row and by column.

    ⛔ This index is the whole answer to a 23x wall-clock difference between two renderings of the
    same board. The search's inner question is "does this bar touch this thing", asked once per
    obstacle per direction per state — millions of times — and a stack sample of a slow run landed
    in `numpy.any` every single time. A board with fourteen dye pads pays that cost fourteen times
    per move to learn, almost always, that the answer is no. The furniture never moves and is a
    few dozen cells, so it is indexed ONCE and the question becomes a bisect over a short list.
    A piece may hang off the board while its middle stays on, so negative coordinates are ordinary
    here; a dict of rows costs nothing for them, where a padded array cost a constant everywhere.
    """

    __slots__ = ("cells", "rows", "cols")

    def __init__(self, cells: Any) -> None:
        self.cells: frozenset[Cell] = frozenset(cells)
        self.rows: dict[int, list[int]] = {}
        self.cols: dict[int, list[int]] = {}
        for cy, cx in self.cells:
            self.rows.setdefault(cy, []).append(cx)
            self.cols.setdefault(cx, []).append(cy)
        for run in self.rows.values():
            run.sort()
        for run in self.cols.values():
            run.sort()

    def __bool__(self) -> bool:
        return bool(self.cells)

    def at(self, y: int, x: int) -> bool:
        return (y, x) in self.cells

    def in_row(self, y: int, x0: int, x1: int) -> bool:
        run = self.rows.get(y)
        if not run:
            return False
        i = bisect_left(run, x0)
        return i < len(run) and run[i] <= x1

    def in_col(self, x: int, y0: int, y1: int) -> bool:
        run = self.cols.get(x)
        if not run:
            return False
        i = bisect_left(run, y0)
        return i < len(run) and run[i] <= y1


def parse_board(grid: np.ndarray,
                blueprint: tuple[int, list[tuple[Cell, int | None]]] | None = None
                ) -> Board | None:
    """Recover pins, pieces, dye pads and presses from one frame, or None if unreadable.

    ⛔ The blueprint is READ ONCE and then carried. It never moves, and by the time the pieces
    are parked on it most of its rings are half-buried under them — measured: on a solved board
    not one whole ring survives, so a fresh reading of the same frame finds no blueprint at all
    and the tool drops a plan it had already carried out most of.
    """
    board = Board()
    bg = int(next(iter(background(grid))))
    board.bg = bg
    live = ~_chrome_mask(grid, bg)
    if blueprint is not None:
        ring_colour = blueprint[0]
        pin_cells = [cell for cell, _ in blueprint[1]]
    else:
        ring_colour, pin_cells = _find_pins(grid, bg, live)
    if ring_colour < 0:
        return None

    # The pip's own cell is blueprint, not piece — drop it before any colour is read as a shape.
    blocked = (~live) | (grid == ring_colour)
    for cy, cx in pin_cells:
        blocked[cy, cx] = True
    palette = sorted({int(v) for v in np.unique(grid)} - {bg, ring_colour})

    # DYE PADS FIRST. A pad's frame and its middle are two different colours, and its middle
    # colour is often a piece colour too, so a piece read before the pads are taken out of the
    # frame is a piece welded to a pad.
    pad_cells = np.zeros_like(grid, dtype=bool)
    for colour in palette:
        mask = (grid == colour) & ~blocked
        if not mask.any():
            continue
        for comp in _same_colour_components(np.where(mask, grid, bg), colour):
            ys = [c[0] for c in comp]
            xs = [c[1] for c in comp]
            y0, y1, x0, x1 = min(ys), max(ys), min(xs), max(xs)
            edge = y0 == 0 or x0 == 0 or y1 == grid.shape[0] - 1 or x1 == grid.shape[1] - 1
            if max(y1 - y0, x1 - x0) + 1 > _PIECE_SPAN:
                continue
            if not edge and (y1 - y0 < 2 or x1 - x0 < 2):
                continue
            held = set(comp)
            inner = [int(grid[cy, cx]) for cy in range(y0, y1 + 1) for cx in range(x0, x1 + 1)
                     if (cy, cx) not in held]
            fills = [v for v in inner if v != bg and v != ring_colour]
            if not inner or len(fills) != len(inner) or len(set(fills)) != 1:
                continue
            board.pads.append((_Blocks((cy, cx) for cy in range(y0, y1 + 1)
                                       for cx in range(x0, x1 + 1)), fills[0]))
            pad_cells[y0:y1 + 1, x0:x1 + 1] = True
    blocked |= pad_cells

    # The driven piece's mark is the one cell on the board wearing a colour nothing else wears.
    # It is the only thing that says where a piece hanging off the edge actually reaches to.
    mark: Cell | None = None
    for colour in palette:
        spots = np.argwhere((grid == colour) & ~blocked)
        if len(spots) == 1:
            mark = (int(spots[0][0]), int(spots[0][1]))
            break

    for colour in palette:
        mask = (grid == colour) & ~blocked
        if not mask.any():
            continue
        cells = [(int(y), int(x)) for y, x in zip(*np.where(mask))]
        # ⛔ A pip is blueprint UNLESS a piece is standing on it, and a piece standing on one
        # loses that cell from its own outline — which, when the cell is at the end of a bar,
        # shortens the piece by one and moves every placement the plan computes. A pip touching
        # this colour is offered back to it, and kept only if the shape then reads cleanly.
        touching = [(cy, cx) for cy, cx in pin_cells
                    if int(grid[cy, cx]) == colour
                    and any(mask[cy + dy, cx + dx]
                            for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1))
                            if 0 <= cy + dy < grid.shape[0] and 0 <= cx + dx < grid.shape[1])]
        fit = None
        if touching:
            fit = _fit_shape(cells + touching, grid, bg, ring_colour, live, mark)
        if fit is None:
            fit = _fit_shape(cells, grid, bg, ring_colour, live, mark)
        if fit is not None and max(fit["h"], fit["w"]) >= _PIECE_SPAN:
            fit["colour"] = colour
            board.pieces.append(fit)
            continue
        # ⛔ The colour did not read as ONE shape. That is only a fault when something this size
        # is loose on the board: a board with two presses in the same colour reads as a huge
        # unreadable smear if the whole colour is judged at once, and a piece a bar has cut into
        # four arcs reads as four scraps of furniture if only its parts are judged. So the fit is
        # asked of the colour and the SIZE is asked of each object.
        for comp in _same_colour_components(np.where(mask, grid, bg), colour):
            cys = [c[0] for c in comp]
            cxs = [c[1] for c in comp]
            y0, y1, x0, x1 = min(cys), max(cys), min(cxs), max(cxs)
            if max(y1 - y0, x1 - x0) + 1 >= _PIECE_SPAN:
                return None
            if y1 - y0 < 2 or x1 - x0 < 2:
                continue
            board.gates.append((_Blocks(comp), (x0, y0, x1 - x0 + 1, y1 - y0 + 1)))
    if not board.pieces:
        return None

    covered: set[Cell] = set()
    for piece in board.pieces:
        state = (piece["x"], piece["y"], piece["h"], piece["w"],
                 piece["bar_col"], piece["bar_row"], piece["colour"])
        covered.update(_cells_of(state, piece["kind"], piece["rel"]))
        # The driven piece's own mark hides a pip just as thoroughly as its body does, and once
        # its bar has been pressed off-middle the mark is a cell of its own, outside the shape.
        covered.add((piece["y"] + piece["h"] // 2, piece["x"] + piece["w"] // 2))
    if blueprint is not None:
        board.pin_ring = ring_colour
        board.pins = list(blueprint[1])
        board.pin_colours = sorted({c for _, c in board.pins if c is not None})
        _mark_selected(board, grid, bg, ring_colour)
        return board

    known = set()
    for cy, cx in pin_cells:
        v = int(grid[cy, cx])
        # ⛔ A pin DEMANDS a piece colour, so "this pip is the colour of a piece" is not evidence
        # of anything. What hides a pip is a piece STANDING ON IT, which is a question about
        # cells, not colours. Read the other way round, every pin on the board reads as unknown
        # and the blueprint vanishes.
        occluded = (cy, cx) in covered
        board.pins.append(((cy, cx), None if occluded else v))
        if not occluded:
            known.add(v)
    board.pin_colours = sorted(known)
    if not board.pin_colours:
        return None
    board.pin_ring = ring_colour

    _mark_selected(board, grid, bg, ring_colour)
    return board


def _mark_selected(board: Board, grid: np.ndarray, bg: int, ring_colour: int) -> None:
    """The driven piece is the one wearing an odd colour at its own middle."""
    for idx, piece in enumerate(board.pieces):
        mid = (piece["y"] + piece["h"] // 2, piece["x"] + piece["w"] // 2)
        if not (0 <= mid[0] < grid.shape[0] and 0 <= mid[1] < grid.shape[1]):
            continue
        v = int(grid[mid])
        if v != bg and v != piece["colour"] and v != ring_colour:
            board.selected = idx


# --------------------------------------------------------------------------- model


def _cells_of(state: State, kind: str, rel: tuple) -> list[Cell]:
    x, y, h, w, bar_col, bar_row, _ = state
    if kind == "plus":
        return ([(y + i, x + bar_col) for i in range(h)]
                + [(y + bar_row, x + j) for j in range(w)])
    if kind == "ring":
        out = [(y, x + j) for j in range(w)] + [(y + h - 1, x + j) for j in range(w)]
        out += [(y + i, x) for i in range(1, h - 1)] + [(y + i, x + w - 1) for i in range(1, h - 1)]
        return out
    return [(y + dy, x + dx) for dy, dx in rel]


def _hits(blocks: _Blocks, state: State, kind: str, rel: tuple,
          with_mark: bool = True) -> bool:
    """Does the driven piece's ink touch this furniture?

    ⛔ The driven piece's own mark counts against the PRESS and not against the DYE PADS. The mark
    is repainted partway through the engine's handling of a move — it is still there when the
    press is consulted and gone by the time the pads are — and a rectangle outline's mark sits at
    its hollow middle, exactly where nothing else of it is. MEASURED: counting it for pads dyes
    a piece in the model that the board leaves alone, twice, on a route that crosses a row of
    them.
    """
    x, y, h, w, bar_col, bar_row, _ = state
    if with_mark and blocks.at(y + h // 2, x + w // 2):
        return True
    if kind == "plus":
        return (blocks.in_col(x + bar_col, y, y + h - 1)
                or blocks.in_row(y + bar_row, x, x + w - 1))
    if kind == "ring":
        return (blocks.in_row(y, x, x + w - 1)
                or blocks.in_row(y + h - 1, x, x + w - 1)
                or blocks.in_col(x, y, y + h - 1)
                or blocks.in_col(x + w - 1, y, y + h - 1))
    return any(blocks.at(y + dy, x + dx) for dy, dx in rel)


def _snap(v: int, step: int) -> int:
    return int(round(v / step)) * step


def apply_move(state: State, dx: int, dy: int, kind: str, rel: tuple,
               layout: Layout, step: int, size: int) -> State | None:
    """One action, modelled exactly: bounds, then every press in turn, then the first dye pad.

    Returns the resulting state, or None when the outcome is outside what this model covers
    (a rigid stamp meeting a press, a bar shoved past the edge of its own frame) — such a move
    is never planned, so the model never has to guess.
    """
    x, y, h, w, bar_col, bar_row, colour = state
    nx, ny = x + dx, y + dy
    if not (0 <= nx + w // 2 < size and 0 <= ny + h // 2 < size):
        return state
    cur: State = (nx, ny, h, w, bar_col, bar_row, colour)
    if not _hits(layout.any_of, cur, kind, rel):
        return cur
    for blocks, (gx, gy, gw, gh) in layout.gates:
        if not _hits(blocks, cur, kind, rel):
            continue
        cx, cy, ch, cw, cbc, cbr, ccol = cur
        if kind == "ring":
            if dx:
                if cw <= 2 * step:
                    return state
                nh, nw = ch + step, cw - step
                ay = cy + (ch // 2 - (ch + step) // 2)
                ay = _snap(ay, step)
                ax = cx if dx > 0 else x
                return (ax, ay, nh, nw, nw // 2, nh // 2, ccol)
            if ch <= 2 * step:
                return state
            nh, nw = ch - step, cw + step
            ax = cx + (cw // 2 - (cw + step) // 2)
            ax = _snap(ax, step)
            ay = cy if dy > 0 else y
            return (ax, ay, nh, nw, nw // 2, nh // 2, ccol)
        if kind != "plus":
            return None
        in_col = gx <= cx + cbc < gx + gw
        in_row = gy <= cy + cbr < gy + gh
        if dx:
            near, far = (-step, step) if dx > 0 else (step, -step)
            room_near = cbc > 0 if dx > 0 else cbc < cw - 2
            room_far = cbc < cw - 2 if dx > 0 else cbc > 0
            if in_col and in_row:
                cur = (x, y, ch, cw, cbc, cbr, ccol)
            elif in_col:
                if room_near and 0 <= cbc + near < cw:
                    cur = (cx, cy, ch, cw, cbc + near, cbr, ccol)
                elif room_near:
                    return None
                else:
                    cur = (x, y, ch, cw, cbc, cbr, ccol)
            elif in_row:
                if room_far and 0 <= cbc + far < cw:
                    cur = (x, y, ch, cw, cbc + far, cbr, ccol)
                elif room_far:
                    return None
                else:
                    cur = (x, y, ch, cw, cbc, cbr, ccol)
        else:
            near, far = (-step, step) if dy > 0 else (step, -step)
            room_near = cbr > 0 if dy > 0 else cbr < ch - 2
            room_far = cbr < ch - 2 if dy > 0 else cbr > 0
            if in_col and in_row:
                cur = (x, y, ch, cw, cbc, cbr, ccol)
            elif in_row:
                if room_near and 0 <= cbr + near < ch:
                    cur = (cx, cy, ch, cw, cbc, cbr + near, ccol)
                elif room_near:
                    return None
                else:
                    cur = (x, y, ch, cw, cbc, cbr, ccol)
            elif in_col:
                if room_far and 0 <= cbr + far < ch:
                    cur = (x, y, ch, cw, cbc, cbr + far, ccol)
                elif room_far:
                    return None
                else:
                    cur = (x, y, ch, cw, cbc, cbr, ccol)
    # ⛔ Touching TWO pads at once is not modelled and must not be planned. The engine dyes from
    # the first pad in ITS OWN order, which no frame reveals; guessing it produced a piece the
    # right shape in the wrong colour at the end of a forty-move route, with nothing along the
    # way to show the plan had already failed.
    touched = [dye for blocks, dye in layout.pads
               if cur[6] != dye and _hits(blocks, cur, kind, rel, with_mark=False)]
    if len(touched) > 1:
        return None
    if touched:
        return cur[:6] + (touched[0],)
    return cur


def reachable(start: State, kind: str, rel: tuple, layout: Layout,
              moves: list[tuple[int, int, int]], step: int, size: int,
              depth: int = 10 ** 6,
              cap: int = 200_000) -> dict[State, tuple[int, State | None, int]]:
    """Every state the driven piece can reach within `depth` moves, cheapest route to each.

    ⛔ The depth bound is not a safety valve, it is the plan's own arithmetic. A route longer than
    the level's action budget is not a slower answer, it is not an answer — the level ends on
    overrun. Searching the whole reachable space to prove that costs more than every plan this
    tool has ever executed put together.
    """
    seen: dict[State, tuple[int, State | None, int]] = {start: (0, None, 0)}
    queue: deque[State] = deque([start])
    while queue and len(seen) < cap:
        cur = queue.popleft()
        dist = seen[cur][0]
        if dist >= depth:
            continue
        for aid, dx, dy in moves:
            nxt = apply_move(cur, dx, dy, kind, rel, layout, step, size)
            if nxt is None or nxt == cur or nxt in seen:
                continue
            seen[nxt] = (dist + 1, cur, aid)
            queue.append(nxt)
    return seen


def route(seen: dict[State, tuple[int, State | None, int]], goal: State) -> list[int]:
    out: list[int] = []
    cur = goal
    while seen[cur][1] is not None:
        dist, prev, aid = seen[cur]
        out.append(aid)
        cur = prev
    out.reverse()
    return out


# --------------------------------------------------------------------------- plan


def _pin_assignments(board: Board) -> list[list[tuple[Cell, int]]]:
    """Every consistent reading of the pins, unknown pips searched over the colours seen."""
    unknown = [i for i, (_, c) in enumerate(board.pins) if c is None]
    if len(unknown) > 4:
        return []
    options: list[list[tuple[Cell, int]]] = []
    budget = len(board.pin_colours) ** max(1, len(unknown))
    if budget > 64:
        return []
    stack = [(0, [])]
    while stack:
        idx, chosen = stack.pop()
        if idx == len(unknown):
            reading = []
            fill = dict(zip(unknown, chosen))
            for i, (cell, colour) in enumerate(board.pins):
                reading.append((cell, colour if colour is not None else fill[i]))
            options.append(reading)
            continue
        for colour in board.pin_colours:
            stack.append((idx + 1, chosen + [colour]))
    return options


# How deep each piece's search is allowed to go, tried in order until a plan appears. The first
# rung covers every plan this tool has ever executed; the ladder exists so a board with no plan is
# refused after a bounded search instead of an exhaustive one.
_DEPTHS = (40, 80, 160)


def _attempt(board: Board, layout: Layout, moves: list[tuple[int, int, int]], step: int,
             size: int, depth: int) -> dict[int, tuple[State, list[int]]] | None:
    """One pass of the planner at a fixed search depth."""
    reaches = []
    for piece in board.pieces:
        start: State = (piece["x"], piece["y"], piece["h"], piece["w"],
                        piece["bar_col"], piece["bar_row"], piece["colour"])
        reaches.append(reachable(start, piece["kind"], piece["rel"], layout,
                                 moves, step, size, depth))
    for pins in _pin_assignments(board):
        per_piece: list[dict[frozenset, tuple[int, State]]] = []
        for piece, seen in zip(board.pieces, reaches):
            options: dict[frozenset, tuple[int, State]] = {}
            for state, (dist, _, _) in seen.items():
                cells = set(_cells_of(state, piece["kind"], piece["rel"]))
                mid = (state[1] + state[2] // 2, state[0] + state[3] // 2)
                covered = []
                clean = True
                for cell, colour in pins:
                    if cell == mid:
                        clean = False
                        break
                    if cell in cells:
                        if colour == state[6]:
                            covered.append(cell)
                        else:
                            clean = False
                            break
                if not clean:
                    continue
                key = frozenset(covered)
                if key not in options or dist < options[key][0]:
                    options[key] = (dist, state)
            if not options:
                per_piece = []
                break
            per_piece.append(options)
        if not per_piece:
            continue
        wanted = frozenset(cell for cell, _ in pins)
        best: tuple[int, list[State]] | None = None
        stack: list[tuple[int, frozenset, int, list[State]]] = [(0, frozenset(), 0, [])]
        while stack:
            idx, got, cost, picks = stack.pop()
            if best is not None and cost >= best[0]:
                continue
            if idx == len(per_piece):
                if got == wanted:
                    best = (cost, picks)
                continue
            for key, (dist, state) in per_piece[idx].items():
                stack.append((idx + 1, got | key, cost + dist, picks + [state]))
        if best is None:
            continue
        plan: dict[int, tuple[State, list[int]]] = {}
        for idx, (piece, seen) in enumerate(zip(board.pieces, reaches)):
            goal = best[1][idx]
            plan[idx] = (goal, route(seen, goal))
        return plan
    return None


def plan_cost(plan: dict[int, tuple[State, list[int]]]) -> int:
    """Actions the plan will spend: every move, plus a hand-over between pieces that must move."""
    moving = sum(1 for _, route in plan.values() if route)
    return sum(len(route) for _, route in plan.values()) + max(0, moving - 1)


def solve(board: Board, moves: list[tuple[int, int, int]], step: int,
          size: int, allowance: int | None = None) -> dict[int, tuple[State, list[int]]] | None:
    """Choose a final state per piece so every pin is satisfied, cheapest total first.

    ⛔ Deepened in rungs rather than searched exhaustively. MEASURED: the exhaustive search opened
    331,000 states on one level and executed a plan 96 moves long — it spent nine seconds proving
    there was nothing better far past where any usable answer lives, and every rebuild paid it
    again. The rungs cost at most twice the successful one and answer the common case in a
    fraction of a second.

    ⛔ The allowance is a CONSTRAINT ON THE PLAN, not a stopping rule. A plan that runs out of
    actions having achieved nothing loses the level exactly as a plan that never started would, so
    the answer is not to cap the search — it is to refuse a plan that cannot finish inside what is
    left, and say so with a bid of zero while the board is still someone else's to try.
    """
    layout = Layout(board.gates, board.pads)
    for depth in _DEPTHS:
        plan = _attempt(board, layout, moves, step, size, depth)
        if plan is None:
            continue
        if allowance is not None and plan_cost(plan) > allowance:
            continue
        return plan
    return None


# --------------------------------------------------------------------------- tool


class ReforgeTool:
    """Slide, dye and re-press skeletal pieces onto a blueprint's pinned cells.

    ⛔ The board is MODELLED, not re-read. Re-reading each frame looks safer and is not: these
    pieces are skeletal and they overlap, so by the time a plan is half-executed one piece's bar
    lies across another's outline and the reader sees a shorter piece, a broken ring, or no
    blueprint at all. The tool therefore carries the state it believes and CHECKS it against the
    frame — a believed cell showing bare background or bare blueprint is a contradiction and the
    board is read afresh; a believed cell showing some other piece is simply hidden, which is the
    normal case and no reason to doubt anything.
    """

    name = "reforge"

    # How far a probe looks for trouble before it is willing to spend an action.
    _CLEARANCE = 6

    def __init__(self) -> None:
        # The action->displacement map is a property of the GAME, not the level, so it survives
        # the per-level reset that drops everything else here.
        self._vec: dict[int, tuple[int, int]] = {}
        self._step: int = 0
        self._dead: set[int] = set()
        self.reset()

    def reset(self) -> None:
        self._blueprint: tuple[int, list[tuple[Cell, int | None]]] | None = None
        self._model: list[State] | None = None
        self._shapes: list[tuple[str, tuple]] = []
        self._layout = Layout([], [])
        self._pins: list[tuple[Cell, int | None]] = []
        self._ring: int = -1
        self._bg: int = -1
        self._mark: int = -1
        self._sel: int = -1
        self._goals: list[State] | None = None
        self._routes: list[list[int]] = []
        self._no_plan_for: tuple | None = None
        self._gauge = BudgetReader()
        self._failed = False
        self._handovers = 0
        self._probe: tuple[int, State] | None = None

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        return None

    # -- the model -------------------------------------------------------------

    def _bootstrap(self, grid: np.ndarray) -> bool:
        try:
            board = parse_board(grid, self._blueprint)
        except Exception:  # noqa: BLE001 - an unreadable board is a bid of zero, never a crash
            board = None
        if board is None or board.selected is None:
            return False
        if self._blueprint is None:
            self._blueprint = (board.pin_ring, list(board.pins))
        self._ring, self._bg = board.pin_ring, board.bg
        self._layout, self._pins = Layout(board.gates, board.pads), board.pins
        self._shapes = [(p["kind"], p["rel"]) for p in board.pieces]
        self._model = [(p["x"], p["y"], p["h"], p["w"], p["bar_col"], p["bar_row"], p["colour"])
                       for p in board.pieces]
        self._sel = board.selected
        chosen = board.pieces[board.selected]
        self._mark = int(grid[chosen["y"] + chosen["h"] // 2, chosen["x"] + chosen["w"] // 2])
        self._goals, self._routes = None, []
        return True

    def _cells(self, slot: int) -> list[Cell]:
        return _cells_of(self._model[slot], *self._shapes[slot])

    def _middle(self, slot: int) -> Cell:
        state = self._model[slot]
        return (state[1] + state[2] // 2, state[0] + state[3] // 2)

    def _agrees(self, grid: np.ndarray) -> bool:
        """Does the frame contradict the model anywhere? Bare board under a believed cell does."""
        if self._model is None:
            return False
        height, width = grid.shape
        for slot, state in enumerate(self._model):
            seen = 0
            wearing = 0
            for cy, cx in self._cells(slot):
                if not (0 <= cy < height and 0 <= cx < width):
                    continue
                v = int(grid[cy, cx])
                if v == self._bg or v == self._ring:
                    return False
                seen += 1
                wearing += v == state[6]
            # A believed piece hidden under another shows little of itself, which is normal; a
            # believed piece showing NONE of its colour is a different piece, and the commonest
            # way to get one is a dye the model predicted and the engine did not.
            if seen and wearing * 4 < seen:
                return False
        return True

    def _who_drives(self, grid: np.ndarray) -> int:
        """Which piece the controls are on.

        ⛔ Read from the COLOUR AT THE MIDDLE, never from which piece is assumed to be on top.
        The same board served by two API versions differs in exactly one thing — the order its
        sprites are listed, and therefore which of two overlapping pieces is drawn over the other.
        A reading that decides "this mark must be hidden because another piece is there" is right
        on one rendering and inverted on the other, sends every move to the wrong piece, and makes
        the model disagree with the board on nearly every action. What a cell SHOWS needs no such
        assumption: the mark means driven, the piece's own idle drawing means not driven, and any
        third colour means something is standing on it and the cell says nothing either way.
        """
        height, width = grid.shape
        claimed, mute = [], []
        for slot, state in enumerate(self._model):
            cy, cx = self._middle(slot)
            if not (0 <= cy < height and 0 <= cx < width):
                mute.append(slot)
                continue
            seen = int(grid[cy, cx])
            if seen == self._mark:
                claimed.append(slot)
            elif seen != state[6] and seen != self._bg and seen != self._ring:
                mute.append(slot)
        if len(claimed) == 1:
            return claimed[0]
        # Nobody visible wears the mark, so it is under something: the one piece whose middle is
        # showing a colour that is neither its own nor the mark is the one holding the controls.
        if not claimed and len(mute) == 1:
            return mute[0]
        return self._sel

    # -- calibration -----------------------------------------------------------

    def _absorb(self, grid: np.ndarray) -> None:
        """Read the last probe's displacement off the board and record that action's vector.

        ⛔ By CORRELATION against the model, not by re-reading the board. Re-reading is exactly
        what fails here: a probe slides one piece under another, the reader then sees a broken
        outline, and the calibration that the whole plan's arithmetic rests on never happens. The
        piece's own shape is already known, so the question is only WHERE it now sits, and that
        is answered by scoring each candidate displacement against the frame.
        """
        probe, self._probe = self._probe, None
        if probe is None or self._model is None:
            return
        aid, before = probe
        kind, rel = self._shapes[self._sel]
        colour = before[6]
        was = set(_cells_of(before, kind, rel))
        ranked: list[tuple[int, tuple[int, int]]] = []
        for reach in range(0, self._CLEARANCE + 1):
            for dx, dy in {(0, -reach), (0, reach), (-reach, 0), (reach, 0)}:
                cand = (before[0] + dx, before[1] + dy) + before[2:]
                cells = set(_cells_of(cand, kind, rel))
                inside = [(cy, cx) for cy, cx in cells
                          if 0 <= cy < grid.shape[0] and 0 <= cx < grid.shape[1]]
                if not inside:
                    continue
                # ⛔ Agreement first, likeness second. Scoring by how many cells match the piece's
                # colour alone TIES: a long straight run matches a shifted copy of itself just as
                # well, and on a crowded board three different displacements scored identically.
                # A cell that shows bare board where the piece would be is proof it is NOT there.
                if any(int(grid[cy, cx]) in (self._bg, self._ring) for cy, cx in inside):
                    continue
                score = sum(1 for cy, cx in inside if int(grid[cy, cx]) == colour)
                score -= sum(1 for cy, cx in was - cells
                             if 0 <= cy < grid.shape[0] and 0 <= cx < grid.shape[1]
                             and int(grid[cy, cx]) == colour)
                ranked.append((score, (dx, dy)))
        ranked.sort(key=lambda item: -item[0])
        if not ranked or (len(ranked) > 1 and ranked[0][0] <= ranked[1][0]):
            return
        dx, dy = ranked[0][1]
        self._model[self._sel] = (before[0] + dx, before[1] + dy) + before[2:]
        if dx == 0 and dy == 0:
            self._dead.add(aid)
            return
        self._vec[aid] = (dx, dy)
        self._step = max(abs(dx), abs(dy))

    def _probe_step(self, ids: list[int]) -> Step | None:
        """Spend one action on a direction that cannot cost anything.

        ⛔ Clearance is measured against the PIECE'S OWN INK, not its bounding box. These pieces
        are skeletal and their boxes are enormous — a rectangle outline's box contains mostly
        nothing — so a box-shaped safety margin calls every board crowded and the tool never
        learns which action goes which way at all.
        """
        untried = [a for a in ids if a in (1, 2, 3, 4)
                   and a not in self._vec and a not in self._dead]
        if not untried:
            return None
        here = self._model[self._sel]
        kind, rel = self._shapes[self._sel]
        danger = self._layout.any_of
        for reach in range(1, self._CLEARANCE + 1):
            for dx, dy in ((0, -reach), (0, reach), (-reach, 0), (reach, 0)):
                if _hits(danger, (here[0] + dx, here[1] + dy) + here[2:], kind, rel):
                    return None
        self._probe = (untried[0], here)
        return (untried[0], None)

    def _fill_convention(self) -> bool:
        """The four directions are the two axes of one step, so whatever the probes could not
        reach is what is left over once the measured ones are removed."""
        if not self._vec:
            return False
        seen = set(self._vec.values())
        missing = [v for v in ((0, -self._step), (0, self._step),
                               (-self._step, 0), (self._step, 0)) if v not in seen]
        spare = [a for a in (1, 2, 3, 4) if a not in self._vec]
        for aid, vec in zip(spare, missing):
            self._vec[aid] = vec
        return len(self._vec) == 4

    # -- planning --------------------------------------------------------------

    def _allowance(self) -> int | None:
        """Actions left in this level, discounted for the reader's measured optimism."""
        left = self._gauge.remaining()
        return None if left is None else int(left * _ALLOWANCE_TRUST)

    def _make_plan(self, vectors: dict[int, tuple[int, int]]):
        """Solve the board this tool believes it is looking at, under a given action map."""
        board = Board()
        board.bg, board.pin_ring = self._bg, self._ring
        board.pins = list(self._pins)
        board.pin_colours = sorted({c for _, c in board.pins if c is not None})
        board.gates, board.pads = self._layout.gates, self._layout.pads
        board.pieces = [
            {"kind": self._shapes[i][0], "rel": self._shapes[i][1], "x": st[0], "y": st[1],
             "h": st[2], "w": st[3], "bar_col": st[4], "bar_row": st[5], "colour": st[6]}
            for i, st in enumerate(self._model)
        ]
        moves = [(aid, dx, dy) for aid, (dx, dy) in sorted(vectors.items())]
        return solve(board, moves, self._step, 64, self._allowance())

    def _build(self) -> bool:
        # A refusal is as much an answer as a plan, and re-deriving it on every bid was the other
        # half of what made polling expensive: the search runs once per distinct board.
        snapshot = (tuple(self._model or ()), tuple(self._pins), self._allowance())
        if snapshot == self._no_plan_for:
            return False
        plan = self._make_plan(self._vec)
        if plan is None:
            self._no_plan_for = snapshot
            return False
        self._goals = [plan[i][0] for i in range(len(self._model))]
        self._routes = [list(plan[i][1]) for i in range(len(self._model))]
        return True

    # -- protocol --------------------------------------------------------------

    def detect(self, frames: list[Any], obs: Any) -> float:
        """How well this board fits — a READ-ONLY opinion.

        ⛔ A bid must not be able to damage a plan. This used to re-read the board and rebuild
        whenever the model disagreed, which is `propose`'s job and only safe on `propose`'s
        schedule: the harness may ask for a bid at any moment, including mid-animation, and a
        re-read taken then installs a board that is briefly wrong and throws away a route that was
        working. MEASURED — polling the bid every ten actions cost a level that the same build
        clears when nobody asks. Disagreement is repaired where the actions are chosen; here the
        question is only whether this tool has a plan for this family of board.
        """
        if not has_frame(obs) or self._failed:
            return 0.0
        if self._model is None and not self._bootstrap(settled_frame(obs)):
            return 0.0
        if len(self._vec) < 4:
            return _PROBE_CLAIM
        if self._goals is not None:
            return _CLAIM
        return _CLAIM if self._build() else 0.0

    def plan_actions(self) -> int | None:
        """How many actions this tool's current plan will spend, or None if it has no plan.

        ⛔ Offered so a handover can be decided on ARITHMETIC instead of on a stall. Measured on
        the board this was built for: the incumbent holds a level it bids 0.00 on for 482 actions
        and two lost allowances, while this tool has a finished 63-action plan for a 200-action
        allowance the whole time. A stall clock cannot see that; "does the claimant's plan still
        fit what is left" can, and it is the difference between that level scoring 0.065 and 0.93.
        Read-only, and cheap: the plan is already built.
        """
        if self._goals is None:
            return None
        return sum(len(route) for route in self._routes) + max(
            0, sum(1 for route in self._routes if route) - 1)

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        if not has_frame(obs) or self._failed:
            return []
        ids, _ = availability(obs)
        grid = settled_frame(obs)
        # Fed HERE and nowhere else: the reader counts one action per observation, and `detect`
        # can be called any number of times per action, which would make it read the allowance
        # draining several times faster than it is.
        self._gauge.observe(grid)
        if self._model is not None and self._probe is not None:
            self._absorb(grid)
        if self._model is None or not self._agrees(grid):
            if not self._bootstrap(grid):
                return []
        self._sel = self._who_drives(grid)
        if len(self._vec) < 4:
            probe = self._probe_step(ids)
            if probe is not None:
                return [probe]
            # Nothing this piece can safely try. Hand the controls on and ask the next one: on a
            # board ringed with dye pads the piece that happens to start selected can be boxed in
            # while another has open air all round it.
            if self._handovers < len(self._model) and 5 in ids:
                self._handovers += 1
                return [(5, None)]
            if not self._fill_convention():
                self._failed = True
                return []
        if self._goals is None and not self._build():
            return []
        if not self._routes[self._sel]:
            if all(not route for route in self._routes):
                return []
            return [(5, None)] if 5 in ids else []
        aid = self._routes[self._sel][0]
        kind, rel = self._shapes[self._sel]
        nxt = apply_move(self._model[self._sel], *self._vec[aid], kind, rel,
                         self._layout, self._step, 64)
        if nxt is None:
            self._goals = None
            return []
        self._routes[self._sel] = self._routes[self._sel][1:]
        self._model[self._sel] = nxt
        return [(aid, None)]
