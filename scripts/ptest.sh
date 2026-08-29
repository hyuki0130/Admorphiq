#!/usr/bin/env bash
# Run the test suite ON CEPH-BUILD, out of a private snapshot. The Mac stays responsive.
#
# ⛔ WHY. Rule 0 has always read "the Mac is edit/lint/pytest only", and every agent obeyed it —
# which is how, on 2026-08-29, THREE full `pytest tests -q` runs ended up executing on the laptop at
# once (57%, 56%, 55% CPU) and the user reported the machine unusable. The measured local load was
# not a game run at all; the alarm hook was looking for `score_efficiency` and saw nothing wrong.
#
# The suite is ~1700 tests. One run is a minute of one core; eight agents each running it after each
# edit is the laptop's whole capacity, spent on a machine with 64 idle cores one ssh away.
#
#   bash scripts/ptest.sh                      # whole suite on the box
#   bash scripts/ptest.sh tests/test_foo.py    # just yours — prefer this
#
# Snapshot semantics are `snapgate.sh`'s (rule 7l): `git archive HEAD` into a private directory, so
# a run cannot be disturbed by, and cannot disturb, whatever else is on the box.
#
# ⚠️ It tests HEAD, not your working copy. That is deliberate for a gate and WRONG for a red-green
# loop, so `--dirty` ships the working tree instead. Uncommitted work is named either way.
set -uo pipefail
cd "$(dirname "$0")/.."
KEY="$HOME/VM/keys/nfw-dev.pem"; REMOTE="ubuntu@ceph-build"
DIRTY=0; [ "${1:-}" = "--dirty" ] && { DIRTY=1; shift; }
TARGET="${*:-tests}"

# ⛔ WARN ON THE WHOLE SUITE. Measured 2026-08-30: an untargeted run sat at 2397% CPU — TWENTY-FOUR
# CORES — on a box whose total cap is 60 across every agent. One agent running it after each edit is
# a third of everyone's budget. It is not forbidden (a pre-gate check wants it), but it must be a
# decision rather than a habit.
if [ "$TARGET" = "tests" ]; then
  echo "⚠️  whole suite: ~24 cores of the 60-core TOTAL cap. Prefer 'bash scripts/ptest.sh tests/test_yours.py'." >&2
fi
SNAP="ptest_$$"

if [ "$DIRTY" = 1 ]; then
  echo "=== shipping the WORKING TREE (uncommitted edits included)"
  tar czf "/tmp/$SNAP.tgz" --exclude='__pycache__' src scripts tests notebooks pyproject.toml
else
  if ! git diff --quiet HEAD -- src/ tests/; then
    echo "⚠️  testing HEAD; these uncommitted edits are EXCLUDED (use --dirty to include them):"
    git diff --name-only HEAD -- src/ tests/ | sed 's/^/      /'
  fi
  git archive --format=tar.gz -o "/tmp/$SNAP.tgz" HEAD src scripts tests notebooks pyproject.toml
fi

scp -q -i "$KEY" "/tmp/$SNAP.tgz" "$REMOTE:~/" || { echo "⛔ scp failed"; exit 1; }
# ⛔ PASS THROUGH THE ENVIRONMENT, NOT POSITIONALLY. `ssh host bash -s "$SNAP" "$TARGET"` joins its
# arguments with spaces, so a TARGET of two files arrives as $2 and $3 — and the remote script,
# reading only $2, RAN THE FIRST FILE AND SILENTLY DROPPED THE SECOND. Measured 2026-08-30: the gate
# called it with `test_every_tool_is_registered.py test_detect_purity.py`, the purity test was never
# run, and a deliberately broken purity pin reported "guards hold". A guard that silently tests less
# than it was asked to is worse than no guard — it reports success for work it did not do, which is
# the fail-open shape this repository has now paid for four times.
ssh -o ConnectTimeout=20 -i "$KEY" "$REMOTE" "SNAP='$SNAP' TARGET='$TARGET' bash -s" <<'EOS'
set -u
export PATH=$HOME/.local/bin:$PATH
rm -rf "$HOME/$SNAP"; mkdir -p "$HOME/$SNAP"
tar xzf "$HOME/$SNAP.tgz" -C "$HOME/$SNAP"
ln -s "$HOME/admorphiq/.venv" "$HOME/$SNAP/.venv" 2>/dev/null
# ⛔ The suite spawns SUBPROCESSES that score games (test_adapter_detection.py does), and they find
# the games by a cwd-relative default — score_efficiency.py reads neither ENVIRONMENTS_DIR nor
# passes environments_dir=. Without this link the snapshot has no environment_files, the subprocess
# scores 0 games, and the assertion fails on a message about nothing. CLAUDE.md already records this
# exact trap costing a GPU session: unset environments = a healthy-looking run that scores zero.
ln -s "$HOME/admorphiq/environment_files" "$HOME/$SNAP/environment_files" 2>/dev/null
ln -s "$HOME/admorphiq/ARC-AGI-3-Agents" "$HOME/$SNAP/ARC-AGI-3-Agents" 2>/dev/null
# Same shape again: tests read recorded traces from data/. Link, never copy — these are large and a
# per-run copy would be the box's disk instead of the Mac's CPU.
ln -s "$HOME/admorphiq/data" "$HOME/$SNAP/data" 2>/dev/null
cd "$HOME/$SNAP"
# ⛔ PYTHONPATH IS LOAD-BEARING AND ITS ABSENCE WAS SILENT. The linked venv installs admorphiq
# EDITABLE, and `_editable_impl_admorphiq.pth` carries the ABSOLUTE path `/home/ubuntu/admorphiq/src`
# baked in at install time. Without this line the snapshot's own `src/` is shadowed by the box's
# stale copy, so `--dirty` shipped the working tree and then tested the code already on the box —
# a green suite for a file that was never imported. Measured 2026-08-29: a brand-new function in
# the shipped tree came back `ImportError: cannot import name`, which is the LOUD version; a
# CHANGED function comes back green, which is the expensive one.
# -p no:randomly: an agent comparing two runs needs the same order both times.
PYTHONPATH="$HOME/$SNAP/src" .venv/bin/python -m pytest $TARGET -q -p no:randomly 2>&1 | tail -25
rc=${PIPESTATUS[0]}
cd "$HOME"; rm -rf "$HOME/$SNAP" "$HOME/$SNAP.tgz"
exit $rc
EOS
