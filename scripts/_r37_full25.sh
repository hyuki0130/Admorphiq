#!/bin/zsh
cd /Users/nhn/Workspace/Admorphiq
log=scripts/r37_full25.log; : > $log
echo "[r37] START $(date) — R34 card full-25, cap 2500" >> $log
BC_TTT=0 uv run python scripts/score_efficiency.py --agent worldmodel --games all \
  --max-actions 2500 --out scripts/efficiency_worldmodel_full25_r34.json >> $log 2>&1
echo "[r37] SUMMARY $(date)" >> $log
uv run python - >> $log 2>&1 <<'PY'
import json
d=json.load(open("scripts/efficiency_worldmodel_full25_r34.json"))
seen={}
for g in d['games']:
    t=(g.get('title') or '').upper(); lc=g.get('levels_completed',0)
    if t not in seen or lc>seen[t]: seen[t]=lc
clear=sorted([t for t,l in seen.items() if l>0])
zero=sorted([t for t,l in seen.items() if l==0])
print(f"total_pct: {d['total_score_pct']}  | unique cleared: {len(clear)}/{len(seen)}")
print("CLEARED:", {t:seen[t] for t in clear})
print("ZERO (R38 targets):", zero)
PY
echo "[r37] DONE $(date)" >> $log
