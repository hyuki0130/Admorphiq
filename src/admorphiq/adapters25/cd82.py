"""script25 quarantined adapter: CD82 (ring-paint — match a target painting).

*** QUARANTINE — MODEL-NEVER-VISIBLE. See admorphiq.adapters25's package
docstring. ***

``.wiki/wiki/games/CD82.md`` (read for reference, not imported) records CD82 as
the PAINT game: a brittle legacy solver cleared 6/6 by reading hardcoded sprite
positions, and a from-scratch ``ring_paint`` search solver later cleared 6/6
frame-only (``game_score`` 0.9463, ~108 actions). Reading the game source
(offline, for understanding only — never imported) settles the exact mechanic;
this adapter re-expresses that mechanic as a stdlib + ``admorphiq.kernels``
composition with ALL geometry measured from the frame (no hardcoded pixel
coordinates, palettes, or level solutions).

**Mechanic (measured from the source + a live region probe)**:

- A basket sits on one of EIGHT ring positions — the 3×3 grid minus its centre —
  around a 10×10 **CANVAS**. ``available_actions = [1,2,3,4,5,6]``.
  ACTION1-4 walk the basket one ring cell (up/down/left/right, the centre cell is
  skipped); the basket always STARTS a level at ring position 0 (top-centre).
- ACTION5 **LAUNCHES**: it overwrites one fixed region of the canvas with the
  currently-selected colour. The region is a pure function of the ring position:
  0/2/4/6 paint the top/right/bottom/left HALVES; 1/3/5/7 paint the four
  diagonal TRIANGLES. (This region table is the mechanic — declared HERE as the
  adapter's semantics, exactly as re86/sc25 declare theirs; it is relative 10×10
  geometry, never a screen coordinate.)
- ACTION6 on a top-row colour **SWATCH** selects that colour (the basket recolours
  to confirm). ACTION6 on an **ARROW** sprite (present only from level 3, and only
  while the basket is on a half position 0/2/4/6) paints a small centre-edge PATCH
  of the canvas — the only way to make a sub-half detail.
- A separate 10×10 **TARGET** panel (top-left) shows the goal. The level clears
  when the canvas matches the target on the OFF-DIAGONAL cells only — the game's
  win check ignores the two main diagonals (cells ``[i,i]`` and ``[i,9-i]``). The
  planner therefore matches off-diagonal cells only, or it would over-search.
- 100-action budget per level; overrun is a GAME_OVER that resets the attempt to
  the pristine start (handled the standard script25 way — reset, keep going).

**Design — reactive plan-one-op-then-replan.** Launch/arrow animations are ATOMIC
from the harness's view (the engine resolves the whole animation inside one
``env.step`` because the ACTION5/arrow branches don't complete the action until
the paint finishes), so every observation this adapter sees is a SETTLED frame.
Each time the primitive queue empties, the adapter re-reads the live canvas +
target, BFS-plans the shortest paint-op sequence from the CURRENT canvas to the
target (``_plan_paint`` — a breadth-first search over launch/arrow ops with
per-state dedup, matching off-diagonal only), and executes the FIRST op's
primitives (navigate the ring → select the colour if not already held → launch or
arrow-click). Replanning from the actual canvas each op is self-correcting: a
misfired op just gets re-planned away, and the plan shrinks by one op per fire
until the canvas matches and the level auto-advances.

**Frame-only geometry (no hardcoded coordinates)**:
  - The CANVAS is the uniform ~10×10 region in the lower half; its origin is
    LOCKED at level start (when it is still one clean single-colour region — after
    the first paint it fragments, so the locked origin is reused all level).
  - The TARGET is the coloured block in the upper-LEFT (left of the swatches); its
    origin + 10×10 pattern are locked once. Its own colours ARE the paint palette.
  - The SWATCHES are the small top-band colour dots to the RIGHT of the target
    whose colour appears in the target palette (this palette filter drops the
    swatch BORDER colour without hardcoding it). Colour → click ``(x, y)``.
  - The ARROW click point is DETECTED at fire time as the small region sitting
    just outside the canvas on the basket's current side (never a fixed pixel).

Composition from ``admorphiq.kernels``:
  - :func:`admorphiq.kernels.find_regions` segments the frame into the canvas,
    the target block, the swatch dots, the basket, and (at fire time) the arrow.
  - :func:`admorphiq.kernels.template_occupancy` is not needed here — the target
    is read as a raw 10×10 colour block, richer than a boolean occupancy.
"""

