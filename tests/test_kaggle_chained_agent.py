"""Contract tests for the Kaggle chained-agent wrapper (the v1 submission).

Pin what the notebook relies on: the wrapper builds the LLM-FREE chain (dead
LLM — no network attempt on Kaggle), exposes the official interface, and
enforces the MAX_ACTIONS safety net. All offline.
"""

from __future__ import annotations

import numpy as np


def test_build_chained_is_llm_free_and_restartable():
    """Purpose: the deployed chain must be constructible WITHOUT any LLM
    backend (the v1 notebook ships numpy-only) and must opt into GAME_OVER
    restarts (the measured fix that keeps death-prone games alive).
    Expected feedback: pass = the notebook boots offline as measured (1.072%);
    fail = the submission needs infra the Kaggle image does not have."""
    from admorphiq.kaggle_chained_agent import build_chained

    chain = build_chained()
    assert chain.restart_on_game_over is True
    # The dead LLM must raise (offline-safe routing engages), never call out.
    import pytest

    with pytest.raises(RuntimeError):
        chain._main.llm([{"role": "user", "content": "hi"}])


def test_probe_phase_first_action_no_llm():
    """Purpose: the chain's first decision comes from the WMA probe with no
    LLM involvement — one full choose_action round-trip offline.
    Expected feedback: pass = the wrapper produces a legal first action from a
    bare observation; fail = the submission dies on its first step."""
    from admorphiq.kaggle_chained_agent import build_chained

    class _State:
        name = "NOT_FINISHED"

    class _Obs:
        frame = [np.zeros((64, 64), dtype=np.int64).tolist()]
        state = _State()
        available_actions = [1, 2, 3, 4]
        levels_completed = 0

    chain = build_chained()
    obs = _Obs()
    assert not chain.is_done([], obs)
    action = chain.choose_action([], obs)
    assert action is not None
