"""R7 feedback-schema tests — FeatureGap/WikiGap parsing + whitelist validation.

These cover the pure helpers introduced to structure the LLM's per-env
feedback (features_missing, wiki_gaps) and to filter hallucinated strategy
names out of the primary/fallback picks.

Every test below has a Purpose and Expected-feedback docstring, per the
Implementation Discipline in CLAUDE.md.
"""

from __future__ import annotations

from admorphiq.hypothesis import FeatureGap, Hypothesis, WikiGap
from admorphiq.hypothesis.wiki_agent import (
    _parse_feature_gaps,
    _parse_wiki_gaps,
    _validate_whitelist,
)


# ---------------------------------------------------------------------------
# _parse_feature_gaps
# ---------------------------------------------------------------------------


def test_parse_feature_gaps_accepts_full_dict_form():
    """Purpose: the canonical R7 schema (dict with name/why_needed/derive_hint)
    must round-trip into a FeatureGap with all three fields populated.

    Expected feedback: failure means the parser is dropping either why_needed
    or derive_hint, which degrades every downstream reflection to name-only
    bullet points and loses the dev-time signal we designed R7 around.
    """
    out = _parse_feature_gaps(
        [
            {
                "name": "sprite_pixel_count",
                "why_needed": "separate slider from point-player",
                "derive_hint": "count pixels of player_color in RESET frame",
            }
        ]
    )
    assert len(out) == 1
    assert out[0].name == "sprite_pixel_count"
    assert out[0].why_needed.startswith("separate slider")
    assert out[0].derive_hint.startswith("count pixels")


# FEEDBACK-GATED: validates the tolerance we added for pre-R7 traces that
# emit bare strings. Once every agent trace carries dict form, this test is
# deletable.
def test_parse_feature_gaps_accepts_bare_string_as_name_only():
    """Purpose: confirm legacy / degraded LLM output (bare strings) still
    yields a usable FeatureGap carrying just the name.

    Expected feedback: if this test fails after we've confirmed all live
    traces emit dicts, delete the test (it's feedback-gated) rather than
    patching the parser — the tolerance is no longer needed.
    """
    out = _parse_feature_gaps(["dir_map_v2"])
    assert len(out) == 1
    assert out[0].name == "dir_map_v2"
    assert out[0].why_needed == ""
    assert out[0].derive_hint == ""


def test_parse_feature_gaps_drops_unnamed_entries():
    """Purpose: entries without a non-empty `name` carry zero actionable
    information; they must be dropped at parse time, not copied into the
    trace to be filtered later.

    Expected feedback: failure means noise can reach the analyzer's
    by_feature grouping where it gets keyed by empty string.
    """
    out = _parse_feature_gaps([{"why_needed": "missing name"}, {"name": "  "}])
    assert out == []


def test_parse_feature_gaps_returns_empty_for_non_list():
    """Purpose: defend against the LLM emitting `features_missing` as a dict
    or null. The dev-time loop should see an empty list, not a crash.

    Expected feedback: failure means a malformed LLM response kills the
    per-env trace build.
    """
    assert _parse_feature_gaps(None) == []
    assert _parse_feature_gaps({"name": "x"}) == []


def test_parse_feature_gaps_caps_at_eight():
    """Purpose: bound the per-env feedback payload so an over-reporting LLM
    cannot inflate the trace beyond usable size. Eight is arbitrary but is
    what the R7 prompt's "be surgical" guidance expects.

    Expected feedback: failure means a chatty LLM can balloon the trace and
    dominate Claude Code's context during reflection.
    """
    many = [{"name": f"f_{i}"} for i in range(20)]
    assert len(_parse_feature_gaps(many)) == 8


# ---------------------------------------------------------------------------
# _parse_wiki_gaps
# ---------------------------------------------------------------------------


def test_parse_wiki_gaps_requires_topic():
    """Purpose: a WikiGap without a topic is unfileable — Claude Code can't
    route it to a page. The parser rejects topic-less entries rather than
    propagating them as "".

    Expected feedback: failure means untriageable items reach the wiki
    authoring step and have to be filtered there instead.
    """
    out = _parse_wiki_gaps(
        [
            {"topic": "merge mechanics", "proposed_addition": "distinguish variants"},
            {"suggested_page": "concepts/foo.md"},  # no topic → dropped
            {"topic": "   "},  # whitespace-only topic → dropped
        ]
    )
    assert len(out) == 1
    assert out[0].topic == "merge mechanics"


