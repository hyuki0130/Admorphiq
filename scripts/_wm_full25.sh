#!/bin/zsh
cd /Users/nhn/Workspace/Admorphiq
log=scripts/wm_full25.log; : > $log
echo "[wm25] START $(date) — world-model (R29) on ALL 25 public games, cap 2500" >> $log
uv run python scripts/score_efficiency.py --agent worldmodel --games all \
  --max-actions 2500 --out scripts/efficiency_worldmodel_full25.json >> $log 2>&1
echo "[wm25] SUMMARY $(date)" >> $log
uv run python - >> $log 2>&1 <<'PY'
import json
d=json.load(open("scripts/efficiency_worldmodel_full25.json"))
cl=[(g['title'],g['levels_completed'],g['win_levels']) for g in d['games'] if g.get('levels_completed',0)>0]
print(f"total_pct: {d['total_score_pct']}  | games clearing >=1: {len(cl)}")
for t,lc,wl in sorted(cl,key=lambda x:-x[1]): print(f"  {t}: {lc}/{wl}")
PY
echo "[wm25] DONE $(date)" >> $log
