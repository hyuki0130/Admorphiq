#!/bin/zsh
cd /Users/nhn/Workspace/Admorphiq
log=scripts/holdout_ttt.log; : > $log
HOLD="tu93,ar25,cd82,ft09,su15,sb26,sc25"
echo "[ttt] START $(date) — holdout model on 7 UNSEEN games, TTT=ON, cap 3000" >> $log
BC_TTT=1 BC_WEIGHTS=models/bc_holdout.pt \
  uv run python scripts/score_efficiency.py --agent bc --titles $HOLD \
  --max-actions 3000 --out scripts/efficiency_holdout_unseen_ttt.json >> $log 2>&1
echo "[ttt] SUMMARY $(date)" >> $log
uv run python - >> $log 2>&1 <<'PY'
import json
HOLD=["tu93","ar25","cd82","ft09","su15","sb26","sc25"]
def by_title(p):
    d=json.load(open(p)); o={}
    for g in d["games"]:
        t=(g.get("title") or g.get("game_id") or "").lower(); gs=g.get("game_score")
        lc=g.get("levels_completed",0)
        if t not in o or (gs or 0)>o[t][0]: o[t]=((gs or 0),lc)
    return o
ttt=by_title("scripts/efficiency_holdout_unseen_ttt.json")
off=by_title("scripts/efficiency_holdout_unseen.json")
print(f"{'game':7}{'TTT=ON score':>14}{'lvls':>6}{'  | TTT=OFF':>12}")
son=soff=0.0
for t in HOLD:
    a=ttt.get(t,(0,0)); b=off.get(t,(0,0)); son+=a[0]; soff+=b[0]
    print(f"{t:7}{a[0]:>14.4f}{a[1]:>6}{b[0]:>12.4f}")
print(f"{'MEAN':7}{son/7:>14.4f}{'':>6}{soff/7:>12.4f}")
print("\nEVIDENCE:", "BC+TTT clears SOME unseen games -> base score plausible" if son>0
      else "BC+TTT clears ZERO unseen games -> NO evidence of any base score on private")
PY
echo "[ttt] DONE $(date)" >> $log
