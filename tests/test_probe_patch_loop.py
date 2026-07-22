"""Smoke test for scripts/probe_patch_loop.py's patch-ask + driver plumbing.

This is a MEASUREMENT DRIVER, not a unit-tested library — the probe itself
needs no test suite. But the plumbing that step 3 (validate) and step 4 (the
matched-replay driver call through ``run_code``) share with a real Kaggle-time
run MUST be exercised hermetically (no Arcade env, no network LLM): a MockLLM
returns the UNCHANGED toggle core source as a single fenced block, and we prove
validate() accepts it and the driver call executes it in the sandbox exactly
as the probe's ``_run_patch`` would, on synthetic lights-out evidence.
"""

from __future__ import annotations

import numpy as np
import pytest

import scripts.probe_patch_loop as ppl
from admorphiq.tools.solver_core import paint_core, source_card, toggle_core


@pytest.fixture
def bridge_on(monkeypatch):
    """The driver line references ``transitions``/``K``, only exposed when the
    kernel bridge gate is set (byte-identical sandbox otherwise)."""
    monkeypatch.setenv("HARNESS_KERNEL_API", "1")


def _fence(code: str) -> str:
    return f"```python\n{code}\n```"


def test_validate_patch_accepts_the_unchanged_toggle_core():
    """Purpose: validate_patch() must accept the REAL, unmodified toggle core
    source (exactly one fenced block, compiles, defines toggle_core, no
    disallowed imports) — the baseline "no-op patch" case a weak model might
    produce when it can't improve on the original.

    Expected feedback: pass ⇒ a faithful patch is never rejected by the
    validator; fail ⇒ the validator is too strict to even accept a copy."""
    card = source_card("toggle")
    code, err = ppl.validate_patch(_fence(card), "toggle_core")
    assert err is None
    assert code is not None
    assert "def toggle_core" in code


def test_validate_patch_rejects_multiple_fenced_blocks():
    """Purpose: the 'exactly one fenced block' rule is enforced, not just
    'at least one' — a response with two blocks is ambiguous about which is
    the patch and must be rejected (triggering the one retry in ask_patch).

    Expected feedback: pass ⇒ ambiguous multi-block responses are caught;
    fail ⇒ the probe could silently execute the wrong block."""
    text = _fence("def toggle_core(a, b, c, d=None): pass") + "\n" + \
        _fence("def toggle_core(a, b, c, d=None): pass")
    code, err = ppl.validate_patch(text, "toggle_core")
    assert code is None
    assert "found 2" in err


def test_validate_patch_rejects_disallowed_import():
    """Purpose: a patch that imports outside the sandbox whitelist (e.g. `os`)
    must be rejected at validation, before it ever reaches run_code — the
    sandbox's own import guard is a second, redundant layer, not the only one.

    Expected feedback: pass ⇒ disallowed imports are caught at validate time;
    fail ⇒ only the sandbox's runtime guard would catch it (later, noisier)."""
    text = _fence("import os\ndef toggle_core(a, b, c, d=None): pass")
    code, err = ppl.validate_patch(text, "toggle_core")
    assert code is None
    assert "disallowed import" in err


def test_validate_patch_rejects_missing_core_fn():
    """Purpose: a patch that compiles but never defines the required core
    function name must be rejected — a plausible-looking block that renamed
    or omitted the function would otherwise silently no-op at driver time.

    Expected feedback: pass ⇒ a missing target function is caught explicitly;
    fail ⇒ the probe would run a driver call against an undefined name and
    misreport the failure as "execute", not "validate"."""
    text = _fence("def some_other_name(a, b, c, d=None): pass")
    code, err = ppl.validate_patch(text, "toggle_core")
    assert code is None
    assert "does not define toggle_core" in err


def test_ask_patch_accepts_unchanged_source_from_mock_llm():
    """Purpose: end-to-end steps 2+3 — a MockLLM returning the UNCHANGED toggle
    core (the honest "I can't improve this" response) is accepted on the FIRST
    attempt with no retry and no failure_stage.

    Expected feedback: pass ⇒ ask_patch's happy path works without a live LLM;
    fail ⇒ the generation/validate wiring itself is broken, independent of any
    model's actual patch quality."""
    card = source_card("toggle")
    text = _fence(card)

    def mock_llm(messages: list[dict[str, str]]) -> str:
        assert messages and messages[0]["role"] == "user"
        return text

    result = ppl.ask_patch(mock_llm, "toggle", "toggle_core", card, "(none)", "levels=0 actions=0")
    assert result["failure_stage"] is None
    assert result["attempts"] == 1
    assert "def toggle_core" in result["code"]


