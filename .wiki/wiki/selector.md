# Strategy Selector

> Feature-driven dispatch rules the Hypothesis Engine LLM uses to pick
> `primary_strategy` and `fallback_stack` from a `DiscoveryReport`. This
> page is the single source of truth — Python never second-guesses the
> LLM's pick (see [[architecture#Wiki-First-Routing-no-Python-strategy-selection]]).

Input: `DiscoveryReport` from the first 20 discovery actions (see
[[reasoning/discovery_phase]]).
Output: `primary_strategy` + ordered `fallback_stack` (3 strategies max,
all whitelist names).

## How to read the probe signature

The LLM sees `probe_diffs` as a dict `{action_id: pixel_diff, ...}`
plus the derived features. These four questions usually pin down the
dispatch row:

**Q1 — Are movement actions present?**  `avail ⊇ {1, 2, 3, 4}` →
the game accepts directional input. Pure `avail == [6]` means click-only.
`avail ⊇ {5, 6}` with no 1-4 means sort/pick-place-style.

**Q2 — Is click action present and responsive?**  `6 ∈ avail` +
`click_responsive_cells` (the `-6` key) tells you how many of 5 sampled
cells reacted to ACTION6. 0/5 → clicks fall on nothing (FT09 rare-target
structure). 3-5/5 → the game is primarily click-paint / click-toggle.

**Q3 — Are movement probes uniform or asymmetric?**  Compute
`max(probe_diffs[1..4]) / max(1, min(probe_diffs[1..4]))`. Ratio ≤ 2 →
all four movement directions cause similar-size changes (player moves
across a grid → movement game). Ratio ≥ 10 → some moves are no-ops
while others trigger large transformations (paint-reveal or level-wide
overwrite — NOT a movement game even though 1-4 are in `avail`).

**Q4 — Does the title hint at a known game, AND does the signature
support it?**  A title-specific strategy (e.g. `sb26_sort`,
`su15_frame_only`) is only a good pick when the observed signature
matches that game's structure. A title alone is not sufficient — if the
title says "SB26" but `avail` doesn't include 5 and 6, the env is a
different game under the same label (API hash rotation is possible —
see [[lessons/api_hash_rotation_20260421]]).

## Dispatch Rules

Match the first rule that applies. The discriminators above should be
enough to choose confidently; if two rules overlap, pick the more
specific one (smaller match set).

| # | Probe signature | game_type | primary_strategy | fallback_stack |
|---|----------------|-----------|------------------|----------------|
| 1 | `avail ⊇ {1,2,3,4}`, no 6, movement probes 1-10 each, uniform | `movement` | `bfs_state_space` | `graph_explore`, `wall_avoid` |
| 2 | `avail ⊇ {1,2,3,4}`, no 6, movement probes all ≥50 and uniform | `transform` | `bfs_state_space` | `paint_game`, `click_rare` |
| 3a | `avail ⊇ {1,2,3,4} ∪ {6}`, movement probes **uniform** (ratio ≤ 2), click 0/5 responsive | `movement-hybrid` | `bfs_state_space` | `graph_explore`, `click_rare` |
| 3b | `avail ⊇ {1,2,3,4} ∪ {6}`, movement probes **asymmetric** (ratio ≥ 5), click ≥ 3/5 responsive | `paint-hybrid` | `paint_game` | `click_toggle_detect`, `bfs_state_space` |
| 3c | `avail ⊇ {1,2,3,4} ∪ {6}`, movement probes asymmetric, click 0/5 responsive | `transform-hybrid` | `paint_game` | `bfs_state_space`, `click_rare` |
| 4 | `avail == [6]`, probe 6 returns 0 on all 5 coords | `click-rare` | `click_rare` | `lights_out`, `paint_game` |
| 5 | `avail == [6]`, probe 6 ∈ [1..40], responsive ≥ 4/5 | `programming-puzzle` (bit panel) | `tn36_frame_only` | `click_rare`, `raster` |
| 6 | `avail == [6, 7]`, probe 6 ≥ 20, responsive ≥ 3/5 | `merge-puzzle` | `su15_frame_only` | `click_rare`, `click_all_colors` |
| 7 | `avail ⊇ {5, 6}`, no 1-4 | `sort-puzzle` | `sb26_sort` | `click_rare`, `click_color_order` |
| 8 | `avail == [6]`, probe 6 ≥ 100 on first click, responsive ≥ 3/5 | `click-paint` | `paint_game` | `lights_out`, `click_rare` |
| 9 | everything else | `unknown` | `bfs_state_space` | `click_rare`, `lights_out` |

