#!/usr/bin/env bash
# Fan a probe on ceph-build out of a PRIVATE snapshot of THIS working tree, src included.
#
# ⛔ WHY THIS EXISTS AND WHY IT IS NOT `pfan.sh`. `pfan.sh` ships only `scripts/`, deliberately —
# it is additive and cannot disturb a peer's measurement. That makes it the wrong tool for testing
# an edit to `src/`: the probe would import the BOX's shared copy, which eight agents are editing
# and which does not carry this change at all. That is rule 7n's trap in its expensive form — a
# CHANGED function comes back green against the old code, and the run looks like a measurement.
#
# ⛔ AND IT MUST NOT WRITE TO `~/admorphiq` (rule 7l). Snapshot semantics are `snapgate.sh`'s: a
# private directory, the shared tree read only for its venv and its environment files.
#
#   bash scripts/_lf52_snapfan.sh lf52fire scripts/_lf52_fire.py 6 6
#                                 ^name    ^probe                ^n ^-P
set -uo pipefail
cd "$(dirname "$0")/.."
NAME="${1:?a short name — results land in /tmp/snapfan_<name>.jsonl}"
PROBE="${2:?probe path}"
N="${3:-6}"
PAR="${4:-6}"
KEY="$HOME/VM/keys/nfw-dev.pem"; REMOTE="ubuntu@ceph-build"

grep -q "__main__" "$PROBE" || { echo "⛔ $PROBE has no entrypoint — rule 7e"; exit 1; }

SNAP="snap_$NAME"
tar czf "/tmp/$SNAP.tgz" --exclude='__pycache__' src scripts pyproject.toml
scp -q -i "$KEY" "/tmp/$SNAP.tgz" "$REMOTE:~/" || { echo "⛔ scp failed"; exit 1; }
rm -f "/tmp/$SNAP.tgz"

ssh -o ConnectTimeout=20 -i "$KEY" "$REMOTE" bash -s "$SNAP" "$NAME" "$PROBE" "$N" "$PAR" <<'EOS'
set -u
SNAP="$1"; NAME="$2"; PROBE="$3"; N="$4"; PAR="$5"
export PATH=$HOME/.local/bin:$PATH
rm -rf "$HOME/$SNAP"; mkdir -p "$HOME/$SNAP"
tar xzf "$HOME/$SNAP.tgz" -C "$HOME/$SNAP" && rm -f "$HOME/$SNAP.tgz"
ln -s "$HOME/admorphiq/.venv" "$HOME/$SNAP/.venv" 2>/dev/null
ln -s "$HOME/admorphiq/environment_files" "$HOME/$SNAP/environment_files" 2>/dev/null
ln -s "$HOME/admorphiq/ARC-AGI-3-Agents" "$HOME/$SNAP/ARC-AGI-3-Agents" 2>/dev/null
cd "$HOME/$SNAP"
# ⛔ REFUSE rather than measure the wrong tree. The linked venv installs admorphiq EDITABLE with
# /home/ubuntu/admorphiq/src baked into a .pth, so without PYTHONPATH the snapshot's own src is
# shadowed — and a changed function then passes against the old code in silence (rule 7n).
GOT=$(PYTHONPATH="$HOME/$SNAP/src" .venv/bin/python -c \
  'import admorphiq,sys; sys.stdout.write(admorphiq.__file__)')
case "$GOT" in
  "$HOME/$SNAP/src/"*) echo "# importing $GOT" ;;
  *) echo "⛔ REFUSED: imported $GOT, not the snapshot"; exit 3 ;;
esac
cat > "/tmp/snapfan_$NAME.sh" <<EOF
#!/usr/bin/env bash
export PATH=\$HOME/.local/bin:\$PATH
export PYTHONPATH=$HOME/$SNAP/src
cd $HOME/$SNAP
rm -f /tmp/snapfan_$NAME.jsonl /tmp/snapfan_$NAME.err
seq 1 $N | xargs -P $PAR -I{} sh -c 'timeout 2400 .venv/bin/python $PROBE {} 2>>/tmp/snapfan_$NAME.err | grep "^{" >> /tmp/snapfan_$NAME.jsonl'
echo '{"DONE":1}' >> /tmp/snapfan_$NAME.jsonl
EOF
chmod +x "/tmp/snapfan_$NAME.sh"
nohup "/tmp/snapfan_$NAME.sh" >/dev/null 2>&1 &
echo "launched $N x $PROBE at -P $PAR out of $HOME/$SNAP"
EOS
echo "results: ssh -i $KEY $REMOTE 'cat /tmp/snapfan_$NAME.jsonl'"
