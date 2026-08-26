#!/usr/bin/env bash
# Full-25 measurement of the GENERIC TOOLS ALONE (--agent unified), one game per process.
#
# This is stage one's own scoreboard and it did not exist. The card number is the tools PLUS
# thirteen hand-written per-game adapters, so it cannot say how far the generic path has come —
# and stage one is defined as "the tools clear all 25 sample games". This measures the tools.
#
# Purpose: the card's number is a MEAN over 25 games, so a port's effect on it can only be
# read from a full run. Arithmetic on the previous mean predicts it; this measures it.
#
# ⛔ Throttling uses `xargs -P`, not a `wait -n` loop. macOS ships bash 3.2, where `wait -n`
# is an INVALID OPTION — the guard fails open, the loop never blocks, and every game launches
# at once. Measured: the first two runs of this file did exactly that. Scores are per-process
# and deterministic so neither run's numbers were affected, but the machine was, and the
# second run was killed under the load.
#
# Games already having a result are SKIPPED, so a killed run resumes instead of restarting.
# The task tools notified this file's own kill at 17 of 25; re-running the 17 would have cost
# more than the 8 that were left.
#
# The agent must be the deployed one. `--agent kaggle_detect` refuses to run when
# GF_GIVEUP / HARNESS_STALL / HARNESS_CTX are set, because a runner exporting those
# silently measures a different configuration than the one that ships — that defect
# produced a "shipped" measurement at budget 100,000 once already.
set -u
cd "$(dirname "$0")/../../.."
unset GF_GIVEUP HARNESS_STALL HARNESS_CTX
OUT=scripts/rounds/R101FAN2
GAMES="ar25 bp35 cd82 cn04 dc22 ft09 g50t ka59 lf52 lp85 ls20 m0r0 r11l re86 s5i5 sb26 sc25 sk48 sp80 su15 tn36 tr87 tu93 vc33 wa30"
# ⛔ HARD CAP 60 (user directive, 2026-08-26, restated after being forgotten twice).
# ceph-build has 64 cores and saturating them locks out SSH — the box becomes unreachable
# mid-round and a running measurement cannot even be checked on. Leave 4 cores for the
# shell. This is CLAMPED here rather than trusted to whoever sets PAR, because the rule
# has already been forgotten once with the runner in hand.
PAR="${PAR:-6}"
if [ "$PAR" -gt 60 ]; then
  echo "[runner] PAR=$PAR exceeds the 60-core cap; clamping to 60 so SSH stays reachable"
  PAR=60
fi
BUDGET="${BUDGET:-4000}"
# AGENT exists so the BENCHED configuration (--agent detect) can be measured with the
# same runner as the SHIPPED one (--agent kaggle_detect). They are different
# configurations, and comparing them is what caught a "shipped" measurement that had
# silently run at budget 100,000.
AGENT="${AGENT:-unified}"

export OUT BUDGET GAMES AGENT
run_one() {
  [ -s "$OUT/games/$1.json" ] && { echo "$1 already measured — skipped"; return; }
  uv run python scripts/score_efficiency.py --agent "$AGENT" --titles "$1" \
    --max-actions "$BUDGET" --out "$OUT/games/$1.json" >"$OUT/games/$1.log" 2>&1
  uv run python scripts/rounds/aggregate.py "$OUT" "$(echo $GAMES | tr ' ' ',')" 1 >/dev/null 2>&1
  echo "$(date '+%Y-%m-%d %H:%M:%S %Z')  $1 done"
}
export -f run_one
echo "$GAMES" | tr ' ' '\n' | xargs -P "$PAR" -I{} bash -c 'run_one {}'
uv run python scripts/rounds/aggregate.py "$OUT" "$(echo $GAMES | tr ' ' ',')" 1
echo "[R101FAN2] $(date '+%Y-%m-%d %H:%M:%S %Z') full 25 complete"
