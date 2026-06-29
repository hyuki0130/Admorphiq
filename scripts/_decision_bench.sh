#!/bin/zsh
cd /Users/nhn/Workspace/Admorphiq
log=scripts/decision_bench.log; : > $log
echo "[dec] START $(date)" >> $log
echo "[dec] world-model (R31) full-25..." >> $log
uv run python scripts/score_efficiency.py --agent worldmodel --games all --max-actions 2500 --out scripts/eff_decision_worldmodel.json >> $log 2>&1
echo "[dec] general/explore full-25..." >> $log
uv run python scripts/score_efficiency.py --agent general --games all --max-actions 2500 --out scripts/eff_decision_general.json >> $log 2>&1
echo "[dec] SUMMARY $(date)" >> $log
uv run python - >> $log 2>&1 <<'PY'
import json
def summ(p):
    d=json.load(open(p)); seen={}
    for g in d['games']:
        t=(g.get('title') or '').upper(); lc=g.get('levels_completed',0)
        if lc>0 and (t not in seen or lc>seen[t]): seen[t]=lc
    return d['total_score_pct'], seen
for name,p in [("WORLD-MODEL","scripts/eff_decision_worldmodel.json"),("GENERAL(explore)","scripts/eff_decision_general.json")]:
    pct,seen=summ(p)
    print(f"{name}: total {pct}%  | {len(seen)} unique games: {dict(sorted(seen.items(),key=lambda x:-x[1]))}")
PY
echo "[dec] DONE $(date)" >> $log
