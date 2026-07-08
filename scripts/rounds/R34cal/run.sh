#!/bin/zsh
cd /Users/nhn/Workspace/Admorphiq
D=scripts/rounds/R34cal; log=$D/run.log; sum=$D/SUMMARY.txt
mkdir -p $D/games; : > $log; : > $sum
GAMES=(ft09 m0r0 bp35 cd82 cn04 ls20 r11l s5i5 sp80)
PAR=2
echo "[R34cal] START $(date '+%Y-%m-%d %H:%M:%S %Z') — random+stochastic baselines on OUR 9-game harness @3000, 3 seeds" | tee -a $log
run_one() {
  ag=$1; g=$2; s=$3; t0=$(date +%s)
  RL_SEED=$s BC_TTT=0 uv run python scripts/score_efficiency.py --agent $ag \
    --titles "$g" --max-actions 3000 --out "$D/games/${ag}_${g}_s${s}.json" >/dev/null 2>&1
  echo "[R34cal] ${ag} ${g} s${s} $(($(date +%s)-t0))s $(date '+%H:%M:%S')" >> $D/run.log
}
pids=()
for ag in random stochastic; do for g in $GAMES; do for s in 1 2 3; do
  run_one $ag "$g" $s &
  pids+=($!)
  while (( ${#pids[@]} >= PAR )); do wait ${pids[1]} 2>/dev/null; pids=(${pids[2,-1]}); done
done; done; done
wait
uv run python - > $sum 2>>$log <<'PY'
import json,glob,re
from collections import defaultdict
agg=defaultdict(list)
for f in sorted(glob.glob('scripts/rounds/R34cal/games/*.json')):
    ag=re.match(r'(random|stochastic)_', __import__('os').path.basename(f)).group(1)
    try: d=json.load(open(f))
    except: continue
    for g in d.get('games',[]): agg[ag].append(g.get('game_score',0))
print("R34 CALIBRATION — baselines on OUR 9-game subset @3000 (3 seeds)")
for ag in ('random','stochastic'):
    v=agg[ag]
    if v: print(f"  {ag}: mean game_score = {sum(v)/len(v):.4f}  (n={len(v)})")
print("COMPARE: our online-RL from-scratch (warm-start OFF) = 0.0014; leaderboard random≈0.18")
print("If random here ~0.001 => our 9-game subset is far harder than the public-LB average (scale differs).")
print("If random here ~0.18 => our agent is genuinely near/below random.")
PY
echo "[R34cal] DONE $(date '+%Y-%m-%d %H:%M:%S %Z')" | tee -a $log
