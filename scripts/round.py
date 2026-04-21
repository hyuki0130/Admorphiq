"""Phase 8 R7d — dev-time round protocol.

Formalizes each iteration of the dev-time loop as a directory under
`.omc/rounds/round_NNN/` with:

  meta.json   — structured metadata (goal, bench-before, bench-after, verdict,
                changes made, prior-round learnings used)
  notes.md    — freeform work log Claude Code writes during the round

Why this exists: without a protocol the "we'll iterate" plan erodes into
ad-hoc bench runs whose provenance gets lost. With it, `round.py learnings N`
replays the accumulated takeaways into the next round's Qwen prompt, closing
the `round_learnings` slot that R7c's template reserves.

Lifecycle:
  1. `round.py start N --goal "..."`     -> init round_NNN/ + meta.json
  2. (apply changes, run bench)           -> scripts/wiki_agent_results_rN.json
  3. `round.py finalize N --trace <path>` -> compute after-summary, verdict
  4. `round.py learnings N`               -> prints carryover for round N+1
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
ROUNDS_DIR = REPO_ROOT / ".omc" / "rounds"
BASELINE_PATH = REPO_ROOT / "scripts" / "regression_baseline.json"


def round_dir(n: int) -> Path:
    return ROUNDS_DIR / f"round_{n:03d}"


def _summary_of_trace(trace: dict[str, Any]) -> dict[str, Any]:
    """Aggregate the trace to the same view the regression gate uses."""
    by_gid: dict[str, dict[str, Any]] = {}
    by_title: dict[str, int] = {}
    for r in trace.get("results", []):
        gid = r.get("game_id")
        title = r.get("game_title")
        levels = int(r.get("best_levels", 0) or 0)
        if gid:
            prev = by_gid.get(gid)
            if prev is None or levels > int(prev.get("levels") or 0):
                by_gid[gid] = {"title": title, "levels": levels}
        if title:
            by_title[title] = max(by_title.get(title, 0), levels)
    cleared = sum(1 for r in by_gid.values() if (r.get("levels") or 0) > 0)
    total_levels = sum(int(r.get("levels") or 0) for r in by_gid.values())
    return {
        "envs_cleared": cleared,
        "total_envs": len(by_gid),
        "total_levels": total_levels,
        "by_game_id": by_gid,
        "by_title": by_title,
    }


def _summary_of_baseline(baseline: dict[str, Any]) -> dict[str, Any]:
    """Extract the same shape from a stored baseline file."""
    by_gid = baseline.get("by_game_id", {}) or {}
    cleared = sum(1 for r in by_gid.values() if (r.get("levels") or 0) > 0)
    total = sum(int(r.get("levels") or 0) for r in by_gid.values())
    return {
        "envs_cleared": cleared,
        "total_envs": len(by_gid),
        "total_levels": total,
        "by_game_id": by_gid,
        "by_title": baseline.get("by_title", {}) or {},
    }


def _compute_verdict(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Strict per-game_id comparison, same rule as regression_gate."""
    regressions = []
    improvements = []
    old_gid = before.get("by_game_id", {})
    new_gid = after.get("by_game_id", {})
    for gid, new_rec in new_gid.items():
        if gid not in old_gid:
            continue
        old_lvl = int(old_gid[gid].get("levels") or 0)
        new_lvl = int(new_rec.get("levels") or 0)
        if new_lvl < old_lvl:
            regressions.append({"game_id": gid, "title": new_rec.get("title"), "delta": new_lvl - old_lvl})
        elif new_lvl > old_lvl:
            improvements.append({"game_id": gid, "title": new_rec.get("title"), "delta": new_lvl - old_lvl})
    return {
        "status": "FAIL" if regressions else "PASS",
        "regressions": regressions,
        "improvements": improvements,
        "cleared_delta": after["envs_cleared"] - before["envs_cleared"],
        "levels_delta": after["total_levels"] - before["total_levels"],
    }


def _collect_prior_learnings(current_round: int) -> str:
    """Concatenate prior rounds' verdicts+takeaways into a carryover string.

    Returns a human-readable paragraph that WikiAgent can inject into Qwen's
    prompt via the `round_learnings` field. Empty (default placeholder)
    when no prior rounds exist.
    """
    if not ROUNDS_DIR.exists():
        return ""
    chunks: list[str] = []
    for prev in sorted(ROUNDS_DIR.iterdir()):
        if not prev.is_dir() or not prev.name.startswith("round_"):
            continue
        try:
            n = int(prev.name.split("_")[1])
        except (IndexError, ValueError):
            continue
        if n >= current_round:
            continue
        meta_path = prev / "meta.json"
        if not meta_path.exists():
            continue
        meta = json.loads(meta_path.read_text())
        verdict = meta.get("verdict") or {}
        takeaway = meta.get("takeaway", "").strip()
        if not takeaway:
            continue
        chunks.append(
            f"Round {n} ({verdict.get('status', '?')}, levels "
            f"{verdict.get('levels_delta', 0):+d}): {takeaway}"
        )
    return "\n".join(chunks)


