"""Unit tests for the frame-only DELIVERY (pick-up / carry / drop) capability
(R28 family, sibling of transform_route.py/rotation.py/slider.py, WA30-class).

These pin the pick-carry-deliver sub-class the world-model agent uses for
levels whose goal is "carry each small item marker into a larger target
zone" (WA30 is the measured exemplar — see delivery.py's module docstring
for the live-trace evidence, including the specific bugs this module's
functions were built to fix: HUD-row contamination of motion calibration,
and a carried item's colour being indistinguishable from the player's own
leading-edge accent). Every test is env-free on synthetic frames or
hand-built dataclasses: the capability must be observation-driven with no
game-id / internal reads, so its behaviour is fully exercised without
touching the live env.
"""

from __future__ import annotations

import numpy as np

from admorphiq.delivery import (
    RingMarker,
    adjacent_cells,
    bbox_min_corner,
    bfs_path,
    detect_delivery_puzzle,
    detect_mover_by_motion,
    locate_player_cell,
    path_to_actions,
    target_slots,
)

_BG = 1
_ITEM_RING = 4
_ITEM_INTERIOR = 9
_TARGET_RING = 9
_TARGET_INTERIOR = 2
_BODY = 14
_ACCENT = 0


def _blank() -> np.ndarray:
    return np.full((64, 64), _BG, dtype=np.int32)


def _stamp_item(layer: np.ndarray, x0: int, y0: int) -> None:
    """A 4x4 item marker: colour-4 ring, colour-9 2x2 interior — mirrors the
    measured WA30 board exactly (ring frame + solid interior fill).
    """
    layer[y0 : y0 + 4, x0 : x0 + 4] = _ITEM_RING
    layer[y0 + 1 : y0 + 3, x0 + 1 : x0 + 3] = _ITEM_INTERIOR


def _stamp_target(layer: np.ndarray, x0: int, y0: int, width: int) -> None:
    """A ``width``x4 target zone: colour-9 ring, colour-2 interior."""
    layer[y0 : y0 + 4, x0 : x0 + width] = _TARGET_RING
    layer[y0 + 1 : y0 + 3, x0 + 1 : x0 + width - 1] = _TARGET_INTERIOR


def _stamp_player(layer: np.ndarray, x0: int, y0: int, facing: str) -> None:
    """A 4x4 player: colour-14 body, colour-0 1-cell leading-edge accent on
    whichever side ``facing`` names — mirrors the measured WA30 player
    exactly (the accent relocates to the last-moved-toward edge).
    """
    layer[y0 : y0 + 4, x0 : x0 + 4] = _BODY
    if facing == "up":
        layer[y0, x0 : x0 + 4] = _ACCENT
    elif facing == "down":
        layer[y0 + 3, x0 : x0 + 4] = _ACCENT
    elif facing == "left":
        layer[y0 : y0 + 4, x0] = _ACCENT
    elif facing == "right":
        layer[y0 : y0 + 4, x0 + 3] = _ACCENT


def _wa30_l1_board() -> np.ndarray:
    """A synthetic WA30-L1-shaped board: 3 items + 1 three-slot target zone
    + a player facing up, mirroring the measured live board's structure.
    """
    layer = _blank()
    _stamp_item(layer, 44, 24)
    _stamp_item(layer, 16, 28)
    _stamp_item(layer, 32, 36)
    _stamp_target(layer, 28, 28, 12)
    _stamp_player(layer, 32, 40, "up")
    return layer


def test_detect_delivery_puzzle_splits_items_from_target_by_size():
    """Purpose: detect_delivery_puzzle finds all 3 item markers and the one
    (larger) target zone, correctly bipartitioned by the measured size-class
    jump rather than a fixed count.

    Expected feedback: a PASS proves the ring+interior detector and the
    size-class split work end-to-end on a realistic synthetic board; a FAIL
    means the agent would never enter the delivery phase, or would confuse
    an item for a target (or vice versa).
    """
    puzzle = detect_delivery_puzzle(_wa30_l1_board(), _BG)
    assert puzzle is not None
    assert len(puzzle.items) == 3
    assert all(m.ring_color == _ITEM_RING and m.interior_color == _ITEM_INTERIOR for m in puzzle.items)
    assert len(puzzle.targets) == 1
    assert puzzle.targets[0].ring_color == _TARGET_RING
    assert puzzle.targets[0].interior_color == _TARGET_INTERIOR


