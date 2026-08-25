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

from collections import Counter, deque
from collections.abc import Iterable
from itertools import permutations
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
    grid_shortest_path,
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


# ── L5 helpers (three movables, uneven 3→2 set-cover, mid-edge station) ──
# L5 breaks three assumptions the two-piece L4 FSM hard-codes: THREE movables,
# a 3-movable→2-colour set-cover (not a 1:1 pairing), and a MID-EDGE changer
# station that a naive edge-row route would clip. The helpers below are frame-
# only (no sprite-tag read); the controller is ``Adapter._decide_l5``. Decoded
# + validated live in ``scratchpad/re86_l5_ctrl2.py`` before this port.


def _l5_gate_colors(
    grid: tuple[tuple[int, ...], ...],
    station_boxes: list[tuple[int, int, int, int]],
    station_colors: set[int],
    movable_colors: set[int],
) -> set[int]:
    """The gate-canvas target colours: station swatch colours that also appear
    as ISOLATED (≤4 px) marks OUTSIDE every station box AND are not a current
    movable colour. The win-check canvas paints each required gate cell in the
    colour a movable must recolour INTO, and a movable can only reach a colour
    that has a matching changer station — so the gate colours are the station
    colours present as loose marks. Excluding the movables' OWN colours is
    essential: a movable's thin sprite arms shed ≤4-px fragments in its colour
    (11/14 here are ALSO station colours), which would otherwise be miscounted
    as gate cells and grow without bound as the piece moves. A movable's target
    gate colour always differs from its original colour (that is the point of
    recolouring), so the exclusion never drops a real gate colour. Derived, not
    hardcoded (measured to yield {8, 9} on this env's L5)."""
    found: set[int] = set()
    for reg in find_regions(grid, background=None, gap=0):
        col = reg["color"]
        if col not in station_colors or col in movable_colors or len(reg["cells"]) > 4:
            continue
        r, c = next(iter(reg["cells"]))
        if _in_boxes((r, c), station_boxes, pad=0):
            continue
        found.add(col)
    return found


def _l5_scan_gates(
    grid: tuple[tuple[int, ...], ...],
    station_boxes: list[tuple[int, int, int, int]],
    gate_colors: set[int],
) -> dict[int, set[Cell]]:
    """Isolated (≤4-px component) gate-canvas cells per gate colour, excluding
    station-box interiors. Movable bodies are dense blobs and a recoloured
    movable's cells read as a large same-colour region — the size floor keeps
    only the loose gate marks. Two of the gate cells start OCCLUDED by a movable
    body, so the caller ACCUMULATES this across frames as pieces move."""
    found: dict[int, set[Cell]] = {c: set() for c in gate_colors}
    for reg in find_regions(grid, background=None, gap=0):
        col = reg["color"]
        if col not in gate_colors or len(reg["cells"]) > 4:
            continue
        r, c = next(iter(reg["cells"]))
        if _in_boxes((r, c), station_boxes, pad=0):
            continue
        found[col].update(reg["cells"])
    return found


