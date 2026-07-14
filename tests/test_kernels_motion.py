"""Tests for the pure frame-diff / object-tracking / learned-operator kernels (R56)."""

from admorphiq.kernels import (
    changed_region_attribution,
    frame_diff,
    learn_point_operators,
    motion_vectors,
    plan_overwrites,
    track_objects,
)

_BG = 0


def _region(color, cells, size=None):
    cells = list(cells)
    rows = [r for r, _c in cells]
    cols = [c for _r, c in cells]
    return {
        "color": color,
        "cells": frozenset(cells),
        "bbox": (min(rows), min(cols), max(rows), max(cols)),
        "centroid": (sum(rows) / len(cells), sum(cols) / len(cells)),
        "size": size if size is not None else len(cells),
    }


def _blank(h, w, bg=_BG):
    return tuple(tuple(bg for _ in range(w)) for _ in range(h))


def _with_cells(frame, cells, color):
    grid = [list(row) for row in frame]
    for r, c in cells:
        grid[r][c] = color
    return tuple(tuple(row) for row in grid)


def test_frame_diff_identical_frames_have_zero_count_and_none_bbox():
    """Purpose: two identical frames must diff to nothing — count 0, cells
    empty, bbox None — establishing the baseline "no action effect" case
    every downstream consumer (attribution, operator learning) relies on.
    Expected feedback: failure means the diff loop is miscomparing values
    (e.g. type mismatch between int and str color indices)."""
    frame = _with_cells(_blank(4, 4), [(1, 1), (2, 2)], color=3)
    diff = frame_diff(frame, frame)
    assert diff == {"cells": frozenset(), "bbox": None, "count": 0}


def test_frame_diff_reports_changed_cells_and_inclusive_bbox():
    """Purpose: a diff between two frames must report exactly the changed
    cells and a tight INCLUSIVE bounding box around them.
    Expected feedback: failure means either the changed-cell set is wrong
    (missed or spurious cells) or the bbox math is off-by-one, corrupting
    every caller that crops around the change (e.g. changed_region_attribution
    callers that visualize the diff)."""
    before = _blank(5, 5)
    after = _with_cells(before, [(1, 2), (3, 4)], color=7)
    diff = frame_diff(before, after)
    assert diff["cells"] == frozenset({(1, 2), (3, 4)})
    assert diff["bbox"] == (1, 2, 3, 4)
    assert diff["count"] == 2


def test_changed_region_attribution_ranks_most_overlapped_region_first():
    """Purpose: when a diff touches multiple regions unevenly, attribution
    must rank by intersection size descending — the region most responsible
    for the observed change should be first, not just any touched region.
    Expected feedback: failure means callers (e.g. a rotation-puzzle solver
    deciding which piece a click affected) would credit the wrong region."""
    diff_cells = [(0, 0), (0, 1), (0, 2), (5, 5)]
    regions = [
        _region(1, [(0, 0), (0, 1)]),  # overlap 2
        _region(2, [(0, 2), (9, 9)]),  # overlap 1
        _region(3, [(8, 8)]),  # overlap 0 -- excluded
    ]
    assert changed_region_attribution(diff_cells, regions) == [0, 1]


def test_changed_region_attribution_ties_break_by_index():
    """Purpose: two regions with equal intersection size must be ordered by
    index ascending, not left to dict/set iteration order.
    Expected feedback: failure means the ranking is nondeterministic across
    runs, breaking reproducible attribution."""
    diff_cells = [(0, 0), (1, 1)]
    regions = [_region(1, [(1, 1)]), _region(2, [(0, 0)])]
    assert changed_region_attribution(diff_cells, regions) == [0, 1]


def test_track_objects_matches_translated_object_and_reports_shift():
    """Purpose: a single same-color, same-shape region that moved between
    frames must be matched to itself and its (dr, dc) shift reported exactly.
    Expected feedback: failure means shape-signature matching or the shift
    computation is wrong, which would corrupt motion_vectors for every
    movement-class game (merge_drag's core capability)."""
    before = [_region(5, [(1, 1), (1, 2)])]
    after = [_region(5, [(3, 4), (3, 5)])]
    result = track_objects(before, after)
    assert result["matches"] == [{"before": 0, "after": 0, "shift": (2, 3)}]
    assert result["vanished"] == []
    assert result["appeared"] == []


def test_track_objects_reports_vanished_and_appeared():
    """Purpose: a region present only in the before-frame (no plausible
    after-match) must be flagged vanished; one present only in the
    after-frame must be flagged appeared -- objects don't silently disappear
    from the accounting.
    Expected feedback: failure means object permanence bookkeeping is wrong,
    so a caller building an entity map would lose track of pieces."""
    before = [_region(5, [(0, 0)])]
    after = [_region(9, [(0, 0)])]  # different color: not a candidate match
    result = track_objects(before, after)
    assert result["matches"] == []
    assert result["vanished"] == [0]
    assert result["appeared"] == [0]


