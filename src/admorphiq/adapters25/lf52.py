"""script25 quarantined adapter: LF52 (peg-solitaire jump-and-capture).

*** QUARANTINE — MODEL-NEVER-VISIBLE. See admorphiq.adapters25's package
docstring. ***

**Mechanic — CORRECTED (2026-07-16, R56b park FALSIFIED by faithful live
reads).** The prior bank claimed LF52's ACTION6 click was an
"input-position-INDEPENDENT side-effect animation" with "no positional
operator to plan over", and banked 0/10 as unclearable. That was a probe
artifact: on level 1 an empty-space click triggers a fixed tutorial-hint
blink (``sgxkqallyv`` -> ``bhdfjlqapap``) at a game-determined spot, so a
sweep that clicks arbitrary cells sees the SAME growth regardless of where it
clicked — and mistakes the hint for the game response. Reading the source
(``dghsidbuet`` click dispatch) and driving the REAL env loop shows the true
mechanic:

- **LF52 is PEG SOLITAIRE.** ACTION6 hit-tests the clicked cell:
  clicking a PIECE (``fozwvlovdui``) SELECTS it (``xpcuvjyrgu`` attaches a
  direction arrow for each legal jump); clicking a legal LANDING cell fires
  the jump (``cfilhtifcb``) — the piece hops two cells over an adjacent piece,
  which is CAPTURED and removed. A jump ``P -> P+2d`` is legal iff ``P+d``
  holds a piece and ``P+2d`` is an empty board slot. WIN fires when the board
  is reduced to ONE piece (``tdcblgbfxw`` -> ``win()``; levels 6/7 win at two).
  The per-level ACTION-COUNT budget (``asqvqzpfdi`` vs 64 / 64*5 / 64*10) is
  the LOSE gate. ACTION1-4 shift walls on some deep levels; peg solitaire needs
  ONLY ACTION6 clicks.
- **Board is frame-parseable**: on a 6-pixel lattice, PIECES are one colour
  (14 on L0) at size ~12, board SLOTS another colour (1 on L0) at size ~16.
  A slot with no piece on it is an empty hole a jump can land in.

**Live verification (faithful passive read, 2026-07-16)**: driving the real
``env.step`` loop with 8 ACTION6 clicks (4 jumps: select piece, click landing
cell) on L0's 5-piece line ``(1,2)(2,2)(4,2)(5,3)(5,5)`` advanced
``levels_completed`` 0 -> 1. So the click IS positional and controllable; the
park's "unclearable" verdict is wrong.

**Method — faithful offline simulator + DFS** (the sb26/sk48 pattern,
[[../lessons/faithful_offline_simulator_20260715]]): parse the visible board
into (pieces, cells) lattice sets, DFS the jump graph offline for a sequence
reducing to one piece, then replay it — two clicks per jump (piece centroid,
then landing centroid). No engine internals at runtime; pieces/slots/lattice
all come from :func:`admorphiq.kernels.find_regions`.

**Scope / honest limits (banked deeper levels)**: the reduce-to-one model
clears levels whose full board is on-screen with a monochrome piece set. Deep
levels add board scrolling (camera pans off-screen pieces into view on
reaching per-level target cells), coloured red/blue pieces with pairing
constraints, and the two-piece win — those parse partially and are banked, not
forced. The generic simulator here is the first LF52 clear path; extending it
to the scroll/colour levels is the reopen pointer.

Composition from ``admorphiq.kernels``: find_regions (board parse).
"""

from __future__ import annotations

from typing import Any

from admorphiq.adapters25.base import (
    GameAction,
    GameAdapter,
    canonical_layer,
    click_action,
    has_frame,
    most_common_color,
    reset_action,
    state_name,
)
from admorphiq.kernels import find_regions

GAME_ID = "lf52"

Cell = tuple[int, int]  # lattice (gx, gy)
Grid = tuple[tuple[int, ...], ...]

_GIVEUP_DEFAULT = 4000

_LATTICE_PITCH = 6
# A board cell renders as a ~4x4 block on the 6px lattice; the size window
# keeps genuine cells and drops 1px decorations and the whole-frame bg blob.
_MIN_CELL_SIZE = 6
_MAX_CELL_SIZE = 30

_DIRS: tuple[Cell, ...] = ((1, 0), (-1, 0), (0, 1), (0, -1))

_DFS_NODE_CAP = 200_000


class Adapter(GameAdapter):
    """Frame-only faithful peg-solitaire simulator + DFS + click replay."""

    GAME_ID = GAME_ID

    def __init__(self, giveup: int = _GIVEUP_DEFAULT) -> None:
        self.restart_on_game_over = True
        self._giveup = giveup
        self._step = 0
        self._levels_seen = -1
        # Replay queue of resolved pixel clicks for the current level's plan.
        self._clicks: list[Cell] = []

    # ── harness contract ────────────────────────────────────────────────

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        return state_name(latest_frame) == "WIN" or self._step >= self._giveup

    def choose_action(self, frames: list[Any], latest_frame: Any) -> GameAction:
        state = state_name(latest_frame)
        if state == "GAME_OVER":
            self._clicks = []
            return reset_action()
        if state == "NOT_PLAYED" or not has_frame(latest_frame):
            self._levels_seen = -1
            self._clicks = []
            return reset_action()

        levels = int(getattr(latest_frame, "levels_completed", 0) or 0)
        if levels != self._levels_seen:
            self._levels_seen = levels
            self._clicks = []

        self._step += 1

        if self._clicks:
            return click_action(*self._clicks.pop(0))

        grid = canonical_layer(latest_frame)
        board = _parse_board(grid)
        if board is None:
            return reset_action()
        pieces, cells, pixel_of = board

        plan = _solve(pieces, cells)
        if not plan:
            return reset_action()

        # Expand each jump into (select piece, click landing) pixel clicks.
        clicks: list[Cell] = []
        for src, dst in plan:
            clicks.append(pixel_of(src))
            clicks.append(pixel_of(dst))
        self._clicks = clicks
        return click_action(*self._clicks.pop(0))


