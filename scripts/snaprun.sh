#!/usr/bin/env bash
# Run a probe on ceph-build out of a PRIVATE snapshot — never writing the shared ~/admorphiq.
#
# ⛔ WHY THIS EXISTS AND `pfan.sh` DOES NOT SUFFICE. `pfan.sh` ships `scripts/` and `tar xzf`s it
# into `~/admorphiq`, which is SHARED. Measured 2026-08-29: two agents handed the same brief wrote
# probes at the same obvious path, and one fan would have swapped the code under the other's
# in-flight 25-game run with nothing in either output to show it. That is rule 7l's contamination —
# a measurement must not write to a shared path — applied to fans rather than gates.
#
# The snapshot is the WORKING TREE (a probe under development is uncommitted by definition), so
# this is for probes only; a GATE still goes through `snapgate.sh`, which archives HEAD.
#
#   bash scripts/snaprun.sh hctrl scripts/_handover_control.py 6 "ls20 re86 su15" 4000
#                           ^name ^probe                       ^-P ^args, one run each  ^extra
set -uo pipefail
cd "$(dirname "$0")/.."
NAME="${1:?a short name, e.g. hctrl — the snapshot and the result file are named after it}"
PROBE="${2:?probe path under scripts/}"
PAR="${3:-4}"
ARGS="${4:?space-separated arguments, one run per item}"
EXTRA="${5:-}"
KEY="$HOME/VM/keys/nfw-dev.pem"
REMOTE="ubuntu@ceph-build"
SSH=(ssh -o ConnectTimeout=20 -i "$KEY" "$REMOTE")

grep -q "__main__" "$PROBE" || { echo "⛔ $PROBE has no entrypoint — rule 7e"; exit 1; }

LOAD=$("${SSH[@]}" "cut -d' ' -f1 /proc/loadavg")
echo "=== ceph-build load $LOAD (cap 60 TOTAL across all agents — rule 1)"

COPYFILE_DISABLE=1 tar --no-xattrs -czf "/tmp/_snaprun_$NAME.tgz" src scripts 2>/dev/null
scp -q -i "$KEY" "/tmp/_snaprun_$NAME.tgz" "$REMOTE:~/" || { echo "⛔ scp failed"; exit 1; }
rm -f "/tmp/_snaprun_$NAME.tgz"

"${SSH[@]}" "cat > /tmp/snaprun_$NAME.sh <<'EOS2'
#!/usr/bin/env bash
export PATH=\$HOME/.local/bin:\$PATH
rm -rf \$HOME/snap_$NAME && mkdir -p \$HOME/snap_$NAME
tar xzf \$HOME/_snaprun_$NAME.tgz -C \$HOME/snap_$NAME 2>/dev/null
rm -f \$HOME/_snaprun_$NAME.tgz /tmp/snaprun_$NAME.jsonl
# ⛔ cwd is the SHARED tree because that is where environment_files lives and the Arcade reads it
# relative to cwd; the CODE comes from the snapshot because the probe inserts its own ../src at
# sys.path[0] (score_efficiency.py:35's trick, and rule 7n's fix).
cd \$HOME/admorphiq
echo $ARGS | tr ' ' '\n' | xargs -P $PAR -I{} sh -c 'timeout 3000 uv run python \$HOME/snap_$NAME/$PROBE {} $EXTRA 2>/dev/null | grep \"^{\" >> /tmp/snaprun_$NAME.jsonl'
echo DONE >> /tmp/snaprun_$NAME.jsonl
EOS2
chmod +x /tmp/snaprun_$NAME.sh && nohup /tmp/snaprun_$NAME.sh >/dev/null 2>&1 &"
echo "launched: $ARGS  (-P $PAR) out of ~/snap_$NAME"
echo "results:  ssh -i $KEY $REMOTE 'cat /tmp/snaprun_$NAME.jsonl'"
