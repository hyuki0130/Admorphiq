"""Tests for the pure closed-frame / fused-ring-splitting / elongated-axis /
covering-offset kernels (R56)."""

import copy
from pathlib import Path

import pytest

from admorphiq.kernels import (
    axis_snap,
    closed_frames,
    connectors,
    covering_offsets,
    elongated_axis,
    max_coverage_offset,
    point_toward,
    project_to_axis,
    recover_occluded_frame,
    split_fused_frame,
)

# data/ is gitignored (not a committed asset) -- the real-data check below
# skips itself when the trace isn't present locally, rather than failing a
# fresh clone or CI checkout that never downloaded it.
_SB26_TRACE = Path(__file__).resolve().parent.parent / "data" / "traces" / "sb26.npz"


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


def _ring_cells(r0, c0, r1, c1):
    return (
        {(r0, c) for c in range(c0, c1 + 1)}
        | {(r1, c) for c in range(c0, c1 + 1)}
        | {(r, c0) for r in range(r0, r1 + 1)}
        | {(r, c1) for r in range(r0, r1 + 1)}
    )


# A 5x5 ring (outer_bbox (0,0,4,4), inner_bbox (1,1,3,3)) reused across
# several split_fused_frame tests below.
_CLEAN_RING = _ring_cells(0, 0, 4, 4)


def test_split_fused_frame_clean_ring_has_no_appendages():
    """Purpose: a ring with nothing fused onto it must report the exact same
    border/outer/inner bbox closed_frames would (matching field shapes), with
    an EMPTY appendages list -- the trivial case a real solver relies on when
    a frame is a genuine standalone ring, not a fusion.
    Expected feedback: failure means the span-mode reconstruction doesn't
    recover the ring exactly when there's nothing to disambiguate it from."""
    out = split_fused_frame(_CLEAN_RING)
    assert out["frame"]["border_cells"] == frozenset(_CLEAN_RING)
    assert out["frame"]["outer_bbox"] == (0, 0, 4, 4)
    assert out["frame"]["inner_bbox"] == (1, 1, 3, 3)
    assert out["frame"]["hole_cells"] == frozenset((r, c) for r in range(1, 4) for c in range(1, 4))
    assert out["appendages"] == []


def test_split_fused_frame_single_pipe_defuses_with_correct_attach_point():
    """Purpose: a ring with ONE thin appendage fused onto its top border must
    still recover the exact ring geometry (unaffected by the appendage) AND
    report the appendage as its own group with the correct attach_point --
    the exact SB26 "hollow box + portal pipe fused as one component" scenario
    this kernel exists to de-fuse.
    Expected feedback: failure means the row/col span-mode approach gets
    confused by the appendage's own cells when computing the ring's true
    width/height, corrupting the recovered bbox."""
    pipe = {(-2, 2), (-1, 2)}  # sticks up from the top border at column 2
    fused = _CLEAN_RING | pipe
    out = split_fused_frame(fused)
    assert out["frame"]["outer_bbox"] == (0, 0, 4, 4)
    assert out["frame"]["border_cells"] == frozenset(_CLEAN_RING)
    assert len(out["appendages"]) == 1
    appendage = out["appendages"][0]
    assert appendage["cells"] == frozenset(pipe)
    assert appendage["attach_point"] == (0, 2)


def test_split_fused_frame_two_appendages_are_separate_groups():
    """Purpose: two DISJOINT appendages fused onto different sides of the
    ring (one vertical off the top, one horizontal off the right) must be
    reported as two SEPARATE groups, each with its own correct attach_point
    -- proving the flood-fill correctly keeps non-touching appendages apart
    and that the span-mode reconstruction is orientation-agnostic (handles
    a HORIZONTAL appendage too, not just the vertical case the original
    sort_match.py reference was scoped to).
    Expected feedback: failure means appendages merge into one group (the
    flood-fill traversed through the border) or the horizontal appendage
    corrupts the ring-height measurement."""
    pipe_top = {(-1, 2)}
    pipe_right = {(2, 5), (2, 6)}
    fused = _CLEAN_RING | pipe_top | pipe_right
    out = split_fused_frame(fused)
    assert out["frame"]["outer_bbox"] == (0, 0, 4, 4)
    assert len(out["appendages"]) == 2
    by_cells = {a["cells"]: a["attach_point"] for a in out["appendages"]}
    assert by_cells[frozenset(pipe_top)] == (0, 2)
    assert by_cells[frozenset(pipe_right)] == (2, 4)