def cmd_start(args: argparse.Namespace) -> int:
    dir_ = round_dir(args.n)
    if dir_.exists():
        print(f"{dir_} already exists — refusing to overwrite", file=sys.stderr)
        return 2
    dir_.mkdir(parents=True)

    before_summary = None
    if BASELINE_PATH.exists():
        before_summary = _summary_of_baseline(json.loads(BASELINE_PATH.read_text()))

    meta = {
        "round_num": args.n,
        "goal": args.goal,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "finished_at": None,
        "before_summary": before_summary,
        "after_summary": None,
        "verdict": None,
        "changes_made": [],
        "takeaway": "",
        "prior_learnings_used": _collect_prior_learnings(args.n),
    }
    (dir_ / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    (dir_ / "notes.md").write_text(
        f"# Round {args.n} notes\n\n## Goal\n\n{args.goal}\n\n## Work log\n\n"
    )
    print(f"Initialized {dir_}")
    return 0


def cmd_finalize(args: argparse.Namespace) -> int:
    dir_ = round_dir(args.n)
    meta_path = dir_ / "meta.json"
    if not meta_path.exists():
        print(f"{meta_path} missing — run `round.py start {args.n}` first", file=sys.stderr)
        return 2
    if not args.trace.exists():
        print(f"trace not found: {args.trace}", file=sys.stderr)
        return 2

    meta = json.loads(meta_path.read_text())
    trace = json.loads(args.trace.read_text())
    after = _summary_of_trace(trace)
    before = meta.get("before_summary") or {"by_game_id": {}, "by_title": {}, "envs_cleared": 0, "total_envs": 0, "total_levels": 0}
    verdict = _compute_verdict(before, after)

    meta["after_summary"] = after
    meta["verdict"] = verdict
    meta["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    meta["trace_source"] = str(args.trace)
    if args.takeaway:
        meta["takeaway"] = args.takeaway
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False))

    print(
        f"\nRound {args.n} {verdict['status']}: "
        f"cleared {before['envs_cleared']} -> {after['envs_cleared']} "
        f"(Δ {verdict['cleared_delta']:+d})   "
        f"levels {before['total_levels']} -> {after['total_levels']} "
        f"(Δ {verdict['levels_delta']:+d})"
    )
    if verdict["regressions"]:
        print(f"  regressions ({len(verdict['regressions'])}):")
        for r in verdict["regressions"]:
            print(f"    - {r['game_id']} ({r['title']}) {r['delta']:+d}")
    if verdict["improvements"]:
        print(f"  improvements ({len(verdict['improvements'])}):")
        for r in verdict["improvements"][:10]:
            print(f"    + {r['game_id']} ({r['title']}) {r['delta']:+d}")
    return 0 if verdict["status"] == "PASS" else 1


def cmd_learnings(args: argparse.Namespace) -> int:
    text = _collect_prior_learnings(args.n)
    if not text:
        print(
            "(First round. No prior rounds' learnings to carry. Respond based "
            "on the discovery data and wiki context directly.)"
        )
    else:
        print(text)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Phase 8 dev-time round protocol (R7d).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_start = sub.add_parser("start", help="Initialize round_NNN/ with a goal")
    p_start.add_argument("n", type=int)
    p_start.add_argument("--goal", required=True, help="1-2 sentence round goal")
    p_start.set_defaults(func=cmd_start)

    p_final = sub.add_parser("finalize", help="Compute verdict from bench trace")
    p_final.add_argument("n", type=int)
    p_final.add_argument("--trace", type=Path, required=True)
    p_final.add_argument("--takeaway", default="", help="One-line lesson for future rounds")
    p_final.set_defaults(func=cmd_finalize)

    p_learn = sub.add_parser(
        "learnings", help="Print prior rounds' learnings for a Qwen prompt"
    )
    p_learn.add_argument("n", type=int, help="Round you're about to start")
    p_learn.set_defaults(func=cmd_learnings)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