def test_track_objects_max_shift_excludes_far_pairs():
    """Purpose: max_shift must cap how far a centroid may move and still be
    considered the same object -- an out-of-range same-color region must NOT
    be matched, even though it's the only same-color candidate.
    Expected feedback: failure means max_shift is ignored, so a distant
    same-color region could be mistaken for the tracked object's new
    position (e.g. confusing two separate same-color sprites)."""
    before = [_region(5, [(0, 0)])]
    after = [_region(5, [(20, 20)])]
    result = track_objects(before, after, max_shift=5.0)
    assert result["matches"] == []
    assert result["vanished"] == [0]
    assert result["appeared"] == [0]


def test_track_objects_stage2_finds_exact_optimum_greedy_would_miss():
    """Purpose: R56 API-inconsistency fix #2 — Stage 2 (the no-shape-match
    fallback) now composes shapes.assign_pairs for an EXACT minimum-total-
    distance assignment instead of a greedy nearest-centroid-first pass.
    This crafted geometry has a genuine greedy failure mode: P0=(0,0) sits
    exactly 1.0 from BOTH Q0=(0,1) and (indirectly, via the crossed pairing)
    contributes to a cheaper total than the 'obvious' pairing. Concretely,
    distances are d(P0,Q0)=1.0, d(P0,Q1)=1.0, d(P1,Q0)=9.0,
    d(P1,Q1)=~10.05. A greedy nearest-edge-first pass grabs the single
    smallest edge (P0-Q0, tied with P0-Q1 but ordered first) immediately,
    forcing the leftover pair P1-Q1 (total 1.0+10.05=11.05). The TRUE
    optimum is the crossed pairing P0-Q1 + P1-Q0 (total 1.0+9.0=10.0) —
    strictly cheaper, and unreachable by any greedy nearest-first strategy
    once it has already committed to P0-Q0. Regions are single-cell
    (before) vs two-cell (after) so no pair can ever shape-match, forcing
    100% of the matching through the refactored Stage 2.
    Expected feedback: failure (matching the OLD greedy pairing, before=0-
    after=0 and before=1-after=1) means Stage 2 silently reverted to greedy
    and is no longer finding the true optimum — exactly the regression this
    test exists to catch."""
    before = [_region(5, [(0, 0)]), _region(5, [(0, 10)])]
    after = [_region(5, [(0, 0), (0, 2)]), _region(5, [(0, 0), (2, 0)])]
    result = track_objects(before, after)
    assert result["matches"] == [
        {"before": 0, "after": 1, "shift": (1, 0)},
        {"before": 1, "after": 0, "shift": (0, -9)},
    ]
    assert result["vanished"] == []
    assert result["appeared"] == []


def test_track_objects_stage2_forced_full_coverage_pick_is_filtered_by_max_shift():
    """Purpose: shapes.assign_pairs always returns a FULL assignment over the
    smaller side, even when some of those pairs are scored with the
    ineligible-pair sentinel (see motion._INELIGIBLE_SCORE) — so Stage 2
    must explicitly re-check max_shift on assign_pairs' own output and
    discard any pair that only got picked because assign_pairs was forced
    to cover every slot. Here only (before=0, after=0) is genuinely within
    max_shift=5.0 (distance 1.0); every other pairing in this 2x2 matrix
    exceeds it (49, 80, ~30) — a naive 'trust assign_pairs' output as-is'
    implementation would incorrectly report a second forced match for the
    remaining (before=1, after=1) slot instead of leaving both unmatched.
    Expected feedback: failure (a spurious second match appearing) means the
    post-assign_pairs eligibility filter was removed or bypassed, silently
    re-introducing exactly the bug max_shift exists to prevent."""
    before = [_region(5, [(0, 0)]), _region(5, [(0, 50)])]
    after = [_region(5, [(0, 0), (0, 2)]), _region(5, [(0, 79), (0, 81)])]
    result = track_objects(before, after, max_shift=5.0)
    assert result["matches"] == [{"before": 0, "after": 0, "shift": (0, 1)}]
    assert result["vanished"] == [1]
    assert result["appeared"] == [1]


def test_motion_vectors_dominant_shift_by_frequency():
    """Purpose: dominant must be the most frequent nonzero per-object shift,
    not merely the first or the largest.
    Expected feedback: failure means downstream global-motion inference
    (e.g. 'the camera/board shifted by X') would pick the wrong vector."""
    matches = [
        {"before": 0, "after": 0, "shift": (1, 0)},
        {"before": 1, "after": 1, "shift": (1, 0)},
        {"before": 2, "after": 2, "shift": (0, 2)},
    ]
    out = motion_vectors(matches)
    assert out["per_object"] == [(1, 0), (1, 0), (0, 2)]
    assert out["dominant"] == (1, 0)


