"""Tests for the S5I5 slider adapter (R56, 2026-07-15).

S5I5 (see the adapter module docstring) is a click-only slider puzzle: clicking a
track frame's far/near half moves its attached goal marker ±1 unit along the
slider axis, and the level wins when every target marker has a goal on it. The
adapter is an online effect-learning greedy; these tests pin the pure helpers
(distance, candidate generation, goal/target split via 8-connectivity) and that
choose_action emits a click.
"""

from __future__ import annotations

from types import SimpleNamespace

from arcengine import GameAction

from admorphiq.adapters25.s5i5 import Adapter, _dist


def _frame(grid: list[list[int]], levels: int = 0, state: str = "NOT_FINISHED") -> SimpleNamespace:
    return SimpleNamespace(
        frame=[[list(row) for row in grid]],
        state=SimpleNamespace(name=state),
        available_actions=[6],
        levels_completed=levels,
    )


def _blank(size: int = 40, bg: int = 5) -> list[list[int]]:
    return [[bg] * size for _ in range(size)]


def test_dist_is_manhattan():
    """Purpose: goal-to-target residuals and effect-direction gains are scored by
    Manhattan distance.
    Expected feedback: failure means the greedy mis-ranks which click reduces a
    goal's distance to its target."""
    assert _dist((0, 0), (3, 4)) == 7
    assert _dist((10, 52), (10, 45)) == 7


def test_make_candidates_emits_four_edge_midpoints_per_track():
    """Purpose: each colour-2 track frame contributes its four edge midpoints as
    candidate click points (the far/near halves that drive the slider on either
    orientation); which one moves a goal is measured, not assumed.
    Expected feedback: failure means the adapter can't reach the track end that
    extends/shrinks the slider, so no goal ever moves."""
    grid = _blank(64)
    # A colour-2 track frame spanning rows 18-24, cols 36-48.
    for c in range(36, 49):
        grid[18][c] = 2
        grid[24][c] = 2
    for r in range(18, 25):
        grid[r][36] = 2
        grid[r][48] = 2
    grid_t = tuple(tuple(r) for r in grid)
    from admorphiq.kernels import find_regions

    ad = Adapter()
    regions = find_regions(grid_t, background=5, connectivity=8)
    pts = ad._make_candidates(regions)
    mr, mc = 21, 42
    assert (mr, 48) in pts and (mr, 36) in pts  # right / left edge midpoints
    assert (24, mc) in pts and (18, mc) in pts  # bottom / top edge midpoints


def test_lock_splits_goals_and_targets_by_size_under_eight_connectivity():
    """Purpose: with 8-connectivity a target's DIAGONAL diamond stays one blob
    (size > goal threshold) while a single-pixel goal stays small — so _lock
    records the diamond as a target and _goals reports the pixel as a goal.
    Expected feedback: failure (e.g. 4-connectivity) shatters the diamond into
    size-1 fragments, so every marker looks like a goal and no target is locked
    — the exact bug that made the first build score 0/8."""
    grid = _blank()
    # A target diamond of 4 diagonally-adjacent colour-13 pixels around (10, 20).
    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        grid[10 + dr][20 + dc] = 13
    # A single-pixel goal at (30, 8).
    grid[30][8] = 13
    grid_t = tuple(tuple(r) for r in grid)
    from admorphiq.kernels import find_regions

    ad = Adapter()
    regions = find_regions(grid_t, background=5, connectivity=8)
    ad._lock(regions, grid_t)
    assert ad._targets == [(10, 20)]  # the diamond, as one target
    assert (30, 8) in ad._goals(regions)  # the single pixel, as a goal


def test_choose_action_emits_a_click():
    """Purpose: S5I5 is click-only; every decision must be an ACTION6 click with
    coordinates, and the env loop must not break.
    Expected feedback: failure means the adapter returns a non-click or crashes,
    so the slider is never driven."""
    grid = _blank()
    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        grid[10 + dr][20 + dc] = 13
    grid[30][8] = 13
    for c in range(4, 13):
        grid[28][c] = 2
        grid[32][c] = 2
    ad = Adapter()
    ad._levels_seen = 0
    action = ad.choose_action([], _frame(grid))
    assert isinstance(action, GameAction)
    assert action.action_data is not None
