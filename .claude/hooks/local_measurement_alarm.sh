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
echo "⛔ $N GAME MEASUREMENT(S) RUNNING ON THE MAC — they belong on ceph-build (rule 0)."
ps -eo pid,pcpu,args 2>/dev/null | grep -E "$PAT" \
  | awk '{printf "   pid %s  %s%% CPU  %s\n", $1, $2, $4}' | head -4
echo "   Kill them and re-launch on the box: bash scripts/pfan.sh NAME PROBE.py N ARG -P"
exit 0
