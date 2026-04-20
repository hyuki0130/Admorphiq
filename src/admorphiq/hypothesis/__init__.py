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

    Lazy import so callers that only need classification avoid pulling in the
    8000-line strategy module.
    """
    from .. import agent_ensemble as ae

    mapping = {
        "bfs_state_space": ae.strat_bfs_state_space,
        "click_rare": ae.strat_click_rare,
        "click_all_colors": ae.strat_click_all_colors,
        "click_progressive": ae.strat_click_progressive,
        "click_toggle_detect": ae.strat_click_toggle_detect,
        "raster": ae.strat_raster,
        "tn36_frame_only": ae.strat_tn36_frame_only,
        "su15_frame_only": ae.strat_su15_frame_only,
    }
    for name in ("strat_spell_cast", "strat_seq_search"):
        fn = getattr(ae, name, None)
        if fn is not None:
            mapping[name.removeprefix("strat_")] = fn
    return mapping


__all__ = [
    "DiscoveryReport",
    "Hypothesis",
    "WikiAgent",
    "default_strategy_registry",
    "discover",
]
