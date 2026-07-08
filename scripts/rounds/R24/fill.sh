#!/bin/zsh
cd /Users/nhn/Workspace/Admorphiq
GAMESCSV="ft09,m0r0,bp35,cd82,cn04,ls20,r11l,s5i5,sp80"
MISSING=("ft09 3" "m0r0 3" "bp35 3" "cd82 3" "cn04 3" "ls20 3" "r11l 3" "s5i5 2" "s5i5 3" "sp80 2" "sp80 3")
PAR=3
echo "[R24-fill] START $(date '+%Y-%m-%d %H:%M:%S %Z') — ${#MISSING[@]} missing, RL_CNN_WIDTH=1.5" >> scripts/rounds/R24/run.log
run_one() {
  g=$1; s=$2; t0=$(date +%s)
  RL_SEED=$s BC_TTT=0 RL_CNN_WIDTH=1.5 RL_PROGRESS_LOG="scripts/rounds/R24/progress/${g}_s${s}.log" RL_PROGRESS_EVERY=200 \
    uv run python scripts/score_efficiency.py --agent online_rl \
    --titles "$g" --max-actions 3000 --out "scripts/rounds/R24/games/${g}_s${s}.json" >/dev/null 2>&1
  echo "[R24] ${g} seed${s} done in $(($(date +%s)-t0))s $(date '+%H:%M:%S')" >> scripts/rounds/R24/run.log
  uv run python scripts/rounds/aggregate.py scripts/rounds/R24 "$GAMESCSV" 3 2>/dev/null
}
pids=()
for pair in $MISSING; do
  run_one ${=pair} &
  pids+=($!)
  while (( ${#pids[@]} >= PAR )); do wait ${pids[1]} 2>/dev/null; pids=(${pids[2,-1]}); done
done
wait
uv run python scripts/rounds/aggregate.py scripts/rounds/R24 "$GAMESCSV" 3
echo "[R24] DONE $(date '+%Y-%m-%d %H:%M:%S %Z') — answer in scripts/rounds/R24/SUMMARY.txt" >> scripts/rounds/R24/run.log