# ── board parse ────────────────────────────────────────────────────────────


def _parse_board(grid: Grid):
    """Parse the visible frame into (pieces, cells, pixel_of).

    ``pieces`` and ``cells`` are lattice-coordinate sets ((gx, gy)); ``cells``
    is every board slot INCLUDING those a piece sits on. ``pixel_of`` maps a
    lattice cell to an integer (x, y) frame click point (detected centroid
    when known, linear lattice extrapolation otherwise). Returns None when the
    frame has no lattice board (piece and slot colours not separable).
    """
    if not grid or not grid[0]:
        return None
    bg = most_common_color(grid)
    regions = [
        r
        for r in find_regions(grid, background=bg)
        if _MIN_CELL_SIZE <= r["size"] <= _MAX_CELL_SIZE
    ]
    if len(regions) < 3:
        return None

    # Colour with the most cell-regions = the empty board slots; the next
    # most common cell colour = the movable pieces. Picking the single
    # most-common non-slot colour (rather than "any non-slot colour") drops
    # one-off decorations like the colour-9 selection/animation marker, which
    # is cell-sized but is not a piece.
    by_color: dict[int, int] = {}
    for r in regions:
        by_color[r["color"]] = by_color.get(r["color"], 0) + 1
    ranked = sorted(by_color.items(), key=lambda kv: (-kv[1], kv[0]))
    if len(ranked) < 2:
        return None  # no distinct piece colour on the board -> nothing to plan
    slot_color = ranked[0][0]
    piece_color = ranked[1][0]

    # Lattice origin = min centroid, so gx/gy are non-negative small integers.
    rows = [r["centroid"][0] for r in regions]
    cols = [r["centroid"][1] for r in regions]
    row0, col0 = min(rows), min(cols)

    def to_lattice(cr: float, cc: float) -> Cell:
        return (
            int(round((cc - col0) / _LATTICE_PITCH)),
            int(round((cr - row0) / _LATTICE_PITCH)),
        )

    pieces: set[Cell] = set()
    cells: set[Cell] = set()
    detected: dict[Cell, Cell] = {}
    for r in regions:
        cr, cc = r["centroid"]
        gx, gy = to_lattice(cr, cc)
        if r["color"] not in (slot_color, piece_color):
            continue  # decoration / marker not on the peg-solitaire board
        cells.add((gx, gy))
        detected[(gx, gy)] = (int(round(cc)), int(round(cr)))
        if r["color"] == piece_color:
            pieces.add((gx, gy))
    # A piece covers its slot, so occupied lattice points are board cells too.
    cells |= pieces
    if not pieces:
        return None

    def pixel_of(cell: Cell) -> Cell:
        if cell in detected:
            return detected[cell]
        gx, gy = cell
        return (int(round(col0 + gx * _LATTICE_PITCH)), int(round(row0 + gy * _LATTICE_PITCH)))

    return pieces, cells, pixel_of


# ── faithful simulator + search ─────────────────────────────────────────────


def _solve(pieces: set[Cell], cells: set[Cell]) -> list[tuple[Cell, Cell]]:
    """DFS the peg-solitaire jump graph for a sequence reducing to one piece.

    Returns a list of (source_cell, landing_cell) jumps, or [] if none found.
    A jump ``P -> P+2d`` is legal iff ``P+d`` holds a piece and ``P+2d`` is an
    empty board slot; it removes ``P`` and ``P+d`` and adds ``P+2d``.
    """
    start = frozenset(pieces)
    seen: set[frozenset] = set()
    nodes = 0

    def moves(state: frozenset) -> list[tuple[Cell, Cell]]:
        out: list[tuple[Cell, Cell]] = []
        for (px, py) in state:
            for dx, dy in _DIRS:
                mid = (px + dx, py + dy)
                land = (px + 2 * dx, py + 2 * dy)
                if mid in state and land in cells and land not in state:
                    out.append(((px, py), land))
        return out

    def dfs(state: frozenset) -> list[tuple[Cell, Cell]] | None:
        nonlocal nodes
        if len(state) == 1:
            return []
        if state in seen:
            return None
        seen.add(state)
        nodes += 1
        if nodes > _DFS_NODE_CAP:
            return None
        for (px, py), land in moves(state):
            mid = ((px + land[0]) // 2, (py + land[1]) // 2)
            nxt = frozenset((state - {(px, py), mid}) | {land})
            rest = dfs(nxt)
            if rest is not None:
                return [((px, py), land), *rest]
        return None

    result = dfs(start)
    return result or []
