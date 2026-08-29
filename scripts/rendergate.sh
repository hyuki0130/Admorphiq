#!/usr/bin/env bash
# Score the full 25 under RENDER-ONLY MUTATIONS of the agent's observation, one arm at a
# time, from a private snapshot on ceph-build. The transfer test that does not need an
# archived version hash, because it MANUFACTURES the re-render.
#
#   bash scripts/rendergate.sh <name> [arms] [par] [budget] [titles]
#   bash scripts/rendergate.sh r1 "identity cperm cpermbg shift1" 12 4000
#   bash scripts/rendergate.sh smoke "identity cperm" 4 800 bp35,vc33
#
# ⭐ WHAT IT MEASURES. Whether the generic tools read the board's STRUCTURE or its PIXELS.
# Each arm relabels or repositions what the agent sees and changes NOTHING the game does:
# the mutation is applied to a copy of the observation after `env.step()` returns, and the
# agent's click is mapped back into the game's own coordinates, so the engine receives the
# input it would have received unmutated. Level structure, win predicate and the human
# `baseline_actions` denominator are therefore untouched BY CONSTRUCTION. Full validity
# argument + the refusal path: `src/admorphiq/render_mutation.py`.
#
# ⛔ WHAT IT DOES NOT PROVE. A relabelled board is the SAME BOARD with the same mechanic —
# a floor on brittleness, exactly like `xfergate.sh`'s archived re-render, and NOT a
# forecast for the 110 private games, which have different MECHANICS. Do not quote a ratio
# from here as a transfer coefficient.
#
# ⭐ WHY IT EXISTS BESIDE `xfergate.sh`. The archive covers 14 of the 25 games (sk48's
# "archive" is the same version hash, byte-identical — a self-substitution, so the recorded
# "fifteen" is fourteen). bp35, cd82, ft09, g50t, lf52, lp85, ls20, sb26, tr87 and wa30 have
# no archived hash and therefore NO transfer evidence of any kind. This instrument reaches
# all 25.
#
# ⛔ THE `identity` ARM IS NOT OPTIONAL. It is the run's own control: same commit, same box,
# same budget, mutation disabled. Every other arm is read against IT, never against a round
# dir measured at an older commit — otherwise code drift is indistinguishable from a
# transfer failure. `rendergate_compare.py` refuses a verdict if the identity arm is absent.
set -uo pipefail
cd "$(dirname "$0")/.."

NAME="${1:?a name for this run, e.g. r1}"
ARMS="${2:-identity cperm cpermbg shift1}"
PAR="${3:-12}"
BUDGET="${4:-4000}"
TITLES="${5:-}"
AGENT="${AGENT:-unified}"
KEY="$HOME/VM/keys/nfw-dev.pem"
REMOTE="ubuntu@ceph-build"
SSH=(ssh -o ConnectTimeout=20 -i "$KEY" "$REMOTE")
SNAP="rend_$NAME"
OUT="scripts/rounds/R101RENDER$(echo "$NAME" | tr 'a-z' 'A-Z')"

[ -d "$OUT" ] && { echo "⛔ $OUT already exists — pick another name"; exit 1; }
case " $ARMS " in *" identity "*) ;; *) echo "⛔ the identity control arm is mandatory"; exit 1;; esac

if ! git diff --quiet HEAD -- src/ scripts/; then
  echo "⚠️  UNCOMMITTED edits below are EXCLUDED — this archives HEAD:"
  git diff --name-only HEAD -- src/ scripts/ | sed 's/^/      /'
fi

find /tmp -maxdepth 1 -name "rend_*.tgz" -mmin +30 -delete 2>/dev/null
git archive --format=tar.gz -o "/tmp/$SNAP.tgz" HEAD src scripts
scp -q -i "$KEY" "/tmp/$SNAP.tgz" "$REMOTE:~/" || { echo "⛔ scp failed"; exit 1; }

