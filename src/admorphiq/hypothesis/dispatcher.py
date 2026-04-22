"""Phase 8 R3 — universal strategy dispatcher.

Exposes every `strat_*` in `agent_ensemble.py` to the WikiAgent LLM without
modifying the strategy functions themselves. Signatures are introspected at
registry-build time; a strategy is auto-registered if every non-default,
non-env, non-budget parameter is a key of `CTX_KEYS` (i.e., derivable from a
DiscoveryReport).

Strategies with runtime-only args (e.g., `strat_extended_winner(env,
winning_aid, ...)`, `strat_sustained(env, aid, ...)`) are skipped with a
logged reason and remain dispatched by the feature-based logic inside
`agent_ensemble.py`. They are NOT exposed to the LLM because a one-shot
classifier can't pick them — they depend on a prior winning action that
only exists mid-run.
"""

from __future__ import annotations

import inspect
from typing import Any, Callable

# Keys that the DiscoveryReport supplies to dispatchable strategies. A new
# ensemble strategy with a parameter outside this set is skipped until either
# (a) the parameter name is added here (and `build_ctx` produces it) or
# (b) the strategy is refactored to one of these existing names.
CTX_KEYS: frozenset[str] = frozenset(
    {
        "avail_actions",
        "dir_actions",
        "dir_to_act",
        "player_color",
        "has_click",
    }
)


# Strategies that read game-internal sprite tags or attribute names and
# therefore only function on the 25 preview games. Round 5 (2026-04-22)
# removed them from the LLM-pickable whitelist; the routing layer cannot
# select these on the Kaggle private test set anyway, and exposing them
# made R2/R3 bench numbers misleading. The functions still exist in
# `agent_ensemble.py` for the internal ensemble dispatcher's
# feature-based fallback path on preview games.
BRITTLE_STRATEGIES: frozenset[str] = frozenset(
    {
        "paint_game",
        "lights_out",
        "sb26_sort",
        "su15_frame_only",
        "su15_vacuum",
        "tn36_frame_only",
        "tn36_puzzle",
        "ka59_sokoban",
        "re86_analytical",
        "wa30_analytical",
        "s5i5_slider",
        "bp35_platformer",
    }
)


# Round 8 (2026-04-22) — strategies Qwen 3 8B anchor-locks on.
# Four rounds of wiki work (R3-R7) did not dislodge Qwen's preference
# for these two names. Across R7's 40-env bench, Qwen picked
# `bfs_state_space` 25x and `click_rare` 15x and `inferential_agent`
# 0x, despite the round-6 compact decision_tree.md seeded first.
#
# Both stay internally callable: the navigation plan inside
# `strat_inferential_agent` already delegates to
# `strat_bfs_state_space`, and click-rare behavior is subsumed by
# the toggle / paint-fill plans.
ANCHOR_BANNED_STRATEGIES: frozenset[str] = frozenset(
    {
        "bfs_state_space",
        "click_rare",
    }
)


# Round 9 (2026-04-22) — ultra-minimal LLM-pickable allowlist.
# Round 8 measured that partial whitelist purging produces
# anchor-whack-a-mole: Qwen abandoned bfs_state_space/click_rare only
# to pick bfs_explore / click_rotation_puzzle / bfs_framehash, all
# weaker strategies. Score collapsed 23 → 4 raw levels.
#
# The allowlist below is the logical endpoint of Wiki-First Routing:
# the routing LLM is offered exactly four names and must pick among
# them. `inferential_agent` is the sole primary — it handles every
# game shape through its five-phase pipeline. The three click-tool
# fallbacks exist only so the run() loop has something to try when
# I-Agent's plans all time out mid-run.
LLM_WHITELIST_ALLOWLIST: frozenset[str] = frozenset(
    {
        # Round 11 (2026-04-22) — single-item allowlist. Round 10
        # renamed `inferential_agent` → `adaptive_bfs_solver` and kept
        # 3 click-tool fallbacks; Qwen still picked click_toggle_detect
        # 11/11. Removing even the fallbacks forces the decoder to
        # return adaptive_bfs_solver as the only option. The schema
        # in wiki_agent.py relaxes uniqueItems/minItems when the
        # whitelist is < 4 so this doesn't become unsatisfiable.
        "adaptive_bfs_solver",
    }
)


