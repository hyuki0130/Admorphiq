"""Offline tests for the UnifiedAgent retry loop (harness/loop.py).

Purpose: prove the self-improving loop's control flow — tool selection from the
LLM, queue refill, transition feedback to every tool, stall-triggered
re-decision, and per-level reset — works without a network or arcengine, using
fake tools and a fake LLM.
Expected feedback: a pass means the orchestration spine is correct and any
game-clearing shortfall is a tool-quality issue, not a loop bug; a failure
localises the defect to the loop itself.
"""

from __future__ import annotations

import numpy as np
import pytest

from admorphiq.harness.loop import UnifiedAgent
from admorphiq.tools.base import Step


class _State:
    def __init__(self, name: str) -> None:
        self.name = name


class _Obs:
    """Duck-typed observation matching the adapter API readers."""

    def __init__(self, grid: np.ndarray, actions: list[int], levels: int = 0,
                 state: str = "NOT_FINISHED") -> None:
        self.frame = [grid.tolist()]
        self.available_actions = actions
        self.levels_completed = levels
        self.state = _State(state)


class _FakeTool:
    """Records lifecycle calls; proposes a fixed legal step."""

    def __init__(self, name: str, step: Step, confidence: float = 0.5) -> None:
        self.name = name
        self._step = step
        self._conf = confidence
        self.observed = 0
        self.resets = 0
        self.proposed = 0

    def detect(self, frames, obs) -> float:
        return self._conf

    def reset(self) -> None:
        self.resets += 1

    def observe(self, prev, action, changed) -> None:
        self.observed += 1

    def propose(self, frames, obs):
        self.proposed += 1
        return [self._step]


def _agent(tools, choice: str):
    """Build an agent whose fake LLM always picks ``choice``."""
    def llm(messages):
        return f'{{"mode":"tool","tool":"{choice}"}}'
    return UnifiedAgent(tools, llm, giveup=1000, stall=3)


def test_llm_tool_choice_drives_refill():
    """Purpose: the LLM's chosen tool is the one asked to propose the queue.
    Expected feedback: pass = decision->tool->propose wiring is intact."""
    grid = np.zeros((64, 64), dtype=np.int64)
    up = _FakeTool("graph", (1, None), 0.9)
    click = _FakeTool("paint", (6, (10, 10)), 0.4)
    agent = _agent([up, click], "paint")
    agent.choose_action([], _Obs(grid, [1, 2, 3, 4, 6]))
    assert click.proposed == 1 and up.proposed == 0
    assert "paint" in agent._tried


def test_transition_feedback_reaches_every_tool():
    """Purpose: each acted transition is fed to observe() on all tools.
    Expected feedback: pass = stateful tools learn from the agent's own probes."""
    g = np.zeros((64, 64), dtype=np.int64)
    t1 = _FakeTool("graph", (1, None), 0.9)
    t2 = _FakeTool("world_model", (2, None), 0.8)
    agent = _agent([t1, t2], "graph")
    agent.choose_action([], _Obs(g, [1, 2, 3, 4]))       # step 1, no prev yet
    g2 = g.copy()
    g2[0, 0] = 5
    agent.choose_action([], _Obs(g2, [1, 2, 3, 4]))      # step 2 records transition
    assert t1.observed == 1 and t2.observed == 1


def test_level_up_resets_all_tools():
    """Purpose: a level transition resets tool state and clears the queue.
    Expected feedback: pass = per-level learning does not leak across levels."""
    g = np.zeros((64, 64), dtype=np.int64)
    tool = _FakeTool("graph", (1, None), 0.9)
    agent = _agent([tool], "graph")
    agent.choose_action([], _Obs(g, [1, 2, 3, 4], levels=0))
    before = tool.resets
    agent.choose_action([], _Obs(g, [1, 2, 3, 4], levels=1))
    assert tool.resets == before + 1
    assert agent._last_levels == 1


def test_stall_triggers_redecision():
    """Purpose: after `stall` inert actions the loop re-decides (re-proposes).
    Expected feedback: pass = the loop escapes a dead tool instead of looping."""
    g = np.zeros((64, 64), dtype=np.int64)  # frame never changes -> every action inert
    tool = _FakeTool("graph", (1, None), 0.9)
    agent = _agent([tool], "graph")
    for _ in range(6):
        agent.choose_action([], _Obs(g, [1, 2, 3, 4]))
    # stall=3 -> at least two refills beyond the initial one
    assert tool.proposed >= 2


def test_progressing_tool_does_not_call_llm_every_action():
    """Purpose: while the current tool keeps changing the frame, the queue may
    empty each step but the LLM is consulted only at decision boundaries, not per
    action — the latency bound the SWA-cache finding (r53) demands.
    Expected feedback: pass = LLM-call rate is bounded; fail = a per-action LLM
    call would blow the 9h/110-game budget."""
    calls = {"n": 0}

    def counting_llm(messages):
        calls["n"] += 1
        return '{"mode":"tool","tool":"graph"}'

    # a tool that proposes ONE step at a time -> queue empties every action
    tool = _FakeTool("graph", (1, None), 0.9)
    agent = UnifiedAgent([tool], counting_llm, giveup=1000, stall=50)
    g = np.zeros((64, 64), dtype=np.int64)
    for i in range(10):
        gi = g.copy()
        gi[0, i] = 1  # every action changes the frame (progress)
        agent.choose_action([], _Obs(gi, [1, 2, 3, 4]))
    # 10 progressing actions, stall=50 never hit -> exactly one decision (the first)
    assert calls["n"] == 1
    assert tool.proposed >= 5  # tool refilled repeatedly WITHOUT the LLM


def test_llm_failure_falls_back_to_signature_default():
    """Purpose: if the LLM raises, the highest-detect tool is used (offline-safe).
    Expected feedback: pass = the agent never crashes when the model is down."""
    g = np.zeros((64, 64), dtype=np.int64)
    hi = _FakeTool("graph", (1, None), 0.95)
    lo = _FakeTool("paint", (6, (5, 5)), 0.1)

    def broken_llm(messages):
        raise RuntimeError("ollama down")

    agent = UnifiedAgent([hi, lo], broken_llm, giveup=1000, stall=3)
    agent.choose_action([], _Obs(g, [1, 2, 3, 4, 6]))
    assert hi.proposed == 1 and lo.proposed == 0


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
