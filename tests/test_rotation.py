"""Unit tests for the frame-only ROTATION-PUZZLE capability (R28 family, S5I5-class).

These pin the click-only, attempt-limited rotation sub-class the world-model
agent uses for levels whose goal is "rotate each piece's interior pattern to
match a reference orientation, using a widget click per rotation, without
wasting any other click on the attempt counter" (S5I5 is the measured
exemplar — two stacked 5x5 pieces with a colour frame + asymmetric colour
interior, plus a separate reference pattern elsewhere on the board). Every
test is env-free on synthetic frames or hand-built dataclasses: the capability
must be observation-driven with no game-id / internal reads, so its behaviour
is fully exercised without touching the live env.
"""

from __future__ import annotations

import numpy as np

from admorphiq.rotation import (
    ReferencePattern,
    RotatablePiece,
    best_rotation,
    detect_reference_patterns,
    detect_rotatable_pieces,
    detect_rotation_puzzle,
    identify_moved_piece,
    piece_matches_target,
    plan_piece_targets,
    widget_candidates,
)

_BG = 0
_FRAME = 4
_INTERIOR = 11
_REF_COLOR = 14

# An asymmetric tight L-shape (3 rows x 2 cols): no rotation of this maps onto
# itself, so all four np.rot90 orientations are distinct — a good probe shape
# for pinning an exact rotation count.
_BASE = np.array(
    [
        [True, False],
        [True, False],
        [True, True],
    ],
    dtype=bool,
)


def _blank() -> np.ndarray:
    return np.full((64, 64), _BG, dtype=np.int32)


def _stamp_ring(layer: np.ndarray, r0: int, r1: int, c0: int, c1: int, color: int) -> None:
    """Draw a 1-cell-thick rectangular border (a piece's frame)."""
    layer[r0, c0 : c1 + 1] = color
    layer[r1, c0 : c1 + 1] = color
    layer[r0 : r1 + 1, c0] = color
    layer[r0 : r1 + 1, c1] = color


def _stamp_shape(layer: np.ndarray, mask: np.ndarray, r0: int, c0: int, color: int) -> None:
    """Paint ``color`` at every True cell of ``mask``, offset by (r0, c0)."""
    for dr, dc in zip(*np.where(mask)):
        layer[r0 + int(dr), c0 + int(dc)] = color


def _two_piece_board() -> np.ndarray:
    """Two 5x5 frame+interior pieces plus one reference shape, well separated.

    Piece A's raw interior is ``_BASE`` (k=0). Piece B's raw interior is
    ``_BASE`` rotated by one step (k=1) — a different current orientation from
    A, so a per-piece rotation-count test is meaningful. The reference shape is
    ``_BASE`` rotated by two steps (k=2), a colour used nowhere else.
    """
    layer = _blank()
    _stamp_ring(layer, 10, 14, 10, 14, _FRAME)
    _stamp_shape(layer, _BASE, 11, 11, _INTERIOR)
    _stamp_ring(layer, 30, 34, 30, 34, _FRAME)
    _stamp_shape(layer, np.rot90(_BASE, 1), 31, 31, _INTERIOR)
    _stamp_shape(layer, np.rot90(_BASE, 2), 45, 45, _REF_COLOR)
    return layer


def test_detect_rotatable_pieces_finds_frame_and_interior():
    """Purpose: detect_rotatable_pieces recovers both pieces' frame colour,
    interior colour, and bbox extent from a synthetic two-piece board.

    Expected feedback: a PASS proves the frame-ring + dominant-interior-colour
    detection is structural (works for either of two same-frame-colour pieces
    at different board positions); a FAIL means the piece detector cannot even
    locate the pieces, so nothing downstream (rotation matching, widget probing)
    could work either.
    """
    pieces = detect_rotatable_pieces(_two_piece_board(), _BG)
    assert len(pieces) == 2
    for p in pieces:
        assert p.frame_color == _FRAME
        assert p.interior_color == _INTERIOR
        r0, r1, c0, c1 = p.bbox
        assert (r1 - r0 + 1, c1 - c0 + 1) == (5, 5)
    centroids = sorted(round(p.cy) for p in pieces)
    assert centroids == [12, 32]


def test_detect_rotatable_pieces_skips_degenerate_interiors():
    """Purpose: a frame ring with an EMPTY or FULLY-FILLED interior (no
    rotation is detectable/meaningful on either) is not returned as a piece.

    Expected feedback: a PASS proves the partial-fill falsifier keeps the
    detector off decorative frames / solid swatches; a FAIL means the detector
    would hallucinate a rotatable piece where no rotation could ever be
    observed, wasting a probe click on it later.
    """
    empty_interior = _blank()
    _stamp_ring(empty_interior, 10, 14, 10, 14, _FRAME)
    assert detect_rotatable_pieces(empty_interior, _BG) == []

    full_interior = _blank()
    _stamp_ring(full_interior, 10, 14, 10, 14, _FRAME)
    full_interior[11:14, 11:14] = _INTERIOR
    assert detect_rotatable_pieces(full_interior, _BG) == []


