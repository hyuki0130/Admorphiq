#!/usr/bin/env bash
# Gate ONE tool change on the full 25, on ceph-build, with every trap this round paid for.
#
# The parent ran this by hand about fifteen times on 2026-08-27 and hit THREE separate
# contaminations doing it. Each one is now a refusal here rather than a habit:
#
#   1. A commit carried an agent's edit. `git add` named explicit paths and registry.py was one
#      of them — naming paths is no protection when the named path is the one file both the
#      parent and the agents write. The committed tree disagreed with every measurement in the
#      round for two hours. -> this script DIFFS registry.py and makes you look.
#   2. The BOX kept a reverted experiment. A targeted `tar czf … one_file.py` outlives the
#      reason for it, so the next gate ran against a file the repository no longer had. The tell
#      was that the new round's regressions matched the reverted experiment's to four decimals.
#      -> this script syncs the WHOLE tree, every time.
#   3. A failed round's result files were SKIPPED on every relaunch, because skipping games that
#      already have a result is how a killed round resumes. The gate then compared the same
#      garbage twice and reported all twenty-five games regressed. -> this script deletes and
#      VERIFIES the delete, and refuses if any game log carries ERROR.
#
# Usage:  bash scripts/rounds/gate_tool.sh <ROUND_NAME> <BASELINE_ROUND_DIR> [UNTOUCHED_GAME]
#   e.g.  bash scripts/rounds/gate_tool.sh R101XY scripts/rounds/R101DC vc33
set -uo pipefail
cd "$(dirname "$0")/../.."

NAME="${1:?round name, e.g. R101XY}"
BASE="${2:?baseline round dir, e.g. scripts/rounds/R101DC}"
CANARY="${3:-vc33}"
OUT="scripts/rounds/$NAME"
REMOTE="ubuntu@ceph-build"
KEY="$HOME/VM/keys/nfw-dev.pem"
SSH=(ssh -o ConnectTimeout=20 -i "$KEY" "$REMOTE")

echo "=== 1. the registry diff — LOOK AT IT. Anything here you did not write is an agent's."
git diff --stat src/admorphiq/harness/registry.py || true
git diff src/admorphiq/harness/registry.py | grep '^[+-]' | grep -v '^[+-][+-]' || echo "  (no registry change)"

echo "=== 2. the tools load, and the ordering invariant still holds"
uv run python -c "
import sys; sys.path.insert(0,'src')
from admorphiq.harness.registry import default_tools
print(' ', len(default_tools()), 'tools load')" || exit 1
uv run pytest tests/test_registry_ordering.py -q 2>&1 | tail -1

echo "=== 3. the canary — a game this change must NOT touch"
uv run python scripts/harness_probe.py "$CANARY" 800 2>&1 | grep "HARNESS:" || true
echo "    ^ compare against the baseline round's number for $CANARY before continuing."

echo "=== 4. sync the WHOLE tree (never one file — see trap 2)"
tar czf /tmp/gate_sync.tgz --exclude=.venv --exclude=.git --exclude='__pycache__' \
    src scripts tests notebooks pyproject.toml uv.lock environment_files ARC-AGI-3-Agents 2>/dev/null
scp -q -i "$KEY" /tmp/gate_sync.tgz "$REMOTE:~/" || exit 1

echo "=== 5. run, on a directory proven empty first (see trap 3)"
"${SSH[@]}" "export PATH=\$HOME/.local/bin:\$PATH; cd ~/admorphiq && tar xzf ~/gate_sync.tgz 2>/dev/null
  rm -rf $OUT/games && mkdir -p $OUT/games
  left=\$(ls $OUT/games 2>/dev/null | wc -l); [ \"\$left\" -eq 0 ] || { echo 'REFUSING: stale results survive'; exit 1; }
  sed 's#OUT=scripts/rounds/R101BASE#OUT=$OUT#' scripts/rounds/R101BASE/run.sh > $OUT/run.sh
  uv run python -c \"import sys;sys.path.insert(0,'src');from admorphiq.harness.registry import default_tools;print(len(default_tools()),'tools OK on the box')\" || exit 1
  nohup env PAR=20 BUDGET=4000 bash $OUT/run.sh > $OUT/run.log 2>&1 &
  sleep 8; echo launched" || exit 1

echo "=== 6. wait"
while [ "$("${SSH[@]}" "ls ~/admorphiq/$OUT/games/*.json 2>/dev/null | wc -l" 2>/dev/null | tr -d ' ')" != "25" ]; do sleep 30; done

echo "=== 7. an ERROR in any game log means a broken environment, not a tool regression"
bad=$("${SSH[@]}" "grep -l ERROR ~/admorphiq/$OUT/games/*.log 2>/dev/null | wc -l" | tr -d ' ')
if [ "$bad" != "0" ]; then
  echo "⛔ $bad game(s) logged ERROR — all-25-at-zero is the signature of a broken environment."
  "${SSH[@]}" "grep -h ERROR ~/admorphiq/$OUT/games/*.log | head -3"
  exit 1
fi

mkdir -p "$OUT/games" && rm -f "$OUT/games"/*.json
scp -q -i "$KEY" "$REMOTE:~/admorphiq/$OUT/games/*.json" "$OUT/games/" || exit 1
echo "=== 8. verdict"
uv run python scripts/rounds/compare.py "$OUT" "$BASE"
