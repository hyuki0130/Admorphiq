#!/usr/bin/env bash
# Print the campaign's next actions into every turn.
#
# ⛔ Between turns I keep nothing, so the plan has to live in a file and be pushed at me. Without
# this the next action is always "whatever the last tool output suggests", which is serial by
# construction — measured 2026-08-29 as 76 commits and zero surviving source changes.
set -u
ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
F="$ROOT/.wiki/wiki/campaign/ACTIVE.md"
[ -f "$F" ] || exit 0
echo "── CAMPAIGN (.wiki/wiki/campaign/ACTIVE.md) ──"
sed -n '/## NEXT ACTIONS/,/## LOG/p' "$F" | head -14
exit 0
