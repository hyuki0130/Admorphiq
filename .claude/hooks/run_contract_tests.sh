#!/usr/bin/env bash
# Stop hook. Fires when Claude Code is about to end an assistant
# response. Runs the Wiki-First Routing contract test and blocks the
# stop (exit 2) if it's red — Claude then has to fix the violation
# before declaring the task done.
#
# Registered via .claude/settings.json (project-local).

set -uo pipefail

repo="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$repo"

# Run only the contract test — fast (< 1s) and scoped to the invariant
# this hook is meant to defend. Full-suite enforcement belongs in CI,
# not in every Stop-hook invocation.
if uv run pytest tests/test_classify_contract.py -q >/dev/null 2>&1; then
  exit 0
fi

cat <<'EOF' >&2
[run_contract_tests] CONTRACT TEST RED — tests/test_classify_contract.py

WikiAgent.classify() is mutating strategy picks after the whitelist
filter. This violates .wiki/wiki/architecture.md § Wiki-First Routing.

Find the helper (ANY name: _augment_*, _inject_*, _reinforce_*,
_override_*, ...) that reads game_title or probe signatures and writes
to Hypothesis.primary_strategy / Hypothesis.fallback_stack. Remove it.
Move the rule into .wiki/wiki/selector.md or a
.wiki/wiki/reasoning/*.md page so Qwen makes the decision itself.

Reproduce:
    uv run pytest tests/test_classify_contract.py -v
EOF

# Exit 2 blocks the Stop — Claude must continue working until the
# contract test is green.
exit 2
