"""Unit tests for the frame-only MATCH-TO-ORDER placement capability (R48).

These pin the click-only sort sub-class of the select-and-place ARRANGEMENT
family the world-model agent uses for levels whose goal is "place a pool of
coloured items into slots so the placed order matches a fixed reference order"
(SB26 L1 — a top row of colour frames as the reference plus a bottom row of
matching swatches as the pool; clears when each mid-row spot holds the swatch
matching the reference frame above it, then a verify action confirms). Every
test is env-free on synthetic frames: the capability must be observation-driven
with no game-id / internal reads, so its behaviour is fully exercised by hand-
built layers.
"""

from __future__ import annotations

import numpy as np

from admorphiq.sort_match import (
    MatchLayout,
    detect_match_layout,
    plan_match_placement,
)

_BG = 4


def _layer_with(boxes: list[tuple[int, int, int, int, int]]) -> np.ndarray:
    """Build a 64x64 background frame with coloured rectangles.

    ``boxes`` is a list of (color, r0, c0, r1, c1) inclusive rectangles.
    """
    layer = np.full((64, 64), _BG, dtype=np.int32)
    for color, r0, c0, r1, c1 in boxes:
        layer[r0 : r1 + 1, c0 : c1 + 1] = color
    return layer


def _sb26_l1_layer() -> np.ndarray:
    """A synthetic SB26-L1-shaped layer: top frames [9,14,11,15], bottom pool.

    Top frames at y~2 (cols 18,25,32,39), bottom swatches at y~57 carrying the
    same colour multiset in a scrambled order. Mirrors the measured SB26 L1.
    """
    top = [
        (9, 1, 18, 4, 21),
        (14, 1, 25, 4, 28),
        (11, 1, 32, 4, 35),
        (15, 1, 39, 4, 42),
    ]
    bottom = [
        (14, 56, 17, 60, 21),
        (15, 56, 25, 60, 29),
        (9, 56, 33, 60, 37),
        (11, 56, 41, 60, 45),
    ]
    return _layer_with(top + bottom)


def test_detect_match_layout_reads_reference_and_pool():
    """Purpose: detect_match_layout recovers the reference colour order from the
    top row and maps every reference colour to a bottom-row pool swatch.

    Expected feedback: a PASS proves the frame-only layout reader extracts the
    target order + pickable pool that the placement plan needs; a FAIL means the
    top/bottom band segmentation or colour-coverage test is broken and the sort
    plan would target the wrong cells.
    """
    layout = detect_match_layout(_sb26_l1_layer(), _BG)
    assert layout is not None
    assert [color for _x, color in layout.reference] == [9, 14, 11, 15]
    assert set(layout.pool) == {9, 14, 11, 15}
    # Placement band sits between the top (y~2) and bottom (y~58) rows.
    assert 10 < layout.placement_y < 53


def test_detect_returns_none_when_pool_cannot_supply_reference():
    """Purpose: a layout whose bottom row lacks the top row's colours is NOT a
    match-to-order puzzle and is rejected.

    Expected feedback: a PASS proves the colour-coverage falsifier prevents the
    sort plan from engaging on unrelated click games (no false positive); a FAIL
    means the plan could fire on a non-sort layout and waste the budget.
    """
    layer = _layer_with(
        [
            (9, 1, 18, 4, 21),
            (14, 1, 25, 4, 28),
            # bottom pool carries different colours → cannot supply 9/14
            (6, 56, 17, 60, 21),
            (7, 56, 25, 60, 29),
        ]
    )
    assert detect_match_layout(layer, _BG) is None


def test_detect_returns_none_without_two_rows():
    """Purpose: a frame with no clear top+bottom row pair is not a sort layout.

    Expected feedback: a PASS proves a single-row or empty frame yields None
    (the plan stays dormant); a FAIL means the detector hallucinates a layout
    from insufficient structure.
    """
    layer = _layer_with([(9, 1, 18, 4, 21), (14, 1, 25, 4, 28)])  # top only
    assert detect_match_layout(layer, _BG) is None
    assert detect_match_layout(np.array([], dtype=np.int32), _BG) is None


def test_plan_match_placement_orders_clicks_by_reference():
    """Purpose: the plan clicks each pool swatch then its reference column in
    reference order, and ends with the verify action.

    Expected feedback: a PASS proves the emitted (swatch click, slot click)+
    verify sequence matches the placement protocol that cleared SB26 L1; a FAIL
    means the agent would place swatches in the wrong slots or skip verification.
    """
    layout = MatchLayout(
        reference=[(20, 9), (28, 14), (34, 11), (42, 15)],
        pool={9: (36, 58), 14: (20, 58), 11: (44, 58), 15: (28, 58)},
        placement_y=30,
    )
    plan = plan_match_placement(layout, verify_action=5)
    # 4 placements (2 clicks each) + 1 verify.
    assert len(plan) == 9
    assert plan[-1] == ("simple", 5)
    # First placement targets colour 9: click its swatch, then reference col 20.
    assert plan[0] == ("click", 36, 58)
    assert plan[1] == ("click", 20, 30)
    # Every placement's second click is at a reference column at the mid band.
    slot_clicks = [p for i, p in enumerate(plan[:-1]) if i % 2 == 1]
    assert [c[1] for c in slot_clicks] == [20, 28, 34, 42]
    assert all(c[2] == 30 for c in slot_clicks)
