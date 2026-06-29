"""Unit tests for the object-centric ONLINE world-model agent (R28).

These pin the four stages the general (test-time-learning) path is built on,
each tested env-free and deterministically: object segmentation, the online
EffectModel update (per-action change probability + player/direction inference),
goal inference (navigate / interact / explore), and the navigation planner
(shortest path through the learned dynamics). The whole point of this agent is
that nothing is learned from public gold — it learns per game from its own
probes — so these tests exercise that learning on synthetic frames, never a
trained checkpoint.

One optional slow live-env smoke is skipped unless ``WM_SMOKE=1``.
"""

from __future__ import annotations

import os

import numpy as np
import pytest

from admorphiq.world_model_agent import (
    EffectModel,
    Goal,
    WorldModelAgent,
    infer_goal,
    plan_interaction,
    plan_navigation,
    segment_objects,
)


def _layer(h: int = 8, w: int = 8, bg: int = 0) -> np.ndarray:
    """A background-filled int layer of shape (h, w)."""
    return np.full((h, w), bg, dtype=np.int32)


def _block(layer: np.ndarray, color: int, r0: int, c0: int, size: int = 2) -> np.ndarray:
    """Return a copy of ``layer`` with a ``size``x``size`` ``color`` block placed."""
    out = layer.copy()
    out[r0 : r0 + size, c0 : c0 + size] = color
    return out


class _FakeState:
    def __init__(self, name: str) -> None:
        self.name = name


class _FakeObs:
    """Minimal stand-in for the arcengine observation the harness passes."""

    def __init__(self, layer: np.ndarray, avail: list[int], state: str = "PLAYING", levels: int = 0) -> None:
        self.frame = [layer]
        self.available_actions = avail
        self.state = _FakeState(state)
        self.levels_completed = levels


# ── Stage (a): perception → objects ──────────────────────────────────────────


def test_segment_objects_extracts_nonbackground_components():
    """Purpose: object segmentation returns one component per distinct
    non-background colour blob, with its colour and centroid.

    Expected feedback: pass means the perception layer sees the right entities;
    a fail means every downstream stage (player id, goal, planning) keys off a
    wrong object set.
    """
    layer = _block(_block(_layer(), color=3, r0=1, c0=1), color=5, r0=5, c0=5)
    objs = segment_objects(layer, background=0)
    colors = sorted(o["color"] for o in objs)
    assert colors == [3, 5]
    by_color = {o["color"]: o for o in objs}
    assert by_color[3]["size"] == 4
    assert by_color[3]["cx"] == pytest.approx(1.5)
    assert by_color[3]["cy"] == pytest.approx(1.5)


# ── Stage (b): online world model ────────────────────────────────────────────


def test_effect_model_change_prob_reflects_observed_changes():
    """Purpose: the online change model raises P(change|action) for actions that
    changed the frame and lowers it for no-ops, with a neutral prior for untried.

    Expected feedback: pass means the agent can rank actions by learned
    effectiveness; a fail means greedy interaction would waste budget on dead
    actions (which the squared-efficiency metric punishes).
    """
    model = EffectModel()
    before = _layer()
    model.set_background(before)
    # Action 1: a true no-op (frame unchanged) observed twice.
    model.observe(1, None, before, before, level_up=False)
    model.observe(1, None, before, before, level_up=False)
    # Action 2: changed the frame once.
    after = _block(before, color=4, r0=2, c0=2)
    model.observe(2, None, before, after, level_up=False)

    assert model.change_prob(1) < 0.5  # no-op action de-prioritised
    assert model.change_prob(2) > 0.5  # frame-changer prioritised
    assert model.change_prob(99) == pytest.approx(0.5)  # untried → neutral prior


def test_effect_model_learns_player_and_direction_from_probes():
    """Purpose: from movement probes the model infers the player colour and the
    per-action pixel shift (the learned dynamics the planner simulates).

    Expected feedback: pass means online perception identifies the controllable
    object and its action→shift map without any gold; a fail means navigation
    planning has no dynamics to search over.
    """
    model = EffectModel()
    base = _block(_layer(), color=7, r0=2, c0=2)  # player colour 7, 2x2 block
    model.set_background(base)
    # Action 3 shifts the player +2 columns (right); action 4 shifts +2 rows.
    right = _block(_layer(), color=7, r0=2, c0=4)
    down = _block(_layer(), color=7, r0=4, c0=2)
    model.observe(3, None, base, right, level_up=False)
    model.observe(4, None, base, down, level_up=False)

    assert model.player_color == 7
    assert model.predict_player_shift(3) == (2, 0)
    assert model.predict_player_shift(4) == (0, 2)
    # Quantised unit steps for the planner: (d_col, d_row).
    steps = model.step_dirs()
    assert steps[3] == (1, 0)
    assert steps[4] == (0, 1)


