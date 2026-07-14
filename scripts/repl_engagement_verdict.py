"""Evaluate the engagement-flag ablation (R55 REPL_EXPERIMENT=engagement).

Reads a run package of ``{game}_{cell}_r{rep}`` diagnostics (cells: base, afirst,
rfb, both) and reports, per game, each treatment cell's delta vs base on the
mechanism metric it targets, plus clears — so the reader can judge whether each
engagement flag fixed its wall without regressing the guards:

- sb26 (truncation wall) → REPL_ACTION_FIRST should cut parse_failures/truncations.
- ft09 (repeat-rejection wall) → REPL_REPEAT_FEEDBACK should cut governor_rejections.
- su15, r11l (guards) → every cell must preserve the clear (no level regression).

Promotion (analogous to the Codex gates): a flag is promotable if it produces a
new clear on its target wall reproduced in >= ceil(reps/2) reps, OR materially
improves the target mechanism metric, AND no guard loses a clear it had at base.

Usage:
    uv run python scripts/repl_engagement_verdict.py --dir <engagement_run_dir>
"""

from __future__ import annotations

import argparse
import json
import math
import os
from glob import glob

TARGETS = {"sb26": "parse_failures", "ft09": "governor_rejections"}
GUARDS = ("su15", "r11l")
CELLS = ("base", "afirst", "rfb", "both")


def _split_tag(tag: str) -> tuple[str, str, int] | None:
    """``sb26_afirst_r2`` -> (``sb26``, ``afirst``, 2)."""
    parts = tag.rsplit("_", 2)
    if len(parts) != 3 or not parts[2].startswith("r"):
        return None
    game, cell, rep = parts
    try:
        return game, cell, int(rep[1:])
    except ValueError:
        return None


def load_runs(run_dir: str) -> list[dict]:
    runs: list[dict] = []
    for dp in sorted(glob(os.path.join(run_dir, "diagnostics", "*.json"))):
        tag = os.path.basename(dp)[:-5]
        parsed = _split_tag(tag)
        if parsed is None:
            continue
        game, cell, rep = parsed
        with open(dp) as fh:
            d = json.load(fh)
        runs.append({"game": game, "cell": cell, "rep": rep, "d": d})
    return runs


def _agg(runs: list[dict], game: str, cell: str) -> dict:
    rs = [r["d"] for r in runs if r["game"] == game and r["cell"] == cell]
    if not rs:
        return {}
    n = len(rs)
    keys = ("levels", "actions", "parse_failures", "truncations",
            "governor_rejections", "inspections")
    out = {k: sum(int(r.get(k, 0)) for r in rs) / n for k in keys}
    out["clears"] = sum(1 for r in rs if int(r.get("levels", 0)) >= 1)
    out["reps"] = n
    return out


def evaluate(run_dir: str) -> dict:
    runs = load_runs(run_dir)
    if not runs:
        return {"error": f"no diagnostics under {run_dir}"}
    games = sorted({r["game"] for r in runs})
    per_game: dict[str, dict] = {}
    for g in games:
        base = _agg(runs, g, "base")
        per_game[g] = {"base": base,
                       **{c: _agg(runs, g, c) for c in CELLS if c != "base"}}

    # promotion per flag: which cell(s) carry the flag, on its target wall.
    verdict = {}
    for wall, metric in TARGETS.items():
        if wall not in per_game:
            continue
        base = per_game[wall].get("base", {})
        rows = {}
        for cell in ("afirst", "rfb", "both"):
            c = per_game[wall].get(cell, {})
            if not c:
                continue
            need = math.ceil(c.get("reps", 1) / 2)
            new_clear = c["clears"] >= need and c["clears"] > base.get("clears", 0)
            metric_delta = c.get(metric, 0) - base.get(metric, 0)  # want negative
            rows[cell] = {"clears": c["clears"], "base_clears": base.get("clears", 0),
                          f"{metric}_base": round(base.get(metric, 0), 1),
                          f"{metric}_cell": round(c.get(metric, 0), 1),
                          "metric_delta": round(metric_delta, 1),
                          "new_clear": new_clear}
        verdict[wall] = {"target_metric": metric, "cells": rows}

    guard_ok = {}
    for g in GUARDS:
        if g not in per_game:
            continue
        base_clears = per_game[g].get("base", {}).get("clears", 0)
        regress = {c: per_game[g][c]["clears"] for c in ("afirst", "rfb", "both")
                   if per_game[g].get(c) and per_game[g][c]["clears"] < base_clears}
        guard_ok[g] = {"base_clears": base_clears, "regressions": regress,
                       "ok": not regress}

    return {"run_dir": run_dir, "n_runs": len(runs), "per_game": per_game,
            "target_verdict": verdict, "guard_preservation": guard_ok}


def _fmt_game(g: str, cells: dict) -> str:
    base = cells.get("base", {})
    out = [f"  {g}: base clears={base.get('clears','?')}/{base.get('reps','?')} "
           f"lvl={base.get('levels',0):.1f} pf={base.get('parse_failures',0):.1f} "
           f"trunc={base.get('truncations',0):.1f} rej={base.get('governor_rejections',0):.1f}"]
    for c in ("afirst", "rfb", "both"):
        cc = cells.get(c)
        if not cc:
            continue
        out.append(f"    +{c}: clears={cc['clears']}/{cc['reps']} lvl={cc['levels']:.1f} "
                   f"pf={cc['parse_failures']:.1f} trunc={cc['truncations']:.1f} "
                   f"rej={cc['governor_rejections']:.1f}")
    return "\n".join(out)


def main() -> None:
    p = argparse.ArgumentParser(description="Engagement-flag ablation verdict.")
    p.add_argument("--dir", required=True)
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    res = evaluate(args.dir)
    if args.json or "error" in res:
        print(json.dumps(res, indent=2))
        return
    print(f"engagement verdict  dir={res['run_dir']}  runs={res['n_runs']}")
    for g, cells in res["per_game"].items():
        print(_fmt_game(g, cells))
    print("--- target walls ---")
    for wall, v in res["target_verdict"].items():
        print(f"  {wall} (target {v['target_metric']}):")
        for cell, row in v["cells"].items():
            tag = "NEW-CLEAR" if row["new_clear"] else "no-clear"
            print(f"    +{cell}: {tag}  Δ{v['target_metric']}={row['metric_delta']:+.1f} "
                  f"(base {row[v['target_metric']+'_base']} -> {row[v['target_metric']+'_cell']})")
    print("--- guards (must preserve clears) ---")
    for g, gk in res["guard_preservation"].items():
        print(f"  {g}: {'OK' if gk['ok'] else 'REGRESSION ' + str(gk['regressions'])}")


if __name__ == "__main__":
    main()
