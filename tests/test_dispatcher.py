"""Unit tests for the R3 universal strategy dispatcher.

Validates that:
  1. `build_ctx` produces all required keys and falls back gracefully when
     discovery signals are absent.
  2. `introspect_strategies` auto-registers uniform/dir-only/avail-only
     strategies and skips runtime-only ones.
  3. `_make_wrapper` forwards ctx-derived args to the wrapped strategy in the
     same positional order as the original signature.
"""

from __future__ import annotations

import pytest

from admorphiq.hypothesis import CTX_KEYS
from admorphiq.hypothesis.dispatcher import (
    _make_wrapper,
    build_ctx,
    introspect_strategies,
)
from admorphiq.hypothesis.wiki_agent import DiscoveryReport


def _report(**kwargs) -> DiscoveryReport:
    defaults = dict(
        game_title="X",
        available_actions=[1, 2, 3, 4, 6],
        layer_count=1,
        dominant_colors=[],
        probe_diffs={},
        reset_levels=0,
        frame_shape=(64, 64),
    )
    defaults.update(kwargs)
    return DiscoveryReport(**defaults)


# ---------------------------------------------------------------------------
# build_ctx
# ---------------------------------------------------------------------------


def test_build_ctx_exposes_all_ctx_keys():
    ctx = build_ctx(_report(dir_map={1: "N"}, player_color=5))
    assert set(ctx.keys()) == set(CTX_KEYS)


def test_build_ctx_dir_actions_from_dir_map():
    ctx = build_ctx(_report(dir_map={1: "N", 3: "E"}))
    assert ctx["dir_actions"] == [1, 3]
    assert ctx["dir_to_act"] == {"N": 1, "E": 3}


def test_build_ctx_fallback_dir_actions_when_map_empty():
    """When probes gave no directional evidence, fall back to 1-4 ∩ avail."""
    ctx = build_ctx(_report(available_actions=[1, 2, 3, 4, 6], dir_map={}))
    assert ctx["dir_actions"] == [1, 2, 3, 4]


def test_build_ctx_excludes_reset_and_cancel_from_avail():
    ctx = build_ctx(_report(available_actions=[0, 1, 2, 3, 4, 6, 7]))
    assert 0 not in ctx["avail_actions"]
    assert 7 not in ctx["avail_actions"]


def test_build_ctx_player_color_zero_when_none():
    ctx = build_ctx(_report(player_color=None))
    assert ctx["player_color"] == 0


def test_build_ctx_has_click_reflects_action6_availability():
    assert build_ctx(_report(available_actions=[1, 2, 3, 4]))["has_click"] is False
    assert build_ctx(_report(available_actions=[1, 2, 3, 4, 6]))["has_click"] is True


# ---------------------------------------------------------------------------
# introspect_strategies (against the real ensemble module)
# ---------------------------------------------------------------------------


def test_introspect_real_ensemble_exposes_many_more_than_pre_r3():
    """R3 must expose materially more than the pre-R3 manual whitelist of 17."""
    from admorphiq import agent_ensemble as ae

    registry, skipped = introspect_strategies(ae)
    assert len(registry) >= 30, (
        f"Only {len(registry)} strategies dispatchable after R3; the pre-R3 "
        f"manual list had 17, so this is a regression. Skipped reasons: {skipped}"
    )


def test_introspect_skips_runtime_only_strategies():
    """Functions whose first non-env non-budget arg is a runtime value (aid,
    winning_aid, a1, winning_fn) must be skipped, not dispatchable."""
    from admorphiq import agent_ensemble as ae

    _, skipped = introspect_strategies(ae)
    skipped_names = {name for name, _ in skipped}
    # At least these four must be in the skipped set — they have purely
    # runtime-dependent required args.
    for required in ("sustained", "zigzag", "extended_winner", "continue_multilevel"):
        assert required in skipped_names, (
            f"expected {required!r} to be skipped (runtime-only args), "
            f"skipped={sorted(skipped_names)}"
        )


def test_introspect_preserves_previous_uniform_strategies():
    """Previously-exposed uniform strategies must still be in the new
    registry. Round 5 (2026-04-22) excluded `tn36_frame_only` and
    `su15_frame_only` from this list because they were renamed
    "frame_only" but actually read game-internal sprite tags — see
    BRITTLE_STRATEGIES in dispatcher.py. Round 8 additionally excluded
    `bfs_state_space` and `click_rare` as LLM anchor-banned — they
    remain internally callable via strat_inferential_agent's
    navigation / toggle plans.
    """
    from admorphiq import agent_ensemble as ae

    registry, _ = introspect_strategies(ae)
    pre_r3_uniform = {
        "click_all_colors",
        "click_progressive",
        "click_toggle_detect",
        "click_diff_track",
        "click_frame_adaptive",
        "click_color_order",
        "click_grid_aligned",
        "raster",
    }
    missing = pre_r3_uniform - set(registry.keys())
    assert not missing, f"registry dropped pre-R3 uniform strategies: {missing}"


