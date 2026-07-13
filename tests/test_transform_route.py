"""Unit tests for the frame-only TRANSFORM-PUZZLE capability (R28 family,
sibling of rotation.py/slider.py, RE86-class).

These pin the simple-action, multi-sprite target-coverage transform
sub-class the world-model agent uses for levels whose goal is "move each
movable sprite (only one controllable at a time, ACTION5 cycles which) so
its own pixel footprint covers every same-coloured required point" (RE86 is
the measured exemplar — a plus/cross-shaped sprite whose arms must pass
through several scattered ring+dot markers of its own colour; see
transform_route.py's module docstring for the live-trace evidence). Every
test is env-free on synthetic frames or hand-built dataclasses: the
capability must be observation-driven with no game-id / internal reads, so
its behaviour is fully exercised without touching the live env.
"""

from __future__ import annotations

import numpy as np

from admorphiq.transform_route import (
    Sprite,
    TargetPoint,
    build_move_actions,
    detect_sprite_by_motion,
    detect_sprite_candidates,
    detect_target_points,
    detect_transform_puzzle,
    find_active_color,
    find_covering_offset,
    snap_to_axis,
    sprite_bbox_implausible,
)

_BG = 0
_FRAME = 4
_ACTIVE_MARK = 7


def _blank() -> np.ndarray:
    return np.full((64, 64), _BG, dtype=np.int32)


def _stamp_cross(
    layer: np.ndarray, cx: int, cy: int, half_len: int, color: int, active_mark: int | None = None
) -> None:
    """A plus/cross sprite: a vertical + horizontal arm crossing at (cx, cy).

    When ``active_mark`` is given, the centre cell is recoloured to it
    (mirrors the measured RE86 active-sprite indicator) instead of the
    sprite's own colour.
    """
    for y in range(cy - half_len, cy + half_len + 1):
        layer[y, cx] = color
    for x in range(cx - half_len, cx + half_len + 1):
        layer[cy, x] = color
    if active_mark is not None:
        layer[cy, cx] = active_mark


def _stamp_marker(layer: np.ndarray, cx: int, cy: int, dot_color: int) -> None:
    """A 3x3 ring+dot target marker centred at (cx, cy) (colour4 frame)."""
    layer[cy - 1, cx - 1 : cx + 2] = _FRAME
    layer[cy + 1, cx - 1 : cx + 2] = _FRAME
    layer[cy - 1 : cy + 2, cx - 1] = _FRAME
    layer[cy - 1 : cy + 2, cx + 1] = _FRAME
    layer[cy, cx] = dot_color


def _re86_l1_board() -> np.ndarray:
    """A synthetic RE86-L1-shaped board: one active cross sprite (colour 6,
    centred (30,30), half-length 5) whose arms must be moved to cover 4
    scattered ring+dot markers (colour 6) forming the same cross geometry at
    a different position — mirrors the measured board's structure.
    """
    layer = _blank()
    _stamp_cross(layer, 30, 30, 5, 6, active_mark=_ACTIVE_MARK)
    for x, y in [(10, 7), (10, 17), (5, 12), (15, 12)]:
        _stamp_marker(layer, x, y, 6)
    return layer


def test_detect_target_points_reads_ring_and_dot():
    """Purpose: detect_target_points recovers all 4 marker positions and
    their required colour from ring+dot icons.

    Expected feedback: a PASS proves the marker reader correctly extracts
    (x, y, colour) from a frame+single-dot structure (reusing rotation.py's
    ring-shape test); a FAIL means the plan would never know which points
    a sprite must cover.
    """
    points = detect_target_points(_re86_l1_board(), _BG)
    assert len(points) == 4
    assert {(p.x, p.y, p.color) for p in points} == {
        (10, 7, 6),
        (10, 17, 6),
        (5, 12, 6),
        (15, 12, 6),
    }


def test_detect_sprite_candidates_bridges_the_active_marker_gap():
    """Purpose: detect_sprite_candidates recovers the cross sprite as ONE
    cluster even though its centre cell is a different colour (the active
    marker), which would otherwise fragment it into two disconnected arms
    under plain 4-connectivity.

    Expected feedback: a PASS proves the gap-bridging clustering survives the
    measured active-marker artefact; a FAIL means an active sprite would be
    split into pieces too small to plan a covering offset for.
    """
    sprites = detect_sprite_candidates(_re86_l1_board(), _BG, {6})
    assert len(sprites) == 1
    assert sprites[0].color == 6
    # 2 arms of 11 cells sharing 1 centre cell, minus the 1 active-marked
    # centre cell = 20 own-colour cells.
    assert len(sprites[0].cells) == 20


