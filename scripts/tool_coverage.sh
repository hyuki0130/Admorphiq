#!/bin/bash
# Direct-probe a given tool across all 25 games, PAR at a time.
# Usage: tool_coverage.sh <toolname> [budget]
cd ~/admorphiq
TOOL=${1:-graph}
BUDGET=${2:-3000}
GAMES="ar25 bp35 cd82 cn04 dc22 ft09 g50t ka59 lf52 lp85 ls20 m0r0 r11l re86 s5i5 sb26 sc25 sk48 sp80 su15 tn36 tr87 tu93 vc33 wa30"
PAR=1
rm -f ~/cov_${TOOL}_*.out
run_one() {
  ~/.local/bin/uv run python scripts/probe_tool_direct.py --tool "$2" --game "$1" --budget "$3" 2>/dev/null | grep TOOL= > ~/cov_${2}_$1.out
}
export -f run_one
n=0
for g in $GAMES; do
  run_one "$g" "$TOOL" "$BUDGET" &
  n=$((n+1)); [ $((n % PAR)) -eq 0 ] && wait
done
wait
echo "=== ${TOOL} COVERAGE (25 games, budget ${BUDGET}) ==="
tot=0
for g in $GAMES; do
  lv=$(grep -oE 'levels=[0-9]+' ~/cov_${TOOL}_$g.out 2>/dev/null | cut -d= -f2)
  lv=${lv:-ERR}
  echo "$g: $lv"
  [ "$lv" != "ERR" ] && [ "$lv" -gt 0 ] 2>/dev/null && tot=$((tot+1))
done
echo "${TOOL}_GAMES_CLEARED=$tot / 25"
