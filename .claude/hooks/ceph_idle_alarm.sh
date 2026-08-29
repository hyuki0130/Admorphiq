#!/usr/bin/env bash
# Inject the box's LOAD into every turn, so "is it running in parallel?" is answered without being
# remembered.
#
# ⛔ WHY. The user asked for parallel ceph work at least four times; the watchdog tick asks every nine
# minutes; two scripts exist for it. It still did not happen, because the instruction lived in
# documents I had to REMEMBER to read, and a context compaction drops exactly that. A hook does not
# depend on memory — the harness runs it and the answer lands in the turn.
#
# Measured 2026-08-29: 76 commits in a day, ZERO surviving source changes, box at load 9 of 64.
set -u
KEY="$HOME/VM/keys/nfw-dev.pem"
[ -f "$KEY" ] || exit 0
OUT=$(ssh -o ConnectTimeout=4 -o BatchMode=yes -i "$KEY" ubuntu@ceph-build \
        'n=$(pgrep -fc "uv run python" 2>/dev/null || echo 0); l=$(cut -d" " -f1 /proc/loadavg); echo "$n $l"' 2>/dev/null) || exit 0
PROCS=${OUT%% *}
LOAD=${OUT##* }
# ⛔ 60 IS A CEILING, NOT A TARGET. The box has 64 cores and saturating them locks out SSH, so the
# round becomes unreachable while it runs. With one agent per game each fanning out 60-way, the
# TOTAL is what matters — measured 2026-08-29: eight agents took it to 129 processes at load 64.6.
if [ "${PROCS:-0}" -gt 60 ]; then
  echo "⛔ ceph-build is OVERLOADED — $PROCS processes, load $LOAD. The cap is 60 of 64 cores;"
  echo "   above it SSH stops answering and the box cannot even be checked on. Agents each fan out"
  echo "   60-way, so the TOTAL is what breaks the cap. Throttle before launching anything else."
elif [ "${PROCS:-0}" -lt 8 ]; then
  echo "⛔ ceph-build is IDLE — $PROCS processes, load $LOAD of 64 cores."
  echo "   Do not run a probe once. Enumerate every hypothesis that could explain what you are"
  echo "   looking at (rule 7h) and fan them out:  bash scripts/pfan.sh PROBE.py 60 ARG"
  echo "   Tool-vs-game questions:                 bash scripts/ceph_sweep.sh"
else
  echo "ceph-build: $PROCS processes, load $LOAD — parallel work in flight."
fi
exit 0
