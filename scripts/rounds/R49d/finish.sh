#!/bin/zsh
# R49d finisher — remaining 14b games, one bench invocation per game so any
# external kill costs at most the in-flight game. Run via launchd (detached
# from the dev session's process tree; three harness background tasks were
# externally killed with no kernel/log trace on 2026-07-06/07).
cd /Users/nhn/Workspace/Admorphiq || exit 1
LOG=scripts/rounds/R49d/run.log
echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] finish.sh (launchd): remaining games start" >> "$LOG"
for g in tn36 tr87 tu93 vc33 wa30; do
  if [ -f "scripts/rounds/R49d/games/qwen3_14b__${g}.json" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] skip ${g} (already done)" >> "$LOG"
    continue
  fi
  /Users/nhn/.local/bin/uv run python scripts/llm_worldmodel_bench.py \
    --models qwen3:14b --games "$g" --rounds 3 \
    --num-ctx 24576 --max-tokens 8192 \
    --out scripts/rounds/R49d >> "$LOG" 2>&1
done
echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] finish.sh (launchd): DONE" >> "$LOG"
