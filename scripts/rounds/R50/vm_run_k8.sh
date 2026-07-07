#!/bin/bash
# R50b — K=8 refinement-depth run on the cloud VM (user-directed: K=3 is
# conservative vs the 9h Kaggle budget; cloud speed is ~45s/game at K=3).
# Top-2 models from the K=3 pass, all 18 games, train-fit selection harness.
cd "$HOME/bench"
LOG=out_k8/run.log
mkdir -p out_k8/games
GAMES="ar25 dc22 g50t ka59 lf52 lp85 re86 s5i5 sb26 sc25 sk48 sp80 su15 tn36 tr87 tu93 vc33 wa30"
echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] R50b K=8 start" >> "$LOG"
for model in "$@"; do
  safe=$(echo "$model" | tr ':/' '__')
  for g in $GAMES; do
    if [ -f "out_k8/games/${safe}__${g}.json" ]; then
      continue
    fi
    python3 llm_worldmodel_bench.py \
      --models "$model" --games "$g" --rounds 8 \
      --num-ctx 65536 --max-tokens 8192 \
      --data-dir "$HOME/bench/data/transitions/train" \
      --out "$HOME/bench/out_k8" >> "$LOG" 2>&1
  done
  echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] model done: $model" >> "$LOG"
done
echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] R50b K=8 DONE" >> "$LOG"
