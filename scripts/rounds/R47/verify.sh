#!/bin/zsh
cd /Users/nhn/Workspace/Admorphiq
D=scripts/rounds/R47
# SC25 with knob ON — 2/2 reproduction
for t in 1 2; do
  GF_MEASURE_EXPAND=1 GF_GIVEUP=30000 uv run python scripts/score_efficiency.py --agent graph_frontier --titles sc25 --max-actions 30000 --out "$D/games/sc25_on_t${t}.json" >/dev/null 2>&1
done
# KA59 both ways
GF_GIVEUP=30000 uv run python scripts/score_efficiency.py --agent graph_frontier --titles ka59 --max-actions 30000 --out "$D/games/ka59_off.json" >/dev/null 2>&1
GF_MEASURE_EXPAND=1 GF_GIVEUP=30000 uv run python scripts/score_efficiency.py --agent graph_frontier --titles ka59 --max-actions 30000 --out "$D/games/ka59_on.json" >/dev/null 2>&1
# no-loss with default OFF
GF_GIVEUP=30000 uv run python scripts/score_efficiency.py --agent graph_frontier --titles tu93 --max-actions 30000 --out "$D/games/tu93_def.json" >/dev/null 2>&1
uv run python - > $D/VERIFY.txt 2>/dev/null <<'PY'
import json,glob,os,datetime
ts=datetime.datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')
print(f"[generated {ts}] R47 independent verification")
for f in sorted(glob.glob('scripts/rounds/R47/games/*.json')):
    d=json.load(open(f)); g=d['games'][0]
    acts=[p.get('agent_actions') for p in g.get('per_level',[]) if p.get('agent_actions')]
    print(f"  {os.path.basename(f)[:-5]}: lvl={g['levels_completed']} act={acts}")
PY
