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
# ⛔ COUNT THE INTERPRETER, NOT THE LAUNCHER — and DECIDE ON THE LOAD, not the count.
# The first version counted `uv run python`. Then snapgate/ptest/pfan moved to private snapshots
# that invoke `.venv/bin/python` DIRECTLY (rules 7l/7m/7r), and the hook went blind to every one of
# them: measured 2026-08-30 it reported "⛔ ceph-build is IDLE — 2 processes" while the box was at
# LOAD 65 with 17 script processes and a full pytest suite eating 24 cores. **My own infrastructure
# fix blinded my own watchdog**, and it failed toward "do more work", which is the direction that
# overloads the box.
#
# Load average is the honest signal: it needs no pattern to match and cannot be defeated by a change
# of launcher. The process count is kept, but only as detail.
OUT=$(ssh -o ConnectTimeout=4 -o BatchMode=yes -i "$KEY" ubuntu@ceph-build \
        'n=$(pgrep -fc "python[0-9.]* " 2>/dev/null || echo 0); l=$(cut -d" " -f1 /proc/loadavg); echo "$n $l"' 2>/dev/null) || exit 0
PROCS=${OUT%% *}
LOAD=${OUT##* }
LOADI=${LOAD%%.*}
# ⛔ 60 IS A CEILING, NOT A TARGET. The box has 64 cores and saturating them locks out SSH, so the
# round becomes unreachable while it runs. With one agent per game each fanning out 60-way, the
# TOTAL is what matters — measured 2026-08-29: eight agents took it to 129 processes at load 64.6.
# ⛔ LOAD ALONE DECIDES. Rule 7ad said "decide on the LOAD, not on a pattern match" and the first fix
# kept the count in an OR — which promptly fired OVERLOADED at load 21. Measured: the pattern matches
# 62 processes while only 22 consume any CPU, because a fan spawns `sh -c` wrappers and queued workers
# that are matched and idle. A count of processes is not a count of work. The number is still printed,
# because it is useful DETAIL; it just does not get a vote.
if [ "${LOADI:-0}" -gt 55 ]; then
  echo "⛔ ceph-build is OVERLOADED — $PROCS processes, load $LOAD. The cap is 60 of 64 cores;"
  echo "   above it SSH stops answering and the box cannot even be checked on. Agents each fan out"
  echo "   60-way, so the TOTAL is what breaks the cap. Throttle before launching anything else."
elif [ "${LOADI:-0}" -lt 8 ]; then
  echo "⛔ ceph-build is IDLE — $PROCS processes, load $LOAD of 64 cores."
  echo "   Do not run a probe once. Enumerate every hypothesis that could explain what you are"
  echo "   looking at (rule 7h) and fan them out:  bash scripts/pfan.sh PROBE.py 60 ARG"
  echo "   Tool-vs-game questions:                 bash scripts/ceph_sweep.sh"
else
  echo "ceph-build: $PROCS processes, load $LOAD — parallel work in flight."
fi
exit 0