def build_ctx(report) -> dict[str, Any]:
    """Derive the strategy-call context dict from a DiscoveryReport.

    Every key in the returned dict corresponds to a parameter name used by at
    least one `strat_*` function in `agent_ensemble.py`. When adding a new
    key, extend `CTX_KEYS` in the same commit so the introspector will
    actually accept strategies that use it.
    """
    avail = [a for a in report.available_actions if a not in (0, 7)]
    # `dir_actions` = action ids observed to cause movement during discovery.
    # If nothing moved (probe noise or static scene), fall back to 1-4 ∩ avail
    # so movement strategies at least have a shot at the first level.
    dir_actions = sorted(report.dir_map.keys()) or [a for a in avail if 1 <= a <= 4]
    dir_to_act = {direction: aid for aid, direction in report.dir_map.items()}
    return {
        "avail_actions": list(avail),
        "dir_actions": list(dir_actions),
        "dir_to_act": dir_to_act,
        "player_color": (
            int(report.player_color) if report.player_color is not None else 0
        ),
        "has_click": 6 in avail,
    }


def _make_wrapper(fn: Callable, extra_names: list[str]) -> Callable:
    """Build a ctx-aware wrapper that looks up `extra_names` in ctx and calls
    `fn(env, *extras, budget)` positionally. Budget is always last — matches
    the `strat_*` convention in agent_ensemble.py."""

    def _wrapped(env: Any, budget: int, ctx: dict[str, Any]):
        args = [ctx[name] for name in extra_names]
        return fn(env, *args, budget)

    _wrapped.__name__ = fn.__name__ + "_wrapped"
    _wrapped.__wrapped_strategy__ = fn  # type: ignore[attr-defined]
    _wrapped.__ctx_keys__ = list(extra_names)  # type: ignore[attr-defined]
    return _wrapped


def introspect_strategies(
    module,
) -> tuple[dict[str, Callable], list[tuple[str, str]]]:
    """Walk `module` looking for `strat_*` callables and classify each.

    Returns
    -------
    registry : dict[str, Callable]
        Maps short strategy name (without ``strat_`` prefix) to a ctx-aware
        callable ``(env, budget, ctx) -> (levels, label, actions)``.
    skipped : list[tuple[str, str]]
        ``(name, reason)`` for every strategy that could not be auto-registered.
        The reason string is diagnostic only — no runtime behavior branches on
        it.
    """
    registry: dict[str, Callable] = {}
    skipped: list[tuple[str, str]] = []
    for attr_name in dir(module):
        if not attr_name.startswith("strat_"):
            continue
        fn = getattr(module, attr_name)
        if not callable(fn):
            continue
        try:
            sig = inspect.signature(fn)
        except (TypeError, ValueError):
            skipped.append((attr_name, "signature unreadable"))
            continue
        params = list(sig.parameters.values())
        if not params or params[0].name != "env":
            skipped.append((attr_name, "first parameter is not 'env'"))
            continue
        short_name = attr_name[len("strat_") :]
        if short_name in BRITTLE_STRATEGIES:
            skipped.append(
                (
                    short_name,
                    "brittle: reads game-internal sprite/attribute names — "
                    "kept in agent_ensemble for preview-game ensemble use, "
                    "denied from the LLM-pickable whitelist (round 5 rule)",
                )
            )
            continue
        if short_name in ANCHOR_BANNED_STRATEGIES:
            skipped.append(
                (
                    short_name,
                    "anchor-banned in round 8 — Qwen locked onto this "
                    "name through R3-R7; removing it from the LLM whitelist "
                    "forces inferential_agent as the routing entry point. "
                    "Still callable internally via strat_inferential_agent "
                    "navigation plan delegation.",
                )
            )
            continue
        if short_name not in LLM_WHITELIST_ALLOWLIST:
            skipped.append(
                (
                    short_name,
                    "round-9 allowlist: only inferential_agent + 3 click "
                    "fallbacks are LLM-pickable. Round 8 measured that "
                    "partial purging produces anchor-whack-a-mole; the "
                    "allowlist is the logical endpoint of Wiki-First "
                    "Routing. Strategy still callable internally when the "
                    "inferential agent's plans decide to route here.",
                )
            )
            continue
        extra_params = [p for p in params[1:] if p.name != "budget"]
        missing_required = [
            p.name
            for p in extra_params
            if p.default is inspect.Parameter.empty and p.name not in CTX_KEYS
        ]
        if missing_required:
            skipped.append(
                (short_name, f"requires runtime-only args: {missing_required}")
            )
            continue
        extra_names = [p.name for p in extra_params if p.name in CTX_KEYS]
        registry[short_name] = _make_wrapper(fn, extra_names)
    return registry, skipped
