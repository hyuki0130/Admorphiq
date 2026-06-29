#!/bin/zsh
cd /Users/nhn/Workspace/Admorphiq
log=scripts/v6_pipeline.log; : > $log
echo "[v6] START $(date)" >> $log
# 1) BC retrain on FULL 24-game gold (balanced + DAgger)
echo "[v6] BC retrain (24-game gold)" >> $log
uv run python scripts/train_policy.py --epochs 40 --patience 10 --dagger-rounds 2 --dagger-boost 3.0 --out models/bc_policy_v6.pt >> $log 2>&1
echo "[v6] BC done $(date)" >> $log; ls -la models/bc_policy_v6.pt >> $log 2>&1
# 2) RL fine-tune from v6
echo "[v6] RL fine-tune" >> $log
uv run python scripts/train_rl.py --init models/bc_policy_v6.pt --out models/bc_policy_v6_rl.pt --max-env-steps 50000 >> $log 2>&1
echo "[v6] RL done $(date)" >> $log; ls -la models/bc_policy_v6_rl.pt >> $log 2>&1
# 3) score both (TTT off for speed-ranking)
echo "[v6] scoring v6" >> $log
BC_TTT=0 BC_WEIGHTS=models/bc_policy_v6.pt uv run python scripts/score_efficiency.py --agent bc --games all --out scripts/efficiency_v6.json >> $log 2>&1
echo "[v6] scoring v6_rl" >> $log
BC_TTT=0 BC_WEIGHTS=models/bc_policy_v6_rl.pt uv run python scripts/score_efficiency.py --agent bc --games all --out scripts/efficiency_v6_rl.json >> $log 2>&1
# 4) promote best of {v2(current), v6, v6_rl}
echo "[v6] decision" >> $log
uv run python - >> $log 2>&1 <<'PY'
import json,shutil
def load(p):
    try:
        d=json.load(open(p)); t=d.get("total_score",0.0)
        n=len({g["game_id"].split("-")[0] for g in d["games"] if (g.get("levels_completed") or 0)>0})
        return t,n
    except Exception as e: return -1,0
V2=(0.022004,10)
cands={"v2_current":(V2,"models/bc_policy.pt"),
       "v6":(load("scripts/efficiency_v6.json"),"models/bc_policy_v6.pt"),
       "v6_rl":(load("scripts/efficiency_v6_rl.json"),"models/bc_policy_v6_rl.pt")}
for k,((t,n),_) in cands.items(): print(f"[cand] {k}: total={t} games={n}")
best=max(cands.items(), key=lambda kv: kv[1][0][0])
name,((bt,bn),path)=best
if name!="v2_current" and bt>V2[0]:
    shutil.copyfile(path,"models/bc_policy.pt")
    print(f"[PROMOTE] bc_policy.pt = {name} (total={bt} games={bn})")
else:
    print(f"[KEEP] v2 stays best (challengers did not beat total={V2[0]})")
PY
echo "[v6] DONE $(date)" >> $log
