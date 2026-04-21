"""Phase 8 R4 — reflection module.

Reads a WikiAgent run trace (`scripts/wiki_agent_results.json`), condenses
it, and asks the configured LLM to propose concrete improvements as a JSON
object. The output is advisory — application is a separate step (Claude
Code reads the proposal and implements it under human supervision, per the
architecture contract in `.wiki/wiki/architecture.md`).

The script does no env I/O. It only reads files and calls the LLM backend,
so it can run on any machine with Ollama + the pulled candidate.

Run:
    uv run python scripts/reflect_wiki_agent.py
    uv run python scripts/reflect_wiki_agent.py --trace scripts/wiki_agent_results.json
    uv run python scripts/reflect_wiki_agent.py --candidate qwen_3_14b_q4
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

from admorphiq.hypothesis import CTX_KEYS, default_strategy_registry
from admorphiq.llm import load_candidate, load_registry


REPO_ROOT = Path(__file__).resolve().parent.parent
ARCH_DOC = REPO_ROOT / ".wiki" / "wiki" / "architecture.md"
BRITTLE_TELLS = REPO_ROOT / ".wiki" / "wiki" / "lessons" / "brittle_tells.md"
DEFAULT_TRACE = REPO_ROOT / "scripts" / "wiki_agent_results.json"
DEFAULT_OUT = REPO_ROOT / "scripts" / "reflection_proposal.json"


_PROMPT_TEMPLATE = """TASK: You are the Phase 8 reflection agent for Admorphiq (an ARC-AGI-3 AI
solver). Below you will see an architecture contract, context keys, strategy
whitelist, and a WikiAgent run trace. Your ONLY job is to emit one JSON
object analyzing the trace and proposing improvements. Do NOT describe the
input. Do NOT write an introduction. Do NOT use markdown code fences. Your
entire response MUST be exactly one JSON object.

EXAMPLE OF A WELL-FORMED RESPONSE (illustrative content — replace with your
own analysis of the actual trace):

{{"summary": "15/40 envs cleared. Main failure: movement games with avail=[1..4,6] were mis-routed to click_rare despite dir_map being populated.",
 "failure_patterns": [
   {{"pattern": "movement game routed to click strategy",
     "envs": ["M0R0", "KA59", "CN04"],
     "root_cause_hypothesis": "LLM ignored dir_map when avail included action 6; selector rules did not disambiguate"}}
 ],
 "wiki_edits": [
   {{"path": "wiki/selector.md",
     "operation": "append",
     "section": null,
     "content": "## Rule override\\n`dir_map` non-empty AND `movable_region_count == 1` → movement, regardless of action-6 availability",
     "why": "prevents click_rare routing when a sprite clearly moves"}}
 ],
 "new_features": [
   {{"name": "sprite_pixel_count",
     "derive_recipe": "Count pixels whose color equals `player_color` in the RESET frame.",
     "expected_signal": "Small (<=4) = point-player; larger = extended sprite (slider, platformer).",
     "why": "Distinguishes slider_puzzle from basic movement."}}
 ],
 "new_strategies": [
   {{"name": "navigate_until_level_up",
     "sketch": "BFS over movement actions, prioritize actions that increase levels_completed observable via env.step return.",
     "needs": ["dir_actions"],
     "why": "Movement games without a clear reward signal."}}
 ]}}

CONSTRAINTS:
- Do NOT propose brittle solvers that read game-internal attributes (see the
  brittle_tells lesson below).
- Do NOT propose features requiring network access or external data.
- Every `new_feature` MUST be derivable from the frames already captured in
  the probe phase (RESET frame + per-action before/after diffs).
- Return an empty list for any category with no honest proposal.
- Keep the full response under 2000 tokens.

=== ARCHITECTURE CONTRACT (load-bearing — do not contradict) ===
{architecture}

=== BRITTLE TELLS (what NOT to propose) ===
{brittle}

=== CURRENT CONTEXT KEYS ===
{ctx_keys}

=== CURRENT DISPATCHABLE STRATEGIES ({n_strategies}) ===
{strategies}

