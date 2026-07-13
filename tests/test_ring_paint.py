"""Unit tests for the frame-only RING-PAINT solver (CD82-class efficiency).

These pin the paint capability the world-model agent uses to clear a ring-basket
paint puzzle EFFICIENTLY (CD82 L1: ~8 actions vs the graph fallback's ~2000+):
an 8-position basket ring paints regions of a 10x10 canvas to match a 10x10
target. Every test is env-free on synthetic frames — the capability must be
observation-driven with no game-id / internal reads.
"""

from __future__ import annotations

import numpy as np

from admorphiq.ring_paint import (
    detect_paint_layout,
    nav_path,
    plan_paint,
)

_BG = 5


def _paint_board(target_top: int, target_bot: int, canvas_color: int) -> np.ndarray:
    """A synthetic CD82-L1-shaped board: a lower uniform canvas, a top-left
    two-colour horizontal-split target, and two top swatches (the target colours).
    """
    layer = np.full((64, 64), _BG, dtype=np.int32)
    # target 10x10 at (3,3): top half / bottom half
    layer[3:8, 3:13] = target_top
    layer[8:13, 3:13] = target_bot
    # canvas 10x10 at (27,34), uniform
    layer[34:44, 27:37] = canvas_color
    # top swatches (small blocks) at y~3-5 for each target colour
    layer[3:6, 34:38] = target_top
    layer[3:6, 40:44] = target_bot
    return layer


def test_plan_paint_horizontal_split_paints_only_the_differing_half():
    """Purpose: plan_paint emits ONE launch for a top/bottom split whose top
    already matches the uniform canvas — only the bottom half needs painting
    (the measured CD82 L1: target top-0/bottom-15, canvas all-0 -> launch pos 4).

    Expected feedback: a PASS proves the planner skips already-correct regions
    (efficiency — the whole point of this capability); a FAIL means it would
    over-paint or target the wrong ring position.
    """
    target = np.zeros((10, 10), dtype=np.int32)
    target[5:10, :] = 15  # top 0, bottom 15
    assert plan_paint(target, canvas_start=0) == [(4, 15)]


def test_plan_paint_vertical_split_uses_left_right_positions():
    """Purpose: a left/right split maps to ring positions 6 (left) and 2 (right),
    skipping the half that matches the canvas start colour.

    Expected feedback: a PASS proves the vertical-axis mapping; a FAIL means a
    left/right target would be painted with the wrong (top/bottom) positions.
    """
    target = np.full((10, 10), 8, dtype=np.int32)
    target[:, 5:10] = 9  # left 8, right 9
    assert plan_paint(target, canvas_start=8) == [(2, 9)]


def test_plan_paint_returns_empty_on_non_half_split():
    """Purpose: a target that is not a clean two-colour half-split (e.g. a
    diagonal / multi-band pattern) yields NO plan, so the caller defers to the
    existing path rather than mis-painting.

    Expected feedback: a PASS proves the planner is correctly scoped to the L1
    class and never fires a wrong plan on deeper levels; a FAIL means it could
    regress a board it cannot actually solve.
    """
    target = np.zeros((10, 10), dtype=np.int32)
    for i in range(10):
        target[i, : i + 1] = 15  # diagonal triangle
    assert plan_paint(target, canvas_start=0) == []


def test_detect_paint_layout_reads_target_canvas_swatches_and_plans():
    """Purpose: detect_paint_layout finds the canvas, the top-left target, and
    the swatches on a synthetic board and returns the correct launch plan +
    clickable swatch x positions.

    Expected feedback: a PASS proves the end-to-end frame-only detection that
    lets the agent clear CD82 L1 in ~8 actions; a FAIL means the paint phase
    would never engage (falling back to the ~2000-action brute force).
    """
    layer = _paint_board(target_top=0, target_bot=15, canvas_color=0)
    layout = detect_paint_layout(layer, _BG)
    assert layout is not None
    assert layout.launches == [(4, 15)]
    assert 15 in layout.swatch_x  # the colour we need is clickable


def test_detect_paint_layout_none_without_a_canvas():
    """Purpose: a board with no lower canvas block is not a ring-paint layout.

    Expected feedback: a PASS proves the detector stays dormant on non-paint
    boards (no false engage on other movement+click games); a FAIL means the
    paint phase could hijack an unrelated board.
    """
    layer = np.full((64, 64), _BG, dtype=np.int32)
    layer[3:8, 3:13] = 0
    layer[8:13, 3:13] = 15  # a target-like top-left block but NO canvas
    assert detect_paint_layout(layer, _BG) is None


def test_nav_path_routes_around_the_excluded_centre():
    """Purpose: nav_path returns a valid ACTION1-4 route between ring positions
    that never enters the excluded 3x3 centre.

    Expected feedback: a PASS proves the basket navigation reaches any launch
    position; a FAIL means the executor could stall trying to cross the centre.
    """
    path = nav_path(0, 4)  # top -> bottom, must go around
    assert path and all(a in (1, 2, 3, 4) for a in path)
    # start pos 0 = grid (0,1); walking the path must avoid (1,1).
    pos = (0, 1)
    delta = {1: (-1, 0), 2: (1, 0), 3: (0, -1), 4: (0, 1)}
    for a in path:
        dr, dc = delta[a]
        pos = (pos[0] + dr, pos[1] + dc)
        assert pos != (1, 1)
    assert pos == (2, 1)  # arrived at ring position 4
