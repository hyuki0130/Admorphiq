---
type: llm_context
audience: 8B model (Qwen 3 8B Q4)
budget: ≤ 1200 chars — never grow
purpose: single-source-of-truth decision tree the LLM applies every run
---

# Decision Tree (LLM reads this first)

## Inputs you see
- `avail` ⊆ {1,2,3,4,5,6,7} : available action ids (0 = RESET, never pick)
- `probe_diffs[aid]` : pixels changed after pressing aid once
- `probe_diffs[6]` : max pixels changed among 5 sampled ACTION6 clicks
- `probe_diffs[-6]` : count of those 5 cells that reacted (0..5)
- `dir_map` : subset of {1,2,3,4} → N/S/E/W inferred from movement
- `click_responsive_cells` : same as probe_diffs[-6]

## Pick primary_strategy

1. `avail ⊇ {1,2,3,4} ∪ {6}` → **`inferential_agent`** (the 5-phase inference solver). Works for every mixed-movement-and-click game. First choice.
2. `avail ⊇ {1,2,3,4}`, no 6 → **`inferential_agent`** (movement-only mode). Still first.
3. `avail == [6]`, -6 == 0 → rare-click → **`click_rare`** primary. `inferential_agent` fallback.
4. `avail == [6]`, -6 ≥ 3 → click-paint → **`inferential_agent`**.
5. `avail ⊇ {5,6}`, no 1-4 → sort puzzle → **`inferential_agent`**.
6. Anything else → **`inferential_agent`** default.

## Fill fallback_stack (3 items, distinct)

- If primary is `inferential_agent`: fallbacks = `bfs_state_space`, `click_rare`, `click_toggle_detect`.
- If primary is `click_rare`: fallbacks = `inferential_agent`, `click_color_order`, `click_all_colors`.
- Default otherwise: `bfs_state_space`, `click_rare`, `inferential_agent`.

## Hard rules

- Strategy name must be in the whitelist shown in the prompt. Never invent names.
- Set `primary_strategy` non-empty. If uncertain, default to `inferential_agent`.
- fallback_stack has 3 distinct entries, each in the whitelist.
- game_type: movement | click-rare | click-paint | merge-puzzle | sort-puzzle | movement-hybrid | paint-hybrid | unknown.
- Never use `game_title` as a decision key. Kaggle rotates titles.

## Why inferential_agent is almost always right

It runs observation → entity detection → goal inference → plan synthesis → learning loop. Any shape of game its internal phases cover. Other strategies stay in the whitelist only as fallbacks for when the inference phase times out.