def test_detect_reference_patterns_excludes_piece_colors():
    """Purpose: detect_reference_patterns finds the isolated reference shape
    and never re-labels a piece's own frame/interior colour as a reference.

    Expected feedback: a PASS proves the exclude-set correctly filters out the
    piece colours so the reference search targets only the genuinely distinct
    colour; a FAIL means a piece could be mistaken for its own target, which
    would corrupt the rotation-count computation.
    """
    layer = _two_piece_board()
    refs = detect_reference_patterns(layer, _BG, exclude_colors={_BG, _FRAME, _INTERIOR})
    assert len(refs) == 1
    assert refs[0].color == _REF_COLOR
    assert refs[0].size == 4


def test_best_rotation_matches_known_rot90_relationship():
    """Purpose: best_rotation recovers the EXACT rotation count for a piece
    whose interior is a known np.rot90 relationship to the reference.

    Expected feedback: a PASS proves the rotation search correctly identifies
    k=2 (and a perfect IoU score) when the reference is literally
    ``np.rot90(interior, 2)``; a FAIL means the plan would click the wrong
    number of times and never reach the target orientation.
    """
    piece = RotatablePiece(
        frame_color=_FRAME,
        interior_color=_INTERIOR,
        bbox=(10, 14, 10, 14),
        interior_mask=_BASE,
        cx=12.0,
        cy=12.0,
    )
    reference = ReferencePattern(
        color=_REF_COLOR, mask=np.rot90(_BASE, 2), cx=46.0, cy=46.0, size=4
    )
    k, score = best_rotation(piece, reference)
    assert k == 2
    assert score == 1.0


def test_plan_piece_targets_assigns_each_piece_its_own_rotation_count():
    """Purpose: plan_piece_targets computes a DIFFERENT rotation count for two
    pieces that start at different orientations but share the same target
    shape, and greedily assigns one reference per piece.

    Expected feedback: a PASS proves the per-piece target is derived from each
    piece's OWN current interior (not a shared global rotation count); a FAIL
    means one piece would be assigned the wrong number of clicks.
    """
    piece_a = RotatablePiece(_FRAME, _INTERIOR, (10, 14, 10, 14), _BASE, 12.0, 12.0)
    piece_b = RotatablePiece(_FRAME, _INTERIOR, (30, 34, 30, 34), np.rot90(_BASE, 1), 32.0, 32.0)
    # Two references with the SAME target shape (np.rot90(_BASE, 2)) at
    # different colours/positions, mirroring two independent target patterns
    # that happen to coincide in shape.
    ref1 = ReferencePattern(_REF_COLOR, np.rot90(_BASE, 2), 46.0, 46.0, 4)
    ref2 = ReferencePattern(15, np.rot90(_BASE, 2), 50.0, 50.0, 4)
    targets = plan_piece_targets([piece_a, piece_b], [ref1, ref2])
    assert len(targets) == 2
    assert all(t is not None for t in targets)
    # Piece A (k=0 raw) needs k=2 to reach the target; piece B (k=1 raw) needs
    # only k=1. Both targets equal the same final shape.
    assert np.array_equal(targets[0], np.rot90(_BASE, 2))
    assert np.array_equal(targets[1], np.rot90(_BASE, 2))


def test_plan_piece_targets_none_without_pieces_or_references():
    """Purpose: an empty piece list or empty reference list yields no targets
    rather than raising or hallucinating an assignment.

    Expected feedback: a PASS proves the function degrades safely on the
    "nothing to plan" inputs the live agent will pass on a non-rotation game;
    a FAIL means a downstream caller would crash instead of falling through to
    normal interaction.
    """
    piece = RotatablePiece(_FRAME, _INTERIOR, (10, 14, 10, 14), _BASE, 12.0, 12.0)
    ref = ReferencePattern(_REF_COLOR, np.rot90(_BASE, 2), 46.0, 46.0, 4)
    assert plan_piece_targets([], [ref]) == []
    assert plan_piece_targets([piece], []) == [None]


def test_detect_rotation_puzzle_full_pipeline():
    """Purpose: detect_rotation_puzzle end-to-end on a genuine two-piece +
    reference board returns both pieces, a target for at least one, and a
    widget-candidate list covering the piece and reference centroids.

    Expected feedback: a PASS proves the composed detection entry point (the
    one the world-model agent's probe-phase gate calls) works on a realistic
    synthetic board; a FAIL means the agent would never enter the rotation
    phase on a genuine layout.
    """
    puzzle = detect_rotation_puzzle(_two_piece_board(), _BG)
    assert puzzle is not None
    assert len(puzzle.pieces) == 2
    assert any(t is not None for t in puzzle.targets)
    # Candidates cover every piece + reference centroid, de-duplicated.
    assert len(puzzle.candidates) == 3
    assert len(set(puzzle.candidates)) == len(puzzle.candidates)


