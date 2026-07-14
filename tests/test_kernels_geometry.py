"""Tests for the pure closed-frame / elongated-axis / covering-offset kernels (R56)."""

from admorphiq.kernels import (
    axis_snap,
    closed_frames,
    connectors,
    covering_offsets,
    elongated_axis,
    point_toward,
    project_to_axis,
)


def _blank(h, w, bg=0):
    return [[bg for _ in range(w)] for _ in range(h)]


def _paint_rect(grid, r0, c0, r1, c1, color):
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            grid[r][c] = color


def _paint_border(grid, r0, c0, r1, c1, color):
    for c in range(c0, c1 + 1):
        grid[r0][c] = color
        grid[r1][c] = color
    for r in range(r0, r1 + 1):
        grid[r][c0] = color
        grid[r][c1] = color


def _region(color, cells):
    cells = list(cells)
    rows = [r for r, _c in cells]
    cols = [c for _r, c in cells]
    return {
        "color": color,
        "cells": frozenset(cells),
        "bbox": (min(rows), min(cols), max(rows), max(cols)),
        "centroid": (sum(rows) / len(cells), sum(cols) / len(cells)),
        "size": len(cells),
    }


def test_closed_frames_hollow_ring_reports_hole_solid_rect_excluded():
    """Purpose: a hollow rectangular border (a genuine ring around a hole)
    must be reported with the correct outer/inner bbox and hole cells, while
    a SOLID rectangle of the same colour (no enclosed hole) must be excluded
    entirely -- the defining distinction closed_frames exists to make.
    Expected feedback: failure means the border-equality check is wrong, so
    a caller (e.g. a sort-puzzle solver looking for genuine frames) would
    either miss real rings or mistake solid blocks for them."""
    grid = _blank(10, 10, bg=0)
    _paint_border(grid, 1, 1, 5, 5, color=3)
    grid[3][3] = 7  # something sitting in the hole -- irrelevant to detection
    _paint_rect(grid, 1, 7, 4, 9, color=6)  # solid block, no hole

    frames = closed_frames(grid, background=0)
    assert len(frames) == 1
    ring = frames[0]
    assert ring["border_color"] == 3
    assert ring["outer_bbox"] == (1, 1, 5, 5)
    assert ring["inner_bbox"] == (2, 2, 4, 4)
    assert ring["hole_cells"] == frozenset(
        (r, c) for r in range(2, 5) for c in range(2, 5)
    )


def test_closed_frames_degenerate_thin_border_has_no_hole():
    """Purpose: a 2-row-thick border has no interior at all (nothing can be
    "enclosed") and must be excluded, not reported with a bogus empty or
    inverted inner_bbox.
    Expected feedback: failure means the interior-emptiness guard is
    missing, and a caller would receive a nonsensical inner_bbox for a shape
    that structurally cannot hold a hole."""
    grid = _blank(6, 6, bg=0)
    _paint_border(grid, 1, 1, 2, 4, color=5)  # only 2 rows tall -- no interior
    assert closed_frames(grid, background=0) == []


def test_elongated_axis_detects_bar_and_rejects_below_min_aspect():
    """Purpose: a bar well past the aspect threshold must report the correct
    axis/length/thickness/endpoints; a region whose aspect ratio falls short
    of min_aspect must return None rather than a false-positive axis.
    Expected feedback: failure means the aspect-ratio gate or the axis
    convention (row=tall, col=wide) is wrong, corrupting any caller that
    plans movement along the reported axis."""
    tall_bar = _region(4, [(0, 2), (1, 2), (2, 2), (3, 2), (4, 2), (5, 2)])  # 6x1
    out = elongated_axis(tall_bar, min_aspect=3.0)
    assert out == {"axis": "row", "endpoints": ((0, 2), (5, 2)), "length": 6, "thickness": 1}

    squarish = _region(4, [(0, 0), (0, 1), (1, 0), (1, 1)])  # 2x2, aspect 1.0
    assert elongated_axis(squarish, min_aspect=3.0) is None


def test_elongated_axis_wide_bar_uses_col_axis():
    """Purpose: a WIDE bar (more columns than rows) must be classified with
    axis='col' and endpoints running along the fixed row -- the orthogonal
    case to the tall-bar test, proving both branches of the row/col
    convention are exercised.
    Expected feedback: failure means the wide-bar branch swaps row/col or
    mis-picks the fixed midline row."""
    wide_bar = _region(2, [(3, 0), (3, 1), (3, 2), (3, 3), (3, 4), (3, 5)])  # 1x6
    out = elongated_axis(wide_bar, min_aspect=3.0)
    assert out == {"axis": "col", "endpoints": ((3, 0), (3, 5)), "length": 6, "thickness": 1}


def test_project_to_axis_clamps_onto_both_axis_kinds():
    """Purpose: projecting a point beyond either end of a row-axis or
    col-axis segment must clamp onto the segment, not extrapolate past it;
    a point beside the segment must project straight onto the fixed line.
    Expected feedback: failure means the clamp or the fixed-coordinate pick
    is wrong, so a caller attributing a click to the nearest axis point
    would compute a cell that is not even on the segment."""
    row_axis = {"axis": "row", "endpoints": ((0, 2), (5, 2))}
    assert project_to_axis((3, 9), row_axis) == (3, 2)  # beside the line -> onto it
    assert project_to_axis((-4, 2), row_axis) == (0, 2)  # past the top -> clamp
    assert project_to_axis((99, 2), row_axis) == (5, 2)  # past the bottom -> clamp

    col_axis = {"axis": "col", "endpoints": ((3, 0), (3, 5))}
    assert project_to_axis((9, 2), col_axis) == (3, 2)
    assert project_to_axis((3, 99), col_axis) == (3, 5)


