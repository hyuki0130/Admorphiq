"""Contract tests for the adaptive multi-config EWM synthesizer (R52 / US-2)."""

from __future__ import annotations

import numpy as np

from admorphiq.ewm.core import Transition
from admorphiq.ewm.synthesizer import (
    DEFAULT_CONFIGS,
    SynthesisConfig,
    synthesize_world_model,
)

GOOD = (
    "```python\n"
    "def predict_next_frame(frame, action, xy=None):\n"
    "    out = [row[:] for row in frame]\n"
    "    out[0][0] = 1\n"
    "    return out\n"
    "```"
)
BAD = "```python\ndef predict_next_frame(frame, action, xy=None):\n    return frame\n```"
BROKEN = "```python\ndef predict_next_frame(frame, action, xy=None:\n```"


def _transitions(n: int = 3) -> list[Transition]:
    z = np.zeros((4, 4), dtype=np.int16)
    a = z.copy()
    a[0, 0] = 1
    return [Transition(frame=z, action_idx=0, next_frame=a) for _ in range(n)]


class ScriptedLLM:
    """Replays a fixed reply sequence and records every prompt it was given."""

    def __init__(self, replies: list[str]):
        self._replies = iter(replies)
        self.seen: list[list[dict]] = []

    def __call__(self, messages, model, max_tokens):
        self.seen.append(messages)
        return next(self._replies), {}


def test_higher_fit_config_wins_and_early_exit_stops_calls():
    """Purpose: the synthesizer must pick the config/round whose candidate fits
    the FULL observation set best, and stop calling the LLM once fit_target is
    reached (runtime budget guard).

    Expected feedback: pass ⇒ adaptive selection works and perfect-fit early
    exit saves LLM calls; fail ⇒ either a worse config is deployed or budget
    is wasted after a perfect rule is found.
    """
    configs = (
        SynthesisConfig("weak", few=3, rounds=1),
        SynthesisConfig("strong", few=3, rounds=1),
    )
    llm = ScriptedLLM([BAD, BAD, GOOD, BAD])  # weak r0/r1, strong r0 perfect
    res = synthesize_world_model(_transitions(), llm, "mock", configs=configs)
    assert res is not None
    assert res.config.name == "strong"
    assert res.train_fit == 1.0
    assert len(llm.seen) == 3  # early exit: strong r1 never requested


def test_invalid_late_round_does_not_poison_selection():
    """Purpose: a late refinement round that emits uncompilable code (the qwen
    tu93 empty-final-round class) must not displace an earlier valid candidate.

    Expected feedback: pass ⇒ keep-best survives broken late generations;
    fail ⇒ the deployed model can be a syntax error.
    """
    configs = (SynthesisConfig("only", few=3, rounds=2),)
    llm = ScriptedLLM([GOOD, BROKEN, BROKEN])
    res = synthesize_world_model(_transitions(), llm, "mock", configs=configs)
    assert res is not None
    assert res.train_fit == 1.0
    assert res.round == 0


def test_mechanics_prior_only_in_prior_configs():
    """Purpose: prior-enabled configs must inject the mechanic vocabulary into
    the system prompt and plain configs must not — keeping the R51 axes
    isolated at runtime exactly as they were measured.

    Expected feedback: pass ⇒ config prompts match the benched protocol;
    fail ⇒ runtime behavior diverges from what R51 measured.
    """
    configs = (
        SynthesisConfig("plain", few=3, rounds=0),
        SynthesisConfig("primed", few=3, rounds=0, mechanics_prior=True),
    )
    llm = ScriptedLLM([BAD, BAD])
    synthesize_world_model(_transitions(), llm, "mock", configs=configs)
    plain_sys = llm.seen[0][0]["content"]
    primed_sys = llm.seen[1][0]["content"]
    assert "Sokoban-like" not in plain_sys
    assert "Sokoban-like" in primed_sys


def test_default_configs_cover_measured_union():
    """Purpose: pin the deployed config set to the three whose per-game union
    R51 measured (f15 / f40 / prior) so a silent edit can't shrink coverage.

    Expected feedback: pass ⇒ runtime tries exactly the measured configs;
    fail ⇒ the adaptive union the design depends on is no longer explored.
    """
    names = [c.name for c in DEFAULT_CONFIGS]
    assert names == ["f15", "f40", "prior"]
    assert DEFAULT_CONFIGS[1].few == 40
    assert DEFAULT_CONFIGS[2].mechanics_prior is True
