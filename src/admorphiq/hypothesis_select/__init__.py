"""R95a discriminative-selection templates (part 1, no LLM).

A :class:`~admorphiq.hypothesis_select.templates.HypothesisTemplate` is a
finite, hand-authored candidate mechanic hypothesis for one game: the
known-correct ORACLE plus 3-5 hard negatives. Each template exposes two pure
prediction functions — ``predict_click`` (which cells an ACTION6 click is
expected to change) and ``predict_win`` (whether a board frame is a
winning/cast state) — that ``scripts/probe_hypothesis_select.py`` scores on
held-out recorded transitions against an exhaustive replay-ranking baseline.

Design source: ``docs/design_hypothesis_dsl_r95.md`` (sections "R95a —
discriminative selection test" and "R95a candidate template sets").
"""

from admorphiq.hypothesis_select.templates import (
    HypothesisTemplate,
    ft09_oracle_name,
    ft09_templates,
    sc25_oracle_name,
    sc25_templates,
    state_signature_for,
    templates_for_game,
)

__all__ = [
    "HypothesisTemplate",
    "ft09_oracle_name",
    "ft09_templates",
    "sc25_oracle_name",
    "sc25_templates",
    "state_signature_for",
    "templates_for_game",
]
