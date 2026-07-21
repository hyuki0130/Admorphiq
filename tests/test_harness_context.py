"""Tests for the minimal signature-targeted wiki context (harness/context.py).

Purpose: prove the runtime context is (a) derived from observable frame signals
only, and (b) trimmed to a char budget by relevance — the mechanism that keeps
the weak offline model inside its window while still seeing the right tool docs.
Expected feedback: a pass means context injection behaves as retrieval (not
few-shot dump); a failure means the model would get the wrong or oversized slice.
"""

from __future__ import annotations

import numpy as np
import pytest

from admorphiq.harness.context import (
    Signature,
    build_context,
    compute_signature,
)


class _State:
    def __init__(self, name: str) -> None:
        self.name = name


class _Obs:
    def __init__(self, actions: list[int]) -> None:
        self.frame = [np.zeros((8, 8), dtype=np.int64).tolist()]
        self.available_actions = actions
        self.levels_completed = 0
        self.state = _State("NOT_FINISHED")


def test_signature_movement_vs_click():
    """Purpose: availability drives has_movement / click_fraction.
    Expected feedback: pass = the signature reflects the action space correctly."""
    mov = compute_signature(_Obs([1, 2, 3, 4]), [])
    clk = compute_signature(_Obs([6]), [])
    assert mov.has_movement and mov.click_fraction == 0.0
    assert not clk.has_movement and clk.click_fraction == 1.0


def test_signature_detects_nondeterminism():
    """Purpose: same (state, action) -> different next-state raises nondeterminism.
    Expected feedback: pass = aliasing/nondeterminism is measured from transitions."""
    a = np.zeros((8, 8), dtype=np.int64)
    b = a.copy(); b[0, 0] = 1
    c = a.copy(); c[7, 7] = 2
    # identical prev+action (Step (1, None)) yielding two different next frames
    # -> nondeterministic. Transitions carry the full Step now, not a bare int.
    sig = compute_signature(_Obs([1, 2]), [(a, (1, None), b), (a, (1, None), c)])
    assert sig.nondeterminism > 0.0


def test_build_context_respects_budget():
    """Purpose: build_context never exceeds the char budget it is given.
    Expected feedback: pass = the runtime model's window is protected."""
    sig = Signature(avatar_mobility=0.8, click_fraction=0.0, nondeterminism=0.0,
                    recolor_scale=5.0, has_movement=True)
    small = build_context(sig, budget_chars=800)
    big = build_context(sig, budget_chars=8000)
    assert len(small) <= 800
    # a larger budget admits at least as much context as a smaller one
    assert len(big) >= len(small)


def test_relevant_tools_order_tracks_signature():
    """Purpose: a navigation signature front-loads graph; a transform one llm_goal.
    Expected feedback: pass = the right tool docs win the limited budget."""
    nav = Signature(avatar_mobility=0.9, click_fraction=0.0, nondeterminism=0.0,
                    recolor_scale=5.0, has_movement=True)
    transform = Signature(avatar_mobility=0.0, click_fraction=0.2, nondeterminism=0.0,
                          recolor_scale=200.0, has_movement=False)
    from admorphiq.harness.context import _relevant_tools
    assert _relevant_tools(nav).index("graph") < _relevant_tools(nav).index("llm_goal")
    assert _relevant_tools(transform).index("llm_goal") < _relevant_tools(transform).index("graph")


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
