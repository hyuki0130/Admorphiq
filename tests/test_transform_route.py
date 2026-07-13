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
    detect_sprite_candidates,
    detect_target_points,
    detect_transform_puzzle,
    find_active_color,
    find_covering_offset,
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
