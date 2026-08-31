#!/usr/bin/env bash
# Re-measure the SHIPPED wrapper against the current card, and say plainly whether it drifted.
#
# ⛔ WHY THIS IS A SCRIPT AND NOT A NOTE. The card is measured with `--agent unified` (the bench
# member) while the notebook ships `KaggleUnifiedAgent` (`--agent kaggle_unified`). They are supposed
# to be the same thing — the wrapper MIRRORS `_make_agent("unified")` line for line — and a mirror
# drifts. Five research commits once shipped in the deployed fallback unmeasured while the hidden
# score moved 0.20 -> 0.18 with NO attributable cause. CLAUDE.md has carried "measure the card AS
# SHIPPED" ever since, and for days the gate could not even take an agent argument (rule 7bv).
#
# ⚠️ AND THE CURRENT NUMBERS DISAGREE RIGHT NOW: the bench path is 0.9135 after crag's gain
# (scripts/rounds/R101CRAGONLY) and the last shipped measurement is 0.9082, taken BEFORE it. `crag`
# is in the shipped path, so it SHOULD be 0.9135 — but that is an inference, and this file exists
# because inferences about the wrapper have been wrong before.
#
#   bash scripts/remeasure_shipped.sh            # default: PAR 2, budget 4000, vs R101CRAGONLY
#   bash scripts/remeasure_shipped.sh 12         # on a real box
set -uo pipefail
cd "$(dirname "$0")/.."

PAR="${1:-2}"
BUDGET="${2:-4000}"
BASE="${3:-scripts/rounds/R101CRAGONLY}"
NAME="shipped$(date +%m%d%H%M)"

[ -d "$BASE/games" ] || { echo "⛔ baseline $BASE/games not found"; exit 1; }
echo "=== re-measuring the SHIPPED wrapper (kaggle_unified) against $BASE"
echo "    expect: the same mean, ZERO games differing. Anything else is DRIFT and is the finding."
echo

AGENT=kaggle_unified bash scripts/gate_local.sh "$NAME" "$BASE" "$PAR" "$BUDGET"
rc=$?

echo
if [ "$rc" -ne 0 ]; then
  echo "⛔ the run did not produce a verdict — read the message above. NOT a drift result."
  exit "$rc"
fi
echo "⭐ If that said 'no game regressed' with no rows, the wrapper still mirrors the bench member."
echo "⛔ If any game differs, the wrapper has DRIFTED: diff src/admorphiq/kaggle_unified_agent.py"
echo "   against _make_agent(\"unified\") in scripts/score_efficiency.py before anything else."
