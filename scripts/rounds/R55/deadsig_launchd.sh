#!/bin/zsh
# R55 — dead-signature (US-12) measurement. LLM-FREE (no ollama/GPU), so it is
# cheap (~5 min for 25 games like R52 arm0) and safe to run right after R53
# frees the box. Compares GF_DEAD_SIG=1 vs the deployed baseline (R52/games0,
# regression-verified byte-identical to default). Full-25 @8000, PAR=2, ratchet.
cd /Users/nhn/Workspace/Admorphiq
# Wait for the R53 planning run (and its GPU model) to finish first.
while pgrep -f "R53/run_launchd.sh" >/dev/null 2>&1; do sleep 60; done
D=scripts/rounds/R55
ALL=(ar25 bp35 cd82 cn04 dc22 ft09 g50t ka59 lf52 lp85 ls20 m0r0 r11l re86 s5i5 sb26 sc25 sk48 sp80 su15 tn36 tr87 tu93 vc33 wa30)
PAR=2

agg() {
  /Users/nhn/.local/bin/uv run python - > $D/SUMMARY.txt 2>/dev/null <<'PY'
import json, glob, datetime
def load(pat):
    sc={}
    for f in sorted(glob.glob(pat)):
        try: d=json.load(open(f))
        except Exception: continue
        for g in d.get('games',[]):
            t=(g.get('title') or '?').upper(); sc[t]=(g.get('game_score',0), g.get('levels_completed',0))
    return sc
base=load('scripts/rounds/R52/games0/*.json'); ds=load('scripts/rounds/R55/games/*.json')
ts=datetime.datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')
print(f"[generated {ts}] R55 — GF_DEAD_SIG vs deployed baseline, full-25 @8000 (LIVE {len(ds)}/25)")
for name,sc in (('BASE',base),('DEADSIG',ds)):
    if sc:
        v=[x[0] for x in sc.values()]; lv=sum(x[1] for x in sc.values()); clr=sum(1 for x in sc.values() if x[1]>0)
        print(f"  {name}: mean={sum(v)/len(v):.4f} levels={lv} clearing={clr}/{len(sc)}")
print(f"{'game':<6}{'base':>9}{'deadsig':>9}  lvl b/d")
delta=0.0
for t in sorted(set(base)|set(ds)):
    b,e=base.get(t),ds.get(t)
    fb='   --' if b is None else f"{b[0]:.4f}"; fe='   --' if e is None else f"{e[0]:.4f}"
    if b and e: delta+=e[0]-b[0]
    mark=' *' if (b and e and e[0]!=b[0]) else ''
    print(f"{t:<6}{fb:>9}{fe:>9}  {b[1] if b else '-'}/{e[1] if e else '-'}{mark}")
print(f"\nscore delta (deadsig-base): {delta:+.4f}")
PY
}

run_one() {
  local g=$1 t0=$(date +%s)
  [ -f "$D/games/${g}.json" ] && return
  GF_GIVEUP=8000 GF_DEAD_SIG=1 /Users/nhn/.local/bin/uv run python scripts/score_efficiency.py \
    --agent graph_frontier --titles "$g" --max-actions 8000 \
    --out "$D/games/${g}.json" >/dev/null 2>&1
  echo "[R55 deadsig] $g $(($(date +%s)-t0))s $(date '+%H:%M:%S')" >> $D/run.log
  agg
}

mkdir -p $D/games
echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] R55 start (after R53): GF_DEAD_SIG=1 full-25 @8000" >> $D/run.log
pids=()
for g in $ALL; do
  run_one "$g" &
  pids+=($!)
  while (( ${#pids[@]} >= PAR )); do wait ${pids[1]} 2>/dev/null; pids=(${pids[2,-1]}); done
done
wait; agg
echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] R55 ALL DONE" >> $D/run.log
