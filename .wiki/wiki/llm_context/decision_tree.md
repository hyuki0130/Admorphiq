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

**Always `inferential_agent` unless a narrower rule applies.** It is the only first-class routing choice. Every other strategy in the whitelist is a fallback.

| Case | primary_strategy |
|---|---|
| Anything at all, default | `inferential_agent` |

The `bfs_state_space` and `click_rare` strategies are no longer in the whitelist (round 8, 2026-04-22 — anchor-banned). Their behavior is reachable via `strat_inferential_agent`'s navigation and toggle plans, which delegate internally. Do not attempt to pick them — the decoder will reject.

## Fill fallback_stack (3 items, distinct)

If primary is `inferential_agent`, fallbacks = `click_toggle_detect`, `click_color_order`, `click_all_colors` (generic click tools for when the agent's plan synthesis needs an exploration-style backstop).

## Hard rules

- Strategy name must be in the whitelist shown in the prompt. Never invent names.
- Set `primary_strategy` = `inferential_agent` unless there is a specific, whitelist-valid reason to deviate.
- fallback_stack has 3 distinct entries, each in the whitelist.
- game_type: movement | click-rare | click-paint | merge-puzzle | sort-puzzle | movement-hybrid | paint-hybrid | unknown.
- Never use `game_title` as a decision key. Kaggle rotates titles.

## Why inferential_agent is the only first-class choice

It runs observation → entity detection → goal inference → plan synthesis → learning loop. The plan synthesis step already selects the right internal strategy (navigation BFS for movement, cluster-click for merge, probe-and-classify for toggle, palette+executor for paint). The routing layer you're in — the one that writes `primary_strategy` — should not try to make that choice. Hand routing over to the agent and let its five phases decide per-env.
