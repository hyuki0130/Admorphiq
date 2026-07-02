#!/bin/zsh
# R14 — measure the no-op-suppression efficiency change. Same 9 L1-stuck stable
# games @3000, 3 seeds, PARALLEL(PAR=3). KEY metric is EFFICIENCY: game_score and
# agent_actions-to-clear (not just clears), vs the R13 baseline. SUMMARY.txt is
# regenerated LIVE (clear-rate + in-flight TICK); a final EFFICIENCY block reports
# per-game avg game_score + avg agent_actions with the R13 baseline alongside.
cd /Users/nhn/Workspace/Admorphiq
D=scripts/rounds/R19
log=$D/run.log; sum=$D/SUMMARY.txt
mkdir -p $D/games $D/progress
: > $log; : > $sum
GAMES=(ft09 m0r0 bp35 cd82 cn04 ls20 r11l s5i5 sp80)
GAMESCSV="ft09,m0r0,bp35,cd82,cn04,ls20,r11l,s5i5,sp80"
SEEDS=(1 2 3)
PAR=3
echo "[R19] START $(date '+%Y-%m-%d %H:%M:%S %Z') — parallel(${PAR}) no-op-suppression, 9 games x3 seeds @3000 (efficiency)" | tee -a $log

run_one() {
  g=$1; s=$2; t0=$(date +%s)
  RL_SEED=$s BC_TTT=0 RL_PROGRESS_LOG="scripts/rounds/R19/progress/${g}_s${s}.log" RL_PROGRESS_EVERY=200 \
    uv run python scripts/score_efficiency.py --agent online_rl \
    --titles "$g" --max-actions 3000 --out "scripts/rounds/R19/games/${g}_s${s}.json" >/dev/null 2>&1
  echo "[R19] ${g} seed${s} done in $(($(date +%s)-t0))s $(date '+%H:%M:%S')" >> scripts/rounds/R19/run.log
  uv run python scripts/rounds/aggregate.py scripts/rounds/R19 "$GAMESCSV" 3 2>/dev/null
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
uv run python scripts/rounds/aggregate.py scripts/rounds/R19 "$GAMESCSV" 3

# --- EFFICIENCY report: avg game_score + avg agent_actions vs R13 baseline ---
uv run python - >> $sum 2>>$log <<'PY'
import json, glob
from collections import defaultdict

def load(round_dir):
    sc = defaultdict(list); act = defaultdict(list)
    for f in sorted(glob.glob(f"{round_dir}/games/*.json")):
        try: d = json.load(open(f))
        except Exception: continue
        for g in d.get("games", []):
            t = (g.get("title") or "?").upper()
            sc[t].append(g.get("game_score", 0.0))
            for pl in g.get("per_level", []):
                if pl.get("agent_actions"): act[t].append(pl["agent_actions"])
    return sc, act

r14s, r14a = load("scripts/rounds/R19")
r13s, r13a = load("scripts/rounds/R13")
order = ["FT09","M0R0","BP35","CD82","CN04","LS20","R11L","S5I5","SP80"]
print("\n--- EFFICIENCY (R14 no-op-suppression vs R13 baseline) ---")
print(f"{'game':6} {'R13_score':>10} {'R14_score':>10} {'R13_act':>8} {'R14_act':>8}")
tot13 = tot14 = 0.0; n = 0
for t in order:
    m13 = sum(r13s.get(t,[]))/len(r13s[t]) if r13s.get(t) else 0
    m14 = sum(r14s.get(t,[]))/len(r14s[t]) if r14s.get(t) else 0
    a13 = sum(r13a.get(t,[]))/len(r13a[t]) if r13a.get(t) else 0
    a14 = sum(r14a.get(t,[]))/len(r14a[t]) if r14a.get(t) else 0
    tot13 += m13; tot14 += m14; n += 1
    print(f"{t:6} {m13:10.4f} {m14:10.4f} {a13:8.0f} {a14:8.0f}")
print(f"{'MEAN':6} {tot13/n:10.4f} {tot14/n:10.4f}   (game_score; higher=better)")
print("KEEP if R14 mean game_score > R13 AND no clear lost (clears in the table above).")
PY
echo "[R19] DONE $(date '+%Y-%m-%d %H:%M:%S %Z') — answer in $sum" | tee -a $log
