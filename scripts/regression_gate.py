"""Phase 8 R5 — regression gate.

Compares a new WikiAgent run trace against a stored baseline and flags any
env whose cleared-level count dropped. The gate's verdict drives whether a
proposed change (wiki edit, new feature, new strategy, config tweak) is
kept or rolled back — see `.wiki/wiki/architecture.md` step 4.

Two views are computed to cope with the ARC Prize API's hash-rotation
behavior (see `.wiki/wiki/lessons/api_hash_rotation_20260421.md`):

  by_game_id  — strict, same (title, hash) pair only. Catches "same env
                scored lower after my change."
  by_title    — aggregate, best_levels across all current hashes of a
                title. Catches "v1 was 9 levels, but after my change
                v1 dropped to 5 even though v2 reached 6."

The gate **fails** only on strict by_game_id regressions. The by_title
delta is reported for awareness but does not block — API hash rotations
create and destroy envs outside our control.

Baseline is stored at `scripts/regression_baseline.json`. Seed it with
`--seed` on first use; afterwards use `--promote` after a PASS to update.

Run:
    uv run python scripts/regression_gate.py                   # just compare
    uv run python scripts/regression_gate.py --seed            # first time
    uv run python scripts/regression_gate.py --promote         # update baseline after PASS
    uv run python scripts/regression_gate.py --trace other.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TRACE = REPO_ROOT / "scripts" / "wiki_agent_results.json"
DEFAULT_BASELINE = REPO_ROOT / "scripts" / "regression_baseline.json"

# Exit codes (scripted consumers can branch on these):
EXIT_PASS = 0
EXIT_REGRESSIONS = 1
EXIT_INPUT_ERROR = 2


def summarize(trace: dict[str, Any]) -> dict[str, Any]:
    """Extract the minimal per-env record the gate compares on.

    When the same game_id appears multiple times in the trace (WikiAgent
    sometimes plays the same env twice across v1/v2 discovery passes), the
    MAX levels is kept — the gate cares about best achievable, not the
    most-recent run of an env.
    """
    summary: dict[str, Any] = {
        "timestamp": trace.get("timestamp"),
        "candidate": trace.get("candidate"),
        "by_game_id": {},
        "by_title": {},
    }
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
    summary["by_game_id"] = by_gid
    summary["by_title"] = by_title
    return summary


def compare(new: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    """Return a structured diff with strict and aggregate views.

    A regression is a decrease in the strict `by_game_id` view; anything
    else is informational.
    """
    new_gid = new.get("by_game_id", {})
    old_gid = baseline.get("by_game_id", {})
    new_title = new.get("by_title", {})
    old_title = baseline.get("by_title", {})

    regressions: list[dict[str, Any]] = []
    improvements: list[dict[str, Any]] = []
    held: list[str] = []
    for gid, rec in new_gid.items():
        if gid not in old_gid:
            continue
        old_lvl = int(old_gid[gid].get("levels", 0) or 0)
        new_lvl = int(rec.get("levels", 0) or 0)
        if new_lvl < old_lvl:
            regressions.append(
                {
                    "game_id": gid,
                    "title": rec.get("title"),
                    "baseline_levels": old_lvl,
                    "new_levels": new_lvl,
                    "delta": new_lvl - old_lvl,
                }
            )
        elif new_lvl > old_lvl:
            improvements.append(
                {
                    "game_id": gid,
                    "title": rec.get("title"),
                    "baseline_levels": old_lvl,
                    "new_levels": new_lvl,
                    "delta": new_lvl - old_lvl,
                }
            )
        else:
            held.append(gid)

    new_envs = sorted(set(new_gid) - set(old_gid))
    missing_envs = sorted(set(old_gid) - set(new_gid))

    title_regressions: list[dict[str, Any]] = []
    for title, old_best in old_title.items():
        new_best = new_title.get(title)
        if new_best is None:
            continue  # API removed the title entirely; handled via missing_envs
        if new_best < old_best:
            title_regressions.append(
                {
                    "title": title,
                    "baseline_best": int(old_best),
                    "new_best": int(new_best),
                    "delta": int(new_best) - int(old_best),
                }
            )

    total_levels_new = sum(int(r["levels"] or 0) for r in new_gid.values())
    total_levels_old = sum(int(r["levels"] or 0) for r in old_gid.values())
    cleared_new = sum(1 for r in new_gid.values() if (r["levels"] or 0) > 0)
    cleared_old = sum(1 for r in old_gid.values() if (r["levels"] or 0) > 0)

    return {
        "verdict": "FAIL" if regressions else "PASS",
        "regressions": regressions,
        "improvements": improvements,
        "held_stable": len(held),
        "new_envs": new_envs,
        "missing_envs": missing_envs,
        "title_regressions": title_regressions,
        "headline": {
            "baseline_envs_cleared": cleared_old,
            "new_envs_cleared": cleared_new,
            "baseline_total_levels": total_levels_old,
            "new_total_levels": total_levels_new,
            "level_delta": total_levels_new - total_levels_old,
        },
    }


def _print_verdict(diff: dict[str, Any]) -> None:
    print(f"\n=== Regression gate: {diff['verdict']} ===")
    h = diff["headline"]
    print(
        f"  cleared:  {h['baseline_envs_cleared']} -> {h['new_envs_cleared']}   "
        f"total_levels:  {h['baseline_total_levels']} -> {h['new_total_levels']}   "
        f"delta={h['level_delta']:+d}"
    )
    print(
        f"  held={diff['held_stable']}  improved={len(diff['improvements'])}  "
        f"regressed={len(diff['regressions'])}  new_envs={len(diff['new_envs'])}  "
        f"missing_envs={len(diff['missing_envs'])}"
    )
    if diff["regressions"]:
        print("  REGRESSIONS (strict by_game_id):")
        for r in diff["regressions"]:
            print(
                f"    - {r['game_id']:<22} ({r['title']}) "
                f"{r['baseline_levels']} -> {r['new_levels']} ({r['delta']:+d})"
            )
    if diff["title_regressions"]:
        print("  TITLE-LEVEL BEST DROPPED (informational):")
        for r in diff["title_regressions"]:
            print(f"    - {r['title']:<8} best {r['baseline_best']} -> {r['new_best']} ({r['delta']:+d})")
    if diff["improvements"]:
        print("  improvements:")
        for r in diff["improvements"][:10]:
            print(
                f"    + {r['game_id']:<22} ({r['title']}) "
                f"{r['baseline_levels']} -> {r['new_levels']} ({r['delta']:+d})"
            )


def main() -> int:
    ap = argparse.ArgumentParser(description="R5 regression gate")
    ap.add_argument("--trace", type=Path, default=DEFAULT_TRACE)
    ap.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    ap.add_argument(
        "--seed",
        action="store_true",
        help="First-run mode: write the current trace as the baseline and exit PASS",
    )
    ap.add_argument(
        "--promote",
        action="store_true",
        help="After a PASS verdict, overwrite the baseline with the new trace",
    )
    ap.add_argument("--dry-run", action="store_true", help="Do not write the baseline even if promoted")
    args = ap.parse_args()

    if not args.trace.exists():
        print(f"trace not found: {args.trace}", file=sys.stderr)
        return EXIT_INPUT_ERROR

    new_trace = json.loads(args.trace.read_text())
    new_summary = summarize(new_trace)

    if args.seed:
        if args.dry_run:
            print("--seed + --dry-run: would seed but not writing", flush=True)
            return EXIT_PASS
        payload = {
            "seeded_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "seeded_from": str(args.trace),
            **new_summary,
        }
        args.baseline.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
        cleared = sum(1 for r in new_summary["by_game_id"].values() if r["levels"] > 0)
        total_lvl = sum(int(r["levels"] or 0) for r in new_summary["by_game_id"].values())
        print(
            f"Seeded baseline at {args.baseline} from {args.trace}: "
            f"{cleared} envs cleared, {total_lvl} levels"
        )
        return EXIT_PASS

    if not args.baseline.exists():
        print(
            f"baseline not found: {args.baseline}\n"
            f"  run with --seed to create it from the current trace.",
            file=sys.stderr,
        )
        return EXIT_INPUT_ERROR

    baseline = json.loads(args.baseline.read_text())
    diff = compare(new_summary, baseline)
    diff_out = args.baseline.with_name("regression_diff.json")
    diff_out.write_text(json.dumps(diff, indent=2, ensure_ascii=False))
    _print_verdict(diff)

    if diff["verdict"] == "PASS" and args.promote:
        if args.dry_run:
            print("\n--promote + --dry-run: would update baseline but not writing", flush=True)
        else:
            payload = {
                "promoted_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "promoted_from": str(args.trace),
                **new_summary,
            }
            args.baseline.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
            print(f"\nPromoted {args.trace} as new baseline at {args.baseline}")

    return EXIT_PASS if diff["verdict"] == "PASS" else EXIT_REGRESSIONS


if __name__ == "__main__":
    sys.exit(main())
