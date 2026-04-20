---
type: game_type
examples: [LF52]
refactor_status: fallback_stack
---

# Unknown Game Type

> Games that do not yet fit any recognized pattern. Use the general fallback strategy stack.

## Fallback strategy stack

1. [[../strategies/frame_only/bfs_state_space]]
2. [[../strategies/frame_only/click_rare]]
3. [[../strategies/frame_only/seq_repeat]]
4. [[../strategies/frame_only/spell_cast]]
5. If still stalled: invoke LLM Hypothesis Engine on the wiki to propose a new `game_type`

## Games currently in this bucket

| Game | v1 | v2 | Notes |
|------|-----|-----|-------|
| [[../games/LF52]] | 0/10 | n/a | silent regression — needs Phase 8 Step 4 bisect to recover |
| [[../games/SK48]] | 0/8 | 0/8 | silent regression — same |

## How to move a game out of "unknown"

Once one of the fallback strategies clears a level or first-20-action discovery yields
a repeatable pattern, create/assign a proper `game_type` page and migrate the game
entry to it. Update `wiki/selector.md` dispatch rule.
