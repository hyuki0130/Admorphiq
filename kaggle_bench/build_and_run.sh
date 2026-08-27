#!/bin/bash
# Build and RUN the R101 LLM bench kernel. This never touches the leaderboard.
#
# ⛔ This is NOT a submission. `kaggle kernels push` runs a notebook server-side without
# consuming the daily submission slot, and the standing directive is that nothing is
# submitted until the sample games are cleared. There is deliberately no --submit path
# in this script: the submission build is kaggle/build_and_push.sh and only that one.
#
# What the kernel measures: the generic tool set routed by an OFFLINE MODEL over all 25
# sample games, against the LLM-FREE fallback in a matched arm. Every R101 number so far
# came from the fallback, because ceph-build has no GPU.
#
# WHERE EACH INPUT COMES FROM (recovered by reading the R98 kernels that actually ran,
# not guessed — the recipe cost a campaign to establish):
#   * the 25 games          competition mount, environment_files/<game>/<hash>/
#   * the official framework competition mount, ARC-AGI-3-Agents/ (its absence scores
#                            0.0000 on all 25 and reads exactly like a broken agent)
#   * vLLM + arc wheels     kernel_sources philipvonderlind/vllm-deps (internet is off)
#   * the model             model_sources, FULL instance path owner/slug/Framework/var/ver
#   * our source + runner   the admorphiq-bench dataset this script uploads
set -euo pipefail
cd "$(dirname "$0")/.."

COMMIT=$(git rev-parse --short HEAD)
STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT

# The package must arrive as a real directory, so `--dir-mode zip` — the DEFAULT is `skip`,
# which ignores directories and once produced an EMPTY dataset and a ModuleNotFoundError.
# zip strips the top level, hence staging under src/.
# ⛔ `git archive`, NOT `cp -R`. MEASURED 2026-08-27: `cp -R` copies the WORKING TREE, so a
# background agent's half-finished tool shipped in the dataset and the kernel measured a tree
# that exists in no commit — g50t came back at 0.7500 where the committed tree measures 0.5357.
# A kernel run costs a GPU session; it must measure a COMMIT or it is not attributable. This is
# the same moving-target trap that cost a full-25 run twice today, reached from a third
# direction.
mkdir -p "$STAGE/src" "$STAGE/scripts"
git archive HEAD src/admorphiq | tar -x -C "$STAGE" --strip-components=1
mkdir -p "$STAGE/src" && mv "$STAGE/admorphiq" "$STAGE/src/" 2>/dev/null || true
git archive HEAD scripts/score_efficiency.py | tar -x -C "$STAGE"
find "$STAGE" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
echo "$COMMIT" > "$STAGE/COMMIT.txt"
cat > "$STAGE/dataset-metadata.json" <<JSON
{"title": "admorphiq-bench", "id": "jaehyukhyun/admorphiq-bench", "licenses": [{"name": "CC0-1.0"}]}
JSON

if uv run kaggle datasets status jaehyukhyun/admorphiq-bench >/dev/null 2>&1; then
  uv run kaggle datasets version -p "$STAGE" -d --dir-mode zip -m "admorphiq bench @ $COMMIT"
else
  uv run kaggle datasets create -p "$STAGE" --dir-mode zip
fi

# WAIT for the version to be SERVED. `datasets version` returns before the new files are,
# and a kernel pushed too early silently runs stale code — measured twice in R98. Poll for
# THIS commit's own stamp; polling for any file passes instantly and guards nothing.
echo "waiting for the dataset version to be served…"
served=""
for _ in $(seq 1 90); do
  uv run kaggle datasets download jaehyukhyun/admorphiq-bench -f COMMIT.txt \
      -p "$STAGE/check" --force --quiet >/dev/null 2>&1 || true
  stamp=$(tr -d '[:space:]' < "$STAGE/check/COMMIT.txt" 2>/dev/null || true)
  if [ "$stamp" = "$COMMIT" ]; then served=yes; break; fi
  sleep 20
done
if [ -z "$served" ]; then
  echo "ERROR: the dataset never served commit $COMMIT — refusing to push against stale code." >&2
  exit 1
fi

cp notebooks/r101_llm_full25.py kaggle_bench/r101_llm_full25.py
uv run kaggle kernels push -p kaggle_bench
echo "bench kernel pushed at commit $COMMIT — watch with:"
echo "  uv run kaggle kernels status jaehyukhyun/admorphiq-r101-llm-full25"
echo "  uv run kaggle kernels output jaehyukhyun/admorphiq-r101-llm-full25 -p /tmp/r101out"
