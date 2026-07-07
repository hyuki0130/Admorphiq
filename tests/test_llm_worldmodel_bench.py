"""Unit tests for the R49 executable-world-model LLM-selection benchmark.

These tests exercise the non-LLM machinery — serialization, sandboxed
execution, scoring math, and prompt construction — so the bench's measurements
are trustworthy before any live model runs. No Ollama call is made; the model is
mocked via an injected chat function.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "llm_worldmodel_bench.py"
_SPEC = importlib.util.spec_from_file_location("llm_worldmodel_bench", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
_MOD = importlib.util.module_from_spec(_SPEC)
sys.modules["llm_worldmodel_bench"] = _MOD
_SPEC.loader.exec_module(_MOD)


# ─────────────────────────────────────────────────────────────────────────────
# Serialization round-trips
# ─────────────────────────────────────────────────────────────────────────────
def test_grid_serialization_round_trips():
    """Purpose: prove serialize_grid/parse_grid are exact inverses for 0-15 cells.

    Expected feedback: pass ⇒ the compact hex encoding shown to the LLM loses no
    information; fail ⇒ the initial-frame context is corrupted, invalidating any
    downstream model behaviour.
    """
    rng = np.random.RandomState(1)
    frame = rng.randint(0, 16, size=(64, 64)).astype(np.int16)
    restored = _MOD.parse_grid(_MOD.serialize_grid(frame))
    assert restored.shape == (64, 64)
    assert np.array_equal(restored, frame)


def test_diff_apply_round_trips():
    """Purpose: prove diff_cells + apply_diff reconstruct the exact next frame.

    Expected feedback: pass ⇒ the {action, changed} transition encoding is a
    lossless representation of a transition; fail ⇒ few-shot examples would
    misrepresent the game's dynamics to the model.
    """
    before = np.zeros((64, 64), dtype=np.int16)
    after = before.copy()
    after[3, 5] = 7
    after[10, 0] = 15
    cells = _MOD.diff_cells(before, after)
    assert cells == [[3, 5, 0, 7], [10, 0, 0, 15]]
    assert np.array_equal(_MOD.apply_diff(before, cells), after)


def test_action_decoding_simple_and_click():
    """Purpose: pin the combined-logit → (action, xy) convention shared with
    collect_transitions.py (idx 0-4 simple, idx 5 + y*64 + x = click).

    Expected feedback: pass ⇒ actions passed to the generated function match the
    data's encoding; fail ⇒ every prediction would be scored against the wrong
    action, silently zeroing accuracy.
    """
    assert _MOD.action_call_args(0) == ("ACTION1", None)
    assert _MOD.action_call_args(4) == ("ACTION5", None)
    # click at x=3, y=2 → idx = 5 + 2*64 + 3
    idx = 5 + 2 * 64 + 3
    assert _MOD.action_call_args(idx) == ("ACTION6", (3, 2))
    assert _MOD.action_label(idx) == "ACTION6(3,2)"
    assert _MOD.action_label(2) == "ACTION3"


# ─────────────────────────────────────────────────────────────────────────────
# Sandbox execution
# ─────────────────────────────────────────────────────────────────────────────
_GOOD_FN = """
def predict_next_frame(frame, action, xy=None):
    out = [row[:] for row in frame]
    if action == "ACTION6" and xy is not None:
        x, y = xy
        out[y][x] = 9
    return out
