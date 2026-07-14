"""Pure region-segmentation and relation kernels ("regions_and_relations", R56).

Generic same-colour connected-component segmentation, pairwise spatial
relations, axis clustering, shape-multiset comparison, and bbox tiling — the
reusable math behind puzzle classes that group, sort, or size-compare small
coloured clusters on a grid. Reference sources (read for the math, never
imported, and stripped of their game semantics before landing here):
:mod:`admorphiq.sort_match` (row/column grouping, multiset comparison, hollow
frame + connector extraction), :mod:`admorphiq.delivery` (size clustering,
bbox/slot tiling), :mod:`admorphiq.transform_route` (gap-tolerant clustering),
:mod:`admorphiq.merge_drag` (region features feeding a caller-supplied
predicate). None of THOSE modules' role assignments travel with the math —
no "largest region is the goal", no "small rings are items", no "top row is
the target order", no ring-dot colour rules. This module only segments,
measures, and relates; the caller supplies every semantic label.

A frame is any 2D grid (list-of-lists / tuple-of-tuples) of ints (colour
indices); it is normalized internally to a tuple of tuples. Cell coordinates
throughout are ``(row, col)``, and a bbox is the inclusive
``(row0, col0, row1, col1)``.

Stdlib only — no numpy. These kernels must run inside the sandboxed REPL
where only the standard library and explicitly provided modules exist.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from typing import Any

from admorphiq.kernels._common import normalize_frame as _normalize_frame

Cell = tuple[int, int]
Bbox = tuple[int, int, int, int]
Region = dict[str, Any]


def _normalize_background(background: int | Iterable[int] | None) -> frozenset[int]:
    if background is None:
        return frozenset()
    if isinstance(background, int):
        return frozenset({background})
    return frozenset(int(b) for b in background)


def _neighbor_offsets(connectivity: int) -> list[Cell]:
    if connectivity == 4:
        return [(-1, 0), (1, 0), (0, -1), (0, 1)]
    return [(dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1) if (dr, dc) != (0, 0)]


def _gap_offsets(gap: int) -> list[Cell]:
    radius = gap + 1
    return [
        (dr, dc)
        for dr in range(-radius, radius + 1)
        for dc in range(-radius, radius + 1)
        if (dr, dc) != (0, 0)
    ]


def find_regions(
    frame: Sequence[Sequence[int]],
    background: int | Iterable[int] | None = None,
    connectivity: int = 4,
    gap: int = 0,
) -> list[Region]:
    """Same-colour connected components of ``frame``.

    ``background``, when given, excludes matching colour(s) from every
    region entirely (a single int or any iterable of ints). ``connectivity``
    (4 or 8) selects immediate-neighbour adjacency and is used whenever
    ``gap == 0``. When ``gap > 0``, adjacency switches to gap-tolerant
    clustering: two same-colour cells join the same region whenever their
    Chebyshev distance is at most ``gap + 1`` — this OVERRIDES
    ``connectivity`` (the bridging radius subsumes both 4- and
    8-connectivity at ``gap == 0`` equivalent to radius 1), matching
    :mod:`admorphiq.transform_route`'s technique for reconnecting a cluster
    split by a foreign marker cell.

    Returns one dict per component: ``{"color", "cells", "bbox", "centroid",
    "size"}``, where ``cells`` is a ``frozenset`` of ``(row, col)``, ``bbox``
    is the inclusive ``(row0, col0, row1, col1)``, and ``centroid`` is the
    mean ``(row, col)`` as floats. Results are sorted deterministically by
    ``(bbox row0, bbox col0, color)`` — independent of BFS traversal order.
    Pure / no environment access.
    """
    if connectivity not in (4, 8):
        raise ValueError(f"connectivity must be 4 or 8, got {connectivity!r}")
    if gap < 0:
        raise ValueError(f"gap must be >= 0, got {gap!r}")
    grid = _normalize_frame(frame)
    if not grid or not grid[0]:
        return []
    bg = _normalize_background(background)
    h, w = len(grid), len(grid[0])
    offsets = _gap_offsets(gap) if gap > 0 else _neighbor_offsets(connectivity)

    visited: set[Cell] = set()
    regions: list[Region] = []
    for r0 in range(h):
        for c0 in range(w):
            if (r0, c0) in visited:
                continue
            color = grid[r0][c0]
            visited.add((r0, c0))
            if color in bg:
                continue
            cells: set[Cell] = set()
            stack = [(r0, c0)]
            while stack:
                r, c = stack.pop()
                cells.add((r, c))
                for dr, dc in offsets:
                    nr, nc = r + dr, c + dc
                    if (
                        0 <= nr < h
                        and 0 <= nc < w
                        and (nr, nc) not in visited
                        and grid[nr][nc] == color
                    ):
                        visited.add((nr, nc))
                        stack.append((nr, nc))
            rows = [r for r, _c in cells]
            cols = [c for _r, c in cells]
            bbox: Bbox = (min(rows), min(cols), max(rows), max(cols))
            centroid = (sum(rows) / len(cells), sum(cols) / len(cells))
            regions.append(
                {
                    "color": color,
                    "cells": frozenset(cells),
                    "bbox": bbox,
                    "centroid": centroid,
                    "size": len(cells),
                }
            )
    regions.sort(key=lambda reg: (reg["bbox"][0], reg["bbox"][1], reg["color"]))
    return regions


def _bbox_strictly_contains(outer: Bbox, inner: Bbox) -> bool:
    or0, oc0, or1, oc1 = outer
    ir0, ic0, ir1, ic1 = inner
    if not (or0 <= ir0 and oc0 <= ic0 and or1 >= ir1 and oc1 >= ic1):
        return False
    return outer != inner


def _cells_touch_4(cells_a: frozenset[Cell], cells_b: frozenset[Cell]) -> bool:
    smaller, larger = (cells_a, cells_b) if len(cells_a) <= len(cells_b) else (cells_b, cells_a)
    for r, c in smaller:
        if (r - 1, c) in larger or (r + 1, c) in larger or (r, c - 1) in larger or (r, c + 1) in larger:
            return True
    return False


def region_relations(regions: Sequence[Region]) -> list[dict[str, Any]]:
    """Pairwise spatial relations that hold between every pair in ``regions``.

    For each unordered pair ``(i, j)`` (``i < j``), emits one dict per
    relation that holds — a pair may satisfy more than one relation
    (concentric shapes sharing a centroid satisfy ``contains`` AND both
    ``aligned_row``/``aligned_col``, for instance):

    - ``contains``: one region's bbox strictly (non-equal) contains the
      other's. ``a`` is always the CONTAINER here, so ``a`` may be the
      larger index when the container comes later in ``regions``.
    - ``adjacent``: some cell of one region is 4-connectivity-adjacent to
      some cell of the other (checked at 4-connectivity regardless of how
      the regions themselves were segmented).
    - ``aligned_row`` / ``aligned_col``: the two regions' centroids agree on
      the row (resp. column) axis within 0.5 cells.

    For every relation except ``contains``, ``a < b`` (the lower index is
    always ``a``). Pure / no environment access.
    """
    n = len(regions)
    relations: list[dict[str, Any]] = []
    for i in range(n):
        for j in range(i + 1, n):
            bbox_i, bbox_j = regions[i]["bbox"], regions[j]["bbox"]
            if _bbox_strictly_contains(bbox_i, bbox_j):
                relations.append({"a": i, "b": j, "relation": "contains"})
            elif _bbox_strictly_contains(bbox_j, bbox_i):
                relations.append({"a": j, "b": i, "relation": "contains"})
            if _cells_touch_4(regions[i]["cells"], regions[j]["cells"]):
                relations.append({"a": i, "b": j, "relation": "adjacent"})
            ci, cj = regions[i]["centroid"], regions[j]["centroid"]
            if abs(ci[0] - cj[0]) <= 0.5:
                relations.append({"a": i, "b": j, "relation": "aligned_row"})
            if abs(ci[1] - cj[1]) <= 0.5:
                relations.append({"a": i, "b": j, "relation": "aligned_col"})
    return relations


def group_by_axis(
    regions: Sequence[Region], axis: str = "row", tolerance: float = 1.0
) -> list[list[int]]:
    """Cluster region indices by centroid ``axis`` position within ``tolerance``.

    Regions are sorted by their centroid on ``axis`` ("row" or "col"), then
    chained into a group as long as each next centroid is within
    ``tolerance`` of the PREVIOUS one in sorted order (so a group can span
    more than ``tolerance`` end-to-end, the same transitive-chaining
    behaviour :mod:`admorphiq.sort_match`'s row/column banding relies on).
    Groups are returned sorted by their minimum axis coordinate; within a
    group, indices are sorted by the OTHER axis. Pure / no environment
    access.
    """
    if axis not in ("row", "col"):
        raise ValueError(f"axis must be 'row' or 'col', got {axis!r}")
    axis_idx = 0 if axis == "row" else 1
    other_idx = 1 - axis_idx

    order = sorted(range(len(regions)), key=lambda i: regions[i]["centroid"][axis_idx])
    groups: list[list[int]] = []
    current: list[int] = []
    prev_val: float | None = None
    for i in order:
        val = regions[i]["centroid"][axis_idx]
        if current and prev_val is not None and (val - prev_val) > tolerance:
            groups.append(current)
            current = []
        current.append(i)
        prev_val = val
    if current:
        groups.append(current)

    for group in groups:
        group.sort(key=lambda i: regions[i]["centroid"][other_idx])
    groups.sort(key=lambda group: min(regions[i]["centroid"][axis_idx] for i in group))
    return groups


def multiset_signature(region: Region) -> frozenset[Cell]:
    """A translation-invariant shape signature for ``region``.

    The region's ``cells`` re-expressed relative to its own bounding box's
    top-left corner (min row / min col subtracted to 0), as a ``frozenset``
    — hashable, and identical for two regions that share the same shape
    regardless of where each sits on the frame. Pure / no environment
    access.
    """
    cells = region["cells"]
    if not cells:
        return frozenset()
    r0 = min(r for r, _c in cells)
    c0 = min(c for _r, c in cells)
    return frozenset((r - r0, c - c0) for r, c in cells)


def multisets_equal(regions_a: Sequence[Region], regions_b: Sequence[Region]) -> bool:
    """Do ``regions_a`` and ``regions_b`` hold the same multiset of (colour, shape)?

    Compares the two lists as multisets of ``(color, multiset_signature)`` —
    order-independent, translation-invariant, but sensitive to both shape
    and colour (see :func:`multiset_signature`). Matches
    :mod:`admorphiq.sort_match`'s "does the pool supply the reference set"
    comparison, generalised to arbitrary regions. Pure / no environment
    access.
    """
    sig_a = Counter((r["color"], multiset_signature(r)) for r in regions_a)
    sig_b = Counter((r["color"], multiset_signature(r)) for r in regions_b)
    return sig_a == sig_b


def size_clusters(regions: Sequence[Region], ratio: float = 1.5) -> list[list[int]]:
    """Group region indices into size classes by consecutive-size jumps.

    Sorts regions by ``size`` ascending, then starts a new cluster whenever
    the next size divided by the previous size exceeds ``ratio`` — the same
    "measured size outlier" technique :mod:`admorphiq.delivery` uses to
    split items from target zones, generalised to any number of size
    classes (not just a single item/target binary split). Pure / no
    environment access.
    """
    order = sorted(range(len(regions)), key=lambda i: regions[i]["size"])
    clusters: list[list[int]] = []
    current: list[int] = []
    prev_size: int | None = None
    for i in order:
        size = regions[i]["size"]
        if current and prev_size and (size / prev_size) > ratio:
            clusters.append(current)
            current = []
        current.append(i)
        prev_size = size
    if current:
        clusters.append(current)
    return clusters


def tile_bbox(bbox: Bbox, rows: int, cols: int) -> list[Bbox]:
    """Tile ``bbox`` into a ``rows`` x ``cols`` grid of sub-bboxes, integer-fair.

    Each dimension is partitioned as evenly as integers allow (sizes differ
    by at most 1; any remainder cells go to the earliest partitions), so the
    union of the returned sub-bboxes exactly covers ``bbox`` with no gaps
    and no overlaps — matching :mod:`admorphiq.delivery`'s slot-tiling of a
    target zone's footprint. Returned in row-major order (top row
    left-to-right, then the next row). ``rows`` and ``cols`` must both be
    positive. Pure / no environment access.
    """
    r0, c0, r1, c1 = bbox
    row_sizes = _fair_partition(r1 - r0 + 1, rows)
    col_sizes = _fair_partition(c1 - c0 + 1, cols)
    out: list[Bbox] = []
    r_cursor = r0
    for rs in row_sizes:
        c_cursor = c0
        for cs in col_sizes:
            out.append((r_cursor, c_cursor, r_cursor + rs - 1, c_cursor + cs - 1))
            c_cursor += cs
        r_cursor += rs
    return out


def _fair_partition(total: int, n: int) -> list[int]:
    if n <= 0:
        raise ValueError(f"n must be positive, got {n!r}")
    base, rem = divmod(total, n)
    return [base + 1 if i < rem else base for i in range(n)]