def test_point_toward_rounds_and_clamps_at_target():
    """Purpose: point_toward must land exactly at the requested distance
    along a straight line for a clean case, and must clamp to the target
    (never overshoot) when the requested distance exceeds the actual
    origin-target distance.
    Expected feedback: failure means the direction normalization or the
    overshoot clamp is broken, which would send a caller's click past the
    intended target cell."""
    assert point_toward((0, 0), (0, 10), distance=3) == (0, 3)
    assert point_toward((0, 0), (3, 4), distance=100) == (3, 4)  # clamps at target
    assert point_toward((5, 5), (5, 5), distance=1) == (5, 5)  # already at target


def test_axis_snap_within_tolerance_zeros_minor_axis():
    """Purpose: an offset with a small residual on the non-dominant axis
    (e.g. (5, 1)) must snap that residual to zero when it's within
    tolerance, matching the axis-aligned-motion assumption downstream
    callers rely on.
    Expected feedback: failure means the tolerance/dominance comparison is
    wrong, so a caller would register a phantom step on an axis that never
    actually moved."""
    assert axis_snap((5, 1), tolerance=1) == (5, 0)
    assert axis_snap((1, 5), tolerance=1) == (0, 5)


def test_axis_snap_beyond_tolerance_is_unchanged():
    """Purpose: when the minor-axis component exceeds tolerance, the offset
    genuinely has two-axis motion and must be returned as-is, not
    incorrectly forced onto a single axis.
    Expected feedback: failure means the guard fires too aggressively,
    discarding real diagonal motion a caller needed to see."""
    assert axis_snap((5, 3), tolerance=1) == (5, 3)


def test_covering_offsets_minimal_cover_matches_greedy_result():
    """Purpose: two disjoint 2-point clusters, each exactly matching the
    shape, must be covered by exactly 2 translations -- verifying both
    minimality (no caller wants 4 single-point offsets when 2 suffice) and
    that this small case (6 candidates, so the exact branch runs) agrees
    with what a greedy newly-covered-first search would ALSO produce here:
    hand-tracing greedy on this input picks offset (0,0) first (max gain 2,
    first among gain-2 ties in sorted candidate order), then (5,5) (the only
    remaining gain-2 offset) -- identical to the exact result asserted below.
    Expected feedback: failure means either the candidate derivation missed
    the optimal offsets or the exact/greedy split disagrees on a case they
    should both solve identically."""
    shape = frozenset({(0, 0), (0, 1)})
    targets = [(0, 0), (0, 1), (5, 5), (5, 6)]
    result = covering_offsets(shape, targets)
    assert result == [(0, 0), (5, 5)]


def test_covering_offsets_single_point_needs_one_offset():
    """Purpose: a single target point must be covered by exactly one
    translation -- the minimal base case, pinning that the algorithm doesn't
    over-generate offsets for trivial input.
    Expected feedback: failure means the loop structure emits redundant
    steps even when a 1-offset cover obviously exists."""
    shape = frozenset({(0, 0), (1, 1)})
    targets = [(4, 4)]
    result = covering_offsets(shape, targets)
    assert len(result) == 1
    dr, dc = result[0]
    translated = {(sr + dr, sc + dc) for sr, sc in shape}
    assert (4, 4) in translated


def test_connectors_links_two_boxes_three_region_blob_rejected():
    """Purpose: a thin 1-cell-wide path touching exactly two given regions
    must be reported as a connector between them; a wide blob touching
    THREE regions must be rejected (not a two-endpoint link).
    Expected feedback: failure means either the thinness gate or the
    exactly-two-regions gate is missing/wrong, so a caller building a
    connectivity graph would get spurious or missing edges."""
    grid = _blank(10, 10, bg=0)
    box_a = [(1, 1), (1, 2), (2, 1), (2, 2)]
    box_b = [(1, 7), (1, 8), (2, 7), (2, 8)]
    for r, c in box_a + box_b:
        grid[r][c] = 4
    # thin 1-cell-wide pipe linking box_a's right edge to box_b's left edge
    for c in range(3, 7):
        grid[1][c] = 9
    regions = [_region(4, box_a), _region(4, box_b)]

    result = connectors(grid, regions, background=0)
    assert len(result) == 1
    conn = result[0]
    assert conn["a"] == 0 and conn["b"] == 1
    assert conn["color"] == 9
    assert conn["path_cells"] == frozenset((1, c) for c in range(3, 7))

    # A single thin pipe that 4-connectivity touches THREE regions (not a
    # two-endpoint link) must not be treated as a connector.
    grid2 = _blank(10, 12, bg=0)
    for c in range(1, 11):
        grid2[5][c] = 9  # one thin horizontal pipe, row 5, cols 1..10
    third_box_a = [(4, 2)]  # sits directly above the pipe at col 2
    third_box_b = [(4, 5)]  # sits directly above the pipe at col 5
    third_box_c = [(6, 8)]  # sits directly below the pipe at col 8
    for r, c in third_box_a + third_box_b + third_box_c:
        grid2[r][c] = 4
    regions2 = [_region(4, third_box_a), _region(4, third_box_b), _region(4, third_box_c)]
    assert connectors(grid2, regions2, background=0) == []
