#!/usr/bin/env bash
# Run ANY probe across many seeds/bands on ceph-build, 60 at once. The default shape of a probe.
#
# ⛔ WHY THIS EXISTS. The watchdog tick already says "check whether parallel agents are running", and
# the answer was repeatedly "no" — because CHECKING is not DOING. I would verify the box was idle and
# then carry on with a single serial probe, because each investigation needs a bespoke script and I
# never asked whether that script could be sixty processes instead of one. Measured 2026-08-29: 76
# commits in a day, ZERO surviving source changes, and the box at load 9 of 64 for most of it.
#
#   bash scripts/pfan.sh scripts/_s5i5_hunt.py 60 700     # seeds 1..60, second arg to the probe
#   bash scripts/pfan.sh scripts/_dc22_hunt.py 40 900
#
# The probe must take its varying parameter FIRST (a seed, a band start, a prefix length) and print
# one JSON line. Results land in /tmp/pfan.jsonl on the box and are summarised here.
set -u
cd "$(dirname "$0")/.."
PROBE="${1:?probe path, e.g. scripts/_s5i5_hunt.py}"
N="${2:-60}"
REST="${3:-}"
KEY="$HOME/VM/keys/nfw-dev.pem"
REMOTE="ubuntu@ceph-build"
SSH=(ssh -o ConnectTimeout=20 -i "$KEY" "$REMOTE")

grep -q "__main__" "$PROBE" || { echo "⛔ $PROBE has no entrypoint — rule 7e"; exit 1; }

tar czf /tmp/_pfan.tgz scripts 2>/dev/null
scp -q -i "$KEY" /tmp/_pfan.tgz "$REMOTE:~/" && rm -f /tmp/_pfan.tgz
"${SSH[@]}" "cat > /tmp/pfan.sh <<'EOS'
#!/usr/bin/env bash
export PATH=\$HOME/.local/bin:\$PATH
cd ~/admorphiq
tar xzf ~/_pfan.tgz
rm -f /tmp/pfan.jsonl
seq 1 $N | xargs -P 60 -I{} sh -c 'timeout 1800 uv run python $PROBE {} $REST >> /tmp/pfan.jsonl 2>/dev/null'
echo DONE >> /tmp/pfan.jsonl
EOS
chmod +x /tmp/pfan.sh && nohup /tmp/pfan.sh >/dev/null 2>&1 &"
echo "launched $N x $PROBE on ceph-build; results: ssh … 'grep -o \"{[^}]*}\" /tmp/pfan.jsonl'"
