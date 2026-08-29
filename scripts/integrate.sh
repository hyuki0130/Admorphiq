#!/usr/bin/env bash
# Integrate ONE agent's change: verify the tree, gate it on the full 25, keep or revert. One command.
#
# ⛔ WHY. Fifteen repairs were built today and every one had to be gated by hand — assembling the
# command, remembering the baseline, remembering that a gate re-syncs the tree and must not overlap
# another, and remembering that a change which does not RAISE the mean gets reverted. That is four
# things to recall at the exact moment attention is on the result instead of the procedure, and it
# was got wrong twice.
#
#   bash scripts/integrate.sh dc22 gantry        # gate the working tree's change to gantry
#
# Refuses if another gate or a sweep is already running on the box (rule 7i: a gate re-syncs, so two
# at once measure each other's bytes).
set -u
cd "$(dirname "$0")/.."
GAME="${1:?game, e.g. dc22}"
TOOL="${2:?the tool whose source changed, e.g. gantry}"
BASE="${3:-scripts/rounds/R101REACH}"
KEY="$HOME/VM/keys/nfw-dev.pem"
REMOTE="ubuntu@ceph-build"

BUSY=$(ssh -o ConnectTimeout=10 -i "$KEY" "$REMOTE" 'pgrep -fc "score_efficiency" || true' 2>/dev/null)
if [ "${BUSY:-0}" -gt 4 ]; then
  echo "⛔ REFUSING: $BUSY scoring processes already on the box. A gate re-syncs the tree, so it"
  echo "   would change the source under whatever is measuring. Wait, then re-run."
  exit 1
fi

if git diff --quiet -- src/; then
  echo "⛔ REFUSING: no change in src/. There is nothing to gate."
  exit 1
fi
echo "=== changed files"
git diff --name-only -- src/ | sed 's/^/    /'

NAME="R101$(echo "$GAME" | tr 'a-z' 'A-Z')"
echo "=== gating $NAME against $BASE (canary vc33, tool $TOOL)"
bash scripts/rounds/gate_tool.sh "$NAME" "$BASE" vc33 "$TOOL" | tail -20

echo
echo "⛔ KEEP only if the mean ROSE. If it did not:  git checkout src/"
echo "   Then record the measurement in .wiki/wiki/sample_games_mechanics.md — a measured negative"
echo "   is the point, and fifteen of them are why cumulative regressions are still zero."
