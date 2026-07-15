"""Tests for the CN04 connector-marker arrangement adapter (R56, 2026-07-15).

CN04 is a rigid-arrangement puzzle (see the adapter module docstring): the
active sprite (rendered colour 0) is rotated (ACTION5) and translated
(ACTION1-4) so its colour-8 connector stubs coincide with another sprite's
stubs, which then recolour to 3; the level wins when every stub is satisfied.
These tests pin the load-bearing perception and control contracts:

  * row-0 HUD masking (the step bar is colour 0/4 and must not read as body);
  * shape fingerprinting (drives whether the adapter rotates);
  * distance-hill-climb pairing cost (drives which unit move it takes);
  * target/marker attribution by body proximity (mine vs target);
  * the wrong-chirality RESET (a full coincidence with no WIN retries the
    opposite 180-degree orientation, since the win pairs by a hidden colour).
"""

from __future__ import annotations

from types import SimpleNamespace

from admorphiq.adapters25.cn04 import Adapter, _mask_hud, _sign


def _grid(size: int, bg: int) -> list[list[int]]:
    return [[bg] * size for _ in range(size)]


def _stamp(grid: list[list[int]], r0: int, c0: int, r1: int, c1: int, colour: int) -> None:
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            grid[r][c] = colour


def _frame(grid: list[list[int]], levels: int = 0, state: str = "NOT_FINISHED") -> SimpleNamespace:
    return SimpleNamespace(
        frame=[[list(row) for row in grid]],
        state=SimpleNamespace(name=state),
        available_actions=[1, 2, 3, 4, 5, 6],
        levels_completed=levels,
    )


def test_mask_hud_blanks_only_row_zero():
    """Purpose: pin that HUD masking replaces the top scanline (the colour-0/4
    step-countdown bar) with background and leaves every other row untouched.
    Expected feedback: failure means the depleting step bar's colour-0 pixels
    leak into the 'active sprite = colour 0' reading, corrupting the body
    centroid the whole controller is built on."""
    grid = tuple(tuple(row) for row in _grid(8, bg=7))
    dirty = list(list(row) for row in grid)
    dirty[0] = [0, 0, 4, 4, 0, 0, 4, 4]  # a step-bar-like top row
    masked = _mask_hud(tuple(tuple(r) for r in dirty), bg=7)
    assert masked[0] == (7,) * 8  # row 0 fully background
    assert masked[1:] == grid[1:]  # every other row identical


def test_sign_is_three_valued():
    """Purpose: the direction-sign helper must return exactly -1/0/+1 so
    measured move directions and residuals compare cleanly.
    Expected feedback: failure means direction matching (_move_for) could pick
    the wrong axis or fail to match a measured move."""
    assert (_sign(-5), _sign(0), _sign(9)) == (-1, 0, 1)


def test_rel_shape_is_translation_invariant_but_orientation_sensitive():
    """Purpose: the shape fingerprint must be equal for two marker sets that
    differ only by translation (so a pure translate is recognised and the
    adapter stops rotating) and UNEQUAL for a horizontal vs a vertical pair
    (so a mismatched orientation triggers a rotation). This is the single
    decision that gates ACTION5 vs translation.
    Expected feedback: failure means the adapter either rotates forever
    (never recognising a match) or never rotates (never fixing a genuine
    orientation mismatch), both of which strand every level."""
    ad = Adapter()
    cell = 3
    horiz_a = [(30, 15), (30, 21)]  # same row, 2 cells apart
    horiz_b = [(9, 6), (9, 12)]  # a pure translate of horiz_a
    vert = [(36, 39), (42, 39)]  # same col, 2 cells apart
    assert ad._rel_shape(horiz_a, cell) == ad._rel_shape(horiz_b, cell)
    assert ad._rel_shape(horiz_a, cell) != ad._rel_shape(vert, cell)


def test_pair_cost_scores_a_shifted_sorted_pairing():
    """Purpose: the hill-climb cost is the total Manhattan distance of the
    sorted marker->target pairing under a candidate move delta; a delta that
    closes the gap must score lower than no move.
    Expected feedback: failure means _translate_step can't tell an
    improving move from a worsening one, reproducing the oscillation that a
    rounded-centroid step caused before this cost replaced it."""
    ad = Adapter()
    mine = [(10, 10), (16, 10)]
    target = [(10, 13), (16, 13)]  # 3 px (one cell) to the right of mine
    assert ad._pair_cost(mine, target, (0, 0)) == 6  # 3 + 3
    assert ad._pair_cost(mine, target, (0, 3)) == 0  # exact overlap after the move


def test_lock_targets_splits_markers_by_body_proximity():
    """Purpose: at the first clean sighting, colour-8 stubs hugging the active
    body (mine) must be separated from the distant stubs of another sprite
    (targets), and only the distant ones stored as targets. The bbox-edge
    distance (not the body centroid) is what makes this clean for a large
    hollow body.
    Expected feedback: failure means the adapter mistakes its own markers for
    targets (or vice versa) and either never has a goal or aims at itself."""
    grid = _grid(40, bg=7)
    _stamp(grid, 5, 5, 12, 12, 0)  # active body (hollow-ish is fine; solid here)
    _stamp(grid, 13, 5, 13, 6, 8)  # my stub, one row under the body edge
    _stamp(grid, 13, 10, 13, 11, 8)  # my second stub
    _stamp(grid, 30, 30, 30, 31, 8)  # a distant sprite's stub (target)
    _stamp(grid, 34, 30, 34, 31, 8)  # its second stub (target)
    grid_t = tuple(tuple(row) for row in grid)

    from admorphiq.kernels import find_regions

    regions = find_regions(grid_t, background=7)
    ad = Adapter()
    ad._lock_targets(regions)
    assert ad._targets_locked
    # Only the two distant stubs are targets; both my stubs are excluded.
    assert len(ad._targets) == 2
    assert all(r >= 25 for r, _c in ad._targets)


def test_full_coincidence_without_win_triggers_chirality_reset():
    """Purpose: the win pairs markers by a hidden original colour the frame
    can't show, so a geometric coincidence recolours every stub to 3 yet may
    not win. When that happens (oriented, zero colour-8 left, colour-3
    present, no WIN state) the adapter must RESET and queue two extra
    pre-rotations to try the opposite chirality.
    Expected feedback: failure means the adapter declares victory on a
    coincidence that didn't actually win, or gets stuck on the wrong
    chirality forever -- the exact trap measured on level 1 (rot=1 coincides
    but only rot=3 wins)."""
    ad = Adapter()
    ad._levels_seen = 0  # suppress the level-up reset so our hand-set state stays
    ad._targets_locked = True
    ad._targets = [(20, 20), (24, 20)]
    ad._oriented = True
    ad._cell_px = 3
    ad._dir = {1: (-1, 0), 2: (1, 0), 3: (0, -1), 4: (0, 1)}

    grid = _grid(40, bg=7)
    _stamp(grid, 5, 5, 10, 10, 0)  # an active body still on the board
    _stamp(grid, 20, 20, 20, 20, 3)  # a satisfied (coincided) stub
    _stamp(grid, 24, 20, 24, 20, 3)  # the other satisfied stub -- NO colour 8 left
    action = ad.choose_action([], _frame(grid))

    assert action == __import__("arcengine").GameAction.RESET
    assert ad._pre_rot_remaining == 2
    assert ad._attempt == 1
