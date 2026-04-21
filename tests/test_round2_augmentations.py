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
    _augment_hybrid_rule3,
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
# _augment_hybrid_rule3 (Round 3 — 2026-04-21)
# ---------------------------------------------------------------------------


# FEEDBACK-GATED: pins CD82's round-2 signature (avail=[1..6], probe3/4=201,
# probe6=1, -6=5) — Qwen picked click_select_move and lost all 6 levels
# that baseline recovered via paint_game. Once rule-3 reinforcement has
# survived a multi-round bench, this specific signature pin is deletable.
def test_hybrid_rule3_injects_paint_game_on_cd82_signature():
    """Purpose: reproduce CD82's round-2 probe signature and confirm rule-3
    augmentation injects paint_game into fallback_stack. CD82 baseline
    cleared 6/6 via paint_game; round 2 lost all 6 because the Qwen pick
    omitted it.

    Expected feedback: if this fails, round 3's CD82 recovery is broken
    and the -6 regression persists.
    """
    rep = _report(
        game_title="CD82",
        available_actions=[1, 2, 3, 4, 5, 6],
        probe_diffs={1: 1, 2: 1, 3: 201, 4: 201, 6: 1, -6: 5},
    )
    hyp = _hyp(primary="click_select_move", fallbacks=["click_toggle_detect", "click_color_order"])
    valid = {"click_select_move", "click_toggle_detect", "click_color_order", "paint_game", "bfs_state_space"}
    out = _augment_hybrid_rule3(hyp, rep, valid)
    assert "paint_game" in out.fallback_stack
    assert out.primary_strategy == "click_select_move"  # LLM primary preserved
    assert len(out.fallback_stack) <= 3


# FEEDBACK-GATED: pins AR25's round-2 signature (avail=[1..7], probe1-4=109,
# probe6=0) — Qwen picked explore_and_interact with no bfs_state_space in
# the chain. Baseline got 2/8 via bfs_state_space. Deletable once rule-3
# reinforcement is stable across rounds.
def test_hybrid_rule3_injects_bfs_on_ar25_signature():
    """Purpose: reproduce AR25's round-2 probe signature and confirm rule-3
    augmentation prepends bfs_state_space to fallback_stack. AR25 baseline
    cleared 2/8 via bfs_state_space; round 2 lost both.

    Expected feedback: if this fails, round 3's AR25 recovery is broken.
    """
    rep = _report(
        game_title="AR25",
        available_actions=[1, 2, 3, 4, 5, 6, 7],
        probe_diffs={1: 109, 2: 109, 3: 109, 4: 109, 6: 0, -6: 0},
    )
    hyp = _hyp(primary="explore_and_interact", fallbacks=["click_toggle_detect", "move_then_click_grid"])
    valid = {"explore_and_interact", "click_toggle_detect", "move_then_click_grid", "bfs_state_space", "paint_game"}
    out = _augment_hybrid_rule3(hyp, rep, valid)
    assert "bfs_state_space" in out.fallback_stack
    assert out.fallback_stack[0] == "bfs_state_space"  # priority position
    assert out.primary_strategy == "explore_and_interact"


def test_hybrid_rule3_noop_when_no_action6():
    """Purpose: rule 3 requires action 6 alongside 1-4. Pure movement
    games (avail has 1-4, no 6) match rule 1, not rule 3 — augmentation
    must not fire.

    Expected feedback: failure means movement games get paint_game /
    click_toggle_detect injected, displacing valid movement fallbacks.
    """
    rep = _report(
        available_actions=[1, 2, 3, 4],
        probe_diffs={1: 5, 2: 5, 3: 5, 4: 5},
    )
    hyp = _hyp(primary="bfs_state_space", fallbacks=["click_rare", "raster"])
    valid = {"bfs_state_space", "click_rare", "raster", "paint_game", "click_toggle_detect"}
    out = _augment_hybrid_rule3(hyp, rep, valid)
    assert "paint_game" not in out.fallback_stack
    assert "click_toggle_detect" not in out.fallback_stack
    assert out.fallback_stack == ["click_rare", "raster"]


