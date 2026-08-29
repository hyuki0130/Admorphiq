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
SNAP="ptest_$$"

if [ "$DIRTY" = 1 ]; then
  echo "=== shipping the WORKING TREE (uncommitted edits included)"
  tar czf "/tmp/$SNAP.tgz" --exclude='__pycache__' src scripts tests pyproject.toml
else
  if ! git diff --quiet HEAD -- src/ tests/; then
    echo "⚠️  testing HEAD; these uncommitted edits are EXCLUDED (use --dirty to include them):"
    git diff --name-only HEAD -- src/ tests/ | sed 's/^/      /'
  fi
  git archive --format=tar.gz -o "/tmp/$SNAP.tgz" HEAD src scripts tests pyproject.toml
fi

scp -q -i "$KEY" "/tmp/$SNAP.tgz" "$REMOTE:~/" || { echo "⛔ scp failed"; exit 1; }
ssh -o ConnectTimeout=20 -i "$KEY" "$REMOTE" bash -s "$SNAP" "$TARGET" <<'EOS'
set -u
SNAP="$1"; TARGET="$2"
export PATH=$HOME/.local/bin:$PATH
rm -rf "$HOME/$SNAP"; mkdir -p "$HOME/$SNAP"
tar xzf "$HOME/$SNAP.tgz" -C "$HOME/$SNAP"
ln -s "$HOME/admorphiq/.venv" "$HOME/$SNAP/.venv" 2>/dev/null
cd "$HOME/$SNAP"
# -p no:randomly: an agent comparing two runs needs the same order both times.
.venv/bin/python -m pytest $TARGET -q -p no:randomly -x 2>&1 | tail -25
rc=${PIPESTATUS[0]}
cd "$HOME"; rm -rf "$HOME/$SNAP" "$HOME/$SNAP.tgz"
exit $rc
EOS