from __future__ import annotations

from collections import deque
from typing import Any

from admorphiq.adapters25.base import (
    GameAction,
    GameAdapter,
    canonical_layer,
    click_action,
    has_frame,
    most_common_color,
    reset_action,
    simple_action,
    state_name,
)
from admorphiq.kernels import find_regions

GAME_ID = "cd82"

Grid = tuple[tuple[int, ...], ...]
Canvas = tuple[int, ...]  # 100 ints, row-major 10x10
Region = dict[str, Any]
# A primitive action: a ring move ("m", id), a swatch click ("c", x, y), a launch
# ("L",), or an arrow paint ("A", ring_position — coord resolved at fire time).
Prim = tuple[Any, ...]

_GIVEUP_DEFAULT = 4000
_N = 10  # canvas / target edge length
# The arrow sprite is a small patch (measured ≤ ~14px); the basket that hugs the
# same side is far larger (its border alone ≥ ~30px, its arc ≥ ~80px). This size
# ceiling is what lets the arrow be told apart from the basket that sits between
# it and the canvas — a measured discriminator, no coordinate.
_ARROW_MAX_SIZE = 24

# Ring position -> (row, col) on the 3x3 grid (the centre (1,1) is excluded).
# ACTION1-4 move the basket between ADJACENT ring cells (up/down/left/right).
_POS_GRID: dict[int, tuple[int, int]] = {
    0: (0, 1), 1: (0, 2), 2: (1, 2), 3: (2, 2),
    4: (2, 1), 5: (2, 0), 6: (1, 0), 7: (0, 0),
}

# Off-diagonal cell indices — the game's win check compares canvas==target ONLY
# off the two main diagonals, so the planner matches exactly these.
_OFFDIAG = tuple(
    r * _N + c for r in range(_N) for c in range(_N) if r != c and r != _N - 1 - c
)


def _launch_cells(pos: int) -> frozenset[int]:
    """The 10×10 cell indices a LAUNCH from ring ``pos`` overwrites: 0/2/4/6 =
    top/right/bottom/left halves; 1/3/5/7 = the four diagonal triangles. This is
    the game's launch geometry (the mechanic), expressed as relative grid cells."""
    cells: set[int] = set()
    if pos == 0:
        cells = {r * _N + c for r in range(0, 5) for c in range(_N)}
    elif pos == 4:
        cells = {r * _N + c for r in range(5, _N) for c in range(_N)}
    elif pos == 6:
        cells = {r * _N + c for r in range(_N) for c in range(0, 5)}
    elif pos == 2:
        cells = {r * _N + c for r in range(_N) for c in range(5, _N)}
    elif pos == 1:
        cells = {r * _N + c for r in range(_N) for c in range(r, _N)}
    elif pos == 3:
        cells = {r * _N + c for r in range(_N) for c in range(_N - 1 - r, _N)}
    elif pos == 5:
        cells = {r * _N + c for r in range(_N) for c in range(0, r + 1)}
    elif pos == 7:
        cells = {r * _N + c for r in range(_N) for c in range(0, _N - r)}
    return frozenset(cells)


def _arrow_cells(pos: int) -> frozenset[int]:
    """The 10×10 patch an ARROW-click overwrites at half-position ``pos`` — a
    small centre-edge block distinct from a launch's half (the game geometry)."""
    cells: set[int] = set()
    if pos == 0:
        cells = {r * _N + c for r in range(0, 3) for c in range(3, 7)}
    elif pos == 4:
        cells = {r * _N + c for r in range(7, _N) for c in range(3, 7)}
    elif pos == 6:
        cells = {r * _N + c for r in range(3, 7) for c in range(0, 3)}
    elif pos == 2:
        cells = {r * _N + c for r in range(3, 7) for c in range(7, _N)}
    return frozenset(cells)


# Precomputed op geometry: ("L", pos) launches + ("A", pos) arrows.
_OPS: list[tuple[str, int, frozenset[int]]] = [("L", p, _launch_cells(p)) for p in range(8)]
_OPS += [("A", p, _arrow_cells(p)) for p in (0, 2, 4, 6)]


