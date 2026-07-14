"""Tests for the pure 1D/structural measurement kernels (axis-neutral
occupied-run projection, generic colour histogram, size-jump clustering)
(R56)."""

import pytest

from admorphiq.kernels import (
    cluster_widths,
    color_mode,
    occupied_runs,
    size_clusters,
)

# Two-row band with THREE two-colour content runs (fill+ink, neither
# colour alone would stay 4-connected across both rows) separated by
# gaps of different widths (2 and 3 background columns) -- the exact
# "single-colour connected components fragment a 2-colour cell" scenario
# that motivated this module (see parse.py's docstring). Row1 col3 is
# deliberately background (0) so run 0's "cells" must exclude it even
# though columns 2-4 all belong to the run's column SPAN.
_ROW0 = [0, 0, 5, 9, 5, 0, 0, 7, 9, 7, 0, 0, 0, 5, 9, 0, 0]
_ROW1 = [0, 0, 9, 0, 9, 0, 0, 9, 7, 9, 0, 0, 0, 9, 5, 0, 0]
_FRAME = [_ROW0, _ROW1]


def test_occupied_runs_segments_two_colour_content_correctly():
    """Purpose: a region with 2-colour (fill+ink) content must segment into
    exactly its 3 true runs by background-only column runs -- NOT fragment
    into more runs the way single-colour connected-component segmentation
    would (a 2-colour block's own ink pixels need not be 4-connected). Also
    pins that "cells" excludes a background cell that falls WITHIN a run's
    column span (row1 col3).
    Expected feedback: failure means the has-content test or the cells
    filter is wrong, corrupting every downstream consumer."""
    out = occupied_runs(_FRAME, axis="col", background=0)
    runs = out["runs"]
    assert [(r["start"], r["end"]) for r in runs] == [(2, 5), (7, 10), (13, 15)]
    assert runs[0]["cells"] == frozenset({(0, 2), (0, 3), (0, 4), (1, 2), (1, 4)})
    assert runs[1]["cells"] == frozenset({(0, 7), (0, 8), (0, 9), (1, 7), (1, 8), (1, 9)})
    assert runs[2]["cells"] == frozenset({(0, 13), (0, 14), (1, 13), (1, 14)})


def test_occupied_runs_gap_widths_between_consecutive_runs():
    """Purpose: the reported gap widths must be the exact background-only
    column counts strictly BETWEEN consecutive runs (2 then 3 here, by
    construction), with exactly len(runs)-1 entries.
    Expected feedback: failure means the gap-width arithmetic is off by
    one, or gaps are computed against the wrong pair of runs."""
    out = occupied_runs(_FRAME, axis="col", background=0)
    assert out["gaps"] == [2, 3]


def test_occupied_runs_all_background_region_is_empty():
    """Purpose: a region with no content at all must return empty runs AND
    empty gaps, not raise or return a spurious single run.
    Expected feedback: failure means the in-run/out-of-run state machine
    mishandles the degenerate all-background case."""
    assert occupied_runs([[0, 0, 0], [0, 0, 0]], background=0) == {"runs": [], "gaps": []}


def test_occupied_runs_axis_row_is_the_transpose_of_axis_col():
    """Purpose: axis="row" must project along rows exactly the way axis="col"
    projects along columns (transposed) -- a genuinely different scan
    direction, not a no-op alias. Transposing _FRAME (rows<->cols) and
    scanning axis="row" on the transposed grid must reproduce axis="col"'s
    runs on the original, with (row,col) cells swapped accordingly.
    Expected feedback: failure means the axis="row" branch's primary/cross
    dimension selection is wrong."""
    transposed = list(map(list, zip(*_FRAME, strict=True)))
    col_result = occupied_runs(_FRAME, axis="col", background=0)
    row_result = occupied_runs(transposed, axis="row", background=0)
    assert [(r["start"], r["end"]) for r in row_result["runs"]] == [
        (r["start"], r["end"]) for r in col_result["runs"]
    ]
    assert row_result["gaps"] == col_result["gaps"]
    for row_run, col_run in zip(row_result["runs"], col_result["runs"], strict=True):
        assert row_run["cells"] == {(c, r) for r, c in col_run["cells"]}


