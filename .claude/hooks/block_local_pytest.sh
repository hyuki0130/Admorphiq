#!/usr/bin/env bash
# PreToolUse(Bash): REFUSE a local pytest / game run. The Mac is editor + grep + ruff (rule 7m).
#
# ⛔ WHY A HOOK AND NOT A RULE. On 2026-08-29 the user reported the laptop unusable. Three full
# `pytest tests -q` suites were running here at once; they were killed; TWO MORE RESPAWNED within
# minutes, and a peer agent found and killed those. Every agent had been told, in writing, in the
# same hour. Rules 7i, 7j, 7k and 7m are all the same failure — a limit that asks a participant to
# remember it at the moment their attention is on something else. The version that holds is checked
# by something that is not a participant.
cmd=$(cat | python3 -c 'import json,sys;print(json.load(sys.stdin).get("tool_input",{}).get("command",""))' 2>/dev/null)
[ -z "$cmd" ] && exit 0

# Anything routed to the box is fine — that is the whole point.
case "$cmd" in *ssh*|*ceph-build*|*pfan.sh*|*snapgate.sh*|*ptest.sh*) exit 0 ;; esac

if printf '%s' "$cmd" | grep -qE '(^|[;&|[:space:]])(uv run )?(python3?|\.venv/bin/python3?)? ?-?m? ?pytest'; then
  cat >&2 <<'MSG'
⛔ BLOCKED: pytest does not run on the Mac (OPERATING_RULES.md rule 7m).

Three concurrent suites made the laptop unusable and the user asked twice for it to stop; two more
respawned after they were killed. ~1700 tests is a minute of a core, and there are 64 idle ones one
ssh away.

Run it on the box instead — same command shape, private snapshot, deleted on exit:

    bash scripts/ptest.sh tests/test_yours.py          # just yours — PREFER THIS
    bash scripts/ptest.sh --dirty tests/test_yours.py  # include uncommitted edits
    bash scripts/ptest.sh                              # whole suite, when you truly need it
MSG
  exit 2
fi

if printf '%s' "$cmd" | grep -qE 'score_efficiency|scripts/_[a-z0-9]+_'; then
  cat >&2 <<'MSG'
⛔ BLOCKED: game measurements do not run on the Mac (OPERATING_RULES.md rule 0 and 7k).

A replay, a solver, a BFS and an "offline enumeration" all count — if you are unsure, it counts.

    bash scripts/pfan.sh <name> <probe.py> <n> "<arg>" 6     # fan it on ceph-build
MSG
  exit 2
fi
exit 0
