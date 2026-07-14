"""Pure closed-frame, elongated-axis, and covering-offset kernels ("shape
geometry", R56 — remaining geometry extractions from the Codex decomposition
table).

Generic geometry the LLM (or a quarantined public-game adapter script)
composes by supplying frames, regions, and points — no role semantics.
Reference sources (read for the math, never imported, and stripped of their
game-specific labels before landing here): :mod:`admorphiq.delivery`
(closed-frame / ring detection), :mod:`admorphiq.slider` (elongated-region
detection, axis/endpoints, point-to-axis projection), :mod:`admorphiq.
transform_route` (axis snapping, `covering_offsets`-style set cover),
:mod:`admorphiq.sort_match` (hollow-box + connector extraction), and
:mod:`admorphiq.merge_drag` (`point_toward`-style stepping). None of THOSE
modules' role assignments travel with the math — no "small ring is an item",
no "foreign cell is a tip", no "ring dot is the required colour". This module
only measures shapes and plans translations; the caller supplies every
semantic label.

Frames are 2D grids of ints (colour indices), normalized internally to a
tuple of tuples. Regions are plain dicts in the shape produced by
:mod:`admorphiq.kernels.regions`'s ``find_regions`` — ``{"color", "cells",
"bbox", "centroid", "size"}`` — but this module does not import that module;
it only reads those keys. Cell coordinates are ``(row, col)``; a bbox is the
inclusive ``(row0, col0, row1, col1)``.

Stdlib only — no numpy. These kernels must run inside the sandboxed REPL
where only the standard library and explicitly provided modules exist.
"""

from __future__ import annotations

import itertools
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence

Cell = tuple[int, int]
Bbox = tuple[int, int, int, int]
Shift = tuple[int, int]
Region = Mapping[str, object]
Grid = tuple[tuple[int, ...], ...]

_CARDINAL: tuple[Cell, ...] = ((-1, 0), (1, 0), (0, -1), (0, 1))

# connectors(): a linking path must be at most this many cells thick (its
# bounding box's shorter side) to count as a "thin" connector rather than a
# blob — matches the "1-2 cell wide" pipes measured in sort_match's portal
# links.
_MAX_CONNECTOR_THICKNESS = 2


def _normalize_frame(frame: Sequence[Sequence[int]]) -> Grid:
    return tuple(tuple(int(v) for v in row) for row in frame)


def _normalize_cells(cells: Iterable[Sequence[int]]) -> frozenset[Cell]:
    return frozenset((int(r), int(c)) for r, c in cells)


def _resolve_background(grid: Grid, background: int | None) -> int:
    if background is not None:
        return int(background)
    counts = Counter(v for row in grid for v in row)
    return counts.most_common(1)[0][0]


def _flood_fill(grid: Grid, r0: int, c0: int, color: int, visited: set[Cell]) -> set[Cell]:
    h, w = len(grid), len(grid[0])
    cells: set[Cell] = set()
    stack = [(r0, c0)]
    while stack:
        r, c = stack.pop()
        cells.add((r, c))
        for dr, dc in _CARDINAL:
            nr, nc = r + dr, c + dc
            if 0 <= nr < h and 0 <= nc < w and (nr, nc) not in visited and grid[nr][nc] == color:
                visited.add((nr, nc))
                stack.append((nr, nc))
    return cells


def _rect_border(r0: int, c0: int, r1: int, c1: int) -> frozenset[Cell]:
    top_bottom = {(r0, c) for c in range(c0, c1 + 1)} | {(r1, c) for c in range(c0, c1 + 1)}
    left_right = {(r, c0) for r in range(r0, r1 + 1)} | {(r, c1) for r in range(r0, r1 + 1)}
    return frozenset(top_bottom | left_right)


def _touches_4(cells_a: frozenset[Cell], cells_b: frozenset[Cell]) -> bool:
    smaller, larger = (cells_a, cells_b) if len(cells_a) <= len(cells_b) else (cells_b, cells_a)
    for r, c in smaller:
        if (r - 1, c) in larger or (r + 1, c) in larger or (r, c - 1) in larger or (r, c + 1) in larger:
            return True
    return False


