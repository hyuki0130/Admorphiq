#!/usr/bin/env bash
# Score games with ONE TOOL REMOVED, on ceph-build, out of a private snapshot.
#
#   bash scripts/ablategate.sh <name> [par] [budget] [pairsfile]
#   bash scripts/ablategate.sh own 12 4000                 # control: all 25, drop nothing
#   bash scripts/ablategate.sh drop1 12 4000 /tmp/pairs.txt # "<game> <tool>" per line
#
# ⭐ WHAT IT MEASURES. The closest available proxy to an UNSEEN GAME. Every other transfer
# instrument here perturbs the RENDERING of a game one of our tools already implements —
# the archived re-render (7by), the colour permutation and identifier rename (7ce). None
# perturbs the MECHANIC, and "a board whose mechanic no tool implements" is the actual
# private-110 condition. Removing a game's owner manufactures that condition.
#
# ⛔ WHAT IT DOES NOT PROVE. A game minus its owner is still a game the OTHER 46 tools were
# built against, on a board whose art, palette and control scheme are ours. It is a proxy,
# and a pessimistic-or-optimistic one in ways nothing here can bound.
#
# ⛔ THE `own` ARM (drop=none) IS THE MANDATORY CONTROL and it does double duty: it must
# reproduce `scripts/rounds/R101SHIPPED` exactly, and it is where OWNERSHIP is read from —
# per action, from `UnifiedAgent._current`, never from `detect()` (rule 7g).
#
# ⛔ environment_files is SYMLINKED, never written. Nothing is edited in the shared tree:
# the ablation monkeypatches `default_tools` inside the measuring process only (rule 7o —
# this is a measurement, and nothing ships off the back of it).
set -uo pipefail
cd "$(dirname "$0")/.."

NAME="${1:?a name for this run, e.g. own}"
PAR="${2:-12}"
BUDGET="${3:-4000}"
PAIRS="${4:-}"
AGENT="${AGENT:-unified}"
KEY="$HOME/VM/keys/nfw-dev.pem"
REMOTE="ubuntu@ceph-build"
SSH=(ssh -o ConnectTimeout=20 -i "$KEY" "$REMOTE")
SNAP="abl_$NAME"
OUT="scripts/rounds/R101ABLATE$(echo "$NAME" | tr 'a-z' 'A-Z')"

[ -d "$OUT" ] && { echo "⛔ $OUT already exists — pick another name"; exit 1; }
if [ -n "$PAIRS" ]; then
  [ -s "$PAIRS" ] || { echo "⛔ pairs file $PAIRS is missing or empty — REFUSING"; exit 1; }
fi

if ! git diff --quiet HEAD -- src/ scripts/; then
  echo "⚠️  UNCOMMITTED edits below are EXCLUDED — this archives HEAD:"
  git diff --name-only HEAD -- src/ scripts/ | sed 's/^/      /'
fi

find /tmp -maxdepth 1 -name "abl_*.tgz" -mmin +30 -delete 2>/dev/null
git archive --format=tar.gz -o "/tmp/$SNAP.tgz" HEAD src scripts
scp -q -i "$KEY" "/tmp/$SNAP.tgz" "$REMOTE:~/" || { echo "⛔ scp failed"; exit 1; }
if [ -n "$PAIRS" ]; then
  scp -q -i "$KEY" "$PAIRS" "$REMOTE:~/$SNAP.pairs" || { echo "⛔ pairs scp failed"; exit 1; }
else
  "${SSH[@]}" "rm -f ~/$SNAP.pairs"
fi

"${SSH[@]}" bash -s "$SNAP" "$PAR" "$BUDGET" "$AGENT" <<'EOS'
set -u
SNAP="$1"; PAR="$2"; BUDGET="$3"; AGENT="$4"
export PATH=$HOME/.local/bin:$PATH
cd "$HOME"
find "$HOME" -maxdepth 1 -name 'abl_*' -type d -mmin +240 -exec rm -rf {} + 2>/dev/null
rm -rf "$SNAP" "${SNAP}_out"; mkdir -p "$SNAP" "${SNAP}_out"
tar xzf "$SNAP.tgz" -C "$SNAP"
ln -s "$HOME/admorphiq/environment_files" "$HOME/$SNAP/environment_files"
ln -s "$HOME/admorphiq/.venv" "$HOME/$SNAP/.venv"
ln -s "$HOME/admorphiq/ARC-AGI-3-Agents" "$HOME/$SNAP/ARC-AGI-3-Agents" 2>/dev/null
cd "$HOME/$SNAP"

PYTHONPATH="$HOME/$SNAP/src" .venv/bin/python -c \
  "import admorphiq,sys; p=admorphiq.__file__; sys.exit(0 if p.startswith('$HOME/$SNAP/') else print('SHADOWED',p) or 1)" \
  || { echo "⛔ the snapshot is shadowed by the box's install — refusing"; exit 1; }

if [ -f "$HOME/$SNAP.pairs" ]; then
  cp "$HOME/$SNAP.pairs" pairs.txt
else
  ls environment_files | sed 's/$/ none/' > pairs.txt
fi
NG=$(wc -l < pairs.txt)
echo "pairs:$NG par:$PAR budget:$BUDGET agent:$AGENT"

cat pairs.txt | xargs -P "$PAR" -n 2 sh -c \
  "timeout 5400 .venv/bin/python \$HOME/$SNAP/scripts/ablate_run.py --agent $AGENT \
     --titles \$0 --drop \$1 --max-actions $BUDGET \
     --out \$HOME/${SNAP}_out/\$0.json > \$HOME/${SNAP}_out/\$0.log 2>&1"

n=$(ls $HOME/${SNAP}_out/*.json 2>/dev/null | wc -l)
echo "ABLATEDONE $n/$NG"
[ "$n" -eq "$NG" ] || { echo "⛔ $n of $NG produced a result — see \$HOME/${SNAP}_out/*.log"; exit 1; }
EOS
[ $? -eq 0 ] || { echo "⛔ the remote run failed — NO VERDICT"; exit 1; }

mkdir -p "$OUT/games"
git rev-parse --short HEAD > "$OUT/COMMIT"
scp -q -i "$KEY" "$REMOTE:~/${SNAP}_out/*.json" "$OUT/games/" || { echo "⛔ pull failed"; exit 1; }
scp -q -i "$KEY" "$REMOTE:~/${SNAP}_out/*.log" "$OUT/games/" 2>/dev/null
echo "=== pulled to $OUT/games"
uv run python scripts/ablate_report.py "$OUT"
