#!/bin/zsh
# Held-out transfer test: train pure BC on 18 games, score the 7 held-out games
# the policy has NEVER seen. Measures whether BC generalizes to unseen games or
# memorizes the training set — the decisive experiment for the world-model pivot.
cd /Users/nhn/Workspace/Admorphiq
log=scripts/transfer_test.log; : > $log
HOLD="tu93,ar25,cd82,ft09,su15,sb26,sc25"   # class-spanning: nav/paint/toggle/merge/sort/spell
CAP=5000   # diagnostic action cap; clears beyond this score ~0 under squared-eff anyway

echo "[xfer] START $(date)" >> $log

# 1) Pure BC on the 18 non-held-out games (DAgger OFF → zero holdout leakage).
echo "[xfer] TRAIN holdout=$HOLD" >> $log
uv run python scripts/train_policy.py --epochs 30 --patience 8 \
  --dagger-rounds 0 --no-dagger-rollout \
  --holdout $HOLD --out models/bc_holdout.pt >> $log 2>&1
echo "[xfer] train done $(date)" >> $log

# 2) Score ONLY the 7 held-out (unseen) games with the holdout model.
echo "[xfer] SCORE held-out (unseen), cap=$CAP" >> $log
BC_TTT=0 BC_WEIGHTS=models/bc_holdout.pt \
  uv run python scripts/score_efficiency.py --agent bc --titles $HOLD \
  --max-actions $CAP --out scripts/efficiency_holdout_unseen.json >> $log 2>&1
echo "[xfer] score done $(date)" >> $log

# 3) Compare unseen (holdout model) vs in-sample (v6 saw these games).
echo "[xfer] SUMMARY" >> $log
uv run python - >> $log 2>&1 <<'PY'
import json
HOLD = ["tu93","ar25","cd82","ft09","su15","sb26","sc25"]
def by_title(path):
    d = json.load(open(path)); out = {}
    for g in d["games"]:
        t = (g.get("title") or g.get("game_id") or "").lower()
        gs = g.get("game_score")
        if gs is not None and (t not in out or gs > out[t]):
            out[t] = gs
    return out
unseen = by_title("scripts/efficiency_holdout_unseen.json")
insample = by_title("scripts/efficiency_v6.json")
print(f"{'game':8} {'UNSEEN(holdout)':>16} {'IN-SAMPLE(v6)':>15}")
us=ins=0.0; n=0
for t in HOLD:
    u = unseen.get(t); i = insample.get(t)
    us += (u or 0.0); ins += (i or 0.0); n += 1
    print(f"{t:8} {('%.4f'%u) if u is not None else '   n/a':>16} {('%.4f'%i) if i is not None else '   n/a':>15}")
print(f"{'MEAN':8} {us/n:>16.4f} {ins/n:>15.4f}")
ratio = (us/n) / (ins/n) if ins else 0.0
print(f"\nTRANSFER RATIO (unseen / in-sample) = {ratio:.2%}")
print("VERDICT:", "BC GENERALIZES (transfer real)" if ratio >= 0.5
      else "BC MOSTLY MEMORIZES (low transfer -> world-model/online-learning is the general path)")
PY
echo "[xfer] DONE $(date)" >> $log
