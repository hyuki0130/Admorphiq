#!/bin/zsh
cd /Users/nhn/Workspace/Admorphiq
log=scripts/r47_full25.log; : > $log
echo "[r47full] START $(date)" >> $log
BC_TTT=0 uv run python scripts/score_efficiency.py --agent worldmodel --games all --max-actions 3000 --out scripts/efficiency_worldmodel_r47_full25.json >> $log 2>&1
uv run python - >> $log 2>&1 <<'PY'
import json
d=json.load(open("scripts/efficiency_worldmodel_r47_full25.json"))
seen={}
for g in d['games']:
    t=(g.get('title') or '').upper(); lc=g.get('levels_completed',0)
    if t not in seen or lc>seen[t]: seen[t]=lc
cl={t:l for t,l in sorted(seen.items()) if l>0}
print("[r47full] total_pct:", d['total_score_pct'], "| cleared:", cl)
PY
echo "[r47full] DONE $(date)" >> $log