def test_detect_rotation_puzzle_none_without_reference():
    """Purpose: a board with pieces but NO distinct reference colour returns
    None — a rotation plan cannot pick a target without a reference.

    Expected feedback: a PASS proves the plan stays dormant on a click game
    that merely happens to have a frame+interior-shaped object but no visible
    target pattern (avoiding a wasted, directionless probe); a FAIL means the
    agent could enter the rotation phase with no way to ever succeed.
    """
    layer = _blank()
    _stamp_ring(layer, 10, 14, 10, 14, _FRAME)
    _stamp_shape(layer, _BASE, 11, 11, _INTERIOR)
    assert detect_rotation_puzzle(layer, _BG) is None


def test_detect_rotation_puzzle_none_without_pieces():
    """Purpose: a board with an isolated shape but NO frame+interior piece
    structure returns None (not a false-positive rotation puzzle).

    Expected feedback: a PASS proves an unrelated click game (e.g. a plain
    coloured cluster with no ring/interior structure) does not trigger the
    rotation phase; a FAIL would mean the detector fires on almost any
    multi-colour frame, defeating the point of a structural gate.
    """
    layer = _blank()
    _stamp_shape(layer, _BASE, 20, 20, _REF_COLOR)
    assert detect_rotation_puzzle(layer, _BG) is None


def test_widget_candidates_dedup_piece_and_reference_centroids():
    """Purpose: widget_candidates returns one (x, y) per piece + reference
    centroid, de-duplicated when two candidates round to the same pixel.

    Expected feedback: a PASS proves the probe queue the live agent drains is
    bounded to distinct positions (no repeated wasted click on the same
    coordinate); a FAIL means the probe budget could be silently wasted on
    duplicate candidates.
    """
    piece = RotatablePiece(_FRAME, _INTERIOR, (10, 14, 10, 14), _BASE, 12.0, 12.0)
    ref_same = ReferencePattern(_REF_COLOR, np.rot90(_BASE, 2), 12.0, 12.0, 4)
    ref_other = ReferencePattern(15, np.rot90(_BASE, 2), 46.0, 46.0, 4)
    cands = widget_candidates([piece], [ref_same, ref_other])
    assert cands == [(12, 12), (46, 46)]


def test_identify_moved_piece_attributes_the_changed_interior():
    """Purpose: identify_moved_piece pinpoints WHICH piece's interior changed
    between a before/after frame pair, and returns None when neither did.

    Expected feedback: a PASS proves a widget-candidate probe can be correctly
    attributed to the piece it controls (or ruled out as a non-widget click);
    a FAIL means the live agent could build a wrong widget->piece mapping and
    click the wrong piece's widget during commit.
    """
    before = _two_piece_board()
    pieces = detect_rotatable_pieces(before, _BG)
    piece_b = max(pieces, key=lambda p: p.cy)  # the piece at rows 30-34
    after = before.copy()
    r0, r1, c0, c1 = piece_b.bbox
    sub = after[r0 : r1 + 1, c0 : c1 + 1]
    sub[sub == piece_b.interior_color] = _BG
    _stamp_shape(after, _BASE, r0 + 1, c0 + 1, piece_b.interior_color)

    moved = identify_moved_piece(pieces, before, after)
    assert moved == pieces.index(piece_b)
    # A before/after pair with no change attributes to no piece.
    assert identify_moved_piece(pieces, before, before.copy()) is None


def test_piece_matches_target_reads_the_live_frame():
    """Purpose: piece_matches_target compares a piece's CURRENT (live) interior
    shape to its target, not the shape captured at detection time.

    Expected feedback: a PASS proves the live commit loop can tell "reached
    the target" from the frame alone after clicks have moved the piece; a FAIL
    means the agent could click forever (never detects a match) or stop too
    early (false match).
    """
    layer = _two_piece_board()
    pieces = detect_rotatable_pieces(layer, _BG)
    piece_a = min(pieces, key=lambda p: p.cy)  # the piece at rows 10-14
    target = np.rot90(_BASE, 2)
    # Not yet rotated: piece A's raw interior is _BASE (k=0), not the target.
    assert piece_matches_target(piece_a, layer, target) is False
    # Rotate piece A's interior in place on a copy to the target orientation.
    rotated = layer.copy()
    r0, r1, c0, c1 = piece_a.bbox
    sub = rotated[r0 : r1 + 1, c0 : c1 + 1]
    sub[sub == piece_a.interior_color] = _BG
    _stamp_shape(rotated, target, r0 + 1, c0 + 1, piece_a.interior_color)
    assert piece_matches_target(piece_a, rotated, target) is True
