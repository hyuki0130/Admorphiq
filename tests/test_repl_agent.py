"""End-to-end tests for the ReplAgent loop assembly (R55 module 6).

These drive the full code-REPL loop offline with a scripted MockLLM (no network)
over synthetic frames, exercising every wired path the design requires: a
sandbox inspection round-trip, a governed action, a rejected illegal action
(falling back safely), a macro that stops on surprise, and transcript
record→replay equality. Passing means the Kaggle LLM wiring is a pure client
swap — the harness logic is proven independent of any model.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import numpy as np

import admorphiq.repl_agent.agent as agent_mod
from admorphiq.repl_agent.agent import (
    MockLLM,
    OpenAICompatClient,
    ReplAgent,
    normalize_parse,
    parse_model_output,
    parse_prediction,
    strip_thinking,
)
from admorphiq.repl_agent.transcript import TranscriptRecorder, TranscriptReplayer

# Sanitized tail of our OWN first-run dc22 output (thinking mode on): a long
# <think> block ending </think>, then the bare-text action the model naturally
# emitted. The v3 parser must recover the action from this shape.
_DC22_TAIL = (
    "<think>\n"
    "The red target spans x:34-38, y:42-54. Safe click [35, 46] is inside.\n"
    "coordinate_rule: MOUSE(row, col), zero-based. Row is y, col is x.\n"
    "MOUSE(46, 35) is correct. Final Answer.\n"
    "</think>\n\n"
    "MOUSE(46, 35)"
)


def _obs(frame, state="PLAYING", avail=(3, 4, 6), levels=0):
    return SimpleNamespace(
        frame=frame,
        state=SimpleNamespace(name=state),
        available_actions=list(avail),
        levels_completed=levels,
    )


def _frame(obj_col: int = 5) -> np.ndarray:
    f = np.zeros((16, 16), dtype=np.int64)
    f[5, obj_col] = 2
    f[5, obj_col + 1] = 2
    return f


# ----- parse ------------------------------------------------------------------
def test_parse_code_and_action_and_macro():
    """Purpose: the parser distinguishes a code block, an action JSON, and a
    macro JSON deterministically.

    Feedback: failure means the loop routes the model output to the wrong path.
    """
    assert parse_model_output("```python\naction('LEFT')\n```").kind == "code"
    assert parse_model_output('{"action":"LEFT"}').kind == "actions"
    assert parse_model_output('{"macro":[{"action":"UP"}]}').kind == "macro"
    assert parse_model_output("no structure here").kind == "none"


def test_strip_thinking():
    """Purpose: a <think>…</think> block is removed before parsing; an unclosed
    block yields no answer.

    Feedback: failure means 9-11k chars of CoT reach the parser and swamp it
    (the first-run bug).
    """
    assert strip_thinking("<think>reasoning</think>\nMOUSE(1, 2)") == "MOUSE(1, 2)"
    assert strip_thinking("no think here") == "no think here"
    assert strip_thinking("<think>truncated cot with no close") == ""


def test_parse_bare_text_action_from_real_dc22_tail():
    """Purpose: the v3 parser recovers the bare-text MOUSE action our own model
    emitted after </think> (the first-run parse failure).

    Feedback: failure means near-successful turns (perception + reasoning worked)
    are still dropped as parse failures.
    """
    p = parse_model_output(_DC22_TAIL)
    assert p.kind == "actions"
    assert p.actions == [{"action": "MOUSE", "row": 46, "col": 35}]


def test_parse_bare_movement_word():
    """Purpose: a lone movement word on the last line parses as that action.

    Feedback: failure means simple movement replies are dropped.
    """
    p = parse_model_output("Some reasoning about the maze.\nLEFT")
    assert p.kind == "actions"
    assert p.actions == [{"action": "LEFT"}]


def test_json_preferred_over_bare_text():
    """Purpose: a valid JSON action still wins over the bare-text fallback.

    Feedback: failure means the requested output contract is overridden.
    """
    p = parse_model_output('reasoning\n{"action":"MOUSE","row":1,"col":2}\nMOUSE(9, 9)')
    assert p.actions == [{"action": "MOUSE", "row": 1, "col": 2}]


def test_openai_client_disables_thinking_and_caps_tokens(monkeypatch):
    """Purpose: the client sends enable_thinking=false + a max_tokens cap + the
    300s timeout (the v3 latency fix), with no network in the test.

    Feedback: failure means the deploy client re-enables the CoT that timed out.
    """
    captured: dict = {}

    class _FakeResp:
        status = 200

        def read(self):
            return json.dumps({"choices": [{"message": {"content": "UP"}}]}).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def _fake_urlopen(req, timeout=None):
        captured["body"] = json.loads(req.data.decode())
        captured["timeout"] = timeout
        return _FakeResp()

    monkeypatch.setenv("REPL_LLM_BASE_URL", "http://x/v1")
    monkeypatch.setattr(agent_mod.urllib.request, "urlopen", _fake_urlopen)
    client = OpenAICompatClient(model="qwen")
    assert client.complete("hi") == "UP"
    assert captured["body"]["chat_template_kwargs"] == {"enable_thinking": False}
    assert captured["body"]["max_tokens"] == 1536
    assert captured["timeout"] == 300.0


def test_causal_feedback_in_last_action_and_recent():
    """Purpose: LAST_ACTION carries the action + coords + source + outcome, and
    RECENT_TRANSITIONS is serialized (v5 restores the causal history Qwen was
    reverse-engineering).

    Feedback: failure means the model can't see where its click landed or whether
    it worked.
    """
    prompts = []

    def capture(prompt, images=None):
        prompts.append(prompt)
        return '{"action":"MOUSE","row":10,"col":12}'

    agent = ReplAgent(SimpleNamespace(complete=capture), render_images=False,
                      game_id="g1")
    agent.choose_action([], _obs(_frame(obj_col=5)))          # MOUSE(10,12)
    agent.choose_action([], _obs(_frame(obj_col=7)))          # frame changed
    p = prompts[-1]
    # LAST_ACTION shows the prior MOUSE coords, its source, and the outcome.
    assert "row: 10" in p and "col: 12" in p
    assert "source: llm" in p
    assert "board_changed: true" in p
    assert "RECENT_TRANSITIONS" in p
    assert "game_id: g1" in p  # defect #10 fixed


def test_image_is_wired_into_the_call():
    """Purpose: the agent renders the frame and sends it as an image (v5 made it
    a multimodal agent instead of text-only complete(prompt, None)).

    Feedback: failure means we ship a text-only policy, not the multimodal REPL
    agent the design requires.
    """
    seen = {}

    def capture(prompt, images=None):
        seen["images"] = images
        return '{"action":"UP"}'

    ag = ReplAgent(SimpleNamespace(complete=capture))
    ag.choose_action([], _obs(_frame(), avail=(1, 2, 3, 4)))
    assert isinstance(seen["images"], list) and len(seen["images"]) == 1
    assert isinstance(seen["images"][0], str) and seen["images"][0]  # base64 PNG
    rec_agent = ReplAgent(SimpleNamespace(complete=capture), render_images=False)
    rec_agent.choose_action([], _obs(_frame(), avail=(1, 2, 3, 4)))
    assert seen["images"] is None  # JSON-only arm sends no image


def test_prompt_describes_repl_and_binds_legal_actions():
    """Purpose: the v4 prompt tells the model the REPL/inspection API exists and
    forbids MOUSE when it is not legal.

    Feedback: failure means the model stays blind to the sandbox (v3 used it 0
    times) and keeps proposing illegal clicks on movement games.
    """
    seen = {}

    def capture(prompt, images=None):
        seen["prompt"] = prompt
        return '{"action":"UP"}'

    ag = ReplAgent(SimpleNamespace(complete=capture))
    ag.choose_action([], _obs(_frame(), avail=(1, 2, 3, 4)))  # movement only, no MOUSE
    p = seen["prompt"]
    assert "python" in p and "objects(" in p and "action(" in p
    assert "MOUSE is NOT available" in p  # legal-action binding


def test_client_captures_usage_and_finish_reason(monkeypatch):
    """Purpose: the client parses vLLM usage (input/output/reasoning/cached) +
    finish_reason into last_meta (truthfulness #1).

    Feedback: failure means the transcript can't show token cost or detect
    length truncation.
    """
    class _FakeResp:
        status = 200

        def read(self):
            return json.dumps({
                "choices": [{"message": {"content": "UP"}, "finish_reason": "length"}],
                "usage": {"prompt_tokens": 1200, "completion_tokens": 1536,
                          "completion_tokens_details": {"reasoning_tokens": 0},
                          "prompt_tokens_details": {"cached_tokens": 800}},
            }).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setenv("REPL_LLM_BASE_URL", "http://x/v1")
    monkeypatch.setattr(agent_mod.urllib.request, "urlopen",
                        lambda req, timeout=None: _FakeResp())
    client = OpenAICompatClient(model="qwen")
    client.complete("hi")
    assert client.last_meta["finish_reason"] == "length"
    assert client.last_meta["tokens"] == {"input": 1200, "output": 1536,
                                          "reasoning": 0, "cached": 800}


def test_agent_records_finish_reason_and_counts_truncation():
    """Purpose: the agent copies finish_reason + tokens into the transcript and
    counts a length-truncation.

    Feedback: failure means the su15 truncation finding can't become a tracked
    metric.
    """
    class _StubLLM:
        last_meta = {"finish_reason": "length", "tokens": {"input": 10, "output": 1536}}

        def complete(self, prompt, images=None):
            return "some reasoning that got cut off"  # no action -> parse fail

    rec = TranscriptRecorder()
    agent = ReplAgent(_StubLLM(), recorder=rec)
    agent.choose_action([], _obs(_frame()))
    assert agent.truncations == 1
    turn = rec.records[-1]
    assert turn.finish_reason == "length"
    assert turn.tokens == {"input": 10, "output": 1536}


def test_parse_prediction():
    """Purpose: a PREDICT line is parsed into {prediction, hypothesis}.

    Feedback: failure means predictions can't be scored against transitions.
    """
    assert parse_prediction("PREDICT: changed — box moves left\nLEFT") == {
        "prediction": "changed", "hypothesis": "box moves left"}
    assert parse_prediction("PREDICT: no_change (wall blocks)\nLEFT")["prediction"] \
        == "no_change"
    assert parse_prediction("just an action\nLEFT") is None


def test_prediction_scored_and_memory_evolves():
    """Purpose: a per-turn PREDICT is scored against the observed change, counted,
    and fed to the falsifiable memory so MEMORY stops being static (the v3 gap).

    Feedback: failure means the causal 'predicted vs actual' account the
    observability directive requires is missing.
    """
    # Turn 1: predict changed + move; turn 2: the frame actually changed.
    llm = MockLLM(["PREDICT: changed — I move right\n{\"action\":\"RIGHT\"}",
                   "PREDICT: no_change\n{\"action\":\"LEFT\"}"])
    agent = ReplAgent(llm)
    agent.choose_action([], _obs(_frame(obj_col=5)))   # sets pending prediction
    agent.choose_action([], _obs(_frame(obj_col=7)))   # frame changed -> score it
    assert agent.predictions_made == 1
    assert agent.predictions_correct == 1               # predicted changed, it did
    mem = agent._memory.to_dict()
    assert mem["goal_hypotheses"]                        # memory is no longer static
    assert mem["goal_hypotheses"][0]["prediction"] == "changed"


def test_llm_error_is_survived_and_recorded():
    """Purpose: a raised LLM call (e.g. a timeout) does NOT end the game — it is
    recorded (latency + error) and the loop falls back to a legal action.

    Feedback: failure means one slow/failed call aborts a whole game (the
    first-run failure mode).
    """
    def boom(prompt, images=None):
        raise TimeoutError("timed out")

    rec = TranscriptRecorder()
    agent = ReplAgent(SimpleNamespace(complete=boom), recorder=rec)
    action = agent.choose_action([], _obs(_frame()))
    assert action is not None                 # game continues via fallback
    assert agent.llm_errors == 1
    turn = rec.records[-1]
    assert "TimeoutError" in turn.sandbox_error
    assert turn.latency_ms >= 0.0


# ----- inspection round-trip + governed action -------------------------------
def test_code_inspection_roundtrip_and_governed_action():
    """Purpose: a model code block that inspects objects() and requests an action
    runs in the sandbox, and the governed action executes.

    Feedback: failure means the code-REPL spine (packet→LLM→sandbox→governor) is
    broken end to end.
    """
    resp = "```python\nobjs = objects(-1)\nprint('seen', len(objs))\naction('LEFT')\n```"
    agent = ReplAgent(MockLLM([resp]), recorder=TranscriptRecorder())
    agent.choose_action([], _obs(_frame()))
    rec = agent._recorder.records[-1]
    assert "seen" in rec.sandbox_stdout
    assert rec.action == {"action": "LEFT"}
    assert agent._governor.total_actions == 1


def test_json_action_governed():
    """Purpose: a direct action JSON is governed and executed.

    Feedback: failure means the JSON (non-code) action path is broken.
    """
    agent = ReplAgent(MockLLM(['{"action":"RIGHT"}']))
    agent.choose_action([], _obs(_frame()))
    assert agent._prev_action == {"action": "RIGHT"}
    assert agent._governor.total_actions == 1


# ----- illegal action rejected -> fallback -----------------------------------
def test_illegal_action_rejected_and_fallback():
    """Purpose: an action not in the legal set (SPACE, when only LEFT/RIGHT/MOUSE
    are legal) is rejected by the governor; the loop falls back to a legal action
    instead of emitting the illegal one.

    Feedback: failure means an illegal action could reach the env, or the loop
    stalls with an empty queue.
    """
    agent = ReplAgent(MockLLM(['{"action":"SPACE"}']), recorder=TranscriptRecorder())
    agent.choose_action([], _obs(_frame(), avail=(3, 4, 6)))
    rec = agent._recorder.records[-1]
    assert rec.action is None              # model's illegal action was NOT accepted
    assert agent._prev_action == {"action": "LEFT"}  # safe fallback executed
    assert agent.llm_calls == 1
    assert agent.governor_rejections >= 1  # observability counter wired


# ----- macro stop-on-surprise -------------------------------------------------
def test_macro_stops_on_surprise():
    """Purpose: an armed 2-step macro predicting a change continues while the
    board changes, then ABORTS when a predicted change fails to occur — after
    which the loop re-decides (a fresh LLM call) instead of running step 2.

    Feedback: failure means a macro whose premise broke keeps executing blindly.
    """
    macro = json.dumps({"macro": [
        {"action": "RIGHT", "precondition": "path clear", "predicted_invariant": "board changes"},
        {"action": "RIGHT", "precondition": "path clear", "predicted_invariant": "board changes"},
    ]})
    llm = MockLLM([macro, '{"action":"LEFT"}'])
    agent = ReplAgent(llm)

    agent.choose_action([], _obs(_frame(obj_col=5)))          # turn1: arm + step1 RIGHT
    assert agent._prev_action == {"action": "RIGHT"}
    assert agent._macro_active is True

    agent.choose_action([], _obs(_frame(obj_col=6)))          # turn2: board changed -> step2 RIGHT
    assert agent._prev_action == {"action": "RIGHT"}
    assert len(llm.calls) == 1                                # no LLM call mid-macro

    agent.choose_action([], _obs(_frame(obj_col=6)))          # turn3: no change -> abort + re-decide
    assert agent._macro_active is False
    assert len(llm.calls) == 2                                # re-decided after the abort
    assert agent._prev_action == {"action": "LEFT"}


# ----- transcript record -> replay equality ----------------------------------
def test_record_then_replay_equality():
    """Purpose: a recorded session replays (re-parses the raw output with no
    model) with zero mismatches.

    Feedback: failure means the transcript is not a faithful, replayable record —
    the scientific-iteration foundation is broken.
    """
    resp = "```python\naction('LEFT')\n```"
    rec = TranscriptRecorder()
    agent = ReplAgent(MockLLM([resp, '{"action":"RIGHT"}']), recorder=rec)
    agent.choose_action([], _obs(_frame(obj_col=5)))
    agent.choose_action([], _obs(_frame(obj_col=7)))
    result = TranscriptReplayer(normalize_parse).replay(rec.records)
    assert result.ok
    assert result.total == len(rec.records) >= 1