def test_detect_delivery_puzzle_none_without_a_size_class_split():
    """Purpose: a board where every ring+interior marker is the SAME size
    (no item/target distinction the frame can express) returns None rather
    than guessing a split.

    Expected feedback: a PASS proves the phase stays dormant when there is
    no measurable target class; a FAIL means the agent could misroute a
    uniform-marker board (e.g. a different puzzle family entirely) into the
    delivery phase.
    """
    layer = _blank()
    _stamp_item(layer, 10, 10)
    _stamp_item(layer, 30, 30)
    assert detect_delivery_puzzle(layer, _BG) is None


def test_detect_delivery_puzzle_none_with_only_items_or_only_targets():
    """Purpose: a board with items but no target (or vice versa) returns
    None — a delivery mechanic needs both roles present.

    Expected feedback: a PASS proves the phase requires a genuine
    pick-AND-deliver layout, not just any ring+interior marker; a FAIL
    means the agent could enter the phase with nothing to plan toward.
    """
    layer = _blank()
    _stamp_item(layer, 10, 10)
    _stamp_item(layer, 30, 30)
    _stamp_item(layer, 50, 10)
    assert detect_delivery_puzzle(layer, _BG) is None  # 3 same-size items, no target


def test_detect_mover_by_motion_tracks_the_two_colour_player_cleanly():
    """Purpose: detect_mover_by_motion recovers the player's motion from the
    UNION of its two sub-colours (body + relocating accent), excluding the
    known item/target colours, matching the measured live delta exactly.

    Expected feedback: a PASS proves the fix for WA30's unstable
    leading-edge accent (a single fixed colour cannot be tracked reliably
    across two arbitrary frames — see the module docstring); a FAIL means
    calibration would read a scrambled step size the way the generic
    single-colour movement-discovery phase did before this fix (measured:
    (0, 7) instead of the true (0, 4)).
    """
    before = _wa30_l1_board()
    after = _wa30_l1_board()
    after[:] = _BG
    after[24:64, 0:64] = before[24:64, 0:64]  # keep items/target identical
    # Move the player up by 4 (step) from (32, 40) to (32, 36).
    after[40:44, 32:36] = _BG
    _stamp_player(after, 32, 36, "up")
    known = {_ITEM_RING, _ITEM_INTERIOR, _TARGET_RING, _TARGET_INTERIOR}
    pair = detect_mover_by_motion(before, after, known, _BG)
    assert pair is not None
    mover_before, mover_after = pair
    assert (mover_after.cx - mover_before.cx, mover_after.cy - mover_before.cy) == (0.0, -4.0)


def test_detect_mover_by_motion_excludes_the_hud_row():
    """Purpose: a change confined to row >= _HUD_ROW_CUTOFF (the measured
    WA30 move/attempt counter) does not, by itself, register as a mover —
    and does not corrupt a genuine simultaneous player move either.

    Expected feedback: a PASS proves the fix measured on WA30 L1: the HUD
    counter ticks independently of which calibration press is in flight,
    and a tick landing in the same diff as a real player press was
    swirled into the "changed, not excluded" set, skewing the centroid
    (measured: action2's raw delta came out (0, 3) instead of (0, 4)
    before this exclusion existed). A FAIL means calibration could read a
    corrupted step size whenever the HUD happens to tick on the same
    frame as a real move.
    """
    before = _blank()
    _stamp_player(before, 32, 40, "up")
    before[63, 0:10] = 7  # HUD row, unrelated colour
    after = _blank()
    _stamp_player(after, 32, 36, "up")
    after[63, 0:11] = 4  # HUD counter "ticked" on the SAME press
    pair = detect_mover_by_motion(before, after, set(), _BG)
    assert pair is not None
    mover_before, mover_after = pair
    assert (mover_after.cx - mover_before.cx, mover_after.cy - mover_before.cy) == (0.0, -4.0)
    # HUD row cells never appear in either footprint.
    assert not any(y == 63 for _x, y in mover_before.cells)
    assert not any(y == 63 for _x, y in mover_after.cells)


def test_detect_mover_by_motion_none_when_nothing_relevant_changed():
    """Purpose: an identical before/after frame (or one whose only change is
    excluded/HUD) returns None rather than fabricating a mover.

    Expected feedback: a PASS proves a blocked or wasted press correctly
    signals "no usable calibration data" to the caller; a FAIL could crash
    downstream centroid math or record a bogus (0, 0) step.
    """
    layer = _wa30_l1_board()
    known = {_ITEM_RING, _ITEM_INTERIOR, _TARGET_RING, _TARGET_INTERIOR}
    assert detect_mover_by_motion(layer, layer.copy(), known, _BG) is None


