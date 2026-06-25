---
type: llm_context
audience: Qwen 3 8B Q4
budget: ≤ 1500 chars
description: Compact dispatch read first by Qwen — default primary adaptive_bfs_solver, peer-swap only on Observable-Signature match, 3-deep fallback_stack by game shape, re-ask on primary failure via each plan's Falsification Signature + Next-Best.
---

# Decision Tree

## Inputs
`avail`, `probe_diffs[aid]`, `probe_diffs[6]`, `probe_diffs[-6]`,
`dir_map`.

## primary_strategy

Default `"adaptive_bfs_solver"` (5-phase
observation→entity→goal→plan→loop; runs specialised plans
internally). Pick a peer ONLY if env signature matches that peer's
**Observable Signature** at `strategies/frame_only/<name>.md`:
- pure-movement uniform probes → `bfs_state_space`
- click-only NxN grid + sparse responsive → `click_toggle_detect`

## fallback_stack (3 distinct from whitelist)

By shape:
- movement-pure: bfs_state_space / tu93_maze / tr87_rotation
- click-rare: click_rare / click_toggle_detect / click_color_order
- click-paint: click_color_order / click_select_move / click_all_colors
- hybrid: bfs_state_space / explore_and_interact / click_select_move
- programming: spell_cast + 2 click peers
- sokoban-like: bfs_state_space / sk48_snake / tu93_maze

## Rules
- Names from prompt whitelist only.
- Never use `game_title`.
- `game_type` ∈ {movement, click-rare, click-paint, merge-puzzle,
  sort-puzzle, movement-hybrid, paint-hybrid, unknown}.

## On primary failure (R7f)

Runtime re-asks with `{prev, envelope, attempted}`. Read plan-fn
page's **Falsification Signature** + **Next-Best**. Plans:
navigation / merge / paint_fill / toggle / lights_out /
click_then_move.