def test_split_fused_frame_solid_blob_returns_none():
    """Purpose: a SOLID filled rectangle (no hole at all) must return None,
    not a bogus ring-plus-appendages reading with the entire interior
    misreported as "appendages" -- the same solid-vs-hollow distinction
    closed_frames makes, preserved here despite the looser (subset, not
    equality) border test this kernel otherwise uses.
    Expected feedback: failure means the hole-must-be-cell-free check is
    missing or wrong, so a filled block gets a spurious ring reading."""
    blob = {(r, c) for r in range(5) for c in range(5)}
    assert split_fused_frame(blob) is None


def test_split_fused_frame_does_not_mutate_input():
    """Purpose: the input cell set must be left exactly as given -- a caller
    that reuses or re-inspects it afterward must not observe any change.
    Expected feedback: failure means the function mutates shared state
    in-place, a surprising side effect for a "pure kernel" contract."""
    pipe = {(-1, 2)}
    fused = _CLEAN_RING | pipe
    original = copy.deepcopy(fused)
    split_fused_frame(fused)
    assert fused == original


def test_split_fused_frame_accepts_a_region_dict_directly():
    """Purpose: the function must accept EITHER a find_regions-shaped region
    dict (reading its "cells" key) or a bare iterable of cells -- both are
    documented entry points, and a caller shouldn't need to unpack a region
    dict manually before calling.
    Expected feedback: failure means only one of the two accepted input
    shapes actually works, silently breaking whichever caller convention
    isn't covered."""
    region = _region(7, _CLEAN_RING)
    out = split_fused_frame(region)
    assert out["frame"]["outer_bbox"] == (0, 0, 4, 4)
    assert out["appendages"] == []


def test_split_fused_frame_frame_validation_rejects_multi_colour_cells():
    """Purpose: when frame is supplied, every one of the given cells must
    resolve to the SAME colour in it -- a cell set spanning multiple
    colours isn't a genuine single fused component, and silently proceeding
    would compute geometry over a nonsensical mixed-colour "blob".
    Expected feedback: failure means the frame cross-check is missing or
    doesn't actually inspect every cell's colour."""
    grid = _blank(6, 6, bg=0)
    _paint_border(grid, 0, 0, 4, 4, 7)
    grid[0][0] = 3  # one corner cell recoloured -- now spans two colours
    with pytest.raises(ValueError, match="multiple colours"):
        split_fused_frame(_ring_cells(0, 0, 4, 4), frame=grid)


def test_split_fused_frame_frame_validation_rejects_background_colour():
    """Purpose: when both frame and background are supplied, a cell set
    whose colour equals the declared background isn't a fused component at
    all (it's empty space) -- must raise, not silently compute a
    "ring" out of background pixels.
    Expected feedback: failure means the background cross-check is missing,
    letting a caller accidentally run this on background cells."""
    grid = _blank(6, 6, bg=0)
    _paint_border(grid, 0, 0, 4, 4, 0)
    with pytest.raises(ValueError, match="background"):
        split_fused_frame(_ring_cells(0, 0, 4, 4), frame=grid, background=0)


# ---- recover_occluded_frame: the inverse case (MISSING, not extra, border cells) ----


def test_recover_occluded_frame_recovers_ring_when_gap_matches_an_occluder():
    """Purpose: the exact SB26 second-portal-frame scenario this kernel was
    built for -- a ring missing two border cells because a differently-
    coloured pipe crosses exactly there. Occluder cells covering precisely
    the gap must recover the FULL geometric border (including the two
    currently-foreign-coloured cells), report them as occluded_cells, and
    attribute them to the contributing occluder.
    Expected feedback: failure means either the gap-detection (bbox from the
    ring's own cells) or the occluder-coverage check is wrong -- the primary
    contract this kernel exists to satisfy."""
    gapped = _CLEAN_RING - {(4, 2), (4, 3)}
    occluder = {(4, 2), (4, 3), (5, 2), (5, 3)}  # extends past the ring too, like a real pipe
    out = recover_occluded_frame(gapped, occluders=[occluder])
    assert out["frame"]["border_cells"] == frozenset(_CLEAN_RING)
    assert out["frame"]["outer_bbox"] == (0, 0, 4, 4)
    assert out["frame"]["inner_bbox"] == (1, 1, 3, 3)
    assert out["occluded_cells"] == frozenset({(4, 2), (4, 3)})
    assert out["occluded_by"] == [{"occluder_index": 0, "cells": frozenset({(4, 2), (4, 3)})}]


