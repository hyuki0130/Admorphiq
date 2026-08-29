#!/usr/bin/env bash
# THE default way to investigate stuck games. One command, 60-way parallel, on ceph-build.
#
# ⛔ WHY THIS FILE EXISTS. "Use ceph in parallel" has been said by the user at least three times and
# is written into OPERATING_RULES.md rule 7b — and the box still sat at load 7 of 64 while games were
# probed one at a time for hours. A rule that DESCRIBES what to do loses to a habit; a COMMAND does
# not. If you are investigating why a game is stuck, run this instead of writing another probe.
#
#   bash scripts/ceph_sweep.sh                       # the five stuck games x every tool
#   bash scripts/ceph_sweep.sh "dc22 wa30" 2500      # a chosen set, chosen budget
#
# Reads: one JSON line per (game, tool) in /tmp/solo/out.jsonl on the box, then a summary here.
set -u
cd "$(dirname "$0")/.."
GAMES="${1:-dc22 wa30 s5i5 bp35 lf52}"
CAP="${2:-2500}"
KEY="$HOME/VM/keys/nfw-dev.pem"
REMOTE="ubuntu@ceph-build"
SSH=(ssh -o ConnectTimeout=20 -i "$KEY" "$REMOTE")

echo "=== sync the whole tree (a targeted tar outlives the reason for it — rule 7b trap 2)"
tar czf /tmp/_sweep.tgz src scripts 2>/dev/null
scp -q -i "$KEY" /tmp/_sweep.tgz "$REMOTE:~/" && rm -f /tmp/_sweep.tgz
"${SSH[@]}" 'export PATH=$HOME/.local/bin:$PATH; cd ~/admorphiq && tar xzf ~/_sweep.tgz && uv sync -q'

echo "=== launch: every registered tool, alone, on each game — 60 cores, never 64"
"${SSH[@]}" "export PATH=\$HOME/.local/bin:\$PATH; cd ~/admorphiq && rm -rf /tmp/solo && mkdir -p /tmp/solo &&
TOOLS=\$(uv run python -c 'from admorphiq.harness.registry import default_tools; print(\" \".join(t.name for t in default_tools()))') &&
for g in $GAMES; do for t in \$TOOLS; do echo \"\$g \$t\"; done; done |
xargs -P 60 -n 2 sh -c 'timeout 900 uv run python scripts/_solo_tool.py \"\$0\" \"\$1\" $CAP >> /tmp/solo/out.jsonl 2>/dev/null'
echo DONE >> /tmp/solo/out.jsonl"

echo "=== results: the best tool per game, and anything that beats the current best"
"${SSH[@]}" 'cd /tmp/solo && python3 -c "
import json
best = {}
for line in open(\"out.jsonl\"):
    line = line.strip()
    if not line or line == \"DONE\":
        continue
    d = json.loads(line)
    if \"levels\" not in d:
        continue
    k = d[\"game\"]
    if k not in best or d[\"levels\"] > best[k][\"levels\"]:
        best[k] = d
for g, d in sorted(best.items()):
    print(f\"  {g}: {d[\'levels\']} levels by {d[\'tool\']} in {d[\'actions\']} actions\")
"'
