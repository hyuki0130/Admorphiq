#!/bin/zsh
# R52 — GF_EWM measurement: baseline (GF_EWM=0) vs world-model pruning
# (GF_EWM=1, gpt-oss:20b local). Full-25 @8000 actions, PAR=2 per arm,
# per-game ratchet (skip existing JSONs), live SUMMARY after every game.
# launchd-run: the durable local pattern (R49d traceless harness-task kills).
cd /Users/nhn/Workspace/Admorphiq
D=scripts/rounds/R52
ALL=(ar25 bp35 cd82 cn04 dc22 ft09 g50t ka59 lf52 lp85 ls20 m0r0 r11l re86 s5i5 sb26 sc25 sk48 sp80 su15 tn36 tr87 tu93 vc33 wa30)
PAR=2

agg() {
  /Users/nhn/.local/bin/uv run python - > $D/SUMMARY.txt 2>/dev/null <<'PY'
import json, glob, datetime

def load(arm):
    sc = {}
    for f in sorted(glob.glob(f'scripts/rounds/R52/games{arm}/*.json')):
        try:
            d = json.load(open(f))
        except Exception:
            continue
        for g in d.get('games', []):
            t = (g.get('title') or '?').upper()
            sc[t] = (g.get('game_score', 0), g.get('levels_completed', 0))
    return sc

b, e = load(0), load(1)
ts = datetime.datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')
print(f"[generated {ts}] R52 — GF_EWM off/on, full-25 @8000 (LIVE {len(b)}/{len(e)} of 25 per arm)")
for arm, sc in (('BASE (GF_EWM=0)', b), ('EWM  (GF_EWM=1)', e)):
    if sc:
        vals = [v[0] for v in sc.values()]
        lv = sum(v[1] for v in sc.values())
        clr = sum(1 for v in sc.values() if v[1] > 0)
        print(f"  {arm}: mean={sum(vals)/len(vals):.4f} levels={lv} clearing={clr}/{len(sc)}")
print(f"{'game':<6}{'base':>9}{'ewm':>9}  {'lvl b/e':>8}")
for t in sorted(set(b) | set(e)):
    bs, es = b.get(t, (None, None)), e.get(t, (None, None))
    fb = '   --' if bs[0] is None else f"{bs[0]:.4f}"
    fe = '   --' if es[0] is None else f"{es[0]:.4f}"
    mark = ' *' if (bs[0] is not None and es[0] is not None and es[0] != bs[0]) else ''
    print(f"{t:<6}{fb:>9}{fe:>9}  {str(bs[1]):>3}/{str(es[1]):<3}{mark}")
PY
}

run_one() {
  local arm=$1 g=$2 t0=$(date +%s)
  [ -f "$D/games${arm}/${g}.json" ] && return
  local envs=(GF_GIVEUP=8000)
  local log=/dev/null
  if [ "$arm" = "1" ]; then
    envs+=(GF_EWM=1 GF_EWM_MODEL=gpt-oss:20b GF_DEBUG=1)
    log="$D/games1/${g}.log"   # captures the [GF-EWM] synthesized-fit line
  fi
  env $envs /Users/nhn/.local/bin/uv run python scripts/score_efficiency.py \
    --agent graph_frontier --titles "$g" --max-actions 8000 \
    --out "$D/games${arm}/${g}.json" > "$log" 2>&1
  echo "[R52 arm$arm] $g $(($(date +%s)-t0))s $(date '+%H:%M:%S')" >> $D/run.log
  agg
}

mkdir -p $D/games0 $D/games1
echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] R52 start: full-25 @8000, arm0=base arm1=GF_EWM(gpt-oss:20b)" >> $D/run.log
for arm in 0 1; do
  pids=()
  for g in $ALL; do
    run_one "$arm" "$g" &
    pids+=($!)
    while (( ${#pids[@]} >= PAR )); do wait ${pids[1]} 2>/dev/null; pids=(${pids[2,-1]}); done
  done
  wait
  echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] R52 arm$arm DONE" >> $D/run.log
done
agg
echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] R52 ALL DONE" >> $D/run.log