def closed_frames(frame: Sequence[Sequence[int]], background: int | None = None) -> list[dict[str, object]]:
    """Rectangular one-colour rings that fully enclose a hole.

    A component qualifies only when its cells are EXACTLY the border of its
    own bounding box (every cell on all four edges, and nothing else) — a
    solid filled rectangle of the same colour has extra interior cells of
    that colour, so it fails this equality and is excluded, distinguishing a
    genuine hollow ring from a filled block. The bbox must also be large
    enough to have a nonempty interior (at least 3 rows and 3 columns);
    degenerate 1-thick "rings" have no hole and are excluded too.
    ``background`` (default: the frame's most-common colour) is never
    considered a ring candidate.

    Returns one dict per qualifying ring: ``{"border_color", "outer_bbox",
    "inner_bbox", "hole_cells"}``. ``hole_cells`` is every cell strictly
    inside the border (regardless of what colour(s) currently occupy it —
    this kernel reports the enclosed AREA, not its contents). Sorted by
    ``(outer_bbox row0, outer_bbox col0, border_color)``.
    """
    grid = _normalize_frame(frame)
    if not grid or not grid[0]:
        return []
    h, w = len(grid), len(grid[0])
    bg = _resolve_background(grid, background)

    visited: set[Cell] = set()
    out: list[dict[str, object]] = []
    for r0 in range(h):
        for c0 in range(w):
            if (r0, c0) in visited:
                continue
            color = grid[r0][c0]
            visited.add((r0, c0))
            if color == bg:
                continue
            cells = _flood_fill(grid, r0, c0, color, visited)
            rows = [r for r, _c in cells]
            cols = [c for _r, c in cells]
            r0b, r1b, c0b, c1b = min(rows), max(rows), min(cols), max(cols)
            if frozenset(cells) != _rect_border(r0b, c0b, r1b, c1b):
                continue
            inner: Bbox = (r0b + 1, c0b + 1, r1b - 1, c1b - 1)
            if inner[0] > inner[2] or inner[1] > inner[3]:
                continue
            hole_cells = frozenset(
                (r, c) for r in range(inner[0], inner[2] + 1) for c in range(inner[1], inner[3] + 1)
            )
            out.append(
                {
                    "border_color": color,
                    "outer_bbox": (r0b, c0b, r1b, c1b),
                    "inner_bbox": inner,
                    "hole_cells": hole_cells,
                }
            )
    out.sort(key=lambda d: (d["outer_bbox"][0], d["outer_bbox"][1], d["border_color"]))  # type: ignore[index]
    return out


def elongated_axis(region: Region, min_aspect: float = 3.0) -> dict[str, object] | None:
    """The principal axis of an elongated region, or None when it isn't elongated.

    Uses ``region["bbox"]`` only. ``axis`` is ``"row"`` when the region is
    taller than wide (elongated top-to-bottom; ``endpoints`` run down a
    fixed column) or ``"col"`` when wider than tall (elongated
    left-to-right; ``endpoints`` run across a fixed row) — ties (square
    bbox) default to ``"row"``. Qualifies only when
    ``length / thickness >= min_aspect``; ``length`` is the long-dimension
    cell count, ``thickness`` the short-dimension cell count. The fixed
    coordinate is the bbox's own midline (integer floor), not the region's
    true cell-weighted centroid, so ``endpoints`` are exact bbox-edge cells.
    """
    r0, c0, r1, c1 = region["bbox"]  # type: ignore[misc]
    height = r1 - r0 + 1
    width = c1 - c0 + 1
    if height >= width:
        axis, length, thickness = "row", height, width
    else:
        axis, length, thickness = "col", width, height
    if thickness <= 0 or length / thickness < min_aspect:
        return None
    if axis == "row":
        mid_c = (c0 + c1) // 2
        endpoints = ((r0, mid_c), (r1, mid_c))
    else:
        mid_r = (r0 + r1) // 2
        endpoints = ((mid_r, c0), (mid_r, c1))
    return {"axis": axis, "endpoints": endpoints, "length": length, "thickness": thickness}


