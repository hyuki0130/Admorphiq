"""Tests for the RE86 delivery / colour-assignment adapter (R56, 2026-07-15).

RE86 (see the adapter module docstring) is a delivery + colour-assignment
puzzle: ACTION1-4 move the selected movable, ACTION5 cycles selection, changers
recolour a movable, and the win covers each static colour-bordered target box
with a matching-colour movable pixel. The adapter is a banked best-effort
covering-offset greedy; these tests pin the pure perception helpers and that
choose_action returns a real GameAction.
"""

from __future__ import annotations

from types import SimpleNamespace

from arcengine import GameAction

from admorphiq.adapters25.re86 import Adapter, _sign, _target_boxes


def test_active_movable_is_the_centroid_nearest_region_not_the_largest():
    """Purpose: the SELECTED movable carries the marker at its geometric centre,
    so ``_active_movable`` must return the region whose centroid is nearest the
    marker — even when a larger region's sparse body overlaps the marker's
    neighbourhood. Pin that the small plus the marker sits inside wins over a
    bigger cross whose bounding box also reaches the marker.
    Expected feedback: failure resurrects the L2 mis-selection bug where the
    planner drove a big cross's covering offset while the engine moved the other
    piece, oscillating without ever converging."""
    bg = 5
    grid = [[bg] * 24 for _ in range(24)]
    # A big colour-7 X (sparse, ~24 cells) whose arms sweep across the frame and
    # reach toward the marker's neighbourhood, centroid near the middle.
    for i in range(20):
        grid[2 + i][2 + i] = 7
        grid[2 + i][21 - i] = 7
    # A small colour-8 plus (12 cells) tightly centred on the marker at (11,11).
    grid[11][11] = 0  # selection marker at the plus centre
    for d in range(1, 4):
        grid[11 - d][11] = grid[11 + d][11] = 8
        grid[11][11 - d] = grid[11][11 + d] = 8
    grid_t = tuple(tuple(r) for r in grid)
    ad = Adapter()
    active = ad._active_movable(grid_t, (11, 11))
    assert active is not None
    assert active[0] == 8  # the plus the marker sits inside, not the bigger X


def _frame(grid: list[list[int]], levels: int = 0, state: str = "NOT_FINISHED") -> SimpleNamespace:
    return SimpleNamespace(
        frame=[[list(row) for row in grid]],
        state=SimpleNamespace(name=state),
        available_actions=[1, 2, 3, 4, 5],
        levels_completed=levels,
    )


def test_sign_is_three_valued():
    """Purpose: measured move directions and covering residuals compare via
    -1/0/+1 per axis.
    Expected feedback: failure means the adapter can't match a measured move to
    the axis it needs to close."""
    assert (_sign(-4), _sign(0), _sign(6)) == (-1, 0, 1)


def test_target_boxes_finds_colour_bordered_centres():
    """Purpose: a target is a coloured centre enclosed on all four sides by the
    border colour (4); its centre cell (and colour) is the delivery goal. Pin
    that such a box is detected and its colour readable at the returned cell.
    Expected feedback: failure means the adapter has no goals to aim movables
    at, or aims at the wrong cell/colour."""
    bg = 5
    grid = [[bg] * 12 for _ in range(12)]
    # A colour-9 target box at centre (3, 3): 4-border around a 9 centre.
    grid[2][2], grid[2][3], grid[2][4] = 4, 4, 4
    grid[3][2], grid[3][3], grid[3][4] = 4, 9, 4
    grid[4][2], grid[4][3], grid[4][4] = 4, 4, 4
    grid_t = tuple(tuple(r) for r in grid)
    boxes = _target_boxes(grid_t)
    assert (3, 3) in boxes
    assert grid_t[3][3] == 9


def test_target_boxes_ignores_border_and_unbordered_pixels():
    """Purpose: border pixels (colour 4) and lone coloured pixels without a full
    4-border must NOT be reported as targets.
    Expected feedback: failure means changer lines / stray movable pixels get
    mistaken for delivery goals, sending movables to bogus positions."""
    bg = 5
    grid = [[bg] * 10 for _ in range(10)]
    grid[5][5] = 9  # a lone coloured pixel, no border
    grid[1][1] = 4  # a lone border pixel
    grid_t = tuple(tuple(r) for r in grid)
    assert _target_boxes(grid_t) == []


def test_choose_action_returns_a_gameaction_and_measures_a_move():
    """Purpose: choose_action must return a real GameAction, and a movement
    action followed by an observed marker displacement must be recorded in the
    measured direction map (the covering planner depends on it).
    Expected feedback: failure means the env loop breaks (non-GameAction) or the
    adapter never learns which action moves which way, so it can never aim a
    covering move."""
    bg = 5
    # A selection marker (0) that the adapter tracks; move it up between frames.
    grid_a = [[bg] * 12 for _ in range(12)]
    grid_a[6][6] = 0
    ad = Adapter()
    ad._levels_seen = 0
    a1 = ad.choose_action([], _frame(grid_a))
    assert isinstance(a1, GameAction)

    # Marker moved up one cell — the pending action's direction should record.
    grid_b = [[bg] * 12 for _ in range(12)]
    grid_b[5][6] = 0
    pending = ad._pending_action
    a2 = ad.choose_action([], _frame(grid_b))
    assert isinstance(a2, GameAction)
    if pending is not None:
        assert pending in ad._dir  # the displacement was measured