def test_ask_patch_retries_once_then_reports_failure_stage():
    """Purpose: a MockLLM that ALWAYS returns invalid text (no fenced block) is
    retried exactly once, then reported as a "parse" failure_stage rather than
    raising — the probe must degrade to PATCH_INVALID, never crash.

    Expected feedback: pass ⇒ the one-retry-then-fail contract holds; fail ⇒
    either no retry happens or the failure crashes the probe."""
    calls = {"n": 0}

    def mock_llm(messages: list[dict[str, str]]) -> str:
        calls["n"] += 1
        return "I cannot produce a patch."

    result = ppl.ask_patch(mock_llm, "toggle", "toggle_core", "(card)", "(none)", "levels=0")
    assert calls["n"] == 2  # one call + one retry
    assert result["code"] is None
    assert result["failure_stage"] == "parse"


def test_run_patched_step_solves_toggle_through_the_sandbox(bridge_on):
    """Purpose: the step-4 driver primitive (``run_patched_step``) — patched
    source + a driver call executed via ``run_code`` — runs the UNCHANGED
    toggle core on synthetic single-cell-flip stencil evidence and queues the
    correct GF(2) solve clicks, exactly as ``_run_patch``'s refill would.

    Expected feedback: pass ⇒ the matched-replay driver call is wired
    correctly end to end; fail ⇒ a real patch run would silently queue
    nothing or the wrong clicks."""
    card = source_card("toggle")

    # Chained single-cell-flip clicks: click (x, 0) flips board cell (0, x).
    clicks = [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0)]
    states = [np.zeros((8, 8), dtype=np.int64)]
    for x, y in clicks:
        nxt = states[-1].copy()
        nxt[y, x] ^= 1
        states.append(nxt)
    level_transitions = [
        {"action": "CLICK", "xy": [x, y], "before": states[i], "after": states[i + 1]}
        for i, (x, y) in enumerate(clicks)
    ]
    board = np.zeros((8, 8), dtype=np.int64)
    board[0, 1] = 1
    board[0, 3] = 1  # ON at cells covered by clicks (1,0) and (3,0)

    res = ppl.run_patched_step(card, "toggle_core", board, level_transitions)

    assert res.error == "", res.error
    assert sorted(res.actions) == [("ACTION6", (1, 0)), ("ACTION6", (3, 0))]


def test_run_patched_step_solves_paint_through_the_sandbox(bridge_on):
    """Purpose: the same step-4 driver primitive works for the paint core (the
    OTHER falsification-probe tool), proving the driver plumbing is tool-
    agnostic — it just needs the core fn name + matching transitions shape.

    Expected feedback: pass ⇒ paint patches can be matched-replayed the same
    way as toggle; fail ⇒ the driver silently only works for one tool."""
    card = source_card("paint")
    before = np.zeros((8, 8), dtype=np.int16)
    after = before.copy()
    for y, x in ((1, 1), (1, 2), (2, 1), (2, 2)):
        after[y, x] = 5
    level_transitions = [{"action": "CLICK", "xy": [1, 1], "before": before, "after": after}]
    board = np.full((8, 8), 5, dtype=np.int16)
    board[4:7, 4:7] = 0

    res = ppl.run_patched_step(card, "paint_core", board, level_transitions)

    assert res.error == "", res.error
    assert res.actions == [("ACTION6", (5, 5))]


def test_to_step_round_trips_action_names():
    """Purpose: _to_step (the reverse of code_agent's action-name mapping) must
    turn a CodeResult action back into the correct internal Step for both a
    click and a simple action — the glue between the sandbox output and the
    env-stepping loop.

    Expected feedback: pass ⇒ patched-core actions replay correctly against
    the live env; fail ⇒ clicks or simple actions would be misdirected."""
    assert ppl._to_step("ACTION6", (12, 40)) == (6, (12, 40))
    assert ppl._to_step("ACTION1", None) == (1, None)
    assert ppl._to_step("ACTION7", None) == (7, None)


