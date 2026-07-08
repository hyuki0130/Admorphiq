#!/bin/zsh
# R53 — goal-conditioned WM planning (GF_EWM_PLAN=1, gpt-oss:20b) vs the deployed
# baseline. Baseline arm reuses scripts/rounds/R52/games0 (GF_EWM_PLAN default OFF
# is regression-verified byte-identical), so only the PLAN arm runs here.
# Full-25 @8000, PAR=2, per-game ratchet, live SUMMARY, GF_DEBUG captures plan
# counts. launchd-run (durable local pattern).
cd /Users/nhn/Workspace/Admorphiq
D=scripts/rounds/R53
ALL=(ar25 bp35 cd82 cn04 dc22 ft09 g50t ka59 lf52 lp85 ls20 m0r0 r11l re86 s5i5 sb26 sc25 sk48 sp80 su15 tn36 tr87 tu93 vc33 wa30)
PAR=2

agg() {
  /Users/nhn/.local/bin/uv run python - > $D/SUMMARY.txt 2>/dev/null <<'PY'
import json, glob, datetime

def load(pat):
    sc = {}
    for f in sorted(glob.glob(pat)):
        try:
            d = json.load(open(f))
        except Exception:
            continue
        for g in d.get('games', []):
            t = (g.get('title') or '?').upper()
            sc[t] = (g.get('game_score', 0), g.get('levels_completed', 0))
    return sc

base = load('scripts/rounds/R52/games0/*.json')      # deployed baseline
plan = load('scripts/rounds/R53/games/*.json')        # GF_EWM_PLAN=1
ts = datetime.datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')
print(f"[generated {ts}] R53 — GF_EWM_PLAN vs deployed baseline, full-25 @8000 (LIVE plan {len(plan)}/25)")
for name, sc in (('BASE (deployed)', base), ('PLAN (GF_EWM_PLAN)', plan)):
    if sc:
        vals = [v[0] for v in sc.values()]
        lv = sum(v[1] for v in sc.values())
        clr = sum(1 for v in sc.values() if v[1] > 0)
        print(f"  {name}: mean={sum(vals)/len(vals):.4f} levels={lv} clearing={clr}/{len(sc)}")
print(f"{'game':<6}{'base':>9}{'plan':>9}  {'lvl b/p':>8}")
delta = 0.0
for t in sorted(set(base) | set(plan)):
    b, p = base.get(t), plan.get(t)
    fb = '   --' if b is None else f"{b[0]:.4f}"
    fp = '   --' if p is None else f"{p[0]:.4f}"
    if b is not None and p is not None:
        delta += p[0] - b[0]
    mark = ' *' if (b and p and p[0] != b[0]) else ''
    print(f"{t:<6}{fb:>9}{fp:>9}  {str(b[1]) if b else '-':>3}/{str(p[1]) if p else '-':<3}{mark}")
print(f"\nscore delta (plan-base) over common games: {delta:+.4f}")
PY
}

run_one() {
  local g=$1 t0=$(date +%s)
  [ -f "$D/games/${g}.json" ] && return
  GF_GIVEUP=8000 GF_EWM_PLAN=1 GF_EWM_MODEL=gpt-oss:20b GF_DEBUG=1 \
    /Users/nhn/.local/bin/uv run python scripts/score_efficiency.py \
    --agent graph_frontier --titles "$g" --max-actions 8000 \
    --out "$D/games/${g}.json" > "$D/games/${g}.log" 2>&1
  echo "[R53 plan] $g $(($(date +%s)-t0))s $(date '+%H:%M:%S')" >> $D/run.log
  agg
}

mkdir -p $D/games
echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] R53 start: GF_EWM_PLAN=1 full-25 @8000 (baseline = R52/games0)" >> $D/run.log
pids=()
for g in $ALL; do
  run_one "$g" &
  pids+=($!)
  while (( ${#pids[@]} >= PAR )); do wait ${pids[1]} 2>/dev/null; pids=(${pids[2,-1]}); done
done
wait
agg
echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] R53 ALL DONE" >> $D/run.log