def test_detect_sprite_candidates_keeps_distant_same_color_sprites_separate():
    """Purpose: two genuinely separate sprites of the SAME colour, far apart,
    are returned as two distinct clusters, not merged into one.

    Expected feedback: a PASS proves the gap-bridge radius (2px) is narrow
    enough to only bridge the 1-cell active-marker hole, not merge unrelated
    same-coloured structures; a FAIL means a multi-sprite-same-colour level
    would collapse into a single bogus giant sprite.
    """
    layer = _blank()
    _stamp_cross(layer, 15, 15, 4, 9)
    _stamp_cross(layer, 50, 50, 4, 9)
    sprites = detect_sprite_candidates(layer, _BG, {9})
    assert len(sprites) == 2


def test_find_active_color_reads_the_hole_not_a_nearby_marker_frame():
    """Purpose: find_active_color identifies the sprite with a foreign cell
    AT ITS OWN CENTROID as active, and is NOT fooled by an unrelated marker
    frame that happens to sit elsewhere within a DIFFERENT, inactive
    sprite's bounding box.

    Expected feedback: a PASS proves the centroid-window check (not a
    whole-bbox scan) correctly distinguishes the true active-marker hole
    from incidental marker-frame pixels that land inside a sprite's sparse
    bbox once nearby — the exact false positive measured live on RE86 after
    a sprite moved next to its own target markers; a FAIL means the agent
    could misidentify which sprite responds to ACTION1-4 and move the wrong
    one (or move nothing).
    """
    layer = _blank()
    _stamp_cross(layer, 50, 50, 5, 8)  # sprite B: NOT active
    _stamp_marker(layer, 46, 46, 8)  # an unrelated marker INSIDE B's bbox,
    # far from B's own centroid (50,50) — a whole-bbox scan would wrongly
    # flag B as active because of this frame-colour pixel.
    _stamp_cross(layer, 30, 30, 5, 6, active_mark=_ACTIVE_MARK)  # sprite A: active
    sprites = detect_sprite_candidates(layer, _BG, {8, 6})
    # Order sprite B first so a buggy whole-bbox check would return early
    # with the wrong answer before ever reaching sprite A.
    ordered = sorted(sprites, key=lambda s: 0 if s.color == 8 else 1)
    assert find_active_color(layer, _BG, ordered) == 6


def test_find_active_color_none_when_no_sprite_has_a_hole():
    """Purpose: find_active_color returns None when every candidate sprite
    is a clean, fully-connected shape (no active marker present at all).

    Expected feedback: a PASS proves the detector does not hallucinate an
    active sprite from noise; a FAIL means the agent could try to move a
    sprite that is not actually controllable.
    """
    layer = _blank()
    _stamp_cross(layer, 30, 30, 5, 6)
    sprites = detect_sprite_candidates(layer, _BG, {6})
    assert find_active_color(layer, _BG, sprites) is None


def test_find_active_color_rejects_a_multi_cell_structure_near_an_inactive_centroid():
    """Purpose: an INACTIVE sprite whose centroid window happens to contain a
    multi-cell foreign structure (e.g. a nearby target-marker frame edge, 3
    cells of one colour) is NOT mistaken for active — only a genuine
    SINGLE-cell hole counts.

    Expected feedback: a PASS proves the fix measured on RE86 L2: a sprite
    that had just moved onto/near one of its own target markers left that
    marker's multi-cell frame edge inside the OTHER (inactive) sprite's
    small centroid window, which a "foreign.size > 0" check wrongly read as
    still-active — permanently locking cycling onto the wrong sprite and
    starving the genuinely active one of its turn. A FAIL means the agent
    could move the wrong sprite (or never reach the right one) whenever a
    sprite ends up near unrelated board structure.
    """
    layer = _blank()
    _stamp_cross(layer, 10, 10, 5, 6, active_mark=_ACTIVE_MARK)  # sprite A: genuinely active
    _stamp_cross(layer, 30, 30, 5, 8)  # sprite B: inactive
    # A 3-cell foreign structure (e.g. a marker-frame edge) falling inside
    # B's own radius-2 centroid window — NOT a genuine single-cell hole.
    layer[28, 29] = 4
    layer[28, 30] = 4
    layer[28, 31] = 4
    sprites = detect_sprite_candidates(layer, _BG, {6, 8})
    assert find_active_color(layer, _BG, sprites) == 6


