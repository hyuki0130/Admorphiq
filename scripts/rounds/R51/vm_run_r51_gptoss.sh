#!/bin/bash
# R51 chain — same two axes for gpt-oss:120b (user-directed: it's fast, keep
# the comparison running). Waits for the gemma runner to finish first: models
# can't share the 96GB GPU concurrently (33GB + 65GB + KV > 96GB).
cd "$HOME/bench"
while pgrep -f "vm_run_r51[.]sh" >/dev/null; do sleep 60; done

MODEL="gpt-oss:120b"
GAMES="ar25 dc22 g50t ka59 lf52 lp85 re86 s5i5 sb26 sc25 sk48 sp80 su15 tn36 tr87 tu93 vc33 wa30"

run_pass() {
  local out="$1"; shift
  local extra=("$@")
  mkdir -p "$out/games"
  local log="$out/run.log"
  echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] R51 gptoss pass -> $out (${extra[*]})" >> "$log"
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
  echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] R51 gptoss pass DONE -> $out" >> "$log"
}

run_pass out_r51a --few 40
run_pass out_r51b --mechanics-prior
echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] R51 GPTOSS ALL DONE" >> out_r51a/run.log
