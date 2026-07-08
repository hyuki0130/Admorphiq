"""Contract tests for goal-conditioned WM planning (R53 / US-6)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import numpy as np

from admorphiq.ewm.forward_model import EWMForwardModel
from admorphiq.graph_frontier_agent import GraphFrontierAgent
from admorphiq.planner.goal import GoalSpec, GoalType


@dataclass
class _StubResult:
    fn: Callable[..., Any]
    train_fit: float


def test_adapter_maps_action_idx_and_reports_train_fit():
    """Purpose: EWMForwardModel must decode a combined action_idx to the
    (action_str, xy) the synthesized fn expects, run it, and report the model's
    train_fit as confidence.

    Expected feedback: pass ⇒ the planner sees correctly-labeled actions and a
    usable confidence; fail ⇒ the world model is queried with wrong actions.
    """
    seen: list[tuple[str, Any]] = []

    def fn(frame: Any, action: str, xy: Any = None) -> Any:
        seen.append((action, xy))
        out = [row[:] for row in frame]
        out[0][0] = 9
        return out

    fwd = EWMForwardModel(fn, train_fit=0.9)
    frame = np.zeros((4, 4), dtype=np.int16)
    nxt, conf = fwd.predict_next_frame(frame, 0)      # idx 0 -> ACTION1
    assert seen[-1] == ("ACTION1", None)
    assert conf == 0.9
    assert nxt[0, 0] == 9
    fwd.predict_next_frame(frame, 5)                   # idx 5 -> ACTION6 click (0,0)
    assert seen[-1][0] == "ACTION6"


def test_adapter_noop_on_sandbox_error():
    """Purpose: a synthesized fn that raises (or returns a wrong shape) must
    degrade to the unchanged input frame, never propagate — one bad rollout
    step cannot crash planning.

    Expected feedback: pass ⇒ planning is robust to bad generations; fail ⇒ a
    single malformed prediction aborts the game loop.
    """
    def bad(frame: Any, action: str, xy: Any = None) -> Any:
        raise ValueError("boom")

    fwd = EWMForwardModel(bad, train_fit=1.0)
    frame = np.zeros((4, 4), dtype=np.int16)
    frame[1, 1] = 3
    nxt, conf = fwd.predict_next_frame(frame, 0)
    assert np.array_equal(nxt, frame)  # no-op
    assert conf == 1.0


def test_planning_selects_goal_maximizing_action(monkeypatch):
    """Purpose: with a confident world model and a concrete goal, the agent must
    pick the candidate action the model predicts moves closest to the goal —
    the whole point of R53 (use the LLM for planning, not pruning).

    Expected feedback: pass ⇒ the agent takes the goal-directed move; fail ⇒
    planning does not steer action choice.
    """
    monkeypatch.setenv("GF_EWM_PLAN", "1")
    monkeypatch.setenv("GF_EWM_PLAN_HORIZON", "1")  # isolate the first-move choice
    agent = GraphFrontierAgent()
    assert agent.ewm_plan is True

    # Goal: MAXIMIZE_OBJECT_COUNT of colour 5. ACTION2 (idx 1) paints a colour-5
    # cell (raises the count); ACTION1 (idx 0) is inert.
    def fn(frame: Any, action: str, xy: Any = None) -> Any:
        out = [row[:] for row in frame]
        if action == "ACTION2":
            out[2][2] = 5
        return out

    agent._ewm_result = _StubResult(fn=fn, train_fit=1.0)
    agent._goal = GoalSpec(goal_type=GoalType.MAXIMIZE_OBJECT_COUNT, color=5)
    frame = np.zeros((8, 8), dtype=np.int16)
    key = agent._ewm_plan_action(frame, simple_ids=[1, 2], action6_ok=False)
    assert key == 2  # ACTION2 (idx 1 -> key 2) is the goal-maximizing move


def test_planning_declines_when_not_confident(monkeypatch):
    """Purpose: below the confidence floor the planner must decline so the agent
    falls back to novelty exploration — planning is ADDITIVE, never a
    low-confidence override.

    Expected feedback: pass ⇒ an untrusted model does not hijack action choice;
    fail ⇒ a weak world model steers the agent on guesses.
    """
    monkeypatch.setenv("GF_EWM_PLAN", "1")
    monkeypatch.setenv("GF_EWM_PLAN_CONF", "0.9")
    agent = GraphFrontierAgent()
    agent._ewm_result = _StubResult(fn=lambda f, a, xy=None: f, train_fit=0.3)  # < 0.9
    agent._goal = GoalSpec(goal_type=GoalType.MAXIMIZE_OBJECT_COUNT, color=5)
    frame = np.zeros((8, 8), dtype=np.int16)
    key = agent._ewm_plan_action(frame, simple_ids=[1, 2], action6_ok=False)
    assert key is None


def test_gf_ewm_plan_off_by_default():
    """Purpose: GF_EWM_PLAN unset must leave the agent in its deployed state —
    no planning, no forced goal activation beyond the existing flags — so the
    shipped card is byte-identical.

    Expected feedback: pass ⇒ default-OFF regression guard holds; fail ⇒ the
    planning hook leaks into deployment.
    """
    agent = GraphFrontierAgent()
    assert agent.ewm_plan is False
    assert agent.ewm_enabled is False
