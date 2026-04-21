#!/usr/bin/env bash
# PreToolUse hook. Fires when Claude Code is about to Edit / Write a
# file. If the target is src/admorphiq/hypothesis/wiki_agent.py, inject
# a reminder of the Wiki-First Routing rule from
# .wiki/wiki/architecture.md.
#
# The hook reads a JSON payload on stdin (Claude Code contract) and
# looks for `tool_input.file_path`. It never blocks the edit; it only
# surfaces a reminder so Claude re-reads the architectural lock before
# adding routing logic in Python.
#
# Registered via .claude/settings.json (project-local).

set -euo pipefail

payload="$(cat)"
# Extract file_path without adding a jq dependency. The payload is a
# single-level object emitted by Claude Code; a line-oriented grep +
# sed is sufficient and avoids runtime deps.
target="$(printf '%s' "$payload" | python3 -c 'import json,sys
try:
    data=json.load(sys.stdin)
    print((data.get("tool_input") or {}).get("file_path",""))
except Exception:
    pass')"

case "$target" in
  *src/admorphiq/hypothesis/wiki_agent.py)
    cat <<'EOF' >&2
[guard_wiki_agent] ARCHITECTURAL LOCK

You are about to edit src/admorphiq/hypothesis/wiki_agent.py.

.wiki/wiki/architecture.md § "Wiki-First Routing" prohibits adding any
Python helper that mutates Hypothesis.primary_strategy or
Hypothesis.fallback_stack beyond the whitelist filter — regardless of
the helper's name (_augment_*, _inject_*, _reinforce_*, _override_*, ...).

If a bench trace shows Qwen picked the wrong strategy, the correct fix
is to edit .wiki/wiki/selector.md or .wiki/wiki/reasoning/*.md so the
LLM makes the right pick from frame observations alone. Do NOT add a
Python branch that reads game_title or probe signatures and writes to
the Hypothesis.

If this edit is a refactor / typing / comment change, ignore this
reminder. If it is a new routing decision, stop and move the rule into
the wiki.

Enforced by:
  - tests/test_classify_contract.py (semantic contract test)
  - .claude/hooks/run_contract_tests.sh (Stop hook)
EOF
    ;;
  *) : ;;
esac

# Never block. Reminder only.
exit 0
