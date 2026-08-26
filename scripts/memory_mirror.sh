#!/usr/bin/env bash
# Mirror machine-local Claude memory INTO the repo, so continuity survives a machine change.
# See .wiki/wiki/memory/README.md for why. Run at the end of any session that wrote memory.
set -u
M="$HOME/.claude/projects/-Users-nhn-Workspace-Admorphiq/memory"
cd "$(dirname "$0")/.."
[ -d "$M" ] || { echo "no local memory at $M — nothing to mirror"; exit 0; }
mkdir -p .wiki/wiki/memory
cp "$M"/*.md .wiki/wiki/memory/ 2>/dev/null
echo "mirrored $(ls "$M"/*.md 2>/dev/null | wc -l | tr -d ' ') files -> .wiki/wiki/memory/"
echo "now: git add -A .wiki/wiki/memory && commit"
