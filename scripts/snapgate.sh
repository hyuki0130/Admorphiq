#!/usr/bin/env bash
# Gate a change on the full 25 out of a PRIVATE SNAPSHOT — never touching the shared tree.
#
# ⛔ WHY THIS EXISTS. `scripts/rounds/gate_tool.sh` syncs ~/admorphiq on the box, and that is a
# SHARED resource: eight agents edit src/ continuously, so a gate that re-syncs changes the code
# under whoever else is measuring, and its own verdict carries every rider in the tree. Trap 4 and
# trap 5 in that script are both this one cause. The answer is not a lock and not one tree per
# worker — it is that a MEASUREMENT SHOULD NOT WRITE TO A SHARED PATH AT ALL.
#
# The lp85 agent found this independently on 2026-08-29 by A/B-ing two private snapshots while a
# peer's gate was in flight; both measurements stood. This script is that method, made reusable.
#
#   bash scripts/snapgate.sh re86 scripts/rounds/R101REACH
#
# The snapshot is `git archive HEAD` — the COMMITTED tree, so the verdict names a commit and not a
# working directory. Uncommitted edits (a peer mid-change) are excluded BY CONSTRUCTION, which is
# the whole point: a rider can no longer ride.
#
# ⛔ score_efficiency.py:35 is `sys.path.insert(0, Path(__file__).resolve().parent.parent/"src")` —
# it resolves relative to THE RUNNER FILE BEING EXECUTED, not to PYTHONPATH and not to cwd. That is
# why invoking the copy inside the snapshot selects the snapshot's code, and it is why the snapshot
# MUST carry `scripts/` as well as `src/`: snapshotting src alone and running the SHARED runner
# silently measures the shared tree. (`scripts/measure_frozen.sh` learned this one the hard way.)
set -uo pipefail
cd "$(dirname "$0")/.."

NAME="${1:?a name for this gate, e.g. re86}"
BASE="${2:-scripts/rounds/R101REACH}"
PAR="${3:-8}"
BUDGET="${4:-4000}"
# ⛔ THE GATE MUST BE ABLE TO MEASURE THE CONFIGURATION THAT SHIPS. `--agent unified` was hardcoded
# here, so every gate scored the BENCH member while the notebook ships `KaggleUnifiedAgent` — two
# different wrappers, and CLAUDE.md has a standing warning that they are measured separately.
#   AGENT=kaggle_unified bash scripts/snapgate.sh shipped <baseline>
AGENT="${AGENT:-unified}"
# ⛔ ENV THE RUN ACTUALLY NEEDS, PASSED THROUGH. Measured 2026-08-30: in EVERY environment this
# campaign has measured — local gate, shipped wrapper, Kaggle — the harness's LLM target draw has
# never once succeeded (404 on the box for an unpulled model name, connection refused on Kaggle),
# so 0.9082 is tools + signature routing with the LLM contributing exactly zero. Measuring whether
# it would help needs HARNESS_MODEL to reach the remote run, and it had no way to.
#   HARNESS_MODEL=gemma4:26b bash scripts/snapgate.sh llmdraw <baseline> 8 4000
PASSENV=""
for v in HARNESS_MODEL HARNESS_HOST HARNESS_CTX OLLAMA_NUM_THREAD GF_GIVEUP GF_EWM; do
  eval "val=\${$v:-}"
  [ -n "$val" ] && PASSENV="$PASSENV $v=$val"
done
if [ -n "$PASSENV" ]; then echo "=== passing through:$PASSENV"; fi

# ⛔ REFUSE AN LLM ARM ON ceph-build. Measured 2026-08-30, and CLAUDE.md had already written it down:
# one 26B model on this box takes **51.8 seconds for four tokens** and, when the arm was run anyway,
# **3665% CPU — thirty-seven cores** — driving the load average to 110 against a 60-core cap, on a
# SHARED machine whose other tenants were still working. `OLLAMA_NUM_THREAD` did NOT restrain it:
# `ollama_llm` puts it in the request's `options.num_thread`, and the server had already spawned the
# runner with its own defaults. There is no client-side cap to reach for.
#
# The rule existed and I ran the arm regardless, which is exactly the failure mode this campaign
# keeps meeting — a rule DESCRIBES and therefore needs someone to decide; a runner does not.
# An LLM arm needs a GPU. Set FORCE_LLM_ON_CPU_BOX=1 only with a reason you can defend.
case "$PASSENV" in
  *HARNESS_MODEL=*|*HARNESS_LLM_BASE_URL=*)
    if [ "${FORCE_LLM_ON_CPU_BOX:-0}" != "1" ]; then
      echo "⛔ REFUSING: an LLM arm on ceph-build. One 26B model = ~37 cores and 51.8s per four"
      echo "   tokens there; the last attempt put the shared box at load 110 (cap 60) and"
      echo "   OLLAMA_NUM_THREAD does not restrain it. Use a GPU host, or FORCE_LLM_ON_CPU_BOX=1."
      exit 1
    fi
    echo "⚠️  FORCE_LLM_ON_CPU_BOX=1 — running an LLM arm on the shared CPU box anyway."
    ;;
