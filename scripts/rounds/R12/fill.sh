#!/bin/zsh
cd /Users/nhn/Workspace/Admorphiq
GAMESCSV="ar25,ft09,lp85,m0r0,bp35,cd82,cn04,lf52,ls20,r11l,s5i5,sc25,sp80,vc33"
MISSING=("ar25 3" "ft09 3" "lp85 3" "m0r0 3" "bp35 3" "cd82 3" "cn04 3" "lf52 3" "ls20 3" "r11l 3" "s5i5 3" "sc25 3" "sp80 3" "vc33 2" "vc33 3")
PAR=3
echo "[R12-fill] START $(date) — ${#MISSING[@]} missing runs" >> scripts/rounds/R12/run.log
run_one() {
  g=$1; s=$2; t0=$(date +%s)
  RL_SEED=$s BC_TTT=0 uv run python scripts/score_efficiency.py --agent online_rl \
    --titles "$g" --max-actions 3000 --out "scripts/rounds/R12/games/${g}_s${s}.json" >/dev/null 2>&1
  echo "[R12] ${g} seed${s} done in $(($(date +%s)-t0))s $(date)" >> scripts/rounds/R12/run.log
  uv run python scripts/rounds/aggregate.py scripts/rounds/R12 "$GAMESCSV" 3 2>/dev/null
}
pids=()
for pair in $MISSING; do
  run_one ${=pair} &
  pids+=($!)
  while (( ${#pids[@]} >= PAR )); do wait ${pids[1]} 2>/dev/null; pids=(${pids[2,-1]}); done
done
wait
uv run python scripts/rounds/aggregate.py scripts/rounds/R12 "$GAMESCSV" 3
echo "[R12] DONE $(date) — answer in scripts/rounds/R12/SUMMARY.txt" >> scripts/rounds/R12/run.log
