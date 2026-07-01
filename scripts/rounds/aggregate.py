"""Reusable round aggregator — regenerate SUMMARY.txt from whatever per-game
jsons exist SO FAR. Called after every run completes so SUMMARY.txt is always
live (readable mid-run, and a valid partial on crash). Convention: one file,
scripts/rounds/<RN>/SUMMARY.txt, is the single answer for the round.

Usage: python scripts/rounds/aggregate.py <round_dir> <game1,game2,...> <seeds>
  round_dir  e.g. scripts/rounds/R12
  games      ordered comma list of expected titles (upper/lowercase ok)
  seeds      number of seeds expected per game (for the X/N denominator)
"""

from __future__ import annotations

import glob
import json
import os
import sys
from collections import defaultdict


def main() -> None:
    round_dir, games_csv, seeds_s = sys.argv[1], sys.argv[2], sys.argv[3]
    order = [g.strip().upper() for g in games_csv.split(",") if g.strip()]
    n_seeds = int(seeds_s)
    games_dir = os.path.join(round_dir, "games")
    log_path = os.path.join(round_dir, "run.log")

    cr: dict[str, int] = defaultdict(int)
    ml: dict[str, list[int]] = defaultdict(list)
    for f in sorted(glob.glob(os.path.join(games_dir, "*.json"))):
        try:
            d = json.load(open(f))
        except (json.JSONDecodeError, OSError):
            continue  # a file mid-write; the next aggregate call picks it up
        for g in d.get("games", []):
            t = (g.get("title") or "?").upper()
            lc = g.get("levels_completed", 0)
            if lc > 0:
                cr[t] += 1
            ml[t].append(lc)

    done = sum(len(ml[t]) for t in order)
    total = len(order) * n_seeds
    stable = [t for t in order if cr[t] >= 2]
    lines = [
        f"ROUND {os.path.basename(round_dir)} SUMMARY (LIVE — regenerated per run) "
        f"progress {done}/{total} runs",
        f"VERDICT DATA: STABLE (>=2/{n_seeds}) = {len(stable)}/{len(order)} : "
        f"{', '.join(stable) if stable else '(none yet)'}",
    ]
    for t in order:
        runs = ml[t]
        m = sum(runs) / len(runs) if runs else 0.0
        tag = (
            "STABLE"
            if cr[t] >= 2
            else "flaky"
            if cr[t] == 1
            else ("LOST" if runs else "pending")
        )
        lines.append(f"  {t}: {cr[t]}/{len(runs)}  mean={m:.2f}  {runs}  [{tag}]")

    # LIVE in-flight view: last TICK from each per-game progress log whose game
    # has NOT yet produced a result json (i.e. still running). Lets one glance at
    # SUMMARY show currently-running games' level/actions, not just completed ones.
    prog_dir = os.path.join(round_dir, "progress")
    done_stems = {
        os.path.basename(f)[:-5] for f in glob.glob(os.path.join(games_dir, "*.json"))
    }
    inflight = []
    for pf in sorted(glob.glob(os.path.join(prog_dir, "*.log"))):
        stem = os.path.basename(pf)[:-4]
        if stem in done_stems:
            continue
        last = None
        for ln in open(pf):
            if ln.startswith("TICK"):
                last = ln.rstrip()
        if last:
            inflight.append(f"  [running] {stem}: {last}")
    if inflight:
        lines.append("")
        lines.append("--- IN PROGRESS (live TICK from running games) ---")
        lines += inflight

    if os.path.exists(log_path):
        timings = [ln for ln in open(log_path) if "done in" in ln]
        if timings:
            lines.append("")
            lines.append(f"--- last timings ({len(timings)} runs done) ---")
            lines += [t.rstrip() for t in timings[-4:]]

    import datetime as _dt

    stamp = _dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    header = f"[generated {stamp}] " + lines[0]
    lines[0] = header
    with open(os.path.join(round_dir, "SUMMARY.txt"), "w") as fh:
        fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
