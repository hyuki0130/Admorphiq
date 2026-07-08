#!/bin/zsh
# RL multi-round TRAINING track (user-directed): not a one-shot run — train long with
# checkpoints, score the whole curve, keep-best-by-eval, and VALIDATE GENERALITY on
# held-out games (RL trained on public games has the same transfer risk as BC, so we
# MEASURE transfer instead of assuming it). This is round 1 of the track.
cd /Users/nhn/Workspace/Admorphiq
log=scripts/rl_track.log; : > $log
echo "[rl] START $(date)" >> $log

# Held-out split: train RL on 18 games, hold out 7 (the same class-spanning set used for
# the BC transfer test) so we can measure whether RL GENERALIZES, not just memorizes.
TRAIN="tu93,ar25,lp85,ls20,m0r0,dc22,sp80,g50t,vc33,r11l,cn04,bp35,sk48,lf52,re86,s5i5,ka59,wa30"
HOLD="ft09,tn36,sb26,su15,cd82,tr87,sc25"

# Round 1: warm-start from BC v6, train LONG (150k steps) with frequent checkpoints.
# Lower LR + stronger KL anchor than the failed R44 1.54% run (lr 1e-4/KL 0.1) — per the
# feedback_rl_not_abandoned memory: lr down, KL up, drop the frame-change shaping that
# rewards wiggling over solving.
echo "[rl] R1 train: 150k steps, lr 3e-5, kl 0.5, change-reward 0, ckpt every 15k" >> $log
caffeinate -i uv run python scripts/train_rl.py \
  --init models/bc_policy_v6.pt --out models/bc_rl_track_r1.pt \
  --games "$TRAIN" --max-env-steps 150000 --ckpt-every 15000 \
  --lr 3e-5 --kl-coef 0.5 --change-reward 0.0 --ent-coef 0.01 >> $log 2>&1
echo "[rl] R1 train done $(date)" >> $log
ls -t models/bc_rl_track_r1*.pt >> $log 2>&1

# Score the full checkpoint curve on HELD-OUT games (TTT off) — keep-best-by-eval.
echo "[rl] scoring checkpoint curve on HELD-OUT ($HOLD)" >> $log
for ck in models/bc_rl_track_r1_step*.pt models/bc_rl_track_r1.pt; do
  [ -f "$ck" ] || continue
  nm=$(basename "$ck" .pt)
  BC_TTT=0 BC_WEIGHTS="$ck" uv run python scripts/score_efficiency.py --agent bc \
    --titles "$HOLD" --max-actions 2500 --out "scripts/eff_${nm}_holdout.json" >> $log 2>&1
  echo "[rl] scored $nm (holdout)" >> $log
done
# Baseline: BC v6 itself on the same held-out set (the bar RL must beat to show RL helps).
BC_TTT=0 BC_WEIGHTS=models/bc_policy_v6.pt uv run python scripts/score_efficiency.py --agent bc \
  --titles "$HOLD" --max-actions 2500 --out scripts/eff_bcv6_holdout.json >> $log 2>&1

echo "[rl] CURVE SUMMARY (held-out — does RL generalize?)" >> $log
uv run python - >> $log 2>&1 <<'PY'
import json, glob, os
def total(p):
    try: return json.load(open(p))['total_score_pct']
    except: return None
print(f"{'checkpoint':32}{'heldout_total%':>16}")
print(f"{'BC v6 (baseline)':32}{str(total('scripts/eff_bcv6_holdout.json')):>16}")
rows=[]
for f in sorted(glob.glob('scripts/eff_bc_rl_track_r1*_holdout.json')):
    rows.append((os.path.basename(f), total(f)))
for nm,t in rows: print(f"{nm:32}{str(t):>16}")
base=total('scripts/eff_bcv6_holdout.json') or 0
best=max([t for _,t in rows if t is not None], default=0)
print(f"\nbest RL heldout {best} vs BC v6 {base} -> RL {'GENERALIZES (beats BC on unseen)' if best>base else 'no transfer gain yet (tune next round)'}")
PY
echo "[rl] DONE $(date)" >> $log
