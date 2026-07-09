"""Contract tests for redraw diversity (r51 config-UNION applied to draws).

The FIRST target draw must stay the measured-optimal simple prompt (enriching
it was measured to regress cd82); only stall-gated REDRAWS add the observed
action->effect evidence block. All offline; no LLM.
"""

from __future__ import annotations

import numpy as np

from admorphiq.harness.loop import UnifiedAgent
from admorphiq.tools.graph_search import GraphSearchTool
from admorphiq.tools.targetgrid import build_target_prompt


def _frame() -> np.ndarray:
    f = np.zeros((64, 64), dtype=np.int64)
    f[10:20, 10:20] = 3
    return f


def test_first_draw_prompt_has_no_evidence_block():
    """Purpose: the base prompt (draw 1) must be byte-stable vs the validated
    simple prompt — no evidence section unless action_evidence is passed.
    Expected feedback: pass = cd82's proven draw path is untouched; fail = the
    measured-harmful enriched-prompt regression is back on the FIRST draw."""
    p = build_target_prompt(_frame())
    assert "mechanics evidence" not in p


def test_redraw_prompt_carries_action_evidence():
    """Purpose: when action_evidence is passed (redraw config), the prompt
    contains the evidence block verbatim.
    Expected feedback: pass = redraws actually vary the evidence mix; fail =
    diversity is cosmetic and every draw repeats the same failed config."""
    ev = "- MOUSE: 12 tries, median 4 cells changed"
    p = build_target_prompt(_frame(), action_evidence=ev)
    assert "mechanics evidence" in p and ev in p


def test_action_evidence_summarizes_own_transitions():
    """Purpose: _action_evidence compacts the agent's own logged transitions
    into per-action median-changed-cells lines (the evidence the redraw cites).
    Expected feedback: pass = redraws cite real observed mechanics; fail = the
    evidence block is empty/garbage and diversity adds nothing."""
    agent = UnifiedAgent([GraphSearchTool()], llm=lambda m: "")
    assert agent._action_evidence() is None  # no transitions yet
    a, b = _frame(), _frame()
    b[0, 0:4] = 7  # 4 cells changed
    agent._transitions = [(a, 6, b), (a, 6, b), (a, 1, a)]
    ev = agent._action_evidence()
    assert "median 4 cells changed" in ev  # ACTION6 line
    assert "2 tries" in ev
    assert "median 0 cells changed" in ev  # the no-op action line
