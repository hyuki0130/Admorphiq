---
type: llm_context
audience: 8B model (Qwen 3 8B Q4)
budget: ≤ 1200 chars — never grow
purpose: single-source-of-truth decision tree the LLM applies every run
---

# Decision Tree (LLM reads this first)

## Inputs
- `avail` ⊆ {1,2,3,4,5,6,7} : available action ids
- `probe_diffs[aid]` : pixels changed after pressing aid
- `probe_diffs[6]` : max pixels among 5 sampled ACTION6 clicks
- `probe_diffs[-6]` : count of those 5 that reacted (0..5)
- `dir_map` : {1,2,3,4} → N/S/E/W inferred from movement

## primary_strategy

Always `adaptive_bfs_solver`. It is the five-phase
observation-entity-goal-plan-loop engine that picks the right
internal algorithm per env. Other whitelist names exist only as
fallback backstops.

## fallback_stack (3 distinct items from whitelist)

1. `click_toggle_detect`
2. `click_all_colors`
3. `click_color_order`

## Hard rules

- `primary_strategy` = `"adaptive_bfs_solver"` every run.
- `fallback_stack` = the three click tools above, in any order.
- Strategy names must be from the whitelist shown in the prompt.
- game_type: movement | click-rare | click-paint | merge-puzzle |
  sort-puzzle | movement-hybrid | paint-hybrid | unknown.
- Never use `game_title` as a decision key (Kaggle rotates titles).

## Why adaptive_bfs_solver is the only first-class choice

It runs observation (probe each action, classify effects) → entity
detection (player / goal / item / palette / executor via color-cluster
matching) → goal inference (paint-fill / navigation / merge / toggle
from observed transitions) → plan synthesis (delegates to the right
internal engine per inferred goal) → learning loop (retries with
wider probes on failure). No game shape in the whitelist benefits
from your routing pick beyond it.