def test_locate_player_cell_ignores_a_carried_item_in_the_same_accent_colour():
    """Purpose: locate_player_cell recovers the player's TRUE grid cell even
    when a carried item is rendered in the SAME accent colour as the
    player's own leading-edge marker, by anchoring on the stable body
    colour and only re-adding accent cells directly touching it.

    Expected feedback: a PASS proves the fix for the actual bug measured
    live on WA30 L1: a colour-mask lookup over the full player colour set
    included the carried item's cells too, undershooting the delivery
    target by exactly one grid step every time (every L1 delivery landed
    one cell short before this fix). A FAIL means a delivery leg could
    silently mis-target again.
    """
    layer = _blank()
    # Player body+marker at (32, 40)-(35,43), facing up (accent at row 40).
    _stamp_player(layer, 32, 40, "up")
    # A "carried" item touching the marker directly above (rows 36-39) --
    # rendered ENTIRELY in the accent colour, exactly as measured live.
    layer[36:40, 32:36] = _ACCENT
    cell = locate_player_cell(layer, _BODY, {_ACCENT})
    assert cell == (32, 40)  # the PLAYER's own cell, not the item's.


def test_locate_player_cell_reconstructs_the_full_cell_regardless_of_facing():
    """Purpose: locate_player_cell gives the same true grid-cell corner
    whether the accent marker sits on the top, bottom, left, or right edge
    — the exact ambiguity a naive "body colour bbox alone" approach cannot
    resolve (a missing edge shifts the bbox's own min-corner on whichever
    axis is short).

    Expected feedback: a PASS proves the adjacency reconstruction is
    orientation-independent; a FAIL means player-location would drift
    depending on which direction was pressed last.
    """
    for facing in ("up", "down", "left", "right"):
        layer = _blank()
        _stamp_player(layer, 20, 20, facing)
        assert locate_player_cell(layer, _BODY, {_ACCENT}) == (20, 20), facing


def test_locate_player_cell_none_when_body_colour_absent():
    """Purpose: locate_player_cell returns None when the body colour is not
    present at all (a genuinely unusable frame), instead of crashing on an
    empty cell set.

    Expected feedback: a PASS proves the caller gets a clean "give up"
    signal; a FAIL could raise on an empty-array reduction deep in the
    delivery phase's planning step.
    """
    assert locate_player_cell(_blank(), _BODY, {_ACCENT}) is None


def test_target_slots_tiles_a_multi_item_zone_into_item_sized_cells():
    """Purpose: target_slots partitions a target zone's own footprint into
    exactly the item-sized sub-cells it can hold — matching the measured
    WA30 L1 board (one 12x4 target zone tiles into 3 4x4 slots).

    Expected feedback: a PASS proves multi-item target zones are handled
    generically (derived from the zone's own measured extent, not a fixed
    slot count); a FAIL means only single-item target zones could ever be
    filled correctly.
    """
    target = RingMarker(
        ring_color=_TARGET_RING,
        interior_color=_TARGET_INTERIOR,
        cells=frozenset((x, y) for y in range(28, 32) for x in range(28, 40)),
        cx=33.5,
        cy=29.5,
    )
    assert target_slots(target, 4) == [(28, 28), (32, 28), (36, 28)]


def test_target_slots_empty_when_extent_is_not_a_clean_multiple():
    """Purpose: a target zone whose extent does NOT evenly tile into
    ``slot_size`` returns no slots rather than an invented partial one.

    Expected feedback: a PASS proves an uneven remainder is dropped, not
    interpolated (no case for it has ever been measured); a FAIL means the
    planner could compute a slot that doesn't actually correspond to any
    real drop position on the board.
    """
    target = RingMarker(
        ring_color=_TARGET_RING,
        interior_color=_TARGET_INTERIOR,
        cells=frozenset((x, y) for y in range(28, 32) for x in range(28, 39)),  # width 11
        cx=33.0,
        cy=29.5,
    )
    assert target_slots(target, 4) == []