def test_parse_wiki_gaps_rejects_bare_strings():
    """Purpose: unlike FeatureGap, wiki gaps have no useful single-string
    degenerate form — "fix the wiki" with no topic is noise. The parser
    drops strings outright.

    Expected feedback: failure means string entries end up in wiki_gaps and
    clutter the reflection input.
    """
    out = _parse_wiki_gaps(["the wiki needs more info"])
    assert out == []


# ---------------------------------------------------------------------------
# _validate_whitelist
# ---------------------------------------------------------------------------


# FEEDBACK-GATED: this test pins the specific Qwen 3 14B failure mode
# observed on 2026-04-21 (hallucinated `seq_search`). Once the feedback
# loop has produced at least one round where no model hallucinates
# whitelist-invalid names, this test is deletable — the invariant is
# better expressed by the more general test below it.
def test_validate_whitelist_filters_seq_search_hallucination():
    """Purpose: lock in the specific regression the R7 filter was built for
    — 14B's habit of suggesting `seq_search` on FT09.

    Expected feedback: if this fails after delete of `seq_search` from
    live traces, this test is done its job and can be removed.
    """
    valid = {"bfs_state_space", "click_rare", "lights_out", "paint_game"}
    hyp = Hypothesis(
        game_type="unknown",
        primary_strategy="bfs_state_space",
        fallback_stack=["click_rare", "seq_search"],
    )
    cleaned = _validate_whitelist(hyp, valid)
    assert cleaned.fallback_stack == ["click_rare"]
    assert "seq_search" not in cleaned.fallback_stack


def test_validate_whitelist_empties_invalid_primary():
    """Purpose: when the LLM picks a nonsense primary_strategy, the
    downstream run() loop must see "no primary" rather than try to dispatch
    a nonexistent function. Emptying primary_strategy is the contract.

    Expected feedback: failure means nonsense primary names would reach the
    dispatcher and trigger `unknown_strategy` noise in the execution log.
    """
    valid = {"bfs_state_space", "click_rare"}
    hyp = Hypothesis(
        game_type="unknown",
        primary_strategy="totally_fake_strategy",
        fallback_stack=["click_rare"],
    )
    cleaned = _validate_whitelist(hyp, valid)
    assert cleaned.primary_strategy == ""
    assert cleaned.fallback_stack == ["click_rare"]


def test_validate_whitelist_leaves_valid_picks_untouched():
    """Purpose: the filter must be a no-op when the LLM cooperates. If it
    mutates a valid hypothesis, we have a subtle bug.

    Expected feedback: failure means the filter is over-zealous and will
    erase legitimate LLM picks.
    """
    valid = {"bfs_state_space", "click_rare", "lights_out"}
    hyp = Hypothesis(
        game_type="click",
        primary_strategy="click_rare",
        fallback_stack=["lights_out", "bfs_state_space"],
    )
    cleaned = _validate_whitelist(hyp, valid)
    assert cleaned.primary_strategy == "click_rare"
    assert cleaned.fallback_stack == ["lights_out", "bfs_state_space"]


# ---------------------------------------------------------------------------
# Hypothesis dataclass defaults (shape sanity)
# ---------------------------------------------------------------------------


def test_hypothesis_has_r7_fields_with_safe_defaults():
    """Purpose: regression pin against field drift. Any branch that renames
    or removes doubt / wiki_gaps / wiki_needs silently would break the
    reflection schema.

    Expected feedback: failure here means the trace emission code must be
    updated in lockstep. Do not silently delete this test.
    """
    h = Hypothesis(game_type="unknown", primary_strategy="")
    assert h.doubt == ""
    assert h.features_missing == []
    assert h.wiki_gaps == []
    assert h.wiki_needs == []
    # Structured subtypes are importable from the public API
    assert FeatureGap(name="x").name == "x"
    assert WikiGap(topic="t").topic == "t"
