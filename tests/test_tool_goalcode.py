"""Contract tests for the executable goal scorer (tools/goalcode.py).

These pin the frontier lever's safety story: a model-written goal_score is only
injected after compiling in the restricted sandbox AND returning a finite number
on the live frame — garbage costs nothing (the caller keeps its frame-only base).
All offline; no LLM.
"""

from __future__ import annotations

import numpy as np

from admorphiq.tools.goalcode import build_scorer_prompt, compile_scorer
from admorphiq.tools.graph_search import GraphSearchTool


def _frame() -> np.ndarray:
    f = np.zeros((64, 64), dtype=np.int64)
    f[10:14, 10:14] = 3
    return f


def test_valid_scorer_compiles_and_scores():
    """Purpose: a well-formed goal_score block compiles in the sandbox and the
    returned callable scores frames (higher = closer).
    Expected feedback: pass = the executable-goal path works end to end; fail =
    the frontier lever cannot inject any scorer at all."""
    txt = "```python\ndef goal_score(frame):\n    return sum(row.count(3) for row in frame)\n```"
    fn, why = compile_scorer(txt, _frame())
    assert fn is not None, why
    more3 = _frame()
    more3[20:30, 20:30] = 3
    assert fn(more3) > fn(_frame())


def test_garbage_and_hostile_scorers_rejected():
    """Purpose: no-function replies, crashing bodies, non-finite returns and
    sandbox-escaping imports are all rejected (fn is None), never injected.
    Expected feedback: pass = garbage draws cost nothing; fail = a bad scorer
    could crash or hijack the frontier ranking."""
    f = _frame()
    assert compile_scorer("no code here", f)[0] is None
    assert compile_scorer("```python\ndef goal_score(frame):\n    return 1/0\n```", f)[0] is None
    assert compile_scorer(
        "```python\ndef goal_score(frame):\n    return float('nan')\n```", f)[0] is None
    assert compile_scorer(
        "```python\nimport os\ndef goal_score(frame):\n    return 1\n```", f)[0] is None


def test_graph_steers_toward_injected_scorer():
    """Purpose: set_external_scorer makes the frontier ranking prefer states the
    scorer rates higher (exclusive mode: tracker/target cleared).
    Expected feedback: pass = an LLM-written goal actually steers graph's search;
    fail = the injection is cosmetic."""
    tool = GraphSearchTool()
    tool.set_external_scorer(lambda fr: float(np.sum(np.asarray(fr) == 3)))
    assert tool._goal_tracker is None and tool._target_grid is None
    lo = np.zeros((8, 8), dtype=np.int64)
    hi = lo.copy()
    hi[0:4, 0:4] = 3
    tool._state_frame["lo"] = lo
    tool._state_frame["hi"] = hi
    assert tool._goal_proximity("hi") > tool._goal_proximity("lo")


def test_prompt_mentions_board_facts():
    """Purpose: the scorer prompt carries the observable evidence (colour counts,
    object list, action effects) the model needs to infer the goal.
    Expected feedback: pass = the model gets real signal, not a blind ask."""
    p = build_scorer_prompt(_frame(), [{"action": 6, "changed_cells": 12}])
    assert "colour 3" in p and "goal_score" in p and "12 cells changed" in p