def _apply(canvas: Canvas, cells: frozenset[int], colour: int) -> Canvas:
    lst = list(canvas)
    for i in cells:
        lst[i] = colour
    return tuple(lst)


def _matches(canvas: Canvas, target: Canvas) -> bool:
    return all(canvas[i] == target[i] for i in _OFFDIAG)


def _plan_paint(
    canvas: Canvas, target: Canvas, colours: list[int], max_depth: int = 4
) -> list[tuple[str, int, int]]:
    """Shortest paint-op sequence taking ``canvas`` to ``target`` (off-diagonal).

    BFS over ``("L", pos, colour)`` launches and ``("A", pos, colour)`` arrow-
    clicks — each op overwrites its region, later ops paint over earlier — with
    per-canvas dedup so the reachable-state fan-out stays bounded. Returns the op
    list, ``[]`` when already matching or when nothing up to ``max_depth`` matches
    (the caller then idles / re-reads next frame)."""
    if _matches(canvas, target):
        return []
    combos = [(kind, pos, cells, col) for (kind, pos, cells) in _OPS for col in colours]
    frontier: deque[tuple[Canvas, list[tuple[str, int, int]]]] = deque([(canvas, [])])
    seen = {canvas}
    while frontier:
        cur, seq = frontier.popleft()
        if len(seq) >= max_depth:
            continue
        for kind, pos, cells, col in combos:
            nxt = _apply(cur, cells, col)
            if nxt == cur:
                continue
            if _matches(nxt, target):
                return [*seq, (kind, pos, col)]
            if nxt not in seen:
                seen.add(nxt)
                frontier.append((nxt, [*seq, (kind, pos, col)]))
    return []


def _ring_path(cur: int, tgt: int) -> list[int]:
    """BFS the basket from ring position ``cur`` to ``tgt`` (ACTION1-4), skipping
    the excluded 3×3 centre; returns the action-id path."""
    if cur == tgt:
        return []
    cr, cc = _POS_GRID[cur]
    tr, tc = _POS_GRID[tgt]
    q: deque[tuple[int, int, list[int]]] = deque([(cr, cc, [])])
    seen = {(cr, cc)}
    while q:
        r, c, path = q.popleft()
        if (r, c) == (tr, tc):
            return path
        for dr, dc, a in ((-1, 0, 1), (1, 0, 2), (0, -1, 3), (0, 1, 4)):
            nr, nc = r + dr, c + dc
            if 0 <= nr <= 2 and 0 <= nc <= 2 and (nr, nc) != (1, 1) and (nr, nc) not in seen:
                seen.add((nr, nc))
                q.append((nr, nc, [*path, a]))
    return []


