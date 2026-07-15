"""Tests for the WA30 delivery adapter (R56 delivery-kernel rewire,
2026-07-15).

See that module's docstring: WA30 is a pick-carry-drop delivery — a worker
ferries boxes to a goal pad. The adapter detects the worker/boxes/goal roles
from the frame and composes ``plan_delivery`` (min-cost assignment + per-leg
routing) over a coarse logical grid into an ordered pick->deliver chain,
falling back to generic transition-graph exploration otherwise.

These tests pin the role detection and plan composition (the parts the
adapter owns). Note (banked divergence): the generic route-and-interact plan
does NOT model WA30's carry-follow/facing mechanic (a box follows the worker
rather than staying where it was interacted), so the executed chain does not
by itself clear the live level — the graph fallback preserves the prior 0/9
baseline. The kernel is validated independently in test_kernels_paths.py.
"""

from __future__ import annotations

from types import SimpleNamespace

from admorphiq.adapters25.wa30 import Adapter, _logical

_BG = 1


def _grid(h, w, stamps, bg=_BG):
    g = [[bg] * w for _ in range(h)]
    for color, cells in stamps:
        for r, c in cells:
            g[r][c] = color
    return tuple(tuple(row) for row in g)


def _rect(color, r0, c0, r1, c1):
    return (color, [(r, c) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)])


def test_logical_maps_bbox_centre_to_coarse_cell():
    """Purpose: _logical must map a region's bbox centre to the coarse
    logical grid (frame px / 4) the planner runs on.
    Expected feedback: failure means every detected role lands on the wrong
    planning cell, so routes and interactions target the wrong places."""
    assert _logical((36, 32, 39, 35)) == (9, 8)  # centre (37,33) // 4
    assert _logical((49, 32, 51, 35)) == (12, 8)


def test_detect_roles_separates_worker_boxes_and_goal_pad():
    """Purpose: the crux role-detection contract — boxes are the UNIFORM-size
    same-colour class (not merely the most populous colour, which a shared
    sprite-core/pad colour would win), the worker is a singleton mover, and
    the goal pad is the largest remaining region tiled into logical cells.
    This pins the exact bug found live: colour-9 was shared by 3 box cores + a
    large pad border, so 'most populous colour' mis-picked colour-9 as boxes;
    the uniform-size rule picks the true colour-4 boxes.
    Expected feedback: failure means the planner assigns deliveries over the
    wrong cells entirely (cores/pad mistaken for boxes)."""
    regions = [
        {"color": 4, "size": 12, "bbox": (24, 44, 27, 47), "cells": frozenset()},
        {"color": 9, "size": 4, "bbox": (25, 45, 26, 46), "cells": frozenset()},   # box core
        {"color": 4, "size": 12, "bbox": (28, 16, 31, 19), "cells": frozenset()},
        {"color": 9, "size": 28, "bbox": (28, 28, 31, 39), "cells": frozenset()},  # pad border
        {"color": 9, "size": 4, "bbox": (29, 17, 30, 18), "cells": frozenset()},   # box core
        {"color": 2, "size": 20, "bbox": (29, 29, 30, 38), "cells": frozenset()},  # pad interior
        {"color": 4, "size": 12, "bbox": (36, 32, 39, 35), "cells": frozenset()},
        {"color": 9, "size": 4, "bbox": (37, 33, 38, 34), "cells": frozenset()},   # box core
        {"color": 14, "size": 12, "bbox": (49, 32, 51, 35), "cells": frozenset()},  # worker
    ]
    roles = Adapter()._detect_roles(regions)
    assert roles is not None
    worker, boxes, goals = roles
    assert worker == (12, 8)
    assert set(boxes) == {(6, 11), (7, 4), (9, 8)}  # the three colour-4 boxes
    assert len(goals) == 3  # one goal cell per box, on the pad


def test_detect_roles_returns_none_without_a_uniform_box_class():
    """Purpose: with no same-colour, same-size repeated class (nothing that
    reads as a box set), role detection must return None so the adapter falls
    back to graph exploration rather than plan over garbage.
    Expected feedback: failure means the adapter plans a delivery on a board
    that has no detectable delivery structure."""
    regions = [
        {"color": 14, "size": 12, "bbox": (49, 32, 51, 35), "cells": frozenset()},
        {"color": 2, "size": 20, "bbox": (29, 29, 30, 38), "cells": frozenset()},
    ]
    assert Adapter()._detect_roles(regions) is None


def test_build_plan_composes_a_delivery_chain_over_detected_roles():
    """Purpose: end-to-end at the adapter layer — from a live-shaped frame the
    adapter must detect roles and compose a non-empty plan whose interacts
    equal two per box (pick + drop), in the 'plan' phase.
    Expected feedback: failure means the role-detection -> plan_delivery
    wiring is broken (wrong passability, wrong move labels), so the adapter
    never even attempts the composed chain."""
    # Two boxes (colour 4, uniform 4x4), a goal pad (colour 2, largest
    # region), a worker (colour 14 singleton).
    grid = _grid(
        64, 64,
        [
            _rect(4, 20, 20, 23, 23),   # box 1
            _rect(4, 20, 40, 23, 43),   # box 2 (same size -> uniform box class)
            _rect(2, 40, 20, 43, 27),   # goal pad interior (largest region), two cells wide
            _rect(14, 8, 8, 11, 11),    # worker singleton
        ],
    )
    adapter = Adapter()
    adapter._build_plan(grid)
    assert adapter._phase == "plan"
    assert adapter._plan_queue  # a composed chain exists
    assert adapter._plan_queue.count(5) == 4  # pick + drop for each of two boxes


def test_build_plan_falls_back_to_graph_when_roles_undetectable():
    """Purpose: a frame with no delivery structure must send _build_plan to
    the 'graph' phase, preserving the generic-explorer baseline.
    Expected feedback: failure means the adapter would stall on an empty plan
    instead of exploring."""
    grid = _grid(64, 64, [_rect(14, 8, 8, 11, 11)])  # worker only, no boxes
    adapter = Adapter()
    adapter._build_plan(grid)
    assert adapter._phase == "graph"


def test_level_up_and_game_over_reset_the_plan_pipeline():
    """Purpose: a new level restarts the plan pipeline and wipes the fallback
    graph; a GAME_OVER attempt-reset restarts the plan pipeline but KEEPS the
    graph (same board).
    Expected feedback: failure means a stale plan or graph leaks across a
    level/attempt boundary, producing wrong moves from the first frame."""
    adapter = Adapter()
    adapter._phase = "graph"
    adapter._planned = True
    adapter._plan_queue = [1, 5]
    adapter._transitions = [("k0", 1, "k1")]

    adapter._on_level_up(1)
    assert adapter._phase == "plan"
    assert adapter._planned is False
    assert adapter._plan_queue == []
    assert adapter._transitions == []

    adapter._planned = True
    adapter._transitions = [("k0", 1, "k1")]
    action = adapter.choose_action([], SimpleNamespace(state=SimpleNamespace(name="GAME_OVER")))
    assert action.value == 0  # RESET
    assert adapter._planned is False
    assert adapter._transitions == [("k0", 1, "k1")]  # graph kept
