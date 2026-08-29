#!/usr/bin/env bash
# Fan ANY probe across seeds/bands on ceph-build. The default shape of a probe.
#
# ⛔ THIS SCRIPT USED TO CORRUPT OTHER AGENTS' RESULTS. It wrote to a fixed `/tmp/pfan.jsonl` and
# `rm -f`d it at launch, which is fine for one worker and destructive for eight: measured
# 2026-08-29, a 30-way lf52 fan came back with 359 lines and NOT ONE of its own, because a peer's fan
# owned the file — and this fan's own `rm` had already destroyed the peer's accumulated results. A
# fan-out that cannot tell its own output from someone else's is not a measurement. The NAME is now
# required, so results land in /tmp/pfan_<name>.jsonl and cannot collide.
#
# ⛔ AND IT HARDCODED -P 60. The 60-core cap is a TOTAL across everyone on the box, not a per-worker
# budget; with one agent per game each fanning 60-way the box hit 129 processes at load 64.6, where
# SSH stops answering. Parallelism is now an explicit argument with a modest default.
#
#   bash scripts/pfan.sh lf52l6 scripts/_lf52_verbs.py 30 "" 24
#                        ^name  ^probe                 ^n  ^arg ^-P
set -u
cd "$(dirname "$0")/.."
NAME="${1:?a short name for this fan, e.g. lf52l6 — results go to /tmp/pfan_<name>.jsonl}"
PROBE="${2:?probe path, e.g. scripts/_probe.py}"
N="${3:-30}"
REST="${4:-}"
PAR="${5:-24}"
KEY="$HOME/VM/keys/nfw-dev.pem"
REMOTE="ubuntu@ceph-build"
SSH=(ssh -o ConnectTimeout=20 -i "$KEY" "$REMOTE")

grep -q "__main__" "$PROBE" || { echo "⛔ $PROBE has no entrypoint — rule 7e"; exit 1; }

# ⚠️ Do NOT re-sync the whole tree here: another agent may be measuring against it (rule 7i). Ship
# only the scripts directory, which is additive.
tar czf "/tmp/_pfan_$NAME.tgz" scripts 2>/dev/null
scp -q -i "$KEY" "/tmp/_pfan_$NAME.tgz" "$REMOTE:~/" && rm -f "/tmp/_pfan_$NAME.tgz"
"${SSH[@]}" "cat > /tmp/pfan_$NAME.sh <<'EOS'
#!/usr/bin/env bash
export PATH=\$HOME/.local/bin:\$PATH
cd ~/admorphiq
tar xzf ~/_pfan_$NAME.tgz && rm -f ~/_pfan_$NAME.tgz
rm -f /tmp/pfan_$NAME.jsonl
seq 1 $N | xargs -P $PAR -I{} sh -c 'timeout 1800 uv run python $PROBE {} $REST 2>>/tmp/pfan_$NAME.err | grep \"^{\" >> /tmp/pfan_$NAME.jsonl'
echo DONE >> /tmp/pfan_$NAME.jsonl
EOS
chmod +x /tmp/pfan_$NAME.sh && nohup /tmp/pfan_$NAME.sh >/dev/null 2>&1 &"
echo "launched $N x $PROBE at -P $PAR"
echo "results:  ssh -i $KEY $REMOTE 'grep -o \"{[^}]*}\" /tmp/pfan_$NAME.jsonl'"