def test_motion_vectors_ties_prefer_smallest_l1_then_lexicographic():
    """Purpose: when two shifts tie on frequency, the smaller-L1-norm one
    wins; if L1 also ties, the lexicographically smaller tuple wins -- a
    fixed, reproducible tie-break rather than dict-iteration-order luck.
    Expected feedback: failure means dominant-vector selection is
    nondeterministic across equivalent runs."""
    matches = [
        {"before": 0, "after": 0, "shift": (3, 0)},  # L1 3, count 2
        {"before": 1, "after": 1, "shift": (3, 0)},
        {"before": 2, "after": 2, "shift": (1, 1)},  # L1 2, count 2 -- ties on count, wins on L1
        {"before": 3, "after": 3, "shift": (1, 1)},
    ]
    out = motion_vectors(matches)
    assert out["dominant"] == (1, 1)

    tie_matches = [
        {"before": 0, "after": 0, "shift": (0, 1)},
        {"before": 1, "after": 1, "shift": (1, 0)},
    ]
    assert motion_vectors(tie_matches)["dominant"] == (0, 1)


def test_motion_vectors_all_zero_shifts_yields_no_dominant():
    """Purpose: a set of matches where nothing actually moved must report
    dominant=None, not (0, 0) -- (0, 0) is 'no motion', which is different
    from 'motion detected, direction X'.
    Expected feedback: failure means a caller checking `if dominant:` for
    'did anything move' would be fooled by a truthy (0, 0)-shaped mistake,
    or a caller relying on None would crash unpacking a fake vector."""
    matches = [{"before": 0, "after": 0, "shift": (0, 0)}]
    out = motion_vectors(matches)
    assert out["dominant"] is None


def test_learn_point_operators_clusters_identical_effects_and_flags_no_change():
    """Purpose: two clicks with identical write footprints must cluster into
    ONE operator with support 2 and both points recorded; a third click with
    no effect must NOT be folded into that operator -- it forms its own
    empty-footprint operator, distinguishable from a real effect.
    Expected feedback: failure means either operator clustering conflates
    distinct effects, or a no-op click contaminates a real learned operator
    (which would make plan_overwrites apply a "no effect" step believing it
    does something)."""
    base = _blank(4, 4)
    after_effect = _with_cells(base, [(0, 0), (0, 1)], color=6)
    observations = [
        {"point": (2, 2), "before": base, "after": _with_cells(base, [(2, 2), (2, 3)], color=6)},
        {"point": (1, 1), "before": base, "after": _with_cells(base, [(1, 1), (1, 2)], color=6)},
        {"point": (3, 3), "before": base, "after": base},  # no-change
    ]
    operators = learn_point_operators(observations)
    assert len(operators) == 2

    real = next(op for op in operators if op["footprint"])
    assert real["support"] == 2
    assert real["footprint"] == frozenset({(0, 0), (0, 1)})
    assert real["writes"] == {(0, 0): 6, (0, 1): 6}
    assert set(real["points"]) == {(2, 2), (1, 1)}

    noop = next(op for op in operators if not op["footprint"])
    assert noop["support"] == 1
    assert noop["writes"] == {}
    assert noop["points"] == [(3, 3)]
    del after_effect  # unused sample retained only to document the effect shape


def test_plan_overwrites_solves_small_puzzle_with_two_operators():
    """Purpose: given two learned operators, plan_overwrites must find a
    step sequence that transforms initial into target, applying operators at
    the points that make progress -- proving the greedy search actually
    reaches a real target, not just that it terminates.
    Expected feedback: failure means the greedy scoring (fixed - broken) or
    the apply-in-bounds logic is wrong, so a caller could not turn learned
    click effects into an action plan."""
    initial = _blank(2, 2)
    target = _with_cells(initial, [(0, 0)], color=6)
    target = _with_cells(target, [(1, 1)], color=6)
    operators = [
        {"footprint": frozenset({(0, 0)}), "writes": {(0, 0): 6}, "support": 1, "points": [(0, 0)]},
        {"footprint": frozenset({(0, 0)}), "writes": {(0, 0): 6}, "support": 1, "points": [(1, 1)]},
    ]
    steps = plan_overwrites(initial, target, operators, max_steps=8)
    assert steps is not None

    state = [list(row) for row in initial]
    for step in steps:
        r, c = step["point"]
        for (dr, dc), color in operators[step["operator"]]["writes"].items():
            rr, cc = r + dr, c + dc
            if 0 <= rr < 2 and 0 <= cc < 2:
                state[rr][cc] = color
    assert tuple(tuple(row) for row in state) == target


def test_plan_overwrites_returns_none_when_unsolvable():
    """Purpose: when no available operator can ever produce the target color
    at some cell, plan_overwrites must return None rather than an infinite
    or a silently-incomplete step list.
    Expected feedback: failure means a caller would believe a plan succeeded
    (or hang) when the learned operator vocabulary genuinely cannot reach
    the target -- a false positive is worse than an honest None."""
    initial = _blank(2, 2)
    target = _with_cells(initial, [(0, 0)], color=9)  # no operator ever writes 9
    operators = [
        {"footprint": frozenset({(0, 0)}), "writes": {(0, 0): 6}, "support": 1, "points": [(0, 0)]},
    ]
    assert plan_overwrites(initial, target, operators, max_steps=8) is None
