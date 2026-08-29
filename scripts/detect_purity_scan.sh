#!/usr/bin/env bash
# Which tools' `detect` can mutate state? A grep-only static scan — no engine, no box, no venv.
#
# ⛔ THE CONTRACT. `detect` is a QUESTION: the harness asks every registered tool whether it
# recognises a board, at every re-decide, for all ~47 tools. Asking must not change the tool.
# MEASURED 2026-08-30 (R101SELECT part 3): sampling `railpeg.detect` every 10th action moves lf52
# from 823 actions to 827, because its `detect` runs the planner and the planner spends the tool's
# own three-unit patience and give-up counters. Merely ASKING it brings forward the moment it quits.
#
# ⚠️ WHY A STATIC SCAN AS WELL AS THE RUNTIME FAN. The fan (`scripts/_select_detectfx.py`) can only
# see a tool that reaches its mutating path ON THAT BOARD; most tools early-return on a game that is
# not theirs and score a clean 823 while still being unsafe elsewhere. The eval is 110 games whose
# boards we have never seen and the tool set is the same one, so "clean on lf52" is not "pure".
#
# ⛔ It is a SCAN, not a gate: it reports, it does not fail. Several tools mutate deliberately and
# one (`socketmerge`) mutates and RESTORES in a `finally`, which is the pattern worth copying — a
# line-counting scan cannot tell those apart, so a hit is a question, not a verdict.
set -u
cd "$(dirname "$0")/../src/admorphiq/tools"

body() {  # $1=file $2=method — print that method's body
  awk -v h="    def $2(" 'index($0,h)==1{inb=1;next} inb && /^    def /{inb=0} inb{print}' "$1"
}
MUT='self\._[a-zA-Z0-9]+ *(=|\+=|-=)[^=]|self\._[a-zA-Z0-9]+\.(append|add|update|clear|pop)\('

OUT=$(mktemp); total=0; dirty=0
for f in *.py; do
  [ "$f" = "base.py" ] && continue
  grep -q "^    def detect(" "$f" || continue
  total=$((total + 1))
  d=$(body "$f" detect)
  n=$(printf '%s\n' "$d" | grep -cE "$MUT")
  where=""
  [ "$n" -gt 0 ] && where="detect:$n"
  # one level of indirection: helpers detect calls on itself
  for h in $(printf '%s\n' "$d" | grep -oE "self\._[a-z_]+\(" | sort -u | tr -d '(' | sed 's/self\.//'); do
    k=$(body "$f" "$h" | grep -cE "$MUT")
    [ "$k" -gt 0 ] && { n=$((n + k)); where="$where $h:$k"; }
  done
  if [ "$n" -gt 0 ]; then
    dirty=$((dirty + 1))
    printf "%-16s %3d  %s\n" "${f%.py}" "$n" "$where" >> "$OUT"
  fi
# ⛔ NOT `done | sort` — a pipeline puts the loop in a subshell and the counters come back ZERO
# while every row still prints, which is the fail-open shape: a total that reads 0 of 0 beside
# nineteen listed tools. Collect, then sort.
done
sort -k2 -rn "$OUT"; rm -f "$OUT"
echo
echo "$dirty of $total tools have a detect that reaches a mutating line (scan, not verdict)."
