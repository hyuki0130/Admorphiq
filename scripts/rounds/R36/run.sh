#!/bin/zsh
# R36 — graph-frontier agent (training-free) on the 9-game subset, @3000 and @8000.
# Compare vs transfer-honest baseline 0.0014 (from-scratch online-RL) and random 0.0000.
cd /Users/nhn/Workspace/Admorphiq
D=scripts/rounds/R36; log=$D/run.log; sum=$D/SUMMARY.txt
mkdir -p $D/games; : > $log; : > $sum
GAMES=(ft09 m0r0 bp35 cd82 cn04 ls20 r11l s5i5 sp80)
PAR=2
echo "[R36] START $(date '+%Y-%m-%d %H:%M:%S %Z') — graph_frontier @3000 + @8000, 9 games" | tee -a $log
run_one() {
  g=$1; b=$2; t0=$(date +%s)
  uv run python scripts/score_efficiency.py --agent graph_frontier \
    --titles "$g" --max-actions $b --out "$D/games/${g}_b${b}.json" >/dev/null 2>&1
  echo "[R36] ${g} @${b} $(($(date +%s)-t0))s $(date '+%H:%M:%S')" >> $D/run.log
  uv run python - <<'PY' > $D/SUMMARY.txt 2>/dev/null
import json,glob,os,re
from collections import defaultdict
res=defaultdict(dict)
for f in sorted(glob.glob('scripts/rounds/R36/games/*.json')):
    m=re.match(r'(\w+)_b(\d+)\.json', os.path.basename(f))
    if not m: continue
    try: d=json.load(open(f))
    except: continue
    for g in d.get('games',[]):
        res[m.group(2)][(g.get('title') or '?').upper()]=(g.get('game_score',0), g.get('levels_completed',0))
print(f"R36 graph_frontier LIVE — baselines: online-RL from-scratch 0.0014, random 0.0000")
for b in sorted(res):
    v=res[b]; sc=[x[0] for x in v.values()]
    print(f"--- @{b} ({len(v)}/9 games) mean game_score={sum(sc)/max(1,len(sc)):.4f} ---")
    for t in sorted(v): print(f"  {t}: score={v[t][0]:.4f} levels={v[t][1]}")
PY
}
for b in 3000 8000; do
  pids=()
  for g in $GAMES; do
    run_one "$g" $b &
    pids+=($!)
    while (( ${#pids[@]} >= PAR )); do wait ${pids[1]} 2>/dev/null; pids=(${pids[2,-1]}); done
  done
  wait
done
echo "" >> $sum
echo "[R36] DONE $(date '+%Y-%m-%d %H:%M:%S %Z')" | tee -a $log >> $sum
