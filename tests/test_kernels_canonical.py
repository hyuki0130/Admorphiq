"""Tests for the pure state-canonicalization kernels (R56)."""

import pytest

from admorphiq.kernels.canonical import (
    canonical_key,
    choose_canonicalization,
    key_table,
    stability_report,
)


def test_exact_differs_but_downsample_ignores_minority_pixel_flip():
    """Purpose: within one downsample block, flipping a MINORITY pixel to a
    different minority colour (majority colour unchanged) must change the
    'exact' key but leave 'downsample' (mode-pooled) unchanged.
    Expected feedback: failure on 'exact' unchanged means the raw-grid
    passthrough is broken; failure on 'downsample' changed means mode-
    pooling isn't actually pooling (degenerated to exact)."""
    frame_a = [
        [0, 0, 0, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 1],
    ]
    frame_b = [
        [3, 0, 0, 0],  # a DIFFERENT minority pixel flipped elsewhere
        [0, 0, 0, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 1],
    ]
    assert canonical_key(frame_a, mode="exact") != canonical_key(frame_b, mode="exact")
    assert canonical_key(frame_a, mode="downsample", factor=4) == canonical_key(
        frame_b, mode="downsample", factor=4
    )


def test_exact_differs_but_histogram_ignores_position_only_swap():
    """Purpose: swapping the POSITIONS of two colours (same colour counts,
    different layout) must change 'exact' but leave 'histogram' unchanged —
    histogram is spatially blind by design.
    Expected feedback: failure on 'histogram' changed means the colour
    census is accidentally position-sensitive (e.g. iterating without
    actually aggregating counts)."""
    frame_c = [
        [0, 1],
        [0, 0],
    ]
    frame_d = [
        [0, 0],
        [0, 1],
    ]
    assert canonical_key(frame_c, mode="exact") != canonical_key(frame_d, mode="exact")
    assert canonical_key(frame_c, mode="histogram") == canonical_key(frame_d, mode="histogram")
    assert canonical_key(frame_c, mode="histogram") == ((0, 3), (1, 1))


def test_shape_mode_ignores_sprite_translation():
    """Purpose: the same 3-cell sprite shape drawn at two different board
    positions over the same background must produce the SAME 'shape' key
    (bounding-box-normalized), while 'exact' still tells them apart.
    Expected feedback: failure means shape mode either isn't cropping to
    the bounding box (so translation still changes the key) or is
    accidentally colour-sensitive in a way that breaks pure position
    comparison."""
    frame_e = [
        [0, 0, 0, 0, 0],
        [0, 5, 5, 0, 0],
        [0, 5, 0, 0, 0],
        [0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0],
    ]
    frame_f = [
        [0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0],
        [0, 0, 0, 5, 5],
        [0, 0, 0, 5, 0],
        [0, 0, 0, 0, 0],
    ]
    assert canonical_key(frame_e, mode="exact") != canonical_key(frame_f, mode="exact")
    key_e = canonical_key(frame_e, mode="shape", background=0)
    key_f = canonical_key(frame_f, mode="shape", background=0)
    assert key_e == key_f
    assert key_e == frozenset({(0, 0), (0, 1), (1, 0)})


def test_shape_mode_default_background_is_most_common_colour():
    """Purpose: when background is not given, it must be inferred as the
    grid's own most common colour, not hardcoded to 0.
    Expected feedback: failure means shape mode can't be used on a frame
    whose background colour genuinely isn't 0 (a real possibility — the
    game's palette is not fixed)."""
    frame = [
        [7, 7, 7],
        [7, 9, 7],
        [7, 7, 7],
    ]
    key = canonical_key(frame, mode="shape")  # background inferred as 7
    assert key == frozenset({(0, 0)})


def test_canonical_key_unknown_mode_raises():
    """Purpose: an unrecognized mode string is a caller error, rejected
    loudly rather than silently returning a wrong/default key.
    Expected feedback: failure means a typo'd mode name would silently
    produce a garbage or misleading canonicalization instead of a clear
    error the caller can act on."""
    with pytest.raises(ValueError):
        canonical_key([[0]], mode="bogus")


def test_canonical_key_downsample_nonpositive_factor_raises():
    """Purpose: factor <= 0 has no valid block-pooling interpretation (0
    would infinite-loop the block stride) and must raise, not hang or
    silently misbehave.
    Expected feedback: failure means a bad factor value risks a runtime
    hang inside the 9h Kaggle budget instead of a clean, immediate error."""
    with pytest.raises(ValueError):
        canonical_key([[0, 0], [0, 0]], mode="downsample", factor=0)


def test_canonical_key_empty_frame_every_mode():
    """Purpose: an empty frame (no rows) must degrade cleanly to an empty/
    trivial key under every mode, never raise.
    Expected feedback: failure means a genuinely empty observation (e.g.
    before any frame has been seen) crashes canonicalization instead of
    returning a well-defined 'nothing here' key."""
    assert canonical_key([], mode="exact") == ()
    assert canonical_key([], mode="downsample") == ()
    assert canonical_key([], mode="histogram") == ()
    assert canonical_key([], mode="shape") == frozenset()