def test_find_covering_offset_matches_the_measured_offset():
    """Purpose: find_covering_offset computes the exact translation that
    makes the cross sprite's own footprint cover all 4 scattered points —
    matching the offset independently measured live on RE86's real board
    for the analogous geometry.

    Expected feedback: a PASS proves the position-agnostic candidate search
    (derived from one point, verified against the rest) finds the correct
    offset without a blind grid search; a FAIL means the plan would move the
    sprite to the wrong place or fail to find a reachable offset at all.
    """
    layer = _re86_l1_board()
    sprites = detect_sprite_candidates(layer, _BG, {6})
    points = detect_target_points(layer, _BG)
    offset = find_covering_offset(sprites[0], points)
    assert offset == (-20, -18)


def test_find_covering_offset_none_when_points_dont_fit_the_shape():
    """Purpose: find_covering_offset returns None when no single translation
    of the sprite's own shape can cover all required points (e.g. two points
    that are not collinear with the sprite's arms at any reachable offset).

    Expected feedback: a PASS proves the agent does not force a wrong
    placement when direct translation genuinely cannot satisfy the
    requirement (this colour may need a coloru-changer, out of this
    module's scope); a FAIL means the agent could commit to a move sequence
    that can never clear the level.
    """
    sprite = Sprite(color=6, cells=frozenset({(30, 25), (30, 35), (25, 30), (35, 30)}), cx=30, cy=30)
    points = [TargetPoint(x=1, y=1, color=6), TargetPoint(x=2, y=50, color=6)]
    assert find_covering_offset(sprite, points) is None


def test_find_covering_offset_prefers_a_step_clean_offset_among_several_valid():
    """Purpose: when a sprite's own cell layout admits MULTIPLE distinct
    valid offsets for the same point set, find_covering_offset prefers the
    one that is a clean multiple of the measured per-click step, not
    whichever is found first.

    Expected feedback: a PASS proves the fix measured on RE86 L2's diamond-
    outline sprite: the naive "first found" offset was NOT reachable by the
    sprite's own 3px step, while a DIFFERENT valid offset for the exact same
    points was — and build_move_actions correctly refuses an unreachable
    offset, so returning the wrong one silently strands the sprite
    unplaced. A FAIL means a level solvable by direct placement could be
    given up on for no real reason.
    """
    # 3 collinear cells 5 apart; two adjacent cells can each anchor a valid
    # offset onto the same two 5-apart points, differing by exactly 5.
    sprite = Sprite(
        color=6, cells=frozenset({(0, 0), (5, 0), (10, 0)}), cx=5.0, cy=0.0
    )
    points = [TargetPoint(x=20, y=0, color=6), TargetPoint(x=25, y=0, color=6)]
    # Sanity: both (20, 0) and (15, 0) are genuinely valid for this sprite.
    assert find_covering_offset(sprite, points, step=1) in {(20, 0), (15, 0)}
    # With step=10, only (20, 0) is a clean multiple (15 % 10 != 0).
    assert find_covering_offset(sprite, points, step=10) == (20, 0)


def test_build_move_actions_uses_the_measured_dir_map_not_hardcoded_ids():
    """Purpose: build_move_actions resolves +x/-x/+y/-y to WHATEVER action
    ids the measured dir_map assigns them (here deliberately scrambled, not
    RE86's own 1=up/2=down/3=left/4=right), and rejects an offset that is
    not a clean multiple of the measured step.

    Expected feedback: a PASS proves the action-id-to-direction mapping is
    read from measurement, never assumed; a FAIL means the plan could move
    the wrong direction on a game whose action ids are bound differently.
    """
    dir_map = {7: (0, -5), 8: (0, 5), 9: (-5, 0), 2: (5, 0)}  # scrambled ids, step 5
    actions = build_move_actions(-10, 15, dir_map, step=5)
    assert actions.count(9) == 2  # -x, twice
    assert actions.count(8) == 3  # +y, three times
    assert len(actions) == 5
    # Not a clean multiple of the measured step -> no plan.
    assert build_move_actions(-11, 15, dir_map, step=5) == []
    # A needed direction was never observed during calibration -> no plan.
    assert build_move_actions(-10, 0, {8: (0, 5)}, step=5) == []


