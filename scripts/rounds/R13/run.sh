#!/bin/zsh
# R13 — depth push on the 9 L1-STUCK stable games (from R12 analysis), applying
# R8's proven-safe lever: MORE per-game budget (6000 vs 3000). Question: does
# budget alone break L1->L2? 3 seeds, PARALLEL(PAR=3). SUMMARY.txt regenerated
# LIVE per run (scripts/rounds/aggregate.py) so it is always readable mid-run
# and a valid partial on crash — the single answer for the round.
cd /Users/nhn/Workspace/Admorphiq
D=scripts/rounds/R13
log=$D/run.log; sum=$D/SUMMARY.txt
mkdir -p $D/games
: > $log; : > $sum
GAMES=(ft09 m0r0 bp35 cd82 cn04 ls20 r11l s5i5 sp80)
GAMESCSV="ft09,m0r0,bp35,cd82,cn04,ls20,r11l,s5i5,sp80"
SEEDS=(1 2 3)
PAR=3
echo "[R13] START $(date) — parallel(${PAR}) 9 L1-stuck games x3 seeds online_rl @6000 (budget depth test)" | tee -a $log

run_one() {
  g=$1; s=$2; t0=$(date +%s)
  RL_SEED=$s BC_TTT=0 uv run python scripts/score_efficiency.py --agent online_rl \
    --titles "$g" --max-actions 6000 --out "scripts/rounds/R13/games/${g}_s${s}.json" >/dev/null 2>&1
  echo "[R13] ${g} seed${s} done in $(($(date +%s)-t0))s $(date)" >> scripts/rounds/R13/run.log
  uv run python scripts/rounds/aggregate.py scripts/rounds/R13 "$GAMESCSV" 3 2>/dev/null
}

pids=()
for s in $SEEDS; do
  for g in $GAMES; do
    run_one "$g" "$s" &
    pids+=($!)
    while (( ${#pids[@]} >= PAR )); do wait ${pids[1]} 2>/dev/null; pids=(${pids[2,-1]}); done
  done
done
wait
uv run python scripts/rounds/aggregate.py scripts/rounds/R13 "$GAMESCSV" 3
echo "[R13] DONE $(date) — answer in $sum (baseline: all 9 were mean=1.0 @3000; did any reach L2?)" | tee -a $log
