#!/bin/zsh
cd /Users/nhn/Workspace/Admorphiq
log=scripts/rl_curve.log; : > $log
echo "[curve] START $(date)" >> $log
for ck in v6_rl_step10122 v6_rl_step20147 v6_rl_step30162 v6_rl_step40270 v6_rl; do
  echo "[curve] scoring $ck $(date)" >> $log
  BC_TTT=0 BC_WEIGHTS=models/bc_policy_$ck.pt \
    uv run python scripts/score_efficiency.py --agent bc --games all \
    --out scripts/efficiency_$ck.json >> $log 2>&1
  echo "[curve] done $ck" >> $log
done
echo "[curve] SUMMARY $(date)" >> $log
uv run python - >> $log 2>&1 <<'PY'
import json
rows=[("v6(init)","efficiency_v6.json")]
for ck in ["v6_rl_step10122","v6_rl_step20147","v6_rl_step30162","v6_rl_step40270","v6_rl"]:
    rows.append((ck,f"efficiency_{ck}.json"))
print(f"{'checkpoint':22} {'total%':>8} {'games>=1':>9}")
for name,f in rows:
    try:
        d=json.load(open("scripts/"+f))
        g=sum(1 for x in d['games'] if x.get('levels_completed',0)>0)
        print(f"{name:22} {d['total_score_pct']:>8.3f} {g:>9}")
    except Exception as e:
        print(f"{name:22}  MISSING ({e})")
PY
echo "[curve] DONE $(date)" >> $log