### Why rule 3 splits into 3a / 3b / 3c

Round 3 bench (2026-04-21) measured that collapsing all "`avail ⊇
{1,2,3,4} ∪ {6}`" games into a single `hybrid` bucket with primary
`bfs_state_space` loses the paint-dominant games entirely:

- **AR25** has probes `{1:109, 2:109, 3:109, 4:109, 6:0}` — uniform
  movement, click dead. That's 3a — the player moves through a grid,
  `bfs_state_space` finds the path.
- **CD82** has probes `{1:1, 2:1, 3:201, 4:201, 6:1, -6:5}` — asymmetric
  movement (3 and 4 are much bigger than 1 and 2), click responsive on
  every sampled cell. That's 3b — each click paints / reveals, `paint_game`
  solves it. Trying `bfs_state_space` first wastes budget because the
  state graph is huge and success requires knowing *which cells to click*,
  not *where to walk*.

The probe-ratio discriminator is observable — you don't need the title
to tell 3a from 3b.

### Title-match preference (secondary)

When the title matches a known game (TN36, SU15, RE86, KA59, S5I5,
CN04, LS20, CD82, FT09, SB26) AND the probe signature above picks a
generic strategy, a title-specific strategy often does better *if it
exists in the whitelist for this run*:

- SB26 → `sb26_sort` (sort-puzzle structure)
- TN36 → `tn36_frame_only` (bit-panel programming puzzle)
- SU15 → `su15_frame_only` (merge puzzle)
- FT09 → `lights_out` is an effective generic match for the rare-click
  signature; no FT09-specific entry exists.
- CD82 → `paint_game` is the generic for paint-hybrid (rule 3b); no
  CD82-specific entry exists.

Never invent a strategy name. If the title-specific one is not in the
live whitelist, skip this consideration and use the row from the
dispatch table above.

## Anti-patterns (do not recommend)

- Any strategy in [[strategies/brittle/]] — reference only, not for
  execution (they depend on game-internal attribute reads that break
  when the API rotates hashes; see [[lessons/api_hash_rotation_20260421]]).
- `ml_continuation` as primary — only as continuation after another
  strategy progressed.

## LLM Prompt Template (model-agnostic)

```
You are a strategy selector. Given:
- DiscoveryReport with probe_diffs, dir_map, click_responsive_cells,
  change_topology, color_histogram, symmetry_score, game_title, layer_count
- Matching game_type page from the wiki
- Top-3 similar wiki game pages

Output JSON matching the enforced schema:
{
  "game_type": "<one of: movement | click-rare | click-paint | programming-puzzle | merge-puzzle | sort-puzzle | movement-hybrid | paint-hybrid | transform | transform-hybrid | unknown>",
  "primary_strategy": "<whitelist name, chosen per the dispatch table>",
  "fallback_stack": ["...", "...", "..."],
  "rationale": "<1-2 sentences — cite the probe signature that drove the pick>",
  "confidence": 0.0-1.0,
  "doubt": "<what signal would flip your pick>"
}
```

## Related

- [[architecture]] § Wiki-First Routing — why Python never overrides
  the LLM's pick
- [[reasoning/discovery_phase]] — what probes get collected
- [[reasoning/frame_to_strategy_chain]] — worked examples of the
  signature → strategy chain
- [[concepts/probe_signature]] — glossary of signature terms used here
