"""Contract tests for the dead-signature action prior (R53 / US-12)."""

from __future__ import annotations

from admorphiq.graph_frontier_agent import GraphFrontierAgent


def test_dead_sig_off_by_default_byte_identical():
    """Purpose: GF_DEAD_SIG unset must leave untried ordering unchanged (the
    deployed card is untouched).

    Expected feedback: pass ⇒ default-OFF regression guard holds; fail ⇒ the
    prior leaks into deployment.
    """
    agent = GraphFrontierAgent()
    assert agent.dead_sig is False
    agent._untried["s"] = [1, 2]
    agent._action_tier[1] = 0
    agent._action_tier[2] = 0
    assert agent._best_untried_within_tier("s") == 1  # registration order


def test_dead_class_sorts_last_within_tier(monkeypatch):
    """Purpose: an action class observed inert (self-loop) >= dead_sig_min times
    with zero changes must sort AFTER a live class of the same tier, so the
    agent stops wasting probes on it (raises squared-efficiency).

    Expected feedback: pass ⇒ inert classes are deprioritized; fail ⇒ the prior
    does not steer exploration and GF_DEAD_SIG is a no-op.
    """
    monkeypatch.setenv("GF_DEAD_SIG", "1")
    monkeypatch.setenv("GF_DEAD_SIG_MIN", "3")
    agent = GraphFrontierAgent()
    assert agent.dead_sig is True
    # Two simple actions, same tier; action 1's bucket is dead, action 2 is live.
    agent._untried["s"] = [1, 2]
    agent._action_tier[1] = 0
    agent._action_tier[2] = 0
    b1, b2 = agent._bucket_of(1), agent._bucket_of(2)
    agent._ds_inert[b1] = 5      # >= min, zero active -> dead
    agent._ds_active[b2] = 1     # live
    assert agent._best_untried_within_tier("s") == 2  # live class wins


def test_single_change_revives_a_class(monkeypatch):
    """Purpose: one state-changing observation must revive a class — a useful
    action is never permanently suppressed by earlier inert probes.

    Expected feedback: pass ⇒ revival is immediate; fail ⇒ a class that acted
    once can still be wrongly treated as dead.
    """
    monkeypatch.setenv("GF_DEAD_SIG", "1")
    monkeypatch.setenv("GF_DEAD_SIG_MIN", "3")
    agent = GraphFrontierAgent()
    b = agent._bucket_of(1)
    agent._ds_inert[b] = 100
    agent._ds_active[b] = 1  # one change
    assert agent._bucket_is_dead(1) is False
