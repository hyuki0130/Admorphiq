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
# ⛔ score_efficiency.py:35 inserts ITS OWN repo's src ahead of PYTHONPATH, so invoking the copy
# inside the snapshot is what selects the snapshot's code. Running it with cwd=~/admorphiq is what
# gives it the environment files. Both halves are load-bearing; neither is obvious.
set -uo pipefail
cd "$(dirname "$0")/.."

NAME="${1:?a name for this gate, e.g. re86}"
BASE="${2:-scripts/rounds/R101REACH}"
PAR="${3:-8}"
BUDGET="${4:-4000}"
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

COMMIT=$(git rev-parse --short HEAD)
echo "=== gating $COMMIT out of a private snapshot ~/$SNAP (par $PAR, budget $BUDGET)"

git archive --format=tar.gz -o "/tmp/$SNAP.tgz" HEAD src scripts
scp -q -i "$KEY" "/tmp/$SNAP.tgz" "$REMOTE:~/" || { echo "⛔ scp failed"; exit 1; }

"${SSH[@]}" bash -s "$SNAP" "$PAR" "$BUDGET" <<'EOS'
set -u
SNAP="$1"; PAR="$2"; BUDGET="$3"
export PATH=$HOME/.local/bin:$PATH
cd "$HOME"
rm -rf "$HOME/$SNAP" "$HOME/${SNAP}_out"
mkdir -p "$HOME/$SNAP" "$HOME/${SNAP}_out"
tar xzf "$HOME/$SNAP.tgz" -C "$HOME/$SNAP"
cd "$HOME/admorphiq"                      # for environment_files + the venv
ls environment_files | xargs -P "$PAR" -I{} sh -c \
  "timeout 2400 uv run python \$HOME/$SNAP/scripts/score_efficiency.py --agent unified \
     --titles {} --max-actions $BUDGET --out \$HOME/${SNAP}_out/{}.json \
     > \$HOME/${SNAP}_out/{}.log 2>&1"
echo "GATEDONE $(ls $HOME/${SNAP}_out/*.json 2>/dev/null | wc -l) games"
EOS

mkdir -p "$OUT/games"
scp -q -i "$KEY" "$REMOTE:~/${SNAP}_out/*.json" "$OUT/games/" 2>/dev/null
echo "$COMMIT" > "$OUT/COMMIT"
uv run python scripts/rounds/compare.py "$OUT" "$BASE"
