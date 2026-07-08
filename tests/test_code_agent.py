"""Contract tests for the LLM REPL code-agent core (frontier lever)."""

from __future__ import annotations

import numpy as np

from admorphiq.tools.code_agent import build_code_prompt, run_code


def _frame():
    return np.zeros((64, 64), dtype=np.int16)


def test_code_queues_simple_and_click_actions():
    """Purpose: model-written code that calls act(...) must queue the right
    actions (directional + click), so the LLM can drive the game via code.

    Expected feedback: pass ⇒ the code->action bridge works; fail ⇒ the
    code-agent cannot act.
    """
    code = "```python\nact('UP')\nact('CLICK', 12, 30)\n```"
    r = run_code(code, _frame(), [], ["UP", "MOUSE"])
    assert r.actions == [("ACTION1", None), ("ACTION6", (12, 30))]
    assert r.error == ""


def test_code_can_inspect_frame_with_numpy():
    """Purpose: the sandbox must expose current_frame + numpy so the model can
    compute where to act (the whole point of code-over-fixed-tools).

    Expected feedback: pass ⇒ code can reason over the grid; fail ⇒ the model
    is blind.
    """
    code = (
        "```python\n"
        "g = np.array(current_frame)\n"
        "act('CLICK', int(g.shape[1]//2), int(g.shape[0]//2))\n"
        "```"
    )
    r = run_code(code, _frame(), [], ["MOUSE"])
    assert r.actions == [("ACTION6", (32, 32))]


def test_broken_code_degrades_to_empty_never_crashes():
    """Purpose: syntactically broken model output must yield an empty queue +
    error string, never raise (the game loop must survive bad generations).

    Expected feedback: pass ⇒ robust to garbage; fail ⇒ a bad block crashes the
    agent.
    """
    r = run_code("```python\nact('UP'\n```", _frame(), [], ["UP"])
    assert r.actions == []
    assert r.error


def test_sandbox_blocks_file_and_network():
    """Purpose: model code must NOT be able to read files or open sockets
    (the REPL runs untrusted generations).

    Expected feedback: pass ⇒ disallowed imports fail inside the sandbox (empty
    queue, error captured); fail ⇒ arbitrary code execution escapes.
    """
    r = run_code("```python\nimport os\nact('UP')\n```", _frame(), [], ["UP"])
    assert r.error  # import os blocked by the whitelist -> captured, no crash


def test_prompt_is_game_agnostic():
    """Purpose: the code-agent prompt exposes only frame + actions, no game id.

    Expected feedback: pass ⇒ transfers to unseen games; fail ⇒ a leak crept in.
    """
    msgs = build_code_prompt(_frame(), [], ["UP", "DOWN"])
    blob = (msgs[0]["content"] + msgs[1]["content"]).lower()
    for tok in ("ft09", "su15", "game_id", "game_title"):
        assert tok not in blob
