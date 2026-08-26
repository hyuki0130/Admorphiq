---
name: Proactive Doc Sync
description: Update CLAUDE.md and project memories without being asked when phase/state changes
type: feedback
originSessionId: 96a72d05-e421-4801-9b30-810c293777f0
---
When project state changes (game clears, phase transitions, score jumps, new strategy added, LLM/model decisions), proactively update:
1. **CLAUDE.md** — Current Status section, Phase status, hardcoding debt list
2. **memory/project_current_state.md** — score, per-game depth, next-phase tasks
3. **memory/MEMORY.md** index entries

**Why:** User explicitly objected ("왜 업데이트하면서 진행을 안한거야? 컨텍스트에 그렇게 안나와있니? 없으면 보강을 해!") when I noticed CLAUDE.md was stale (11/25 listed vs actual 25/25) but only suggested updates instead of doing them. Project moves fast — stale docs cause downstream wrong decisions.

**How to apply:**
- After any commit that changes game-clear count, score, phase status, or strategy roster → update docs in the same turn, not as a separate suggestion
- After any new model/library/architecture decision (e.g., LLM choice) → write it to CLAUDE.md immediately
- Verify actual state from commits/logs/code before writing — don't trust stale CLAUDE.md sections
- Treat CLAUDE.md as the live source-of-truth for downstream agents (executor, planner, etc.); a stale CLAUDE.md will mislead them
- Never just propose "옵션 A/B/C, 어떤 거 할까요?" for routine doc-sync — pick the full update and execute
