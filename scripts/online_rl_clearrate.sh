#!/bin/zsh
# K-seed CLEAR-RATE harness for the test-time online RL agent.
#
# WHY: the online RL agent is stochastic — a single run's clear/miss on a game is
# variance, not signal. To judge any future learner change we need a TRUSTWORTHY
# bar, so we run the SAME small game set over K seeds and report, per game, the
# CLEAR-RATE (how many of K seeds cleared >=1 level) and the mean levels cleared.
#
# Usage:
#   scripts/online_rl_clearrate.sh                       # defaults below
#   GAMES=ar25,m0r0 K=3 MAX_ACTIONS=1500 scripts/online_rl_clearrate.sh
#
# Bounded by design: small game set + low max-actions so the whole sweep stays
# in the tens-of-minutes range on a laptop. RL_SEED is varied per seed; the
# per-game progress log is written to scripts/online_rl_progress.log.
set -e
cd "$(dirname "$0")/.."   # repo root (works from a worktree too)

GAMES="${GAMES:-ar25,m0r0,tu93,dc22,ft09,lp85}"
K="${K:-3}"
MAX_ACTIONS="${MAX_ACTIONS:-1500}"
OUTDIR="${OUTDIR:-scripts/online_rl_clearrate}"
PROGRESS="${RL_PROGRESS_LOG:-scripts/online_rl_progress.log}"
mkdir -p "$OUTDIR"
: > "$PROGRESS"

log="$OUTDIR/run.log"; : > "$log"
echo "[clearrate] START $(date) games=$GAMES K=$K max_actions=$MAX_ACTIONS" >> "$log"

for seed in $(seq 1 "$K"); do
  echo "[clearrate] seed=$seed $(date)" >> "$log"
  RL_SEED="$seed" RL_PROGRESS_LOG="$PROGRESS" \
    uv run python scripts/score_efficiency.py --agent online_rl \
      --titles "$GAMES" --max-actions "$MAX_ACTIONS" \
      --out "$OUTDIR/seed_${seed}.json" >> "$log" 2>&1
  echo "[clearrate] seed=$seed done" >> "$log"
done

echo "[clearrate] AGGREGATE $(date)" >> "$log"
OUTDIR="$OUTDIR" K="$K" GAMES="$GAMES" uv run python - <<'PY' | tee -a "$log"
import glob, json, os
from collections import defaultdict

outdir = os.environ["OUTDIR"]
k = int(os.environ["K"])
files = sorted(glob.glob(os.path.join(outdir, "seed_*.json")))

# per title: list of (levels_completed, win_levels) across seeds
levels = defaultdict(list)
wins = {}
for f in files:
    d = json.load(open(f))
    for g in d["games"]:
        title = g.get("title", g["game_id"])
        lv = g.get("levels_completed", 0)
        levels[title].append(lv)
        wins[title] = g.get("win_levels", 0)

print(f"\n{'game':10}{'win':>5}{'clear_rate':>12}{'mean_lvls':>11}{'levels_by_seed':>20}")
for title in sorted(levels):
    lvs = levels[title]
    cleared = sum(1 for v in lvs if v >= 1)
    mean = sum(lvs) / len(lvs) if lvs else 0.0
    print(f"{title:10}{wins[title]:>5}{f'{cleared}/{len(lvs)}':>12}"
          f"{mean:>11.2f}{str(lvs):>20}")
PY
echo "[clearrate] DONE $(date)" >> "$log"
