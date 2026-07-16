"""Tests for the pure frame-diff / object-tracking / learned-operator kernels (R56)."""

from admorphiq.kernels import (
    changed_region_attribution,
    frame_diff,
    learn_point_operators,
    motion_vectors,
    plan_overwrites,
    separate_by_motion,
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


# ── reflective-symmetry kernels (learn_reflection_operators / plan) ─────────

from admorphiq.kernels import (  # noqa: E402
    learn_reflection_operators,
    plan_reflection_coverage,
    reflect_cells,
    reflection_orbit,
)

_MIRROR_K = 19  # doubled vertical-axis position: reflect column c -> 19 - c


def _reflect_v(cells, k=_MIRROR_K):
    return {(r, k - c) for r, c in cells}


def _render_mirror(piece_cells, piece_color=5, image_color=4, h=24, w=24, bg=0):
    """A frame with ``piece_cells`` painted ``piece_color`` and its vertical
    reflection painted ``image_color`` (the distinct colour a kaleidoscope
    renders reflections in), on a ``bg`` field."""
    g = [[bg] * w for _ in range(h)]
    for r, c in _reflect_v(piece_cells):
        if 0 <= r < h and 0 <= c < w:
            g[r][c] = image_color
    for r, c in piece_cells:
        g[r][c] = piece_color
    return tuple(tuple(row) for row in g)


def test_reflect_cells_col_and_row_axes():
    """Purpose: reflect_cells must implement the doubled-axis convention
    exactly — a 'col' axis mirrors the column (c -> k - c) and a 'row' axis
    mirrors the row (r -> k - r) — because the whole coverage planner's
    footprint prediction is built on this one transform.
    Expected feedback: failure means every reflected footprint is wrong, so
    plan_reflection_coverage would target the wrong cells."""
    assert reflect_cells({(2, 3)}, ("col", 19)) == frozenset({(2, 16)})
    assert reflect_cells({(2, 3)}, ("row", 10)) == frozenset({(8, 3)})


def test_reflection_orbit_single_axis_is_involution_and_two_axes_close():
    """Purpose: the orbit under one axis is exactly the cells plus their one
    reflection (reflection is an involution — no infinite growth), and under
    two axes it closes to a finite set clipped to bounds (a mirror only
    renders on-grid).
    Expected feedback: failure means the rendered footprint is either
    incomplete (misses a reflected copy, undercounting coverage) or fails to
    terminate on a multi-axis board."""
    single = reflection_orbit({(2, 3)}, [("col", 19)], bounds=(24, 24))
    assert single == frozenset({(2, 3), (2, 16)})
    two = reflection_orbit({(2, 3)}, [("col", 19), ("row", 10)], bounds=(24, 24))
    # (2,3) -> col:(2,16) -> row:(8,16); (2,3) -> row:(8,3); closure of 4.
    assert two == frozenset({(2, 3), (2, 16), (8, 3), (8, 16)})


def test_learn_reflection_operators_recovers_axis_piece_and_deltas():
    """Purpose: from a column-move observation (which splits the piece from
    its reflected image by opposite column shift) plus a row-move
    observation, the kernel must recover the vertical mirror axis, the
    driven piece's colours, its FULL colour-membership footprint (not
    track_objects' possibly-undercounted matched subset), and the per-action
    displacement map.
    Expected feedback: failure means the AR25-class adapter cannot build a
    dynamics model from its probes — the axis, piece, or deltas would be
    wrong and no correct coverage plan could follow."""
    piece = {(2, 2), (2, 3), (3, 2), (3, 3)}
    obs = [
        {"before": _render_mirror(piece), "after": _render_mirror({(r, c + 1) for r, c in piece}), "label": 4},
        {"before": _render_mirror(piece), "after": _render_mirror({(r + 1, c) for r, c in piece}), "label": 2},
    ]
    model = learn_reflection_operators(obs, background=0)
    assert model["axes"] == [("col", _MIRROR_K)]
    assert model["piece_colors"] == frozenset({5})
    assert model["delta_map"] == {4: (0, 1), 2: (1, 0)}
    assert model["piece_cells"] == frozenset(piece)  # exact full footprint
    assert 4 in model["moving_colors"] and 5 in model["moving_colors"]


def test_learn_reflection_operators_no_axis_split_returns_empty_model():
    """Purpose: when no observation splits a piece from an image by opposite
    shift (e.g. only same-direction motion was seen), the kernel must return
    an empty axes/piece model rather than fabricating a mirror — the caller
    reads this as 'reflection model unavailable, fall back'.
    Expected feedback: failure means a caller would plan against a
    hallucinated axis on a board that isn't a reflective-coverage puzzle."""
    piece = {(2, 2), (2, 3)}
    # A lone frame with no image cluster: a single moving region, no split.
    def _plain(cells, h=12, w=12):
        g = [[0] * w for _ in range(h)]
        for r, c in cells:
            g[r][c] = 5
        return tuple(tuple(row) for row in g)

    obs = [{"before": _plain(piece), "after": _plain({(r, c + 1) for r, c in piece}), "label": 4}]
    model = learn_reflection_operators(obs, background=0)
    assert model["axes"] == []
    assert model["piece_cells"] == frozenset()
    assert model["delta_map"] == {}


def test_plan_reflection_coverage_finds_a_covering_motion():
    """Purpose: given a learned single-axis model, the planner must return a
    piece-move sequence whose rendered footprint (piece + reflection) covers
    a target, and executing that sequence must actually achieve coverage.
    Expected feedback: failure means the coverage search is wrong — either
    it can't find a reachable covering anchor, or the anchor it returns
    doesn't cover, which is exactly the AR25 win condition."""
    piece = {(2, 2), (2, 3), (3, 2), (3, 3)}
    axes = [("col", _MIRROR_K)]
    delta_map = {4: (0, 1), 3: (0, -1), 2: (1, 0), 1: (-1, 0)}
    target = _reflect_v({(r, c + 5) for r, c in piece})  # image of piece moved right 5
    plan = plan_reflection_coverage(piece, axes, target, delta_map, (24, 24))
    assert plan is not None
    anchor = (0, 0)
    for a in plan:
        dr, dc = delta_map[a]
        anchor = (anchor[0] + dr, anchor[1] + dc)
    moved = frozenset((r + anchor[0], c + anchor[1]) for r, c in piece)
    assert target <= reflection_orbit(moved, axes, bounds=(24, 24))


def test_plan_reflection_coverage_returns_none_without_a_model():
    """Purpose: with no axes (or no deltas) the planner cannot predict any
    footprint and must return None, never a spurious empty/partial plan.
    Expected feedback: failure means the AR25 adapter would 'execute' an
    invalid plan instead of falling back to graph exploration."""
    piece = {(2, 2), (2, 3)}
    assert plan_reflection_coverage(piece, [], {(2, 2)}, {4: (0, 1)}, (12, 12)) is None
    assert plan_reflection_coverage(piece, [("col", 19)], {(2, 2)}, {}, (12, 12)) is None


# ── fluid-flow kernels (learn_flow_operators / simulate_flow / plan) ────────

from admorphiq.kernels import (  # noqa: E402
    learn_flow_operators,
    plan_flow_coverage,
    plan_flow_coverage_multi,
    simulate_flow,
)


def _flow_layer(h, w, water_cells, bg=0, water=6):
    g = [[bg] * w for _ in range(h)]
    for r, c in water_cells:
        g[r][c] = water
    return tuple(tuple(row) for row in g)


def test_learn_flow_operators_recovers_fall_direction_and_source():
    """Purpose: from a spill's stacked animation layers (each layer one tick,
    water accumulating a downward trail), learn_flow_operators must recover
    the flowing colour, the unit fall direction, and the layer-0 emit cells —
    the model simulate_flow/plan_flow_coverage are seeded from.
    Expected feedback: failure means the SP80-class adapter learns the wrong
    flow geometry (e.g. sideways instead of down) and every simulated layout
    is wrong."""
    layers = [
        _flow_layer(8, 6, {(1, 3)}),
        _flow_layer(8, 6, {(1, 3), (2, 3)}),
        _flow_layer(8, 6, {(1, 3), (2, 3), (3, 3)}),
    ]
    model = learn_flow_operators(layers, background=0)
    assert model["flow_color"] == 6
    assert model["fall_dir"] == (1, 0)
    assert model["source_cells"] == frozenset({(1, 3)})


def test_simulate_flow_straight_fall_covers_a_target_interior():
    """Purpose: with no obstacles, fluid falls straight down and satisfies a
    target only when it enters the target's INTERIOR (both perpendicular
    neighbours are the same region) — the exact SP80 win rule.
    Expected feedback: failure means the coverage test is wrong (edge hits
    counted as covered, or interior hits missed), so plans would be scored
    against the wrong win condition."""
    target = frozenset({(8, 3), (8, 4), (8, 5)})  # centre col 4
    res = simulate_flow([(0, 4)], frozenset(), [target], (1, 0), (10, 10))
    assert res["satisfied"] == frozenset({0})
    # A source offset to a target EDGE column (3) is not an interior hit.
    res_edge = simulate_flow([(0, 3)], frozenset(), [target], (1, 0), (10, 10))
    assert res_edge["satisfied"] == frozenset()


def test_simulate_flow_splits_around_a_block_to_cover_two_targets():
    """Purpose: fluid hitting an obstacle must spread perpendicular to the
    fall and resume falling off both edges, so ONE source can satisfy two
    targets flanking a centred block — the core SP80 deflection mechanic the
    learned model reproduces.
    Expected feedback: failure means the split rule is wrong (water passes
    through, or spreads the wrong way), so no two-target layout would ever
    verify as a win in planning."""
    block = frozenset({(3, 3), (3, 4), (3, 5)})  # centred under the source col 4
    left = frozenset({(8, 1), (8, 2), (8, 3)})  # centre col 2
    right = frozenset({(8, 5), (8, 6), (8, 7)})  # centre col 6
    res = simulate_flow([(0, 4)], block, [left, right], (1, 0), (10, 10))
    assert res["satisfied"] == frozenset({0, 1})


def test_plan_flow_coverage_finds_a_block_placement_covering_all_targets():
    """Purpose: plan_flow_coverage must search movable-block translations for
    one whose simulated flow satisfies EVERY target, returning the shortest
    action sequence — the SP80 layout-planning step.
    Expected feedback: failure means the planner can't turn a learned flow
    model into a covering layout, so L0 would fall back to slow blind search."""
    # A 3-wide block one column left of centred; moving it right by 1 centres
    # it under the source so the split reaches both target interiors.
    movable = frozenset({(3, 2), (3, 3), (3, 4)})
    delta_map = {4: (0, 1), 3: (0, -1)}
    left = frozenset({(8, 1), (8, 2), (8, 3)})
    right = frozenset({(8, 5), (8, 6), (8, 7)})
    plan = plan_flow_coverage(movable, delta_map, frozenset(), [(0, 4)], [left, right], (1, 0), (10, 10))
    assert plan is not None
    # Execute the plan and confirm the resulting layout truly covers both.
    anchor = (0, 0)
    for a in plan:
        dr, dc = delta_map[a]
        anchor = (anchor[0] + dr, anchor[1] + dc)
    placed = frozenset((r + anchor[0], c + anchor[1]) for r, c in movable)
    res = simulate_flow([(0, 4)], placed, [left, right], (1, 0), (10, 10))
    assert res["satisfied"] == frozenset({0, 1})


def test_plan_flow_coverage_returns_none_without_a_model():
    """Purpose: with no movable, no targets, no deltas, or a zero fall
    direction the planner cannot predict any flow and must return None so the
    adapter falls back to graph exploration.
    Expected feedback: failure means the adapter would 'execute' an invalid
    empty plan instead of falling back."""
    mv = frozenset({(3, 2), (3, 3)})
    assert plan_flow_coverage(mv, {}, frozenset(), [(0, 4)], [frozenset({(8, 4)})], (1, 0), (10, 10)) is None
    assert plan_flow_coverage(mv, {4: (0, 1)}, frozenset(), [(0, 4)], [], (1, 0), (10, 10)) is None
    assert plan_flow_coverage(mv, {4: (0, 1)}, frozenset(), [(0, 4)], [frozenset({(8, 4)})], (0, 0), (10, 10)) is None


def test_plan_flow_coverage_multi_covers_three_targets_with_two_deflectors():
    """Purpose: plan_flow_coverage_multi must jointly place SEVERAL movable
    deflectors so their combined flow satisfies every target — the SP80 L1+
    multi-piece layout step a single-block plan cannot solve. It returns a
    (piece_index, action_label) sequence and never overlaps a piece onto a
    target, another piece, or the source.
    Expected feedback: failure means deeper SP80 levels (3 pieces / 3 targets)
    can never be planned, and the adapter is stuck at the single-piece ceiling."""
    # Two 3-wide deflectors, each one column left of where it must deflect flow
    # into a flanking target. A single block cannot reach both flanks; the joint
    # search must move each block right by one so both interiors get wet.
    piece_a = frozenset({(3, 1), (3, 2), (3, 3)})
    piece_b = frozenset({(3, 5), (3, 6), (3, 7)})
    delta_map = {4: (0, 1), 3: (0, -1)}
    source = [(0, 2), (0, 6)]
    left = frozenset({(8, 1), (8, 2), (8, 3)})
    right = frozenset({(8, 5), (8, 6), (8, 7)})
    targets = [left, right]
    plan = plan_flow_coverage_multi(
        [piece_a, piece_b], delta_map, frozenset(), source, targets, (1, 0), (10, 10)
    )
    assert plan is not None
    # Replay the plan and confirm the final joint layout truly covers both.
    anchors = [(0, 0), (0, 0)]
    for idx, label in plan:
        dr, dc = delta_map[label]
        anchors[idx] = (anchors[idx][0] + dr, anchors[idx][1] + dc)
    placed = frozenset()
    for cells, (dr, dc) in zip((piece_a, piece_b), anchors):
        placed |= frozenset((r + dr, c + dc) for r, c in cells)
    res = simulate_flow(source, placed, targets, (1, 0), (10, 10))
    assert res["satisfied"] == frozenset({0, 1})


def test_plan_flow_coverage_multi_never_places_a_piece_on_a_target():
    """Purpose: a piece placed on a target cell would block the very flow that
    must wet it, so every state the joint search visits must keep pieces off the
    targets, the source, and each other — the legality invariant.
    Expected feedback: failure means the planner could return a self-defeating
    layout that blocks a target it claims to satisfy."""
    piece_a = frozenset({(3, 1), (3, 2), (3, 3)})
    piece_b = frozenset({(3, 5), (3, 6), (3, 7)})
    delta_map = {4: (0, 1), 3: (0, -1)}
    source = [(0, 2), (0, 6)]
    targets = [frozenset({(8, 1), (8, 2), (8, 3)}), frozenset({(8, 5), (8, 6), (8, 7)})]
    plan = plan_flow_coverage_multi(
        [piece_a, piece_b], delta_map, frozenset(), source, targets, (1, 0), (10, 10)
    )
    assert plan is not None
    anchors = [(0, 0), (0, 0)]
    seen: set = set()
    target_cells = frozenset().union(*targets) | frozenset(source)
    for idx, label in plan:
        dr, dc = delta_map[label]
        anchors[idx] = (anchors[idx][0] + dr, anchors[idx][1] + dc)
    for cells, (dr, dc) in zip((piece_a, piece_b), anchors):
        placed = frozenset((r + dr, c + dc) for r, c in cells)
        assert not (placed & target_cells)
        assert not (placed & seen)
        seen |= placed


def test_plan_flow_coverage_multi_returns_none_when_uncoverable():
    """Purpose: when no joint placement can satisfy every target (or the model
    is empty), the planner returns None so the adapter falls back to graph
    exploration rather than committing a doomed spill.
    Expected feedback: failure means the adapter would waste its scarce spill
    attempts on an unreachable layout."""
    piece = frozenset({(3, 4)})
    delta_map = {4: (0, 1), 3: (0, -1)}
    # A single 1-cell piece cannot split flow to two far-apart targets.
    far = [frozenset({(8, 0)}), frozenset({(8, 9)})]
    assert plan_flow_coverage_multi([piece], delta_map, frozenset(), [(0, 4)], far, (1, 0), (10, 10)) is None
    assert plan_flow_coverage_multi([], delta_map, frozenset(), [(0, 4)], far, (1, 0), (10, 10)) is None
    assert plan_flow_coverage_multi([piece], {}, frozenset(), [(0, 4)], far, (1, 0), (10, 10)) is None


def test_separate_by_motion_isolates_the_moved_object_from_a_merged_blob():
    """Purpose: two same-colour shapes touching form ONE connected component,
    so find_regions cannot tell them apart; when only one translates,
    separate_by_motion must return exactly the MOVED shape's after-cells,
    isolated from the static one, via the motion delta + connectivity.
    Expected feedback: a FAIL means a merged multi-piece scene (re86 L3) cannot
    be de-fused by motion, so the covering planner operates on the fused blob."""
    # before: mover B (row 5, cols 4-8) touching static A (row 5, cols 9-12) —
    # one merged colour-8 bar. after: B moved UP one row, detaching from A.
    before = [[0] * 16 for _ in range(16)]
    after = [[0] * 16 for _ in range(16)]
    for c in range(4, 9):
        before[5][c] = 8
        after[4][c] = 8  # B moved up
    for c in range(9, 13):
        before[5][c] = 8
        after[5][c] = 8  # A static
    out = separate_by_motion(before, after, background=0)
    assert out["shift"] == (-1, 0)
    assert out["cells"] == frozenset((4, c) for c in range(4, 9))


def test_separate_by_motion_reports_no_motion_when_nothing_moved():
    """Purpose: with identical frames there is no leading/trailing edge, so the
    kernel reports an empty moved-object and zero shift rather than inventing a
    piece. Expected feedback: a FAIL means the caller would probe-loop forever
    treating a static scene as if a piece just moved."""
    frame = [[0, 0, 0], [0, 8, 8], [0, 0, 0]]
    out = separate_by_motion(frame, frame, background=0)
    assert out["cells"] == frozenset()
    assert out["shift"] == (0, 0)
