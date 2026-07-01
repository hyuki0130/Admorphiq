#!/bin/zsh
# R17 — honest baseline: the DEPLOYED card's FULL-25 total game_score (real RHAE
# proxy-leaderboard number). We've only ever measured subsets/levels; this is the
# true total_score. PARALLEL(PAR=3), 1 seed @3000. SUMMARY regenerated LIVE; a
# final TOTAL block reports mean game_score across all 25 games (the number any
# future structural bet must beat).
cd /Users/nhn/Workspace/Admorphiq
D=scripts/rounds/R17
log=$D/run.log; sum=$D/SUMMARY.txt
mkdir -p $D/games $D/progress
: > $log; : > $sum
GAMES=(ar25 bp35 cd82 cn04 dc22 ft09 g50t ka59 lf52 lp85 ls20 m0r0 r11l re86 s5i5 sb26 sc25 sk48 sp80 su15 tn36 tr87 tu93 vc33 wa30)
GAMESCSV="ar25,bp35,cd82,cn04,dc22,ft09,g50t,ka59,lf52,lp85,ls20,m0r0,r11l,re86,s5i5,sb26,sc25,sk48,sp80,su15,tn36,tr87,tu93,vc33,wa30"
PAR=3
echo "[R17] START $(date '+%Y-%m-%d %H:%M:%S %Z') — parallel(${PAR}) DEPLOYED card full-25 total game_score, seed1 @3000" | tee -a $log

run_one() {
  g=$1; t0=$(date +%s)
  RL_SEED=1 BC_TTT=0 RL_PROGRESS_LOG="scripts/rounds/R17/progress/${g}_s1.log" RL_PROGRESS_EVERY=200 \
    uv run python scripts/score_efficiency.py --agent online_rl \
    --titles "$g" --max-actions 3000 --out "scripts/rounds/R17/games/${g}_s1.json" >/dev/null 2>&1
  echo "[R17] ${g} done in $(($(date +%s)-t0))s $(date '+%H:%M:%S')" >> scripts/rounds/R17/run.log
  uv run python scripts/rounds/aggregate.py scripts/rounds/R17 "$GAMESCSV" 1 2>/dev/null
}

pids=()
for g in $GAMES; do
  run_one "$g" &
  pids+=($!)
  while (( ${#pids[@]} >= PAR )); do wait ${pids[1]} 2>/dev/null; pids=(${pids[2,-1]}); done
done
wait
uv run python scripts/rounds/aggregate.py scripts/rounds/R17 "$GAMESCSV" 1

# --- TOTAL game_score across all 25 (the real proxy-leaderboard number) ---
uv run python - >> $sum 2>>$log <<'PY'
import json, glob
scores = {}
for f in sorted(glob.glob("scripts/rounds/R17/games/*.json")):
    try: d = json.load(open(f))
    except Exception: continue
    for g in d.get("games", []):
        scores[(g.get("title") or "?").upper()] = g.get("game_score", 0.0)
if scores:
    vals = list(scores.values())
    mean = sum(vals) / len(vals)
    cleared = sum(1 for v in vals if v > 0)
    print("\n--- TOTAL (deployed card, full-25, seed1 @3000) ---")
    for t in sorted(scores, key=lambda k: -scores[k]):
        print(f"  {t}: game_score={scores[t]:.4f}")
    print(f"MEAN game_score across {len(vals)} games = {mean:.4f}  ({cleared} games > 0)")
    print("This is the real RHAE proxy-leaderboard number. Any future round must beat it.")
PY
echo "[R17] DONE $(date '+%Y-%m-%d %H:%M:%S %Z') — answer in $sum" | tee -a $log
