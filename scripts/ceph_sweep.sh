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

# ⛔ IT USED TO EXTRACT INTO THE SHARED `~/admorphiq` — rule 7l forbids that: eight agents edit
# `src/` continuously, so writing there changes the code under whoever else is measuring, and the
# sweep's own verdict carries every rider in the tree. Found 2026-08-30 by auditing which scripts
# still execute a forbidden path (the same audit caught `integrate.sh` calling the superseded gate
# and this file's sibling runner invoking pytest on the Mac).
echo "=== snapshot into a PRIVATE directory on the box (rule 7l)"
tar czf /tmp/_sweep.tgz src scripts 2>/dev/null
scp -q -i "$KEY" /tmp/_sweep.tgz "$REMOTE:~/" && rm -f /tmp/_sweep.tgz

echo "=== launch: every registered tool, alone, on each game — 60 cores, never 64"
# ⛔ ONE FILE PER PAIR, then concatenate. Appending every worker's stdout to ONE file with `>>` is
# atomic only below the pipe buffer: a line over ~4KB interleaves and every run but one reads as
# "produced nothing" — the fail-toward-nothing shape (same defect fixed in `pfan.sh` today).
"${SSH[@]}" "export PATH=\$HOME/.local/bin:\$PATH
S=\$HOME/sweep; rm -rf \$S \$S.d; mkdir -p \$S \$S.d; tar xzf ~/_sweep.tgz -C \$S; rm -f ~/_sweep.tgz
for d in .venv environment_files data ARC-AGI-3-Agents; do ln -s \$HOME/admorphiq/\$d \$S/\$d 2>/dev/null; done
cd \$S
PYTHONPATH=\$S/src .venv/bin/python -c 'import admorphiq,sys;p=admorphiq.__file__;sys.exit(0 if \"/sweep/\" in p else print(\"SHADOWED\",p) or 1)' || exit 1
TOOLS=\$(PYTHONPATH=\$S/src .venv/bin/python -c 'from admorphiq.harness.registry import default_tools; print(\" \".join(t.name for t in default_tools()))')
for g in $GAMES; do for t in \$TOOLS; do echo \"\$g \$t\"; done; done |
xargs -P 60 -n 2 sh -c 'PYTHONPATH='\$S'/src timeout 900 '\$S'/.venv/bin/python '\$S'/scripts/_solo_tool.py \"\$0\" \"\$1\" $CAP > '\$S'.d/\"\$0\"_\"\$1\".json 2>/dev/null'
rm -rf /tmp/solo && mkdir -p /tmp/solo
cat \$S.d/*.json > /tmp/solo/out.jsonl 2>/dev/null
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
