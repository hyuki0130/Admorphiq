#!/bin/zsh
# FINAL — full-25 at the DEPLOYED config (MAX_ACTIONS=100k class; GF_GIVEUP=100000).
# This is the honest final number of the shipped card. PAR=2, live SUMMARY.
cd /Users/nhn/Workspace/Admorphiq
D=scripts/rounds/RFINAL2; : > $D/run.log; : > $D/SUMMARY.txt
ALL=(ar25 bp35 cd82 cn04 dc22 ft09 g50t ka59 lf52 lp85 ls20 m0r0 r11l re86 s5i5 sb26 sc25 sk48 sp80 su15 tn36 tr87 tu93 vc33 wa30)
PAR=2
agg() {
  uv run python - > $D/SUMMARY.txt 2>/dev/null <<'PY'
import json,glob,datetime
sc={}
for f in sorted(glob.glob('scripts/rounds/RFINAL2/games/*.json')):
    try: d=json.load(open(f))
    except: continue
    for g in d.get('games',[]):
        t=(g.get('title') or '?').upper()
        acts=[p.get('agent_actions') for p in g.get('per_level',[]) if p.get('agent_actions')]
        sc[t]=(g.get('game_score',0), g.get('levels_completed',0), acts)
vals=[v[0] for v in sc.values()]; lv=sum(v[1] for v in sc.values()); clr=sum(1 for v in sc.values() if v[1]>0)
ts=datetime.datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')
print(f"[generated {ts}] FINAL card — full-25 @100k (deployed config) LIVE {len(sc)}/25")
print(f"mean game_score = {sum(vals)/max(1,len(vals)):.4f} | total levels = {lv} | games clearing = {clr}/25")
print("(참조: from-scratch online-RL 0.0014, random 0.0000, verified top 0.1258)")
for t in sorted(sc, key=lambda k:-sc[k][0]):
    if sc[t][1]>0: print(f"  * {t}: score={sc[t][0]:.4f} lvl={sc[t][1]} act={sc[t][2]}")
PY
}
run_one() {
  g=$1; t0=$(date +%s)
  GF_GIVEUP=100000 uv run python scripts/score_efficiency.py --agent graph_frontier \
    --titles "$g" --max-actions 100000 --out "$D/games/${g}.json" >/dev/null 2>&1
  echo "[FINAL2] $g $(($(date +%s)-t0))s $(date '+%H:%M:%S')" >> $D/run.log
  agg
}
pids=()
for g in $ALL; do
  run_one "$g" &
  pids+=($!)
  while (( ${#pids[@]} >= PAR )); do wait ${pids[1]} 2>/dev/null; pids=(${pids[2,-1]}); done
done
wait
agg
echo "[FINAL2] DONE $(date '+%Y-%m-%d %H:%M:%S %Z')" >> $D/run.log
