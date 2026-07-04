"""Tests for the R33 goal-planning integration into OnlineRLAgent.

These pin the regression guard (default RL_GOAL_PLAN=0 => byte-identical card:
no forward model, no goal, planning branch never taken, counters stay 0), the
presence of the fwd_planned/fwd_fallback counters, and that enabling the knob
actually builds the forward model and routes action selection through the
planner. No Ollama call is made (RL_GOAL_LLM stays off => heuristic goal).
"""

from __future__ import annotations

import numpy as np
import pytest

from admorphiq.online_rl_agent import OnlineRLAgent


class _Action:
    def __init__(self, value: int) -> None:
        self.value = value


class _State:
    def __init__(self, name: str) -> None:
        self.name = name


class _Obs:
    def __init__(
        self,
        frame: np.ndarray,
        levels: int = 0,
        state: str = "NOT_FINISHED",
        avail: tuple[int, ...] = (1, 2, 3, 4),
    ) -> None:
        self.frame = [frame.tolist()]
        self.levels_completed = levels
        self.state = _State(state)
        self.available_actions = [_Action(a) for a in avail]


def _frame(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.integers(0, 16, size=(64, 64), dtype=np.int64)


def test_default_goal_plan_off_is_byte_identical_setup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Purpose: with RL_GOAL_PLAN unset (default 0), the agent builds NO forward
    model, sets NO goal, and never enters the planning branch — the regression
    guard that R33 does not change the deployed card.

    Expected feedback: pass => goal planning is truly opt-in and the shipped
    behaviour is unchanged; fail => R33 silently altered the default agent.
    """
    monkeypatch.delenv("RL_GOAL_PLAN", raising=False)
    agent = OnlineRLAgent(warmstart=False, device="cpu", seed=0)
    assert agent.GOAL_PLAN == 0
    assert agent.forward_model is None
    assert agent.forward_opt is None
    assert agent._goal is None
    assert agent._llm_call is None
    # Drive several steps; the planning branch must never fire.
    for i in range(6):
        agent.choose_action([], _Obs(_frame(i), levels=0))
    assert agent.fwd_planned == 0
    assert agent.fwd_fallback == 0


def test_fwd_counters_present_and_zero_initialised() -> None:
    """Purpose: the fwd_planned / fwd_fallback diagnostic counters must exist and
    start at 0 regardless of the knob.

    Expected feedback: pass => post-run diagnosis can read planner vs fallback
    pick counts; fail => the counters are missing (measurement discipline gap).
    """
    agent = OnlineRLAgent(warmstart=False, device="cpu", seed=0)
    assert agent.fwd_planned == 0
    assert agent.fwd_fallback == 0


def test_two_default_agents_same_seed_identical_actions(monkeypatch: pytest.MonkeyPatch) -> None:
    """Purpose: default-config determinism is preserved — two seeded agents given
    the same observations emit the same action sequence (byte-identical decode).

    Expected feedback: pass => R33 did not perturb the seeded exploration path;
    fail => an unguarded R33 code path changed default action selection.
    """
    monkeypatch.delenv("RL_GOAL_PLAN", raising=False)
    frames = [_frame(i) for i in range(5)]

    def run() -> list[int]:
        agent = OnlineRLAgent(warmstart=False, device="cpu", seed=42)
        picks = []
        for f in frames:
            a = agent.choose_action([], _Obs(f, levels=0))
            picks.append(getattr(a, "value", None))
        return picks

    assert run() == run()


def test_goal_plan_on_builds_forward_model_and_uses_planner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Purpose: RL_GOAL_PLAN=1 must build the forward model and, once the goal is
    inferred, route action picks through the planner (fwd_planned or fwd_fallback
    advances) — never touching Ollama (RL_GOAL_LLM off => heuristic goal).

    Expected feedback: pass => the knob wires the whole goal path end-to-end
    with the heuristic goal; fail => enabling planning is inert or crashes.
    """
    monkeypatch.setenv("RL_GOAL_PLAN", "1")
    monkeypatch.delenv("RL_GOAL_LLM", raising=False)
    # Infer the goal quickly so planning engages within the test's step budget.
    monkeypatch.setenv("RL_GOAL_CONF_FLOOR", "0.0")  # trust the untrained model so a plan fires
    agent = OnlineRLAgent(warmstart=False, device="cpu", seed=0)
    agent.GOAL_INFER_AFTER = 3
    assert agent.forward_model is not None
    assert agent.forward_opt is not None

    # Alternate distinct frames so probes register changes and the buffer fills.
    for i in range(12):
        f = _frame(i % 4 + 100)
        agent.choose_action([], _Obs(f, levels=0, avail=(1, 2, 3, 4, 6)))

    assert agent._goal is not None, "goal should be inferred after probing"
    assert (agent.fwd_planned + agent.fwd_fallback) > 0, "planner path must be exercised"
