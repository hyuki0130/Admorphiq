"""Phase 8 Hypothesis Engine — wiki-driven LLM agent.

Exports:
  WikiAgent                 - main agent (LLM-agnostic, reads .wiki/ offline)
  DiscoveryReport           - live-game observations fed to the LLM
  Hypothesis                - parsed LLM response
  discover                  - builds a DiscoveryReport from a live env
  default_strategy_registry - curated frame-only dispatch for selector.md names
"""

from __future__ import annotations

from .wiki_agent import DiscoveryReport, Hypothesis, WikiAgent, discover


def default_strategy_registry() -> dict:
    """Return a name → callable map for frame-only strategies in selector.md.

    Only strategies with the uniform `(env, budget)` signature are registered —
    movement-style strats that require `dir_actions` are omitted because the
    dispatcher cannot derive that context from frame diffs alone. The ensemble's
    internal dispatcher handles those via feature-based routing; the WikiAgent
    sticks to the signature-compatible subset.

    Lazy import so callers that only need classification avoid pulling in the
    8000-line strategy module.
    """
    from .. import agent_ensemble as ae

    # All callables below have `(env, budget)` signature.
    mapping: dict = {
        "bfs_state_space": ae.strat_bfs_state_space,
        "click_rare": ae.strat_click_rare,
        "click_all_colors": ae.strat_click_all_colors,
        "click_progressive": ae.strat_click_progressive,
        "click_toggle_detect": ae.strat_click_toggle_detect,
        "click_diff_track": ae.strat_click_diff_track,
        "click_frame_adaptive": ae.strat_click_frame_adaptive,
        "click_color_order": ae.strat_click_color_order,
        "click_grid_aligned": ae.strat_click_grid_aligned,
        "raster": ae.strat_raster,
        "tn36_frame_only": ae.strat_tn36_frame_only,
        "su15_frame_only": ae.strat_su15_frame_only,
    }
    # Optional strategies that may or may not exist across branches.
    for attr in (
        "strat_paint_game",
        "strat_lights_out",
        "strat_sb26_sort",
        "strat_ls20_grid",
        "strat_move_click",
    ):
        fn = getattr(ae, attr, None)
        if fn is not None:
            # These take (env, budget) or (env, aid, budget) — guard at call site.
            mapping[attr.removeprefix("strat_")] = fn
    return mapping


def strategy_whitelist_text(registry: dict) -> str:
    """Render the registry as a bullet list fit for the LLM prompt."""
    names = sorted(registry.keys())
    return ", ".join(names)


__all__ = [
    "DiscoveryReport",
    "Hypothesis",
    "WikiAgent",
    "default_strategy_registry",
    "discover",
    "strategy_whitelist_text",
]