def test_recover_occluded_frame_splits_credit_across_multiple_occluders():
    """Purpose: when two DIFFERENT missing cells are each covered by a
    DIFFERENT occluder, both must be recovered and occluded_by must report
    both contributors separately, by index -- proving credit assignment is
    per-occluder, not just a pooled "some occluder somewhere" check.
    Expected feedback: failure means the union-coverage check works but the
    per-occluder attribution (occluded_by) collapses distinct sources into
    one, which would break a caller trying to identify which occluder
    crosses the border where."""
    gapped = _CLEAN_RING - {(0, 2), (4, 2)}
    occluder_top = {(0, 2), (-1, 2)}
    occluder_bottom = {(4, 2), (5, 2)}
    out = recover_occluded_frame(gapped, occluders=[occluder_top, occluder_bottom])
    assert out["occluded_cells"] == frozenset({(0, 2), (4, 2)})
    by_index = {e["occluder_index"]: e["cells"] for e in out["occluded_by"]}
    assert by_index == {0: frozenset({(0, 2)}), 1: frozenset({(4, 2)})}


def test_recover_occluded_frame_unexplained_gap_returns_none():
    """Purpose: a missing border cell NOT covered by any supplied occluder
    means the gap is genuinely unexplained -- possibly just absent, not
    occluded -- and must NOT be silently recovered. This is the core safety
    property distinguishing "provable occlusion" from "any incomplete ring
    gets patched up."
    Expected feedback: failure means the kernel forces a recovery even when
    no evidence supports it, which would corrupt downstream slot/portal
    detection on a genuinely broken or partially-drawn frame."""
    gapped = _CLEAN_RING - {(4, 2), (4, 3)}
    occluder = {(4, 2)}  # only explains ONE of the two missing cells
    assert recover_occluded_frame(gapped, occluders=[occluder]) is None


def test_recover_occluded_frame_no_missing_cells_returns_none():
    """Purpose: a candidate whose cells already form a complete ring (no
    gap at all) is not an occlusion case -- this kernel deliberately does
    NOT act as a superset of closed_frames, keeping composition explicit
    (callers try closed_frames first, this only as a fallback).
    Expected feedback: failure means the kernel silently duplicates
    closed_frames' job instead of staying a distinct fallback tool."""
    assert recover_occluded_frame(_CLEAN_RING, occluders=[{(9, 9)}]) is None


def test_recover_occluded_frame_solid_blob_missing_corner_returns_none():
    """Purpose: a solid filled rectangle (interior cells present) that also
    happens to be missing one border cell must still be rejected -- the
    hole-must-be-cell-free check applies here exactly as it does in
    split_fused_frame, so a filled block is never mistaken for a hollow
    ring merely because an occluder can explain its one gap.
    Expected feedback: failure means the hole-emptiness guard was dropped
    when adapting split_fused_frame's validation to this inverse case."""
    blob = {(r, c) for r in range(5) for c in range(5)} - {(0, 0)}
    out = recover_occluded_frame(blob, occluders=[{(0, 0)}])
    assert out is None


def test_recover_occluded_frame_accepts_region_dicts_for_both_arguments():
    """Purpose: both the candidate AND each occluder must accept EITHER a
    find_regions-shaped region dict or a bare cell iterable, matching
    split_fused_frame's dual entry-point convention -- a caller composing
    straight from find_regions output should never need to manually unpack
    "cells" from either side.
    Expected feedback: failure means one of the two dict-accepting code
    paths (candidate vs. occluder) was implemented but not the other."""
    gapped = _CLEAN_RING - {(4, 2), (4, 3)}
    candidate_region = _region(7, gapped)
    occluder_region = _region(14, {(4, 2), (4, 3)})
    out = recover_occluded_frame(candidate_region, occluders=[occluder_region])
    assert out["frame"]["outer_bbox"] == (0, 0, 4, 4)
    assert out["occluded_cells"] == frozenset({(4, 2), (4, 3)})


