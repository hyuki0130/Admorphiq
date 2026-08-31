#!/usr/bin/env bash
# Gate a change on the full 25 WITHOUT a remote box. Same guards as `snapgate.sh`, one machine.
#
# ⛔ WHY THIS EXISTS. `ceph-build` was deleted on 2026-08-31 and `snapgate.sh` cannot run without a
# 64-core host. Every gated number in this repository came from that box, and with it gone there was
# no way to gate anything at all — which would have frozen the campaign at "0.9082, unverifiable".
# This is the single-machine fallback, and it keeps every refusal that made the remote gate
# trustworthy, because those refusals are the reason a gate means something.
#
#   bash scripts/gate_local.sh NAME [baseline] [par] [budget]
#   bash scripts/gate_local.sh cragwip scripts/rounds/R101SHIPPED 4 4000
#   AGENT=kaggle_unified bash scripts/gate_local.sh shipped scripts/rounds/R101SHIPPED
#
# ⚠️ PAR DEFAULTS TO 4, NOT 8, AND THAT IS DELIBERATE. The machine that runs this is now also the
# editor. Three concurrent pytest suites once made the previous laptop unusable and the user asked
# twice for it to stop (rule 7m) — a gate that makes the only machine unusable will be killed
# half-finished, and a half-finished gate is worse than none (it produces a mean over a subset).
# On an 8-core M2, ft09 alone scores in ~3.4s; the full 25 at PAR 4 is minutes, not hours.
set -uo pipefail
cd "$(dirname "$0")/.."

NAME="${1:?a name for this gate, e.g. cragwip}"
BASE="${2:-scripts/rounds/R101SHIPPED}"
PAR="${3:-4}"
BUDGET="${4:-4000}"
AGENT="${AGENT:-unified}"
OUT="scripts/rounds/R101$(echo "$NAME" | tr 'a-z' 'A-Z')"
SNAP="$(mktemp -d "${TMPDIR:-/tmp}/gate_${NAME}.XXXXXX")"
trap 'rm -rf "$SNAP"' EXIT

[ -d "$BASE/games" ] || { echo "⛔ baseline $BASE/games not found"; exit 1; }
if [ -d "$OUT/games" ] && [ -n "$(ls -A "$OUT/games" 2>/dev/null)" ]; then
  echo "⛔ REFUSING: $OUT/games already holds $(ls "$OUT/games" | wc -l | tr -d ' ') files."
  echo "   A gate must not mix its results with another experiment's. Pick an unused name."
  exit 1
fi
if ! git diff --quiet HEAD -- src/; then
  echo "⚠️  src/ has UNCOMMITTED edits, EXCLUDED from this gate (it archives HEAD):"
  git diff --name-only HEAD -- src/ | sed 's/^/      /'
fi

COMMIT=$(git rev-parse --short HEAD)
echo "=== gating $COMMIT out of $SNAP (par $PAR, budget $BUDGET, agent $AGENT)"
git archive --format=tar HEAD src scripts | tar x -C "$SNAP"

# ⛔ cwd must CONTAIN environment_files: `score_efficiency.py` reads neither ENVIRONMENTS_DIR nor
# passes environments_dir=, so it finds the games by a cwd-relative default. Measured on a foreign
# cwd: unset = 0 games scored while everything looks healthy. Link, never copy — and link the
# ORIGINALS read-only in spirit: a gate must not be able to edit the corpus (rule 7bu).
for d in environment_files environment_files_archive data ARC-AGI-3-Agents; do
  [ -e "$d" ] && ln -s "$PWD/$d" "$SNAP/$d"
done

# ⛔ Prove the snapshot's code is the code that runs. `score_efficiency.py:35` inserts its own repo's
# `src` at sys.path[0], but an editable install elsewhere can still win — that shadowing is what made
# `ptest.sh` measure a stale tree while reporting success. REFUSE rather than report such a number.
( cd "$SNAP" && PYTHONPATH="$SNAP/src" uv run python -c "
import admorphiq, sys
p = admorphiq.__file__
sys.exit(0 if p.startswith('$SNAP/') else print('SHADOWED', p) or 1)
" ) || { echo "⛔ the snapshot is shadowed by an install elsewhere — refusing to gate"; exit 1; }

mkdir -p "$SNAP/out"
( cd "$SNAP" && ls environment_files | xargs -P "$PAR" -I{} sh -c \
    "PYTHONPATH='$SNAP/src' uv run python '$SNAP/scripts/score_efficiency.py' --agent '$AGENT' \
       --titles {} --max-actions $BUDGET --out '$SNAP/out/{}.json' > '$SNAP/out/{}.log' 2>&1" )

n=$(ls "$SNAP"/out/*.json 2>/dev/null | wc -l | tr -d ' ')
echo "GATEDONE $n games"
# ⛔ A GATE THAT PRODUCED NOTHING MUST NOT REACH THE COMPARATOR. Measured 2026-08-29: 25 runs all
# died on an import and `compare.py` printed every row "(missing)" then "no game regressed" — a PASS
# over zero evidence. And 2026-08-30: a killed gate's 4 surviving results were reported as
# "MEAN new = 1.0000 over 4". Refuse here, not downstream.
[ "$n" -ge 25 ] || { echo "⛔ only $n of 25 produced a result — see $SNAP/out/*.log"; cp -r "$SNAP/out" "/tmp/gate_${NAME}_failed" 2>/dev/null; echo "   logs kept at /tmp/gate_${NAME}_failed"; exit 1; }

mkdir -p "$OUT/games"
cp "$SNAP"/out/*.json "$OUT/games/"
echo "$COMMIT" > "$OUT/COMMIT"
uv run python scripts/rounds/compare.py "$OUT" "$BASE"
