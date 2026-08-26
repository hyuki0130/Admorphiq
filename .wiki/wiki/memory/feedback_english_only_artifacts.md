---
name: English-Only Artifacts
description: All docs, code, comments, wiki pages, commit messages must be English; Korean only in chat with user
type: feedback
originSessionId: 96a72d05-e421-4801-9b30-810c293777f0
---
All **shippable artifacts** for Admorphiq must be written in English:

- `CLAUDE.md`, `README.md`, `AGENTS.md`, any `*.md` in the repo
- All files under `.wiki/` (raw traces, game pages, strategy pages, schema)
- Python source code, docstrings, comments in `src/`, `scripts/`, `tests/`
- Git commit messages
- Config files, YAML, JSON schemas

**Why:** The ARC Prize 2026 competition is judged internationally; graders and reviewers work in English. Open-sourcing the solution (required for prize eligibility) means the audience is global. Mixed-language artifacts look unprofessional and may confuse evaluators. The user explicitly asked on 2026-04-20 to keep docs/code/comments English so the submission is evaluation-ready.

**Exceptions:**
- Conversational replies to the user in this chat stay in Korean (user's preferred language)
- Agent Behavior Rules in CLAUDE.md that quote forbidden Korean phrases — these are behavior anti-examples, not shipping content

**How to apply:**
- Default to English when writing any file in the repo
- When porting a Korean idea from chat into a doc/code, translate cleanly, don't leave Korean fragments
- Periodically grep for `[가-힣]` in the repo to catch slippage (exclude intentional anti-example quotes)
- If referring to user feedback in a doc, paraphrase in English rather than quote in Korean
