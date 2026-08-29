#!/usr/bin/env bash
# Score the full 25 with every AVAILABLE ARCHIVED RE-RENDER substituted for its live game.
#
# ⛔ WHY THIS EXISTS AS A SCRIPT. The transfer number has been measured at least three times
# (`R101XFER9`: ratio 0.9981, 13 of 14 identical) and **the procedure was never recorded** — the
# round dirs hold `games/` and no `run.sh`, so each re-measurement re-derived the substitution by
# hand. That is the same failure as the 0.20 card whose build had to be recovered from a round page.
# A number that has to be re-derived to be repeated is not reproducible.
#
#   bash scripts/xfergate.sh <name> [baseline] [par] [budget]
#   bash scripts/xfergate.sh xfer10 scripts/rounds/R101SHIPPED 12 4000
#
# ⚠️ WHAT IT MEASURES, STATED SO IT IS NOT OVERSOLD. A re-render is the SAME GAME with different
# sprite tags and coordinates. Scoring identically on it proves the tools read MECHANICS rather than
# pixels — it does NOT predict a different game, and the private 110 are different games. It is the
# only generalisation proxy the repository has; treat it as a floor on brittleness, not a forecast.
#
# ⚠️ Only 15 of the 25 have an archived hash. The other ten run LIVE in both arms and are therefore
# expected to be identical — they are the instrument's own control, so a delta on one of THEM means
# the run is nondeterministic, not that transfer failed.
set -uo pipefail
cd "$(dirname "$0")/.."

NAME="${1:?a name for this run, e.g. xfer10}"
BASE="${2:-scripts/rounds/R101SHIPPED}"
PAR="${3:-12}"
BUDGET="${4:-4000}"
AGENT="${AGENT:-unified}"
KEY="$HOME/VM/keys/nfw-dev.pem"
REMOTE="ubuntu@ceph-build"
SSH=(ssh -o ConnectTimeout=20 -i "$KEY" "$REMOTE")
SNAP="snap_$NAME"
OUT="scripts/rounds/R101$(echo "$NAME" | tr 'a-z' 'A-Z')"

[ -d "$BASE/games" ] || { echo "⛔ baseline $BASE/games not found"; exit 1; }
[ -d "$OUT/games" ] && { echo "⛔ $OUT/games already holds results — pick another name"; exit 1; }

if ! git diff --quiet HEAD -- src/; then
  echo "⚠️  src/ has UNCOMMITTED edits, EXCLUDED from this run (it archives HEAD):"
  git diff --name-only HEAD -- src/ | sed 's/^/      /'
fi

find /tmp -maxdepth 1 -name "snap_*.tgz" -mmin +30 -delete 2>/dev/null
git archive --format=tar.gz -o "/tmp/$SNAP.tgz" HEAD src scripts
scp -q -i "$KEY" "/tmp/$SNAP.tgz" "$REMOTE:~/" || { echo "⛔ scp failed"; exit 1; }

"${SSH[@]}" bash -s "$SNAP" "$PAR" "$BUDGET" "$AGENT" <<'EOS'
set -u
SNAP="$1"; PAR="$2"; BUDGET="$3"; AGENT="$4"
export PATH=$HOME/.local/bin:$PATH
cd "$HOME"
find "$HOME" -maxdepth 1 -name 'snap_*' -mmin +120 -exec rm -rf {} + 2>/dev/null
rm -rf "$SNAP" "${SNAP}_out"; mkdir -p "$SNAP" "${SNAP}_out"
tar xzf "$SNAP.tgz" -C "$SNAP"
cp -r "$HOME/admorphiq/environment_files" "$HOME/$SNAP/"
ln -s "$HOME/admorphiq/.venv" "$HOME/$SNAP/.venv" 2>/dev/null
ln -s "$HOME/admorphiq/ARC-AGI-3-Agents" "$HOME/$SNAP/ARC-AGI-3-Agents" 2>/dev/null
cd "$HOME/$SNAP"

# ⛔ SUBSTITUTE, DO NOT ADD. Two version dirs under one game are the r59s15 duplicate-game_id
# hazard (rule 7bu): the loader keeps whichever `rglob` yields first, so ADDING the archive would
# score an unpredictable mixture of the two arms and look like a clean run.
SUBBED=""
for g in $(ls "$HOME/admorphiq/environment_files_archive" 2>/dev/null); do
  [ -d "environment_files/$g" ] || continue
  rm -rf "environment_files/$g"
  cp -r "$HOME/admorphiq/environment_files_archive/$g" "environment_files/$g"
  SUBBED="$SUBBED $g"
done
echo "SUBSTITUTED:$SUBBED"
echo "environments: $(ls environment_files | wc -l)"

PYTHONPATH="$HOME/$SNAP/src" .venv/bin/python -c \
  "import admorphiq,sys; p=admorphiq.__file__; sys.exit(0 if p.startswith('$HOME/$SNAP/') else print('SHADOWED',p) or 1)" \
  || { echo "⛔ the snapshot is shadowed by the box's install — refusing"; exit 1; }

ls environment_files | xargs -P "$PAR" -I{} sh -c \
  "timeout 2400 .venv/bin/python \$HOME/$SNAP/scripts/score_efficiency.py --agent "$AGENT" \
     --titles {} --max-actions $BUDGET --out \$HOME/${SNAP}_out/{}.json \
     > \$HOME/${SNAP}_out/{}.log 2>&1"

n=$(ls $HOME/${SNAP}_out/*.json 2>/dev/null | wc -l)
echo "XFERDONE $n games"
[ "$n" -ge 25 ] || { echo "⛔ only $n of 25 produced a result — see \$HOME/${SNAP}_out/*.log"; exit 1; }
EOS
[ $? -eq 0 ] || { echo "⛔ the remote run failed — no verdict"; exit 1; }

mkdir -p "$OUT/games"
scp -q -i "$KEY" "$REMOTE:~/${SNAP}_out/*.json" "$OUT/games/" || { echo "⛔ pull failed"; exit 1; }
echo "=== transfer: archived re-renders vs $BASE (live)"
# ⛔ READ compare.py's VERDICT LINE AS "DIFFERED", NOT "REGRESSED". Its language is a GATE's — it
# exists to refuse a code change that costs a game — and here nothing about the code changed: the
# BOARD did. A game that scores lower on a re-render has not regressed, it has failed to transfer,
# and the two call for opposite responses (revert vs investigate the tool's board-reading).
uv run python scripts/rounds/compare.py "$OUT" "$BASE"
echo "⚠️  above: 'REGRESSED' means DIFFERED ON A RE-RENDER. Nothing here is a reason to revert."