def test_occupied_runs_bbox_restricts_the_scan():
    """Purpose: a caller-supplied bbox must restrict BOTH which lines are
    scanned (the cross-axis range) and which positions are considered (the
    primary-axis range) -- a run entirely outside bbox must not appear, and
    background is resolved (when auto) only from within bbox.
    Expected feedback: failure means bbox is ignored or only partially
    applied (e.g. cross-axis range honored but primary-axis range is not)."""
    # Restrict to rows 0 only (drops row 1) and columns 0-9 (drops the run at 13-15).
    out = occupied_runs(_FRAME, axis="col", bbox=(0, 0, 0, 9), background=0)
    assert [(r["start"], r["end"]) for r in out["runs"]] == [(2, 5), (7, 10)]
    assert out["runs"][0]["cells"] == frozenset({(0, 2), (0, 3), (0, 4)})


def test_occupied_runs_rejects_unknown_axis():
    """Purpose: an axis value other than 'row'/'col' is a caller contract
    violation and must raise clearly, not silently default to one behavior.
    Expected feedback: failure means invalid input is accepted instead of
    surfaced as an error."""
    with pytest.raises(ValueError, match="axis"):
        occupied_runs(_FRAME, axis="diagonal")


def test_color_mode_ranks_by_frequency_descending():
    """Purpose: color_mode must rank purely by frequency, with no
    background/ink/majority semantics baked in -- just a histogram.
    Expected feedback: failure means the ranking or count is wrong."""
    values = [5, 5, 5, 7, 7, 0]
    assert color_mode(values, k=3) == [
        {"color": 5, "count": 3},
        {"color": 7, "count": 2},
        {"color": 0, "count": 1},
    ]


def test_color_mode_ties_break_by_first_encountered_order():
    """Purpose: values tied on count must be ordered by which was first
    encountered while consuming the input -- deterministic, not dependent on
    dict/set iteration order.
    Expected feedback: failure means Counter's insertion-order stability
    guarantee was broken by an intermediate re-ordering step."""
    values = [9, 5, 5, 7, 7, 9]  # 9 first-seen at index0, 5 at index1, 7 at index3 -- all count 2
    assert color_mode(values, k=3) == [
        {"color": 9, "count": 2},
        {"color": 5, "count": 2},
        {"color": 7, "count": 2},
    ]


def test_color_mode_k_limits_and_never_pads():
    """Purpose: k caps how many entries come back, but never PADS past the
    number of distinct values actually present (k=5 on 2 distinct values
    returns exactly 2 entries, not 5 with fabricated zero-count fillers).
    Expected feedback: failure means the function invents entries for
    colours that were never observed."""
    assert color_mode([1, 1, 2], k=1) == [{"color": 1, "count": 2}]
    assert color_mode([1, 1, 2], k=5) == [{"color": 1, "count": 2}, {"color": 2, "count": 1}]
    assert color_mode([], k=2) == []


def test_color_mode_caller_supplies_the_mask_predicate():
    """Purpose: color_mode has no "background" parameter and no ink/minority
    concept -- a caller who wants to exclude a colour (or restrict to
    specific cells) does so BEFORE calling, by filtering the values they
    pass in. This proves that composition works and produces the expected
    result once background(9) is caller-filtered out.
    Expected feedback: failure means color_mode secretly special-cases some
    value instead of being a pure frequency count over whatever it's given."""
    band = [[9, 5, 5, 7, 7, 9], [9, 5, 5, 7, 7, 9]]
    all_values = [v for row in band for v in row]
    filtered = [v for v in all_values if v != 9]
    assert color_mode(all_values, k=1) == [{"color": 9, "count": 4}]
    assert color_mode(filtered, k=2) == [{"color": 5, "count": 4}, {"color": 7, "count": 4}]


def test_cluster_widths_matches_size_clusters_on_the_same_fixture():
    """Purpose: regions.size_clusters now DELEGATES to cluster_widths --
    calling cluster_widths directly on the regions' own size list must
    produce the byte-identical clustering size_clusters returns (using the
    fixture already pinned by test_kernels_regions.py's own
    test_size_clusters_splits_at_ratio_jump, so this also proves the
    refactor didn't silently change size_clusters' observable behaviour).
    Expected feedback: failure means the delegation changed sort/tie-break
    behaviour, silently breaking every existing size_clusters caller."""
    regions = [
        {"size": 10},
        {"size": 50},
        {"size": 12},
        {"size": 55},
        {"size": 11},
        {"size": 48},
    ]
    widths = [r["size"] for r in regions]
    expected = [[0, 4, 2], [5, 1, 3]]
    assert cluster_widths(widths, ratio=1.5) == expected
    assert size_clusters(regions, ratio=1.5) == expected
