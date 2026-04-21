"""Wiki-First Routing contract test.

Enforces the .wiki/wiki/architecture.md rule: `WikiAgent.classify()`
must return exactly what the LLM emitted, filtered only by the live
strategy whitelist. No Python helper may mutate `primary_strategy` or
`fallback_stack` after the whitelist filter — regardless of the helper's
name.

Each test carries Purpose + Expected-feedback docstrings per the
Implementation Discipline in CLAUDE.md. These tests are NOT feedback-
gated: they are durable contracts that outlive any single round.
"""

from __future__ import annotations

from typing import Any

from admorphiq.hypothesis.wiki_agent import DiscoveryReport, WikiAgent


class _FixedLLM:
    """Minimal LLM stub that always emits the same raw JSON string.

    The real :class:`OllamaBackend` calls a remote HTTP endpoint; the
    contract test must stay hermetic. This stub implements only what
    `WikiAgent.classify()` consumes: a single `generate(...)` returning
    a raw string. Schema / max_tokens args are accepted but ignored.
    """

    def __init__(self, raw: str) -> None:
        self.raw = raw
        self.last_prompt: str | None = None
        self.last_schema: Any = None

    def generate(self, prompt: str, *, max_tokens: int = 512, json_schema: Any = None) -> str:
        self.last_prompt = prompt
        self.last_schema = json_schema
        return self.raw


def _registry(names: list[str]) -> dict[str, Any]:
    """Build a minimal strategy registry. The callables are never invoked
    by classify(); they only need to exist as dict values so the enum is
    populated."""
    def _noop(env: Any, budget: int, ctx: dict[str, Any]) -> tuple[int, str, int]:
        return (0, "noop", 0)

    return {n: _noop for n in names}


def _report(title: str = "UNKNOWN", **overrides: Any) -> DiscoveryReport:
    defaults = dict(
        game_title=title,
        available_actions=[1, 2, 3, 4, 6],
        layer_count=1,
        dominant_colors=[],
        probe_diffs={1: 1, 2: 1, 3: 201, 4: 201, 6: 1, -6: 5},
        reset_levels=0,
        frame_shape=(64, 64),
    )
    defaults.update(overrides)
    return DiscoveryReport(**defaults)


def test_classify_returns_llm_primary_unchanged():
    """Purpose: when the LLM picks a whitelisted primary, classify() must
    return that primary verbatim. Any Python post-processing that replaces
    the primary with a hand-picked alternative (by title, probe signature,
    or any other rule) is a Wiki-First Routing violation.

    Expected feedback: if this fails, some helper in wiki_agent.py is
    mutating primary_strategy after the whitelist filter. Remove the
    helper; move the routing decision into selector.md or a reasoning
    page so the LLM makes it.
    """
    raw = (
        '{"game_type":"click","primary_strategy":"click_select_move",'
        '"fallback_stack":["click_toggle_detect","click_color_order"],'
        '"rationale":"x","confidence":0.5}'
    )
    agent = WikiAgent(
        _FixedLLM(raw),
        _registry(["click_select_move", "click_toggle_detect", "click_color_order", "paint_game", "bfs_state_space"]),
    )
    hyp = agent.classify(_report(title="CD82"))
    assert hyp.primary_strategy == "click_select_move"


def test_classify_preserves_llm_fallback_order_and_contents():
    """Purpose: fallback_stack must be exactly what the LLM emitted (in
    order), minus any invalid names. No Python layer may reorder, prepend,
    append, or inject strategies — even ones that happen to match a probe
    signature.

    Expected feedback: if this fails, some helper is prepending / appending
    strategies to fallback_stack (e.g., injecting paint_game for CD82-like
    signatures). Remove it; teach the rule to Qwen via wiki instead.
    """
    raw = (
        '{"game_type":"hybrid","primary_strategy":"explore_and_interact",'
        '"fallback_stack":["click_toggle_detect","move_then_click_grid"],'
        '"rationale":"x","confidence":0.5}'
    )
    agent = WikiAgent(
        _FixedLLM(raw),
        _registry(["explore_and_interact", "click_toggle_detect", "move_then_click_grid", "paint_game", "bfs_state_space"]),
    )
    hyp = agent.classify(_report(title="AR25"))
    assert hyp.fallback_stack == ["click_toggle_detect", "move_then_click_grid"]


def test_classify_drops_invalid_names_but_does_not_add():
    """Purpose: the sole permitted Python transformation after decoding is
    removing names not in the live whitelist. Names outside the whitelist
    become an empty primary (the run() loop then advances to fallbacks)
    or are dropped from fallback_stack. Under no circumstance does
    classify() replace a dropped name with a hand-picked substitute.

    Expected feedback: if this fails, the whitelist filter has been
    replaced by something that substitutes an alternative strategy name
    — that is routing logic and belongs in the LLM + wiki, not Python.
    """
    raw = (
        '{"game_type":"unknown","primary_strategy":"seq_search",'
        '"fallback_stack":["click_rare","hallucinated_x"],'
        '"rationale":"x","confidence":0.2}'
    )
    agent = WikiAgent(
        _FixedLLM(raw),
        _registry(["click_rare", "bfs_state_space", "paint_game"]),
    )
    hyp = agent.classify(_report())
    assert hyp.primary_strategy == ""
    assert hyp.fallback_stack == ["click_rare"]


