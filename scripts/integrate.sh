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
# ⛔ IT USED TO CALL `scripts/rounds/gate_tool.sh`, WHICH RULE 7l FORBIDS — that script syncs the
# SHARED `~/admorphiq`, so its verdict carries every agent's work-in-progress and the tree can move
# under it. Both of its own documented traps are that one cause. It now calls `snapgate.sh`, which
# archives HEAD into a private directory on the box: two gates run at once and a rider cannot ride.
#
# ⚠️ Found 2026-08-30 by auditing which scripts were still referenced by anything — this one had been
# left pointing at the superseded gate for a full day while the rules said not to use it. A wrapper
# is a place a superseded call hides.
set -u
cd "$(dirname "$0")/.."
GAME="${1:?game, e.g. dc22}"
TOOL="${2:?the tool whose source changed, e.g. gantry}"
BASE="${3:-scripts/rounds/R101REACH}"
KEY="$HOME/VM/keys/nfw-dev.pem"
REMOTE="ubuntu@ceph-build"

# ⚠️ No longer refuses on a busy box: `snapgate.sh` runs from a private snapshot, so two gates and a
# peer's fan coexist (verified 2026-08-29 alongside a 50-run A/B). Load is still worth a glance.

# ⛔ THE CHANGE MUST BE COMMITTED. `snapgate.sh` archives HEAD, which is the whole point of rule 7l:
# a peer's uncommitted edit cannot ride into the verdict, and the verdict names a COMMIT rather than
# a working directory. An uncommitted change is simply invisible to it.
if ! git diff --quiet HEAD -- src/; then
  echo "⚠️  src/ has UNCOMMITTED edits — the gate archives HEAD, so these are EXCLUDED:"
  git diff --name-only HEAD -- src/ | sed 's/^/      /'
  echo "    Commit yours first (stage and commit in ONE step — rule 7w)."
fi
echo "=== src/ commits since the baseline"
git log --oneline -3 -- src/ | sed 's/^/    /'

echo "=== gating $GAME against $BASE"
bash scripts/snapgate.sh "$GAME" "$BASE" | tail -20

echo
echo "⛔ KEEP only if the mean ROSE. If it did not:  git checkout src/"
echo "   Then record the measurement in .wiki/wiki/sample_games_mechanics.md — a measured negative"
echo "   is the point, and fifteen of them are why cumulative regressions are still zero."
