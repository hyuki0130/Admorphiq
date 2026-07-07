#!/bin/zsh
# R49e — gpt-oss:20b local bench, full 18 games, one bench invocation per game
# (ratchet: an external kill costs at most the in-flight game). launchd-run:
# the durable pattern from R49d (three traceless harness-task kills).
# num_ctx 20480 (not 24576): 20b MXFP4 ~13GB sits between safe 14b(11GB) and
# the Q3-30b(16GB) that went kernel-critical at 24k on this 24GB machine.
cd /Users/nhn/Workspace/Admorphiq || exit 1
LOG=scripts/rounds/R49e/run.log
echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] R49e (launchd): gpt-oss:20b, 18 games, K=3, num_ctx=20480, max_tokens=8192" >> "$LOG"
for g in ar25 dc22 g50t ka59 lf52 lp85 re86 s5i5 sb26 sc25 sk48 sp80 su15 tn36 tr87 tu93 vc33 wa30; do
  if [ -f "scripts/rounds/R49e/games/gpt-oss_20b__${g}.json" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] skip ${g} (already done)" >> "$LOG"
    continue
  fi
  /Users/nhn/.local/bin/uv run python scripts/llm_worldmodel_bench.py \
    --models gpt-oss:20b --games "$g" --rounds 3 \
    --num-ctx 20480 --max-tokens 8192 \
    --out scripts/rounds/R49e >> "$LOG" 2>&1
done
echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] R49e (launchd): DONE" >> "$LOG"
