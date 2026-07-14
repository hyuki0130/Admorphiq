"""Compare two repl-bench run packages (R55) — e.g. v6 vs v5.

Computes the per-game deltas that decide "what did the working sandbox buy":
inspection success rate (v5's P0 bug made this ~0%), the action-source split
(model-chosen vs fallback), per-decision information usage (inspection rounds
that returned real data AND led to an action), plus levels / PREDICT accuracy /
parse-fail / throughput.

A run package is a dir with ``transcripts/{game}.jsonl`` (+ optional
``diagnostics/{game}.json``, ``events/{game}.events.jsonl``).

Usage:
    uv run python scripts/repl_bench_compare.py --a <v6_dir> --b <v5_dir>
    uv run python scripts/repl_bench_compare.py --a <dir>            # single summary
"""

from __future__ import annotations

import argparse
import json
import os
import re
from glob import glob

_SRC_RE = re.compile(r"source:\s*(\w+)")


def _load_jsonl(path: str) -> list[dict]:
    with open(path) as fh:
        return [json.loads(line) for line in fh if line.strip()]


def summarize_game(recs: list[dict], events: list[dict] | None,
                   diag: dict | None) -> dict:
    """Per-game metrics from a transcript (+ optional events/diagnostics)."""
    turns = len(recs)
    code = [r for r in recs if "```" in (r.get("raw_output") or "")]
    inspect_only = [r for r in code if "action(" not in (r.get("raw_output") or "")]
    sbx_err = [r for r in code if (r.get("sandbox_error") or "")]
    # inspection success = code turns whose sandbox did NOT error.
    insp_success = (len(code) - len(sbx_err)) / len(code) if code else 0.0
    # per-decision info usage: an inspection round that returned real stdout
    # (no error, non-empty) — the tool loop actually informed the model.
    informed = sum(1 for r in inspect_only
                   if (r.get("sandbox_stdout") or "") and not (r.get("sandbox_error") or ""))
    src: dict[str, int] = {}
    for r in recs:
        m = _SRC_RE.search(r.get("prompt_text") or "")
        if m:
            src[m.group(1)] = src.get(m.group(1), 0) + 1
    src_total = sum(src.values()) or 1
    env_actions = (
        sum(1 for e in (events or []) if e.get("type") == "action_executed")
        or (diag or {}).get("actions", 0))
    parse_fail = sum(1 for r in recs if not r.get("parsed_tool_calls"))
    return {
        "turns": turns,
        "env_actions": env_actions,
        "levels": (diag or {}).get("levels", 0),
        "code_turns": len(code),
        "inspect_only": len(inspect_only),
        "sandbox_error_turns": len(sbx_err),
        "inspection_success_rate": round(insp_success, 3),
        "informed_inspections": informed,
        "src_llm_pct": round(100 * src.get("llm", 0) / src_total, 1),
        "src_fallback_pct": round(100 * src.get("fallback", 0) / src_total, 1),
        "parse_fail_pct": round(100 * parse_fail / turns, 1) if turns else 0.0,
        "predict_made": (diag or {}).get("predictions_made", 0),
        "predict_correct": (diag or {}).get("predictions_correct", 0),
    }


def summarize_run(run_dir: str) -> dict[str, dict]:
    """Summarize every game in a run package, keyed by game id."""
    out: dict[str, dict] = {}
    for tp in sorted(glob(os.path.join(run_dir, "transcripts", "*.jsonl"))):
        game = os.path.basename(tp)[:-6]
        recs = _load_jsonl(tp)
        ep = os.path.join(run_dir, "events", f"{game}.events.jsonl")
        events = _load_jsonl(ep) if os.path.exists(ep) else None
        dp = os.path.join(run_dir, "diagnostics", f"{game}.json")
        diag = json.load(open(dp)) if os.path.exists(dp) else None
        out[game] = summarize_game(recs, events, diag)
    return out


def action_phases(run_dir: str, game: str) -> dict:
    """Break the FIRST level-up into action phases from the event stream + the
    transcript's audit records (Codex v7: total actions != actions-to-L1 because
    the bench continues after L1). Reports actions-to-first-level-up, before-first
    -audit, between-audits, revision(last audit before clear)-to-level-up, and
    after-level-up.
    """
    tp = os.path.join(run_dir, "transcripts", f"{game}.jsonl")
    ep = os.path.join(run_dir, "events", f"{game}.events.jsonl")
    if not (os.path.exists(tp) and os.path.exists(ep)):
        return {}
    events = _load_jsonl(ep)
    recs = _load_jsonl(tp)
    action_ev = [e for e in events if e.get("type") == "action_executed"]
    total_actions = len(action_ev)
    lvl = next((e for e in events if e.get("type") == "level_up"), None)
    audits = sorted(r["audit"]["action_count"] for r in recs
                    if r.get("audit") and r["audit"].get("action_count") is not None)
    if lvl is None:
        return {"cleared": False, "total_actions": total_actions,
                "first_audit_at": audits[0] if audits else None,
                "between_audits": _diffs(audits)}
    to_lvl = sum(1 for e in action_ev if e["seq"] < lvl["seq"])
    pre = [a for a in audits if a <= to_lvl]
    return {
        "cleared": True,
        "actions_to_first_level_up": to_lvl,
        "actions_before_first_audit": pre[0] if pre else None,
        "between_audits": _diffs(audits),
        "revision_to_level_up": (to_lvl - pre[-1]) if pre else None,
        "actions_after_level_up": total_actions - to_lvl,
        "total_actions": total_actions,
    }


def _diffs(xs: list[int]) -> list[int]:
    return [b - a for a, b in zip(xs, xs[1:])]


_COLS = ["levels", "env_actions", "inspection_success_rate", "informed_inspections",
         "src_llm_pct", "src_fallback_pct", "sandbox_error_turns", "parse_fail_pct"]


def _print_single(a: dict[str, dict]) -> None:
    print(f"{'game':16s} " + " ".join(f"{c:>10s}" for c in _COLS))
    for g, m in a.items():
        print(f"{g:16s} " + " ".join(f"{str(m.get(c, '')):>10s}" for c in _COLS))


def _print_delta(a: dict[str, dict], b: dict[str, dict]) -> None:
    print("Δ = A - B (A=first --a, B=second --b)\n")
    print(f"{'game':16s} " + " ".join(f"{c:>16s}" for c in _COLS))
    for g in sorted(set(a) | set(b)):
        ma, mb = a.get(g, {}), b.get(g, {})
        cells = []
        for c in _COLS:
            va, vb = ma.get(c), mb.get(c)
            if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
                cells.append(f"{va}|{vb}|{round(va - vb, 3)}")
            else:
                cells.append(f"{va}|{vb}")
        print(f"{g:16s} " + " ".join(f"{s:>16s}" for s in cells))


def main() -> None:
    p = argparse.ArgumentParser(description="Compare two repl-bench run packages.")
    p.add_argument("--a", required=True, help="run dir A (e.g. v6)")
    p.add_argument("--b", default=None, help="run dir B to diff against (e.g. v5)")
    p.add_argument("--phases", action="store_true",
                   help="print the first-level-up action-phase breakdown for run A")
    args = p.parse_args()
    a = summarize_run(args.a)
    if args.phases:
        for game in a:
            print(f"{game:16s} {action_phases(args.a, game)}")
    elif args.b is None:
        _print_single(a)
    else:
        _print_delta(a, summarize_run(args.b))


if __name__ == "__main__":
    main()