def test_hybrid_rule3_noop_when_missing_action_1_to_4():
    """Purpose: rule 3 also requires 1-4 in avail. avail=[6] triggers
    rule 4 (click-only), not rule 3 — augmentation must not fire.

    Expected feedback: failure means click-only games get bfs injected
    which is wasted budget (movement actions don't do anything).
    """
    rep = _report(
        available_actions=[6],
        probe_diffs={6: 0, -6: 0},
    )
    hyp = _hyp(primary="click_rare", fallbacks=["lights_out"])
    valid = {"click_rare", "lights_out", "bfs_state_space", "paint_game", "click_toggle_detect"}
    out = _augment_hybrid_rule3(hyp, rep, valid)
    assert "bfs_state_space" not in out.fallback_stack
    assert out.fallback_stack == ["lights_out"]


def test_hybrid_rule3_fills_empty_primary_preserved():
    """Purpose: rule 3 augmentation is additive even when the LLM left
    primary empty. The primary is set by title-match (earlier in the
    pipeline) or stays empty; rule 3 only touches fallback_stack — never
    overrides or fills primary. That is the title-match function's job.

    Expected feedback: failure means rule-3 and title-match fight over
    the primary slot, one overwriting the other.
    """
    rep = _report(
        available_actions=[1, 2, 3, 4, 6],
        probe_diffs={1: 100, 2: 100, 3: 100, 4: 100, 6: 0, -6: 0},
    )
    hyp = _hyp(primary="", fallbacks=[])
    valid = {"bfs_state_space", "paint_game", "click_toggle_detect"}
    out = _augment_hybrid_rule3(hyp, rep, valid)
    assert out.primary_strategy == ""  # rule-3 never writes primary
    assert out.fallback_stack == ["bfs_state_space", "paint_game", "click_toggle_detect"]


def test_hybrid_rule3_does_not_duplicate_already_picked():
    """Purpose: if the LLM already picked bfs_state_space (rule 3's
    canonical primary), the augmentation must not re-insert it into
    fallback_stack.

    Expected feedback: failure means CN04-style envs (primary already
    bfs_state_space) get bfs duplicated into fallback, wasting a slot.
    """
    rep = _report(
        available_actions=[1, 2, 3, 4, 6],
        probe_diffs={1: 144, 2: 144, 3: 198, 4: 198, 6: 279, -6: 1},
    )
    hyp = _hyp(primary="bfs_state_space", fallbacks=["explore_and_interact", "click_toggle_detect"])
    valid = {"bfs_state_space", "explore_and_interact", "click_toggle_detect", "paint_game"}
    out = _augment_hybrid_rule3(hyp, rep, valid)
    assert out.fallback_stack.count("bfs_state_space") == 0  # already primary
    assert "paint_game" in out.fallback_stack  # only missing piece added


def test_hybrid_rule3_respects_valid_names_filter():
    """Purpose: rule-3 names that aren't in the live whitelist must not
    be injected — enum constraint at the decoder would reject them
    anyway, but the augmentation runs after decoding and must not
    reintroduce hallucinations via the back door.

    Expected feedback: failure means bfs_state_space leaks into a
    registry that doesn't export it (e.g., a minimal test harness),
    causing downstream `unknown_strategy` errors in run().
    """
    rep = _report(
        available_actions=[1, 2, 3, 4, 6],
        probe_diffs={1: 5, 2: 5, 3: 5, 4: 5, 6: 0, -6: 0},
    )
    hyp = _hyp(primary="click_rare", fallbacks=[])
    valid = {"click_rare", "click_toggle_detect"}  # no bfs, no paint
    out = _augment_hybrid_rule3(hyp, rep, valid)
    assert out.fallback_stack == ["click_toggle_detect"]


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