def test_metrics_from_transitions_counts_states_and_noop_rate():
    """Purpose: _metrics_from_transitions must correctly count distinct states,
    distinct transitions, and the no-op rate from a synthetic transition log —
    the exact quantities the PATCH_WINS/PARENT_HOLDS verdict compares.

    Expected feedback: pass ⇒ the verdict's inputs are computed correctly;
    fail ⇒ the lexicographic comparison would be silently wrong."""
    a = np.zeros((4, 4), dtype=np.int64)
    b = a.copy()
    b[0, 0] = 1
    transitions = [
        (a, (6, (0, 0)), b),   # a real change
        (b, (1, None), b),     # a no-op
    ]
    m = ppl._metrics_from_transitions(transitions, levels=1, actions=2)
    assert m["levels"] == 1
    assert m["actions"] == 2
    assert m["distinct_states"] == 2
    assert m["distinct_transitions"] == 2
    assert m["noop_rate"] == pytest.approx(0.5)


def test_patch_beats_parent_is_lexicographic():
    """Purpose: pin the verdict's comparison ORDER — levels first, then
    distinct states, then distinct transitions, then (lower) no-op rate — so a
    future edit can't silently reorder the tie-breaks.

    Expected feedback: pass ⇒ the documented lexicographic contract holds;
    fail ⇒ PATCH_WINS/PARENT_HOLDS could flip on an unintended axis."""
    base = {"levels": 1, "distinct_states": 5, "distinct_transitions": 5, "noop_rate": 0.5}
    # more levels wins outright, even with worse everything else
    worse_but_more_levels = {**base, "levels": 2, "distinct_states": 1,
                              "distinct_transitions": 1, "noop_rate": 0.9}
    assert ppl._patch_beats_parent(worse_but_more_levels, base)
    # same levels, more distinct states wins
    more_states = {**base, "distinct_states": 6}
    assert ppl._patch_beats_parent(more_states, base)
    # everything tied except noop_rate: lower wins
    lower_noop = {**base, "noop_rate": 0.1}
    assert ppl._patch_beats_parent(lower_noop, base)
    # a genuine tie is not a win
    assert not ppl._patch_beats_parent(dict(base), dict(base))


def test_module_is_importable_without_a_live_arcade_env():
    """Purpose: arc_agi/arcengine (the live-env dependencies) must be imported
    LAZILY inside the env-driving functions, not at module scope — otherwise
    every hermetic test in this file would require a real game engine.

    Expected feedback: pass ⇒ the module already imported cleanly above (this
    just documents/pins the intent); fail would mean a future edit hoisted an
    engine import to module scope, breaking hermetic testability."""
    import scripts.probe_patch_loop as reloaded
    assert callable(reloaded.validate_patch)
    assert callable(reloaded.run_patched_step)
    # sanity: the cores this probe drives are the exact ones solver_core execs
    assert toggle_core.__name__ == "toggle_core"
    assert paint_core.__name__ == "paint_core"


# ── regression pins for the three MEASURED v1/v2 Kaggle failure shapes ───────
# The original MockLLM smoke returned perfectly-formed code and masked all
# three; each pin below replays the exact reply shape gemma4 actually produced.


def test_single_function_patch_calling_card_helpers_executes(bridge_on):
    """Purpose: pin the v2 paint failure — a patch that returns ONLY the core
    function and calls card helpers (`_infer_fill_color`, `paint_plan`) that
    exist nowhere in its own code must execute via the `_card_prelude`.

    Expected feedback: pass ⇒ the sandbox provisions the card's real helpers
    (patch styles 'single function' are viable); fail ⇒ prelude wiring broke
    and every single-function patch will NameError again (v2 regression)."""
    patch = (
        "def paint_core(current_frame, transitions, act, trace=None):\n"
        "    frame = np.asarray(current_frame)\n"
        "    _infer_fill_color(transitions)\n"
        "    clicks = paint_plan(frame, trace=trace)\n"
        "    for (x, y) in clicks[:2]:\n"
        "        act('CLICK', x, y)\n"
    )
    frame = np.zeros((8, 8), dtype=np.int16)
    frame[2:5, 2:5] = 3
    res = ppl.run_patched_step(patch, "paint_core", frame, [],
                               prelude=ppl._card_prelude("paint", "paint_core"))
    assert res.error == ""
    assert res.actions


