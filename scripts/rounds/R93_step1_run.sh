#!/bin/bash
# R93 Step-1: direct tool×game stall matrix (no LLM). 4 tools x 4 games @300.
cd ~/admorphiq
OUT=scripts/rounds/R93/step1
mkdir -p "$OUT"
echo "[$(date "+%F %T")] R93 step1 start" > "$OUT/SUMMARY.txt"
run_one() {
  tool=$1; game=$2
  log="$OUT/${tool}_${game}.log"
  timeout 600 ~/admorphiq/.venv/bin/python scripts/probe_tool_direct.py --tool "$tool" --game "$game" --budget 300 > "$log" 2>&1
  echo "[$(date "+%F %T")] $tool x $game done rc=$?" >> "$OUT/SUMMARY.txt"
  tail -3 "$log" | sed "s/^/    /" >> "$OUT/SUMMARY.txt"
}
export -f run_one; export OUT
for t in graph world_model paint toggle; do
  for g in m0r0 vc33 cd82 ls20; do
    echo "$t $g"
  done
done | xargs -P 4 -n 2 bash -c "run_one \$0 \$1"
echo "[$(date "+%F %T")] R93 step1 COMPLETE" >> "$OUT/SUMMARY.txt"
