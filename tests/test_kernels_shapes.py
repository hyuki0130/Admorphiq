"""Tests for the pure shape-transform and assignment kernels (R56)."""

from admorphiq.kernels import (
    assign_pairs,
    best_transform_match,
    crop_to_content,
    dihedral_transforms,
    iou,
)

# F-pentomino: chosen because it has trivial symmetry under D4 (no rotation or
# reflection maps it onto itself), so all 8 dihedral transforms are pairwise
# distinct — the property several tests below rely on.
_F_PENTOMINO = (
    (False, True, True),
    (True, True, False),
    (False, True, False),
)


def test_dihedral_transforms_all_eight_distinct_on_asymmetric_mask():
    """Purpose: on a shape with no symmetry, the 8 D4 transforms must be 8
    pairwise-distinct masks — collapsing any pair would mean the transform
    generation is not actually producing the full dihedral group.
    Expected feedback: failure means _rotate90/_flip_h composition is buggy
    (e.g. a wrong rotation direction that accidentally aliases two names)."""
    out = dihedral_transforms(_F_PENTOMINO)
    assert [d["name"] for d in out] == [
        "identity",
        "rot90",
        "rot180",
        "rot270",
        "flip_h",
        "flip_h_rot90",
        "flip_h_rot180",
        "flip_h_rot270",
    ]
    masks = [d["mask"] for d in out]
    assert len({m for m in masks}) == 8


def test_dihedral_transforms_identity_is_unchanged():
    """Purpose: the 'identity' entry must be exactly the (normalized) input,
    not merely equivalent under some transform.
    Expected feedback: failure means the loop that seeds `current = base`
    is wrong, corrupting every downstream consumer's baseline."""
    out = dihedral_transforms(_F_PENTOMINO)
    assert out[0]["mask"] == _F_PENTOMINO


def test_rotation_group_closes_after_four_quarter_turns():
    """Purpose: rot360 must equal identity — composing dihedral_transforms
    twice (source -> rot90, then that mask's own rot270) must recover the
    original mask, proving the rotation group is closed and consistent.
    Expected feedback: failure means _rotate90's direction or cell mapping
    is inconsistent across calls, which would silently corrupt any
    multi-step transform composition (e.g. best_transform_match)."""
    rot90_mask = dihedral_transforms(_F_PENTOMINO)[1]["mask"]
    recovered = dihedral_transforms(rot90_mask)[3]["mask"]  # rot270 of rot90 = rot360
    assert recovered == _F_PENTOMINO


def test_dihedral_transforms_rotation_transposes_non_square_mask():
    """Purpose: a non-square mask's rot90/rot270 must have swapped dimensions
    (h x w -> w x h); rot180 keeps the original dimensions.
    Expected feedback: failure means the rotation only works for square
    inputs, breaking every non-square piece shape."""
    mask = ((True, True, False),)  # 1x3
    out = dihedral_transforms(mask)
    assert len(out[0]["mask"]) == 1 and len(out[0]["mask"][0]) == 3
    assert len(out[1]["mask"]) == 3 and len(out[1]["mask"][0]) == 1
    assert len(out[2]["mask"]) == 1 and len(out[2]["mask"][0]) == 3


def test_crop_to_content_offset_and_mask():
    """Purpose: crop_to_content must return both the tight-cropped mask and
    the (row, col) offset of its bounding box in the original coordinates.
    Expected feedback: failure means downstream callers (e.g.
    best_transform_match) would compare shapes at the wrong alignment, or
    lose the ability to place a cropped result back on the board."""
    mask = (
        (False, False, False, False),
        (False, True, True, False),
        (False, True, False, False),
        (False, False, False, False),
    )
    out = crop_to_content(mask)
    assert out["offset"] == (1, 1)
    assert out["mask"] == ((True, True), (True, False))


def test_crop_to_content_empty_mask_returns_empty_offset_zero():
    """Purpose: an all-False mask (or an empty mask) has no bounding box —
    this must degrade to an empty mask and offset (0, 0), not raise.
    Expected feedback: failure means a game frame with no truthy cells
    (e.g. a fully-cleared toggle puzzle) crashes shape analysis instead of
    reporting 'nothing here'."""
    assert crop_to_content(((False, False), (False, False))) == {"mask": (), "offset": (0, 0)}
    assert crop_to_content(()) == {"mask": (), "offset": (0, 0)}


def test_iou_known_half_overlap_value():
    """Purpose: pin a known IoU value — two 2-cell masks sharing exactly one
    cell (union 3, intersection 1) must score exactly 1/3.
    Expected feedback: failure means the intersection/union counting is
    off, which would silently mis-rank every transform-matching decision."""
    a = ((True, True, False),)
    b = ((False, True, True),)
    assert iou(a, b) == 1 / 3


def test_iou_identical_masks_is_one_and_disjoint_is_zero():
    """Purpose: sanity-bound the IoU scale — identical truthy sets score 1.0,
    completely disjoint truthy sets score 0.0.
    Expected feedback: failure means the score has an off-by-something that
    would make 'high confidence match' and 'no match' indistinguishable."""
    a = ((True, False), (False, True))
    assert iou(a, a) == 1.0
    b = ((False, True), (True, False))
    assert iou(a, b) == 0.0


def test_iou_both_empty_masks_is_perfect_match():
    """Purpose: two masks with no truthy cells at all are defined as a
    perfect match (1.0), matching the documented degenerate-case contract.
    Expected feedback: failure (e.g. returning 0.0 or raising ZeroDivision)
    means an 'everything already cleared' comparison is misjudged as a
    total mismatch."""
    assert iou((), ()) == 1.0
    assert iou(((False, False),), ((False, False),)) == 1.0


