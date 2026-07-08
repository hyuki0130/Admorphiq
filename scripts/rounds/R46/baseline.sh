#!/usr/bin/env bash
# R46 BEFORE baseline: goal_rank OFF (current default). Semantic-candidate group @30000.
set -u
cd "$(dirname "$0")/../../.."
OUT=scripts/rounds/R46/games
for g in ka59 sb26 s5i5 su15 g50t sc25 dc22 re86 wa30; do
  echo "=== BEFORE $g @30000 $(date '+%H:%M:%S') ==="
  GF_GIVEUP=30000 uv run python scripts/score_efficiency.py --agent graph_frontier \
    --titles "$g" --max-actions 30000 --out "$OUT/before_$g.json" 2>/dev/null \
    | grep -E "levels=|Total"
done
echo "BASELINE DONE $(date '+%H:%M:%S')"