def test_recover_occluded_frame_does_not_mutate_inputs():
    """Purpose: neither the candidate cell set nor any occluder's cell set
    may be mutated -- matching split_fused_frame's identical no-mutation
    contract, since both are meant to compose freely with a caller's own
    still-in-use region lists.
    Expected feedback: failure means the kernel mutates shared state
    in-place, a surprising side effect for a "pure kernel" contract."""
    gapped = _CLEAN_RING - {(4, 2), (4, 3)}
    occluder = {(4, 2), (4, 3)}
    gapped_before, occluder_before = copy.deepcopy(gapped), copy.deepcopy(occluder)
    recover_occluded_frame(gapped, occluders=[occluder])
    assert gapped == gapped_before
    assert occluder == occluder_before


@pytest.mark.skipif(not _SB26_TRACE.exists(), reason="data/traces/sb26.npz not present locally (gitignored)")
def test_recover_occluded_frame_real_sb26_second_portal_frame():
    """Purpose: real-data check against the actual SB26 gold-trace frame
    this kernel was built to diagnose -- level_index 1, frame 10 of
    data/traces/sb26.npz. The colour-8 ring at outer_bbox (18,18,27,45) is
    missing exactly the two cells (27,34)/(27,35) where a colour-14 portal
    pipe (one 98-cell connected component spanning an icon, a connecting
    pipe, and a second embedded ring at outer_bbox (32,18,41,45)) crosses
    its bottom border. Composing recover_occluded_frame (for the colour-8
    frame, occluder = the colour-14 blob) with split_fused_frame (for the
    colour-14 blob's own embedded second ring) must recover BOTH of
    sb26's two portal frames from one frame, closing the gap the R56 round
    page recorded as sb26's remaining kernel-coverage limitation.
    Expected feedback: failure means the diagnosis or the kernel doesn't
    actually hold on the real game data it was built from -- a synthetic-
    only pass would be insufficient evidence for this specific claim."""
    import numpy as np

    from admorphiq.kernels import find_regions

    data = np.load(_SB26_TRACE, allow_pickle=True)
    frame = data["frames"][10]
    grid = tuple(tuple(int(v) for v in row) for row in frame)
    regions = find_regions(grid, background=4)

    frame_a = next(r for r in regions if r["color"] == 8 and r["bbox"] == (18, 18, 27, 45))
    pipe = next(r for r in regions if r["color"] == 14 and r["bbox"] == (21, 18, 41, 45))

    recovered_a = recover_occluded_frame(frame_a, occluders=[pipe])
    assert recovered_a is not None
    assert recovered_a["frame"]["outer_bbox"] == (18, 18, 27, 45)
    assert recovered_a["occluded_cells"] == frozenset({(27, 34), (27, 35)})

    recovered_b = split_fused_frame(pipe)
    assert recovered_b is not None
    assert recovered_b["frame"]["outer_bbox"] == (32, 18, 41, 45)


def test_max_coverage_offset_claims_the_subset_one_piece_can_cover():
    """Purpose: when a piece cannot cover every target at once, gate-claiming
    needs the SINGLE translation covering the most targets (unlike
    covering_offsets, which returns a multi-offset set). A horizontal 2-cell
    piece over three points must pick the offset landing on the adjacent PAIR.
    Expected feedback: a FAIL means a multi-piece cover (re86 L3) cannot greedily
    assign each piece the subset it reaches, so no partition is found."""
    shape = [(0, 0), (0, 1)]
    points = [(5, 5), (5, 6), (9, 9)]
    off, covered = max_coverage_offset(shape, points)
    assert off == (5, 5)
    assert covered == frozenset({0, 1})


def test_max_coverage_offset_none_on_empty_input():
    """Purpose: empty shape or empty target list has no coverage to maximise.
    Expected feedback: a FAIL means the claimer would crash or fabricate an
    offset on a degenerate scene."""
    assert max_coverage_offset([], [(1, 1)]) is None
    assert max_coverage_offset([(0, 0)], []) is None
