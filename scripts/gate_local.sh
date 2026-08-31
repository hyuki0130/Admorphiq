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
# ⛔ NORMALISE THE PATH OR THE SHADOW CHECK LIES. `TMPDIR` on macOS ends in a slash, so mktemp
# returns `/var/folders/.../T//gate_x` while Python resolves the same file to a single-slash path —
# and the `startswith` test below then reports SHADOWED on a perfectly good snapshot. Measured
# 2026-08-31 on the first real run. ⚠️ It failed CLOSED (refused instead of passing), which is the
# right direction for a guard to be wrong in, and it was still wrong.
SNAP="$(cd "$SNAP" && pwd -P)"
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

# ⛔ REFUSE ON A MACHINE SOMEONE ELSE IS USING. Measured 2026-08-31 on the replacement host
# (8-core M2): load was 38 before we started anything, and the cause was several `clang` processes
# from another person's build. Adding a 25-game gate to that is the load-110 incident on ceph-build
# repeated on a machine one eighth the size. ⚠️ The threshold is the CORE COUNT: above it the box is
# already oversubscribed and our work would be queueing behind someone else's.
CORES=$(sysctl -n hw.ncpu 2>/dev/null || nproc 2>/dev/null || echo 8)
LOAD1=$(uptime | sed 's/.*averages*: *//' | awk '{print int($1)}')
if [ "${LOAD1:-0}" -gt "$CORES" ]; then
  echo "⛔ REFUSING: load is $LOAD1 on $CORES cores — this machine is already oversubscribed."
  echo "   Someone else's work is queued here; a gate added to it will be slow AND will make the"
  echo "   machine unusable, which is how a gate gets killed half-finished. Check with 'top -o cpu'."
  echo "   Override with FORCE_LOADED_GATE=1 if you know the load is yours and finishing."
  [ "${FORCE_LOADED_GATE:-0}" = "1" ] || exit 1
  echo "⚠️  FORCE_LOADED_GATE=1 — proceeding on a loaded machine anyway."
fi

COMMIT=$(git rev-parse --short HEAD)
echo "=== gating $COMMIT out of $SNAP (par $PAR, budget $BUDGET, agent $AGENT)"
# ⛔ VERIFY THE SNAPSHOT BY COUNTING, NOT BY TRUSTING tar's EXIT. macOS bsdtar prints
# "scripts/rounds/.gitignore: Failed to restore metadata: File exists" and then "Error exit delayed"
# while extracting every file correctly — so the exit code is useless in both directions here.
# ⚠️ The tempting fix is `|| true`, which is the fail-open shape this repository has paid for four
# times: it would also swallow a genuinely empty extraction. Count the files instead.
git archive --format=tar HEAD src scripts | tar x -C "$SNAP" 2>/dev/null
got=$(find "$SNAP/src" "$SNAP/scripts" -type f -name '*.py' 2>/dev/null | wc -l | tr -d ' ')
want=$(git ls-files 'src/*.py' 'scripts/*.py' 'scripts/**/*.py' 2>/dev/null | wc -l | tr -d ' ')
if [ "$got" -lt 100 ] || [ "$got" -lt $(( want / 2 )) ]; then
  echo "⛔ the snapshot extracted only $got python files (HEAD tracks about $want) — refusing to gate"
  exit 1
fi
echo "    snapshot: $got python files"

# ⛔ cwd must CONTAIN environment_files: `score_efficiency.py` reads neither ENVIRONMENTS_DIR nor
# passes environments_dir=, so it finds the games by a cwd-relative default. Measured on a foreign
# cwd: unset = 0 games scored while everything looks healthy. Link, never copy — and link the
# ORIGINALS read-only in spirit: a gate must not be able to edit the corpus (rule 7bu).
for d in environment_files environment_files_archive data ARC-AGI-3-Agents; do
  [ -e "$d" ] && ln -s "$PWD/$d" "$SNAP/$d"
done
# ⛔ LINK THE VENV AND CALL ITS INTERPRETER DIRECTLY — `uv run` inside the snapshot BUILDS A FRESH
# ENVIRONMENT, because the archive carries only src+scripts and no pyproject.toml. `snapgate.sh`
# already documents this exact trap ("reported 25 missing games") and I did not copy it across:
# every one of the 25 runs died on `ModuleNotFoundError: No module named 'arc_agi'`.
# ⚠️ The venv is read-only here; the code being measured is still the snapshot's, because
# `score_efficiency.py:35` inserts the runner's own repo `src` at sys.path[0].
[ -d .venv ] || { echo "⛔ no .venv — run 'uv sync' first"; exit 1; }
ln -s "$PWD/.venv" "$SNAP/.venv"

# ⛔ Prove the snapshot's code is the code that runs. `score_efficiency.py:35` inserts its own repo's
# `src` at sys.path[0], but an editable install elsewhere can still win — that shadowing is what made
# `ptest.sh` measure a stale tree while reporting success. REFUSE rather than report such a number.
( cd "$SNAP" && PYTHONPATH="$SNAP/src" .venv/bin/python -c "
import admorphiq, sys
p = admorphiq.__file__
sys.exit(0 if p.startswith('$SNAP/') else print('SHADOWED', p) or 1)
" ) || { echo "⛔ the snapshot is shadowed by an install elsewhere — refusing to gate"; exit 1; }

mkdir -p "$SNAP/out"
# ⛔ RELATIVE PATHS AND AN EXPORTED PYTHONPATH. The absolute snapshot path appears four times per
# invocation, and on macOS `$TMPDIR` is long enough that `xargs` refused outright with "command line
# cannot be assembled, too long" — producing zero results. ⭐ The no-verdict guard below caught that
# ("only 0 of 25"), which is the whole reason it exists.
( cd "$SNAP" && export PYTHONPATH="$SNAP/src" && ls environment_files | xargs -P "$PAR" -I{} sh -c \
    ".venv/bin/python scripts/score_efficiency.py --agent $AGENT --titles {} \
       --max-actions $BUDGET --out out/{}.json > out/{}.log 2>&1" )

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