# ⛔ ssh does NOT preserve argv — it joins the command into ONE string that the remote
# shell re-parses. An argument containing spaces silently becomes several, shifting every
# argument after it: the first smoke run reported "arms:[identity] games:1" because the
# arm list split and the titles argument was read from the middle of it. Arms travel
# COMMA-SEPARATED for that reason.
ARMS_CSV=$(echo "$ARMS" | tr -s ' ' ',')
"${SSH[@]}" bash -s "$SNAP" "$PAR" "$BUDGET" "$AGENT" "$ARMS_CSV" "${TITLES:-ALL}" <<'EOS'
set -u
SNAP="$1"; PAR="$2"; BUDGET="$3"; AGENT="$4"; ARMS=$(echo "$5" | tr ',' ' '); TITLES="$6"
[ "$TITLES" = "ALL" ] && TITLES=""
export PATH=$HOME/.local/bin:$PATH
cd "$HOME"
# ⛔ rule 7bi — the box's disk filled with our own snapshots once already.
find "$HOME" -maxdepth 1 -name 'rend_*' -mmin +240 -exec rm -rf {} + 2>/dev/null
rm -rf "$SNAP" "${SNAP}_out"; mkdir -p "$SNAP" "${SNAP}_out"
tar xzf "$SNAP.tgz" -C "$SNAP"
# ⛔ environment_files is SYMLINKED, never copied and never written. This instrument does
# not mutate the games at all — the ground truth is untouched by construction.
ln -s "$HOME/admorphiq/environment_files" "$HOME/$SNAP/environment_files"
ln -s "$HOME/admorphiq/.venv" "$HOME/$SNAP/.venv"
ln -s "$HOME/admorphiq/ARC-AGI-3-Agents" "$HOME/$SNAP/ARC-AGI-3-Agents" 2>/dev/null
cd "$HOME/$SNAP"

PYTHONPATH="$HOME/$SNAP/src" .venv/bin/python -c \
  "import admorphiq,sys; p=admorphiq.__file__; sys.exit(0 if p.startswith('$HOME/$SNAP/') else print('SHADOWED',p) or 1)" \
  || { echo "⛔ the snapshot is shadowed by the box's install — refusing"; exit 1; }

if [ -n "$TITLES" ]; then
  GAMES=$(echo "$TITLES" | tr ',' ' ')
else
  GAMES=$(ls environment_files)
fi
NG=$(echo "$GAMES" | wc -w)
echo "arms:[$ARMS] games:$NG par:$PAR budget:$BUDGET agent:$AGENT"

for arm in $ARMS; do mkdir -p "$HOME/${SNAP}_out/$arm"; done
for arm in $ARMS; do for g in $GAMES; do echo "$arm $g"; done; done | \
  xargs -P "$PAR" -n 2 sh -c \
    "timeout 3600 .venv/bin/python \$HOME/$SNAP/scripts/rendergate_run.py --agent $AGENT \
       --mutation \$0 --titles \$1 --max-actions $BUDGET \
       --out \$HOME/${SNAP}_out/\$0/\$1.json > \$HOME/${SNAP}_out/\$0/\$1.log 2>&1"

for arm in $ARMS; do
  n=$(ls $HOME/${SNAP}_out/$arm/*.json 2>/dev/null | wc -l)
  echo "ARM $arm -> $n/$NG results"
  [ "$n" -eq "$NG" ] || { echo "⛔ arm $arm produced $n of $NG — see \$HOME/${SNAP}_out/$arm/*.log"; FAIL=1; }
done
[ "${FAIL:-0}" = 0 ] || exit 1
echo "RENDERDONE"
EOS
[ $? -eq 0 ] || { echo "⛔ the remote run failed — NO VERDICT"; exit 1; }

mkdir -p "$OUT"
git rev-parse --short HEAD > "$OUT/COMMIT"
for arm in $ARMS; do
  mkdir -p "$OUT/$arm/games"
  scp -q -i "$KEY" "$REMOTE:~/${SNAP}_out/$arm/*.json" "$OUT/$arm/games/" \
    || { echo "⛔ pull of arm $arm failed"; exit 1; }
done
uv run python scripts/rendergate_compare.py "$OUT"
