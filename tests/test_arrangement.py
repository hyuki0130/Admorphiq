"""Unit tests for the multi-entity ARRANGEMENT capability (R47).

These pin the select-and-place primitive the world-model agent uses for levels
whose goal is "assign N controllable pieces to a target configuration, with a
selection action cycling which piece moves" (AR25 L2 — a horizontally-movable
alignment bar plus a pair of shapes that descend together; clears only when the
bar sits at a specific column AND the shapes reach the goal-marker row). Every
test is env-free on synthetic frames: the capability must be observation-driven
with no game-id / internal reads, so its behaviour is fully exercised by hand-
built layers and a learned (action -> per-mode movement) model.
"""

from __future__ import annotations

import numpy as np

from admorphiq.arrangement import (
    ArrangementSim,
    SelectionModel,
    entity_centroids,
    goal_marker_rows,
    learn_selection_modes,
    plan_descend_and_sweep,
)

_BG = 9


def _frame_with(entities: dict[int, list[tuple[int, int, int, int]]]) -> np.ndarray:
    """Build a 64x64 background frame with rectangular coloured entities.

    ``entities`` maps colour -> list of (r0, c0, r1, c1) inclusive boxes.
    """
    layer = np.full((64, 64), _BG, dtype=np.int32)
    for color, boxes in entities.items():
        for r0, c0, r1, c1 in boxes:
            layer[r0 : r1 + 1, c0 : c1 + 1] = color
    return layer


def _ar25_like_start() -> np.ndarray:
    """An AR25-L2-like layout: centre bar (10), two shapes (4 left, 5 right),
    a left-side goal marker (11) low on the board."""
    return _frame_with(
        {
            10: [(10, 36, 52, 38)],  # vertical alignment bar, centre
            4: [(18, 15, 29, 24)],  # left shape
            5: [(18, 45, 29, 54)],  # right shape
            11: [(44, 6, 51, 15)],  # goal marker, lower-left
        }
    )


def test_entity_centroids_filters_hud_and_small() -> None:
    """Purpose: entity_centroids returns the largest sizeable component per colour
    above the HUD band, keyed by colour.

    Expected feedback: pass confirms the abstract arrangement state is read
    cleanly from the frame (one centroid per movable/marker colour); failure means
    the simulator would track noise (single-pixel artefacts / bottom-band timers).
    """
    layer = _ar25_like_start()
    layer[63, 0:30] = 5  # a bottom HUD/timer band of colour 5 (must be ignored)
    layer[0, 0] = 4  # single-pixel artefact (too small)
    cents = entity_centroids(layer, _BG)
    assert set(cents) == {10, 4, 5, 11}
    # The colour-5 entity is the upper shape, not the bottom band.
    assert cents[5][1] < 60


def test_learn_selection_modes_builds_per_mode_maps() -> None:
    """Purpose: learn_selection_modes folds a sequenced probe log into per-mode
    movement maps and derives num_modes from the populated modes.

    Expected feedback: pass confirms the online selection model is learned purely
    from the agent's own (action, before, after) probes; failure means the
    simulator's dynamics would be wrong and every plan would mispredict.
    """
    base = _ar25_like_start()
    # Mode 0: a move (action 3) shifts the bar (10) left by 3px.
    after0 = _frame_with(
        {10: [(10, 33, 52, 35)], 4: [(18, 15, 29, 24)], 5: [(18, 45, 29, 54)], 11: [(44, 6, 51, 15)]}
    )
    # Mode 1 (after toggle 5): a move (action 2) shifts BOTH shapes down 3px.
    after1 = _frame_with(
        {10: [(10, 36, 52, 38)], 4: [(21, 15, 32, 24)], 5: [(21, 45, 32, 54)], 11: [(44, 6, 51, 15)]}
    )
    log = [
        {"action": 3, "before": base, "after": after0},
        {"action": 5, "before": base, "after": base},  # toggle (no movement)
        {"action": 2, "before": base, "after": after1},
    ]
    model = learn_selection_modes(log, _BG, toggle_action=5)
    assert model.toggle_action == 5
    assert model.num_modes == 2
    assert 10 in model.mode_maps[0][3] and model.mode_maps[0][3][10][0] < 0  # bar left
    assert {4, 5} <= set(model.mode_maps[1][2]) and model.mode_maps[1][2][4][1] > 0  # shapes down


