#!/usr/bin/env bash
# Measure a FROZEN copy of the tools, never the live tree.
#
# ⛔ WHY THIS EXISTS. On 2026-08-27 the same defect was hit FOUR times in one afternoon, in four
# different disguises, and every one of them was "the code moved while it was being measured":
#
#   * a commit said "BANK the measured tree" for a tool that changed between the sync and the
#     commit, so code that had never been measured was committed as if it had;
#   * a box kept a stale tarball, so five deterministic runs returned 0.7500 for a tool whose
#     current version scores 1.0000 -- deterministic, repeated, and wrong;
#   * `blastclock.py` moved FOUR times inside one hour (ef0dafdf -> d33922ec -> fce28fc4 ->
#     8cc9e8b8) while three parties measured ka59 and compared notes;
#   * an agent reported a hash and a score taken at different moments of the same file.
#
# The cause is structural, not carelessness: agents are told NOT to commit, so their work is
# always live in the shared tree, and any measurement of that tree describes a moment rather
# than an artefact. Repeating the measurement does not help -- it makes the wrong number more
# convincing. The fix is to measure something that CANNOT change: a copy.
#
# Usage:  bash scripts/measure_frozen.sh --agent unified --titles ka59 --max-actions 4000
#         (every argument is passed through to scripts/score_efficiency.py)
set -euo pipefail
cd "$(dirname "$0")/.."

SNAP="${TMPDIR:-/tmp}/frozen_$$"
mkdir -p "$SNAP"
cp -R src "$SNAP/src"
trap 'rm -rf "$SNAP"' EXIT

# The identity of what is about to be measured, printed BEFORE the run so it appears in the log
# next to the number and cannot be attached afterwards from a second reading of the file.
FP=$(cd "$SNAP" && find src/admorphiq/tools src/admorphiq/harness -name '*.py' \
       | sort | xargs shasum -a1 | shasum -a1 | cut -c1-12)
echo "[frozen] tools+harness fingerprint: $FP   (snapshot $SNAP)"
echo "[frozen] git HEAD: $(git rev-parse --short HEAD)   dirty tools: $(git status --porcelain src/admorphiq/tools | wc -l | tr -d ' ')"

PYTHONPATH="$SNAP/src" uv run python scripts/score_efficiency.py "$@"
echo "[frozen] the number above is of fingerprint $FP"
