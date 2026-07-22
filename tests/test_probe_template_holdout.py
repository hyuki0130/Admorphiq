"""Smoke test for scripts/probe_template_holdout.py's adaptation-ask + selection
plumbing (the R94 D5 paired-holdout runner).

This is a MEASUREMENT DRIVER, not a unit-tested library — the holdout run itself
needs a live Arcade env + vLLM server. But the plumbing that decides the reported
outcome (the adaptation ask + validate, the select-on-adaptation-replay rule, the
frozen JSON shape, and the trace-capturing template driver) MUST be exercised
hermetically: a MockLLM returns the UNCHANGED card as one fenced block, and we
prove ask_adaptation accepts it, decide_selection applies the lexicographic rule,
result_json carries every frozen field, and the template driver executes the
verbatim card in the sandbox — all with no env and no network LLM.
"""

from __future__ import annotations

import numpy as np
import pytest

import scripts.probe_template_holdout as pth
from admorphiq.tools.solver_core import source_card


@pytest.fixture
def bridge_on(monkeypatch):
    """The driver line references ``transitions``, only exposed when the kernel
    bridge gate is set (byte-identical sandbox otherwise)."""
    monkeypatch.setenv("HARNESS_KERNEL_API", "1")


def _fence(code: str) -> str:
    return f"```python\n{code}\n```"


def _metrics(levels=0, states=1, transitions=1, noop=0.5):
    """A synthetic metrics dict in the shape _metrics_from_transitions emits."""
    return {"levels": levels, "actions": 100, "distinct_states": states,
            "distinct_transitions": transitions, "noop_rate": noop}


def test_ask_adaptation_accepts_unchanged_card_from_mock_llm():
    """Purpose: end-to-end adaptation ask — a MockLLM returning the UNCHANGED
    toggle core (the honest "the template already fits" reply) is accepted on the
    FIRST attempt with no retry and no failure_stage.

    Expected feedback: pass ⇒ ask_adaptation's happy path + shared validate_patch
    wiring works without a live LLM; fail ⇒ the ask/validate plumbing is broken
    independent of any model's actual adaptation quality."""
    card = source_card("toggle")
    text = _fence(card)

    def mock_llm(messages: list[dict[str, str]]) -> str:
        assert messages and messages[0]["role"] == "user"
        # the holdout instruction, not R93's "keep the structure" patch ask
        assert "DIFFERENT game" in messages[0]["content"]
        return text

    result = pth.ask_adaptation(mock_llm, "toggle", "toggle_core", card,
                                "(none)", "levels=0 actions=0")
    assert result["failure_stage"] is None
    assert result["attempts"] == 1
    assert "def toggle_core" in result["code"]


def test_ask_adaptation_retries_once_then_reports_failure_stage():
    """Purpose: a MockLLM that ALWAYS returns invalid text (no fenced block) is
    retried exactly once, then reported as a "parse" failure_stage rather than
    raising — the runner must degrade to a template selection, never crash.

    Expected feedback: pass ⇒ the one-retry-then-fail contract holds; fail ⇒
    either no retry happens or the failure crashes the runner."""
    calls = {"n": 0}

    def mock_llm(messages: list[dict[str, str]]) -> str:
        calls["n"] += 1
        return "I cannot adapt this solver."

    result = pth.ask_adaptation(mock_llm, "simdfs", "simdfs_core", "(card)",
                               "(none)", "levels=0")
    assert calls["n"] == 2  # one call + one retry
    assert result["code"] is None
    assert result["failure_stage"] == "parse"


def test_decide_selection_holds_template_when_adaptation_invalid():
    """Purpose: pin the frozen rule — when the adaptation never produced runnable
    code (adaptation_replay is None), the verbatim template is selected.

    Expected feedback: pass ⇒ an invalid adaptation can never be scored; fail ⇒
    the runner could report a null replay as the outcome."""
    assert pth.decide_selection(_metrics(levels=1), None, execute_failed=False) == "template"


def test_decide_selection_holds_template_on_execute_failure():
    """Purpose: an adapted core that validated but failed to execute (every
    sandbox invocation errored) must NOT be selected over the template.

    Expected feedback: pass ⇒ execute-failed adaptations fall back to template;
    fail ⇒ a non-running adaptation could be reported as the scored variant."""
    assert pth.decide_selection(_metrics(levels=1), _metrics(levels=0),
                                execute_failed=True) == "template"


def test_decide_selection_picks_adapted_when_it_beats_baseline():
    """Purpose: the adapted replay is selected iff it beats the template baseline
    by the lexicographic rule — here it clears MORE levels.

    Expected feedback: pass ⇒ select-on-adaptation-replay rewards a genuine
    improvement; fail ⇒ the experiment's headline signal is inverted."""
    assert pth.decide_selection(_metrics(levels=0), _metrics(levels=1),
                                execute_failed=False) == "adapted"