def test_classify_is_title_blind():
    """Purpose: `game_title` MUST NOT influence classify()'s output. The
    LLM can read the title from the prompt and reason about it via the
    wiki, but Python code reading `report.game_title` to steer the pick
    is Kaggle-invisible hardcoding (titles are obfuscated there).

    The invariant: same LLM output + same whitelist → same Hypothesis,
    regardless of title. Two classify() calls with identical mock LLM
    responses but different titles (including titles that historically
    triggered title-match augmentation like "SB26", "SU15") must return
    byte-identical primary_strategy and fallback_stack.

    Expected feedback: if this fails, a Python helper is branching on
    `report.game_title`. Remove it; the LLM already sees the title in
    its prompt and can use it via the wiki if that is warranted.
    """
    raw = (
        '{"game_type":"click","primary_strategy":"click_rare",'
        '"fallback_stack":["click_color_order"],'
        '"rationale":"x","confidence":0.3}'
    )
    agent = WikiAgent(
        _FixedLLM(raw),
        _registry(["click_rare", "click_color_order", "sb26_sort", "su15_frame_only", "su15_vacuum"]),
    )
    hyp_unknown = agent.classify(_report(title="UNKNOWN"))
    hyp_sb26 = agent.classify(_report(title="SB26"))
    hyp_su15 = agent.classify(_report(title="SU15"))
    assert hyp_unknown.primary_strategy == hyp_sb26.primary_strategy == hyp_su15.primary_strategy == "click_rare"
    assert (
        hyp_unknown.fallback_stack
        == hyp_sb26.fallback_stack
        == hyp_su15.fallback_stack
        == ["click_color_order"]
    )


def test_classify_is_probe_signature_blind():
    """Purpose: probe signatures (avail == [6], avail ⊇ {1..4} ∪ {6},
    click responsiveness, etc.) MUST NOT influence classify()'s output
    through Python. The LLM can read the probes from the prompt and
    reason via `selector.md`; Python branches that inject strategies
    for a specific signature are prohibited.

    Invariant: two reports with different signatures but identical LLM
    output produce identical Hypothesis objects. Historically these
    signatures triggered _augment_click_only_rule4 and _augment_hybrid_rule3
    — those helpers are now banned.

    Expected feedback: if this fails, a probe-signature branch in Python
    is still mutating the output. Move the rule into selector.md (or a
    reasoning page) with the discriminating signal explained so Qwen
    applies it at the LLM layer.
    """
    raw = (
        '{"game_type":"click","primary_strategy":"click_rare",'
        '"fallback_stack":["click_color_order"],'
        '"rationale":"x","confidence":0.3}'
    )
    agent = WikiAgent(
        _FixedLLM(raw),
        _registry(["click_rare", "click_color_order", "lights_out", "paint_game", "bfs_state_space", "click_toggle_detect"]),
    )
    # Signature 1: rule-4 shape (click-only, no response)
    hyp_rule4 = agent.classify(
        _report(available_actions=[6], probe_diffs={6: 0, -6: 0})
    )
    # Signature 2: rule-3 shape (hybrid)
    hyp_rule3 = agent.classify(
        _report(available_actions=[1, 2, 3, 4, 6], probe_diffs={1: 100, 2: 100, 3: 100, 4: 100, 6: 0, -6: 0})
    )
    # Signature 3: CD82-style paint-hybrid
    hyp_paint = agent.classify(
        _report(available_actions=[1, 2, 3, 4, 5, 6], probe_diffs={1: 1, 2: 1, 3: 201, 4: 201, 6: 1, -6: 5})
    )
    assert (
        hyp_rule4.primary_strategy
        == hyp_rule3.primary_strategy
        == hyp_paint.primary_strategy
        == "click_rare"
    )
    assert (
        hyp_rule4.fallback_stack
        == hyp_rule3.fallback_stack
        == hyp_paint.fallback_stack
        == ["click_color_order"]
    )


def test_classify_does_not_fill_empty_primary_from_python():
    """Purpose: when the LLM emits an empty primary or the whitelist
    filter empties it (invalid name), classify() leaves it empty. The
    run() loop will advance to the first valid fallback. No Python
    helper may fabricate a primary from `report.game_title`, probe
    signatures, or any heuristic.

    Expected feedback: if primary becomes non-empty after the filter
    dropped an invalid name, a helper (title-match, signature-match,
    or otherwise) is fabricating picks. Remove it.
    """
    raw = (
        '{"game_type":"unknown","primary_strategy":"definitely_not_whitelisted",'
        '"fallback_stack":[],'
        '"rationale":"x","confidence":0.0}'
    )
    agent = WikiAgent(
        _FixedLLM(raw),
        _registry(["click_rare", "sb26_sort", "su15_frame_only", "bfs_state_space"]),
    )
    hyp = agent.classify(_report(title="SB26"))
    assert hyp.primary_strategy == ""
    assert hyp.fallback_stack == []
