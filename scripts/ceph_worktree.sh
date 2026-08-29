#!/usr/bin/env bash
# Give a worker its OWN tree on ceph-build. One directory per game, never the shared one.
#
# ⛔ WHY. `~/admorphiq` was the only tree on the box, overwritten by a whole-tree tar on every sync.
# That was fine while one person worked serially, and it is why `gate_tool.sh` grew a check that
# REFUSES a verdict when the tree moves mid-measurement — a guard around a shared resource instead of
# a fix for it. The moment eight agents ran at once (2026-08-29) they began overwriting each other's
# source while measuring, so every number was suspect and the box hit 129 processes.
#
#   bash scripts/ceph_worktree.sh bp35      # creates ~/wt/bp35 from the local tree, prints the path
#
# The caller then runs everything with `cd ~/wt/<name>`, so two workers cannot touch the same bytes.
set -u
cd "$(dirname "$0")/.."
NAME="${1:?worker name, e.g. the game}"
KEY="$HOME/VM/keys/nfw-dev.pem"
REMOTE="ubuntu@ceph-build"

tar czf "/tmp/_wt_$NAME.tgz" --exclude=.venv --exclude=.git --exclude='__pycache__' \
    src scripts tests pyproject.toml uv.lock 2>/dev/null
scp -q -i "$KEY" "/tmp/_wt_$NAME.tgz" "$REMOTE:~/" && rm -f "/tmp/_wt_$NAME.tgz"
ssh -o ConnectTimeout=20 -i "$KEY" "$REMOTE" "
  export PATH=\$HOME/.local/bin:\$PATH
  mkdir -p ~/wt/$NAME && cd ~/wt/$NAME
  # environment_files are large, read-only and identical for everyone — link, do not copy.
  [ -e environment_files ] || ln -s ~/admorphiq/environment_files environment_files
  [ -e ARC-AGI-3-Agents ] || ln -s ~/admorphiq/ARC-AGI-3-Agents ARC-AGI-3-Agents 2>/dev/null || true
  tar xzf ~/_wt_$NAME.tgz && rm -f ~/_wt_$NAME.tgz
  uv sync -q 2>/dev/null
  echo \"worktree ready: ~/wt/$NAME\"
"