def test_iou_alignment_is_top_left_not_registration_searched():
    """Purpose: pin the documented alignment rule — masks are top-left
    padded to the common bounding size, not translation-registered, so a
    shape and its own translated copy do NOT automatically score 1.0.
    Expected feedback: failure (an unexpectedly high score here) means IoU
    silently started doing registration search, contradicting the
    documented contract that callers must crop first for that behavior."""
    a = ((True, False), (False, False))
    b = ((False, False), (False, True))
    assert iou(a, b) == 0.0


def test_best_transform_match_recovers_known_rotation():
    """Purpose: given source = rot90(shape) and target = shape, the best
    match must be found at 'rot270' (the inverse rotation) with IoU 1.0 —
    end-to-end proof that dihedral generation + IoU scoring + argmax work
    together to recover a known planted transform.
    Expected feedback: failure means either the transform enumeration or
    the scoring loop picks the wrong candidate, which is the exact failure
    mode that would misroute a live rotation-puzzle piece to the wrong
    click target."""
    rotated_source = dihedral_transforms(_F_PENTOMINO)[1]["mask"]  # rot90 of F
    match = best_transform_match(rotated_source, _F_PENTOMINO)
    assert match["name"] == "rot270"
    assert match["iou"] == 1.0
    assert match["mask"] == _F_PENTOMINO


def test_best_transform_match_crop_true_ignores_translation():
    """Purpose: with crop=True (default), a target that is a translated copy
    of source must still match at 'identity' with IoU 1.0 — translation
    must not defeat the match once both sides are cropped to content.
    Expected feedback: failure means the crop step isn't actually being
    applied before scoring, making every real-board (untranslated-source,
    translated-target) match fail even when the shapes are truly equal."""
    source = ((True, True), (True, False))
    translated_target = (
        (False, False, False),
        (False, True, True),
        (False, True, False),
    )
    match = best_transform_match(source, translated_target, crop=True)
    assert match["name"] == "identity"
    assert match["iou"] == 1.0


def test_assign_pairs_beats_greedy_on_crafted_matrix():
    """Purpose: on a matrix where the greedy highest-score-first pick is
    suboptimal ([[5,4],[4,0]]: greedy takes (0,0)=5 then is forced into
    (1,1)=0 for total 5), assign_pairs must find the true optimum
    (0,1)+(1,0)=8 via exact search.
    Expected feedback: failure means the implementation degenerated into
    greedy (or another non-optimal heuristic), which would under-solve any
    multi-piece assignment puzzle with this exact score shape."""
    matrix = [[5, 4], [4, 0]]
    pairs = assign_pairs(matrix)
    total = sum(matrix[r][c] for r, c in pairs)
    assert total == 8
    assert pairs == [(0, 1), (1, 0)]
    # Confirm greedy really would have been worse, so this is a real proof.
    greedy_total = matrix[0][0] + matrix[1][1]
    assert greedy_total < total


def test_assign_pairs_rectangular_covers_smaller_dimension():
    """Purpose: with more rows than columns, the result must cover every
    column (2 slots) using the best 2 of 3 rows, leaving one row unused —
    proving the DP correctly handles non-square matrices in both
    orientations (this one is NOT transposed internally: n_cols <= n_rows).
    Expected feedback: failure means the rectangular-matrix branch either
    mis-sizes the DP table or fails to leave surplus items unassigned."""
    matrix = [[1, 9], [9, 1], [5, 5]]
    pairs = assign_pairs(matrix)
    assert len(pairs) == 2
    assert {c for _r, c in pairs} == {0, 1}  # both columns covered
    total = sum(matrix[r][c] for r, c in pairs)
    assert total == 18
    assert pairs == [(0, 1), (1, 0)]


def test_assign_pairs_rectangular_transposed_branch_more_columns_than_rows():
    """Purpose: mirror of the above with more columns than rows, forcing the
    internal transpose branch — every row must be covered, one column left
    unused, and the returned indices must be un-transposed back to the
    original (row, col) space.
    Expected feedback: failure means the transpose-back step is missing or
    wrong, silently swapping row/col indices in the caller-visible result."""
    matrix = [[1, 9, 5], [9, 1, 5]]
    pairs = assign_pairs(matrix)
    assert len(pairs) == 2
    assert {r for r, _c in pairs} == {0, 1}  # both rows covered
    total = sum(matrix[r][c] for r, c in pairs)
    assert total == 18
    assert pairs == [(0, 1), (1, 0)]


def test_assign_pairs_empty_matrix_returns_empty_list():
    """Purpose: no rows, or rows with zero width, are degenerate inputs that
    must return [] rather than raising.
    Expected feedback: failure means a caller with a genuinely empty
    problem (e.g. zero detected pieces) crashes instead of getting a
    trivially-correct empty assignment."""
    assert assign_pairs([]) == []
    assert assign_pairs([[]]) == []


def test_normalizes_non_bool_truthy_values():
    """Purpose: masks supplied as 0/1 ints (a common frame-analysis shape)
    must be accepted identically to bool masks.
    Expected feedback: failure means callers must pre-convert every mask to
    bool by hand, an easy-to-forget step that would silently break on the
    first int-mask caller."""
    int_mask = ((0, 1), (1, 0))
    bool_mask = ((False, True), (True, False))
    assert dihedral_transforms(int_mask)[0]["mask"] == bool_mask
    assert crop_to_content(int_mask)["mask"] == bool_mask
    assert iou(int_mask, bool_mask) == 1.0