"""


def test_sandbox_runs_known_good_function():
    """Purpose: a well-formed generated function compiles, loads, and predicts.

    Expected feedback: pass ⇒ the restricted namespace does not block legitimate
    pure-Python transition code; fail ⇒ the sandbox is too strict and would score
    every candidate as invalid.
    """
    fn = _MOD.compile_predict(_GOOD_FN, timeout=2.0)
    frame = [[0] * 64 for _ in range(64)]
    out = _MOD._run_with_timeout(fn, (frame, "ACTION6", (3, 2)), 2.0)
    grid = _MOD._validate_grid(out, (64, 64))
    assert grid[2, 3] == 9
    assert grid.sum() == 9  # only the clicked cell changed


def test_sandbox_blocks_infinite_loop_via_timeout():
    """Purpose: a looping function is aborted by the per-prediction timeout, not
    left to hang the bench.

    Expected feedback: pass ⇒ a pathological generation degrades to a scored-zero
    case; fail ⇒ one bad model output stalls the entire benchmark.
    """
    def _loop(*_a):
        while True:
            pass

    with pytest.raises(TimeoutError):
        _MOD._run_with_timeout(_loop, ([[0]], "ACTION1", None), 0.3)


def test_sandbox_blocks_malicious_import():
    """Purpose: generated code cannot import os/sys/subprocess in the sandbox.

    Expected feedback: pass ⇒ untrusted model code cannot touch the filesystem or
    shell; fail ⇒ running the bench executes arbitrary model-authored side effects.
    """
    malicious = (
        "def predict_next_frame(frame, action, xy=None):\n"
        "    import os\n"
        "    os.system('echo pwned')\n"
        "    return frame\n"
    )
    fn = _MOD.compile_predict(malicious, timeout=2.0)  # top-level defines fine
    with pytest.raises(ImportError):
        fn([[0]], "ACTION1", None)


def test_sandbox_reports_syntax_error_as_sandbox_error():
    """Purpose: unparseable generations surface as SandboxError, never a crash.

    Expected feedback: pass ⇒ invalid code is a graceful scored-zero; fail ⇒ the
    bench aborts on the first malformed model output.
    """
    with pytest.raises(_MOD.SandboxError):
        _MOD.compile_predict("def predict_next_frame(:\n  pass", timeout=2.0)


# ─────────────────────────────────────────────────────────────────────────────
# Scoring math
# ─────────────────────────────────────────────────────────────────────────────
def _transition(before, after, action_idx=0):
    return _MOD.Transition(
        frame=np.asarray(before, dtype=np.int16),
        action_idx=action_idx,
        next_frame=np.asarray(after, dtype=np.int16),
    )


def test_scoring_math_on_synthetic_cases():
    """Purpose: verify validity/cell/exact math on a hand-built 3-case set where
    the function is exactly right on 1 case and off-by-one-cell on the others.

    Expected feedback: pass ⇒ the headline metrics compute as specified
    (exact = fraction perfect, cell = mean per-cell match); fail ⇒ every reported
    LLM number is arithmetically wrong.
    """
    # 2x2 grids: the function copies frame then sets cell (0,0)=1.
    code = (
        "def predict_next_frame(frame, action, xy=None):\n"
        "    out = [row[:] for row in frame]\n"
        "    out[0][0] = 1\n"
        "    return out\n"
    )
    fn = _MOD.compile_predict(code, timeout=2.0)

    z = [[0, 0], [0, 0]]
    perfect = _transition(z, [[1, 0], [0, 0]])          # matches exactly
    one_off = _transition(z, [[1, 0], [0, 5]])          # 1 of 4 cells wrong
    all_wrong_shapeok = _transition(z, [[0, 0], [0, 0]])  # fn sets (0,0)=1 -> 1 wrong

    res = _MOD.score_predictions(fn, [perfect, one_off, all_wrong_shapeok], timeout=2.0)
    assert res.n == 3
    assert res.code_validity == 1.0  # all three executed + right shape
    assert res.exact_frame_accuracy == pytest.approx(1 / 3)
    # cell match: 4/4 + 3/4 + 3/4 = 2.5 over 3 cases
    assert res.cell_accuracy == pytest.approx(2.5 / 3)
    # two mismatched cases recorded for refinement
    assert len(res.mismatches) == 2


def test_scoring_counts_invalid_function_as_zero():
    """Purpose: an uncompilable / None function scores zero, not an exception.

    Expected feedback: pass ⇒ invalid rounds are quantified (validity 0, exact 0)
    and every held-out case becomes a refinement mismatch; fail ⇒ the refinement
    loop loses its feedback signal on a broken round.
    """
    z = [[0, 0], [0, 0]]
    held = [_transition(z, [[1, 0], [0, 0]]), _transition(z, [[0, 2], [0, 0]])]
    res = _MOD.score_predictions(None, held, timeout=2.0)
    assert res.code_validity == 0.0
    assert res.exact_frame_accuracy == 0.0
    assert res.cell_accuracy == 0.0
    assert len(res.mismatches) == 2
    assert all("error" in m for m in res.mismatches)


# ─────────────────────────────────────────────────────────────────────────────
# Prompt construction
# ─────────────────────────────────────────────────────────────────────────────
def test_observations_block_has_single_initial_frame_and_diffs():
    """Purpose: the few-shot block emits the initial frame ONCE plus one diff line
    per transition (the token-economy contract).

    Expected feedback: pass ⇒ prompts stay compact and structured; fail ⇒ token
    budget blows up or the model loses the per-transition diff structure.
    """
    z = np.zeros((64, 64), dtype=np.int16)
    a = z.copy()
    a[1, 1] = 4
    b = z.copy()
    b[2, 2] = 5
    few = [_transition(z, a, action_idx=0), _transition(z, b, action_idx=1)]
    block = _MOD.build_observations_block(few)
    assert block.count("INITIAL_FRAME") == 1
    assert '"action":"ACTION1"' in block
    assert '"changed":[[1,1,0,4]]' in block
    assert '"changed":[[2,2,0,5]]' in block


def test_refinement_prompt_construction():
    """Purpose: the refinement message includes each mismatch's action, actual
    changed cells, and the prediction (or error), and asks the model to fix.

    Expected feedback: pass ⇒ the model receives actionable per-case feedback to
    climb across rounds; fail ⇒ refinement rounds carry no corrective signal and
    refinement_gain is meaningless.
    """
    mismatches = [
        {"action": "ACTION6(3,2)", "actual_changed": [[2, 3, 0, 9]],
         "pred_changed": [[2, 3, 0, 4]]},
        {"action": "ACTION1", "actual_changed": [[0, 0, 1, 2]],
         "error": "prediction timed out"},
    ]
    prompt = _MOD.build_refinement_prompt("def predict_next_frame(): ...", mismatches)
    assert "ACTION6(3,2)" in prompt
    assert "actual_changed" in prompt
    assert "your_predicted_changed" in prompt
    assert "ERROR: prediction timed out" in prompt
    assert "Fix" in prompt


def test_refinement_prompt_caps_at_three_cases():
    """Purpose: at most 3 mismatched cases are serialized into a refinement prompt.

    Expected feedback: pass ⇒ the feedback prompt stays bounded regardless of how
    many held-out cases failed; fail ⇒ a fully-wrong round produces an oversized
    prompt.
    """
    mismatches = [
        {"action": "ACTION1", "actual_changed": [], "pred_changed": []}
        for _ in range(10)
    ]
    prompt = _MOD.build_refinement_prompt("x", mismatches)
    assert prompt.count("Case ") == 3


# ─────────────────────────────────────────────────────────────────────────────
# Selection determinism
# ─────────────────────────────────────────────────────────────────────────────
def test_select_transitions_is_deterministic_and_prefers_changed():
    """Purpose: the 15/10 split is reproducible for a fixed seed and draws from
    changed transitions first.

    Expected feedback: pass ⇒ re-running the bench compares models on identical
    data; fail ⇒ per-model scores are not comparable across runs.
    """
    n = 60
    rng = np.random.RandomState(0)
    frames = rng.randint(0, 16, size=(n, 64, 64)).astype(np.int16)
    next_frames = frames.copy()
    # Make the first 40 transitions "changed" with small diffs.
    for i in range(40):
        next_frames[i, 0, 0] = (frames[i, 0, 0] + 1) % 16
    data = {"frames": frames, "actions": np.arange(n, dtype=np.int32) % 5,
            "next_frames": next_frames}

    few1, hold1 = _MOD.select_transitions(data, n_few=15, n_hold=10, seed=7)
    few2, hold2 = _MOD.select_transitions(data, n_few=15, n_hold=10, seed=7)
    assert len(few1) == 15 and len(hold1) == 10
    # deterministic
    assert [t.action_idx for t in few1] == [t.action_idx for t in few2]
    assert all(np.array_equal(a.frame, b.frame) for a, b in zip(few1, few2))
    # all 25 picked are from the changed pool (first 40)
    picked = few1 + hold1
    assert all(len(t.changed) > 0 for t in picked)


# ─────────────────────────────────────────────────────────────────────────────
# End-to-end refinement loop with a mocked model (no Ollama)
# ─────────────────────────────────────────────────────────────────────────────
def test_run_model_game_with_mock_chat_records_gain():
    """Purpose: the full round-0 + K-refinement loop runs with a mocked chat that
    returns a bad function first then a correct one, and records the exact-frame
    gain.

    Expected feedback: pass ⇒ the orchestration wires prompt → code → score →
    refine correctly and refinement_gain reflects the R0→RK improvement; fail ⇒
    the reported gain does not track actual round-over-round improvement.
    """
    z = np.zeros((4, 4), dtype=np.int16)
    a = z.copy()
    a[0, 0] = 1
    held = [_transition(z, a) for _ in range(3)]
    few = [_transition(z, a)]

    bad = "```python\ndef predict_next_frame(frame, action, xy=None):\n    return frame\n```"
    good = (
        "```python\n"
        "def predict_next_frame(frame, action, xy=None):\n"
        "    out = [row[:] for row in frame]\n"
        "    out[0][0] = 1\n"
        "    return out\n"
        "```"
    )
    replies = iter([bad, good, good, good])

    def mock_chat(messages, model, max_tokens):
        return next(replies), {"prompt_tokens": 100, "eval_tokens": 50, "latency_s": 0.01}

    rec = _MOD.run_model_game(mock_chat, "mock", "toy", few, held, rounds=3,
                              max_tokens=256, timeout=1.0)
    assert rec["rounds"][0]["exact_frame_accuracy"] == 0.0  # bad function
    assert rec["final"]["exact_frame_accuracy"] == 1.0      # corrected
    assert rec["refinement_gain"] == pytest.approx(1.0)
    assert rec["total_prompt_tokens"] == 400  # 4 calls * 100


def test_selected_round_is_best_train_fit_not_last():
    """Purpose: the deploy policy must pick the round with the best few-shot
    (train) fit, not the last round — a late refinement that regresses (gemma4
    su15 0.60→0.00) or emits invalid code (qwen tu93 empty final round) must
    not poison the deployed function. Selection uses only train labels, so it
    is leakage-free and Kaggle-runtime-realizable.

    Expected feedback: pass ⇒ record["selected"] carries the good mid-round
    code while record["final"] shows the regressed last round; fail ⇒ the
    keep-best-by-train-fit policy silently degraded to keep-last.
    """
    z = np.zeros((4, 4), dtype=np.int16)
    a = z.copy()
    a[0, 0] = 1
    held = [_transition(z, a) for _ in range(3)]
    few = [_transition(z, a)]

    good = (
        "```python\n"
        "def predict_next_frame(frame, action, xy=None):\n"
        "    out = [row[:] for row in frame]\n"
        "    out[0][0] = 1\n"
        "    return out\n"
        "```"
    )
    bad = "```python\ndef predict_next_frame(frame, action, xy=None):\n    return frame\n```"
    replies = iter([bad, good, bad, bad])  # peak at round 1, regress after

    def mock_chat(messages, model, max_tokens):
        return next(replies), {"prompt_tokens": 1, "eval_tokens": 1, "latency_s": 0.0}

    rec = _MOD.run_model_game(mock_chat, "mock", "toy", few, held, rounds=3,
                              max_tokens=256, timeout=1.0)
    assert rec["final"]["exact_frame_accuracy"] == 0.0
    assert rec["selected"]["round"] == 1
    assert rec["selected"]["train_exact"] == 1.0
    assert rec["selected"]["exact_frame_accuracy"] == 1.0