esac
KEY="$HOME/VM/keys/nfw-dev.pem"
REMOTE="ubuntu@ceph-build"
SSH=(ssh -o ConnectTimeout=20 -i "$KEY" "$REMOTE")
SNAP="snap_$NAME"
OUT="scripts/rounds/R101$(echo "$NAME" | tr 'a-z' 'A-Z')"

[ -d "$BASE/games" ] || { echo "⛔ baseline $BASE/games not found"; exit 1; }

if ! git diff --quiet HEAD -- src/; then
  echo "⚠️  src/ has UNCOMMITTED edits. They are EXCLUDED from this gate (it archives HEAD):"
  git diff --name-only HEAD -- src/ | sed 's/^/      /'
  echo "    Commit them first if they are meant to be measured."
fi

# ⛔ RUN THE CHEAP GUARDS BEFORE SPENDING TWENTY MINUTES OF BOX TIME. Measured 2026-08-30: four
# guards were built in one day (a registered-tool check, the detect-purity population, the adapter
# detection contract, the summaries-match-their-data check) and NONE of them ran anywhere
# automatically — not in a hook, not in R98's selfcheck. A guard nobody runs is a finding with an
# expiry date, and this repository has already paid for exactly that (`fogscout` committed but
# unregistered measured like an absent tool, worth +0.0942).
#
# These are seconds and engine-free, and the gate is the one command everyone reaches for.
# ⛔ They go through `ptest.sh` — i.e. ON THE BOX, in a private snapshot — because rule 7m bans
# pytest on the Mac and a PreToolUse hook enforces it. Writing `uv run pytest` here would be blocked
# for whoever ran the gate, which is the shape where a guard teaches people to switch guards off.
if [ "${SKIP_GUARDS:-0}" != "1" ]; then
  if ! bash scripts/ptest.sh --dirty tests/test_every_tool_is_registered.py tests/test_detect_purity.py \
        >/tmp/snapgate_guard.log 2>&1; then
    echo "⛔ GUARDS FAILED before the gate — not spending twenty minutes of box time:"
    tail -14 /tmp/snapgate_guard.log | sed 's/^/    /'
    echo "   Fix it, or re-run with SKIP_GUARDS=1 and record why."
    exit 1
  fi
  echo "=== guards hold (registry, detect-purity)"
fi

COMMIT=$(git rev-parse --short HEAD)
echo "=== gating $COMMIT out of a private snapshot ~/$SNAP (par $PAR, budget $BUDGET)"

# ⛔ SWEEP THE MAC TOO. Rule 7bi put this sweep on the BOX and left the Mac unswept — and on
# 2026-08-30 the Mac's disk hit 100%, at which point Bash could not create its own output file, the
# Stop hook could not create a heredoc, and NO agent on this machine could run a probe, a test or a
# commit. Every gate and every test run leaves a ~5-40MB tarball here and today there were dozens.
# ⚠️ A fix that solves a problem in one place and leaves its twin standing is half a fix.
find /tmp -maxdepth 1 -name "*.tgz" -mmin +30 -delete 2>/dev/null

git archive --format=tar.gz -o "/tmp/$SNAP.tgz" HEAD src scripts
scp -q -i "$KEY" "/tmp/$SNAP.tgz" "$REMOTE:~/" || { echo "⛔ scp failed"; exit 1; }

"${SSH[@]}" bash -s "$SNAP" "$PAR" "$BUDGET" "$AGENT" "$PASSENV" <<'EOS'
set -u
SNAP="$1"; PAR="$2"; BUDGET="$3"; AGENT="$4"; PASSENV="${5:-}"
# `export` each NAME=VALUE the caller forwarded; empty is the common case and a no-op.
for kv in $PASSENV; do export "$kv"; done
export PATH=$HOME/.local/bin:$PATH
cd "$HOME"
# ⛔ Sweep stale snapshots (rule 7d, on the box): ~94MB each, 15GB accumulated by 2026-08-30.
# Two hours untouched means finished; a live fan writes continuously.
find "$HOME" -maxdepth 1 \( -name "pfan_*" -o -name "snap_*" -o -name "*_out" \) -type d -mmin +120 \
     -exec rm -rf {} + 2>/dev/null