def _l5_movables(
    grid: tuple[tuple[int, ...], ...],
    gate_cells: set[Cell],
    station_boxes: list[tuple[int, int, int, int]],
    subtract_boxes: bool,
) -> list[dict[str, Any]]:
    """Movable sprites for L5: colour regions that are not gates/stations/HUD,
    with gate cells subtracted. When ``subtract_boxes`` is set, station-box
    pixels are subtracted too (by BOX, not colour) so a recoloured body abutting
    its same-colour station keeps its true shape/centroid — the L4 gate-cell-
    subtraction pattern extended to the shared corner station."""
    bg = most_common_color(grid)
    exclude = {bg, _BORDER_COLOR, _STATION_BORDER, _SELECTION_COLOR}
    out: list[dict[str, Any]] = []
    for reg in find_regions(grid, background=bg, gap=1):
        if reg["color"] in exclude:
            continue
        cells = frozenset(
            (r, c)
            for (r, c) in reg["cells"]
            if (r, c) not in gate_cells and not (subtract_boxes and _in_boxes((r, c), station_boxes, pad=1))
        )
        if not (20 <= len(cells) <= 120):
            continue
        rs = [r for r, _c in cells]
        cs = [c for _r, c in cells]
        if max(rs) - min(rs) < 3 or max(cs) - min(cs) < 3:
            continue
        cen = (sum(rs) // len(cells), sum(cs) // len(cells))
        if not subtract_boxes and _in_boxes(cen, station_boxes, pad=1):
            continue
        out.append({"color": reg["color"], "cells": cells, "cen": cen})
    return out


def _l5_cluster(cells: Iterable[Cell], radius: int = 20) -> list[list[Cell]]:
    """Group gate cells into spatial clusters (single-link, Manhattan radius).
    The colour-9 gate cells fall into TWO clusters (a top pair and a bottom
    quad) that must be covered by two DIFFERENT movables."""
    clusters: list[list[Cell]] = []
    for cell in cells:
        for cl in clusters:
            if any(abs(cell[0] - x) + abs(cell[1] - y) <= radius for x, y in cl):
                cl.append(cell)
                break
        else:
            clusters.append([cell])
    return clusters


def _l5_hazard_between(
    sbox: dict[int, tuple[int, int, int, int]],
    own_color: int,
    marker: Cell,
    crow: int,
    half: int,
) -> bool:
    """True if a station of a colour OTHER than ``own_color`` lies vertically
    between the piece (centre ``marker``) and its cluster (row ``crow``) AND near
    the piece's current column — i.e. the fat body would clip that station on a
    vertical leg and re-recolour. Every station sits on an EDGE column, so this
    only fires on a left/right-column ascent past a mid-edge station (station-14,
    mid-left, for the top colour-9 piece routing between the bottom-left corner
    station-9 and the top cluster). The board CENTRE is station-free, so the cure
    is to move horizontally to the cluster's centre column first."""
    lo, hi = sorted((marker[0], crow))
    for c, b in sbox.items():
        if c == own_color:
            continue
        sr, sc = (b[0] + b[2]) // 2, (b[1] + b[3]) // 2
        if lo - half <= sr <= hi + half and abs(sc - marker[1]) <= half + _CELL_PX:
            return True
    return False


def _l5_route(
    pos: Cell,
    goal_px: Cell,
    half: int,
    avoid_boxes: list[tuple[int, int, int, int]],
    walls: set[Cell],
    dirmap: dict[int, Cell],
    move_ids: list[int],
) -> int | None:
    """One action stepping the CENTRE from ``pos`` toward pixel ``goal_px`` via
    ``kernels.grid_shortest_path`` over a 3-px-cell passability grid with
    ``avoid_boxes`` inflated by ``half`` (the body half-extent) and learned
    ``walls`` impassable. Returns the measured move id or ``None``."""
    n = 64 // _CELL_PX + 1
    passable = [[True] * n for _ in range(n)]
    for (r0, c0, r1, c1) in avoid_boxes:
        for i in range(max(0, (r0 - half) // _CELL_PX), min(n, (r1 + half) // _CELL_PX + 1)):
            for j in range(max(0, (c0 - half) // _CELL_PX), min(n, (c1 + half) // _CELL_PX + 1)):
                passable[i][j] = False
    for (wi, wj) in walls:
        if 0 <= wi < n and 0 <= wj < n:
            passable[wi][wj] = False
    start = (pos[0] // _CELL_PX, pos[1] // _CELL_PX)
    goal = (min(n - 1, max(0, goal_px[0] // _CELL_PX)), min(n - 1, max(0, goal_px[1] // _CELL_PX)))
    passable[start[0]][start[1]] = True
    passable[goal[0]][goal[1]] = True
    path = grid_shortest_path(passable, start, goal)
    if not path or len(path) < 2:
        return None
    want = (path[1][0] - start[0], path[1][1] - start[1])
    for a, sign in dirmap.items():
        if a in move_ids and sign == want:
            return a
    return None


# ── L6 helpers (reshape-and-place; two movables + a static colour-1 obstacle) ──
# L6 has NO changer stations. movable-11 is a hollow SQUARE outline that reshapes
# perimeter-conserving on obstacle collision (aligned rows + right pushes drive
# 19×19→28×10); movable-9 is a CROSS that SHIFTS its vertical/horizontal bar ±3
# WITHIN a fixed 25×25 frame on collision (a horizontal collision moves the vbar,
# a vertical one the hbar), driven through the collision-free corridors to cover
# its four target cells. Frame-only; source read only informed the mechanic.
_OBSTACLE_COLOR = 1


def _l6_obstacle_box(grid: tuple[tuple[int, ...], ...]) -> tuple[int, int, int, int] | None:
    """The static colour-1 central obstacle's bbox (r0, c0, r1, c1), or None. It is
    the reshape anchor — a push that pixel-overlaps it triggers the reshape."""
    bg = most_common_color(grid)
    for reg in find_regions(grid, background=bg, gap=1):
        if reg["color"] == _OBSTACLE_COLOR and len(reg["cells"]) > 10:
            rs = [r for r, _c in reg["cells"]]
            cs = [c for _r, c in reg["cells"]]
            return (min(rs), min(cs), max(rs), max(cs))
    return None


def _l6_bbox(cells: Iterable[Cell]) -> tuple[int, int, int, int]:
    rs = [r for r, _c in cells]
    cs = [c for _r, c in cells]
    return min(rs), max(rs), min(cs), max(cs)


def _l6_cross_state(cells: frozenset[Cell]) -> dict[str, int]:
    """Frame bbox + vertical-bar abs col + horizontal-bar abs row + their
    frame-relative positions, for the movable-9 cross. The vbar/hbar are the
    (near-)full columns/rows of the fixed 25×25 frame; the ±3 collision shift
    repositions them, so their frame-relative index is the reshape control."""
    r0, r1, c0, c1 = _l6_bbox(cells)
    h, w = r1 - r0 + 1, c1 - c0 + 1
    vcols = [c for c in range(c0, c1 + 1) if sum((r, c) in cells for r in range(r0, r1 + 1)) >= h * 0.7]
    hrows = [r for r in range(r0, r1 + 1) if sum((r, c) in cells for c in range(c0, c1 + 1)) >= w * 0.7]
    va = vcols[len(vcols) // 2] if vcols else c0
    ha = hrows[len(hrows) // 2] if hrows else r0
    return {"r0": r0, "r1": r1, "c0": c0, "c1": c1, "va": va, "ha": ha, "vrel": va - c0, "hrel": ha - r0}


# ── L7 (recolour + bar-shift/reshape + place hybrid) ─────────────────────────
# L7 brings the changer stations BACK (unlike L6) plus the single colour-1
# obstacle, and THREE movables whose colours match NO target: each must route to
# its matching-colour station and recolour, then bar-shift/reshape against the
# obstacle, then place on its matching-colour target, all three covering
# SIMULTANEOUSLY (the snapshot win). The CROSS bar-shift is planned by BFS over a
# faithful offline simulator of the engine's collision handler (source
# ``ucpbzrcoui`` else-branch @2004-2059): a push colliding with the obstacle
# shifts the bar OPPOSITE to the obstacle-occupied axis, or pins/translates
# otherwise. Decoded + live-validated (22/22 scripted pushes match the engine) in
# ``scratchpad/re86_l7_sim.py`` + ``re86_l7_simval.py``; the full 3-leg clear is
# ``scratchpad/re86_l7_full.py``. All targets/dims are FRAME-DERIVED.
_L7_STEP = 3


def _l7_cross_collides(
    x: int, y: int, vrel: int, hrel: int, w: int, h: int, ob: tuple[int, int, int, int]
) -> bool:
    """A cross pixel (its full vbar column or hbar row) intersects the obstacle."""
    r0, c0, r1, c1 = ob
    vbar_col = x + vrel
    hbar_row = y + hrel
    vbar_hits = c0 <= vbar_col <= c1 and y <= r1 and y + h - 1 >= r0
    hbar_hits = r0 <= hbar_row <= r1 and x <= c1 and x + w - 1 >= c0
    return vbar_hits or hbar_hits


def _l7_cross_sim(
    state: tuple[int, int, int, int], dx: int, dy: int, w: int, h: int, ob: tuple[int, int, int, int]
) -> tuple[int, int, int, int]:
    """One push of the re86 CROSS handler, in (x=col, y=row, vrel, hrel) space.
    Bounds-checked on the sprite CENTRE (``rtivumgcjd``); on an obstacle collision
    the pushed bar SETS (frame reverts, bar shifts) when the OTHER axis's bar is in
    the obstacle, PINS (frame translates, abs bar fixed) when its OWN bar is, and
    is BLOCKED when both are; otherwise a free translation."""
    x, y, vrel, hrel = state
    r0, c0, r1, c1 = ob
    nx, ny = x + dx, y + dy
    if not (0 <= nx + w // 2 < 64 and 0 <= ny + h // 2 < 64):
        return (x, y, vrel, hrel)
    if not _l7_cross_collides(nx, ny, vrel, hrel, w, h, ob):
        return (nx, ny, vrel, hrel)
    vbar_in = c0 <= nx + vrel <= c1
    hbar_in = r0 <= ny + hrel <= r1
    if dx != 0:
        a = -_L7_STEP if dx > 0 else _L7_STEP
        b = _L7_STEP if dx > 0 else -_L7_STEP
        can_a = (vrel > 0) if dx > 0 else (vrel < w - 2)
        can_b = (vrel < w - 2) if dx > 0 else (vrel > 0)
        if vbar_in and hbar_in:
            return (x, y, vrel, hrel)
        if vbar_in:
            return (nx, ny, vrel + a, hrel) if can_a else (x, y, vrel, hrel)
        if hbar_in:
            return (x, y, vrel + b, hrel) if can_b else (x, y, vrel, hrel)
        return (nx, ny, vrel, hrel)
    a = -_L7_STEP if dy > 0 else _L7_STEP
    b = _L7_STEP if dy > 0 else -_L7_STEP
    can_a = (hrel > 0) if dy > 0 else (hrel < h - 2)
    can_b = (hrel < h - 2) if dy > 0 else (hrel > 0)
    if hbar_in and vbar_in:
        return (x, y, vrel, hrel)
    if hbar_in:
        return (nx, ny, vrel, hrel + a) if can_a else (x, y, vrel, hrel)
    if vbar_in:
        return (x, y, vrel, hrel + b) if can_b else (x, y, vrel, hrel)
    return (nx, ny, vrel, hrel)


# push -> (dx=col, dy=row) and -> (dr,dc) direction for the measured move map.
_L7_SIM_DIRS = {1: (0, -_L7_STEP), 2: (0, _L7_STEP), 3: (-_L7_STEP, 0), 4: (_L7_STEP, 0)}
_L7_SIM_WANT = {1: (-1, 0), 2: (1, 0), 3: (0, -1), 4: (0, 1)}


def _l7_bfs_plan(
    start: tuple[int, int, int, int],
    goal: tuple[int, int, int, int],
    w: int,
    h: int,
    ob: tuple[int, int, int, int],
    valid: Any = None,
    max_nodes: int = 200000,
) -> list[Cell] | None:
    """BFS a push sequence (list of (dr,dc) directions) from ``start`` to ``goal``
    over the exact cross simulator; ``valid(state)`` prunes states the plan must
    never enter (e.g. rising into the station row)."""
    start = tuple(start)  # type: ignore[assignment]
    goal = tuple(goal)  # type: ignore[assignment]
    if start == goal:
        return []
    seen = {start}
    q: deque[tuple[tuple[int, int, int, int], list[Cell]]] = deque([(start, [])])
    while q and len(seen) < max_nodes:
        st, path = q.popleft()
        for a, (dx, dy) in _L7_SIM_DIRS.items():
            ns = _l7_cross_sim(st, dx, dy, w, h, ob)
            if ns in seen or (valid is not None and not valid(ns)):
                continue
            if ns == goal:
                return path + [_L7_SIM_WANT[a]]
            seen.add(ns)
            q.append((ns, path + [_L7_SIM_WANT[a]]))
    return None


def _l7_regions(
    grid: tuple[tuple[int, ...], ...], station_boxes: list[tuple[int, int, int, int]]
) -> list[dict[str, Any]]:
    """Movable regions for L7 (frame-only): station-box pixels subtracted so a
    recoloured piece abutting its same-colour station keeps its shape; excludes
    bg/border/station-border/marker/obstacle. Each entry carries the bbox."""
    bg = most_common_color(grid)
    exclude = {bg, _BORDER_COLOR, _STATION_BORDER, _SELECTION_COLOR, _OBSTACLE_COLOR}
    out: list[dict[str, Any]] = []
    for reg in find_regions(grid, background=bg, gap=1):
        if reg["color"] in exclude:
            continue
        cells = frozenset(c for c in reg["cells"] if not _in_boxes(c, station_boxes, pad=1))
        if len(cells) < 12:
            continue
        rs = [r for r, _c in cells]
        cs = [c for _r, c in cells]
        if max(rs) - min(rs) < 3 or max(cs) - min(cs) < 3:
            continue
        cen = (sum(rs) // len(cells), sum(cs) // len(cells))
        if _in_boxes(cen, station_boxes, pad=1):
            continue
        out.append(
            {"color": reg["color"], "cells": cells, "cen": cen,
             "bbox": (min(rs), max(rs), min(cs), max(cs))}
        )
    return out


def _l7_region_at(
    grid: tuple[tuple[int, ...], ...], marker: Cell, station_boxes: list[tuple[int, int, int, int]]
) -> dict[str, Any] | None:
    """Tightest movable region whose bbox contains the marker (the selected
    piece's live shape once it has separated from the spawn cluster)."""
    best: tuple[dict[str, Any], int] | None = None
    for m in _l7_regions(grid, station_boxes):
        r0, r1, c0, c1 = m["bbox"]
        if r0 - 1 <= marker[0] <= r1 + 1 and c0 - 1 <= marker[1] <= c1 + 1:
            area = (r1 - r0) * (c1 - c0)
            if best is None or area < best[1]:
                best = (m, area)
    return best[0] if best else None


def _l7_full_bars(cells: frozenset[Cell]) -> tuple[int, int]:
    """(#full-height columns, #full-width rows) of a region — distinguishes a
    hollow-rectangle OUTLINE (2 + 2 edges) from a CROSS (1 vbar + 1 hbar)."""
    rs = [r for r, _c in cells]
    cs = [c for _r, c in cells]
    r0, r1, c0, c1 = min(rs), max(rs), min(cs), max(cs)
    h, w = r1 - r0 + 1, c1 - c0 + 1
    full_cols = sum(1 for c in range(c0, c1 + 1) if sum((r, c) in cells for r in range(r0, r1 + 1)) >= h * 0.7)
    full_rows = sum(1 for r in range(r0, r1 + 1) if sum((r, c) in cells for c in range(c0, c1 + 1)) >= w * 0.7)
    return full_cols, full_rows


class Adapter(GameAdapter):
    """Covering-offset greedy delivery composed from admorphiq.kernels."""

    GAME_ID = GAME_ID

    @classmethod
    def _detect_mechanic(cls, latest_frame: Any) -> bool:
        """A delivery / colour-assignment board: cycle-select controls AND target gates.

        1. **Move-and-cycle, no pointer.** ACTION1-4 move the SELECTED piece and ACTION5
           cycles which piece is selected; there is no click at all. That control set is
           shared with two other public games, so it narrows without deciding.
        2. **A selection marker is on the board.** Cycling a selection is only meaningful
           if the board shows which piece is selected — this mechanic marks the selected
           movable's centre in the selection colour.
        3. **Target gates exist.** `_target_boxes` finds colour-bordered gates: a pixel
           flanked by the border colour on a PAIR of opposite sides. A delivery puzzle
           without somewhere to deliver is not this mechanic.
        """
        simple_ids, has_click = available_action_ids(latest_frame)
        if has_click or sorted(simple_ids) != [1, 2, 3, 4, 5]:
            return False
        grid = canonical_layer(latest_frame)
        if not any(_SELECTION_COLOR in row for row in grid):
            return False
        return bool(_target_boxes(grid))

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

        # ── L5 state (three movables, uneven 3→2 set-cover, mid-edge station).
        # Gated on level index (>= 4) so L1-L4 stay byte-identical. ──
        self._l5_settle = 0
        self._l5_locked = False
        self._l5_stations: dict[int, Cell] = {}
        self._l5_station_boxes: list[tuple[int, int, int, int]] = []
        self._l5_sbox: dict[int, tuple[int, int, int, int]] = {}
        self._l5_gate_colors: set[int] = set()
        self._l5_gate_acc: dict[int, set[Cell]] = {}
        self._l5_phase = "reveal"  # "reveal" -> "solve"
        self._l5_reveal_steps = 0
        self._l5_prev_total = -1
        self._l5_stable = 0
        self._l5_pieces: list[dict[str, Any]] | None = None
        self._l5_order: list[int] = []
        # (piece_index, marker_pos, want_dir) of the last directional move, for
        # marker-to-marker wall learning (a move that did not advance ⟹ interior
        # wall at that centre-cell; folded into the piece's passability).
        self._l5_last_move: tuple[int, Cell, Cell] | None = None

        # ── L6 state (reshape-and-place; two movables + a static colour-1
        # obstacle, NO changer stations). Gated on level index (>= 5) + the L6
        # signature so L1-L5 stay byte-identical. movable-11 is a hollow square
        # outline (tag 0036…) that reshapes perimeter-conserving on obstacle
        # collision; movable-9 is a cross that SHIFTS its bars ±3 within a fixed
        # frame on collision. Decoded + validated live in
        # ``scratchpad/re86_l6_solveL6.py`` before this port. ──
        self._l6_settle = 0
        self._l6_locked = False
        self._l6_applies = False
        self._l6_obstacle: tuple[int, int, int, int] | None = None  # r0,c0,r1,c1
        # The two pieces are distinguished by TARGET geometry (frame-only): the
        # OUTLINE piece's four target cells are a rectangle's corners; the CROSS
        # piece's four are a plus (a shared-col pair + a shared-row pair).
        self._l6_cross_color: int | None = None
        self._l6_outline_color: int | None = None
        self._l6_cross_tgt: list[Cell] = []
        self._l6_outline_tgt: list[Cell] = []
        # Cross placement targets, DERIVED from its four tips (never hardcoded):
        # frame top-left (r0_t, c0_t) and the bar frame-relative positions that
        # land the vbar/hbar on the tips' shared col/row.
        self._l6_r0_t = 0
        self._l6_c0_t = 0
        self._l6_vrel_t = 0
        self._l6_hrel_t = 0
        self._l6_size = 25
        self._l6_piece = "cross"  # place the CROSS (corridor bar-control) first, then the OUTLINE
        self._l6_p9 = "vrel"  # vrel → hrel_rise → hrel_left → hrel_down → carry_up → carry_left → done
        self._l6_p11 = "align"  # align → reshape → place → done
        # outline place state (marker-anchored shape + wall learning).
        self._l6_shape_rel: frozenset[Cell] | None = None
        self._l6_walls: set[Cell] = set()
        self._l6_last_move: tuple[Cell, Cell] | None = None  # (marker, want_dir)

        # ── L7 state (recolour + bar-shift/reshape + place hybrid; three
        # mismatched-colour movables + changer stations + a colour-1 obstacle).
        # Gated on level index (>= 6) + the L7 signature (stations present AND a
        # colour-1 obstacle) so L1-L6 stay byte-identical. Identity under the tight
        # spawn overlap is CYCLE-INDEX (a piece's selection-cycle slot never
        # changes, even after recolour); the drive is occlusion-safe (marker None =
        # OCCLUSION, re-issue the current move, never ACTION5). Decoded + validated
        # live in ``scratchpad/re86_l7_*.py`` before this port. ──
        self._l7_settle = 0
        self._l7_locked = False
        self._l7_applies = False
        self._l7_stations: dict[int, Cell] = {}
        self._l7_sbox: dict[int, tuple[int, int, int, int]] = {}
        self._l7_sboxes: list[tuple[int, int, int, int]] = []
        self._l7_obstacle: tuple[int, int, int, int] | None = None
        self._l7_tby: dict[int, list[Cell]] = {}
        self._l7_spawn_cen: dict[int, Cell] = {}
        self._l7_idx_color: list[int] = []
        self._l7_sel = 0
        self._l7_legs: list[dict[str, Any]] = []
        self._l7_leg_i = 0
        self._l7_phase = ""
        self._l7_plan: list[Cell] = []
        self._l7_last_dir: Cell = (-1, 0)
        self._l7_walls: set[Cell] = set()
        self._l7_shape_rel: frozenset[Cell] | None = None
        self._l7_out_last_move: tuple[Cell, Cell] | None = None

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
        self._l5_settle = 0
        self._l5_locked = False
        self._l5_stations = {}
        self._l5_station_boxes = []
        self._l5_sbox = {}
        self._l5_gate_colors = set()
        self._l5_gate_acc = {}
        self._l5_phase = "reveal"
        self._l5_reveal_steps = 0
        self._l5_prev_total = -1
        self._l5_stable = 0
        self._l5_pieces = None
        self._l5_order = []
        self._l5_last_move = None
        self._l6_settle = 0
        self._l6_locked = False
        self._l6_applies = False
        self._l6_obstacle = None
        self._l6_cross_color = None
        self._l6_outline_color = None
        self._l6_cross_tgt = []
        self._l6_outline_tgt = []
        self._l6_r0_t = 0
        self._l6_c0_t = 0
        self._l6_vrel_t = 0
        self._l6_hrel_t = 0
        self._l6_size = 25
        self._l6_piece = "cross"
        self._l6_p9 = "vrel"
        self._l6_p11 = "align"
        self._l6_shape_rel = None
        self._l6_walls = set()
        self._l6_last_move = None
        self._l7_settle = 0
        self._l7_locked = False
        self._l7_applies = False
        self._l7_stations = {}
        self._l7_sbox = {}
        self._l7_sboxes = []
        self._l7_obstacle = None
        self._l7_tby = {}
        self._l7_spawn_cen = {}
        self._l7_idx_color = []
        self._l7_sel = 0
        self._l7_legs = []
        self._l7_leg_i = 0
        self._l7_phase = ""
        self._l7_plan = []
        self._l7_last_dir = (-1, 0)
        self._l7_walls = set()
        self._l7_shape_rel = None
        self._l7_out_last_move = None

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
        if self._levels_seen >= 6:
            # L7 is the recolour+reshape+place HYBRID: changer stations return
            # (unlike L6) alongside the colour-1 obstacle, and three movables whose
            # colours match no target. Gated on level index (>= 6) + the L7
            # signature (stations present AND a colour-1 obstacle) so L1-L6 stay
            # byte-identical; if the signature fails it falls back to _decide_l6.
            stations, _sb = _station_boxes(grid)
            if stations and _l6_obstacle_box(grid) is not None:
                return self._decide_l7(grid, move_ids, can_cycle)
        if self._levels_seen >= 5:
            # L6 is reshape-and-place: two movables + a static colour-1 obstacle,
            # NO changer stations (so the L5 recolour FSM does not apply). Gated on
            # level index (>= 5) + the L6 signature (no stations + a colour-1
            # central obstacle) so L1-L5 stay byte-identical; if the signature
            # fails the controller falls back to _decide_l5 (harmless).
            return self._decide_l6(grid, move_ids, can_cycle)
        if self._levels_seen >= 4:
            # L5 has THREE movables, an uneven 3→2 set-cover assignment, and a
            # MID-EDGE changer station that the L4 edge-row route would clip — a
            # dedicated N-piece controller. Gated on level index so L1-L4 stay
            # byte-identical (the L4 FSM never runs on L5, nor vice versa).
            return self._decide_l5(grid, move_ids, can_cycle)
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

    # ── L5 controller (three movables, uneven 3→2 set-cover, mid-edge station)
    # Ported from the live-validated ``scratchpad/re86_l5_ctrl2.py`` (deterministic
    # 5th-level clear at 367 actions). The three structural additions over L4:
    #   1. N-piece tracking + nearest-centroid selection (the L4 2-piece toggle
    #      cannot express three pieces sharing colour 9).
    #   2. A 3→2 set-cover assignment: one movable recolours to the "single"
    #      colour and covers it; two movables recolour to the "split" colour and
    #      cover one gate cluster each.
    #   3. A station-avoiding path planner (``_l5_route`` over ``grid_shortest_
    #      path``) instead of L4's edge-row column-align — L5 has a MID-EDGE
    #      station (station-14) that the edge-row heuristic would clip.
    # The load-bearing recolour discipline (measured, ``re86_l5_flood.py``): a
    # move during a recolour flood is NOT a no-op — it drives the frozen-looking
    # body into a neighbouring station and re-recolours it — so the flood-wait
    # CYCLES (ACTION5 moves no piece); and the two colour-9 pieces recolour at the
    # single shared corner station strictly one-at-a-time (top-cluster piece
    # first, so it vacates the corner before the bottom one arrives).
    def _decide_l5(self, grid: tuple[tuple[int, ...], ...], move_ids: list[int], can_cycle: bool) -> GameAction:
        if not move_ids:
            return reset_action()
        marker = self._marker(grid)
        # Reuse the level-invariant move map measured on L1-L4 (a probe at L5
        # would drive a movable into a station and mis-recolour it).
        for a, v in self._dir_global.items():
            self._dir.setdefault(a, v)
        if any(a not in self._dir for a in move_ids):
            return self._probe(marker, move_ids)
        # Let the level-load transition settle before reading the static station
        # boxes + gate marks (a cycle moves no piece).
        if self._l5_settle < 2:
            self._l5_settle += 1
            return simple_action(5) if can_cycle else self._probe(marker, move_ids)
        if not self._l5_locked:
            self._l5_stations, self._l5_station_boxes = _station_boxes(grid)
            sbox: dict[int, tuple[int, int, int, int]] = {}
            for col, cen in self._l5_stations.items():
                for b in self._l5_station_boxes:
                    if b[0] <= cen[0] <= b[2] and b[1] <= cen[1] <= b[3]:
                        sbox[col] = b
                        break
            self._l5_sbox = sbox
            movs0 = _l5_movables(grid, set(), self._l5_station_boxes, subtract_boxes=False)
            mov_colors = {m["color"] for m in movs0}
            self._l5_gate_colors = _l5_gate_colors(
                grid, self._l5_station_boxes, set(self._l5_stations), mov_colors
            )
            self._l5_gate_acc = {c: set() for c in self._l5_gate_colors}
            self._l5_locked = True
        if not self._l5_gate_colors:
            return simple_action(5) if can_cycle else self._probe(marker, move_ids)
        if self._l5_phase == "reveal":
            return self._l5_reveal(grid, move_ids, can_cycle, marker)
        return self._l5_solve(grid, move_ids, can_cycle, marker)

    def _l5_all_gates(self) -> set[Cell]:
        return {cell for cells in self._l5_gate_acc.values() for cell in cells}

    def _l5_refresh_gates(self, grid: tuple[tuple[int, ...], ...]) -> None:
        scanned = _l5_scan_gates(grid, self._l5_station_boxes, self._l5_gate_colors)
        for c, cells in scanned.items():
            self._l5_gate_acc[c].update(cells)

    def _l5_emit(
        self,
        action: int,
        marker_pos: Cell | None = None,
        piece_idx: int | None = None,
        want: Cell | None = None,
    ) -> GameAction:
        """Issue an action; record a directional move (piece + pre-move marker +
        intended direction) for next-frame marker-to-marker wall learning. A
        cycle (ACTION5) records nothing (it moves no piece)."""
        if action != 5 and piece_idx is not None and marker_pos is not None and want is not None:
            self._l5_last_move = (piece_idx, marker_pos, want)
        else:
            self._l5_last_move = None
        return simple_action(action)

    def _l5_reveal(
        self, grid: tuple[tuple[int, ...], ...], move_ids: list[int], can_cycle: bool, marker: Cell | None
    ) -> GameAction:
        """Accumulate the gate-canvas cells (two start OCCLUDED by the rightmost
        movable body) by nudging that piece LEFT — away from the right-edge
        stations, so no accidental recolour. Lock the assignment only once the
        gate set is STABLE and a full-cover 3-way assignment exists; an early,
        partial gate set makes the coverage-max permutation pick the WRONG
        mapping (measured)."""
        self._l5_refresh_gates(grid)
        total = sum(len(v) for v in self._l5_gate_acc.values())
        if total == self._l5_prev_total:
            self._l5_stable += 1
        else:
            self._l5_stable = 0
            self._l5_prev_total = total
        self._l5_reveal_steps += 1
        # Complete once the gate set is STABLE (two colour-8 cells start occluded
        # by the rightmost movable body and only appear after it is nudged clear;
        # locking before the full set is revealed picks the WRONG permutation) AND
        # a full-cover 3-way assignment exists (a partial set has none).
        settled = self._l5_reveal_steps >= 8 and self._l5_stable >= 3
        if (settled or self._l5_reveal_steps > 40) and self._l5_build(grid):
            self._l5_phase = "solve"
            return self._l5_solve(grid, move_ids, can_cycle, marker)
        movs = _l5_movables(grid, self._l5_all_gates(), self._l5_station_boxes, subtract_boxes=False)
        if not movs:
            return simple_action(5) if can_cycle else self._probe(marker, move_ids)
        rightmost = max(range(len(movs)), key=lambda i: movs[i]["cen"][1])
        selm = self._l5_marker_piece(movs, marker)
        if selm != rightmost:
            return simple_action(5) if can_cycle else self._probe(marker, move_ids)
        left = self._move_for((0, -1), move_ids)
        if left is None:
            return simple_action(5) if can_cycle else self._probe(marker, move_ids)
        return self._l5_emit(left)

    @staticmethod
    def _l5_marker_piece(movs: list[dict[str, Any]], marker: Cell | None) -> int | None:
        """Index of the movable whose (padded) bbox contains the selection
        marker — the SELECTED piece."""
        if marker is None:
            return None
        for i, m in enumerate(movs):
            rs = [r for r, _c in m["cells"]]
            cs = [c for _r, c in m["cells"]]
            if min(rs) - 2 <= marker[0] <= max(rs) + 2 and min(cs) - 2 <= marker[1] <= max(cs) + 2:
                return i
        return None

    def _l5_build(self, grid: tuple[tuple[int, ...], ...]) -> bool:
        """Parse three movables + cluster the gate cells, then choose the full-
        cover 3→2 assignment: the gate colour whose cells form TWO clusters is
        the SPLIT colour (two movables, one cluster each); the other is the
        SINGLE colour (one movable covers all its cells). Returns True and sets
        ``_l5_pieces`` + ``_l5_order`` only when a FULL-cover assignment exists
        (the reveal gate — a partial set has no full cover)."""
        movs = _l5_movables(grid, self._l5_all_gates(), self._l5_station_boxes, subtract_boxes=False)
        if len(movs) != 3:
            return False
        clusters_by = {c: _l5_cluster(self._l5_gate_acc[c]) for c in self._l5_gate_colors}
        split = [c for c, cls in clusters_by.items() if len(cls) == 2]
        single = [c for c, cls in clusters_by.items() if len(cls) == 1]
        if len(split) != 1 or len(single) != 1:
            return False
        scolor, ucolor = split[0], single[0]
        sclusters = clusters_by[scolor]
        ucells = [cell for cl in clusters_by[ucolor] for cell in cl]

        def cov(mi: int, cells: list[Cell]) -> int:
            best = max_coverage_offset(list(movs[mi]["cells"]), cells)
            return len(best[1]) if best else 0

        best_rank: tuple[int, int] = (-1, -1)
        chosen: tuple[int, dict[int, list[Cell]]] | None = None
        for u_mi in range(3):
            rest = [i for i in range(3) if i != u_mi]
            for m0, m1 in permutations(rest, 2):
                cu = cov(u_mi, ucells)
                c0, c1 = cov(m0, sclusters[0]), cov(m1, sclusters[1])
                full = cu == len(ucells) and c0 == len(sclusters[0]) and c1 == len(sclusters[1])
                rank = (1 if full else 0, cu + c0 + c1)
                if rank > best_rank:
                    best_rank = rank
                    chosen = (u_mi, {m0: sclusters[0], m1: sclusters[1]})
        if chosen is None or best_rank[0] != 1:
            return False
        u_mi, a_split = chosen
        pieces: list[dict[str, Any]] = []
        for mi, m in enumerate(movs):
            if mi == u_mi:
                tcol, cluster_cells, is_single = ucolor, list(ucells), True
            else:
                tcol, cluster_cells, is_single = scolor, list(a_split[mi]), False
            rs = [r for r, _c in m["cells"]]
            cs = [c for _r, c in m["cells"]]
            half = max(max(rs) - min(rs), max(cs) - min(cs)) // 2 + 1
            pieces.append({
                "orig": m["color"], "color": m["color"], "target": tcol,
                "cluster": cluster_cells, "cen": m["cen"], "cells": m["cells"],
                "half": half, "walls": set(), "shape_rel": None,
                "phase": "recolour", "is_single": is_single,
            })
        self._l5_pieces = pieces

        # Processing order: the single-colour piece first (its cover zone is clear
        # of the shared corner station), then the two split-colour pieces TOP
        # cluster BEFORE bottom — both recolour at the single corner station, so
        # send the top-bound one up and away first, leaving the corner free for
        # the bottom one (bottom-first collides the two same-colour bodies there).
        def clu_row(i: int) -> float:
            cl = pieces[i]["cluster"]
            return sum(r for r, _c in cl) / max(1, len(cl))

        self._l5_order = sorted(range(3), key=lambda i: (pieces[i]["target"] != ucolor, clu_row(i)))
        return True

    def _l5_track(self, grid: tuple[tuple[int, ...], ...]) -> None:
        """Match the three tracked pieces to the freshly-parsed movables by
        nearest centroid (≤22 px). Colour is updated only to a KNOWN colour (a
        gate colour or the piece's original) so a mid-flood transient colour does
        not corrupt identity. Station-box pixels are subtracted so a recoloured
        body abutting its same-colour station keeps its true shape."""
        pieces = self._l5_pieces
        if pieces is None:
            return
        movs = _l5_movables(grid, self._l5_all_gates(), self._l5_station_boxes, subtract_boxes=True)
        known = set(self._l5_gate_colors) | {p["orig"] for p in pieces}
        used: set[int] = set()
        for p in pieces:
            best, bd = None, None
            for mi, m in enumerate(movs):
                if mi in used:
                    continue
                d = abs(m["cen"][0] - p["cen"][0]) + abs(m["cen"][1] - p["cen"][1])
                if bd is None or d < bd:
                    bd, best = d, mi
            if best is not None and bd is not None and bd <= 22:
                used.add(best)
                p["cen"] = movs[best]["cen"]
                p["cells"] = movs[best]["cells"]
                if movs[best]["color"] in known:
                    p["color"] = movs[best]["color"]

    def _l5_solve(
        self, grid: tuple[tuple[int, ...], ...], move_ids: list[int], can_cycle: bool, marker: Cell | None
    ) -> GameAction:
        pieces = self._l5_pieces
        assert pieces is not None
        self._l5_track(grid)
        # Keep revealing the occluded single-colour gate cells until the first
        # recolour (the scan is clean while all bodies hold their original
        # colours); refresh the single piece's cover cluster from the growing set.
        any_recoloured = any(p["color"] in self._l5_gate_colors and p["color"] != p["orig"] for p in pieces)
        if not any_recoloured:
            self._l5_refresh_gates(grid)
            for p in pieces:
                if p["is_single"]:
                    p["cluster"] = list(self._l5_gate_acc[p["target"]])
        # marker-to-marker wall learning for the piece the last move drove.
        if self._l5_last_move is not None and marker is not None:
            pi, prev_pos, want = self._l5_last_move
            adv = (marker[0] - prev_pos[0]) * want[0] + (marker[1] - prev_pos[1]) * want[1]
            if adv < 2:
                pieces[pi]["walls"].add((prev_pos[0] // _CELL_PX + want[0], prev_pos[1] // _CELL_PX + want[1]))
        self._l5_last_move = None

        active = next((i for i in self._l5_order if pieces[i]["phase"] != "done"), None)
        if active is None:
            return simple_action(5) if can_cycle else self._probe(marker, move_ids)
        p = pieces[active]
        # selection = NEAREST CENTROID to the marker (a placed piece's large cover
        # bbox can contain another piece's position and steal a bbox-based pick).
        sel = None
        if marker is not None:
            sel = min(
                range(3),
                key=lambda i: abs(pieces[i]["cen"][0] - marker[0]) + abs(pieces[i]["cen"][1] - marker[1]),
            )
        if marker is None:
            return self._l5_emit(5)  # recolour flood: CYCLE (a move would mis-recolour)
        if sel != active:
            return self._l5_emit(5)  # cycle selection to the active piece

        if p["color"] != p["target"]:
            # Drive INTO the target station until the recolour fires; once
            # recoloured the piece sits stably over its same-colour station (a
            # same-colour overlap never re-floods), so the cover phase pulls it
            # out. Non-target stations inflated by the half-extent are avoided.
            others = [b for c, b in self._l5_sbox.items() if c != p["target"]]
            act = _l5_route(marker, self._l5_stations[p["target"]], p["half"], others, p["walls"], self._dir, move_ids)
            if act is None:
                return self._l5_emit(5)
            return self._l5_emit(act, marker, active, self._dir[act])

        # COVER — marker-anchor the shape once, then drive it onto its cluster.
        if p["shape_rel"] is None:
            p["shape_rel"] = frozenset((r - marker[0], c - marker[1]) for r, c in p["cells"])
        cur = {(marker[0] + dr, marker[1] + dc) for dr, dc in p["shape_rel"]}
        need = p["cluster"]
        if not need:
            return self._l5_emit(5)
        if sum(1 for gt in need if gt in cur) == len(need):
            p["phase"] = "done"
            return self._l5_emit(5)  # placed; hold (cycle) while the others finish
        crow = sum(r for r, _c in need) // len(need)
        ccol = sum(c for _r, c in need) // len(need)
        others = [b for c, b in self._l5_sbox.items() if c != p["color"]]
        # RIGHTWARD WAYPOINT: if a different-colour station lies on the vertical
        # leg near this column (station-14 above the corner station-9 for the top
        # colour-9 piece), pull horizontally to the cluster's centre column first
        # — the board centre is station-free, so the vertical leg is then clean.
        if _l5_hazard_between(self._l5_sbox, p["color"], marker, crow, p["half"]) and abs(marker[1] - ccol) > _CELL_PX:
            act = _l5_route(marker, (marker[0], ccol), p["half"], others, p["walls"], self._dir, move_ids)
            if act is None:
                return self._l5_emit(5)
            return self._l5_emit(act, marker, active, self._dir[act])
        best = max_coverage_offset(list(cur), need)
        if best is None:
            return self._l5_emit(5)
        (odr, odc), _cov = best
        goal_px = (marker[0] + odr, marker[1] + odc)
        act = _l5_route(marker, goal_px, p["half"], others, p["walls"], self._dir, move_ids)
        if act is None:
            return self._l5_emit(5)
        return self._l5_emit(act, marker, active, self._dir[act])

    # ── L6 controller (reshape-and-place: two movables + a static obstacle) ──
    # Ported from the live-validated ``scratchpad/re86_l6_solveL6.py`` (deterministic
    # L6 clear). Two pieces, placed sequentially (neither disturbs the other; the
    # win is a simultaneous snapshot):
    #   • the CROSS (movable-9 analogue): a fixed 25×25 frame whose vertical/
    #     horizontal bar SHIFTS ±3 on an obstacle collision. Driven through the
    #     collision-free CORRIDORS (a horizontal move while row-overlapping the
    #     obstacle shifts the vbar; a vertical move while col-overlapping shifts
    #     the hbar), colliding ONLY deliberately to set each bar, then carried to
    #     the frame position that lands the bars on its four target tips.
    #   • the OUTLINE (movable-11 analogue): a hollow square that reshapes
    #     perimeter-conserving on obstacle collision (align rows → push right to
    #     the target height) then `_l5_route`-placed with the obstacle inflated
    #     asymmetrically so the translate never re-collides.
    # All targets/dims are DERIVED from the frame (never hardcoded): the OUTLINE
    # piece is the one whose four target cells are a rectangle's corners; the
    # CROSS piece's four are a plus (a shared-col pair + a shared-row pair).
    @staticmethod
    def _l6_is_rect(tgts: list[Cell]) -> bool:
        rows = sorted({r for r, _c in tgts})
        cols = sorted({c for _r, c in tgts})
        cellset = set(tgts)
        return len(rows) == 2 and len(cols) == 2 and all((r, c) in cellset for r in rows for c in cols)

    def _l6_lock(self, grid: tuple[tuple[int, ...], ...]) -> None:
        stations, _boxes = _station_boxes(grid)
        ob = _l6_obstacle_box(grid)
        by_color: dict[int, list[Cell]] = {}
        for r, c in _target_boxes(grid):
            by_color.setdefault(grid[r][c], []).append((r, c))
        movs = _l5_movables(grid, set(), [], subtract_boxes=False)
        cross_size = self._l6_size
        for m in movs:
            tg = by_color.get(m["color"], [])
            if len(tg) < 4:
                continue
            if self._l6_is_rect(tg):
                self._l6_outline_color = m["color"]
                self._l6_outline_tgt = tg
            else:
                self._l6_cross_color = m["color"]
                self._l6_cross_tgt = tg
                r0, r1, c0, c1 = _l6_bbox(m["cells"])
                cross_size = max(r1 - r0 + 1, c1 - c0 + 1)
        self._l6_size = cross_size
        self._l6_obstacle = ob
        self._l6_applies = (
            not stations
            and ob is not None
            and self._l6_cross_color is not None
            and self._l6_outline_color is not None
        )
        if self._l6_applies:
            self._l6_derive_cross_targets()
        self._l6_locked = True

    def _l6_derive_cross_targets(self) -> None:
        """From the cross's four tips, derive the frame top-left (r0_t, c0_t) and
        bar frame-relative positions (vrel_t, hrel_t) that cover all four. The two
        tips sharing a COLUMN give the vbar target col + vertical span; the two
        sharing a ROW give the hbar target row + horizontal span. Anchoring the
        frame's bottom/right edge on the far tips (r0_t = Rbot-(size-1),
        c0_t = Cright-(size-1)) keeps all four inside the fixed-size frame."""
        tips = self._l6_cross_tgt
        col_counts = Counter(c for _r, c in tips)
        row_counts = Counter(r for r, _c in tips)
        tc = next(c for c, n in col_counts.items() if n >= 2)
        tr = next(r for r, n in row_counts.items() if n >= 2)
        verts = [t for t in tips if t[1] == tc]
        horis = [t for t in tips if t[0] == tr]
        r_bot = max(r for r, _c in verts)
        c_right = max(c for _r, c in horis)
        size = self._l6_size
        self._l6_r0_t = r_bot - (size - 1)
        self._l6_c0_t = c_right - (size - 1)
        self._l6_vrel_t = tc - self._l6_c0_t
        self._l6_hrel_t = tr - self._l6_r0_t

    def _l6_movable(self, grid: tuple[tuple[int, ...], ...], color: int) -> Region | None:
        for m in _l5_movables(grid, set(), [], subtract_boxes=False):
            if m["color"] == color:
                return m
        return None

    @staticmethod
    def _l6_selected(m: Region, marker: Cell) -> bool:
        cen = m["cen"]
        return abs(cen[0] - marker[0]) <= 15 and abs(cen[1] - marker[1]) <= 15

    def _decide_l6(self, grid: tuple[tuple[int, ...], ...], move_ids: list[int], can_cycle: bool) -> GameAction:
        if not move_ids:
            return reset_action()
        marker = self._marker(grid)
        for a, v in self._dir_global.items():
            self._dir.setdefault(a, v)
        if any(a not in self._dir for a in move_ids):
            return self._probe(marker, move_ids)
        if self._l6_settle < 2:
            self._l6_settle += 1
            return simple_action(5) if can_cycle else self._probe(marker, move_ids)
        if not self._l6_locked:
            self._l6_lock(grid)
        if not self._l6_applies:
            # Signature mismatch (a different game's L6 / a changer-station level):
            # fall back to the L5 controller (fails harmlessly, never crashes).
            return self._decide_l5(grid, move_ids, can_cycle)
        if self._l6_piece == "cross":
            if self._l6_p9 != "done":
                return self._l6_step_cross(grid, marker, move_ids, can_cycle)
            self._l6_piece = "outline"
        return self._l6_step_outline(grid, marker, move_ids, can_cycle)

    def _l6_cycle(self, marker: Cell | None, move_ids: list[int], can_cycle: bool) -> GameAction:
        return simple_action(5) if can_cycle else self._probe(marker, move_ids)

    def _l6_mv(self, want: Cell, marker: Cell | None, move_ids: list[int], can_cycle: bool) -> GameAction:
        a = self._move_for(want, move_ids)
        return simple_action(a) if a is not None else self._l6_cycle(marker, move_ids, can_cycle)

    def _l6_step_cross(
        self, grid: tuple[tuple[int, ...], ...], marker: Cell | None, move_ids: list[int], can_cycle: bool
    ) -> GameAction:
        assert self._l6_obstacle is not None and self._l6_cross_color is not None
        m = self._l6_movable(grid, self._l6_cross_color)
        if m is None or marker is None or not self._l6_selected(m, marker):
            return self._l6_cycle(marker, move_ids, can_cycle)
        s = _l6_cross_state(m["cells"])
        ob = self._l6_obstacle
        orow = (ob[0] + ob[2]) // 2
        phase = self._l6_p9
        if phase == "vrel":
            if s["vrel"] == self._l6_vrel_t:
                self._l6_p9 = "hrel_rise"
                return self._l6_step_cross(grid, marker, move_ids, can_cycle)
            cr = (s["r0"] + s["r1"]) // 2
            if s["c0"] < ob[3] - 2:  # not in the right corridor: restore (free)
                return self._l6_mv((0, 1), marker, move_ids, can_cycle)
            if abs(cr - orow) > 3:  # align rows to the obstacle band for the collision
                return self._l6_mv((1, 0) if cr < orow else (-1, 0), marker, move_ids, can_cycle)
            return self._l6_mv((0, -1) if s["vrel"] > self._l6_vrel_t else (0, 1), marker, move_ids, can_cycle)
        if phase == "hrel_rise":
            if s["r0"] <= self._l6_r0_t:  # in the above-obstacle corridor
                self._l6_p9 = "hrel_left"
                return self._l6_step_cross(grid, marker, move_ids, can_cycle)
            return self._l6_mv((-1, 0), marker, move_ids, can_cycle)
        if phase == "hrel_left":
            # move left until the frame col-overlaps the obstacle for the vertical
            # collision, while keeping the vbar (col c0+vrel_t) left of it.
            if s["c0"] <= ob[1] - self._l6_size // 2:
                self._l6_p9 = "hrel_down"
                return self._l6_step_cross(grid, marker, move_ids, can_cycle)
            return self._l6_mv((0, -1), marker, move_ids, can_cycle)
        if phase == "hrel_down":
            if s["hrel"] == self._l6_hrel_t:
                self._l6_p9 = "carry_up"
                return self._l6_step_cross(grid, marker, move_ids, can_cycle)
            return self._l6_mv((1, 0) if s["hrel"] > self._l6_hrel_t else (-1, 0), marker, move_ids, can_cycle)
        if phase == "carry_up":
            if s["r0"] <= self._l6_r0_t:
                self._l6_p9 = "carry_left"
                return self._l6_step_cross(grid, marker, move_ids, can_cycle)
            return self._l6_mv((-1, 0), marker, move_ids, can_cycle)
        # carry_left: reach c0_t, then verify coverage.
        if s["c0"] != self._l6_c0_t:
            return self._l6_mv((0, -1) if s["c0"] > self._l6_c0_t else (0, 1), marker, move_ids, can_cycle)
        if all(t in m["cells"] for t in self._l6_cross_tgt):
            self._l6_p9 = "done"
        return self._l6_cycle(marker, move_ids, can_cycle)

    def _l6_step_outline(
        self, grid: tuple[tuple[int, ...], ...], marker: Cell | None, move_ids: list[int], can_cycle: bool
    ) -> GameAction:
        assert self._l6_obstacle is not None and self._l6_outline_color is not None
        m = self._l6_movable(grid, self._l6_outline_color)
        if m is None or marker is None or not self._l6_selected(m, marker):
            return self._l6_cycle(marker, move_ids, can_cycle)
        ob = self._l6_obstacle
        tgt = self._l6_outline_tgt
        tr0, tr1, tc0, tc1 = _l6_bbox(tgt)
        th, tw = tr1 - tr0 + 1, tc1 - tc0 + 1
        obr = (ob[0] + ob[2]) // 2
        r0, r1, _c0, _c1 = _l6_bbox(m["cells"])
        if self._l6_p11 == "align":
            cr = (r0 + r1) // 2
            if abs(cr - obr) <= 2:
                self._l6_p11 = "reshape"
                return self._l6_step_outline(grid, marker, move_ids, can_cycle)
            return self._l6_mv((-1, 0) if cr > obr else (1, 0), marker, move_ids, can_cycle)
        if self._l6_p11 == "reshape":
            if (r1 - r0 + 1) >= th:  # reshaped to the target height (perimeter-conserving)
                self._l6_p11 = "place"
                return self._l6_step_outline(grid, marker, move_ids, can_cycle)
            return self._l6_mv((0, 1), marker, move_ids, can_cycle)  # push right into the obstacle
        # place — route the reshaped outline centre to the target rectangle centre,
        # obstacle inflated asymmetrically so a translate never re-collides.
        half_h = th // 2 + 1
        half_w = tw // 2 + 1
        avoid = (ob[0] - half_h, ob[1] - half_w, ob[2] + half_h, ob[3] + half_w)
        tgt_cen = ((tr0 + tr1) // 2, (tc0 + tc1) // 2)
        if self._l6_last_move is not None:
            pm, want = self._l6_last_move
            adv = (marker[0] - pm[0]) * want[0] + (marker[1] - pm[1]) * want[1]
            if adv < 2:
                self._l6_walls.add((pm[0] // _CELL_PX + want[0], pm[1] // _CELL_PX + want[1]))
            self._l6_last_move = None
        if self._l6_shape_rel is None:
            self._l6_shape_rel = frozenset((r - marker[0], c - marker[1]) for r, c in m["cells"])
        cur = {(marker[0] + dr, marker[1] + dc) for dr, dc in self._l6_shape_rel}
        if sum(1 for t in tgt if t in cur) == len(tgt):
            self._l6_p11 = "done"
            return self._l6_cycle(marker, move_ids, can_cycle)  # placed — hold
        act = _l5_route(marker, tgt_cen, 0, [avoid], self._l6_walls, self._dir, move_ids)
        if act is None:
            return self._l6_cycle(marker, move_ids, can_cycle)
        self._l6_last_move = (marker, self._dir[act])
        return simple_action(act)

    # ── L7 (recolour + bar-shift/reshape + place hybrid) ────────────────────
    def _decide_l7(self, grid: tuple[tuple[int, ...], ...], move_ids: list[int], can_cycle: bool) -> GameAction:
        if not move_ids:
            return reset_action()
        marker = self._marker(grid)
        for a, v in self._dir_global.items():
            self._dir.setdefault(a, v)
        if any(a not in self._dir for a in move_ids):
            return self._probe(marker, move_ids)
        if self._l7_settle < 3:
            self._l7_settle += 1
            return self._l7_cycle(marker, move_ids, can_cycle, track=False)
        if not self._l7_locked:
            self._l7_lock(grid)
        if not self._l7_applies:
            # Signature mismatch (not the 3-piece L7 scene): fall back to _decide_l6
            # (itself harmless on a non-L6 scene) so the 6/8 floor is never risked.
            return self._decide_l6(grid, move_ids, can_cycle)
        if len(self._l7_idx_color) < 3:
            # Calibrate cycle-index -> spawn colour. Three ACTION5s form a full
            # cycle, so it self-calibrates regardless of the settle count: after it
            # the engine selection is back at idx_color[0]'s slot (sel stays 0).
            if marker is not None:
                self._l7_idx_color.append(self._l7_nearest_spawn(marker))
            return self._l7_cycle(marker, move_ids, can_cycle, track=False)
        if self._l7_leg_i >= len(self._l7_legs):
            return self._l7_cycle(marker, move_ids, can_cycle)
        leg = self._l7_legs[self._l7_leg_i]
        if leg["kind"] == "outline":
            return self._l7_step_outline(grid, marker, move_ids, can_cycle, leg)
        return self._l7_step_cross(grid, marker, move_ids, can_cycle, leg)

    def _l7_lock(self, grid: tuple[tuple[int, ...], ...]) -> None:
        stations, sboxes = _station_boxes(grid)
        self._l7_stations = stations
        self._l7_sboxes = sboxes
        sbox: dict[int, tuple[int, int, int, int]] = {}
        for col, cen in stations.items():
            for b in sboxes:
                if b[0] <= cen[0] <= b[2] and b[1] <= cen[1] <= b[3]:
                    sbox[col] = b
                    break
        self._l7_sbox = sbox
        self._l7_obstacle = _l6_obstacle_box(grid)
        tby: dict[int, list[Cell]] = {}
        for r, c in _target_boxes(grid):
            tby.setdefault(grid[r][c], []).append((r, c))
        self._l7_tby = tby
        regs = _l7_regions(grid, sboxes)
        self._l7_spawn_cen = {m["color"]: m["cen"] for m in regs}
        self._l7_legs = self._l7_assign(regs, tby)
        self._l7_applies = (
            self._l7_obstacle is not None
            and len(regs) == 3
            and len(self._l7_spawn_cen) == 3
            and len(self._l7_legs) == 3
        )
        if self._l7_applies:
            self._l7_next_leg_phase()
        self._l7_locked = True

    @staticmethod
    def _l7_assign(regs: list[dict[str, Any]], tby: dict[int, list[Cell]]) -> list[dict[str, Any]]:
        """Frame-only 1:1 assignment. The target that is a rectangle's corners
        (2 cells) → the OUTLINE movable (2 full-edge cols + 2 full-edge rows); the
        two PLUS targets → the two CROSS movables, widest cross to the widest plus
        (by hbar column span). No colours are hardcoded."""
        rect_color = next((col for col, cells in tby.items() if len(cells) == 2), None)
        plus_colors = [col for col in tby if col != rect_color and len(tby[col]) >= 3]
        if rect_color is None or len(plus_colors) != 2:
            return []
        outline: dict[str, Any] | None = None
        crosses: list[dict[str, Any]] = []
        for m in regs:
            fc, fr = _l7_full_bars(m["cells"])
            if fc >= 2 and fr >= 2:
                outline = m
            else:
                crosses.append(m)
        if outline is None or len(crosses) != 2:
            return []
        plus_colors.sort(key=lambda col: max(c for _r, c in tby[col]) - min(c for _r, c in tby[col]), reverse=True)
        crosses.sort(key=lambda m: m["bbox"][3] - m["bbox"][2], reverse=True)

        def half_w(m: dict[str, Any]) -> int:
            return (m["bbox"][3] - m["bbox"][2] + 1) // 2

        # Order: the crosses first (they share the obstacle, worked one at a time),
        # the outline last. Pieces never collide, so placed ones stay put.
        return [
            {"kind": "cross", "color": crosses[0]["color"], "tgt_color": plus_colors[0], "half_w": half_w(crosses[0])},
            {"kind": "cross", "color": crosses[1]["color"], "tgt_color": plus_colors[1], "half_w": half_w(crosses[1])},
            {"kind": "outline", "color": outline["color"], "tgt_color": rect_color, "half_w": half_w(outline)},
        ]

    def _l7_next_leg_phase(self) -> None:
        self._l7_plan = []
        self._l7_shape_rel = None
        self._l7_out_last_move = None
        if self._l7_leg_i < len(self._l7_legs):
            self._l7_phase = "recolour" if self._l7_legs[self._l7_leg_i]["kind"] == "outline" else "reco_right"

    def _l7_nearest_spawn(self, marker: Cell) -> int:
        return min(
            self._l7_spawn_cen,
            key=lambda k: abs(self._l7_spawn_cen[k][0] - marker[0]) + abs(self._l7_spawn_cen[k][1] - marker[1]),
        )

    def _l7_cycle(self, marker: Cell | None, move_ids: list[int], can_cycle: bool, track: bool = True) -> GameAction:
        if can_cycle:
            if track:
                self._l7_sel = (self._l7_sel + 1) % 3
            return simple_action(5)
        return self._probe(marker, move_ids)

    def _l7_mv_dir(
        self, want: Cell, marker: Cell | None, move_ids: list[int], can_cycle: bool, hold: bool = False
    ) -> GameAction:
        a = self._move_for(want, move_ids)
        if a is None:
            return self._l7_cycle(marker, move_ids, can_cycle)
        if not hold:
            self._l7_last_dir = want
        return simple_action(a)

    def _l7_mv_act(
        self, a: int | None, default: Cell, marker: Cell | None, move_ids: list[int], can_cycle: bool
    ) -> GameAction:
        if a is None:
            return self._l7_mv_dir(default, marker, move_ids, can_cycle)
        if a in self._dir:
            self._l7_last_dir = self._dir[a]
        return simple_action(a)

    @staticmethod
    def _l7_cross_place_target(tgt: list[Cell]) -> tuple[int, int]:
        """Plus/T target -> (vbar col, hbar row): the col shared by >=2 tips is the
        vbar; the row shared by >=2 tips is the hbar."""
        hbar_row = Counter(r for r, _c in tgt).most_common(1)[0][0]
        vbar_col = Counter(c for _r, c in tgt).most_common(1)[0][0]
        return vbar_col, hbar_row

    def _l7_step_cross(
        self,
        grid: tuple[tuple[int, ...], ...],
        marker: Cell | None,
        move_ids: list[int],
        can_cycle: bool,
        leg: dict[str, Any],
    ) -> GameAction:
        assert self._l7_obstacle is not None
        color = leg["color"]
        tgt_color = leg["tgt_color"]
        ob = self._l7_obstacle
        st_col = self._l7_stations[tgt_color][1]
        tgt = sorted(self._l7_tby[tgt_color])
        if marker is None:
            # OCCLUSION (or a 1-frame flood): re-issue the current drive, never
            # ACTION5 (which would desync the cycle-index selection).
            return self._l7_mv_dir(self._l7_last_dir, marker, move_ids, can_cycle, hold=True)
        if self._l7_idx_color[self._l7_sel] != color:
            return self._l7_cycle(marker, move_ids, can_cycle)
        reg = _l7_region_at(grid, marker, self._l7_sboxes)
        cur = reg["color"] if reg else None
        phase = self._l7_phase
        # Recolour: detour RIGHT of the obstacle (a wide hbar pins if risen through
        # it), up above it, left to the station column, then up so ONLY the 1-wide
        # vbar tip enters that one station.
        if phase == "reco_right":
            if cur == tgt_color:
                phase = "settle"
            elif marker[1] < ob[3] + leg["half_w"] + 2:
                self._l7_phase = phase
                return self._l7_mv_dir((0, 1), marker, move_ids, can_cycle)
            else:
                phase = "reco_up1"
        if phase == "reco_up1":
            if cur == tgt_color:
                phase = "settle"
            elif marker[0] > 18:
                self._l7_phase = phase
                return self._l7_mv_dir((-1, 0), marker, move_ids, can_cycle)
            else:
                phase = "reco_left"
        if phase == "reco_left":
            if cur == tgt_color:
                phase = "settle"
            elif marker[1] > st_col + 1:
                self._l7_phase = phase
                return self._l7_mv_dir((0, -1), marker, move_ids, can_cycle)
            elif marker[1] < st_col - 1:
                self._l7_phase = phase
                return self._l7_mv_dir((0, 1), marker, move_ids, can_cycle)
            else:
                phase = "reco_up2"
        if phase == "reco_up2":
            if cur == tgt_color:
                phase = "settle"
            else:
                self._l7_phase = phase
                return self._l7_mv_dir((-1, 0), marker, move_ids, can_cycle)
        if phase == "settle":
            if reg is None or reg["bbox"][0] < 7:
                self._l7_phase = phase
                return self._l7_mv_dir((1, 0), marker, move_ids, can_cycle)
            phase = "plan"
        if phase == "plan":
            if reg is None:
                self._l7_phase = phase
                return self._l7_mv_dir(self._l7_last_dir, marker, move_ids, can_cycle, hold=True)
            s = _l6_cross_state(reg["cells"])
            w = s["c1"] - s["c0"] + 1
            h = s["r1"] - s["r0"] + 1
            st = (s["c0"], s["r0"], s["va"] - s["c0"], s["ha"] - s["r0"])
            vbar_col, hbar_row = self._l7_cross_place_target(tgt)
            place_x = min(c for _r, c in tgt)
            place_y = min(r for r, _c in tgt)
            goal = (place_x, place_y, vbar_col - place_x, hbar_row - place_y)
            self._l7_plan = _l7_bfs_plan(st, goal, w, h, ob, valid=lambda z: z[1] >= 7) or []
            phase = "exec"
        # exec: replay the BFS plan; verify placement from LIVE cells; re-plan when
        # the plan empties without a clear (robust to any sim/engine drift).
        if reg is not None and all(t in reg["cells"] for t in tgt):
            self._l7_leg_i += 1
            self._l7_next_leg_phase()
            return self._l7_cycle(marker, move_ids, can_cycle)
        if reg is None:
            self._l7_phase = phase
            return self._l7_mv_dir(self._l7_last_dir, marker, move_ids, can_cycle, hold=True)
        if not self._l7_plan:
            self._l7_phase = "plan"
            return self._l7_mv_dir((1, 0), marker, move_ids, can_cycle)
        want = self._l7_plan[0]
        a = self._move_for(want, move_ids)
        if a is None:
            self._l7_plan = []
            self._l7_phase = "plan"
            return self._l7_cycle(marker, move_ids, can_cycle)
        self._l7_plan.pop(0)
        self._l7_last_dir = want
        self._l7_phase = phase
        return simple_action(a)

    def _l7_step_outline(
        self,
        grid: tuple[tuple[int, ...], ...],
        marker: Cell | None,
        move_ids: list[int],
        can_cycle: bool,
        leg: dict[str, Any],
    ) -> GameAction:
        assert self._l7_obstacle is not None
        out_color = leg["color"]
        rect_color = leg["tgt_color"]
        ob = self._l7_obstacle
        tgt9 = sorted(self._l7_tby[rect_color])
        tr = [r for r, _c in tgt9]
        tc = [c for _r, c in tgt9]
        rect = (min(tr), max(tr), min(tc), max(tc))
        th, tw = rect[1] - rect[0] + 1, rect[3] - rect[2] + 1
        obc = (ob[1] + ob[3]) // 2
        if marker is None:
            return self._l7_mv_dir(self._l7_last_dir, marker, move_ids, can_cycle, hold=True)
        if self._l7_idx_color[self._l7_sel] != out_color:
            return self._l7_cycle(marker, move_ids, can_cycle)
        reg = _l7_region_at(grid, marker, self._l7_sboxes)
        cur = reg["color"] if reg else None
        phase = self._l7_phase
        if phase == "recolour":
            if cur == rect_color:
                phase = "reshape"
            else:
                scen = self._l7_stations[rect_color]
                if marker[0] > 36:
                    want: Cell = (-1, 0)
                elif abs(marker[1] - scen[1]) > 2:
                    want = (0, 1 if marker[1] < scen[1] else -1)
                else:
                    want = (-1, 0)
                self._l7_phase = phase
                return self._l7_mv_dir(want, marker, move_ids, can_cycle)
        if phase == "reshape":
            if reg is not None:
                r0, r1, c0, c1 = reg["bbox"]
                if (r1 - r0 + 1) <= th:  # reshaped to the wide target height
                    phase = "place"
                else:
                    col_overlap = c0 <= ob[3] and c1 >= ob[1]
                    below_needed = r1 < ob[0]
                    if not col_overlap or below_needed:
                        goal = (max(ob[0] - 7, 14), obc)
                        a = _l5_route(
                            marker, goal, 7, list(self._l7_sbox.values()), self._l7_walls, self._dir, move_ids
                        )
                        self._l7_phase = phase
                        return self._l7_mv_act(a, (1, 0), marker, move_ids, can_cycle)
                    self._l7_phase = phase
                    return self._l7_mv_dir((1, 0), marker, move_ids, can_cycle)  # push DOWN = vertical reshape
            else:
                col_overlap = ob[1] - 7 <= marker[1] <= ob[3] + 7
                below_needed = marker[0] < ob[0] - 6
                if not col_overlap or below_needed:
                    goal = (max(ob[0] - 7, 14), obc)
                    a = _l5_route(marker, goal, 7, list(self._l7_sbox.values()), self._l7_walls, self._dir, move_ids)
                    self._l7_phase = phase
                    return self._l7_mv_act(a, (1, 0), marker, move_ids, can_cycle)
                self._l7_phase = phase
                return self._l7_mv_dir((1, 0), marker, move_ids, can_cycle)
        # place — route the reshaped outline centre to the target rect centre, the
        # obstacle inflated asymmetrically so a translate never re-collides.
        if reg is None:
            return self._l7_mv_dir(self._l7_last_dir, marker, move_ids, can_cycle, hold=True)
        if all(t in reg["cells"] for t in tgt9):
            self._l7_leg_i += 1
            self._l7_next_leg_phase()
            return self._l7_cycle(marker, move_ids, can_cycle)
        tgt_cen = ((rect[0] + rect[1]) // 2, (rect[2] + rect[3]) // 2)
        avoid = (ob[0] - th, ob[1] - tw, ob[2] + th, ob[3] + tw)
        a = _l5_route(marker, tgt_cen, 0, list(self._l7_sbox.values()) + [avoid], self._l7_walls, self._dir, move_ids)
        self._l7_phase = "place"
        return self._l7_mv_act(a, (-1, 0), marker, move_ids, can_cycle)

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