=== RUN TRACE (condensed — THIS is what you analyze) ===
{trace}

NOW output the JSON object. Start your response with `{{` and end with `}}`.
Nothing else."""


def _pick_default_candidate() -> str:
    for meta in load_registry():
        if meta.enabled:
            return meta.id
    raise RuntimeError("No enabled candidate in configs/llm.yaml")


def _summarize_trace(trace: dict[str, Any]) -> dict[str, Any]:
    """Condense the raw trace to the signals reflection needs.

    Drops per-game verbose dominant_colors / click_responsive_cells detail;
    keeps only the classification input + outcome + execution breakdown.
    """
    results = trace.get("results", [])
    per_env = []
    for r in results:
        disc = r.get("discovery", {})
        hyp = r.get("hypothesis", {})
        execs = [
            {
                "strategy": e.get("strategy"),
                "status": e.get("status"),
                "levels": e.get("levels"),
                "actions": e.get("actions"),
            }
            for e in r.get("executions", [])
        ]
        per_env.append(
            {
                "game_id": r.get("game_id"),
                "game_title": r.get("game_title"),
                "avail": disc.get("available_actions"),
                "dir_map": disc.get("dir_map"),
                "player_color": disc.get("player_color"),
                "movable_region_count": disc.get("movable_region_count"),
                "change_topology": disc.get("change_topology"),
                "probe_diffs": disc.get("probe_diffs"),
                "predicted_type": hyp.get("game_type"),
                "primary_strategy": hyp.get("primary_strategy"),
                "fallback_stack": hyp.get("fallback_stack"),
                "confidence": hyp.get("confidence"),
                "features_missing": hyp.get("features_missing"),
                "best_levels": r.get("best_levels"),
                "executions": execs,
            }
        )
    total_levels = sum(int(p.get("best_levels", 0) or 0) for p in per_env)
    envs_cleared = sum(1 for p in per_env if (p.get("best_levels") or 0) > 0)
    return {
        "timestamp": trace.get("timestamp"),
        "candidate": trace.get("candidate"),
        "total_envs": len(per_env),
        "envs_cleared": envs_cleared,
        "total_levels": total_levels,
        "per_env": per_env,
    }


def _parse_proposal(raw: str) -> dict[str, Any]:
    """Extract the JSON proposal from the LLM response.

    Priority order (an 8B-class model frequently emits multiple braces — one
    from the example, one parroting trace entries, one as its own answer):

      1. Fenced code block containing `"summary"` (most reliable).
      2. Any balanced `{...}` span whose top-level keys include `"summary"`.
      3. Largest balanced `{...}` span by length (last-resort).
      4. Error stub with raw head.

    The `"summary"` heuristic pins the parser to the actual proposal rather
    than an in-text example or a trace snippet.
    """
    if not raw:
        return {"error": "empty response"}

    # Collect every balanced brace span by naive stack matching.
    spans: list[str] = []
    depth = 0
    start = -1
    for i, ch in enumerate(raw):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start >= 0:
                    spans.append(raw[start : i + 1])
                    start = -1

    if not spans:
        return {"error": "no JSON object in response", "raw_head": raw[:1500]}

    # Prefer spans that parse AND contain the top-level "summary" key.
    candidates = []
    for span in spans:
        try:
            obj = json.loads(span)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "summary" in obj:
            candidates.append((len(span), obj))
    if candidates:
        # Among summary-bearing candidates, the longest is the richest proposal.
        candidates.sort(key=lambda t: -t[0])
        return candidates[0][1]

    # No span had "summary" — try the largest parseable one as a fallback.
    spans_sorted = sorted(spans, key=len, reverse=True)
    for span in spans_sorted:
        try:
            return json.loads(span)
        except json.JSONDecodeError:
            continue

    return {"error": "no parseable JSON object", "raw_head": raw[:1500]}


def _validate_schema(proposal: dict[str, Any]) -> list[str]:
    """Return a list of schema issues (empty = OK)."""
    issues: list[str] = []
    if "error" in proposal:
        return [f"proposal contains error: {proposal['error']}"]
    for key, expected_type in (
        ("summary", str),
        ("failure_patterns", list),
        ("wiki_edits", list),
        ("new_features", list),
        ("new_strategies", list),
    ):
        if key not in proposal:
            issues.append(f"missing field: {key}")
        elif not isinstance(proposal[key], expected_type):
            issues.append(f"field {key!r} has wrong type: {type(proposal[key]).__name__}")
    return issues


def _print_summary(proposal: dict[str, Any]) -> None:
    print("\n=== Reflection summary ===", flush=True)
    if "error" in proposal:
        print(f"  ERROR: {proposal['error']}")
        return
    print(f"  {proposal.get('summary', '<no summary>')}")
    print(f"  failure_patterns: {len(proposal.get('failure_patterns', []))}")
    print(f"  wiki_edits:       {len(proposal.get('wiki_edits', []))}")
    print(f"  new_features:     {len(proposal.get('new_features', []))}")
    print(f"  new_strategies:   {len(proposal.get('new_strategies', []))}")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="R4 reflection: LLM reviews trace.json and proposes edits."
    )
    ap.add_argument("--trace", type=Path, default=DEFAULT_TRACE)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--candidate", default=None, help="LLM candidate id (default: first enabled)")
    ap.add_argument("--max-tokens", type=int, default=2048)
    ap.add_argument(
        "--arch-char-cap",
        type=int,
        default=6000,
        help="Max chars from architecture.md fed to the prompt",
    )
    args = ap.parse_args()

    if not args.trace.exists():
        print(f"trace not found: {args.trace}", file=sys.stderr)
        return 2

    trace = json.loads(args.trace.read_text())
    condensed = _summarize_trace(trace)
    arch = ARCH_DOC.read_text() if ARCH_DOC.exists() else "<architecture.md missing>"
    brittle = BRITTLE_TELLS.read_text() if BRITTLE_TELLS.exists() else ""
    strategies = sorted(default_strategy_registry().keys())

    prompt_body = _PROMPT_TEMPLATE.format(
        architecture=arch[: args.arch_char_cap],
        brittle=brittle[:3000],
        ctx_keys=sorted(CTX_KEYS),
        n_strategies=len(strategies),
        strategies=", ".join(strategies),
        trace=json.dumps(condensed, indent=2)[:14000],
    )
    # Prefill anchor: 8B-class models recency-bias toward the last JSON they
    # saw (the trace) and will echo a trace entry instead of generating the
    # proposal. Anchoring the completion at `{"summary":` pins it to the
    # correct shape; we prepend the anchor back before parsing.
    anchor = '{"summary": "'
    prompt = prompt_body + "\n\n" + anchor

    cid = args.candidate or _pick_default_candidate()
    print(f"Loading LLM candidate: {cid}", flush=True)
    llm = load_candidate(cid)

    t0 = time.time()
    completion = llm.generate(prompt, max_tokens=args.max_tokens)
    elapsed = time.time() - t0
    raw = anchor + completion
    print(f"Generated {len(completion)} chars in {elapsed:.1f}s (prefill anchor on)", flush=True)

    proposal = _parse_proposal(raw)
    issues = _validate_schema(proposal)
    # Always persist the raw LLM output alongside the parsed proposal so we
    # can diagnose schema failures without re-running the LLM call.
    raw_out = args.out.with_suffix(".raw.txt")
    raw_out.write_text(raw)
    proposal["_meta"] = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "candidate_id": cid,
        "trace_source": str(args.trace),
        "latency_sec": round(elapsed, 1),
        "raw_response_length": len(raw),
        "raw_response_path": str(raw_out),
        "schema_issues": issues,
        "trace_summary": {
            "total_envs": condensed["total_envs"],
            "envs_cleared": condensed["envs_cleared"],
            "total_levels": condensed["total_levels"],
        },
    }

    args.out.write_text(json.dumps(proposal, indent=2, ensure_ascii=False))
    print(f"Wrote {args.out}", flush=True)
    _print_summary(proposal)
    if issues:
        print(f"\n  schema issues: {issues}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
