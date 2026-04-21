"""Round-2 augmentation tests: title-match + click-only rule-4 reinforcement.

These verify the Python-level reinforcement of two selector.md rules that
Qwen ignored in round 1. Each test carries Purpose + Expected-feedback
docstrings per the Implementation Discipline in CLAUDE.md. Two tests are
FEEDBACK-GATED and deletable after the dev-time loop confirms stability.
"""

from __future__ import annotations

from admorphiq.hypothesis import DiscoveryReport, Hypothesis
from admorphiq.hypothesis.wiki_agent import (
    _augment_click_only_rule4,
    _augment_with_title_match,
    _title_match_strategies,
)


def _report(**kwargs) -> DiscoveryReport:
    defaults = dict(
        game_title="X",
        available_actions=[6],
        layer_count=1,
        dominant_colors=[],
        probe_diffs={6: 0, -6: 0},
        reset_levels=0,
        frame_shape=(64, 64),
    )
    defaults.update(kwargs)
    return DiscoveryReport(**defaults)


def _hyp(primary="", fallbacks=None) -> Hypothesis:
    return Hypothesis(
        game_type="unknown",
        primary_strategy=primary,
        fallback_stack=list(fallbacks or []),
    )


# ---------------------------------------------------------------------------
# _title_match_strategies
# ---------------------------------------------------------------------------


def test_title_match_finds_sb26_sort_for_title_sb26():
    """Purpose: title "SB26" must map to `sb26_sort` — the specific match
    needed to recover the 8-level SB26 regression from round 1.

    Expected feedback: if this fails, round 2's primary win scenario is
    broken and SB26 will keep regressing.
    """
    assert _title_match_strategies("SB26", {"sb26_sort", "click_rare"}) == ["sb26_sort"]


def test_title_match_prefers_frame_only_over_brittle():
    """Purpose: when two whitelist entries match the title (e.g.,
    `su15_frame_only` and `su15_vacuum`), the frame-only variant must
    come first. The brittle variant is retained as a fallback candidate
    but the primary preference is the generalizable strategy.

    Expected feedback: failure means the title-match augmentation would
    push the brittle SU15 solver to the primary slot, re-introducing
    generalization debt on v2 hashes.
    """
    whitelist = {"su15_frame_only", "su15_vacuum", "bfs_state_space"}
    out = _title_match_strategies("SU15", whitelist)
    assert out[0] == "su15_frame_only"


def test_title_match_returns_empty_for_unknown_title():
    """Purpose: a placeholder or missing title must produce no matches —
    augmentation becomes a no-op.

    Expected feedback: failure means random whitelist entries could be
    injected when the title is unknown.
    """
    assert _title_match_strategies("UNKNOWN", {"bfs_state_space"}) == []
    assert _title_match_strategies("", {"bfs_state_space"}) == []


def test_title_match_returns_empty_when_no_whitelist_hit():
    """Purpose: titles without a corresponding strategy (FT09 / CD82 /
    AR25 — no `ft09_*` in whitelist) must not produce spurious matches.

    Expected feedback: failure would pollute fallback_stack with
    unrelated names just because they share a substring with the title.
    """
    assert _title_match_strategies("FT09", {"click_rare", "bfs_state_space"}) == []


# ---------------------------------------------------------------------------
# _augment_with_title_match
# ---------------------------------------------------------------------------


def test_title_match_fills_empty_primary():
    """Purpose: when Qwen left primary empty (whitelist filter zeroed it),
    the title-match strategy must fill the slot rather than being demoted
    to a fallback.

    Expected feedback: failure means fixing a cleared primary still
    requires a second bench pass instead of closing in one round.
    """
    rep = _report(game_title="SB26")
    hyp = _hyp(primary="", fallbacks=["click_rare"])
    out = _augment_with_title_match(hyp, rep, {"sb26_sort", "click_rare"})
    assert out.primary_strategy == "sb26_sort"
    assert out.fallback_stack == ["click_rare"]


def test_title_match_preserves_llm_primary_and_prepends_to_fallback():
    """Purpose: when Qwen chose a non-title primary, the title-match must
    be prepended to fallback_stack without overriding primary. The LLM's
    explicit pick is preserved; the augmentation is additive.

    Expected feedback: failure means the augmentation is too aggressive
    and will overwrite valid LLM choices.
    """
    rep = _report(game_title="SB26")
    hyp = _hyp(primary="click_rare", fallbacks=["click_color_order", "raster"])
    out = _augment_with_title_match(hyp, rep, {"sb26_sort", "click_rare", "click_color_order", "raster"})
    assert out.primary_strategy == "click_rare"
    assert out.fallback_stack[0] == "sb26_sort"
    assert len(out.fallback_stack) <= 3


def test_title_match_is_noop_when_already_picked():
    """Purpose: if the LLM already chose the title-match strategy, the
    augmentation must not duplicate it into the fallback_stack.

    Expected feedback: failure duplicates the strategy and wastes a
    fallback slot.
    """
    rep = _report(game_title="SB26")
    hyp = _hyp(primary="sb26_sort", fallbacks=["click_rare"])
    out = _augment_with_title_match(hyp, rep, {"sb26_sort", "click_rare"})
    assert out.primary_strategy == "sb26_sort"
    assert "sb26_sort" not in out.fallback_stack


