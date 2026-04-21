"""Phase 8 Hypothesis Engine — wiki-driven LLM agent.

Exports:
  WikiAgent                 - main agent (LLM-agnostic, reads .wiki/ offline)
  DiscoveryReport           - live-game observations fed to the LLM
  Hypothesis                - parsed LLM response
  discover                  - builds a DiscoveryReport from a live env
  default_strategy_registry - auto-discovers all ensemble strategies
                              dispatchable from a DiscoveryReport (R3)
  build_ctx                 - DiscoveryReport → strategy-call context dict
  introspect_strategies     - explicit (registry, skipped) pair for diagnostics
"""

from __future__ import annotations

from .dispatcher import CTX_KEYS, build_ctx, introspect_strategies
from .wiki_agent import (
    DiscoveryReport,
    FeatureGap,
    Hypothesis,
    WikiAgent,
    WikiGap,
    discover,
)
from .wiki_retrieval import (
    GraphRetriever,
    derive_keywords,
    derive_seed_pages,
    extract_backlinks,
    resolve_link,
    score_link,
    strip_frontmatter,
)


def default_strategy_registry() -> dict:
    """Return a name → ctx-aware callable map covering every ensemble strategy
    whose required args are derivable from a DiscoveryReport.

    Each callable has signature ``(env, budget, ctx) -> (levels, label, actions)``
    and looks up the extras it needs inside ``ctx`` (see
    :func:`dispatcher.build_ctx` for the key definitions).

    Strategies with runtime-only args (winning_aid, a1/a2, winning_fn, …) are
    skipped here — they stay in the internal ensemble dispatcher for feature-
    based routing and are not LLM-pickable.

    Lazy import so callers that only need classification avoid pulling in the
    full 8000-line strategy module.
    """
    from .. import agent_ensemble as ae

    registry, _skipped = introspect_strategies(ae)
    return registry


def strategy_whitelist_text(registry: dict) -> str:
    """Render the registry as a bullet list fit for the LLM prompt."""
    return ", ".join(sorted(registry.keys()))


__all__ = [
    "CTX_KEYS",
    "DiscoveryReport",
    "FeatureGap",
    "GraphRetriever",
    "Hypothesis",
    "WikiAgent",
    "WikiGap",
    "build_ctx",
    "default_strategy_registry",
    "derive_keywords",
    "derive_seed_pages",
    "discover",
    "extract_backlinks",
    "introspect_strategies",
    "resolve_link",
    "score_link",
    "strategy_whitelist_text",
    "strip_frontmatter",
]
