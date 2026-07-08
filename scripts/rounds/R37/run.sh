#!/bin/zsh
# R37 — graph-frontier upside: bigger budgets (@8000/@30000 on the 9-subset) + full-25 @8000.
cd /Users/nhn/Workspace/Admorphiq
D=scripts/rounds/R37; log=$D/run.log; sum=$D/SUMMARY.txt
mkdir -p $D/games; : > $log; : > $sum
NINE=(ft09 m0r0 bp35 cd82 cn04 ls20 r11l s5i5 sp80)
ALL=(ar25 bp35 cd82 cn04 dc22 ft09 g50t ka59 lf52 lp85 ls20 m0r0 r11l re86 s5i5 sb26 sc25 sk48 sp80 su15 tn36 tr87 tu93 vc33 wa30)
PAR=2
echo "[R37] START $(date '+%Y-%m-%d %H:%M:%S %Z')" | tee -a $log
agg() {
  uv run python - > $D/SUMMARY.txt 2>/dev/null <<'PY'
import json,glob,os,re
from collections import defaultdict
res=defaultdict(dict)
for f in sorted(glob.glob('scripts/rounds/R37/games/*.json')):
    m=re.match(r'(\w+)_b(\d+)\.json', os.path.basename(f))
    if not m: continue
    try: d=json.load(open(f))
    except: continue
    for g in d.get('games',[]):
        res[m.group(2)][(g.get('title') or '?').upper()]=(g.get('game_score',0), g.get('levels_completed',0))
print("R37 graph-frontier upside LIVE (baseline: @3000 9-subset 0.0055)")
for b in sorted(res,key=int):
    v=res[b]; sc=[x[0] for x in v.values()]; lv=sum(x[1] for x in v.values())
    print(f"--- @{b} ({len(v)} games) mean={sum(sc)/max(1,len(sc)):.4f} total_levels={lv} ---")
    for t in sorted(v):
        if v[t][1]>0: print(f"  * {t}: score={v[t][0]:.4f} levels={v[t][1]}")
PY
}
run_one() {
  g=$1; b=$2; t0=$(date +%s)
  uv run python scripts/score_efficiency.py --agent graph_frontier \
    --titles "$g" --max-actions $b --out "$D/games/${g}_b${b}.json" >/dev/null 2>&1
  echo "[R37] ${g} @${b} $(($(date +%s)-t0))s $(date '+%H:%M:%S')" >> $D/run.log
  agg
}
for b in 8000 30000; do
  pids=()
  for g in $NINE; do
    run_one "$g" $b &
    pids+=($!)
    while (( ${#pids[@]} >= PAR )); do wait ${pids[1]} 2>/dev/null; pids=(${pids[2,-1]}); done
  done
  wait
done
# full-25 @8000 (fills the non-subset games)
pids=()
for g in $ALL; do
  [ -f "$D/games/${g}_b8000.json" ] && continue
  run_one "$g" 8000 &
  pids+=($!)
  while (( ${#pids[@]} >= PAR )); do wait ${pids[1]} 2>/dev/null; pids=(${pids[2,-1]}); done
done
wait
agg
echo "" >> $sum
echo "[R37] DONE $(date '+%Y-%m-%d %H:%M:%S %Z')" | tee -a $log >> $sum
