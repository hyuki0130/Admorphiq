#!/bin/bash
# R93 Step-1b: budget-confound check — same pairs @2000 actions.
cd ~/admorphiq
OUT=scripts/rounds/R93/step1
echo "[$(date "+%F %T")] step1b @2000 start" >> "$OUT/SUMMARY.txt"
run_one() {
  tool=$1; game=$2
  log="$OUT/${tool}_${game}_2000.log"
  timeout 1800 ~/admorphiq/.venv/bin/python scripts/probe_tool_direct.py --tool "$tool" --game "$game" --budget 2000 > "$log" 2>&1
  echo "[$(date "+%F %T")] @2000 $tool x $game rc=$?" >> "$OUT/SUMMARY.txt"
  grep "TOOL=" "$log" | tail -1 | sed "s/^/    /" >> "$OUT/SUMMARY.txt"
}
export -f run_one; export OUT
printf "%s\n" "graph m0r0" "graph vc33" "toggle vc33" "paint cd82" "world_model ls20" "graph ls20" | xargs -P 3 -n 2 bash -c "run_one \$0 \$1"
echo "[$(date "+%F %T")] step1b COMPLETE" >> "$OUT/SUMMARY.txt"