def test_effect_model_records_responsive_clicks_and_completion_colors():
    """Purpose: ACTION6 responsiveness is learned per cell, and the colour set
    that changed at a level completion is captured as the goal-correlation signal.

    Expected feedback: pass means interaction planning can target cells that
    actually do something and later levels can prefer the completion-correlated
    colour; a fail means clicks are blind and goal inference loses its strongest
    cue.
    """
    model = EffectModel()
    before = _layer()
    model.set_background(before)
    # A responsive click at (4, 4) that flips colour 6 into the frame, and which
    # coincides with a level completion.
    after = _block(before, color=6, r0=4, c0=4, size=1)
    model.observe(6, (4, 4), before, after, level_up=True)
    # A dead click that changed nothing.
    model.observe(6, (1, 1), before, before, level_up=False)

    assert model.responsive_clicks() == [(4, 4)]
    assert 6 in model.completion_target_colors()


# ── Stage (c): goal inference ─────────────────────────────────────────────────


def test_infer_goal_navigate_when_player_and_goal_present():
    """Purpose: with a learned player + a distinct goal region, the goal is
    NAVIGATE (the highest-value, most efficient plan kind).

    Expected feedback: pass means the agent routes movement games to BFS
    navigation; a fail means it would fall back to slow interaction.
    """
    model = EffectModel()
    base = _block(_layer(), color=7, r0=2, c0=2)
    model.set_background(base)
    model.observe(3, None, base, _block(_layer(), color=7, r0=2, c0=4), level_up=False)
    # Current frame: player (7) + a rare goal marker (5).
    layer = _block(_block(_layer(), color=7, r0=2, c0=2), color=5, r0=2, c0=6, size=1)
    # size-1 marker is below the goal-size floor; use a 2x2 marker instead.
    layer = _block(_block(_layer(), color=7, r0=2, c0=2), color=5, r0=5, c0=5)
    goal = infer_goal(layer, model)
    assert goal.kind == "navigate"


def test_infer_goal_interact_when_clicks_responsive_no_player():
    """Purpose: with no controllable player but observed responsive clicks, the
    goal is INTERACT.

    Expected feedback: pass means click/toggle games are routed to greedy
    interaction; a fail means the agent wrongly attempts navigation or idles.
    """
    model = EffectModel()
    before = _layer()
    model.set_background(before)
    after = _block(before, color=6, r0=4, c0=4, size=1)
    model.observe(6, (4, 4), before, after, level_up=False)
    goal = infer_goal(before, model)
    assert goal.kind == "interact"


def test_infer_goal_explore_when_nothing_learned():
    """Purpose: a fresh model with no player, no responsive clicks, no
    high-change action infers EXPLORE.

    Expected feedback: pass means the agent has a disciplined fallback instead
    of committing to a non-existent plan; a fail means it could dead-lock.
    """
    model = EffectModel()
    layer = _layer()
    model.set_background(layer)
    goal = infer_goal(layer, model)
    assert goal.kind == "explore"


# ── Stage (d): search-based planning ──────────────────────────────────────────


def test_plan_navigation_returns_shortest_path_in_learned_model():
    """Purpose: navigation planning returns the SHORTEST learned-action sequence
    from the player to the goal over the learned dynamics.

    Expected feedback: pass means the planner produces near-human-length plans
    (the squared-efficiency metric's whole requirement); a fail means either no
    plan or a wasteful one.
    """
    model = EffectModel()
    model.background = 0
    model.player_color = 7
    # Directly install a learned unit-step dynamics (cell size 1).
    model.move_map = {3: (1, 0), 2: (-1, 0), 4: (0, 1), 1: (0, -1)}
    # Open corridor on row 2: a 1x3 player bar (cols 1-3) and a vertical 3-tall
    # goal bar at col 9 (so the cell left of the goal is open background, not
    # goal-coloured wall). Both meet the min object/goal sizes.
    layer = _layer(5, 12)
    layer[2, 1:4] = 7  # player bar, centroid col 2
    layer[1:4, 9] = 5  # goal bar, centroid (row 2, col 9)
    plan = plan_navigation(layer, model, Goal("navigate", target_color=5))
    # Shortest path from player centroid (row 2, col 2) to the goal (row 2,
    # col 9) is seven steps to the right (action 3).
    assert plan == [3, 3, 3, 3, 3, 3, 3]


def test_plan_navigation_empty_without_player_or_dynamics():
    """Purpose: navigation planning declines (empty plan) when there is no
    player colour or no learned move map.

    Expected feedback: pass means the agent will correctly fall back to
    interaction rather than crash or fabricate a plan; a fail means a contract
    violation feeding garbage into the executor.
    """
    model = EffectModel()
    model.background = 0
    layer = _block(_layer(), color=5, r0=1, c0=1)
    assert plan_navigation(layer, model, Goal("navigate")) == []


