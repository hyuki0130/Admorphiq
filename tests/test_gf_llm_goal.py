"""Contract tests for LLM goal inference in the graph agent (GF_LLM_GOAL)."""

from __future__ import annotations

import numpy as np

from admorphiq.graph_frontier_agent import GraphFrontierAgent


def test_llm_goal_off_by_default():
    """Purpose: GF_LLM_GOAL unset must not activate goal machinery (deployed
    18/25 card unchanged).

    Expected feedback: pass ⇒ default-OFF guard holds; fail ⇒ the feature leaks
    into the deployed config.
    """
    a = GraphFrontierAgent()
    assert a.llm_goal is False
    assert a._goal_active is False


def test_llm_goal_on_activates_goal_and_degrades_gracefully(monkeypatch):
    """Purpose: with GF_LLM_GOAL on, goal machinery activates, and if the model
    is unreachable the inference degrades to the heuristic GoalSpec (never
    blocks the offline agent).

    Expected feedback: pass ⇒ the tool is offline-safe and goal-active; fail ⇒
    it either stays inert or crashes when ollama is down.
    """
    monkeypatch.setenv("GF_LLM_GOAL", "1")
    monkeypatch.setenv("GF_LLM_GOAL_HOST", "http://localhost:1")  # dead port
    a = GraphFrontierAgent()
    assert a.llm_goal is True
    assert a._goal_active is True
    f = np.zeros((64, 64), dtype=np.int64)
    f[10:20, 10:20] = 5
    goal = a._infer_goal_via_llm(f)  # ollama unreachable -> heuristic fallback
    assert goal is not None  # always yields a usable goal, never blocks
