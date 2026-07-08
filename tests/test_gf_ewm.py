"""Contract tests for the GF_EWM world-model pruning hook (R52 / US-3)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import numpy as np

from admorphiq.graph_frontier_agent import GraphFrontierAgent


@dataclass
class _StubResult:
    fn: Callable[..., Any]
    train_fit: float


def _frame() -> np.ndarray:
    return np.zeros((8, 8), dtype=np.int16)


def test_gf_ewm_off_by_default_records_nothing_and_orders_identically():
    """Purpose: with GF_EWM unset the agent must behave byte-identically to
    pre-R52 — no observation logging, no model, untried ordering unchanged —
    so the deployed card is untouched by this round.

    Expected feedback: pass ⇒ default-OFF regression guard holds; fail ⇒ the
    EWM hook leaks into the deployed configuration.
    """
    agent = GraphFrontierAgent()
    assert agent.ewm_enabled is False
    assert agent._ewm_obs == []
    agent._untried["s"] = [3, 1, ("click", 2, 2)]
    agent._action_tier[("click", 2, 2)] = 0
    with_frame = agent._best_untried_within_tier("s", _frame())
    without = agent._best_untried_within_tier("s")
    assert with_frame == without  # frame arg is inert while no model exists


def test_pruning_deprioritizes_predicted_nochange_within_tier(monkeypatch):
    """Purpose: with an accepted world model, an untried action the model
    predicts as no-change must sort AFTER a same-tier action predicted to
    change — deprioritized but never removed.

    Expected feedback: pass ⇒ the agent spends its next real action where the
    model expects an effect (the RHAE-efficiency lever); fail ⇒ the hook does
    not influence expansion order and GF_EWM is a no-op.
    """
    monkeypatch.setenv("GF_EWM", "1")
    agent = GraphFrontierAgent()
    assert agent.ewm_enabled is True

    def fn(frame: Any, action: str, xy: Any = None) -> Any:
        # ACTION1 (key 1) is inert; everything else flips a cell.
        out = [row[:] for row in frame]
        if action != "ACTION1":
            out[0][0] = 1
        return out

    agent._ewm_result = _StubResult(fn=fn, train_fit=1.0)
    # Registration order favours key 1; both are simple actions (same tier).
    agent._untried["s"] = [1, 2]
    picked = agent._best_untried_within_tier("s", _frame())
    assert picked == 2  # predicted-change action wins despite later registration
    # Without the frame (no prediction possible) registration order returns.
    assert agent._best_untried_within_tier("s") == 1


def test_low_fit_synthesis_is_rejected_and_high_fit_kept(monkeypatch):
    """Purpose: a synthesized model is deployed ONLY when its fit over all
    observations reaches GF_EWM_MIN_FIT — a badly-fitting model would
    deprioritize the wrong actions, worse than no model.

    Expected feedback: pass ⇒ the min-fit gate protects the agent from its own
    world model; fail ⇒ low-quality synthesis silently steers exploration.
    """
    monkeypatch.setenv("GF_EWM", "1")
    agent = GraphFrontierAgent()
    frame = _frame()
    nxt = frame.copy()
    nxt[0, 0] = 1
    agent._ewm_obs = [(frame, 0, nxt)] * agent.ewm_min_obs

    agent._ewm_synthesize = lambda ts: _StubResult(fn=lambda *a: None, train_fit=0.2)
    agent._ewm_try_synthesize()
    assert agent._ewm_result is None

    agent._ewm_attempted = False
    good = _StubResult(fn=lambda *a: None, train_fit=0.9)
    agent._ewm_synthesize = lambda ts: good
    agent._ewm_try_synthesize()
    assert agent._ewm_result is good


def test_action_key_mapping_covers_simple_and_click_only():
    """Purpose: pin the graph-key -> EWM-index mapping: simple keys 1..5 map to
    ACTION1..5, click tuples map to coordinate indices, and RESET(0)/6/7 are
    excluded from the observation log (predict_next_frame has no semantics for
    them).

    Expected feedback: pass ⇒ observations reach synthesis with correct action
    labels; fail ⇒ the world model learns from mislabeled actions.
    """
    agent = GraphFrontierAgent()
    assert agent._ewm_action_idx(1) == 0
    assert agent._ewm_action_idx(5) == 4
    assert agent._ewm_action_idx(("click", 3, 2)) == 5 + 2 * 64 + 3
    assert agent._ewm_action_idx(0) is None
    assert agent._ewm_action_idx(6) is None
    assert agent._ewm_action_idx(7) is None