def test_detect_transform_puzzle_full_pipeline():
    """Purpose: detect_transform_puzzle end-to-end on a genuine marker+sprite
    board returns both the targets and the sprite candidate.

    Expected feedback: a PASS proves the composed detection entry point (the
    one the world-model agent's probe-phase gate calls) works on a realistic
    synthetic board; a FAIL means the agent would never enter the transform
    phase on a genuine layout.
    """
    puzzle = detect_transform_puzzle(_re86_l1_board(), _BG)
    assert puzzle is not None
    assert len(puzzle.targets) == 4
    assert len(puzzle.sprites) == 1
    assert puzzle.sprites[0].color == 6


def test_detect_transform_puzzle_none_without_targets():
    """Purpose: a board with a sprite-like cross but NO ring+dot markers
    returns None — there is nothing to plan toward.

    Expected feedback: a PASS proves the plan stays dormant on an unrelated
    game that happens to have a plus-shaped coloured object; a FAIL means the
    agent could enter the transform phase with no target to work toward.
    """
    layer = _blank()
    _stamp_cross(layer, 30, 30, 5, 6, active_mark=_ACTIVE_MARK)
    assert detect_transform_puzzle(layer, _BG) is None


def test_detect_transform_puzzle_none_without_matching_sprite():
    """Purpose: a board with target markers but NO movable sprite of any
    required colour returns None (not a false-positive transform puzzle).

    Expected feedback: a PASS proves an unrelated click/move game with a
    marker-like ring icon somewhere does not trigger the transform phase
    when nothing could ever satisfy it; a FAIL means the agent could enter a
    phase doomed to find zero placeable colours.
    """
    layer = _blank()
    for x, y in [(10, 7), (10, 17), (5, 12), (15, 12)]:
        _stamp_marker(layer, x, y, 6)
    assert detect_transform_puzzle(layer, _BG) is None


# ── motion-based reclassification (R28 family, RE86 L3 same-colour-decoration
# wall — see .wiki/wiki/rounds/r53_unified-harness.md) ───────────────────────

# A diagonal decoration chain: single-pixel dots exactly one Chebyshev step
# apart (already 8-connected — matches the measured RE86 L3 pattern, where
# even standard adjacency, not just the extra _GAP_BRIDGE reach, welds
# decoration onto the real sprite). Deliberately crosses a horizontal bar's
# row at both its "before" and "after" positions, so both frames exhibit a
# genuine touching pixel, exactly as measured live.
def _diagonal_decoration(layer: np.ndarray, color: int) -> None:
    for i in range(40):
        layer[20 + i, i] = color


def _bar_sprite_board(bar_row: int, color: int = 6) -> np.ndarray:
    """A 1-row-tall bar (cols 10-30) plus a same-colour diagonal decoration
    chain that touches it — the synthetic reproduction of RE86 L3's
    corrupted-cluster wall (see transform_route.py's module docstring for
    the live-measured original).
    """
    layer = _blank()
    layer[bar_row, 10:31] = color
    _diagonal_decoration(layer, color)
    return layer


def test_detect_sprite_candidates_merges_touching_decoration_reproduces_the_l3_wall():
    """Purpose: pin the BUG this round fixes — static whole-layer clustering
    welds a same-colour decoration chain onto a real sprite the moment they
    touch at even one pixel, producing one implausible mega-cluster instead
    of the true ~20-cell bar.

    Expected feedback: a PASS documents the corruption is reproducible on a
    minimal synthetic board (bar 21 cells + 40-cell diagonal - 1 shared
    touching pixel = 60 cells, one cluster); a FAIL would mean this synthetic
    board no longer reproduces the measured RE86 L3 failure mode, so it can
    no longer stand in for it in the tests below.
    """
    layer = _bar_sprite_board(bar_row=40)
    sprites = detect_sprite_candidates(layer, _BG, {6})
    assert len(sprites) == 1
    assert len(sprites[0].cells) == 60