def test_selection_model_controllability_split() -> None:
    """Purpose: vertically_controllable (primary group) and horizontally_controllable
    (alignment candidates) are derived correctly from the per-mode maps.

    Expected feedback: pass confirms the planner can separate the shapes (which
    must reach a goal ROW) from the bar (which only slides sideways); failure
    means the descend/sweep roles would be misassigned.
    """
    model = SelectionModel(
        toggle_action=5,
        num_modes=2,
        mode_maps={
            0: {3: {10: (-3, 0)}, 4: {10: (3, 0)}},  # bar: horizontal only
            1: {1: {4: (0, -3), 5: (0, -3)}, 2: {4: (0, 3), 5: (0, 3)}},  # shapes: vertical
        },
    )
    assert model.vertically_controllable() == {4, 5}
    assert 10 in model.horizontally_controllable()
    assert 10 not in model.vertically_controllable()  # bar excluded from primary


def test_arrangement_sim_toggle_and_translate() -> None:
    """Purpose: ArrangementSim cycles the mode on the toggle action and translates
    every entity the active mode's map moves.

    Expected feedback: pass confirms the free simulator the planner expands models
    the mode-gated dynamics correctly; failure means planned sequences would not
    match the real env and no candidate would clear.
    """
    model = SelectionModel(
        toggle_action=5,
        num_modes=2,
        mode_maps={0: {3: {10: (-3, 0)}}, 1: {2: {4: (0, 3), 5: (0, 3)}}},
    )
    sim = ArrangementSim(model)
    cents = {10: (37.0, 31.0), 4: (22.0, 23.0), 5: (52.0, 23.0)}
    mode, c2 = sim.step(0, cents, 3)  # bar left in mode 0
    assert mode == 0 and c2[10] == (34.0, 31.0)
    mode, c3 = sim.step(0, cents, 5)  # toggle
    assert mode == 1 and c3 == cents
    mode, c4 = sim.step(1, cents, 2)  # shapes down in mode 1
    assert c4[4] == (22.0, 26.0) and c4[5] == (52.0, 26.0) and c4[10] == cents[10]


def test_goal_marker_rows_excludes_movables_rarest_first() -> None:
    """Purpose: goal_marker_rows returns static-marker rows, excluding the movable
    entities, rarest colour first.

    Expected feedback: pass confirms the descend target row is the goal marker (not
    a movable piece); failure means the primary group would be navigated to the
    wrong row and never clear.
    """
    layer = _ar25_like_start()
    rows = goal_marker_rows(layer, _BG, exclude_colors={10, 4, 5})
    assert rows  # the colour-11 marker survives
    assert abs(rows[0] - 47.5) < 2.0  # marker centroid row


def test_plan_descend_and_sweep_ar25_like() -> None:
    """Purpose: plan_descend_and_sweep produces (a) a descend plan that toggles to
    the shape mode and moves the primary group toward the goal-marker row, and (b)
    a non-empty alignment sweep whose first plan steps the bar TOWARD the marker.

    Expected feedback: pass confirms the two-stage AR25-class plan (descend once,
    then sweep the alignment column) is generated from the learned model + frame;
    failure means the agent could not assemble the select-and-place sequence that
    clears the level.
    """
    layer = _ar25_like_start()
    model = SelectionModel(
        toggle_action=5,
        num_modes=2,
        mode_maps={
            0: {3: {10: (-3, 0), 4: (-6, 0)}, 4: {10: (3, 0), 4: (6, 0)}},
            1: {1: {4: (0, -3), 5: (0, -3)}, 2: {4: (0, 3), 5: (0, 3)}},
        },
    )
    descend, sweep = plan_descend_and_sweep(layer, _BG, model)
    assert descend is not None and descend  # a real descend plan
    assert 5 in descend  # toggles into the shape (mode 1) movement
    assert descend.count(2) >= 1  # moves the shapes DOWN toward the marker row
    assert sweep  # an alignment sweep exists (separate bar entity)
    # The first sweep plan enters the bar mode and steps it; bar mode is 0, so the
    # entry from the post-descend mode (1) is one toggle, then bar moves.
    first = sweep[0]
    assert 5 in first  # toggles into the bar mode
    assert any(a in (3, 4) for a in first)  # then steps the bar sideways


def test_plan_descend_and_sweep_no_arrangement_when_no_vertical_primary() -> None:
    """Purpose: when no entity is vertically controllable (not an arrangement
    level), plan_descend_and_sweep returns (None, []).

    Expected feedback: pass confirms the capability cleanly declines non-arrangement
    levels so the agent falls back to its normal pipeline; failure means it would
    waste budget on a select-and-place plan that cannot apply.
    """
    layer = _ar25_like_start()
    model = SelectionModel(
        toggle_action=5,
        num_modes=2,
        mode_maps={0: {3: {10: (-3, 0)}, 4: {10: (3, 0)}}},  # only horizontal movement
    )
    descend, sweep = plan_descend_and_sweep(layer, _BG, model)
    assert descend is None and sweep == []
