#!/bin/zsh
# R49f — gemma4:26b-a4b-it-qat local bench, full 18 games, per-game ratchet,
# launchd-run (R49d durable pattern). num_ctx 16384 (16GB model on the 24GB
# Mac: the Q3-30b 16GB went kernel-critical at 24k ctx; 20b/14GB was clean at
# 20k. 16k + q8_0 KV keeps this at the safe edge; the memory watchdog guards).
cd /Users/nhn/Workspace/Admorphiq || exit 1
LOG=scripts/rounds/R49f/run.log
echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] R49f (launchd): gemma4:26b-a4b-it-qat, 18 games, K=3, num_ctx=16384, max_tokens=8192" >> "$LOG"
for g in ar25 dc22 g50t ka59 lf52 lp85 re86 s5i5 sb26 sc25 sk48 sp80 su15 tn36 tr87 tu93 vc33 wa30; do
  if [ -f "scripts/rounds/R49f/games/gemma4_26b-a4b-it-qat__${g}.json" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] skip ${g} (already done)" >> "$LOG"
    continue
  fi
  /Users/nhn/.local/bin/uv run python scripts/llm_worldmodel_bench.py \
    --models gemma4:26b-a4b-it-qat --games "$g" --rounds 3 \
    --num-ctx 16384 --max-tokens 8192 \
    --out scripts/rounds/R49f >> "$LOG" 2>&1
done
echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] R49f (launchd): DONE" >> "$LOG"
