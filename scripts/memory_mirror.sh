#!/usr/bin/env bash
# Mirror machine-local Claude memory INTO the repo, so continuity survives a machine change.
# See .wiki/wiki/memory/README.md for why. Run at the end of any session that wrote memory.
set -u
M="$HOME/.claude/projects/-Users-nhn-Workspace-Admorphiq/memory"
cd "$(dirname "$0")/.."
[ -d "$M" ] || { echo "no local memory at $M — nothing to mirror"; exit 0; }
mkdir -p .wiki/wiki/memory
cp "$M"/*.md .wiki/wiki/memory/ 2>/dev/null
# ⛔ MEMORY.md is a plain list by design (the loader wants no frontmatter), but inside the wiki it
# is a page like any other and the index needs a description. Measured: a blind copy overwrote the
# mirror's frontmatter and the linter went red at the end of the session. Re-add it every time.
python3 - <<'PYEOF'
import pathlib
p = pathlib.Path(".wiki/wiki/memory/MEMORY.md")
if p.exists():
    t = p.read_text()
    if not t.startswith("---"):
        p.write_text(
            "---\ntype: index\ndescription: The machine-local memory index, mirrored; each line "
            "points at one durable fact.\n---\n\n" + t
        )
PYEOF
echo "mirrored $(ls "$M"/*.md 2>/dev/null | wc -l | tr -d ' ') files -> .wiki/wiki/memory/"
echo "now: git add -A .wiki/wiki/memory && commit"
