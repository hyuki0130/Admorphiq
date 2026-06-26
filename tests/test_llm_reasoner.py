"""Unit tests for the optional LLM reasoning layer (``admorphiq.llm_reasoner``).

These cover the two parts that must work WITHOUT a live LLM:
  * ``build_symbolic_state`` — pure string formatting over plain dicts/arrays;
  * ``hypothesize`` parsing — defensive coercion of (mocked) LLM output.

No test here requires Ollama or a GGUF: the LLM is replaced by a fake object
with a ``generate`` method, so the suite stays offline and deterministic.
"""

from __future__ import annotations

import numpy as np

from admorphiq.llm_reasoner import (
    HYPOTHESIS_SCHEMA,
    build_symbolic_state,
    hypothesize,
)


class _FakeLLM:
    """Minimal LLMBackend stand-in returning a canned ``generate`` response."""

    def __init__(self, response: str) -> None:
        self._response = response
        self.last_prompt: str | None = None
        self.last_schema: dict | None = None

    def generate(self, prompt: str, max_tokens: int = 512, json_schema=None) -> str:
        self.last_prompt = prompt
        self.last_schema = json_schema
        return self._response


def test_build_symbolic_state_is_compact_and_omits_raw_grid():
    """Purpose: the symbolic prompt describes entities + action effects and
    NEVER dumps the raw 64x64 pixel grid (frontier models are ~0% on those).

    Expected feedback: pass means the prompt is a short symbolic summary the
    LLM can reason over; a fail (e.g. a row of pixel values leaking in, or a
    missing entity/effect section) means the prompt would be useless or
    bloated and the whole LLM layer is compromised.
    """
    layer = np.zeros((64, 64), dtype=np.int32)
    layer[10:13, 10:13] = 4  # a 3x3 player blob
    layer[40:42, 40:45] = 7  # a goal-ish blob

    before = layer.copy()
    after = layer.copy()
    after[10:13, 10:13] = 0
    after[10:13, 13:16] = 4  # player shifted right by 3 px
    probes = [{"aid": 2, "before": before, "after": after}]

    text = build_symbolic_state(
        layer, probes, avail=[2, 3], dir_map={2: (3, 0)}, player=4
    )

    # Symbolic content present.
    assert "Grid: 64x64" in text
    assert "Available actions" in text
    assert "color 4" in text and "color 7" in text
    assert "PLAYER" in text
    assert "action 2" in text
    # No raw pixel grid: a 64-cell row of identical values must not appear.
    assert "0 0 0 0 0 0 0 0 0 0" not in text
    # Compact: well under the ~1500-token target (rough char proxy).
    assert len(text) < 4000


def test_hypothesize_parses_clean_json_and_passes_schema():
    """Purpose: a well-formed JSON response round-trips into the typed dict and
    the decoder is invoked with HYPOTHESIS_SCHEMA.

    Expected feedback: pass means a cooperative LLM's output is consumed as-is
    and structured output is requested; a fail means parsing or schema-passing
    regressed and downstream goal selection would get wrong types.
    """
    llm = _FakeLLM(
        '{"goal": "reach the exit", "target_color": 7, '
        '"action_meaning": {"2": "move right"}, "plan": ["go right", "go down"]}'
    )
    hyp = hypothesize("state summary", llm)

    assert hyp["goal"] == "reach the exit"
    assert hyp["target_color"] == 7
    assert hyp["action_meaning"] == {"2": "move right"}
    assert hyp["plan"] == ["go right", "go down"]
    assert llm.last_schema is HYPOTHESIS_SCHEMA


def test_hypothesize_recovers_from_noisy_and_malformed_output():
    """Purpose: parsing is defensive — it extracts JSON embedded in stray text
    and coerces/clears bad field types instead of raising.

    Expected feedback: pass means a messy or partial LLM response degrades to
    safe defaults (empty goal, null target) rather than crashing the agent,
    preserving the deterministic fallback path. A fail signals the LLM layer
    could take down a run on imperfect model output.
    """
    # JSON wrapped in prose + a string target_color that should coerce to int.
    noisy = _FakeLLM(
        'Here is my answer: {"goal": "fill cells", "target_color": "3", '
        '"action_meaning": {}, "plan": []} Thanks!'
    )
    hyp = hypothesize("x", noisy)
    assert hyp["goal"] == "fill cells"
    assert hyp["target_color"] == 3

    # Total garbage → safe defaults, no exception.
    garbage = _FakeLLM("not json at all")
    hyp2 = hypothesize("x", garbage)
    assert hyp2 == {
        "primitive": None,
        "confidence": 0.0,
        "goal": "",
        "target_color": None,
        "action_meaning": {},
        "plan": [],
    }

    # Wrong-typed target_color (float) is rejected to None, not crashed on.
    bad_type = _FakeLLM('{"goal": "g", "target_color": 1.5, "action_meaning": 0, "plan": "single"}')
    hyp3 = hypothesize("x", bad_type)
    assert hyp3["target_color"] is None
    assert hyp3["action_meaning"] == {}
    assert hyp3["plan"] == ["single"]


def test_hypothesize_parses_primitive_selection_and_confidence():
    """Purpose: the LLM-as-selector contract — a hypothesis carries an enum
    ``primitive`` choice and a numeric ``confidence`` that the agent uses to
    decide whether to honour the pick.

    Expected feedback: pass means a clean selection round-trips with the
    primitive kept only when it is one of the four dispatchable names and the
    confidence clamped to [0,1]; a fail means the selector signal the agent
    routes on is being dropped or mistyped, collapsing the LLM back to a
    goal-color nudge.
    """
    llm = _FakeLLM(
        '{"primitive": "toggle", "confidence": 0.82, "goal": "flip all cells", '
        '"target_color": null, "action_meaning": {}, "plan": ["click cells"]}'
    )
    hyp = hypothesize("state", llm)
    assert hyp["primitive"] == "toggle"
    assert hyp["confidence"] == 0.82

    # An invented primitive name is rejected to None (deterministic fallback);
    # an out-of-range confidence is clamped, not crashed on.
    bad = _FakeLLM(
        '{"primitive": "teleport", "confidence": 5, "goal": "g", '
        '"target_color": null, "action_meaning": {}, "plan": []}'
    )
    hyp2 = hypothesize("state", bad)
    assert hyp2["primitive"] is None
    assert hyp2["confidence"] == 1.0
