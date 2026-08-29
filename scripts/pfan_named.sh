#!/usr/bin/env bash
# pfan.sh, but with a NAMED result file.
#
# ⛔ WHY. `scripts/pfan.sh` writes to a FIXED `/tmp/pfan.jsonl` and `rm -f`s it at launch. On a box
# several agents share that is a COLLISION: measured 2026-08-29, a 30-way lf52 fan came back with
# 359 lines and not one of its own, because another agent's fan owned the file — and this fan's own
# `rm` had already destroyed that agent's earlier results. A fan-out that cannot tell its own
# output from someone else's is not a measurement.
#
#   bash scripts/pfan_named.sh lf52l6 scripts/_lf52_l6_verbs.py 30 [extra-arg] [-P N]
set -u
cd "$(dirname "$0")/.."
NAME="${1:?a short name for this fan, e.g. lf52l6}"
PROBE="${2:?probe path}"
N="${3:-60}"
REST="${4:-}"
PAR="${5:-24}"
KEY="$HOME/VM/keys/nfw-dev.pem"
REMOTE="ubuntu@ceph-build"
SSH=(ssh -o ConnectTimeout=20 -i "$KEY" "$REMOTE")
OUT="/tmp/pfan_${NAME}.jsonl"

grep -q "__main__" "$PROBE" || { echo "⛔ $PROBE has no entrypoint — rule 7e"; exit 1; }

tar czf /tmp/_pfan_$NAME.tgz scripts 2>/dev/null
scp -q -i "$KEY" /tmp/_pfan_$NAME.tgz "$REMOTE:~/" && rm -f /tmp/_pfan_$NAME.tgz
"${SSH[@]}" "cat > /tmp/pfan_$NAME.sh <<'EOS2'
#!/usr/bin/env bash
export PATH=\$HOME/.local/bin:\$PATH
cd ~/admorphiq
tar xzf ~/_pfan_$NAME.tgz
rm -f $OUT $OUT.err
seq 1 $N | xargs -P $PAR -I{} sh -c 'timeout 2400 uv run python $PROBE {} $REST 2>>$OUT.err | grep \"^{\" >> $OUT'
echo DONE >> $OUT
EOS2
chmod +x /tmp/pfan_$NAME.sh && nohup /tmp/pfan_$NAME.sh >/dev/null 2>&1 &"
echo "launched $N x $PROBE (-P $PAR) on ceph-build -> $OUT"
