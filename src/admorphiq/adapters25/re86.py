"""script25 quarantined adapter: RE86 (delivery / colour-assignment family).

*** QUARANTINE — MODEL-NEVER-VISIBLE. See admorphiq.adapters25's package
docstring. ***

``.wiki/wiki/games/RE86.md`` (read for reference, not imported) records RE86 as
a brittle 6/8 solve that read three sprite tags — ``vzuwsebntu`` (targets),
``vfaeucgcyr`` (movables), ``ozhohpbjxz`` (changers) — with every generic
attempt at 0/8. Reading the game source (dev-time only; this adapter acts
frame-only) plus live probes (``scratchpad`` traces, offline) decode what those
tags track and their frame-observable equivalents:

**Mechanic (measured — roles/hypothesis declared HERE, not in any kernel)**:
RE86 is a delivery + colour-assignment puzzle.

- ``available_actions`` = ``[1,2,3,4,5]``, no ACTION6. ACTION1-4 move the
  SELECTED movable one 3px cell (``ilmaurgzng=3``); the sign per action is
  MEASURED. **ACTION5 CYCLES the selection** to the next movable (its centre
  is marked with the selection colour ``0``). Measured on level 1: exactly TWO
  movables, selection toggling between them.
- Movables (``vfaeucgcyr``) are shaped sprites (a cross/bar) drawn in a colour
  (measured colours 9 and 11 on level 1); their centre carries the selection
  marker (colour 0) when active.
- Targets (``vzuwsebntu``) are static colour-bordered boxes (a colour-4 border
  around a coloured centre) painted on a backdrop canvas. The win check
  (``cdjxpfqest`` in source) stamps every movable onto that canvas and requires
  each target's coloured pixels to be covered by a MATCHING-colour movable
  pixel at the target's position — a bipartite colour assignment scored by
  position (typology T3 variant).
- Changers (``ozhohpbjxz``) are static coloured lines; a movable of a different
  colour that overlaps one is RECOLOURED to the changer's colour (animated,
  spreading across the movable over several steps). This is how a movable is
  re-coloured to match a target it doesn't already match.

**This adapter's approach — covering-offset delivery** (composing the
codex-intended primitives): locate the active movable by its selection marker
(colour 0); recover its FULL shape as the marker-anchored, colour-4/background-
gap-bridged connected component (``find_regions(gap=1)`` — this reunites the
cross the changer line would otherwise split); LOCK the target-box cells per
colour once while the scene is clean; and use ``kernels.covering_offsets`` for a
single translation of the movable's shape onto its matching-colour targets. Step
toward the nearest offset with MEASURED move directions, switching axis on a
walled move, and — crucially — **never disturb a movable already at offset
(0,0)** (both movables must be covered simultaneously to win), cycling ACTION5
to work the other one instead.

**Measured coverage**: on the local env (``re86-8af5384d``) this clears
**2/8** (``game_score`` 0.033, deterministic ×3) — up from 1/8. Baseline:
brittle 6/8 by sprite-tag read, prior generic 0/8. Both L1 and L2 solve through
the SAME covering spine (no per-level code): each colour-coded movable is driven
to the single translation that covers its matching-colour gates, selection is
cycled with ACTION5, and a placed movable is never disturbed.

**Level 2 SOLVED (R59) — two frame-only perception fixes, NO new mechanic**:
the earlier "banked wall" was two perception bugs, not a mechanic gap. Ground
truth was read from the game source win-check (``jeiavrvavi``: every
non-border target-map cell must be covered by a matching-colour movable pixel)
and confirmed frame-for-frame against the gold replay (``data/traces/re86.npz``,
replays 6/6 live). L2 has THREE movables — a colour-12 X, a colour-13 diamond
OUTLINE, a colour-9 plus — and TEN gates (colour-9 ×4, colour-12 ×3, colour-13
×3). The covering solve places each movable's centre at colour-9 → (48,27),
colour-12 → (48,18), colour-13 → (12,21); those destinations are DERIVED by
``covering_offsets`` from the frame-read gate geometry, never hardcoded (they
match the gold win frame exactly). Two prior beliefs were FALSIFIED by live
observation:
  - "colour-13 is invisible" — it is fully visible during play (35–39 px every
    frame); the earlier read failed only on a STALE first frame (below). No
    footprint-probe or shape recovery is needed.
  - "compound colour-11 gate / off-grid colour-12 target / recolour" — none
    exist; the true gate colours are 9/12/13 and no changer/wall is present on
    L2, so there is no recolour.

The two fixes:
  1. **Settle before locking targets.** A level LOAD renders a transient
     camera-transition frame — shifted, showing two colour-9/-11 crosses and 24
     phantom gates — before the engine snaps to steady world coordinates after
     ONE env-step. Locking targets on that first frame captured the phantom
     gate set and doomed the level. ``_decide`` now defers the lock one step
     (a selection cycle settles the render without moving a piece). Generic
     level-load discipline, not a game constant.
  2. **Select by centroid, not by size.** The marker sits at the SELECTED
     movable's centre, so ``_active_movable`` returns the centroid-nearest
     region. The old "largest region touching a marker neighbour" rule returned
     the big colour-12 X whenever its sparse body overlapped the colour-13
     diamond's marker, so the planner drove the X's offset while the engine
     moved the diamond — an endless oscillation.
A third robustness fix (``_decide`` measures every move direction before
covering-navigating an unplaced piece) stops a piece whose larger covering axis
is a still-unmeasured direction from oscillating on the only axis it has learned.

**Residual (efficiency, not correctness)**: the colour-13 diamond is a hollow
outline; occlusion + gap-bridged extraction makes its cell set jitter ±1–2 px,
so ``covering_offsets`` is non-stationary and the greedy wanders (~140 actions
vs the gold's 36) before landing a clean cover. The clear is reliable and
deterministic; a stable hollow-outline extractor is the open efficiency lever.

**Level 3 SOLVED (R60) — separation-by-motion + per-piece gate-claiming**:
deep levels merge SEVERAL same-colour movables into one region, so the
single-piece covering spine cannot address them (``find_regions`` returns one
132px blob for three overlapping colour-8 pieces). Since only the SELECTED
movable moves per action, a probe move perpendicular to the merge seam isolates
it: :func:`admorphiq.kernels.separate_by_motion` returns the moved object's
cells from the motion delta even while merged. With all pieces and all gates the
same colour the win is a geometric set-cover no single piece can satisfy, so the
controller (:meth:`Adapter._decide_multi`, gated on level index >= 2 so L1/L2
stay byte-identical) claims gates piece by piece:
:func:`admorphiq.kernels.max_coverage_offset` picks the translation covering the
most still-unclaimed gates, the piece is driven there, those gates are frozen,
and ACTION5 cycles to the next piece — never re-driving a placed one. Measured
**3/8 @ game_score 0.1162 (deterministic ×3)**, up from 2/8 @ 0.0328.

Composition from ``admorphiq.kernels``:
  - :func:`admorphiq.kernels.find_regions` segments movables / target boxes.
  - :func:`admorphiq.kernels.covering_offsets` finds a translation of the
    active movable's shape onto its matching-colour target cells (L1/L2).
  - :func:`admorphiq.kernels.separate_by_motion` isolates one merged same-colour
    movable from the others by its motion (L3+ separation pre-step).
  - :func:`admorphiq.kernels.max_coverage_offset` picks the single translation
    covering the most still-unclaimed gates (L3+ per-piece gate-claiming).
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from admorphiq.adapters25.base import (
    GameAction,
    GameAdapter,
    available_action_ids,
    canonical_layer,
    has_frame,
    most_common_color,
    reset_action,
    simple_action,
    state_name,
)
from admorphiq.kernels import (
    covering_offsets,
    find_regions,
    max_coverage_offset,
    separate_by_motion,
)

GAME_ID = "re86"

Cell = tuple[int, int]
Region = dict[str, Any]

_GIVEUP_DEFAULT = 4000
_SELECTION_COLOR = 0
_BORDER_COLOR = 4
# Changer stations (deep levels) are bordered by this colour, not _BORDER_COLOR.
_STATION_BORDER = 2
# Move pitch in pixels (measured, ilmaurgzng=3). Only quantises a delta into a
# step count — not a coordinate.
_CELL_PX = 3


def _sign(v: int) -> int:
    return (v > 0) - (v < 0)


def _station_boxes(grid: tuple[tuple[int, ...], ...]) -> tuple[dict[int, Cell], list[tuple[int, int, int, int]]]:
    """Changer stations = solid colour swatches inside a ``_STATION_BORDER``
    (colour-2) bordered box, painted at the frame edges. Each colour-2 ring is
    one connected region (``find_regions``); its bbox interior's dominant colour
    is the swatch a mismatched movable is RECOLOURED to on contact. Returns
    ``{swatch_colour: (centre_row, centre_col)}`` and the box bounding-boxes
    (used to reject station swatches from the movable parse). Frame-only."""
    bg = most_common_color(grid)
    by_color: dict[int, Cell] = {}
    boxes: list[tuple[int, int, int, int]] = []
    for reg in find_regions(grid, background=bg, gap=1):
        if reg["color"] != _STATION_BORDER:
            continue
        ys = [r for r, _c in reg["cells"]]
        xs = [c for _r, c in reg["cells"]]
        r0, c0, r1, c1 = min(ys), min(xs), max(ys), max(xs)
        inside: Counter[int] = Counter(
            grid[y][x]
            for y in range(r0, r1 + 1)
            for x in range(c0, c1 + 1)
            if grid[y][x] not in (_STATION_BORDER, bg)
        )
        if inside:
            by_color[inside.most_common(1)[0][0]] = ((r0 + r1) // 2, (c0 + c1) // 2)
            boxes.append((r0, c0, r1, c1))
    return by_color, boxes


def _in_boxes(cell: Cell, boxes: list[tuple[int, int, int, int]], pad: int = 1) -> bool:
    r, c = cell
    for r0, c0, r1, c1 in boxes:
        if r0 - pad <= r <= r1 + pad and c0 - pad <= c <= c1 + pad:
            return True
    return False


def _target_boxes(grid: tuple[tuple[int, ...], ...]) -> list[Cell]:
    """Cells of colour-bordered target gates: a non-border, non-background,
    non-selection pixel flanked by the border colour on a PAIR of opposite
    sides — left+right OR top+bottom. This covers both the 3×3 fully-bordered
    box (satisfies either pair) and the taller gate bars used on deeper levels
    (a colour column flanked left/right by the border), which the all-four-
    sides rule missed. Returns ``(row, col)`` per gate cell (the required
    colour is ``grid[row][col]``). Frame-only, no sprite-tag read."""
    boxes: list[Cell] = []
    h = len(grid)
    w = len(grid[0]) if grid else 0
    b = _BORDER_COLOR
    for r in range(1, h - 1):
        for c in range(1, w - 1):
            v = grid[r][c]
            if v in (b, _SELECTION_COLOR):
                continue
            horizontal = grid[r][c - 1] == b and grid[r][c + 1] == b
            vertical = grid[r - 1][c] == b and grid[r + 1][c] == b
            if horizontal or vertical:
                boxes.append((r, c))
    return boxes


class Adapter(GameAdapter):
    """Covering-offset greedy delivery composed from admorphiq.kernels."""

    GAME_ID = GAME_ID

    def __init__(self, giveup: int = _GIVEUP_DEFAULT) -> None:
        self.restart_on_game_over = True

        self._giveup = giveup
        self._step = 0
        self._levels_seen = -1

        # Measured (dr_sign, dc_sign) per move action, like m0r0's dir_map.
        self._dir: dict[int, Cell] = {}
        # Same measurement, but NEVER reset across levels — the engine's move map
        # is level-invariant, so L4 can reuse the L1-L3 measurement instead of
        # probing (an L4 probe risks driving a wide movable into a station and
        # recolouring it to a colour it cannot fully cover; carrying the map over
        # avoids that).
        self._dir_global: dict[int, Cell] = {}
        self._pending_action: int | None = None
        self._pending_marker: Cell | None = None
        self._prev_grid: tuple[tuple[int, ...], ...] | None = None
        # Rotates through selection cycling when the active movable has no
        # reachable covering move, so both movables get worked.
        self._stall = 0
        # Target-box cells grouped by required colour, LOCKED once at level
        # start while the scene is clean — a movable occludes the target boxes
        # as it arrives on them, so re-reading targets live destabilises the
        # covering offset near the goal (measured: the offset stops shrinking
        # cleanly a couple of cells short). Targets never move, so the locked
        # set stays valid all level (same discipline as m0r0/cn04).
        self._targets_by_color: dict[int, list[Cell]] = {}
        self._targets_locked = False
        # A level LOAD renders a transient camera-transition frame: the scene
        # is shifted and the movables/gates render in stale colours (measured
        # on L2 — the first post-load frame shows two colour-9/-11 crosses and
        # 24 phantom gates, then the engine snaps to steady WORLD coordinates
        # after ONE env-step, revealing the true three movables + ten gates).
        # Locking targets on that first frame captures the phantom gate set and
        # dooms the level. Defer locking until the scene has settled (one step),
        # a generic level-load discipline, not a game-specific constant.
        self._settled = False
        # (marker_cell, action) pairs that produced no displacement (blocked by
        # a wall/edge) — the covering planner routes around them by axis.
        self._blocked: set[tuple[Cell, int]] = set()

        # ── L3+ separation-and-claim state (multi-piece, same-colour merge) ──
        # On deep levels several same-colour movables render as ONE merged
        # region, so the covering spine cannot address them individually. Gated
        # on level index (>= 2) so L1/L2 stay byte-identical. Gates claimed by a
        # placed piece are frozen so later pieces target only the rest; a placed
        # piece's footprint is recorded and never re-driven.
        self._claimed: set[Cell] = set()
        self._placed: list[frozenset[Cell]] = []
        # The active piece's shape as offsets from the selection marker, learned
        # ONCE from a perpendicular separating move (separate_by_motion isolates
        # the moved piece cleanly only across the merge seam); then the piece is
        # tracked by the marker without re-separating every step.
        self._shape_rel: frozenset[Cell] | None = None
        self._sep_pending = False
        self._sep_steps = 0

        # ── L4+ recolour-routing state (two mismatched-colour movables that
        # must each be routed through a matching-colour CHANGER station to
        # recolour, then cover their now-matching gates). Gated on level index
        # (>= 3) so L1/L2/L3 stay byte-identical. ──
        self._l4_stations: dict[int, Cell] = {}
        self._l4_station_boxes: list[tuple[int, int, int, int]] = []
        self._l4_stations_locked = False
        # Two persistently-tracked pieces (identity by centroid continuity, NOT
        # colour — a recolour changes colour but not position; the marker is
        # occluded when pieces overlap, so selection is tracked by count+marker).
        self._l4_pieces: list[dict[str, Any]] | None = None
        self._l4_sel = 0
        # original-movable-colour -> target gate colour (assignment chosen so
        # BOTH movables fully cover their gates after recolour).
        self._l4_assign: dict[int, int] = {}
        self._l4_blocked: set[tuple[Cell, int]] = set()
        # last directional move issued (blocked-key, action) + the piece it drove
        # and that piece's pre-move centroid, so a no-op (walled) move is detected
        # on the NEXT frame and recorded — the covering planner then switches axis.
        self._l4_last_move: tuple[Cell, int] | None = None
        self._l4_moved_id = 0
        self._l4_moved_cen: Cell | None = None

    # ── harness contract ────────────────────────────────────────────────

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        return state_name(latest_frame) == "WIN" or self._step >= self._giveup

    def choose_action(self, frames: list[Any], latest_frame: Any) -> GameAction:
        state = state_name(latest_frame)
        if state == "GAME_OVER":
            self._pending_action = None
            self._prev_grid = None
            return reset_action()
        if state == "NOT_PLAYED" or not has_frame(latest_frame):
            self._pending_action = None
            self._prev_grid = None
            self._levels_seen = -1
            return reset_action()

        grid = canonical_layer(latest_frame)
        levels = int(getattr(latest_frame, "levels_completed", 0) or 0)
        if levels != self._levels_seen:
            self._on_level_up(levels)

        self._step += 1
        self._observe(grid)

        simple_ids, _a6 = available_action_ids(latest_frame)
        move_ids = [a for a in simple_ids if a in (1, 2, 3, 4)]
        action = self._decide(grid, move_ids, 5 in simple_ids)
        self._prev_grid = grid
        return action

    # ── bookkeeping ─────────────────────────────────────────────────────

    def _on_level_up(self, levels: int) -> None:
        self._levels_seen = levels
        self._dir = {}
        self._pending_action = None
        self._pending_marker = None
        self._prev_grid = None
        self._stall = 0
        self._targets_by_color = {}
        self._targets_locked = False
        self._settled = False
        self._blocked = set()
        self._claimed = set()
        self._placed = []
        self._shape_rel = None
        self._sep_pending = False
        self._sep_steps = 0
        self._l4_stations = {}
        self._l4_station_boxes = []
        self._l4_stations_locked = False
        self._l4_pieces = None
        self._l4_sel = 0
        self._l4_assign = {}
        self._l4_blocked = set()
        self._l4_last_move = None
        self._l4_moved_id = 0
        self._l4_moved_cen = None

    def _lock_targets(self, grid: tuple[tuple[int, ...], ...]) -> None:
        by_color: dict[int, list[Cell]] = {}
        for r, c in _target_boxes(grid):
            by_color.setdefault(grid[r][c], []).append((r, c))
        self._targets_by_color = by_color
        self._targets_locked = True

    def _observe(self, grid: tuple[tuple[int, ...], ...]) -> None:
        action = self._pending_action
        before_marker = self._pending_marker
        self._pending_action = None
        self._pending_marker = None
        if action is None or action not in (1, 2, 3, 4) or before_marker is None:
            return
        marker = self._marker(grid)
        if marker is None:
            return
        dr = marker[0] - before_marker[0]
        dc = marker[1] - before_marker[1]
        if dr or dc:
            self._dir[action] = (_sign(dr), _sign(dc))
            self._dir_global[action] = (_sign(dr), _sign(dc))
        else:
            # The marker did not move: this action is blocked (a wall / edge)
            # from ``before_marker``. Remember it so the covering planner
            # switches to the other axis instead of hammering the wall.
            self._blocked.add((before_marker, action))

    # ── perception ──────────────────────────────────────────────────────

    def _marker(self, grid: tuple[tuple[int, ...], ...]) -> Cell | None:
        h = len(grid)
        w = len(grid[0]) if grid else 0
        for r in range(h):
            for c in range(w):
                if grid[r][c] == _SELECTION_COLOR:
                    return (r, c)
        return None

    def _active_movable(self, grid: tuple[tuple[int, ...], ...], marker: Cell) -> tuple[int, frozenset[Cell]] | None:
        """The SELECTED movable's colour and full cell set: the colour-4-gap-
        bridged connected component whose CENTROID is nearest the selection
        marker.

        The engine stamps the marker at the selected movable's geometric
        CENTRE, so centroid-proximity names it unambiguously. The earlier rule
        (largest region touching a marker NEIGHBOUR) picked the wrong piece
        whenever two movables overlap near the marker: a big sparse cross's
        gap-bridged body reaches the marker of a DIFFERENT, smaller movable and
        won the size tie, so the planner drove the cross's offset while the
        engine moved the other piece — an endless oscillation. Centroid-nearest
        also rejects the HUD (step bar / letterbox) for free: their centroids
        sit far from any movable's marker."""
        bg = most_common_color(grid)
        regions = find_regions(grid, background=(bg, _BORDER_COLOR, _SELECTION_COLOR), gap=1)
        best: Region | None = None
        best_d: int | None = None
        for reg in regions:
            cells = reg["cells"]
            if len(cells) < 8:
                # Gate centres are size-1; movables are dozens of px. The floor
                # keeps a stray gate pixel from ever reading as the movable.
                continue
            cy = sum(c[0] for c in cells) / len(cells)
            cx = sum(c[1] for c in cells) / len(cells)
            d = round(abs(cy - marker[0]) + abs(cx - marker[1]))
            if best_d is None or d < best_d:
                best_d = d
                best = reg
        if best is None:
            return None
        return (best["color"], best["cells"])  # type: ignore[return-value]

    # ── planning ────────────────────────────────────────────────────────

    def _decide(self, grid: tuple[tuple[int, ...], ...], move_ids: list[int], can_cycle: bool) -> GameAction:
        if not move_ids:
            return reset_action()
        if not self._settled:
            # Let the level-load camera transition resolve before reading the
            # gates. A selection cycle (ACTION5) settles the render without
            # moving any piece; when cycling is unavailable, a probe move does
            # the same at the cost of a 3px displacement of the active movable.
            self._settled = True
            if can_cycle:
                return simple_action(5)
            return self._probe(self._marker(grid), move_ids)
        if not self._targets_locked:
            self._lock_targets(grid)
        if self._levels_seen >= 3:
            # L4+ introduces the CHANGER/recolour mechanic: two mismatched-colour
            # movables must each be routed through a matching-colour station to
            # recolour, then cover their gates (multi-piece 2-phase FSM under a
            # colour collision). Gated on level index so L1/L2/L3 stay identical.
            return self._decide_l4(grid, move_ids, can_cycle)
        if self._levels_seen >= 2:
            # Deep levels merge several same-colour movables into one region; the
            # single-piece covering spine below cannot address them. Route to the
            # separation-and-claim controller (gated on level index so L1/L2 are
            # byte-identical).
            return self._decide_multi(grid, move_ids, can_cycle)
        marker = self._marker(grid)
        if marker is None:
            return self._probe(marker, move_ids)
        active = self._active_movable(grid, marker)
        if active is None:
            return self._probe(marker, move_ids)
        color, shape = active
        targets = self._targets_by_color.get(color, [])
        if not targets:
            # This movable matches no locked target — cycle to the other one.
            return simple_action(5) if can_cycle else self._probe(marker, move_ids)

        offsets = covering_offsets(list(shape), targets)
        if not offsets:
            return simple_action(5) if can_cycle else self._probe(marker, move_ids)
        # The single nearest covering translation of the movable's shape onto
        # its locked targets (a full solve reaches offset (0, 0) — the shape
        # then covers every same-colour target).
        dr, dc = min(offsets, key=lambda o: abs(o[0]) + abs(o[1]))
        if dr == 0 and dc == 0:
            # This movable is placed. NEVER disturb it (a move would un-cover
            # it and the two movables must be covered simultaneously to win) —
            # cycle to work the other movable; when both are placed the engine
            # wins.
            return simple_action(5) if can_cycle else self._probe(marker, move_ids)

        # Measure EVERY move direction before covering-navigating. Without this,
        # a piece whose larger covering axis is a still-unmeasured direction
        # never learns it: ``_covering_move`` keeps returning a move on the
        # smaller, already-measured axis, so that axis is the only one ever
        # exercised and the piece oscillates around an off-grid target forever
        # (measured: the diamond, needing LEFT, only ever learned up/down and
        # never converged). One probe per unmeasured direction (≤3 extra steps,
        # paid once per level since ``_dir`` is action→world-direction and
        # shared across pieces) unblocks efficient two-axis navigation. Safe:
        # only reached for an UNPLACED active piece, so it never disturbs a
        # piece already covering its gates.
        untried = [a for a in move_ids if a not in self._dir]
        if untried:
            return self._probe(marker, move_ids)

        move = self._covering_move(dr, dc, marker, move_ids)
        if move is not None:
            return move
        # Every covering axis is blocked: cycle to work the other movable.
        return simple_action(5) if can_cycle else self._probe(marker, move_ids)

    def _covering_move(self, dr: int, dc: int, marker: Cell, move_ids: list[int]) -> GameAction | None:
        """The measured move that reduces the larger covering axis and is not
        known-blocked from ``marker``; falls back to the other axis when the
        preferred one is walled."""
        candidates: list[tuple[int, Cell]] = []
        if dr:
            candidates.append((abs(dr), (_sign(dr), 0)))
        if dc:
            candidates.append((abs(dc), (0, _sign(dc))))
        candidates.sort(reverse=True)
        for _mag, want in candidates:
            move = self._move_for(want, move_ids)
            if move is not None and (marker, move) not in self._blocked:
                return self._issue(move, marker)
        return None

    def _move_for(self, want: Cell, move_ids: list[int]) -> int | None:
        for action, sign in self._dir.items():
            if action in move_ids and sign == want:
                return action
        return None

    def _issue(self, action: int, marker: Cell | None) -> GameAction:
        self._pending_action = action
        self._pending_marker = marker
        return simple_action(action)

    def _probe(self, marker: Cell | None, move_ids: list[int]) -> GameAction:
        untried = [a for a in move_ids if a not in self._dir]
        action = untried[0] if untried else move_ids[0]
        return self._issue(action, marker)

    # ── L3+ separation-and-claim controller ─────────────────────────────

    def _all_gates(self) -> list[Cell]:
        return [c for cells in self._targets_by_color.values() for c in cells]

    def _vert_move(self, move_ids: list[int]) -> int:
        """A measured VERTICAL move (UP preferred) — perpendicular to a
        horizontal merge seam, so :func:`separate_by_motion` isolates the moved
        piece cleanly (a move parallel to an elongated neighbour over-includes)."""
        for want in ((-1, 0), (1, 0)):
            a = self._move_for(want, move_ids)
            if a is not None:
                return a
        return move_ids[0]

    def _decide_multi(self, grid: tuple[tuple[int, ...], ...], move_ids: list[int], can_cycle: bool) -> GameAction:
        """Separate merged same-colour pieces by motion, then claim gates piece
        by piece. Learn each active piece's shape ONCE from a perpendicular
        separating move, drive it to the translation covering the most still-
        unclaimed gates, freeze those gates, and cycle to the next piece."""
        bg = most_common_color(grid)
        marker = self._marker(grid)
        if marker is None:
            return self._probe(marker, move_ids)
        if any(a not in self._dir for a in move_ids):
            return self._probe(marker, move_ids)  # measure all move directions once

        unclaimed = [g for g in self._all_gates() if g not in self._claimed]
        if not unclaimed:
            return simple_action(5) if can_cycle else self._probe(marker, move_ids)

        if self._shape_rel is None:
            sep_cells: frozenset[Cell] = frozenset()
            if self._sep_pending and self._prev_grid is not None:
                sep = separate_by_motion(
                    self._prev_grid, grid, background=(bg, _BORDER_COLOR, _SELECTION_COLOR)
                )
                sep_cells = sep["cells"]  # type: ignore[assignment]
            if sep_cells and self._marker_within(sep_cells, marker):
                # Anchor the isolated piece to the marker (colour-0 at its centre,
                # excluded from the colour set) so it can be tracked without
                # re-separating every step.
                self._shape_rel = frozenset((r - marker[0], c - marker[1]) for r, c in sep_cells)
                self._sep_pending = False
                self._sep_steps = 0
            else:
                self._sep_pending = True
                self._sep_steps += 1
                if self._sep_steps > 10:
                    self._sep_pending = False
                    self._sep_steps = 0
                    return simple_action(5) if can_cycle else self._probe(marker, move_ids)
                vm = self._vert_move(move_ids)
                if (marker, vm) in self._blocked:
                    other = self._move_for((1, 0) if self._dir.get(vm) == (-1, 0) else (-1, 0), move_ids)
                    vm = other if other is not None else vm
                return self._issue(vm, marker)

        cur = [(marker[0] + dr, marker[1] + dc) for dr, dc in self._shape_rel]
        best = max_coverage_offset(cur, unclaimed)
        if best is None or not best[1]:
            self._shape_rel = None  # this piece reaches no unclaimed gate; try another
            return simple_action(5) if can_cycle else self._probe(marker, move_ids)
        (odr, odc), covered = best
        if (odr, odc) == (0, 0):
            for i in covered:
                self._claimed.add(unclaimed[i])
            self._placed.append(frozenset(cur))
            self._shape_rel = None  # placed; never re-drive it — cycle to the next piece
            return simple_action(5) if can_cycle else self._probe(marker, move_ids)
        move = self._covering_move(odr, odc, marker, move_ids)
        if move is not None:
            return move
        self._shape_rel = None  # every covering axis walled; work another piece
        return simple_action(5) if can_cycle else self._probe(marker, move_ids)

    @staticmethod
    def _marker_within(cells: frozenset[Cell], marker: Cell) -> bool:
        """Whether the selection marker sits inside the bounding box of a
        motion-isolated piece — the acceptance test that the separation captured
        the SELECTED piece (not a stray static fragment)."""
        rs = [r for r, _c in cells]
        cs = [c for _r, c in cells]
        return min(rs) <= marker[0] <= max(rs) and min(cs) <= marker[1] <= max(cs)

    # ── L4+ recolour-routing controller ─────────────────────────────────

    def _l4_movables(self, grid: tuple[tuple[int, ...], ...]) -> list[dict[str, Any]]:
        """The movable sprites: connected colour regions that are NOT gate
        boxes, NOT changer-station swatches, and NOT the 1-px HUD bars. Gate
        cells are subtracted so a RECOLOURED movable (now sharing its colour
        with its gates) is not merged with them; station swatches are rejected
        by the station boxes; the HUD/letterbox by their 1-px thickness."""
        bg = most_common_color(grid)
        gate_cells = set(self._all_gates())
        exclude = {bg, _BORDER_COLOR, _STATION_BORDER, _SELECTION_COLOR}
        out: list[dict[str, Any]] = []
        for reg in find_regions(grid, background=bg, gap=1):
            if reg["color"] in exclude:
                continue
            cells = frozenset(reg["cells"]) - gate_cells
            if not (20 <= len(cells) <= 90):
                continue
            rs = [r for r, _c in cells]
            cs = [c for _r, c in cells]
            if max(rs) - min(rs) < 3 or max(cs) - min(cs) < 3:
                continue  # a HUD/letterbox line, not a 2-D sprite
            cen = (sum(rs) // len(cells), sum(cs) // len(cells))
            if _in_boxes(cen, self._l4_station_boxes, pad=1):
                continue  # a station swatch
            out.append({"color": reg["color"], "cells": cells, "centroid": cen})
        return out

    def _l4_track(self, movs: list[dict[str, Any]]) -> None:
        """Persistently match parsed movs to the two tracked pieces by OPTIMAL
        (min-total-distance) centroid assignment — greedy per-piece matching
        swaps identities when pieces pass close. Colour is updated only to a
        KNOWN colour (a gate colour or an original assign colour) so a mid-flood
        transient colour keeps the piece's last stable colour and identity
        survives a recolour."""
        pieces = self._l4_pieces
        if pieces is None:
            return
        known = set(self._targets_by_color) | set(self._l4_assign)
        if len(pieces) == 2 and len(movs) == 2:
            def cost(pi: int, mi: int) -> int:
                a, b = pieces[pi]["centroid"], movs[mi]["centroid"]
                return abs(a[0] - b[0]) + abs(a[1] - b[1])
            pairs = [(0, 0), (1, 1)] if cost(0, 0) + cost(1, 1) <= cost(0, 1) + cost(1, 0) else [(0, 1), (1, 0)]
        else:
            pairs = []
            used: set[int] = set()
            for pi, p in enumerate(pieces):
                best, bd = None, None
                for mi, m in enumerate(movs):
                    if mi in used:
                        continue
                    d = abs(m["centroid"][0] - p["centroid"][0]) + abs(m["centroid"][1] - p["centroid"][1])
                    if bd is None or d < bd:
                        bd, best = d, mi
                if best is not None and bd <= 16:
                    used.add(best)
                    pairs.append((pi, best))
        for pi, mi in pairs:
            m = movs[mi]
            pieces[pi]["centroid"] = m["centroid"]
            pieces[pi]["cells"] = m["cells"]
            if m["color"] in known:
                pieces[pi]["color"] = m["color"]

    def _l4_assign_pieces(self, gate_colors: list[int]) -> None:
        """Choose which movable recolours to which gate colour: the permutation
        where BOTH movables fully cover their gate colour (via
        ``max_coverage_offset``); fall back to the higher-total-coverage
        permutation. Keyed on ORIGINAL movable colour (post-recolour the colour
        equals the gate colour, so the mapping is unambiguous)."""
        pieces = self._l4_pieces
        if pieces is None or len(pieces) != 2 or len(gate_colors) != 2:
            return
        (ca, ma), (cb, mb) = (pieces[0]["color"], pieces[0]), (pieces[1]["color"], pieces[1])
        g0, g1 = gate_colors

        def cov(m: dict[str, Any], g: int) -> int:
            best = max_coverage_offset(list(m["cells"]), self._targets_by_color[g])
            return len(best[1]) if best else 0

        def full(m: dict[str, Any], g: int) -> bool:
            return cov(m, g) == len(self._targets_by_color[g])

        opt1 = full(ma, g0) and full(mb, g1)
        opt2 = full(ma, g1) and full(mb, g0)
        if opt2 and not opt1:
            self._l4_assign = {ca: g1, cb: g0}
        elif opt1 or (cov(ma, g0) + cov(mb, g1) >= cov(ma, g1) + cov(mb, g0)):
            self._l4_assign = {ca: g0, cb: g1}
        else:
            self._l4_assign = {ca: g1, cb: g0}

    @staticmethod
    def _l4_recolour_want(cen: Cell, scen: Cell) -> Cell:
        """Toward the target changer station: COLUMN-align first (horizontal, in
        the station-free interior), then move VERTICALLY along the target's
        column into it. Every station sits on the top/bottom edge row, so this
        provably avoids re-recolouring on a different-colour station en route."""
        if abs(cen[1] - scen[1]) > 3:  # the box only needs to overlap the column
            return (0, _sign(scen[1] - cen[1]))
        return (_sign(scen[0] - cen[0]), 0)

    def _l4_issue_move(self, cen: Cell, odr: int, odc: int, move_ids: list[int]) -> int | None:
        """The measured move reducing the larger covering axis that is not
        known-walled from this centroid; falls back to the other axis."""
        cands: list[tuple[int, Cell]] = []
        if odr:
            cands.append((abs(odr), (_sign(odr), 0)))
        if odc:
            cands.append((abs(odc), (0, _sign(odc))))
        cands.sort(reverse=True)
        key = (round(cen[0] / _CELL_PX), round(cen[1] / _CELL_PX))
        for _mag, want in cands:
            a = self._move_for(want, move_ids)
            if a is not None and (key, a) not in self._l4_blocked:
                return a
        return None

    def _l4_emit(self, action: int, cen: Cell) -> GameAction:
        """Issue an action, cycling selection on ACTION5 and recording a
        directional move for next-frame wall detection."""
        if action == 5:
            if self._l4_pieces is not None and len(self._l4_pieces) == 2:
                self._l4_sel = 1 - self._l4_sel
            self._l4_last_move = None
        else:
            self._l4_last_move = ((round(cen[0] / _CELL_PX), round(cen[1] / _CELL_PX)), action)
            self._l4_moved_id = self._l4_sel
            self._l4_moved_cen = cen
        return simple_action(action)

    def _decide_l4(self, grid: tuple[tuple[int, ...], ...], move_ids: list[int], can_cycle: bool) -> GameAction:
        """Two mismatched-colour movables each routed through a matching-colour
        changer station to recolour, then covering their gates. Recolour BOTH
        first (they end at opposite-edge stations, kept SEPARATED so the marker
        is never occluded) THEN cover both — the marker-anchored covering spine
        converges only while pieces do not overlap. Validated live: L4 wins."""
        if not move_ids:
            return reset_action()
        marker = self._marker(grid)
        # Reuse the level-invariant move map measured on L1-L3 (probing at L4
        # risks recolouring a movable against a station, below). Only probe if
        # a direction was never seen — and probe LAST, after the safe reuse.
        for a, v in self._dir_global.items():
            self._dir.setdefault(a, v)
        if any(a not in self._dir for a in move_ids):
            return self._probe(marker, move_ids)
        if not self._l4_stations_locked:
            self._l4_stations, self._l4_station_boxes = _station_boxes(grid)
            self._l4_stations_locked = True
        gate_colors = sorted(self._targets_by_color)

        if self._l4_pieces is None:
            movs = self._l4_movables(grid)
            if len(movs) < 2:
                return self._probe(marker, move_ids)
            self._l4_pieces = [
                {"color": m["color"], "cells": m["cells"], "centroid": m["centroid"], "shape_rel": None}
                for m in movs[:2]
            ]
            self._l4_sel = 0
            if marker is not None:
                self._l4_sel = min(
                    range(2),
                    key=lambda i: abs(self._l4_pieces[i]["centroid"][0] - marker[0])
                    + abs(self._l4_pieces[i]["centroid"][1] - marker[1]),
                )
            self._l4_assign_pieces(gate_colors)

        movs = self._l4_movables(grid)
        self._l4_track(movs)
        pieces = self._l4_pieces
        assert pieces is not None

        # wall detection: the piece the last move drove did not shift -> walled.
        if self._l4_last_move is not None and self._l4_moved_cen is not None:
            if pieces[self._l4_moved_id]["centroid"] == self._l4_moved_cen:
                self._l4_blocked.add(self._l4_last_move)
            self._l4_last_move = None

        # marker-authoritative selection (pieces kept separated -> visible).
        if marker is not None:
            inside = []
            for i, pp in enumerate(pieces):
                rs = [r for r, _c in pp["cells"]]
                cs = [c for _r, c in pp["cells"]]
                if rs and min(rs) - 1 <= marker[0] <= max(rs) + 1 and min(cs) - 1 <= marker[1] <= max(cs) + 1:
                    inside.append((abs(pp["centroid"][0] - marker[0]) + abs(pp["centroid"][1] - marker[1]), i))
            if inside:
                self._l4_sel = min(inside)[1]

        p = pieces[self._l4_sel]
        color, cen, cells = p["color"], p["centroid"], p["cells"]

        def cycle() -> GameAction:
            return self._l4_emit(5, cen) if can_cycle else self._probe(marker, move_ids)

        if not all(pp["color"] in gate_colors for pp in pieces):
            # RECOLOUR PHASE — recolour both first, ending at opposite stations.
            if color in gate_colors:
                return cycle()  # this one done; select the other to recolour
            if color in self._l4_assign:
                scen = self._l4_stations.get(self._l4_assign[color])
                if scen is None:
                    return cycle()
                dr, dc = self._l4_recolour_want(cen, scen)
                a = self._move_for((dr, dc), move_ids)
                return self._l4_emit(a, cen) if a is not None else cycle()
            return cycle()  # transient flood colour: cycle advances the flood

        # COVER PHASE — MARKER-anchor the shape once (the marker is the sprite's
        # exact centre; a parse centroid quantises 1 px and stalls on the 3-px
        # move grid), then drive the locked shape to cover ALL its gates.
        need = self._targets_by_color[color]
        anchor = marker if marker is not None else cen
        if p["shape_rel"] is None:
            if marker is None:
                return cycle()  # wait for a clean marker to lock the shape
            p["shape_rel"] = frozenset((r - marker[0], c - marker[1]) for r, c in cells)
        cur = {(anchor[0] + dr, anchor[1] + dc) for dr, dc in p["shape_rel"]}
        if sum(1 for gt in need if gt in cur) == len(need):
            return cycle()  # already covering all its gates: hold, work the other
        best = max_coverage_offset(list(cur), need)
        if best is None:
            return cycle()
        (odr, odc), _cov = best
        a = self._l4_issue_move(cen, odr, odc, move_ids)
        return self._l4_emit(a, cen) if a is not None else cycle()