class Adapter(GameAdapter):
    """Reactive ring-paint solver: replan-one-op from the live canvas each fire."""

    GAME_ID = GAME_ID

    def __init__(self, giveup: int = _GIVEUP_DEFAULT, max_depth: int = 4) -> None:
        self.restart_on_game_over = True

        self._giveup = giveup
        self._max_depth = max_depth
        self._step = 0
        self._levels_seen = -1

        # Locked-once level geometry (canvas + target never move within a level).
        self._canvas_origin: tuple[int, int] | None = None  # (row, col)
        self._target: Canvas | None = None
        self._palette: list[int] = []
        self._swatch: dict[int, tuple[int, int]] = {}  # colour -> click (x, y)
        # The prior frame's target read — the board redraws ONE FRAME AFTER
        # ``levels_completed`` increments, so the transition frame still shows the
        # PREVIOUS level's target. Locking is gated on two consecutive equal reads
        # (plus a clean uniform canvas) to reject that stale frame.
        self._target_prev: Canvas | None = None

        # Execution state: the initial basket ring position is 0 and the initial
        # selected colour is the game's level-start default (15). Both are tracked
        # optimistically — every primitive is atomic + deterministic, so after
        # queueing an op the basket IS at its target position and the held colour
        # IS the selected one.
        self._ring = 0
        self._sel = 15
        self._queue: list[Prim] = []

    # ── harness contract ────────────────────────────────────────────────

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        return state_name(latest_frame) == "WIN" or self._step >= self._giveup

    def choose_action(self, frames: list[Any], latest_frame: Any) -> GameAction:
        state = state_name(latest_frame)
        if state == "GAME_OVER":
            self._reset_exec()
            return reset_action()
        if state == "NOT_PLAYED" or not has_frame(latest_frame):
            self._levels_seen = -1
            self._reset_exec()
            return reset_action()

        grid = canonical_layer(latest_frame)
        levels = int(getattr(latest_frame, "levels_completed", 0) or 0)
        if levels != self._levels_seen:
            self._on_level_up(levels)

        self._step += 1
        if not self._queue:
            self._plan_next_op(grid)
        if not self._queue:
            return self._idle(grid)
        prim = self._queue.pop(0)
        return self._to_action(prim, grid)

    # ── level bookkeeping ────────────────────────────────────────────────

    def _on_level_up(self, levels: int) -> None:
        self._levels_seen = levels
        self._canvas_origin = None
        self._target = None
        self._palette = []
        self._swatch = {}
        self._target_prev = None
        self._reset_exec()

    def _reset_exec(self) -> None:
        """Reset the per-attempt execution state — the basket returns to ring 0
        and the held colour to the level-start default on every fresh attempt."""
        self._ring = 0
        self._sel = 15
        self._queue = []

    # ── perception ───────────────────────────────────────────────────────

    def _regions(self, grid: Grid) -> list[Region]:
        if not grid:
            return []
        return find_regions(grid, background=most_common_color(grid))

    def _lock_geometry(self, grid: Grid) -> bool:
        """Detect + lock the canvas origin, the target pattern/palette, and the
        swatch click points, returning whether the full geometry is available.

        Locking is deferred until (a) a CLEAN uniform canvas region is visible
        (present only before the first paint of a level) AND (b) the target reads
        identically two frames running. Together these reject the one-frame stale
        board that the level-up frame still shows."""
        if self._canvas_origin is not None and self._target is not None and self._swatch:
            return True
        if not grid:
            self._target_prev = None
            return False
        regions = self._regions(grid)

        # CANVAS origin: the uniform ~10×10 single-colour region in the lower half.
        # Only detectable while still uniform, so a stale post-paint transition
        # frame (canvas already fragmented) fails this and defers the whole lock.
        if self._canvas_origin is None:
            height = len(grid)
            for r in regions:
                r0, c0, r1, c1 = r["bbox"]
                w, h = c1 - c0 + 1, r1 - r0 + 1
                if 8 <= w <= 12 and 8 <= h <= 12 and r["size"] >= 60 and r["centroid"][0] > height / 2:
                    self._canvas_origin = (r0, c0)
                    break
        if self._canvas_origin is None:
            self._target_prev = None
            return False

        read = self._read_target(grid, regions)
        if read is None:
            self._target_prev = None
            return False
        target, palette, swatch = read
        if target != self._target_prev:
            self._target_prev = target  # first sighting — require one more equal read
            return False
        self._target = target
        self._palette = palette
        self._swatch = swatch
        return bool(self._swatch)

    def _read_target(
        self, grid: Grid, regions: list[Region]
    ) -> tuple[Canvas, list[int], dict[int, tuple[int, int]]] | None:
        """Read the 10×10 target block, its paint palette, and the swatch click
        points from the UPPER band (above the canvas). Interior coloured comps
        only (drop the frame-edge letterbox / step bar / backdrop panels); the
        leftmost comp anchors the target block, swatch dots sit to its right, and
        the palette (the target's own colours) filters the swatch border colour
        out without hardcoding it."""
        if self._canvas_origin is None:
            return None
        height, width = len(grid), len(grid[0])
        canvas_r0 = self._canvas_origin[0]
        bg = most_common_color(grid)
        upper = [
            r
            for r in regions
            if r["centroid"][0] < canvas_r0
            and r["size"] >= 6
            and r["bbox"][0] > 0
            and r["bbox"][1] > 0
            and r["bbox"][2] < height - 1
            and r["bbox"][3] < width - 1
        ]
        if not upper:
            return None
        tx0 = min(r["bbox"][1] for r in upper)
        block = [r for r in upper if r["bbox"][1] < tx0 + _N]
        ty0 = min(r["bbox"][0] for r in block)
        target = self._read_block(grid, ty0, tx0)
        if target is None:
            return None
        palette = sorted(set(target) - {bg})
        swatch: dict[int, tuple[int, int]] = {}
        for r in upper:
            if r["bbox"][1] >= tx0 + _N and r["color"] in palette:
                row, col = r["centroid"]
                swatch.setdefault(int(r["color"]), (int(round(col)), int(round(row))))
        if not swatch:
            return None
        return target, palette, swatch

    def _read_block(self, grid: Grid, r0: int, c0: int) -> Canvas | None:
        height, width = len(grid), len(grid[0])
        if r0 < 0 or c0 < 0 or r0 + _N > height or c0 + _N > width:
            return None
        return tuple(grid[r0 + dr][c0 + dc] for dr in range(_N) for dc in range(_N))

    def _read_canvas(self, grid: Grid) -> Canvas | None:
        if self._canvas_origin is None:
            return None
        r0, c0 = self._canvas_origin
        return self._read_block(grid, r0, c0)

    def _arrow_xy(self, grid: Grid, pos: int) -> tuple[int, int] | None:
        """The ARROW click point for the basket's current half-position ``pos`` —
        the small region sitting just outside the canvas on that side. Detected
        from the frame (never a fixed pixel): pick the closest small region whose
        centroid lies in the ``pos`` direction from the canvas centre with a small
        lateral offset."""
        if self._canvas_origin is None:
            return None
        r0, c0 = self._canvas_origin
        cy, cx = r0 + _N / 2, c0 + _N / 2  # canvas centre (row, col)
        drow, dcol = {0: (-1, 0), 4: (1, 0), 6: (0, -1), 2: (0, 1)}[pos]
        best: tuple[float, int, int] | None = None
        for r in self._regions(grid):
            rr0, cc0, rr1, cc1 = r["bbox"]
            if rr0 >= r0 and cc0 >= c0 and rr1 <= r0 + _N - 1 and cc1 <= c0 + _N - 1:
                continue  # inside the canvas box
            if not 4 <= r["size"] <= _ARROW_MAX_SIZE:
                continue
            rr, cc = r["centroid"]
            proj = (rr - cy) * drow + (cc - cx) * dcol
            lateral = abs((rr - cy) * dcol - (cc - cx) * drow)
            if proj <= 2 or lateral > 4:
                continue
            if best is None or proj < best[0]:
                best = (proj, int(round(cc)), int(round(rr)))
        if best is not None:
            return (best[1], best[2])
        return None

    # ── planning + execution ─────────────────────────────────────────────

    def _plan_next_op(self, grid: Grid) -> None:
        if not self._lock_geometry(grid):
            return
        canvas = self._read_canvas(grid)
        if canvas is None or self._target is None:
            return
        if _matches(canvas, self._target):
            return  # matched — the level auto-advances; idle this frame
        plan = _plan_paint(canvas, self._target, self._palette, self._max_depth)
        if not plan:
            return
        self._queue = self._build_queue(plan[0])

    def _build_queue(self, op: tuple[str, int, int]) -> list[Prim]:
        kind, pos, colour = op
        queue: list[Prim] = [("m", a) for a in _ring_path(self._ring, pos)]
        self._ring = pos
        if self._sel != colour and colour in self._swatch:
            sx, sy = self._swatch[colour]
            queue.append(("c", sx, sy))
            self._sel = colour
        queue.append(("L",) if kind == "L" else ("A", pos))
        return queue

    def _to_action(self, prim: Prim, grid: Grid) -> GameAction:
        tag = prim[0]
        if tag == "m":
            return simple_action(prim[1])
        if tag == "c":
            return click_action(prim[1], prim[2])
        if tag == "L":
            return simple_action(5)
        # tag == "A": resolve the arrow click point from the live frame now.
        xy = self._arrow_xy(grid, prim[1])
        if xy is None:
            return simple_action(5)  # arrow not found — a launch never regresses
        return click_action(xy[0], xy[1])

    def _idle(self, grid: Grid) -> GameAction:
        """A no-effect action while the geometry is not yet readable or the canvas
        already matches: click the canvas centre (the canvas sprite is inert to
        clicks), so no state changes and the level-complete transition can land."""
        if self._canvas_origin is not None:
            r0, c0 = self._canvas_origin
            return click_action(c0 + _N // 2, r0 + _N // 2)
        return click_action(0, 0)
