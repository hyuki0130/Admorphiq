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

from admorphiq.adapters25.re86 import (
    Adapter,
    _l5_gate_colors,
    _l5_hazard_between,
    _sign,
    _station_boxes,
    _target_boxes,
)


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


def test_station_boxes_reads_swatch_colour_and_box_from_colour2_border():
    """Purpose: an L4+ changer station is a solid swatch inside a colour-2
    bordered box; ``_station_boxes`` must return the swatch colour (the colour a
    mismatched movable is recoloured to on contact) keyed to the box centre, plus
    the box bbox used to reject station swatches from the movable parse.
    Expected feedback: failure means L4 loses its recolour destinations, so no
    movable can be routed to match its gates."""
    bg = 5
    grid = [[bg] * 12 for _ in range(12)]
    # A colour-2 bordered 4x4 box at rows 2-5, cols 2-5, colour-7 swatch inside.
    for r in range(2, 6):
        grid[r][2] = grid[r][5] = 2
        grid[2][r] = grid[5][r] = 2
    grid[3][3] = grid[3][4] = grid[4][3] = grid[4][4] = 7
    grid_t = tuple(tuple(r) for r in grid)
    by_color, boxes = _station_boxes(grid_t)
    assert by_color == {7: (3, 3)}
    assert boxes == [(2, 2, 5, 5)]


def test_l4_recolour_want_aligns_column_before_moving_vertically():
    """Purpose: routing a movable to its changer station must align the COLUMN
    first (horizontal, in the station-free interior) and only then move
    vertically along the target's column — every station is on an edge row, so
    this avoids re-recolouring against a different-colour station en route.
    Expected feedback: failure means a route can cross a wrong-colour station and
    corrupt the recolour, breaking the L4 assignment."""
    # Far in column: must move horizontally toward the station column first.
    assert Adapter._l4_recolour_want((30, 10), (6, 30)) == (0, 1)
    # Column aligned (within tolerance): now move vertically toward the row.
    assert Adapter._l4_recolour_want((30, 29), (6, 30)) == (-1, 0)


def test_l5_gate_colors_excludes_movable_colours():
    """Purpose: L5 gate colours are station-swatch colours that appear as
    ISOLATED (≤4-px) marks outside a station box AND are not a current movable
    colour. A movable whose colour is ALSO a station colour (11/14 on this env)
    sheds thin ≤4-px sprite-arm fragments; those must NOT be counted as gate
    cells. Pin that a station colour present as an isolated mark is a gate colour
    UNLESS it is a movable colour.
    Expected feedback: failure resurrects the measured runaway where gate colours
    included the movable colours, the gate accumulator grew without bound as
    pieces moved, the assignment never locked, and the reveal nudged a piece into
    a station and mis-recoloured it."""
    bg = 5
    grid = [[bg] * 20 for _ in range(20)]
    # A station box (colour-2 border) with a colour-3 swatch — colour 3 is a
    # station colour but appears ONLY inside its box (no loose marks) → not a gate.
    for r in range(1, 5):
        grid[r][1] = grid[r][4] = 2
        grid[1][r] = grid[4][r] = 2
    grid[2][2] = grid[2][3] = grid[3][2] = grid[3][3] = 3
    # An isolated colour-7 mark (a real gate cell) far from the box.
    grid[12][12] = 7
    # An isolated colour-9 mark — but colour 9 is a MOVABLE colour → excluded.
    grid[15][15] = 9
    grid_t = tuple(tuple(r) for r in grid)
    _stations, boxes = _station_boxes(grid_t)
    station_colors = {3, 7, 9}  # what the caller derives from the station swatches
    gate_colors = _l5_gate_colors(grid_t, boxes, station_colors, movable_colors={9, 12})
    assert 7 in gate_colors  # isolated station-colour mark, not a movable colour
    assert 9 not in gate_colors  # a movable colour, excluded despite the loose mark
    assert 3 not in gate_colors  # only inside its box, no loose mark


def test_l5_hazard_between_flags_a_mid_edge_station_on_the_vertical_leg():
    """Purpose: the L5 corner-route fix. A colour-9 piece recolours at the
    bottom-left corner station-9 then must reach the TOP cluster; a mid-edge
    station (station-14, left column, between the corner and the top) would clip
    the fat body on a straight ascent. ``_l5_hazard_between`` must flag exactly
    that geometry so the cover phase detours to the station-free centre column,
    and must NOT flag a piece whose vertical leg passes no foreign station.
    Expected feedback: failure means the top colour-9 piece ascends the left
    column into station-14 and re-recolours 9→14, so L5 never clears."""
    # station boxes keyed by swatch colour (row0,col0,row1,col1).
    sbox = {9: (52, 3, 57, 8), 14: (26, 2, 32, 8), 8: (52, 53, 57, 58)}
    half = 11
    # Piece is colour 9 at the corner (row 54, col 5); its cluster is at the top
    # (row 6). station-14 (col 5, row 29) sits on that vertical leg near col 5.
    assert _l5_hazard_between(sbox, own_color=9, marker=(54, 5), crow=6, half=half)
    # Same piece but its cluster is just below it (row 50) — no foreign station on
    # that short leg → no hazard, so the direct cover route is used.
    assert not _l5_hazard_between(sbox, own_color=9, marker=(54, 5), crow=50, half=half)
