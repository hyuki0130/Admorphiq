"""Tests for the pure 1D/structural measurement kernels (axis-neutral
occupied-run projection, exact pitch-based run splitting, generic colour
histogram, size-jump clustering) (R56)."""

import copy

import pytest

from admorphiq.kernels import (
    cluster_widths,
    color_mode,
    occupied_runs,
    size_clusters,
    split_runs_by_pitch,
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


# Three runs shaped exactly like TR87's measured upper-grid widths (7, 14,
# 21 -- single, double, and triple pitch-multiples), used across several
# split_runs_by_pitch tests below.
_PITCH_RUNS = [
    {"start": 0, "end": 7, "cells": frozenset({(0, 2), (1, 4)})},
    {"start": 10, "end": 24, "cells": frozenset({(0, 10), (0, 17), (1, 23)})},
    {"start": 30, "end": 51, "cells": frozenset({(0, 30), (0, 37), (0, 44), (1, 50)})},
]


def test_split_runs_by_pitch_col_axis_recovers_7_14_21():
    """Purpose: the exact TR87-shaped case -- a 7px (single), 14px (double),
    and 21px (triple) run must split into 1, 2, and 3 pitch-wide children
    respectively, with cells correctly partitioned by COLUMN membership in
    each child's span (axis="col").
    Expected feedback: failure means the core split loop or the col-axis
    cell-partition predicate is wrong -- this is the exact measurement that
    recovered all 24 TR87 tokens across levels 1 and 2."""
    children = split_runs_by_pitch(_PITCH_RUNS, 7, axis="col")
    assert len(children) == 6
    assert children[0] == {"start": 0, "end": 7, "cells": frozenset({(0, 2), (1, 4)}), "parent_index": 0}
    assert children[1] == {"start": 10, "end": 17, "cells": frozenset({(0, 10)}), "parent_index": 1}
    assert children[2] == {
        "start": 17,
        "end": 24,
        "cells": frozenset({(0, 17), (1, 23)}),
        "parent_index": 1,
    }
    assert children[3] == {"start": 30, "end": 37, "cells": frozenset({(0, 30)}), "parent_index": 2}
    assert children[4] == {"start": 37, "end": 44, "cells": frozenset({(0, 37)}), "parent_index": 2}
    assert children[5] == {
        "start": 44,
        "end": 51,
        "cells": frozenset({(0, 44), (1, 50)}),
        "parent_index": 2,
    }


def test_split_runs_by_pitch_row_axis_partitions_by_row_not_column():
    """Purpose: axis="row" must partition cells by ROW membership in each
    child span, not column -- the transposed dual of the col-axis test,
    proving axis genuinely changes which coordinate drives both the span
    arithmetic and the cell filter (a single run here, spanning rows, with
    cells that would be split differently under the wrong axis).
    Expected feedback: failure means the axis="row" branch reuses the
    col-axis cell filter instead of switching to row membership."""
    runs = [{"start": 0, "end": 14, "cells": frozenset({(2, 0), (2, 9), (12, 5)})}]
    children = split_runs_by_pitch(runs, 7, axis="row")
    assert children == [
        {"start": 0, "end": 7, "cells": frozenset({(2, 0), (2, 9)}), "parent_index": 0},
        {"start": 7, "end": 14, "cells": frozenset({(12, 5)}), "parent_index": 0},
    ]


def test_split_runs_by_pitch_width_equals_pitch_is_a_single_unchanged_child():
    """Purpose: a run whose width exactly equals pitch is not a "special
    case" that bypasses the algorithm -- it naturally produces exactly one
    child spanning the whole original run, with cells unchanged, via the
    SAME division logic as any other run (width // pitch == 1).
    Expected feedback: failure means single-glyph runs (the common case --
    most TR87 rule sides are 1 token) get mangled or dropped."""
    runs = [{"start": 5, "end": 12, "cells": frozenset({(0, 5), (0, 11)})}]
    assert split_runs_by_pitch(runs, 7, axis="col") == [
        {"start": 5, "end": 12, "cells": frozenset({(0, 5), (0, 11)}), "parent_index": 0}
    ]


def test_split_runs_by_pitch_empty_input_returns_empty():
    """Purpose: no runs to split means no children, trivially -- must not
    raise or fabricate output for empty input.
    Expected feedback: failure means the function crashes or misbehaves on
    the degenerate empty-list case a caller might legitimately pass (e.g.
    an all-background band)."""
    assert split_runs_by_pitch([], 7, axis="col") == []


def test_split_runs_by_pitch_rejects_non_positive_pitch():
    """Purpose: a zero or negative pitch is nonsensical (can't tile a span
    with zero or negative width) and must be rejected up front, not produce
    a division-by-zero or an infinite/negative child count.
    Expected feedback: failure means invalid pitch is silently accepted
    instead of raising a clear, immediate error."""
    with pytest.raises(ValueError, match="pitch"):
        split_runs_by_pitch(_PITCH_RUNS, 0, axis="col")
    with pytest.raises(ValueError, match="pitch"):
        split_runs_by_pitch(_PITCH_RUNS, -3, axis="col")


def test_split_runs_by_pitch_rejects_unknown_axis():
    """Purpose: axis is a closed two-value enum ('row'/'col') -- any other
    value is a caller contract violation and must raise clearly.
    Expected feedback: failure means an invalid axis is silently treated as
    one of the two valid values instead of surfaced as an error."""
    with pytest.raises(ValueError, match="axis"):
        split_runs_by_pitch(_PITCH_RUNS, 7, axis="diagonal")


def test_split_runs_by_pitch_raises_on_nonzero_remainder_never_truncates():
    """Purpose: EXACT division only -- a run whose width is NOT a clean
    multiple of pitch (e.g. width 15 against pitch 7, remainder 1) must
    raise, not silently truncate to 2 children and drop a column, or round
    to some approximate split. This is the specific behaviour Codex's
    ruling required: pitch inference belongs to the caller, but once a
    pitch is supplied, the kernel must never guess through a mismatch.
    Expected feedback: failure means a genuinely wrong pitch (caller bug,
    or a run that isn't actually pitch-tileable -- e.g. TR87 bar2's
    fragmented debris runs) would silently corrupt token boundaries instead
    of surfacing as an error."""
    runs = [{"start": 0, "end": 15, "cells": frozenset()}]
    with pytest.raises(ValueError, match="not an exact multiple"):
        split_runs_by_pitch(runs, 7, axis="col")


def test_split_runs_by_pitch_preserves_parent_index_provenance():
    """Purpose: every child, whether split from a multi-glyph run or passed
    through as a single-glyph run, must carry the INDEX of its own run in
    the input sequence -- this is what lets a caller re-apply grouping
    already computed over the raw (pre-split) runs, e.g. TR87's gap-width
    rule-side pairing, to the split children afterward.
    Expected feedback: failure means downstream grouping logic loses track
    of which original run (and therefore which rule side) a recovered
    token came from."""
    children = split_runs_by_pitch(_PITCH_RUNS, 7, axis="col")
    assert [c["parent_index"] for c in children] == [0, 1, 1, 2, 2, 2]


def test_split_runs_by_pitch_does_not_mutate_input():
    """Purpose: the input ``runs`` list and its dicts must be left exactly
    as given -- a caller that reuses the same run list for something else
    (or re-inspects it after splitting) must not observe any change.
    Expected feedback: failure means the function mutates shared state
    in-place, a surprising side effect for a "pure kernel" contract."""
    original = copy.deepcopy(_PITCH_RUNS)
    split_runs_by_pitch(_PITCH_RUNS, 7, axis="col")
    assert _PITCH_RUNS == original


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