def project_to_axis(point: Sequence[int], axis_info: Mapping[str, object]) -> Cell:
    """Nearest cell on ``axis_info``'s (:func:`elongated_axis`-shaped) segment to ``point``.

    Since the segment is axis-aligned (a fixed row or fixed column between
    its two endpoints), the nearest point is simply the fixed coordinate
    paired with ``point``'s other coordinate clamped into the endpoint
    range — no distance search needed.
    """
    axis = axis_info["axis"]
    (r0, c0), (r1, c1) = axis_info["endpoints"]  # type: ignore[misc]
    pr, pc = int(point[0]), int(point[1])
    if axis == "row":
        lo, hi = min(r0, r1), max(r0, r1)
        return (min(max(pr, lo), hi), c0)
    lo, hi = min(c0, c1), max(c0, c1)
    return (r0, min(max(pc, lo), hi))


def point_toward(origin: Sequence[float], target: Sequence[float], distance: float = 1) -> Cell:
    """The integer cell ``distance`` px from ``origin`` toward ``target``.

    Walks the straight line from ``origin`` to ``target`` and rounds the
    resulting point to the nearest integer cell via Python's ``round()``
    (round-half-to-even), matching :mod:`admorphiq.merge_drag`'s
    ``_step_toward`` convention. When ``distance`` is at or beyond the
    ``origin``-``target`` distance (or ``origin == target``), the result
    clamps to ``target`` exactly rather than overshooting past it.
    """
    ox, oy = float(origin[0]), float(origin[1])
    tx, ty = float(target[0]), float(target[1])
    dx, dy = tx - ox, ty - oy
    dist = (dx * dx + dy * dy) ** 0.5
    if dist <= 1e-9 or distance >= dist:
        return (int(round(tx)), int(round(ty)))
    x = ox + dx / dist * distance
    y = oy + dy / dist * distance
    return (int(round(x)), int(round(y)))


def axis_snap(offset: Sequence[int], tolerance: int = 1) -> Shift:
    """Snap a near-axis ``(dr, dc)`` offset to the pure axis, or leave it unchanged.

    When one component's magnitude is both ``<= tolerance`` and strictly
    smaller than the other's, that component is zeroed (e.g. ``(5, 1)`` with
    ``tolerance=1`` becomes ``(5, 0)``). Otherwise ``offset`` is returned
    unchanged — this only fires when there is a clear dominant axis AND the
    minor axis is within noise tolerance of zero, unlike
    :func:`admorphiq.transform_route.snap_to_axis`'s unconditional
    smaller-magnitude-to-zero rule.
    """
    dr, dc = int(offset[0]), int(offset[1])
    if abs(dc) <= tolerance and abs(dc) < abs(dr):
        return (dr, 0)
    if abs(dr) <= tolerance and abs(dr) < abs(dc):
        return (0, dc)
    return (dr, dc)