rm -rf "$HOME/$SNAP" "$HOME/${SNAP}_out"
mkdir -p "$HOME/$SNAP" "$HOME/${SNAP}_out"
tar xzf "$HOME/$SNAP.tgz" -C "$HOME/$SNAP"
# ⛔ cwd must be a directory CONTAINING environment_files: score_efficiency.py never reads
# ENVIRONMENTS_DIR and never passes environments_dir= to the Arcade, so the Arcade falls back to a
# cwd-relative default. Copy the games INTO the snapshot and cd there, so the gate does not depend
# on what the shared tree's environment_files becomes mid-run. (The lp85 agent's A/B left this as
# its one remaining shared dependency and said so; this closes it.)
cp -r "$HOME/admorphiq/environment_files" "$HOME/$SNAP/" 2>/dev/null
# ⛔ `uv run` inside the snapshot would BUILD A FRESH ENV — the snapshot carries no venv and no
# pyproject, so every game died with `ModuleNotFoundError: No module named 'arc_agi'` and the gate
# reported 25 missing games. Link the shared venv and invoke its interpreter directly. The venv is
# read-only here; the code being measured is still the snapshot's, because score_efficiency.py:35
# inserts the runner's own repo `src` at sys.path position 0.
ln -s "$HOME/admorphiq/.venv" "$HOME/$SNAP/.venv" 2>/dev/null
ln -s "$HOME/admorphiq/ARC-AGI-3-Agents" "$HOME/$SNAP/ARC-AGI-3-Agents" 2>/dev/null
cd "$HOME/$SNAP"

# Prove the snapshot's code is the code that will run, and REFUSE rather than report a number that
# describes the shared tree (the editable-install `.pth` shadowing that ptest.sh was caught by).
PYTHONPATH="$HOME/$SNAP/src" .venv/bin/python -c \
  "import admorphiq,sys; p=admorphiq.__file__; sys.exit(0 if p.startswith('$HOME/$SNAP/') else print('SHADOWED',p) or 1)" \
  || { echo "⛔ the snapshot is shadowed by the box's install — refusing to gate"; exit 1; }

ls environment_files | xargs -P "$PAR" -I{} sh -c \
  "timeout 2400 .venv/bin/python \$HOME/$SNAP/scripts/score_efficiency.py --agent "$AGENT" \
     --titles {} --max-actions $BUDGET --out \$HOME/${SNAP}_out/{}.json \
     > \$HOME/${SNAP}_out/{}.log 2>&1"

n=$(ls $HOME/${SNAP}_out/*.json 2>/dev/null | wc -l)
echo "GATEDONE $n games"
# ⛔ A gate that produced nothing must not reach the comparator. Measured 2026-08-29: 25 games all
# failed to import and `compare.py` printed every row as "(missing)" and then "no game regressed" —
# a PASS verdict over zero evidence, which is the same fail-open shape as the bash-3.2 `wait -n`
# throttle that reported success while protecting nothing.
[ "$n" -ge 25 ] || { echo "⛔ only $n of 25 games produced a result — see \$HOME/${SNAP}_out/*.log"; exit 1; }
EOS

# ⛔ THE REMOTE BLOCK'S REFUSAL MUST STOP THE LOCAL HALF. Measured 2026-08-30: an LLM-arm gate was
# killed mid-run, the remote printed "only 4 of 25 games produced a result" and exited 1 — and this
# script pulled the 4 anyway and ran the comparator, which reported "MEAN new = 1.0000 over 4".
# `compare.py`'s own no-verdict guard caught it, but only because games were MISSING; a remote
# failure that produced 25 present-but-wrong results would have sailed through. **A guard whose
# refusal the caller ignores is decorative** — the same shape as the bash-3.2 `wait -n` throttle.
if [ $? -ne 0 ]; then
  echo "⛔ the remote gate refused (see its message above) — NO VERDICT, nothing pulled."
  exit 1
fi

# ⛔ REFUSE TO WRITE INTO A DIRECTORY THAT ALREADY HOLDS RESULTS. Measured 2026-08-30: an agent's
# 50-file A/B already sat in scripts/rounds/R101LP85/games, the gate's 25 landed beside them, and
# compare.py dutifully reported "no game regressed (75 games compared)" — a verdict over three
# different experiments. The comparator's own no-verdict guard could not catch it because nothing was
# MISSING; there was simply too much. A round name is cheap; reusing one is not.
if [ -d "$OUT/games" ] && [ -n "$(ls -A "$OUT/games" 2>/dev/null)" ]; then
  echo "⛔ REFUSING: $OUT/games already holds $(ls "$OUT/games" | wc -l | tr -d ' ') files."
  echo "   A gate must not mix its results with another experiment's. Pick an unused name."
  exit 1
fi
mkdir -p "$OUT/games"
scp -q -i "$KEY" "$REMOTE:~/${SNAP}_out/*.json" "$OUT/games/" 2>/dev/null
echo "$COMMIT" > "$OUT/COMMIT"
uv run python scripts/rounds/compare.py "$OUT" "$BASE"
