#!/usr/bin/env bash
# The two rule-recovery tools across all 25 sample games, one process per game.
#
# Both are cheap when they do not fit (the stencil tool withdraws in three actions), so the
# interesting column is where they fire at all — that is the transfer measurement, and it is
# what says whether a tool is a mechanic's tool or one game's.
set -u
cd "$(dirname "$0")/../../.."
OUT=scripts/rounds/R101TRACK
mkdir -p "$OUT/games"
GAMES="ar25 bp35 cd82 cn04 dc22 ft09 g50t ka59 lf52 lp85 ls20 m0r0 r11l re86 s5i5 sb26 sc25 sk48 sp80 su15 tn36 tr87 tu93 vc33 wa30"
# ⛔ HARD CAP 60 (user directive): ceph-build has 64 cores and saturating them locks out SSH.
PAR="${PAR:-12}"
[ "$PAR" -gt 60 ] && PAR=60
CAP="${CAP:-400}"
export OUT CAP
run_one() {
  for tool in track stencil; do
    script=scripts/track_probe.py
    [ "$tool" = stencil ] && script=scripts/glyph_stencil_probe.py
    uv run python "$script" "$1" "$CAP" > "$OUT/games/$1.$tool.log" 2>&1
  done
  echo "$(date '+%H:%M:%S')  $1 done"
}
export -f run_one
echo "$GAMES" | tr ' ' '\n' | xargs -P "$PAR" -I{} bash -c 'run_one {}'
echo "[R101TRACK] $(date '+%Y-%m-%d %H:%M:%S %Z') complete"