def covering_offsets(
    shape_cells: Iterable[Sequence[int]], target_points: Sequence[Sequence[int]]
) -> list[Shift]:
    """A minimal set of translations of ``shape_cells`` covering every point in ``target_points``.

    ``shape_cells`` is a frozenset (or any iterable) of ``(dr, dc)`` offsets
    from some shared origin; a translation ``(dr, dc)`` "covers" a target
    point when some translated shape cell lands exactly on it. Only offsets
    that align some shape cell onto some target point can cover anything, so
    the candidate set is derived as ``{point - shape_cell}`` over every
    (point, cell) pair — the same position-agnostic derivation
    :mod:`admorphiq.transform_route`'s ``find_covering_offset`` uses for a
    single offset, generalised here to a covering SET.

    When there are at most 12 distinct candidates, an exact minimum-size set
    cover is found by trying increasing subset sizes over the (pre-sorted,
    so deterministic) candidate list. Above that, a greedy
    most-newly-covered-first search is used instead (not guaranteed
    minimal); ties in both modes favor the numerically smaller offset
    (candidates are iterated in sorted order, and ties keep the
    first-encountered / lowest-index choice).

    ``shape_cells`` must be non-empty for any point to be coverable
    (behaviour is undefined otherwise); an empty ``target_points`` returns
    ``[]`` immediately.
    """
    shape = _normalize_cells(shape_cells)
    points = [(int(r), int(c)) for r, c in target_points]
    if not points:
        return []

    candidate_set: set[Shift] = set()
    for pr, pc in points:
        for sr, sc in shape:
            candidate_set.add((pr - sr, pc - sc))
    candidates = sorted(candidate_set)

    coverage: dict[Shift, frozenset[int]] = {}
    for dr, dc in candidates:
        translated = {(sr + dr, sc + dc) for sr, sc in shape}
        coverage[(dr, dc)] = frozenset(i for i, p in enumerate(points) if p in translated)

    all_covered = frozenset(range(len(points)))

    if len(candidates) <= 12:
        for k in range(1, len(candidates) + 1):
            for combo in itertools.combinations(candidates, k):
                union: frozenset[int] = frozenset().union(*(coverage[c] for c in combo))
                if union == all_covered:
                    return list(combo)

    chosen: list[Shift] = []
    remaining = set(range(len(points)))
    while remaining:
        best = max(candidates, key=lambda off: len(coverage[off] & remaining))
        chosen.append(best)
        remaining -= coverage[best]
    return chosen


def connectors(
    frame: Sequence[Sequence[int]], regions: Sequence[Region], background: int | None = None
) -> list[dict[str, object]]:
    """Thin same-colour paths linking exactly two of ``regions``.

    Every cell already claimed by some entry in ``regions`` is excluded from
    the search up front (a connector is a SEPARATE same-coloured run, not
    part of any given region). Among the remaining non-background cells,
    each 4-connectivity same-colour component is a connector CANDIDATE when
    its bounding box's shorter side is at most 2 cells (the "1-2 cell wide"
    pipe measured in :mod:`admorphiq.sort_match`'s portal links — a wider
    blob is not a path) and it 4-connectivity touches exactly two distinct
    entries of ``regions`` (touching one, zero, or three-or-more is not a
    two-endpoint link and is excluded). ``background`` (default: the
    frame's most-common colour) is never a candidate.

    Returns one dict per qualifying connector: ``{"a": idx, "b": idx,
    "path_cells": frozenset, "color"}`` (``a < b``, both indices into
    ``regions``). Sorted by ``(a, b, path's own bbox row0, col0)``.
    """
    grid = _normalize_frame(frame)
    if not grid or not grid[0]:
        return []
    h, w = len(grid), len(grid[0])
    bg = _resolve_background(grid, background)

    region_cells = [_normalize_cells(r["cells"]) for r in regions]  # type: ignore[index]
    claimed: set[Cell] = set()
    for cells in region_cells:
        claimed |= cells

    visited: set[Cell] = set(claimed)
    out: list[dict[str, object]] = []
    for r0 in range(h):
        for c0 in range(w):
            if (r0, c0) in visited:
                continue
            color = grid[r0][c0]
            visited.add((r0, c0))
            if color == bg:
                continue
            cells = _flood_fill(grid, r0, c0, color, visited)
            rows = [r for r, _c in cells]
            cols = [c for _r, c in cells]
            bh = max(rows) - min(rows) + 1
            bw = max(cols) - min(cols) + 1
            if min(bh, bw) > _MAX_CONNECTOR_THICKNESS:
                continue
            frozen_cells = frozenset(cells)
            touched = {i for i, rc in enumerate(region_cells) if _touches_4(frozen_cells, rc)}
            if len(touched) != 2:
                continue
            a_idx, b_idx = sorted(touched)
            out.append({"a": a_idx, "b": b_idx, "path_cells": frozen_cells, "color": color})
    out.sort(
        key=lambda d: (
            d["a"],
            d["b"],
            min(r for r, _c in d["path_cells"]),  # type: ignore[union-attr]
            min(c for _r, c in d["path_cells"]),  # type: ignore[union-attr]
        )
    )
    return out
