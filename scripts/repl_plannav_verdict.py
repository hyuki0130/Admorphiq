"""Evaluate the decoupled PLAN x NAV 2x2 (R55 REPL_EXPERIMENT=plannav).

Reads ``{game}_{cell}_r{rep}`` diagnostics (cells: base, nav, plan, combined over
ls20/g50t/tu93) and applies the Codex promotion gates
(`docs/r55_codex_matched12_review_20260714.md` + trigger re-ruling). A treatment
cell is promotable only if ALL hold:

1. It produces a new level/clear on a formerly-zero game, reproduced in
   >= ceil(reps/2) replicates.
2. Its median faithful-RHAE delta vs base is positive on >= 2 of the 3 games.
3. It beats base in >= 6/9 paired game-replicates (per game-rep RHAE).
4. Any action-throughput loss exceeds 20% only if compensated by a reproduced
   clear.
5. Among passing cells, choose lexicographically by clears, levels, aggregate
   RHAE, then simplicity (nav/plan over combined). Do not pick combined for a
   small noisy edge.

Faithful RHAE reuses repl_matched_verdict's baseline + per-level-action helpers.

Usage:
    uv run python scripts/repl_plannav_verdict.py --dir <plannav_run_dir>
"""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
from glob import glob

from repl_matched_verdict import faithful_rhae, load_baselines  # sibling

CELLS = ("base", "nav", "plan", "combined")
TREATMENTS = ("nav", "plan", "combined")
_SIMPLICITY = {"nav": 0, "plan": 1, "combined": 2}  # prefer simpler on ties


def _split_tag(tag: str) -> tuple[str, str, int] | None:
    parts = tag.rsplit("_", 2)
    if len(parts) != 3 or not parts[2].startswith("r"):
        return None
    game, cell, rep = parts
    if cell not in CELLS:
        return None
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
        runs.append({"tag": tag, "game": game, "cell": cell, "rep": rep, "d": d})
    return runs


def evaluate(run_dir: str) -> dict:
    runs = load_runs(run_dir)
    if not runs:
        return {"error": f"no diagnostics under {run_dir}"}
    baselines = load_baselines()
    games = sorted({r["game"] for r in runs})

    # rhae[game][cell] = list per rep; actions[game][cell] = list per rep.
    rhae: dict = {g: {c: [] for c in CELLS} for g in games}
    acts: dict = {g: {c: [] for c in CELLS} for g in games}
    levels: dict = {g: {c: [] for c in CELLS} for g in games}
    clears: dict = {g: {c: 0 for c in CELLS} for g in games}
    reps_seen: dict = {g: {c: 0 for c in CELLS} for g in games}
    for r in runs:
        g, c = r["game"], r["cell"]
        val = faithful_rhae(run_dir, r["tag"], g, baselines)
        rhae[g][c].append(val if val is not None else 0.0)
        acts[g][c].append(int(r["d"].get("actions", 0)))
        levels[g][c].append(int(r["d"].get("levels", 0)))
        reps_seen[g][c] += 1
        if int(r["d"].get("levels", 0)) >= 1:
            clears[g][c] += 1

    def _mean(xs):
        return sum(xs) / len(xs) if xs else 0.0

    verdict = {}
    for cell in TREATMENTS:
        # gate 1: new clear on a formerly-zero (base 0-clear) game, reproduced.
        new_clear_games = []
        for g in games:
            need = math.ceil(max(reps_seen[g][cell], 1) / 2)
            if clears[g]["base"] == 0 and clears[g][cell] >= need:
                new_clear_games.append(g)
        g1 = bool(new_clear_games)

        # gate 2: median RHAE delta positive on >= 2/3 games.
        pos_games = 0
        for g in games:
            dm = statistics.median(rhae[g][cell]) - statistics.median(rhae[g]["base"]) \
                if rhae[g][cell] and rhae[g]["base"] else 0.0
            if dm > 0:
                pos_games += 1
        g2 = pos_games >= max(1, math.ceil(2 / 3 * len(games)))

        # gate 3: beats base in >= 6/9 paired game-replicates.
        wins = tot = 0
        for g in games:
            n = min(len(rhae[g][cell]), len(rhae[g]["base"]))
            for i in range(n):
                tot += 1
                if rhae[g][cell][i] > rhae[g]["base"][i]:
                    wins += 1
        g3 = tot > 0 and wins / tot >= 6 / 9

        # gate 4: throughput loss >20% only if compensated by a reproduced clear.
        thr_bad = []
        for g in games:
            b, c = _mean(acts[g]["base"]), _mean(acts[g][cell])
            if b > 0 and (c - b) / b > 0.20 and g not in new_clear_games:
                thr_bad.append(g)
        g4 = not thr_bad

        agg_rhae = _mean([v for g in games for v in rhae[g][cell]])
        total_clears = sum(clears[g][cell] for g in games)
        total_levels = sum(_mean(levels[g][cell]) for g in games)
        verdict[cell] = {
            "gate1_new_clear": g1, "new_clear_games": new_clear_games,
            "gate2_median_rhae_pos": g2, "pos_games": pos_games,
            "gate3_beats_base": g3, "wins": wins, "paired": tot,
            "gate4_throughput_ok": g4, "throughput_regressions": thr_bad,
            "promotable": g1 and g2 and g3 and g4,
            "agg_rhae": round(agg_rhae, 4), "total_clears": total_clears,
            "total_levels": round(total_levels, 2),
        }

    # gate 5: lexicographic selection among promotable cells.
    winners = [c for c in TREATMENTS if verdict[c]["promotable"]]
    winner = None
    if winners:
        winner = sorted(winners, key=lambda c: (
            -verdict[c]["total_clears"], -verdict[c]["total_levels"],
            -verdict[c]["agg_rhae"], _SIMPLICITY[c]))[0]

    return {"run_dir": run_dir, "n_runs": len(runs), "games": games,
            "clears": clears, "cell_verdict": verdict, "winner": winner}


def main() -> None:
    p = argparse.ArgumentParser(description="Decoupled PLANxNAV 2x2 verdict.")
    p.add_argument("--dir", required=True)
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    res = evaluate(args.dir)
    if args.json or "error" in res:
        print(json.dumps(res, indent=2))
        return
    print(f"plannav verdict  dir={res['run_dir']}  runs={res['n_runs']}  games={res['games']}")
    for g in res["games"]:
        cl = res["clears"][g]
        print(f"  {g} clears: " + " ".join(f"{c}={cl[c]}" for c in CELLS))
    print("--- cells ---")
    for cell, v in res["cell_verdict"].items():
        flags = (f"g1={'Y' if v['gate1_new_clear'] else 'n'} "
                 f"g2={'Y' if v['gate2_median_rhae_pos'] else 'n'} "
                 f"g3={'Y' if v['gate3_beats_base'] else 'n'}({v['wins']}/{v['paired']}) "
                 f"g4={'Y' if v['gate4_throughput_ok'] else 'n'}")
        print(f"  {cell}: {'PROMOTABLE' if v['promotable'] else 'no'}  {flags}  "
              f"clears={v['total_clears']} RHAE={v['agg_rhae']} "
              f"new_clear_games={v['new_clear_games']}")
    print(f"  WINNER: {res['winner'] or 'none (no cell passes — use base coverage map)'}")


if __name__ == "__main__":
    main()
