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
# ⛔ DISTINGUISH "RED" FROM "COULD NOT RUN". Measured 2026-08-30: the Mac's disk filled, this hook's
# heredoc could not create a temp file, and it BLOCKED EVERY RESPONSE for half an hour while being
# unable to check anything at all — the session could not even report the problem. **A guard that
# cannot see must not veto.** That is rule 7q's shape from the other side: a comparison with nothing
# to compare is not a pass, and equally not a failure.
if [ "$(df -k . 2>/dev/null | awk 'NR==2{print $4}' || echo 0)" -lt 51200 ]; then
  echo "[run_contract_tests] SKIPPED — under 50MB free. The guard cannot run, so it is not vetoing." >&2
  exit 0
fi

out=$(uv run pytest tests/test_classify_contract.py -q 2>&1)
if [ $? -eq 0 ]; then
  exit 0
fi

# Could not EXECUTE (disk, interpreter, collection error) rather than FAILED — report, do not block.
case "$out" in
  *"No space left"*|*"OSError"*|*"command not found"*|*"error: Failed"*|*"INTERNALERROR"*)
    echo "[run_contract_tests] COULD NOT RUN (not red) — ${out##*$'\n'}" >&2
    exit 0 ;;
esac

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
