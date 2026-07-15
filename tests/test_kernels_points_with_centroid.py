"""Tests for ``admorphiq.kernels.points_with_centroid`` (R56 r11l geometry).

The kernel chooses ``count`` cells whose floor-division centroid equals a
target, all satisfying a caller ``is_free`` predicate, preferring the fewest
moves from a current configuration. It is the game-agnostic core of r11l's
centroid-assembly planner (a creature's body sits at the integer centroid of
its legs; win = body on the target nest).
"""

from __future__ import annotations

from admorphiq.kernels import points_with_centroid


def _floor_centroid(pts, count):
    return (sum(r for r, _ in pts) // count, sum(c for _, c in pts) // count)


def test_move_one_leg_minimal_when_possible():
    """Purpose: with a current 2-leg configuration and an all-free board, the
    kernel keeps one leg and moves exactly one so the floored centroid hits
    the target — the minimum-click solution. Expected feedback: a FAIL means
    the planner would issue more placements than necessary (worse RHAE) or
    miss the exact centroid."""
    target = (21, 39)
    current = [(36, 7), (59, 27)]  # centroid (47, 17)
    pts = points_with_centroid(target, 2, lambda cell: True, current=current)
    assert pts is not None
    assert _floor_centroid(pts, 2) == target
    # exactly one leg moved (the other kept from current)
    kept = [p for p in pts if p in current]
    assert len(kept) == 1


def test_already_solved_returns_zero_moves():
    """Purpose: if the current legs already centroid onto the target and are
    free, return them unchanged (no wasted clicks). Expected feedback: a FAIL
    means the planner re-places legs that were already correct."""
    current = [(10, 10), (30, 30)]  # centroid (20, 20)
    pts = points_with_centroid((20, 20), 2, lambda cell: True, current=current)
    assert pts == [(10, 10), (30, 30)]


def test_straddle_when_move_one_is_blocked():
    """Purpose: when the single-move target cell is blocked (a hazard), the
    kernel falls back to a symmetric straddle of free cells that still sums to
    the exact centroid. Expected feedback: a FAIL means a hazard on the
    one-move cell would strand the planner even though a valid free
    configuration exists."""
    target = (20, 20)
    current = [(0, 0), (5, 5)]
    # Block exactly the two single-move solution cells so pref-2 must fire.
    blocked = {(40, 40), (35, 35)}
    pts = points_with_centroid(
        target, 2, lambda cell: tuple(cell) not in blocked, current=current
    )
    assert pts is not None
    assert _floor_centroid(pts, 2) == target
    assert all(tuple(p) not in blocked for p in pts)


def test_odd_count_uses_centre_plus_pairs():
    """Purpose: an odd leg count is handled (centre point + symmetric pairs),
    still hitting the exact floored centroid. Expected feedback: a FAIL means
    creatures with 3 (or any odd number of) legs cannot be planned."""
    pts = points_with_centroid((10, 10), 3, lambda cell: True)
    assert pts is not None
    assert len(pts) == 3
    assert _floor_centroid(pts, 3) == (10, 10)


def test_returns_none_when_everything_blocked():
    """Purpose: with no free cell anywhere the kernel reports failure rather
    than returning an invalid (hazard-overlapping) plan. Expected feedback: a
    FAIL means the planner could hand the executor a placement onto a hazard,
    risking the game's bad-placement strikes."""
    assert points_with_centroid((5, 5), 2, lambda cell: False, max_radius=5) is None
