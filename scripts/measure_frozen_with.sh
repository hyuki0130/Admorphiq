#!/usr/bin/env bash
# Frozen measurement with ONE file substituted from a git revision, into the SNAPSHOT only.
#
# ⛔ The live tree is never written. This exists because answering "does revision X of this tool
# score Y" by `git checkout`-ing the file takes another agent's uncommitted work out from under
# them mid-edit — a near-miss that happened today. Substituting into the copy answers the same
# question and cannot destroy anything.
#
# Usage: measure_frozen_with.sh <git-rev> <repo-relative-file> -- <score_efficiency args...>
set -euo pipefail
cd "$(dirname "$0")/.."
REV="$1"; FILE="$2"; shift 2; [ "${1:-}" = "--" ] && shift
SNAP="${TMPDIR:-/tmp}/frozensub_$$"
mkdir -p "$SNAP"; cp -R src "$SNAP/src"; trap 'rm -rf "$SNAP"' EXIT
git show "$REV:$FILE" > "$SNAP/$FILE"
FP=$(cd "$SNAP" && find src/admorphiq/tools src/admorphiq/harness -name '*.py' \
       | sort | xargs shasum -a1 | shasum -a1 | cut -c1-12)
echo "[frozen-sub] $FILE replaced with $REV ($(git show "$REV:$FILE" | shasum -a1 | cut -c1-12))"
echo "[frozen-sub] tools+harness fingerprint: $FP"
PYTHONPATH="$SNAP/src" uv run python scripts/score_efficiency.py "$@"
echo "[frozen-sub] the number above is of fingerprint $FP"
