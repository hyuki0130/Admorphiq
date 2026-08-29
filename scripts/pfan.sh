#!/usr/bin/env bash
# Fan ANY probe across seeds/bands on ceph-build, out of a PRIVATE SNAPSHOT. The default shape of a
# probe.
#
#   bash scripts/pfan.sh lf52l6 scripts/_lf52_verbs.py 30 "" 8
#                        ^name  ^probe                 ^n  ^arg ^-P
#
# ⛔ IT USED TO CORRUPT OTHER AGENTS' RESULTS. It wrote to a fixed `/tmp/pfan.jsonl` and `rm -f`d it
# at launch — fine for one worker, destructive for eight: measured 2026-08-29, a 30-way lf52 fan came
# back with 359 lines and NOT ONE of its own, because a peer's fan owned the file, and this fan's own
# `rm` had already destroyed the peer's accumulated results. NAME is required for that reason.
#
# ⛔ AND IT HARDCODED -P 60. The 60-core cap is a TOTAL across everyone on the box, not a per-worker
# budget; one agent per game each fanning 60-way put the box at 129 processes and load 64.6, where
# SSH stops answering. Parallelism is an explicit argument with a modest default.
#
# ⛔ AND IT COULD NOT TEST AN EDIT TO `src/` — reported by the lf52 agent 2026-08-29 and it is rule
# 7n's silent trap in a second place. It shipped ONLY `scripts/`, extracted it INTO the shared
# `~/admorphiq`, and ran from there, so every probe imported the box's shared `src` no matter what
# the author had just changed. A new symbol fails loudly; a CHANGED function passes against the old
# code, which is the expensive half. It also wrote to the shared tree, which rule 7l forbids outright.
#
# Now it takes a private snapshot of the WORKING TREE (`src` + `scripts`, uncommitted edits included
# — a probe is a red-green loop, not a gate), links the venv and the game data read-only, and REFUSES
# to run if the `admorphiq` it would import is not the snapshot's.
set -u
cd "$(dirname "$0")/.."
NAME="${1:?a short name for this fan, e.g. lf52l6 — results go to /tmp/pfan_<name>.jsonl}"
PROBE="${2:?probe path, e.g. scripts/_probe.py}"
N="${3:-30}"
REST="${4:-}"
PAR="${5:-8}"
KEY="$HOME/VM/keys/nfw-dev.pem"
REMOTE="ubuntu@ceph-build"
SSH=(ssh -o ConnectTimeout=20 -i "$KEY" "$REMOTE")
SNAP="pfan_$NAME"

# rule 7e: a probe that prints nothing and exits 0 has lost its entrypoint.
grep -q "__main__" "$PROBE" || { echo "⛔ $PROBE has no entrypoint — rule 7e"; exit 1; }

tar czf "/tmp/_$SNAP.tgz" --exclude='__pycache__' src scripts 2>/dev/null
scp -q -i "$KEY" "/tmp/_$SNAP.tgz" "$REMOTE:~/" || { echo "⛔ scp failed"; exit 1; }
rm -f "/tmp/_$SNAP.tgz"

# ⚠️ Pass through the ENVIRONMENT, not positionally. An empty REST (`""`, the common case — most
# probes take only a seed) makes `bash -s a b c "" e` bind $5 to nothing under `set -u`, and the
# remote script dies with "$5: unbound variable" AFTER the launcher has already printed "launched".
# A launcher that reports success for a job that never started is the fail-open shape again.
"${SSH[@]}" "SNAP='$SNAP' PROBE='$PROBE' N='$N' REST='$REST' PAR='$PAR' bash -s" <<'EOS'
set -u
export PATH=$HOME/.local/bin:$PATH
rm -rf "$HOME/$SNAP"; mkdir -p "$HOME/$SNAP"
tar xzf "$HOME/_$SNAP.tgz" -C "$HOME/$SNAP" && rm -f "$HOME/_$SNAP.tgz"
# Read-only links: the venv, the games, the recorded traces, the official framework dir.
for d in .venv environment_files data ARC-AGI-3-Agents; do
  ln -s "$HOME/admorphiq/$d" "$HOME/$SNAP/$d" 2>/dev/null
done
cd "$HOME/$SNAP"

# ⛔ The venv installs admorphiq EDITABLE, and `_editable_impl_admorphiq.pth` carries the absolute
# path /home/ubuntu/admorphiq/src baked in at install time. Without PYTHONPATH the snapshot's own
# src/ is SHADOWED and the probe measures the shared tree. Refuse rather than report.
PYTHONPATH="$HOME/$SNAP/src" .venv/bin/python -c \
  "import admorphiq,sys; p=admorphiq.__file__; sys.exit(0 if p.startswith('$HOME/$SNAP/') else print('SHADOWED',p) or 1)" \
  || { echo "⛔ the snapshot is shadowed by the box's install — refusing to fan"; exit 1; }

cat > "/tmp/$SNAP.sh" <<INNER
#!/usr/bin/env bash
export PATH=\$HOME/.local/bin:\$PATH
export PYTHONPATH="\$HOME/$SNAP/src"
cd "\$HOME/$SNAP"
rm -f /tmp/$SNAP.jsonl /tmp/$SNAP.err
seq 1 $N | xargs -P $PAR -I{} sh -c 'timeout 1800 .venv/bin/python $PROBE {} $REST 2>>/tmp/$SNAP.err | grep "^{" >> /tmp/$SNAP.jsonl'
echo DONE >> /tmp/$SNAP.jsonl
INNER
chmod +x "/tmp/$SNAP.sh"
nohup "/tmp/$SNAP.sh" >/dev/null 2>&1 &
echo "fan launched out of ~/$SNAP (the shared tree is untouched)"
EOS

echo "launched $N x $PROBE at -P $PAR"
echo "results:  ssh -i $KEY $REMOTE 'grep -o \"{.*}\" /tmp/$SNAP.jsonl'"
echo "errors:   ssh -i $KEY $REMOTE 'tail -20 /tmp/$SNAP.err'"
