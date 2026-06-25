"""Analyze a WikiAgent trace for retrieval coverage and LLM page-utilisation.

Reads `scripts/wiki_agent_results_*.json` and reports:

  1. **Retrieval coverage** — for each env, which pages were fetched, how
     many chars per page, and how close the budget was to saturation.
     Aggregates: which pages appear in ≥X% of envs (seed-confirmed),
     which pages appear in 0% of envs (unreachable via current retrieval).
  2. **Page utilisation** — for each retrieved page, lowercase word overlap
     between the page content and the LLM's `rationale` text. High overlap
     means the LLM cited / paraphrased that page; low overlap means the
     page was retrieved but not used in reasoning.
  3. **Rule compliance** — what primary strategy the LLM picked vs what
     `decision_tree.md` would mandate from the env's discovery signature.
  4. **Anchor diagnostic** — across all envs, how many distinct primaries
     the LLM used; if Qwen converged to one or two, anchor-pathology is
     present.

Run:
    uv run python scripts/analyze_wiki_agent_trace.py \
        --trace scripts/wiki_agent_results_r23_14b_v3.json

Output:
    - Markdown report on stdout
    - `scripts/analyze_wiki_agent_v3.json` machine-readable detail
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
WIKI_DIR = REPO_ROOT / ".wiki" / "wiki"

STOPWORDS = frozenset(
    {
        "the", "and", "for", "are", "with", "this", "that", "from",
        "have", "been", "were", "they", "their", "them", "then",
        "than", "into", "when", "what", "which", "where", "while",
        "should", "could", "would", "must", "will", "must",
        "your", "some", "more", "most", "such", "very",
        "also", "only", "each", "other", "even", "many",
        "after", "before", "between", "across", "around",
        "click", "actions", "action", "primary", "fallback",
        "strategy", "strategies",
    }
)
WORD_RE = re.compile(r"[a-z][a-z0-9_]{3,}")


def page_word_set(path: Path) -> frozenset[str]:
    try:
        text = path.read_text().lower()
    except OSError:
        return frozenset()
    words = set(WORD_RE.findall(text))
    return frozenset(w for w in words if w not in STOPWORDS)


def utilisation(rationale: str, page_words: frozenset[str]) -> tuple[int, int]:
    """Return (overlap_count, page_size) — higher overlap = stronger evidence
    the LLM used the page."""
    rwords = set(WORD_RE.findall(rationale.lower())) - STOPWORDS
    if not rwords or not page_words:
        return 0, len(page_words)
    return len(rwords & page_words), len(page_words)


def discovery_to_expected(disc: dict) -> str:
    """Tiny rule-engine implementing the decision_tree.md table."""
    avail = set(disc.get("available_actions") or [])
    avail.discard(0)
    avail.discard(7)
    probe = disc.get("probe_diffs") or {}

    has_click = 6 in avail
    has_dir = bool({1, 2, 3, 4} & avail)
    dir_probes = [int(probe.get(str(a), probe.get(a, 0))) for a in (1, 2, 3, 4) if a in avail]
    if dir_probes and min(dir_probes) > 0:
        ratio = max(dir_probes) / max(1, min(dir_probes))
    else:
        ratio = 0
    click_responsive = len(disc.get("click_responsive_cells") or [])

    if has_dir and not has_click and dir_probes and ratio <= 2:
        return "bfs_state_space"
    if has_click and not has_dir and click_responsive == 0:
        return "click_rare"
    if has_click and click_responsive >= 3 and ratio >= 5:
        return "click_color_order"  # paint shape
    if has_dir and has_click:
        return "bfs_state_space"  # movement-hybrid default
    if has_click:
        return "click_toggle_detect"
    return "adaptive_bfs_solver"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--trace", type=Path, required=True)
    ap.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "scripts" / "analyze_wiki_agent_v3.json",
    )
    args = ap.parse_args()

    if not args.trace.exists():
        print(f"trace not found: {args.trace}", file=sys.stderr)
        return 2

    data = json.loads(args.trace.read_text())
    results = data.get("results", [])
    if not results:
        print("no results in trace", file=sys.stderr)
        return 2

    page_words_cache: dict[str, frozenset[str]] = {}

    def words_for(path: str) -> frozenset[str]:
        if path not in page_words_cache:
            page_words_cache[path] = page_word_set(WIKI_DIR / path)
        return page_words_cache[path]

    # Aggregate buckets
    page_appearance = collections.Counter()
    page_total_chars = collections.Counter()
    page_clip_count = collections.Counter()
    saturation_buckets = collections.Counter()
    primaries = collections.Counter()
    fallback_total = collections.Counter()
    rule_match = 0
    rule_total = 0
    distinct_primaries: set[str] = set()
    per_env: list[dict] = []

    for r in results:
        title = r.get("game_title", "?")
        disc = r.get("discovery", {})
        hyp = r.get("hypothesis", {})
        primary = hyp.get("primary_strategy", "?")
        primaries[primary] += 1
        distinct_primaries.add(primary)
        for s in hyp.get("fallback_stack", []):
            fallback_total[s] += 1

        budget = r.get("context_budget", 0)
        wiki_chars = r.get("wiki_context_chars", 0)
        sat = wiki_chars / budget if budget else 0
        saturation_buckets[round(sat, 1)] += 1

        details = r.get("retrieved_pages_detail") or [
            {"path": p, "chars": 0} for p in r.get("retrieved_pages", [])
        ]
        rationale = hyp.get("rationale", "") or ""
        per_page_util: list[dict] = []
        for d in details:
            p = d["path"]
            page_appearance[p] += 1
            page_total_chars[p] += d.get("chars", 0)
            full_size = (WIKI_DIR / p).stat().st_size if (WIKI_DIR / p).exists() else d.get("chars", 0)
            if d.get("chars", 0) and full_size and d["chars"] < full_size:
                page_clip_count[p] += 1
            overlap, total = utilisation(rationale, words_for(p))
            per_page_util.append(
                {
                    "path": p,
                    "chars": d.get("chars", 0),
                    "page_words": total,
                    "rationale_overlap": overlap,
                    "util_pct": round(100 * overlap / max(total, 1), 1),
                }
            )

        expected = discovery_to_expected(disc)
        followed = primary == expected
        rule_total += 1
        if followed:
            rule_match += 1

        per_env.append(
            {
                "title": title,
                "primary": primary,
                "expected_by_decision_tree": expected,
                "rule_followed": followed,
                "best_levels": r.get("best_levels", 0),
                "wiki_context_chars": wiki_chars,
                "budget": budget,
                "saturation": round(sat, 2),
                "page_count": len(details),
                "page_utilisation": per_page_util,
            }
        )

    n = len(results)
    out: dict[str, Any] = {
        "trace_file": str(args.trace),
        "candidate": data.get("candidate"),
        "envs": n,
        "primary_distribution": dict(primaries.most_common()),
        "fallback_distribution": dict(fallback_total.most_common()),
        "distinct_primaries": len(distinct_primaries),
        "rule_compliance_pct": round(100 * rule_match / max(rule_total, 1), 1),
        "page_appearance": {
            p: {
                "envs": cnt,
                "envs_pct": round(100 * cnt / n, 1),
                "avg_chars": round(page_total_chars[p] / cnt, 1) if cnt else 0,
                "envs_clipped": page_clip_count[p],
            }
            for p, cnt in page_appearance.most_common()
        },
        "saturation_histogram": dict(saturation_buckets),
        "per_env": per_env,
    }
    args.out.write_text(json.dumps(out, indent=2))

    # --- markdown report ---
    print("# WikiAgent trace analysis")
    print()
    print(f"- Trace: `{args.trace.name}`")
    print(f"- Candidate: `{out['candidate']}`")
    print(f"- Envs: {n}")
    print()

    print("## Primary distribution")
    print()
    for p, c in primaries.most_common():
        print(f"- `{p}`: {c}/{n} ({100*c/n:.0f}%)")
    print()
    print(f"Distinct primaries used: **{len(distinct_primaries)}**.")
    print()

    print("## Rule compliance (vs decision_tree.md)")
    print()
    print(
        f"LLM primary matched the decision-tree expected strategy in "
        f"**{rule_match}/{rule_total}** envs ({100*rule_match/max(rule_total,1):.0f}%)."
    )
    print()

    print("## Retrieval coverage")
    print()
    print("| Page | Envs (%) | Avg chars | Times clipped |")
    print("|---|---|---|---|")
    for p, info in sorted(out["page_appearance"].items(), key=lambda kv: -kv[1]["envs"]):
        if info["envs"] == 0:
            continue
        print(
            f"| `{p}` | {info['envs']}/{n} ({info['envs_pct']:.0f}%) | "
            f"{info['avg_chars']:.0f} | {info['envs_clipped']} |"
        )
    print()

    print("## Saturation histogram (wiki_chars / budget)")
    print()
    for bucket in sorted(saturation_buckets):
        cnt = saturation_buckets[bucket]
        print(f"- {bucket:.1f}: {cnt} envs")
    print()

    # Page utilisation aggregate
    print("## LLM page utilisation (rationale ∩ page-words / page-words)")
    print()
    util_per_page: dict[str, list[float]] = collections.defaultdict(list)
    for env in per_env:
        for p in env["page_utilisation"]:
            util_per_page[p["path"]].append(p["util_pct"])
    print("| Page | Mean util % | Max util % | N envs |")
    print("|---|---|---|---|")
    for path in sorted(util_per_page, key=lambda k: -sum(util_per_page[k]) / len(util_per_page[k])):
        ps = util_per_page[path]
        mean_u = sum(ps) / len(ps)
        max_u = max(ps)
        print(f"| `{path}` | {mean_u:.1f}% | {max_u:.1f}% | {len(ps)} |")
    print()

    print(f"Detail JSON: `{args.out}`")
    return 0


if __name__ == "__main__":
    sys.exit(main())