def test_sprite_bbox_implausible_flags_the_corrupted_cluster_not_a_normal_sprite():
    """Purpose: sprite_bbox_implausible separates the corrupted mega-cluster
    (bbox spans most of the board) from an ordinary compact sprite, using
    only the bbox-vs-playfield-extent relationship — the gate that decides
    whether motion-based reclassification engages at all.

    Expected feedback: a PASS proves normal L1/L2-shaped sprites (this repo's
    measured 19-27px bboxes) never trigger motion mode, while the L3-shaped
    corrupted cluster (measured 51px) always does; a FAIL means either normal
    levels would wrongly detour through motion classification (byte-identical
    guard risk) or a genuinely corrupted cluster would be trusted as-is.
    """
    normal = detect_sprite_candidates(_re86_l1_board(), _BG, {6})[0]
    assert sprite_bbox_implausible(normal, (64, 64)) is False

    corrupted = detect_sprite_candidates(_bar_sprite_board(bar_row=40), _BG, {6})[0]
    assert sprite_bbox_implausible(corrupted, (64, 64)) is True


def test_detect_sprite_by_motion_excludes_static_decoration_and_recovers_the_true_shift():
    """Purpose: detect_sprite_by_motion recovers ONLY the cells that changed
    state between two frames straddling a real movement press, excluding the
    static same-colour decoration entirely — even though the decoration
    touches the sprite (via gap-bridging) at a DIFFERENT pixel in each frame,
    mirroring the measured RE86 L3 evidence exactly.

    Expected feedback: a PASS proves the returned before/after sprites
    contain ONLY genuine bar cells (never a single decoration-chain cell,
    since decoration never changes state and so is never in the moved-cell
    domain — the domain restriction itself, not the gap-bridge radius, is
    what excludes it); a FAIL means motion mode could still leak decoration
    into the reclassified footprint.
    """
    before = _bar_sprite_board(bar_row=40)
    after = _bar_sprite_board(bar_row=37)
    pair = detect_sprite_by_motion(before, after, 6)
    assert pair is not None
    sprite_before, sprite_after = pair

    # The decoration's OWN cells (i != 20 for row 40, i != 17 for row 37 —
    # the two touching pixels) must never appear; only genuine bar cells do.
    decoration_cells = {(i, 20 + i) for i in range(40)}
    assert not (sprite_before.cells & decoration_cells)
    assert not (sprite_after.cells & decoration_cells)
    assert sprite_before.cells == frozenset((x, 40) for x in range(10, 31) if x != 20)
    assert sprite_after.cells == frozenset((x, 37) for x in range(10, 31) if x != 17)


def test_detect_sprite_by_motion_none_when_nothing_of_the_color_moved():
    """Purpose: detect_sprite_by_motion returns None when the two frames are
    identical for the probed colour (a blocked direction, or the wrong
    colour) rather than fabricating a sprite from noise.

    Expected feedback: a PASS proves the caller correctly gets "try the next
    calibration press" signal instead of a bogus zero-cell Sprite; a FAIL
    could crash downstream centroid math or silently record a false (0, 0)
    step.
    """
    layer = _bar_sprite_board(bar_row=40)
    assert detect_sprite_by_motion(layer, layer.copy(), 6) is None


def test_snap_to_axis_zeroes_the_smaller_magnitude_component():
    """Purpose: snap_to_axis keeps the dominant-magnitude axis (rounded) and
    zeroes the other — the fix for the measured RE86 L3 residual (raw
    dx=-0.619 alongside an exact dy=-3.000, from 2-3 of a 39-cell bar's cells
    coinciding with decoration in only one frame).

    Expected feedback: a PASS proves a small cross-axis artefact never
    corrupts the recorded per-action step; a FAIL means
    admorphiq.general_agent._step_cell_size could pick up a spurious 1px
    "step" from noise instead of the true measured step (exactly the
    corruption this round's fix targets).
    """
    assert snap_to_axis(-0.619, -3.0) == (0, -3)
    assert snap_to_axis(3.0, 0.4) == (3, 0)
    assert snap_to_axis(0.0, -3.0) == (0, -3)
    assert snap_to_axis(3.0, 0.0) == (3, 0)
    assert snap_to_axis(0.0, 0.0) == (0, 0)
