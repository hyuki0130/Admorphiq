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
    _l6_cross_state,
    _l6_obstacle_box,
    _l7_bfs_plan,
    _l7_cross_sim,
    _l7_full_bars,
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


def test_l6_is_rect_distinguishes_outline_from_cross_targets():
    """Purpose: L6 has two pieces distinguished ONLY by target geometry (no
    sprite-tag read) — the OUTLINE piece's four targets are a rectangle's four
    corners; the CROSS piece's four are a plus (a shared-col pair + a shared-row
    pair that is NOT a 2x2 grid). ``Adapter._l6_is_rect`` must separate them.
    Expected feedback: failure means the two movables would be mis-assigned (the
    cross driven as an outline or vice versa), so neither reaches its target and
    L6 never clears."""
    outline_corners = [(30, 45), (30, 54), (57, 45), (57, 54)]
    cross_plus = [(6, 12), (9, 9), (9, 30), (27, 12)]
    assert Adapter._l6_is_rect(outline_corners)
    assert not Adapter._l6_is_rect(cross_plus)


def test_l6_derive_cross_targets_are_frame_derived_not_hardcoded():
    """Purpose: the cross's placement targets (frame top-left + bar frame-relative
    positions) must be DERIVED from its four tips, never hardcoded — so a
    hash-rotated L6 with shifted tips still solves. Pin that for the measured tips
    the derivation yields the config proven to cover all four live.
    Expected feedback: failure means the cross would be carried to the wrong
    frame position and miss its tips (regressing the 6/8 clear); a hardcoded
    constant sneaking in would also break this on any shifted-tip input."""
    ad = Adapter()
    ad._l6_cross_tgt = [(6, 12), (9, 9), (9, 30), (27, 12)]
    ad._l6_size = 25
    ad._l6_derive_cross_targets()
    # Tc = 12 (cols 12 shared by the two vertical tips), Tr = 9 (row shared by the
    # two horizontal tips); anchor the frame's far edges on Rbot=27 / Cright=30.
    assert ad._l6_r0_t == 27 - 24
    assert ad._l6_c0_t == 30 - 24
    assert ad._l6_vrel_t == 12 - ad._l6_c0_t
    assert ad._l6_hrel_t == 9 - ad._l6_r0_t


def test_l6_obstacle_box_finds_the_static_colour1_blob():
    """Purpose: the reshape anchor is the static colour-1 central obstacle; a push
    that pixel-overlaps it triggers the reshape, so the controller must locate its
    bbox frame-only. Pin that ``_l6_obstacle_box`` returns the blob's bounds and
    ignores a stray single colour-1 pixel.
    Expected feedback: failure means the corridor tests and reshape alignment lose
    their anchor and the L6 controller cannot place either piece."""
    bg = 5
    grid = [[bg] * 40 for _ in range(40)]
    for r in range(28, 36):
        for c in range(28, 36):
            grid[r][c] = 1
    grid[2][2] = 1  # a stray single colour-1 pixel must be ignored (size floor)
    box = _l6_obstacle_box(tuple(tuple(row) for row in grid))
    assert box == (28, 28, 35, 35)


def test_l6_cross_state_reads_bar_positions_of_a_plus():
    """Purpose: the cross is controlled by its vertical/horizontal bar positions
    within a fixed frame; ``_l6_cross_state`` must recover the vbar abs col + hbar
    abs row (and their frame-relative offsets) from the pixel set.
    Expected feedback: failure means the bar-shift control loses its state read and
    the corridor solver cannot know when a bar reached its target."""
    cells = set()
    for r in range(0, 25):  # vertical bar at col 6
        cells.add((r, 6))
    for c in range(0, 25):  # horizontal bar at row 6
        cells.add((6, c))
    s = _l6_cross_state(frozenset(cells))
    assert s["r0"] == 0 and s["c0"] == 0
    assert s["va"] == 6 and s["ha"] == 6
    assert s["vrel"] == 6 and s["hrel"] == 6


# ── L7 (recolour + bar-shift/reshape + place hybrid) ─────────────────────────

_L7_OB = (28, 28, 35, 35)  # the colour-1 obstacle box shared by L6/L7


def test_l7_full_bars_distinguishes_outline_from_cross():
    """Purpose: L7's three movables are classified frame-only — the OUTLINE (hollow
    rectangle) has 2 full-length edge columns + 2 full-length edge rows, a CROSS
    has exactly 1 full column (vbar) + 1 full row (hbar). ``_l7_full_bars`` must
    return (2,2) for the outline and (1,1) for a cross so the assignment can route
    the reshaper to the rectangle target and the two crosses to the plus targets.
    Expected feedback: failure means the outline/cross roles swap, so a cross is
    driven as a reshaper (or vice versa) and no piece reaches its target."""
    outline = set()
    for i in range(13):  # 13x13 hollow square outline (4 edges)
        outline |= {(0, i), (12, i), (i, 0), (i, 12)}
    cross = set()
    for i in range(19):  # 19x19 plus (1 vbar col 9 + 1 hbar row 9)
        cross |= {(i, 9), (9, i)}
    assert _l7_full_bars(frozenset(outline)) == (2, 2)
    assert _l7_full_bars(frozenset(cross)) == (1, 1)