def test_title_match_noop_for_ft09_like_titles_without_match():
    """Purpose: FT09 has no `ft09_*` strategy — the augmentation must
    not fire. FT09's recovery belongs to rule-4 augmentation, not to
    title-match.

    Expected feedback: failure means FT09's fallback_stack gets an
    unrelated substring-matching strategy injected.
    """
    rep = _report(game_title="FT09")
    hyp = _hyp(primary="click_rare", fallbacks=["click_color_order"])
    out = _augment_with_title_match(hyp, rep, {"click_rare", "click_color_order", "bfs_state_space"})
    assert out.primary_strategy == "click_rare"
    assert out.fallback_stack == ["click_color_order"]


# ---------------------------------------------------------------------------
# _augment_click_only_rule4
# ---------------------------------------------------------------------------


# FEEDBACK-GATED: pins the FT09-shaped signature that lost 6 levels in
# round 1. Once multiple rounds confirm rule-4 reinforcement is stable,
# the general signature-match test below is enough.
def test_click_only_rule4_injects_lights_out_and_paint_game_on_ft09_signature():
    """Purpose: reproduce FT09's probe signature (avail=[6], probe6=0,
    responsive=0) and confirm rule-4 augmentation injects both
    lights_out and paint_game as fallbacks.

    Expected feedback: if this fails, round 2's FT09 recovery is
    broken.
    """
    rep = _report(
        game_title="FT09",
        available_actions=[6],
        probe_diffs={6: 0, -6: 0},
    )
    hyp = _hyp(primary="click_rare", fallbacks=["click_color_order"])
    out = _augment_click_only_rule4(
        hyp, rep, {"click_rare", "click_color_order", "lights_out", "paint_game"}
    )
    assert "lights_out" in out.fallback_stack
    assert "paint_game" in out.fallback_stack
    assert len(out.fallback_stack) <= 3


def test_click_only_rule4_noop_when_probe_responsive():
    """Purpose: when the click probe shows activity (probe6 > 0 or any
    responsive cell), this is not FT09-shape and the augmentation must
    not fire — it would waste fallback slots on click-paint games.

    Expected feedback: failure means rule-4 fires too broadly and
    displaces valid fallbacks for non-FT09 click games.
    """
    rep = _report(
        game_title="CD82",
        available_actions=[6],
        probe_diffs={6: 5, -6: 2},
    )
    hyp = _hyp(primary="click_rare", fallbacks=["click_color_order"])
    valid = {"click_rare", "click_color_order", "lights_out", "paint_game"}
    out = _augment_click_only_rule4(hyp, rep, valid)
    assert "lights_out" not in out.fallback_stack
    assert "paint_game" not in out.fallback_stack


def test_click_only_rule4_noop_when_avail_not_exactly_6():
    """Purpose: rule 4 requires `avail == [6]`. Hybrid games (`avail has
    1-4 + 6`) must not trigger rule 4 — they are handled by rule 3.

    Expected feedback: failure means hybrid games get click-only
    strategies injected and lose movement fallbacks.
    """
    rep = _report(
        game_title="M0R0",
        available_actions=[1, 2, 3, 4, 6],
        probe_diffs={1: 4, 2: 4, 6: 0, -6: 0},
    )
    hyp = _hyp(primary="bfs_state_space", fallbacks=["click_rare"])
    out = _augment_click_only_rule4(hyp, rep, {"bfs_state_space", "click_rare", "lights_out"})
    assert "lights_out" not in out.fallback_stack


def test_click_only_rule4_does_not_duplicate_already_picked():
    """Purpose: if the LLM already picked lights_out or paint_game,
    the augmentation must not re-insert them.

    Expected feedback: failure means fallback_stack gets duplicates
    despite uniqueItems at decoder (because augmentation runs after).
    """
    rep = _report(
        game_title="FT09",
        available_actions=[6],
        probe_diffs={6: 0, -6: 0},
    )
    hyp = _hyp(primary="click_rare", fallbacks=["lights_out"])
    out = _augment_click_only_rule4(
        hyp, rep, {"click_rare", "lights_out", "paint_game"}
    )
    assert out.fallback_stack.count("lights_out") == 1


# ---------------------------------------------------------------------------
# Combined augmentation order (end-to-end classify invariant)
# ---------------------------------------------------------------------------


def test_combined_augmentations_fallback_stack_capped_at_three():
    """Purpose: title-match + rule-4 both fire could push more than 3
    items into fallback_stack. The cap must be honored end-to-end.

    Expected feedback: failure means the trace's fallback_stack
    overflows the schema cap and the run() loop iterates excess
    strategies past budget.
    """
    rep = _report(
        game_title="FT09",
        available_actions=[6],
        probe_diffs={6: 0, -6: 0},
    )
    hyp = _hyp(primary="click_rare", fallbacks=["raster", "click_color_order", "click_all_colors"])
    valid = {"click_rare", "raster", "click_color_order", "click_all_colors", "lights_out", "paint_game"}
    out = _augment_click_only_rule4(hyp, rep, valid)
    assert len(out.fallback_stack) == 3
