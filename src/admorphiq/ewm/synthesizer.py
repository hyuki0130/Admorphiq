"""Adaptive multi-config world-model synthesis with train-fit selection.

R51 measured that no single prompt config wins everywhere (few=15 beats few=40
on simple-rule games and loses on example-hungry ones; the mechanics prior is
model-dependent), but the per-game best config — selectable by train-fit, a
label the agent owns at runtime — reaches 0.211 vs 0.133 for the best fixed
config. This module is that selector, productized for the runtime agent.

Protocol notes (load-bearing, measured in R50b):
- Refinement feedback comes ONLY from mismatches on transitions the model has
  already seen. There is no held-out concept in this module at all.
- Candidates are scored on the FULL observation set (not just the prompt
  subset), so a config that hard-codes its prompt examples and misses the
  rest loses the selection.
- Selection = argmax(fit, round, config order); late invalid rounds cannot
  poison the result (gemma4 su15 0.60->0.00 regression class).

Game-agnostic: frame observations only — no game ids, no titles.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .core import (
    ChatFn,
    SandboxError,
    Transition,
    build_prompt,
    build_refinement_prompt,
    compile_predict,
    extract_code,
    score_predictions,
)


@dataclass(frozen=True)
class SynthesisConfig:
    """One prompt/refinement configuration to try."""

    name: str
    few: int = 15
    mechanics_prior: bool = False
    rounds: int = 3


# The three configs whose per-game union covered ~90% of the measured R51
# ensemble upper bound with a single model.
DEFAULT_CONFIGS: tuple[SynthesisConfig, ...] = (
    SynthesisConfig("f15", few=15, mechanics_prior=False),
    SynthesisConfig("f40", few=40, mechanics_prior=False),
    SynthesisConfig("prior", few=15, mechanics_prior=True),
)


@dataclass
class WorldModelResult:
    """The selected transition function and its provenance."""

    fn: Callable[..., Any]
    train_fit: float
    cell_fit: float
    config: SynthesisConfig
    round: int
    code: str
    n_observations: int


def _pick_examples(transitions: list[Transition], n: int) -> list[Transition]:
    """Choose up to ``n`` prompt examples, preferring compact informative diffs.

    Changed transitions with small diffs first (they serialize cheaply and
    exercise the dynamics), then larger diffs, then no-ops. Order within each
    band preserves observation order, so the choice is deterministic.
    """
    small = [t for t in transitions if 0 < len(t.changed) <= 80]
    big = [t for t in transitions if len(t.changed) > 80]
    noop = [t for t in transitions if not t.changed]
    return (small + big + noop)[:n]


def synthesize_world_model(
    transitions: list[Transition],
    llm: ChatFn,
    model: str,
    configs: tuple[SynthesisConfig, ...] = DEFAULT_CONFIGS,
    max_tokens: int = 8192,
    timeout: float = 2.0,
    fit_target: float = 1.0,
) -> WorldModelResult | None:
    """Synthesize a ``predict_next_frame`` from the agent's own observations.

    Runs round-0 synthesis + K refinement rounds per config, scores every
    candidate on ALL ``transitions``, and returns the best by
    ``(train_fit, round, config order)``. Stops early once a candidate reaches
    ``fit_target``. Returns ``None`` when no candidate compiles at all.
    """
    best: WorldModelResult | None = None

    for cfg in configs:
        examples = _pick_examples(transitions, cfg.few)
        if not examples:
            continue
        messages = build_prompt(examples, mechanics_prior=cfg.mechanics_prior)
        code = ""
        mismatches: list[dict[str, Any]] = []

        for r in range(cfg.rounds + 1):
            if r > 0:
                messages = messages + [
                    {"role": "assistant", "content": f"```python\n{code}\n```"},
                    {"role": "user",
                     "content": build_refinement_prompt(code, mismatches)},
                ]
            text, _meta = llm(messages, model, max_tokens)
            code = extract_code(text)
            try:
                fn = compile_predict(code, timeout)
            except SandboxError:
                continue
            score = score_predictions(fn, transitions, timeout)
            mismatches = score.mismatches
            candidate = WorldModelResult(
                fn=fn,
                train_fit=score.exact_frame_accuracy,
                cell_fit=score.cell_accuracy,
                config=cfg,
                round=r,
                code=code,
                n_observations=len(transitions),
            )
            # >= so ties go to the LATER candidate (later round, later config)
            # — a fresher equally-fitting rule saw more feedback.
            if best is None or candidate.train_fit >= best.train_fit:
                best = candidate
            if best.train_fit >= fit_target:
                return best

    return best
