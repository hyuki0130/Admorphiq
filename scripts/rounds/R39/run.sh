#!/bin/zsh
cd /Users/nhn/Workspace/Admorphiq
D=scripts/rounds/R39; : > $D/run.log
for g in ft09 m0r0 cd82 r11l sp80 lp85 tn36 vc33 cn04; do
  GF_GIVEUP=30000 uv run python scripts/score_efficiency.py --agent graph_frontier --titles "$g" --max-actions 30000 --out "$D/games/${g}_deep.json" >/dev/null 2>&1
  echo "[R39] $g deep $(date '+%H:%M:%S')" >> $D/run.log
done
for g in ft09 m0r0 bp35 cd82 cn04 ls20 r11l s5i5 sp80; do
  uv run python scripts/score_efficiency.py --agent graph_frontier --titles "$g" --max-actions 3000 --out "$D/games/${g}_quick.json" >/dev/null 2>&1
done
uv run python - > $D/SUMMARY.txt 2>>$D/run.log <<'PY'
import json,glob
deep={}; quick={}
for f in sorted(glob.glob('scripts/rounds/R39/games/*_deep.json')):
    d=json.load(open(f))
    for g in d.get('games',[]):
        t=(g.get('title') or '?').upper()
        acts=[p.get('agent_actions') for p in g.get('per_level',[]) if p.get('agent_actions')]
        deep[t]=(g.get('game_score',0), g.get('levels_completed',0), acts)
for f in sorted(glob.glob('scripts/rounds/R39/games/*_quick.json')):
    d=json.load(open(f))
    for g in d.get('games',[]):
        quick[(g.get('title') or '?').upper()]=(g.get('game_score',0), g.get('levels_completed',0))
print("R39 sticky-mask+area-cap 판정 (vs R38: mean 0.0064@8games, CD82/VC33 L2, TN36 145a)")
R38={'CD82':(0.0012,2),'FT09':(0.0,1),'LP85':(0.0,1),'M0R0':(0.0008,1),'R11L':(0.0476,1),'SP80':(0.0001,1),'TN36':(0.0017,1),'VC33':(0.0,2),'CN04':(0.0,0)}
sc=[v[0] for v in deep.values()]
print(f"--- DEEP @30k (9 games incl cn04): mean={sum(sc)/max(1,len(sc)):.4f} ---")
for t in sorted(deep):
    o=R38.get(t,(0,0))
    d_=deep[t]
    mark='*' if (d_[1]>o[1] or d_[0]>o[0]+1e-6) else (' ' if d_[1]==o[1] else '!')
    print(f" {mark} {t}: lvl {d_[1]} (was {o[1]})  score {d_[0]:.4f} (was {o[0]:.4f})  act={d_[2]}")
qs=[v[0] for v in quick.values()]; qc=sum(1 for v in quick.values() if v[1]>0)
print(f"--- QUICK 9-subset @3000: mean={sum(qs)/max(1,len(qs)):.4f} clears={qc}/9 (기준 0.0055, 4/9) ---")
PY
echo "[R39] DONE $(date '+%Y-%m-%d %H:%M:%S %Z')" >> $D/run.log