def test_decide_selection_holds_template_on_tie():
    """Purpose: a genuine tie (identical metrics) is NOT an adapted win — the
    template holds, matching _patch_beats_parent's strict-improvement contract.

    Expected feedback: pass ⇒ no false "adapted wins" on ties; fail ⇒ the
    tie-break leaks a spurious adaptation selection."""
    tied = _metrics(levels=0, states=5, transitions=5, noop=0.5)
    assert pth.decide_selection(dict(tied), dict(tied), execute_failed=False) == "template"


def test_result_json_carries_every_frozen_field():
    """Purpose: pin the reported JSON shape — the frozen protocol requires arm,
    game, budget, template_baseline, adaptation{failure_stage,adapted_code,
    llm_latency_s}, adaptation_replay, selected, fresh_score.

    Expected feedback: pass ⇒ downstream aggregation can rely on the schema;
    fail ⇒ a field was renamed/dropped and the bench summary would KeyError."""
    ask = {"code": "def simdfs_core(a,b,c,d=None): pass", "failure_stage": None,
           "raw_text": "...", "attempts": 1, "error": None}
    res = pth.result_json(
        "simdfs", "sk48", 2000,
        template_baseline=_metrics(levels=1),
        ask=ask, adaptation_replay=_metrics(levels=2), selected="adapted",
        fresh_score=_metrics(levels=2), llm_latency_s=3.14159)
    assert set(res) == {"arm", "game", "budget", "template_baseline",
                        "adaptation", "adaptation_replay", "selected", "fresh_score"}
    assert set(res["adaptation"]) == {"failure_stage", "adapted_code", "llm_latency_s"}
    assert res["adaptation"]["adapted_code"] == ask["code"]
    assert res["adaptation"]["llm_latency_s"] == 3.14
    assert res["selected"] == "adapted"


def test_result_json_falls_back_to_raw_text_when_no_code():
    """Purpose: when the adaptation produced no valid code, adapted_code reports
    the model's RAW reply (for post-hoc diagnosis), not None silently.

    Expected feedback: pass ⇒ invalid adaptations remain inspectable in the JSON;
    fail ⇒ a PATCH_INVALID case loses the model's actual output."""
    ask = {"code": None, "failure_stage": "parse", "raw_text": "no fence here",
           "attempts": 2, "error": "expected exactly one fenced python block, found 0"}
    res = pth.result_json("toggle", "sk48", 2000, _metrics(), ask, None,
                         "template", _metrics(), 1.0)
    assert res["adaptation"]["adapted_code"] == "no fence here"
    assert res["adaptation_replay"] is None
    assert res["selected"] == "template"


def test_template_driver_runs_verbatim_toggle_card_through_the_sandbox(bridge_on):
    """Purpose: the template-baseline primitive (``template_driver`` + a
    ``run_code`` exec) runs the UNCHANGED toggle core on synthetic single-cell-
    flip stencil evidence, queues the correct GF(2) solve clicks, AND surfaces
    the core's trace via the printed ``_tr`` channel the runner harvests.

    Expected feedback: pass ⇒ the verbatim-card driver is wired end to end (both
    actions and trace); fail ⇒ a real baseline run would queue nothing/the wrong
    clicks or lose the trace the adaptation ask depends on."""
    from admorphiq.tools.code_agent import run_code

    card = source_card("toggle")
    driver = pth.template_driver(card, "toggle_core")

    clicks = [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0)]
    states = [np.zeros((8, 8), dtype=np.int64)]
    for x, y in clicks:
        nxt = states[-1].copy()
        nxt[y, x] ^= 1
        states.append(nxt)
    trans = [
        ("CLICK", [x, y], states[i], states[i + 1])
        for i, (x, y) in enumerate(clicks)
    ]
    board = np.zeros((8, 8), dtype=np.int64)
    board[0, 1] = 1
    board[0, 3] = 1  # ON at cells covered by clicks (1,0) and (3,0)

    res = run_code(driver, board, [], ["MOUSE"], transitions=trans)

    assert res.error == "", res.error
    assert sorted(res.actions) == [("ACTION6", (1, 0)), ("ACTION6", (3, 0))]
    assert res.printed  # the core's _tr trace made it back out of the sandbox


def test_module_is_importable_without_a_live_arcade_env():
    """Purpose: arc_agi/arcengine (the live-env dependencies) must be imported
    LAZILY inside the env-driving functions, not at module scope — otherwise
    every hermetic test in this file would require a real game engine.

    Expected feedback: pass ⇒ the module already imported cleanly above (this
    pins the intent); fail ⇒ a future edit hoisted an engine import to module
    scope, breaking hermetic testability."""
    import scripts.probe_template_holdout as reloaded
    assert callable(reloaded.template_driver)
    assert callable(reloaded.ask_adaptation)
    assert callable(reloaded.decide_selection)
    assert set(reloaded._ARM_CORE_FN) == {"simdfs", "simdfs_skel", "toggle"}
