#!/usr/bin/env bash
# Full-25 measurement of the SHIPPED card (--agent kaggle_detect), one game per process.
#
# Purpose: the card's number is a MEAN over 25 games, so a port's effect on it can only be
# read from a full run. Arithmetic on the previous mean predicts it; this measures it.
#
# The agent must be the deployed one. `--agent kaggle_detect` refuses to run when
# GF_GIVEUP / HARNESS_STALL / HARNESS_CTX are set, because a runner exporting those
# silently measures a different configuration than the one that ships — that defect
# produced a "shipped" measurement at budget 100,000 once already.
set -u
cd "$(dirname "$0")/../../.."
unset GF_GIVEUP HARNESS_STALL HARNESS_CTX
OUT=scripts/rounds/R99CARD
GAMES="ar25 bp35 cd82 cn04 dc22 ft09 g50t ka59 lf52 lp85 ls20 m0r0 r11l re86 s5i5 sb26 sc25 sk48 sp80 su15 tn36 tr87 tu93 vc33 wa30"
PAR="${PAR:-6}"
BUDGET="${BUDGET:-4000}"

run_one() {
  uv run python scripts/score_efficiency.py --agent kaggle_detect --titles "$1" \
    --max-actions "$BUDGET" --out "$OUT/games/$1.json" >"$OUT/games/$1.log" 2>&1
  uv run python scripts/rounds/aggregate.py "$OUT" "$(echo $GAMES | tr ' ' ',')" 1 >/dev/null 2>&1
  echo "$(date '+%Y-%m-%d %H:%M:%S %Z')  $1 done"
}

for g in $GAMES; do
  while [ "$(jobs -rp | wc -l)" -ge "$PAR" ]; do wait -n; done
  run_one "$g" &
done
wait
uv run python scripts/rounds/aggregate.py "$OUT" "$(echo $GAMES | tr ' ' ',')" 1
echo "[R99CARD] $(date '+%Y-%m-%d %H:%M:%S %Z') full 25 complete"
