#!/usr/bin/env bash
# Report game measurements running on the MAC into every turn.
#
# ⛔ WHY. Rule 0 says the Mac is edit/lint/pytest only and measurements run on ceph-build — it has
# 64 cores, the Mac has a fraction of that and is the machine the session itself runs on. Measured
# 2026-08-29: with eight agents active, `_bp35_l6_replay.py` was burning 91.9% CPU locally and a
# `score_efficiency.py` run was going too, Mac load 20.2. Nobody noticed until the user asked.
set -u
ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
# ⚠️ Match the INTERPRETER actually executing here, not the ssh/zsh wrapper that launches work on
# the box — the first version counted `ssh -i ...` as a local run and cried wolf three times.
PAT="^(/[^ ]*/)?(python[0-9.]*|\\.venv/bin/python[0-9.]*) .*(score_efficiency|scripts/_)"
N=$(ps -eo args 2>/dev/null | grep -Ec "$PAT" || true)
[ "${N:-0}" -eq 0 ] && exit 0

# ⛔ DO NOT CRY WOLF AT THE SANCTIONED PATH. `ceph-build` was DELETED on 2026-08-31, and
# `scripts/gate_local.sh` is now the only way to gate anything — it runs the 25 HERE, deliberately,
# with its own load guard that refuses above the core count. This hook shouted "they belong on
# ceph-build" at exactly that run, and an alarm that fires on the correct action teaches the next
# session to ignore the alarm, which is how a real one gets missed.
# ⚠️ Narrow on purpose: it recognises a live gate by its own snapshot directory, so a hand-rolled
# local run is still reported.
if pgrep -f "gate_local.sh" >/dev/null 2>&1 || ls -d "${TMPDIR:-/tmp}"/gate_*.*/out >/dev/null 2>&1; then
  echo "ℹ️  $N measurement(s) running locally — a scripts/gate_local.sh gate is in flight, which is"
  echo "   the sanctioned path now that ceph-build is gone. It has its own load guard. Not an alarm."
  exit 0
fi

echo "⛔ $N GAME MEASUREMENT(S) RUNNING ON THE MAC — and no gate_local.sh gate is in flight."
echo "   ⚠️ ceph-build no longer exists; the sanctioned local path is scripts/gate_local.sh, which"
echo "   refuses above the core count. A hand-rolled local run has no such guard."
ps -eo pid,pcpu,args 2>/dev/null | grep -E "$PAT" \
  | awk '{printf "   pid %s  %s%% CPU  %s\n", $1, $2, $4}' | head -4
echo "   Kill them and re-launch on the box: bash scripts/pfan.sh NAME PROBE.py N ARG -P"
exit 0
