#!/usr/bin/env bash
# Fires when any .wiki/wiki page is written. The project HAS a wiki-authoring skill and a linter,
# and a whole session went by without either being invoked — the round page reached 925 lines with
# two outbound links, ten pages had no index summary, and 29 pages were orphans. A rule in a
# markdown file did not prevent that; this does, because it appears at the moment of the edit.
payload=$(cat)
echo "$payload" | grep -q '\.wiki/wiki/' || exit 0
cat <<'MSG'
[wiki] You are editing .wiki/wiki/. Load the `wiki-authoring` skill before continuing, and obey it:
  1. frontmatter with `type:` first;
  2. a one-sentence `>` blockquote immediately after the H1 (or `description:` on a seeded page);
  3. NO dead [[links]] — the target file must exist;
  4. NO orphans — link the new page from its natural parent IN THE SAME EDIT
     (games <- game_types, concepts <- the game_types/strategies that instantiate it,
      lessons <- the games/strategies the lesson is about);
  5. the per-type required sections from .wiki/schema.md;
  6. density over connectivity — the reader is an 8B model on a char budget.
Then: uv run python scripts/generate_wiki_index.py && uv run python scripts/wiki_lint.py
MSG
exit 0
