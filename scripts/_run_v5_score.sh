#!/bin/zsh
cd /Users/nhn/Workspace/Admorphiq
log=scripts/score_v5.log
# 1) wait for training to finish writing the v5 artifact
while ! grep -q "Saved best" scripts/train_v5.log 2>/dev/null; do sleep 120; done
echo "[chain] training done" >> $log
ls -la models/bc_policy_v5*.pt >> $log 2>&1
# 2) score v5 across all games
echo "[chain] scoring v5 ..." >> $log
BC_WEIGHTS=models/bc_policy_v5.pt PYTHONUNBUFFERED=1 uv run python scripts/score_efficiency.py \
  --agent bc --games all --out scripts/efficiency_r20_v5.json >> $log 2>&1
echo "[chain] scoring complete; deciding ..." >> $log
# 3) evidence-based promotion decision (guarded): promote only if v5 beats v2
#    on BOTH total_score and unique games cleared.
uv run python - >> $log 2>&1 <<'PY'
import json, shutil
V2_TOTAL=0.022004
V2_UNIQUE={"AR25","FT09","LP85","LS20","M0R0","SB26","SK48","SP80","VC33","WA30"}
GOLD_UNCLEARED={"BP35","CD82","DC22","G50T","KA59","LF52","R11L","RE86","SC25","TU93"}
d=json.load(open("scripts/efficiency_r20_v5.json"))
total=d.get("total_score",0.0)
cleared={g.get("title") for g in d["games"] if (g.get("levels_completed") or 0)>0}
new_from_uncleared=sorted(cleared & GOLD_UNCLEARED)
print(f"[decision] v5 total={total} (v2={V2_TOTAL})")
print(f"[decision] v5 unique cleared={len(cleared)} (v2={len(V2_UNIQUE)}): {sorted(cleared)}")
print(f"[decision] newly-cleared gold-but-uncleared: {new_from_uncleared}")
if total>V2_TOTAL and len(cleared)>len(V2_UNIQUE):
    shutil.copyfile("models/bc_policy_v5.pt","models/bc_policy.pt")
    print("[decision] PROMOTED: bc_policy.pt = v5 (beats v2 on total AND coverage)")
else:
    print("[decision] KEEP v2: v5 did not beat v2 on both total and coverage")
PY
echo "[chain] DONE" >> $log
