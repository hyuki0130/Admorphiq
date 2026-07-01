#!/bin/zsh
# R11 — full-25 breadth of the online_rl general learner, PARALLEL across cores.
# Games are independent, so we run one score_efficiency process per game with a
# concurrency cap (env.step is CPU-bound; MPS is shared, so 6 keeps GPU sane).
# Each game writes its own json + a timed line; we merge into the fixed
# convention outputs (result.json + SUMMARY.txt). Answer is always SUMMARY.txt.
cd /Users/nhn/Workspace/Admorphiq
D=scripts/rounds/R11
log=$D/run.log; sum=$D/SUMMARY.txt
mkdir -p $D/games
: > $log; : > $sum
GAMES=(ar25 bp35 cd82 cn04 dc22 ft09 g50t ka59 lf52 lp85 ls20 m0r0 r11l re86 s5i5 sb26 sc25 sk48 sp80 su15 tn36 tr87 tu93 vc33 wa30)
PAR=3
echo "[R11] START $(date) — parallel(${PAR}) full-25 online_rl @3000 seed1" | tee -a $log

run_one() {
  g=$1
  t0=$(date +%s)
  RL_SEED=1 BC_TTT=0 uv run python scripts/score_efficiency.py --agent online_rl \
    --titles "$g" --max-actions 3000 --out "scripts/rounds/R11/games/$g.json" >/dev/null 2>&1
  t1=$(date +%s)
  echo "[R11] $g done in $((t1-t0))s $(date)" >> scripts/rounds/R11/run.log
}

# fan out with a concurrency cap
pids=()
for g in $GAMES; do
  run_one "$g" &
  pids+=($!)
  while (( ${#pids[@]} >= PAR )); do
    wait ${pids[1]} 2>/dev/null
    pids=(${pids[2,-1]})
  done
done
wait

echo "[R11] MERGE $(date)" >> $log
uv run python - > $sum 2>>$log <<'PY'
import json,glob,os
games=[]
for f in sorted(glob.glob('scripts/rounds/R11/games/*.json')):
    try:
        d=json.load(open(f)); games += d.get('games',[])
    except Exception as e:
        print(f"# WARN {os.path.basename(f)}: {e}")
json.dump({'games':games}, open('scripts/rounds/R11/result.json','w'))
cleared=[g for g in games if g.get('levels_completed',0)>0]
print(f"R11 SUMMARY — full-25 breadth, online_rl GENERAL learner, seed1 @3000 (PARALLEL)")
print(f"VERDICT DATA: {len(cleared)}/{len(games)} envs cleared >=1 level")
print(f"baseline 6-probe winners = AR25/FT09/LP85/M0R0. Anything NEW below = broader general coverage.")
for g in sorted(games,key=lambda x:(-x.get('levels_completed',0),(x.get('title') or ''))):
    lc=g.get('levels_completed',0); t=(g.get('title') or '?').upper()
    print(f"  {'*' if lc>0 else ' '} {t}: {lc} levels")
PY
echo "" >> $sum
echo "--- per-game wall-time (bottleneck check) ---" >> $sum
grep "done in" $log >> $sum
echo "[R11] DONE $(date) — answer in $sum" | tee -a $log
