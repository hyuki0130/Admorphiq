#!/bin/zsh
# R12 — 3-seed clear-rate on the 14 R11 winners, PARALLEL(PAR=3).
# Online RL is stochastic; R11 found 14/25 on a single seed. This re-runs the
# 14 winners across 3 seeds to separate STABLE general clears from single-seed
# luck. One process per (game,seed). SUMMARY.txt is regenerated LIVE after every
# run (via scripts/rounds/aggregate.py) so it is always readable mid-run and a
# valid partial on crash — the single answer for the round.
cd /Users/nhn/Workspace/Admorphiq
D=scripts/rounds/R12
log=$D/run.log; sum=$D/SUMMARY.txt
mkdir -p $D/games
: > $log; : > $sum
GAMES=(ar25 ft09 lp85 m0r0 bp35 cd82 cn04 lf52 ls20 r11l s5i5 sc25 sp80 vc33)
GAMESCSV="ar25,ft09,lp85,m0r0,bp35,cd82,cn04,lf52,ls20,r11l,s5i5,sc25,sp80,vc33"
SEEDS=(1 2 3)
PAR=3
echo "[R12] START $(date) — parallel(${PAR}) 14 winners x3 seeds online_rl @3000" | tee -a $log

run_one() {
  g=$1; s=$2
  t0=$(date +%s)
  RL_SEED=$s BC_TTT=0 uv run python scripts/score_efficiency.py --agent online_rl \
    --titles "$g" --max-actions 3000 --out "scripts/rounds/R12/games/${g}_s${s}.json" >/dev/null 2>&1
  t1=$(date +%s)
  echo "[R12] ${g} seed${s} done in $((t1-t0))s $(date)" >> scripts/rounds/R12/run.log
  # live re-aggregate so SUMMARY.txt always reflects current standing
  uv run python scripts/rounds/aggregate.py scripts/rounds/R12 "$GAMESCSV" 3 2>/dev/null
}

pids=()
for s in $SEEDS; do
  for g in $GAMES; do
    run_one "$g" "$s" &
    pids+=($!)
    while (( ${#pids[@]} >= PAR )); do
      wait ${pids[1]} 2>/dev/null
      pids=(${pids[2,-1]})
    done
  done
done
wait

uv run python scripts/rounds/aggregate.py scripts/rounds/R12 "$GAMESCSV" 3
echo "[R12] DONE $(date) — answer in $sum" | tee -a $log