def test_patched_constant_is_seen_by_prelude_helpers(bridge_on):
    """Purpose: pin the v2 toggle patch STYLE — a patch that overrides a card
    CONSTANT (`_MAX_STENCIL = 1024`) after the prelude must have that value
    honoured by prelude-defined helpers (call-time global lookup).

    Expected feedback: pass ⇒ constant-only patches (gemma4's actual vc33 fix)
    take effect; fail ⇒ prelude/patch ordering broke and constant patches are
    silently inert — worse than crashing, they'd measure as PARENT_HOLDS."""
    patch = (
        "_MAX_STENCIL = 1024\n"
        "def toggle_core(current_frame, transitions, act, trace=None):\n"
        "    s = _stencils_from_transitions(transitions)\n"
        "    # a 20-cell flip is ONLY a stencil under the patched cap\n"
        "    act('CLICK', len(s), 0)\n"
    )
    before = np.zeros((8, 8), dtype=np.int16)
    after = before.copy()
    after[0:4, 0:5] = 1  # 20 cells flipped — over the original 12-cap
    trans = [{"action": "CLICK", "xy": [3, 3], "before": before.tolist(),
              "after": after.tolist()}]
    res = ppl.run_patched_step(patch, "toggle_core", before, trans,
                               prelude=ppl._card_prelude("toggle", "toggle_core"))
    assert res.error == ""
    # stencil learned under the patched cap ⇒ click at x=1 (len(s)==1)
    assert res.actions == [("ACTION6", (1, 0))]


def test_missing_future_import_patch_still_executes(bridge_on):
    """Purpose: pin the v1 failure — a patch that keeps the card's annotated
    signature but omits `from __future__ import annotations` must not NameError
    on `Any`/`Callable` at def time (the driver prepends the future import).

    Expected feedback: pass ⇒ annotation-carrying patches execute; fail ⇒ the
    v1 PATCH_INVALID(execute)-on-everything regression is back."""
    patch = (
        "def toggle_core(\n"
        "    current_frame: Any,\n"
        "    transitions: list[dict[str, Any]],\n"
        "    act: Callable[..., None],\n"
        "    trace: list[str] | None = None,\n"
        ") -> None:\n"
        "    act('CLICK', 3, 3)\n"
    )
    res = ppl.run_patched_step(patch, "toggle_core",
                               np.zeros((8, 8), dtype=np.int16), [],
                               prelude=ppl._card_prelude("toggle", "toggle_core"))
    assert res.error == ""
    assert res.actions == [("ACTION6", (3, 3))]


def test_truncated_reply_fails_parse_not_execute():
    """Purpose: pin the v2 toggle TRANSPORT failure — a reply cut mid-function
    (opening fence never closed, as produced by num_predict=1024 truncation)
    must be rejected at the PARSE stage with a clear message, never reach the
    sandbox.

    Expected feedback: pass ⇒ truncation is attributed to the harness transport
    stage (fixable by output budget), not misattributed to the model's code;
    fail ⇒ the validator's fence contract changed."""
    truncated = "```python\ndef toggle_core(current_frame, transitions, act):\n    s = _sten"
    code, err = ppl.validate_patch(truncated, "toggle_core")
    assert code is None
    assert "fenced" in err


def test_full_card_patch_with_own_future_import_executes(bridge_on):
    """Purpose: pin the v3 toggle failure — a full-card-style patch that carries
    its OWN `from __future__ import annotations` must not SyntaxError when the
    prelude precedes it (the driver strips the patch's future import; its own
    copy is already first in the file).

    Expected feedback: pass ⇒ full-card patches (gemma4's actual v2/v3 vc33
    style) execute; fail ⇒ the 6th harness edge is back and every full-card
    patch dies at execute."""
    patch = (
        "from __future__ import annotations\n"
        "_MAX_STENCIL = 1024\n"
        "def toggle_core(current_frame, transitions, act, trace=None):\n"
        "    act('CLICK', 5, 5)\n"
    )
    res = ppl.run_patched_step(patch, "toggle_core",
                               np.zeros((8, 8), dtype=np.int16), [],
                               prelude=ppl._card_prelude("toggle", "toggle_core"))
    assert res.error == ""
    assert res.actions == [("ACTION6", (5, 5))]


def test_card_prelude_tolerates_string_registry_entries():
    """Purpose: pin the D5 v2 simdfs-arm crash — _CARD_FNS registries may hold
    raw source STRINGS alongside callables; _card_prelude must include them
    verbatim instead of calling __name__ on them (AttributeError on str).

    Expected feedback: pass ⇒ every registered card's prelude assembles and
    parses; fail ⇒ any string-bearing registry (simdfs) crashes the patch path
    again at adaptation time."""
    import ast

    from admorphiq.tools import solver_core as sc

    for tool in sc._CARD_FNS:
        core_fn = {"toggle": "toggle_core", "paint": "paint_core",
                   "arrangement": "arrangement_core", "simdfs": "simdfs_core",
                   "simdfs_skel": "simdfs_skel_core"}[tool]
        prelude = ppl._card_prelude(tool, core_fn)
        ast.parse(prelude)
        assert f"def {core_fn}(" not in prelude
