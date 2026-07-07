#!/bin/bash
# R51 — two isolated axes vs the R50b honest baseline (gemma4-31b-q8, K=8):
#   A: few-shot 15 -> 40   (data axis)          -> out_r51a
#   B: few 15 + mechanics prior (prior axis)    -> out_r51b
# Per-game ratchet; spot-preemption-safe; honest protocol throughout.
cd "$HOME/bench"
MODEL="gemma4:31b-it-q8_0"
GAMES="ar25 dc22 g50t ka59 lf52 lp85 re86 s5i5 sb26 sc25 sk48 sp80 su15 tn36 tr87 tu93 vc33 wa30"

run_pass() {
  local out="$1"; shift
  local extra=("$@")
  mkdir -p "$out/games"
  local log="$out/run.log"
  echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] R51 pass -> $out (${extra[*]})" >> "$log"
  local safe
  safe=$(echo "$MODEL" | tr ':/' '__')
  for g in $GAMES; do
    if [ -f "$out/games/${safe}__${g}.json" ]; then
      continue
    fi
    python3 llm_worldmodel_bench.py \
      --models "$MODEL" --games "$g" --rounds 8 \
      --num-ctx 65536 --max-tokens 8192 \
      --data-dir "$HOME/bench/data/transitions/train" \
      --out "$HOME/bench/$out" "${extra[@]}" >> "$log" 2>&1
  done
  echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] R51 pass DONE -> $out" >> "$log"
}

run_pass out_r51a --few 40
run_pass out_r51b --mechanics-prior
echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] R51 ALL DONE" >> out_r51a/run.log
