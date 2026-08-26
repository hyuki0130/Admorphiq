#!/usr/bin/env bash
# Stop-hook gate: a response may not complete while the wiki has orphans or unsummarised pages.
# ⛔ Measured 2026-08-27: writing pages without linking them produced 29 orphans and 10 missing
# summaries, and nothing surfaced it until the linter was run by hand at the end of the session.
cd "$CLAUDE_PROJECT_DIR" 2>/dev/null || exit 0
command -v uv >/dev/null 2>&1 || exit 0
out=$(timeout 120 uv run python scripts/wiki_lint.py 2>/dev/null) || exit 0
orphans=$(echo "$out" | grep -c '^- `' </dev/null 2>/dev/null; echo "$out" | sed -n '/Orphan pages (\([0-9]*\))/s//\1/p' | head -1)
summaries=$(echo "$out" | sed -n '/Missing index summary (\([0-9]*\))/s//\1/p' | head -1)
orphans=${orphans:-0}; summaries=${summaries:-0}
if [ "${orphans:-0}" -gt 0 ] || [ "${summaries:-0}" -gt 0 ]; then
  echo "[wiki-lint] BLOCKED: ${orphans} orphan page(s), ${summaries} page(s) with no index summary."
  echo "Run: uv run python scripts/wiki_lint.py — then link each new page from its natural parent"
  echo "and give it a one-sentence '>' summary under the H1. See the wiki-authoring skill."
  exit 2
fi
exit 0