def test_key_table_matches_individual_canonical_key_calls():
    """Purpose: key_table is a convenience wrapper — its per-mode lists must
    match calling canonical_key directly for each (frame, mode) pair.
    Expected feedback: failure means the wrapper's iteration/dispatch is
    inconsistent with the primitive it wraps, which would make any caller
    that switched between the two get different answers for the same input."""
    frames = [[[0, 1]], [[1, 0]]]
    modes = ["exact", "histogram"]
    table = key_table(frames, modes)
    assert table["exact"] == [canonical_key(f, mode="exact") for f in frames]
    assert table["histogram"] == [canonical_key(f, mode="histogram") for f in frames]


# Shared fixture for the stability_report / choose_canonicalization tests
# below: group0 = two frames the caller asserts are the SAME true state (one
# has an irrelevant flickering pixel at (0,0)); group1 = one frame asserting
# a DIFFERENT true state, but sharing group0's dominant colour histogram AND
# (as an isolated single foreground pixel) its shape.
_G1A = [
    [0, 0, 0],
    [0, 5, 0],
    [0, 0, 0],
]
_G1B = [
    [1, 0, 0],  # flicker pixel: (0,0) toggled 0 -> 1, same true state
    [0, 5, 0],
    [0, 0, 0],
]
_G2A = [
    [5, 0, 0],  # a DIFFERENT true state: same colour counts as _G1A,
    [0, 0, 0],  # same isolated-single-pixel shape, different position
    [0, 0, 0],
]
_FRAME_GROUPS = [[_G1A, _G1B], [_G2A]]


def test_stability_report_flags_exact_over_splitting_and_histogram_over_merging():
    """Purpose: on the shared fixture, 'exact' must flag OVER-SPLITTING
    (the flicker pixel fragments one true state into 2 keys, intra_splits=1)
    while correctly reporting ZERO inter_collisions (it never confuses the
    two genuinely different states); 'histogram' must flag OVER-MERGING
    (group0's _G1A and group1's _G2A share identical colour counts,
    inter_collisions=1) despite being asserted as different true states.
    Expected feedback: failure on exact's intra_splits means the grouping-
    consistency accounting is broken; failure on histogram's
    inter_collisions means the aliasing-detection accounting is broken —
    these are the two failure modes a real canonicalization choice must
    trade off between."""
    report = stability_report(_FRAME_GROUPS, modes=("exact", "histogram"))
    assert report["exact"]["intra_splits"] == 1
    assert report["exact"]["inter_collisions"] == 0
    assert report["exact"]["intra_consistent"] is False
    assert report["histogram"]["inter_collisions"] == 1


def test_stability_report_distinct_keys_count():
    """Purpose: pin 'distinct_keys' as a plain count of unique keys across
    ALL frames/groups for a mode — 3 for 'exact' (every frame differs).
    Expected feedback: failure means distinct_keys double-counts, under-
    counts, or conflates it with distinct_keys-per-group instead of
    overall."""
    report = stability_report(_FRAME_GROUPS, modes=("exact",))
    assert report["exact"]["distinct_keys"] == 3


def test_choose_canonicalization_prefers_zero_collisions_over_cost():
    """Purpose: on the shared fixture, 'exact' is the ONLY mode with zero
    inter_collisions (downsample/histogram/shape all merge _G1A and _G2A in
    some form), so it must win despite being the MOST expensive mode by the
    documented cost ranking — proving collision-avoidance dominates cost,
    not the reverse.
    Expected feedback: failure means the priority ordering is implemented
    backwards (cost before correctness), which would pick a cheap mode that
    silently conflates distinct game states."""
    result = choose_canonicalization(_FRAME_GROUPS)
    assert result["mode"] == "exact"
    assert result["report"]["exact"]["inter_collisions"] == 0
    # Every other default mode DOES collide on this fixture (sanity check
    # that this is a real trade-off, not a vacuous win).
    for mode in ("downsample", "histogram", "shape"):
        assert result["report"][mode]["inter_collisions"] > 0


def test_choose_canonicalization_tie_breaks_by_cost_order():
    """Purpose: when two modes tie at zero collisions and zero splits, the
    CHEAPER mode (by the fixed histogram < shape < downsample < exact cost
    ranking) must win — proven here with 'shape' listed first in the
    `modes` argument (so a bug that just returns the first tied entry would
    wrongly pick 'shape', not 'histogram').
    Expected feedback: failure means the tie-break either ignores the cost
    ranking entirely or is order-dependent on how `modes` was passed in,
    making the result non-deterministic across equivalent calls."""
    frame_p = [
        [0, 0, 0, 0],
        [0, 7, 7, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 0],
    ]
    frame_q = [
        [0, 0, 0, 0],
        [0, 0, 0, 0],
        [0, 9, 0, 0],
        [0, 9, 0, 0],
    ]
    groups = [[frame_p], [frame_q]]
    result = choose_canonicalization(groups, modes=("shape", "histogram"))
    assert result["report"]["shape"]["inter_collisions"] == 0
    assert result["report"]["histogram"]["inter_collisions"] == 0
    assert result["mode"] == "histogram"  # cheaper than shape, both tied otherwise
