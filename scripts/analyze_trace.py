"""Phase 8 R4 — deterministic trace analyzer.

Reads a WikiAgent run trace and emits a structured failure-pattern JSON that
the dev-time Cognition layer (Claude Code, per the architecture contract)
consumes to propose wiki/code edits.

Why this exists instead of a pure LLM reflector:

  The R4 experiment (2026-04-21) showed that Qwen 3 8B and 14B cannot
  reliably produce a structured reflection proposal when given the full
  architecture contract + brittle-tells + 40-env trace. Both models drifted
  into "describe the input" mode and echoed trace entries rather than
  proposing improvements. The falsification criterion in
  `.wiki/wiki/architecture.md` anticipated this: at 8B–14B scale, the LLM's
  meta-reasoning is too weak and reflection must be driven by Claude Code
  directly.

  This script does the deterministic part (aggregation, mismatch detection,
  failure-pattern grouping) and hands Claude Code a crisp JSON summary.
  The LLM-based reflector lives next door at `reflect_wiki_agent.py` for
  future use with larger models.

The analysis is deliberately simple — every rule here has a one-line
explanation in the output so Claude Code (or a future stronger LLM) can
audit the reasoning without re-deriving it.

Run:
    uv run python scripts/analyze_trace.py
    uv run python scripts/analyze_trace.py --trace scripts/wiki_agent_results.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TRACE = REPO_ROOT / "scripts" / "wiki_agent_results.json"
DEFAULT_OUT = REPO_ROOT / "scripts" / "trace_analysis.json"


def _is_cleared(env: dict[str, Any]) -> bool:
    return int(env.get("best_levels", 0) or 0) > 0


def _dir_signal_present(discovery: dict[str, Any]) -> bool:
    """True when discovery saw directional motion that any movement strategy
    could exploit — used to flag mis-routes to click strategies."""
    dm = discovery.get("dir_map") or {}
    return bool(dm)


def _is_click_strategy(name: str | None) -> bool:
    return bool(name) and name.startswith("click_")


def _is_movement_strategy(name: str | None) -> bool:
    if not name:
        return False
    movement_prefixes = (
        "bfs_",
        "wall_",
        "move_",
        "maze_",
        "platformer",
        "multi_character",
        "sokoban_",
        "spell_cast",
        "navigate",
        "sidescroll",
        "grab_and_deliver",
        "target_color_chase",
        "systematic_grid_walk",
        "smart_navigate",
        "all_combos",
        "action5_cycle",
        "pattern_repeat",
    )
    return any(name.startswith(p) for p in movement_prefixes) or name == "raster"


def analyze(trace: dict[str, Any]) -> dict[str, Any]:
    """Return a structured analysis. Every pattern has an `envs` field for
    traceability and an `evidence` string that Claude Code can cite when
    proposing edits."""
    results = trace.get("results", [])
    total = len(results)
    cleared = [r for r in results if _is_cleared(r)]
    failed = [r for r in results if not _is_cleared(r)]

    # --- Aggregates ---
    total_levels = sum(int(r.get("best_levels", 0) or 0) for r in results)
    predicted_type_counts = Counter(
        (r.get("hypothesis") or {}).get("game_type") for r in results
    )
    primary_picked_counts = Counter(
        (r.get("hypothesis") or {}).get("primary_strategy") for r in results
    )

    # Confidence distribution (only envs where LLM self-reported)
    confidences = [
        (r.get("hypothesis") or {}).get("confidence")
        for r in results
        if (r.get("hypothesis") or {}).get("confidence") is not None
    ]
    confidences = [float(c) for c in confidences if isinstance(c, (int, float))]

    # --- Pattern 1: dir_map present but click-only primary picked ---
    dir_to_click = []
    for r in results:
        disc = r.get("discovery") or {}
        hyp = r.get("hypothesis") or {}
        primary = hyp.get("primary_strategy")
        if _dir_signal_present(disc) and _is_click_strategy(primary):
            dir_to_click.append(
                {
                    "game_id": r.get("game_id"),
                    "title": r.get("game_title"),
                    "dir_map": disc.get("dir_map"),
                    "primary": primary,
                    "best_levels": r.get("best_levels"),
                }
            )

    # --- Pattern 2: movement predicted but non-movement primary picked ---
    movement_type_wrong_primary = []
    for r in results:
        hyp = r.get("hypothesis") or {}
        if hyp.get("game_type") == "movement" and not _is_movement_strategy(
            hyp.get("primary_strategy")
        ):
            movement_type_wrong_primary.append(
                {
                    "game_id": r.get("game_id"),
                    "title": r.get("game_title"),
                    "primary": hyp.get("primary_strategy"),
                    "best_levels": r.get("best_levels"),
                }
            )

    # --- Pattern 3: all executions status=ok but zero levels (wasted budget) ---
    wasted_budget = []
    for r in failed:
        execs = r.get("executions") or []
        if execs and all(
            e.get("status") == "ok" and (e.get("levels") or 0) == 0 for e in execs
        ):
            total_actions = sum(int(e.get("actions") or 0) for e in execs)
            wasted_budget.append(
                {
                    "game_id": r.get("game_id"),
                    "title": r.get("game_title"),
                    "primary": (r.get("hypothesis") or {}).get("primary_strategy"),
                    "fallback_stack": (r.get("hypothesis") or {}).get("fallback_stack"),
                    "total_actions": total_actions,
                    "strategies_tried": len(execs),
                }
            )

    # --- Pattern 4: unknown_strategy executions (LLM picked nonexistent name) ---
    unknown_strategy_picks = []
    for r in results:
        for e in r.get("executions") or []:
            if e.get("status") == "unknown_strategy":
                unknown_strategy_picks.append(
                    {
                        "game_id": r.get("game_id"),
                        "title": r.get("game_title"),
                        "invented_name": e.get("strategy"),
                    }
                )

    # --- Pattern 5: LLM-flagged missing features ---
    features_missing_reports: dict[str, list[str]] = defaultdict(list)
    for r in results:
        fm = (r.get("hypothesis") or {}).get("features_missing") or []
        for feat in fm:
            features_missing_reports[str(feat)].append(r.get("game_id") or "?")

    # --- Per-primary success rate ---
    primary_success: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"attempts": 0, "cleared": 0, "levels": 0}
    )
    for r in results:
        primary = (r.get("hypothesis") or {}).get("primary_strategy")
        if not primary:
            continue
        primary_success[primary]["attempts"] += 1
        if _is_cleared(r):
            primary_success[primary]["cleared"] += 1
        primary_success[primary]["levels"] += int(r.get("best_levels", 0) or 0)

    return {
        "headline": {
            "total_envs": total,
            "envs_cleared": len(cleared),
            "envs_failed": len(failed),
            "total_levels": total_levels,
            "mean_confidence": (
                round(sum(confidences) / len(confidences), 3) if confidences else None
            ),
        },
        "predicted_type_distribution": dict(predicted_type_counts),
        "primary_strategy_counts": dict(primary_picked_counts),
        "primary_success_rates": {
            name: {
                **stats,
                "cleared_pct": (
                    round(stats["cleared"] / stats["attempts"], 3)
                    if stats["attempts"]
                    else 0.0
                ),
            }
            for name, stats in primary_success.items()
        },
        "patterns": {
            "dir_map_but_click_primary": {
                "count": len(dir_to_click),
                "evidence": (
                    "Discovery saw directional motion (dir_map populated) but the LLM picked "
                    "a click-only primary. Movement games tend to fail without a movement "
                    "strategy in the primary slot."
                ),
                "envs": dir_to_click,
            },
            "movement_type_non_movement_primary": {
                "count": len(movement_type_wrong_primary),
                "evidence": (
                    "LLM predicted game_type='movement' but picked a non-movement primary "
                    "strategy. Suggests the strategy selection rule is inconsistent with "
                    "the type classification."
                ),
                "envs": movement_type_wrong_primary,
            },
            "wasted_budget_zero_levels": {
                "count": len(wasted_budget),
                "evidence": (
                    "All fallback strategies ran to completion (status=ok) with zero level "
                    "gain. Suggests neither the primary nor fallbacks had signal for this env."
                ),
                "envs": wasted_budget,
            },
            "unknown_strategy_picks": {
                "count": len(unknown_strategy_picks),
                "evidence": (
                    "LLM invented a strategy name not in the whitelist. Indicates the "
                    "strategy whitelist or prompt rule was ignored."
                ),
                "envs": unknown_strategy_picks,
            },
            "llm_flagged_missing_features": {
                "count": sum(len(v) for v in features_missing_reports.values()),
                "evidence": (
                    "The LLM self-reported features it wanted but did not have. Direct input "
                    "to R2 expansion — add the feature if derivable from frames."
                ),
                "by_feature": {
                    name: sorted(set(envs))
                    for name, envs in features_missing_reports.items()
                },
            },
        },
        "_meta": {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "trace_timestamp": trace.get("timestamp"),
            "trace_candidate": trace.get("candidate"),
            "deterministic": True,
            "note": (
                "Produced without LLM assistance. Claude Code (dev-time Cognition) "
                "reads this file and proposes wiki/code edits."
            ),
        },
    }


def _print_summary(report: dict[str, Any]) -> None:
    h = report["headline"]
    print(
        f"\n=== Trace analysis ===\n"
        f"  envs_cleared   : {h['envs_cleared']}/{h['total_envs']}\n"
        f"  total_levels   : {h['total_levels']}\n"
        f"  mean_confidence: {h['mean_confidence']}\n"
    )
    for name, p in report["patterns"].items():
        if p["count"] > 0:
            print(f"  {name:<38} {p['count']:>3} envs")
    print()
    # Top primary strategies by usage
    picks = report["primary_strategy_counts"]
    top = sorted(picks.items(), key=lambda kv: -kv[1])[:5]
    print("  Top-5 primary picks:")
    for name, n in top:
        rate = report["primary_success_rates"].get(name, {}).get("cleared_pct", 0.0)
        print(f"    {name:<28} picked {n:>2}× cleared_pct={rate}")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="R4 deterministic trace analyzer (no LLM)."
    )
    ap.add_argument("--trace", type=Path, default=DEFAULT_TRACE)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    if not args.trace.exists():
        print(f"trace not found: {args.trace}", file=sys.stderr)
        return 2
    trace = json.loads(args.trace.read_text())
    report = analyze(trace)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"Wrote {args.out}", flush=True)
    _print_summary(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
