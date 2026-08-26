# Memory, mirrored INTO the repository

⛔ **Why this directory exists (user directive, 2026-08-26).**

Claude Code's memory lives at `~/.claude/projects/<slug>/memory/` — on ONE machine. Move the project
to another box, or work from a different checkout, and every fact recorded there is gone while the
code and the wiki travel fine. That is not continuity; it is a cache pretending to be a record.

So the memory is mirrored here, in the repo, and **the repo copy is the one that matters**. Anything
worth keeping goes into `.wiki/` or `CLAUDE.md` as well — the machine-local copy is a convenience for
the current session and nothing more.

⚠️ The failure this fixes was live the same day it was written: a full day's findings — the card
never tracking the hidden score, the cheap levers closing, the generic path's wall — were written to
machine-local memory and would not have survived a machine change.

Sync with `scripts/memory_mirror.sh`.