def test_plan_interaction_orders_responsive_cells_first():
    """Purpose: interaction candidates are ordered with observed-responsive
    cells ahead of merely-plausible cluster centroids.

    Expected feedback: pass means greedy interaction spends early budget on
    cells already known to do something; a fail means it wastes the squared-
    efficiency budget probing dead cells first.
    """
    model = EffectModel()
    before = _layer(16, 16)
    model.set_background(before)
    after = _block(before, color=6, r0=10, c0=10, size=1)
    model.observe(6, (10, 10), before, after, level_up=False)
    # A layer with an unrelated cluster the planner could also click.
    layer = _block(before, color=4, r0=2, c0=2)
    cands = plan_interaction(layer, model)
    assert cands[0] == ("c", 10, 10)


# ── Agent FSM / harness contract ──────────────────────────────────────────────


def test_agent_choose_action_returns_gameaction_and_counts():
    """Purpose: the agent honours the harness contract — choose_action returns a
    GameAction and advances the internal action counter exactly once per call.

    Expected feedback: pass means the agent plugs into score_efficiency's
    agent-agnostic loop; a fail means the run loop breaks or the budget gate
    miscounts.
    """
    from arcengine import GameAction

    agent = WorldModelAgent()
    obs = _FakeObs(_block(_layer(), color=7, r0=2, c0=2), avail=[1, 2, 3, 4])
    assert agent.is_done([], obs) is False
    action = agent.choose_action([], obs)
    assert isinstance(action, GameAction)
    assert agent._action_count == 1


def test_agent_is_done_on_win_and_budget():
    """Purpose: is_done stops on WIN (the biggest efficiency lever) and on the
    action budget.

    Expected feedback: pass means the agent never grinds past a win or past its
    cap; a fail means wasted actions that tank the efficiency ratio.
    """
    agent = WorldModelAgent()
    win_obs = _FakeObs(_layer(), avail=[1], state="WIN")
    assert agent.is_done([], win_obs) is True
    agent._action_count = agent.MAX_ACTIONS
    assert agent.is_done([], _FakeObs(_layer(), avail=[1])) is True


def test_agent_learns_online_across_calls():
    """Purpose: driving the agent through a move probe then its credit on the
    next call populates the GAME-scope EffectModel (genuine online learning).

    Expected feedback: pass means the agent's model improves from its own
    interaction within a game (the property that transfers to unseen games); a
    fail means the credit/observe wiring is broken and nothing is learned.
    """
    agent = WorldModelAgent()
    base = _block(_layer(), color=7, r0=2, c0=2)
    # Call 1: agent issues its first probe (a movement action) and records it.
    agent.choose_action([], _FakeObs(base, avail=[1, 2, 3, 4]))
    assert agent._pending is not None
    probed_aid = agent._pending["action_id"]
    # Call 2: hand back a frame where the player translated under that probe.
    moved = _block(_layer(), color=7, r0=2, c0=4)
    agent.choose_action([], _FakeObs(moved, avail=[1, 2, 3, 4]))
    # The model has now learned the player colour and a shift for the probed action.
    assert agent.model.player_color == 7
    assert probed_aid in agent.model.move_map


def test_agent_action6_click_carries_xy_data():
    """Purpose: ACTION6 emissions carry clamped (x, y) data so the harness can
    forward the coordinate to env.step.

    Expected feedback: pass means click games receive valid coordinates; a fail
    means ACTION6 steps are malformed and the click is lost.
    """
    agent = WorldModelAgent()
    action = agent._emit_click(100, -5)  # out-of-range → clamped to [0, 63]
    data = action.action_data
    assert (data.x, data.y) == (63, 0)


# ── optional slow live-env smoke (skipped by default) ─────────────────────────


@pytest.mark.skipif(os.environ.get("WM_SMOKE") != "1", reason="slow live-env smoke; set WM_SMOKE=1")
def test_smoke_runs_one_game_offline():
    """Purpose: end-to-end sanity that the agent drives a real offline game
    without crashing (clears are not required for this prototype).

    Expected feedback: pass means the full perceive→learn→plan→act loop runs
    against the real arcengine interface; a fail flags an integration break.
    """
    from arc_agi import Arcade, OperationMode
    from arcengine import GameState

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    env_info = arcade.get_environments()[0]
    env = arcade.make(env_info.game_id)
    obs = env.observation_space
    agent = WorldModelAgent()
    for _ in range(200):
        if agent.is_done([], obs):
            break
        action = agent.choose_action([], obs)
        obs = env.step(action, data=action.action_data.model_dump()) if action.is_complex() else env.step(action)
        if obs is None or obs.state in (GameState.WIN, GameState.GAME_OVER):
            break
    assert agent._action_count > 0
