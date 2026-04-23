#!/usr/bin/env bash
# PreToolUse hook. Fires when Claude Code is about to run a Bash
# command. If the command is `git commit` AND the staged diff modifies
# src/admorphiq/strategies/** OR src/admorphiq/hypothesis/** without
# any .wiki/wiki/** change, surface a reminder that the round's
# lesson / game-page / concept update is probably missing.
#
# Rule origin: feedback_wiki_doctrine + feedback_proactive_doc_sync +
# feedback_generic_not_game_specific — every algorithm round should
# leave a trace in the wiki so the next session (Qwen at Kaggle-time,
# Claude Code in dev-time) can reason from it.
#
# The hook never blocks — it only warns. Pure-bug-fix rounds that
# legitimately don't teach anything new may commit without wiki.

set -euo pipefail

payload="$(cat)"

cmd="$(printf '%s' "$payload" | python3 -c 'import json,sys
try:
    data=json.load(sys.stdin)
    print((data.get("tool_input") or {}).get("command",""))
except Exception:
    pass')"

case "$cmd" in
  *"git commit"*) : ;;
  *) exit 0 ;;
esac

# Check staged diff.
staged_paths="$(git diff --cached --name-only 2>/dev/null || true)"
if [ -z "$staged_paths" ]; then
  exit 0
fi

has_impl_change=0
has_wiki_change=0
while IFS= read -r path; do
  case "$path" in
    src/admorphiq/strategies/*|src/admorphiq/hypothesis/*|src/admorphiq/agent_ensemble.py|src/admorphiq/planner/*)
      has_impl_change=1 ;;
    .wiki/wiki/*)
      has_wiki_change=1 ;;
  esac
done <<< "$staged_paths"

if [ "$has_impl_change" -eq 1 ] && [ "$has_wiki_change" -eq 0 ]; then
  cat <<'EOF' >&2
[remind_wiki_sync] WIKI-SYNC REMINDER

This commit touches agent-impl code but stages no `.wiki/wiki/**`
change. Per the project's three memory rules:

  - feedback_wiki_doctrine.md        (wiki supports LLM reasoning)
  - feedback_proactive_doc_sync.md   (sync docs without being asked)
  - feedback_generic_not_game_specific.md
                                     (math changes must generalize)

each round should leave at least one of:

  - .wiki/wiki/lessons/<topic>_<YYYYMMDD>.md (new finding / regression)
  - .wiki/wiki/games/<GAME>.md               (updated provenance)
  - .wiki/wiki/concepts/<concept>.md         (new reusable abstraction)
  - .wiki/wiki/strategies/frame_only/*.md    (plan-fn contract)

so future Qwen routing AND future Claude Code sessions can recall
what was tried and why. Pure-bug-fix commits that teach nothing may
proceed without wiki — but those are rare. If this round measured
anything new, write the lesson FIRST, then re-stage.

This is a reminder, not a block. Re-invoke `git commit` to proceed.
EOF
fi

exit 0
