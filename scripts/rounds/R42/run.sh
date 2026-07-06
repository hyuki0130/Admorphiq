#!/bin/zsh
# R42 verdict — new claims (S5I5/SB26/TU93) @8000 + full no-loss spot-check.
cd /Users/nhn/Workspace/Admorphiq
D=scripts/rounds/R42; : > $D/run.log
# claimed new clears + the rest of the failing set
for g in s5i5 sb26 tu93 dc22 g50t ka59 re86 sc25 su15 wa30; do
  GF_GIVEUP=8000 uv run python scripts/score_efficiency.py --agent graph_frontier --titles "$g" --max-actions 8000 --out "$D/games/${g}_new.json" >/dev/null 2>&1
  echo "[R42] $g @8k $(date '+%H:%M:%S')" >> $D/run.log
done
# no-loss spot-check: quick set + deep CD82/VC33
for g in ft09 m0r0 cd82 r11l sp80 cn04 lp85 tn36 vc33 bp35 ls20; do
  uv run python scripts/score_efficiency.py --agent graph_frontier --titles "$g" --max-actions 3000 --out "$D/games/${g}_q.json" >/dev/null 2>&1
done
GF_GIVEUP=30000 uv run python scripts/score_efficiency.py --agent graph_frontier --titles cd82 --max-actions 30000 --out "$D/games/cd82_deep.json" >/dev/null 2>&1
GF_GIVEUP=60000 uv run python scripts/score_efficiency.py --agent graph_frontier --titles vc33 --max-actions 60000 --out "$D/games/vc33_deep.json" >/dev/null 2>&1
uv run python - > $D/SUMMARY.txt 2>>$D/run.log <<'PY'
import json,glob,os,datetime
def load(pat):
    r={}
    for f in sorted(glob.glob(pat)):
        try: d=json.load(open(f))
        except: continue
        for g in d.get('games',[]):
            t=(g.get('title') or '?').upper()
            acts=[p.get('agent_actions') for p in g.get('per_level',[]) if p.get('agent_actions')]
            r[t]=(g.get('game_score',0), g.get('levels_completed',0), acts)
    return r
new=load('scripts/rounds/R42/games/*_new.json'); q=load('scripts/rounds/R42/games/*_q.json'); dp=load('scripts/rounds/R42/games/*_deep.json')
ts=datetime.datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')
print(f"[generated {ts}] R42 verdict — adaptive pool-downshift fix")
nc=[t for t in new if new[t][1]>0]
print(f"--- 잔여 10게임 @8k: {len(nc)} clear: {', '.join(sorted(nc))} ---")
for t in sorted(new): print(f"  {t}: lvl={new[t][1]} score={new[t][0]:.4f} act={new[t][2]}")
print(f"--- no-loss quick 11게임 @3k: {sum(1 for v in q.values() if v[1]>0)}/11 clear ---")
for t in sorted(q):
    if q[t][1]==0: print(f"  ! {t}: LOST (was clearing)") 
print(f"--- deep: CD82 lvl={dp.get('CD82',(0,0))[1]} (need 2), VC33 lvl={dp.get('VC33',(0,0))[1]} (need 3) ---")
PY
echo "[R42] DONE $(date '+%Y-%m-%d %H:%M:%S %Z')" >> $D/run.log
