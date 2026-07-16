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

from admorphiq.adapters25.wa30 import (
    Adapter,
    _logical,
    _multiagent_layer,
    _parse_state,
    _search_plan,
    _snap,
    _Wa30Sim,
)

_BG = 1

# The canonical WA30 L1 layout (decoded from the game source; the numbers match
# what the frame parser recovers from the live render). One worker, one
# autonomous colour-12 agent, five boxes, a 6-slot goal pad, 70-step budget.
_L1_WORKER = (12, 8)
_L1_BOXES = [(36, 28), (40, 20), (44, 40), (48, 24), (48, 32)]
_L1_AUTOS = [(24, 36)]
_L1_GOAL = {(x, y) for x in range(12, 20) for y in range(28, 40)}
_L1_STATE = {"worker": _L1_WORKER, "boxes": _L1_BOXES, "autos": _L1_AUTOS, "goal": _L1_GOAL}


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


# ── L1 cooperative-delivery solver (faithful simulator + search) ─────────────


def _render_l1_grid():
    """A synthetic 64x64 grid rendering the canonical L1 sprites the way the
    engine's top layer does: colour-12 auto (4x4), colour-14 worker (a 3-row
    block one row below the sprite top), colour-9 box cores (2x2 one px inside a
    4x4), and the colour-2 goal-pad interior (the pad bbox minus its 1-px ring)."""
    g = [[_BG] * 64 for _ in range(64)]
    ax, ay = _L1_AUTOS[0]
    for r in range(ay, ay + 4):
        for c in range(ax, ax + 4):
            g[r][c] = 12
    wx, wy = _L1_WORKER
    for r in range(wy + 1, wy + 4):  # colour-14 occupies rows y+1..y+3 (row y is padding)
        for c in range(wx, wx + 4):
            g[r][c] = 14
    for bx, by in _L1_BOXES:
        for r in range(by + 1, by + 3):  # 2x2 core one px inside the 4x4 box
            for c in range(bx + 1, bx + 3):
                g[r][c] = 9
    for r in range(29, 39):  # goal interior = pad bbox (28..39, 12..19) minus the ring
        for c in range(13, 19):
            g[r][c] = 2
    return tuple(tuple(row) for row in g)


def test_wa30_sim_search_finds_a_winning_open_loop_sequence():
    """Purpose: the crux of the L1 build — searching macro-plans in the faithful
    simulator must return a player action sequence that, replayed OPEN-LOOP in a
    fresh simulator, reaches the all-boxes-on-goal win within the 70-step budget.
    Expected feedback: failure means either the search or the simulated
    cooperation is broken, so L1 cannot clear and wa30 regresses to 1/9."""
    seq = _search_plan(_L1_STATE)
    assert seq is not None
    assert len(seq) <= 70  # fits the L1 StepCounter
    sim = _Wa30Sim(_L1_WORKER, _L1_BOXES, _L1_AUTOS, _L1_GOAL, steps=len(seq) + 8)
    won = False
    for a in seq:
        sim.player(a)
        if sim.won():
            won = True
            break
    assert won


def test_wa30_sim_win_requires_every_box_on_goal_and_not_carried():
    """Purpose: pin the win predicate — a box sitting on a goal cell but still
    CARRIED does not count (it counts only once dropped), matching the engine's
    ymzfopzgbq. Expected feedback: failure means the search could accept a false
    'win' where the auto agent is mid-carry, producing sequences that lose live."""
    sim = _Wa30Sim((0, 0), [(12, 28)], [], _L1_GOAL, steps=10)
    assert sim.won()  # the single box is on a goal cell and uncarried
    sim2 = _Wa30Sim((8, 28), [(12, 28)], [], _L1_GOAL, steps=10)
    sim2.wrot = 90  # face right (+x): the box at (12,28) is one cell ahead of (8,28)
    sim2.player(5)  # pick it up — now on-goal BUT carried
    assert not sim2.won()


def test_wa30_parse_state_recovers_the_l1_layout_from_pixels():
    """Purpose: the frame parser must recover the exact worker/boxes/auto/goal
    from a rendered L1 frame (snapped to the 4-grid), so the simulator is seeded
    correctly. Expected feedback: failure means the sim starts from a wrong state
    and the searched sequence desyncs on the real board."""
    grid = _render_l1_grid()
    st = _parse_state(grid)
    assert st is not None
    assert st["worker"] == _L1_WORKER
    assert st["autos"] == _L1_AUTOS
    assert sorted(st["boxes"]) == sorted(_L1_BOXES)
    assert st["goal"] == _L1_GOAL


def test_wa30_parse_state_gate_returns_none_without_autonomous_agent():
    """Purpose: the L0-vs-L1 gate — a board with no colour-12 autonomous agent
    must parse to None so the adapter keeps the byte-identical L0 carry-plan
    path. Expected feedback: failure means the L1 simulator path would engage on
    L0 and could disturb the super-human L0 clear."""
    grid = _render_l1_grid()
    no_auto = tuple(tuple(_BG if v == 12 else v for v in row) for row in grid)
    assert _parse_state(no_auto) is None


def test_wa30_multiagent_layer_picks_the_layer_holding_the_agent():
    """Purpose: WA30 renders on two layers and only the top one carries the
    colour-12 agent + goal interior; the gate must select that layer regardless
    of index. Expected feedback: failure means the adapter reads the base layer
    (no agent) and never engages the L1 solver."""
    base = tuple(tuple(_BG for _ in range(4)) for _ in range(4))
    top = tuple(tuple(12 if (r, c) == (0, 0) else _BG for c in range(4)) for r in range(4))
    frame = SimpleNamespace(frame=[base, top])
    assert _multiagent_layer(frame) == top
    assert _multiagent_layer(SimpleNamespace(frame=[base, base])) is None


def test_wa30_snap_is_rotation_independent_on_the_worker_block():
    """Purpose: the worker sprite's padding row moves to a different edge as it
    turns, shifting the colour-14 block's raw min-row ±1; snapping to the 4-grid
    must recover the same top-left for both renderings. Expected feedback:
    failure means the per-step verification sees a phantom divergence and
    abandons a valid open-loop plan to the graph fallback."""
    # padding at top: colour-14 rows 13..15 -> min row 13; padding at bottom: rows 12..14 -> min 12
    assert _snap(13) == 12
    assert _snap(12) == 12
    assert _snap(min([13, 14, 15])) == _snap(min([12, 13, 14])) == 12