def test_l7_cross_sim_vbar_set_on_hbar_in_obstacle_left_push():
    """Purpose: the load-bearing bar-SET op. With the HBAR row inside the obstacle
    rows and the VBAR col OUTSIDE the obstacle cols, a LEFT push must revert the
    frame (no translation) and shift the vbar −3 (abs col −3). This is how colour-7
    walks its vbar to the target column.
    Expected feedback: failure means the simulator (hence the BFS place plan)
    disagrees with the engine and the cross never reaches its target col — it was
    live-validated 22/22 pushes, so a break here is a real divergence."""
    # 37x19 cross, hbar row 30 (in obstacle rows 28-35), vbar col 24 (out of 28-35).
    # x=6, y=... : hrel places hbar at row 30, vrel places vbar at col 24.
    x, y, w, h = 6, 12, 37, 19
    vrel, hrel = 18, 18  # vbar col 24, hbar row 30
    before = (x, y, vrel, hrel)
    after = _l7_cross_sim(before, -3, 0, w, h, _L7_OB)  # LEFT push (dx=-3)
    assert after == (x, y, vrel - 3, hrel)  # frame unchanged, vbar shifted -3


def test_l7_cross_sim_free_translation_when_no_bar_in_obstacle():
    """Purpose: away from the obstacle a push is a plain translation of the whole
    frame (bars keep their frame-relative offsets) — the carry mode used to
    position the cross before/after a bar-set.
    Expected feedback: failure means the plan mis-models free motion and the BFS
    routes the piece incorrectly around the board."""
    before = (6, 45, 18, 9)  # spawn-like, far below the obstacle
    after = _l7_cross_sim(before, 0, -3, 6, 6, _L7_OB)  # a small clear cross moving up
    assert after == (6, 42, 18, 9)


def test_l7_bfs_plan_reaches_the_colour8_place_state():
    """Purpose: the cross bar-shift+place is PLANNED by BFS over the faithful
    simulator (not a hand FSM). Pin that a plan exists from a post-recolour state
    to the colour-8 plus place-state (frame x=3,y=9,vrel=6,hrel=6) and that
    replaying it on the simulator lands exactly on the goal.
    Expected feedback: failure means the L7 colour-7 leg has no reachable plan and
    7/8 regresses to 6/8 — the goal was live-verified reachable (~21 pushes)."""
    w, h = 37, 19
    start = (18, 9, 18, 9)
    goal = (3, 9, 6, 6)
    plan = _l7_bfs_plan(start, goal, w, h, _L7_OB, valid=lambda z: z[1] >= 7)
    assert plan is not None
    st = start
    want_to_push = {(-1, 0): (0, -3), (1, 0): (0, 3), (0, -1): (-3, 0), (0, 1): (3, 0)}
    for want in plan:
        dx, dy = want_to_push[want]
        st = _l7_cross_sim(st, dx, dy, w, h, _L7_OB)
    assert st == goal


def test_l7_assign_is_frame_only_rect_to_outline_widest_cross_to_widest_plus():
    """Purpose: the 1:1 movable→target assignment is derived from FRAME geometry
    only — the 2-cell rectangle-corner target goes to the outline (2+2 bars), and
    the wider plus target goes to the wider cross. No colours are hardcoded.
    Expected feedback: failure means a hash-rotated L7 (different colours) would be
    mis-assigned and none of the three pieces would place, so L7 never clears."""
    # Targets: colour-9 = 2-cell rect corners; colour-8 = wide plus; colour-11 = narrow plus.
    tby = {
        9: [(18, 57), (24, 39)],
        8: [(9, 9), (15, 3), (15, 36), (27, 9)],
        11: [(30, 45), (48, 39), (48, 51)],
    }
    # Movables: a 13x13 outline (colour 12), a 37-wide cross (colour 7), a 19-wide
    # cross (colour 10) — only bbox width + bar counts matter here.
    outline_cells = frozenset(
        {(0, i) for i in range(13)} | {(12, i) for i in range(13)}
        | {(i, 0) for i in range(13)} | {(i, 12) for i in range(13)}
    )
    wide_cross = frozenset({(i, 18) for i in range(19)} | {(9, i) for i in range(37)})
    narrow_cross = frozenset({(i, 9) for i in range(19)} | {(9, i) for i in range(19)})
    regs = [
        {"color": 12, "cells": outline_cells, "bbox": (0, 12, 0, 12)},
        {"color": 7, "cells": wide_cross, "bbox": (0, 18, 0, 36)},
        {"color": 10, "cells": narrow_cross, "bbox": (0, 18, 0, 18)},
    ]
    legs = Adapter._l7_assign(regs, tby)
    by_color = {leg["color"]: leg for leg in legs}
    assert by_color[12]["kind"] == "outline" and by_color[12]["tgt_color"] == 9
    assert by_color[7]["kind"] == "cross" and by_color[7]["tgt_color"] == 8  # widest -> widest plus
    assert by_color[10]["kind"] == "cross" and by_color[10]["tgt_color"] == 11


def test_l7_cross_place_target_reads_plus_bars():
    """Purpose: a cross's place target (vbar col, hbar row) is the col shared by the
    vertical tips and the row shared by the horizontal tips of its plus target.
    Expected feedback: failure means the BFS goal is wrong and the cross places off
    its tips."""
    tgt8 = [(9, 9), (15, 3), (15, 36), (27, 9)]  # vbar col 9, hbar row 15
    assert Adapter._l7_cross_place_target(tgt8) == (9, 15)
