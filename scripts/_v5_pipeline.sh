#!/bin/zsh
cd /Users/nhn/Workspace/Admorphiq
log=scripts/v5_pipeline.log
: > $log
echo "[v5] train start $(date)" >> $log
uv run python scripts/train_policy.py --epochs 40 --patience 10 --dagger-rounds 2 --dagger-boost 3.0 --out models/bc_policy_v5.pt >> $log 2>&1
echo "[v5] train done $(date)" >> $log
ls -la models/bc_policy_v5*.pt >> $log 2>&1
echo "[v5] scoring all games" >> $log
BC_WEIGHTS=models/bc_policy_v5.pt uv run python scripts/score_efficiency.py --agent bc --games all --out scripts/efficiency_r20_v5.json >> $log 2>&1
echo "[v5] scoring done; decision" >> $log
uv run python - >> $log 2>&1 <<'PY'
import json,shutil
V2_TOTAL=0.022004; V2_N=10
d=json.load(open("scripts/efficiency_r20_v5.json"))
total=d.get("total_score",0.0)
n=len({g["game_id"].split("-")[0] for g in d["games"] if (g.get("levels_completed") or 0)>0})
print(f"[decision] v5 total={total} n={n} | v2 total={V2_TOTAL} n={V2_N}")
if total>V2_TOTAL and n>=V2_N:
    shutil.copyfile("models/bc_policy_v5.pt","models/bc_policy.pt")
    print("[decision] PROMOTED bc_policy.pt=v5")
else:
    print("[decision] KEEP v2")
PY
echo "[v5] DONE $(date)" >> $log
