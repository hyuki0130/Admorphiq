"""Contract tests for hidden-state de-aliasing (US-11, GF_DEALIAS)."""

from __future__ import annotations

import numpy as np

from admorphiq.graph_frontier_agent import GraphFrontierAgent


def _frame() -> np.ndarray:
    f = np.zeros((64, 64), dtype=np.int64)
    f[10:14, 10:14] = 3
    return f


def test_dealias_off_is_byte_identical_to_base():
    """Purpose: GF_DEALIAS unset must make _hash byte-identical to the base hash —
    the deployed 18/25 card must be untouched by this feature.

    Expected feedback: pass ⇒ default-OFF regression guard holds; fail ⇒ the
    de-aliasing feature changed the baseline hashing.
    """
    agent = GraphFrontierAgent()
    assert agent.dealias is False
    f = _frame()
    assert agent._hash(f) == agent._base_hash(f)  # no suffix ever applied


def test_dealias_splits_only_flagged_aliased_bases(monkeypatch):
    """Purpose: with GF_DEALIAS on, a state whose base is NOT flagged aliased
    hashes to its base (no explosion); once flagged, the SAME frame hashes
    differently under different recent action-histories (true-states separate).

    Expected feedback: pass ⇒ de-aliasing is surgical (only aliased bases split,
    by history); fail ⇒ either it never splits or it splits everything (the R39
    state-explosion class).
    """
    monkeypatch.setenv("GF_DEALIAS", "1")
    agent = GraphFrontierAgent()
    assert agent.dealias is True
    f = _frame()
    base = agent._base_hash(f)

    # Not flagged yet -> hash == base (no explosion for ordinary states).
    assert agent._hash(f) == base

    # Flag the base as aliased; now history discriminates.
    agent._aliased_bases.add(base)
    agent._action_hist.clear()
    agent._action_hist.append(1)
    h1 = agent._hash(f)
    agent._action_hist.clear()
    agent._action_hist.append(("click", 5, 5))
    h2 = agent._hash(f)
    assert h1 != base and h2 != base   # suffix applied
    assert h1 != h2                    # different histories -> different nodes
