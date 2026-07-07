#!/bin/bash
# R50 — cloud bench runner (on-VM). Per-game ratchet, resumable after spot
# preemption: completed game JSONs are skipped by filename.
# Usage: bash vm_run.sh  (expects ~/bench/{llm_worldmodel_bench.py,data/...})
cd "$HOME/bench"
LOG=out/run.log
GAMES="ar25 dc22 g50t ka59 lf52 lp85 re86 s5i5 sb26 sc25 sk48 sp80 su15 tn36 tr87 tu93 vc33 wa30"
echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] R50 cloud bench start" >> "$LOG"
# Prefer the highest-precision pulled variant per family (q8 > qat > default).
QWEN=$(ollama list | awk '{print $1}' | grep '^qwen3-coder:30b' | sort -r | head -1)
GEMMA_BIG=$(ollama list | awk '{print $1}' | grep '^gemma4:31b' | sort -r | head -1)
for model in "gpt-oss:120b" ${QWEN:+"$QWEN"} "gemma4:26b-a4b-it-qat" ${GEMMA_BIG:+"$GEMMA_BIG"}; do
  safe=$(echo "$model" | tr ':/' '__')
  for g in $GAMES; do
    if [ -f "out/games/${safe}__${g}.json" ]; then
      continue
    fi
    python3 llm_worldmodel_bench.py \
      --models "$model" --games "$g" --rounds 3 \
      --num-ctx 65536 --max-tokens 8192 \
      --data-dir "$HOME/bench/data/transitions/train" \
      --out "$HOME/bench/out" >> "$LOG" 2>&1
  done
  echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] model done: $model" >> "$LOG"
done
echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] R50 cloud bench DONE" >> "$LOG"