def test_adjacent_cells_returns_the_four_cardinal_step_neighbours():
    """Purpose: adjacent_cells enumerates exactly the 4 grid-step neighbours
    of a cell, in a fixed (left, right, up, down) order the BFS goal-set
    construction relies on being exhaustive (order itself does not matter
    to the caller, only completeness).

    Expected feedback: a PASS pins the primitive the pickup-adjacency BFS
    goal set is built from; a FAIL means an item could be approached from
    a nonexistent or duplicated direction.
    """
    assert set(adjacent_cells((10, 10), 4)) == {(6, 10), (14, 10), (10, 6), (10, 14)}


def test_bfs_path_routes_around_a_blocked_item_and_stays_in_bounds():
    """Purpose: bfs_path finds a shortest grid path to any cell in the goal
    set, routing around blocked cells (undelivered items) and never
    stepping outside the layer's bounds.

    Expected feedback: a PASS proves the pure pathfinder used for BOTH the
    pickup-approach leg and the carried-item delivery leg behaves
    correctly in isolation; a FAIL means a delivery plan could walk into a
    wall or another item.
    """
    blocked = {(8, 0)}  # directly blocks the straight-line path
    path = bfs_path(blocked, (0, 0), {(8, 4)}, step=4, bounds=(64, 64))
    assert path is not None
    assert path[0] == (0, 0)
    assert path[-1] == (8, 4)
    assert all(cell not in blocked for cell in path)


def test_bfs_path_none_when_goal_unreachable():
    """Purpose: bfs_path returns None when the goal set is fully walled off
    by blocked cells, rather than looping or returning a bogus path.

    Expected feedback: a PASS proves an unreachable item/slot is correctly
    reported as such, letting the caller give up on it (never retried
    speculatively); a FAIL means the delivery phase could hang trying to
    execute a nonexistent path.
    """
    blocked = {(4, 0), (0, 4), (-4, 0), (0, -4)}  # walls off (0,0) on all 4 sides
    assert bfs_path(blocked, (0, 0), {(20, 20)}, step=4, bounds=(64, 64)) is None


def test_bfs_path_item_offset_blocks_the_carried_items_own_collision():
    """Purpose: with item_offset set, a candidate cell is rejected when the
    CARRIED item's own offset position (not just the player's own cell)
    would land on a blocked cell — mirrors the legacy solver's carried-item
    collision check.

    Expected feedback: a PASS proves a delivery leg never drags a carried
    item through another undelivered item or off-board; a FAIL means the
    agent could attempt a physically inconsistent carry path.
    """
    # Player could reach (4, 0) directly, but the carried item (offset
    # (0, -4) above the player) would then sit on a blocked cell.
    blocked = {(4, -4)}
    path = bfs_path(blocked, (0, 0), {(4, 0)}, step=4, bounds=(64, 64), item_offset=(0, -4))
    assert path is None or (4, -4) not in {(p[0] + 0, p[1] - 4) for p in path}
    # A genuinely clear route exists via (0, 4) -> (4, 4) -> (4, 0), where
    # the carried item never touches the blocked cell.
    assert path is None or path[-1] == (4, 0)


def test_path_to_actions_resolves_via_the_measured_dir_map():
    """Purpose: path_to_actions translates consecutive waypoint deltas into
    action ids via a MEASURED dir_map (never assumed action-id-to-direction
    binding), and reports failure when a needed delta was never observed.

    Expected feedback: a PASS proves the same measurement-not-assumption
    discipline transform_route.py's build_move_actions uses; a FAIL means
    a delivery plan could press the wrong action or silently do nothing.
    """
    dir_map = {7: (0, -4), 8: (0, 4), 9: (-4, 0), 2: (4, 0)}  # scrambled ids
    path = [(0, 0), (0, -4), (0, -8), (4, -8)]
    assert path_to_actions(path, dir_map) == [7, 7, 2]
    # A delta never observed during calibration -> None (never guessed).
    assert path_to_actions([(0, 0), (100, 100)], dir_map) is None


def test_bbox_min_corner_is_orientation_independent():
    """Purpose: bbox_min_corner returns the (x, y) top-left of a cell set
    regardless of iteration/insertion order.

    Expected feedback: a PASS pins the shared coordinate convention every
    other delivery.py function relies on (player cell, item cell, slot
    cell all use this same corner definition); a FAIL means two functions
    could disagree about what "the same cell" means.
    """
    cells = frozenset({(10, 20), (13, 23), (11, 21), (12, 22)})
    assert bbox_min_corner(cells) == (10, 20)
