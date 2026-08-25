#!/bin/bash
# Build and push the submission kernel — the BUILD, committed, because the 0.20 card's was not.
#
# The v3 card that scored 0.20 on 2026-07-14 could not be rebuilt from this repository: no
# kernel-metadata was ever committed, no push command was recorded, and the mapping from the
# Kaggle dataset version to the commit it was built from was written nowhere. Recovering what
# it even contained took a grep of the round pages. This script exists so that never repeats.
#
# Usage:  bash kaggle/build_and_push.sh            # push dataset + kernel, no submission
#         bash kaggle/build_and_push.sh --submit   # also consume the daily submission slot
#
# The user decides submissions. --submit is never passed automatically.
set -euo pipefail
cd "$(dirname "$0")/.."

COMMIT=$(git rev-parse --short HEAD)
STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT

# 1. The source dataset. Ship exactly what the agent imports, and stamp the commit INSIDE it
#    so a future session can map any dataset version back to a tree.
mkdir -p "$STAGE/src"
cp -R src/admorphiq "$STAGE/src/"
find "$STAGE" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
echo "$COMMIT" > "$STAGE/src/COMMIT.txt"
cat > "$STAGE/dataset-metadata.json" <<JSON
{"title": "admorphiq-src", "id": "jaehyukhyun/admorphiq-src", "licenses": [{"name": "CC0-1.0"}]}
JSON
uv run kaggle datasets version -p "$STAGE" -d --dir-mode zip -m "admorphiq src @ $COMMIT"

# 2. WAIT for the version to exist. `datasets version` returns BEFORE the new files are
#    served, and pushing a kernel against the old ones silently runs stale code — measured
#    twice in the R98 campaign. Poll the FILE LISTING by size, never `datasets status`.
echo "waiting for the dataset version to be served…"
for _ in $(seq 1 60); do
  if uv run kaggle datasets files jaehyukhyun/admorphiq-src 2>/dev/null | grep -q 'admorphiq'; then
    break
  fi
  sleep 20
done

# 3. The kernel itself.
cp notebooks/kaggle_submission.py kaggle/kaggle_submission.py
uv run kaggle kernels push -p kaggle
echo "kernel pushed at commit $COMMIT"

if [ "${1:-}" = "--submit" ]; then
  uv run kaggle competitions submit -c arc-prize-2026-arc-agi-3 \
    -k jaehyukhyun/admorphiq-submission \
    -m "detection dispatch over the chained card; public-25 proxy 0.2771 @ $COMMIT"
fi
