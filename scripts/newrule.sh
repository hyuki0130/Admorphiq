#!/usr/bin/env bash
# Claim the next free rule number in OPERATING_RULES.md and print the header to use.
#
# ⛔ WHY. Three collisions in one night (7ap, 7bc, 7bf), each written twice by two agents within the
# same hour, each costing a renumber plus a correction to whatever already cited the wrong number.
# "Read the file and pick the next letter" is a read-modify-write with no lock, and in a fan-out the
# read is stale before the write.
#
#   bash scripts/newrule.sh "the title of your rule"
#
# ⚠️ It claims by APPENDING a stub immediately, so the number is taken the moment you ask rather than
# when you finish writing. Fill the stub in; do not add a second header.
set -uo pipefail
cd "$(dirname "$0")/.."
TITLE="${1:?a short rule title}"
F=OPERATING_RULES.md

# Suffixes run 7c, 7d ... 7z, then 7aa, 7ab ... — the same order the file already uses.
# ⛔ `local letters=({a..z})` does NOT expand — brace expansion happens before `local` assigns, so the
# array holds the literal "{a..z}" and the first "free" suffix printed was `7(z)`. Build it without
# a brace inside an assignment.
next() {
  local letters i j
  letters=$(printf '%s ' {a..z})
  # ⚠️ 7a and 7b predate the "### 7x — " header style and appear in other forms, so a grep for the
  # HEADER alone reports them free. Match the number anywhere it is cited.
  for i in $letters; do
    grep -q "\b7$i\b" "$F" || { echo "7$i"; return; }
  done
  for i in $letters; do for j in $letters; do
    grep -q "\b7$i$j\b" "$F" || { echo "7$i$j"; return; }
  done; done
  echo "7zzz"
}

N=$(next)
DATE=$(date +%Y-%m-%d)
printf '\n### %s — %s (%s)\n\n_(stub claimed by scripts/newrule.sh — fill this in)_\n' "$N" "$TITLE" "$DATE" >> "$F"
echo "claimed $N"
echo "header:  ### $N — $TITLE ($DATE)"
echo "⚠️ the stub is already appended; edit it in place rather than adding a second header."