def test_round8_anchor_ban_is_enforced():
    """Purpose: round 8's ANCHOR_BANNED_STRATEGIES set — currently
    `bfs_state_space` and `click_rare` — MUST NOT appear in the
    LLM-pickable registry. Qwen 8B anchor-locked on these across
    R3-R7 (measured 40/40 picks = bfs + click_rare, zero
    inferential_agent), so this ban is the mechanism that forces the
    Wiki-First Routing architecture to actually route through
    inferential_agent. Both names stay internally callable.

    Expected feedback: failure means a banned name leaked back into
    the whitelist, Qwen picks it again, and the five-phase
    inferential pipeline never executes.
    """
    from admorphiq import agent_ensemble as ae
    from admorphiq.hypothesis.dispatcher import ANCHOR_BANNED_STRATEGIES

    registry, skipped = introspect_strategies(ae)
    leaked = sorted(ANCHOR_BANNED_STRATEGIES & set(registry.keys()))
    assert not leaked, f"anchor-banned strategies leaked into registry: {leaked}"
    skipped_names = {n for n, _ in skipped}
    not_skipped = sorted(ANCHOR_BANNED_STRATEGIES - skipped_names)
    assert not not_skipped, (
        f"anchor-banned strategies missing from skipped list: {not_skipped}"
    )


def test_round8_inferential_agent_remains_registered():
    """Purpose: after removing the anchors, `inferential_agent` must
    still be the one first-class routing choice. If it also drops out
    of the registry (e.g., by import failure or signature drift),
    Qwen has no valid primary to pick.

    Expected feedback: failure means the five-phase agent is not
    reachable — immediate rollback or fix required.
    """
    from admorphiq import agent_ensemble as ae

    registry, _ = introspect_strategies(ae)
    assert "inferential_agent" in registry, (
        "inferential_agent missing from registry — round 8 routing "
        "architecture cannot function"
    )


def test_round5_brittle_deny_list_is_enforced():
    """Purpose: the 12 game-internal-hardcoded strategies on the
    BRITTLE_STRATEGIES deny-list MUST NOT appear in the LLM-pickable
    registry, even though their `strat_*` functions still exist in
    `agent_ensemble.py`. This is the round-5 contract — without this,
    Qwen could pick `paint_game` for a CD82-shape env on Kaggle and
    get an AttributeError because the sprite tags don't exist.

    Expected feedback: failure means a brittle strategy leaked into
    the LLM whitelist. Either the deny-list dropped a name or
    introspect_strategies stopped checking it.
    """
    from admorphiq import agent_ensemble as ae
    from admorphiq.hypothesis.dispatcher import BRITTLE_STRATEGIES

    registry, skipped = introspect_strategies(ae)
    leaked = sorted(BRITTLE_STRATEGIES & set(registry.keys()))
    assert not leaked, f"brittle strategies leaked into registry: {leaked}"
    skipped_names = {n for n, _ in skipped}
    not_skipped = sorted(BRITTLE_STRATEGIES - skipped_names)
    assert not not_skipped, (
        f"brittle strategies missing from skipped list: {not_skipped}"
    )


def test_round5_generic_g1_to_g4_are_registered():
    """Purpose: the four round-5 generic inference strategies
    (G1 interactive_grid_toggle, G2 sprite_cluster_interaction,
    G3 push_bfs_grid, G4 bfs_framehash) MUST appear in the registry.
    They replace the routing role of the brittle strategies and the
    LLM cannot pick them otherwise.

    Expected feedback: failure means a Gx function was renamed,
    deleted, or its signature broke ctx-introspection. Re-add it or
    fix its signature so the introspector accepts it.
    """
    from admorphiq import agent_ensemble as ae

    registry, _ = introspect_strategies(ae)
    expected = {
        "interactive_grid_toggle",
        "sprite_cluster_interaction",
        "push_bfs_grid",
        "bfs_framehash",
    }
    missing = expected - set(registry.keys())
    assert not missing, f"round-5 generics missing from registry: {missing}"


# ---------------------------------------------------------------------------
# _make_wrapper
# ---------------------------------------------------------------------------


def test_wrapper_forwards_single_ctx_arg_in_order():
    def fake(env, dir_actions, budget):
        return (0, f"got dir_actions={dir_actions}", budget)

    w = _make_wrapper(fake, ["dir_actions"])
    ctx = build_ctx(_report(dir_map={1: "N", 2: "S"}))
    assert w(None, 123, ctx) == (0, "got dir_actions=[1, 2]", 123)


def test_wrapper_forwards_multi_ctx_args_in_declared_order():
    def fake(env, player_color, dir_to_act, budget):
        return (0, f"pc={player_color} dir={dir_to_act}", budget)

    w = _make_wrapper(fake, ["player_color", "dir_to_act"])
    ctx = build_ctx(_report(dir_map={1: "N"}, player_color=4))
    result = w(None, 77, ctx)
    assert result[0] == 0
    assert "pc=4" in result[1]
    assert "'N': 1" in result[1]
    assert result[2] == 77


def test_wrapper_uniform_strategy_adds_no_extras():
    def fake_uniform(env, budget):
        return (0, "uniform", budget)

    w = _make_wrapper(fake_uniform, [])
    ctx = build_ctx(_report())
    assert w(None, 500, ctx) == (0, "uniform", 500)


def test_wrapper_exposes_wrapped_strategy_and_ctx_keys_for_debug():
    def fake(env, avail_actions, budget):
        return (0, "fake", budget)

    w = _make_wrapper(fake, ["avail_actions"])
    assert w.__wrapped_strategy__ is fake
    assert w.__ctx_keys__ == ["avail_actions"]


# ---------------------------------------------------------------------------
# default_strategy_registry integration
# ---------------------------------------------------------------------------


def test_default_registry_matches_introspection():
    from admorphiq.hypothesis import default_strategy_registry

    registry = default_strategy_registry()
    # Every entry must be ctx-aware (our wrappers expose __ctx_keys__)
    for name, fn in registry.items():
        assert hasattr(fn, "__ctx_keys__"), (
            f"strategy {name!r} is not a ctx-aware wrapper; "
            f"did something bypass introspect_strategies()?"
        )
