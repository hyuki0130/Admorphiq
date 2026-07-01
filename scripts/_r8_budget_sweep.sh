#!/bin/zsh
cd /Users/nhn/Workspace/Admorphiq
log=scripts/r8_budget_sweep.log; : > $log
echo "[r8] START $(date) — does more per-game budget lift online_rl clear-rate?" >> $log
GAMES="ar25,ft09,lp85,m0r0,dc22,tu93"
for budget in 1500 3000 6000; do
  for seed in 1 2 3; do
    out="scripts/r8_sweep/b${budget}_s${seed}.json"
    mkdir -p scripts/r8_sweep
    echo "[r8] budget=$budget seed=$seed $(date)" >> $log
    RL_SEED=$seed BC_TTT=0 uv run python scripts/score_efficiency.py --agent online_rl \
      --titles "$GAMES" --max-actions $budget --out "$out" >> $log 2>&1
  done
done
echo "[r8] AGGREGATE $(date)" >> $log
uv run python - >> $log 2>&1 <<'PY'
import json,glob
from collections import defaultdict
for budget in [1500,3000,6000]:
    cr=defaultdict(int); ml=defaultdict(list); n=0
    for f in sorted(glob.glob(f'scripts/r8_sweep/b{budget}_s*.json')):
        n+=1; d=json.load(open(f))
        for g in d.get('games',[]):
            t=(g.get('title') or '').upper(); lc=g.get('levels_completed',0)
            if lc>0: cr[t]+=1
            ml[t].append(lc)
    print(f"--- budget {budget} ({n} seeds) ---")
    for t in sorted(ml):
        m=sum(ml[t])/len(ml[t]) if ml[t] else 0
        print(f"  {t}: {cr[t]}/{n}  mean={m:.2f}")
PY
echo "[r8] DONE $(date)" >> $log
