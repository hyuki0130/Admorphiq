#!/usr/bin/env bash
# Score the full 25 under a PAINT-ORDER (z-order) mutation of the rendered frame, one arm
# at a time, from a private snapshot on ceph-build.
#
#   bash scripts/zordergate.sh <name> [arms] [par] [budget] [titles]
#   bash scripts/zordergate.sh z1 "identity zrev zrot" 8 4000
#   bash scripts/zordergate.sh smoke "identity zrev" 2 600 s5i5
#
# ⭐ WHY IT EXISTS BESIDE `rendergate.sh`. Rule 7cd named the campaign's ONLY measured
# transfer defect — s5i5's L4 costs 22 extra actions on the archived re-render because
# that file lists the rider BEFORE the bar it rides, so one cell is covered and a tool
# that identifies the rider by whether it is DRAWN loses the pin. ⛔ `rendergate.sh`
# CANNOT produce that: a colour permutation is a bijection and preserves which sprite is
# on top; a translation does too. Nothing in the repository changed paint order until
# this script.
#
# ⭐ WHAT THE MUTATION IS. Within each LAYER, the sprites are permuted among themselves
# — reversed (`zrev`) or cycled by one (`zrot`) — and every layer keeps the list SLOTS it
# already occupied, so no sprite ever crosses a layer boundary. The engine's paint sort
# is `sorted(..., key=layer)` and STABLE, so within a layer the list order IS the z-order;
# permuting it changes only which of two co-located sprites wins a pixel. Three games
# (s5i5, tu93, wa30) override `_raw_render` and do not sort at all, so for them the list
# order alone decides — the same-layer rule is still the conservative one there.
#
# ⭐ VALIDITY IS BY CONSTRUCTION, AND THE ARGUMENT IS ONE LINE OF THE ENGINE.
# `Camera.render` has exactly ONE caller in arcengine — `base_game.perform_action`, whose
# return value is the observation frame. Game logic that reads the picture goes through
# `BaseGame.get_pixels` -> `camera._raw_render`, which this instrument does not touch, and
# click resolution goes through `Level.get_sprite_at`, which reads `Level._sprites` and is
# likewise untouched. So the game's state trajectory stays a function of the action
# sequence alone. Full argument: `src/admorphiq/zorder_mutation.py`.
#
# ⭐ AND THE HUMAN DENOMINATOR IS INVARIANT — MEASURED. The two s5i5 serializations differ
# only in list order (`scripts/_s5i5_srcdiff.py`) and ship the IDENTICAL
# `baseline_actions` [20, 89, 106, 54, 162, 38, 86, 83]. The competition's own re-render
# of this board changed the paint order and did not change the human count.
#
# ⛔ THE `identity` ARM IS NOT OPTIONAL. It is the run's own control: same commit, same
# box, same budget, patch installed but inert. Every other arm is read against IT, never
# against a round dir measured at an older commit — otherwise code drift and a paint-order
# dependence are the same number. `rendergate_compare.py` refuses a verdict without it.
#
# ⛔ AND THE POSITIVE CONTROL IS s5i5. Rule 7cd banked the known answer: L4 goes 39 -> 61
# actions when the rider is painted under the bar. An arm that cannot score its own known
# positive has measured nothing — five instruments in this campaign failed exactly there.
set -uo pipefail
cd "$(dirname "$0")/.."

NAME="${1:?a name for this run, e.g. z1}"
ARMS="${2:-identity zrev zrot}"
PAR="${3:-8}"
BUDGET="${4:-4000}"
TITLES="${5:-}"
AGENT="${AGENT:-unified}"
KEY="$HOME/VM/keys/nfw-dev.pem"
REMOTE="ubuntu@ceph-build"
SSH=(ssh -o ConnectTimeout=20 -i "$KEY" "$REMOTE")
SNAP="zord_$NAME"
OUT="scripts/rounds/R101ZORDER$(echo "$NAME" | tr 'a-z' 'A-Z')"

[ -d "$OUT" ] && { echo "⛔ $OUT already exists — pick another name"; exit 1; }
case " $ARMS " in *" identity "*) ;; *) echo "⛔ the identity control arm is mandatory"; exit 1;; esac

# ⛔ rule 7cc — an LLM arm on this box took 37 cores and drove the load to 110.
if [ -n "${HARNESS_MODEL:-}${HARNESS_LLM_BASE_URL:-}" ]; then
  echo "⛔ HARNESS_MODEL/HARNESS_LLM_BASE_URL is set — ceph-build has no GPU. Refusing."
  exit 1
fi

if ! git diff --quiet HEAD -- src/ scripts/; then
  echo "⚠️  UNCOMMITTED edits below are EXCLUDED — this archives HEAD:"
  git diff --name-only HEAD -- src/ scripts/ | sed 's/^/      /'
fi

find /tmp -maxdepth 1 -name "zord_*.tgz" -mmin +30 -delete 2>/dev/null
git archive --format=tar.gz -o "/tmp/$SNAP.tgz" HEAD src scripts
scp -q -i "$KEY" "/tmp/$SNAP.tgz" "$REMOTE:~/" || { echo "⛔ scp failed"; exit 1; }

# ⛔ ssh does NOT preserve argv — it joins the command into ONE string the remote shell
# re-parses, so an argument containing spaces silently becomes several and shifts every
# argument after it (rendergate.sh paid for this). Arms travel COMMA-SEPARATED.
ARMS_CSV=$(echo "$ARMS" | tr -s ' ' ',')
"${SSH[@]}" bash -s "$SNAP" "$PAR" "$BUDGET" "$AGENT" "$ARMS_CSV" "${TITLES:-ALL}" <<'EOS'
set -u
SNAP="$1"; PAR="$2"; BUDGET="$3"; AGENT="$4"; ARMS=$(echo "$5" | tr ',' ' '); TITLES="$6"
[ "$TITLES" = "ALL" ] && TITLES=""
export PATH=$HOME/.local/bin:$PATH
cd "$HOME"
# ⛔ rule 7bi — the box's disk filled with our own snapshots once already.
find "$HOME" -maxdepth 1 -name 'zord_*' -mmin +240 -exec rm -rf {} + 2>/dev/null
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
    "timeout 3600 .venv/bin/python \$HOME/$SNAP/scripts/zordergate_run.py --agent $AGENT \
       --mutation \$0 --titles \$1 --max-actions $BUDGET \
       --out \$HOME/${SNAP}_out/\$0/\$1.json > \$HOME/${SNAP}_out/\$0/\$1.log 2>&1"

for arm in $ARMS; do
  n=$(ls $HOME/${SNAP}_out/$arm/*.json 2>/dev/null | wc -l)
  echo "ARM $arm -> $n/$NG results"
  [ "$n" -eq "$NG" ] || { echo "⛔ arm $arm produced $n of $NG — see \$HOME/${SNAP}_out/$arm/*.log"; FAIL=1; }
done
[ "${FAIL:-0}" = 0 ] || exit 1
echo "ZORDERDONE"
EOS
[ $? -eq 0 ] || { echo "⛔ the remote run failed — NO VERDICT"; exit 1; }

mkdir -p "$OUT"
git rev-parse --short HEAD > "$OUT/COMMIT"
for arm in $ARMS; do
  mkdir -p "$OUT/$arm/games"
  scp -q -i "$KEY" "$REMOTE:~/${SNAP}_out/$arm/*.json" "$OUT/$arm/games/" \
    || { echo "⛔ pull of arm $arm failed"; exit 1; }
done
uv run python scripts/rendergate_compare.py "$OUT" "${BASE:-scripts/rounds/R101SHIPPED}"
