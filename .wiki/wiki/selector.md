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
| 1 | `avail ⊇ {1,2,3,4}`, no 6, movement probes 1-10 each, uniform | `movement` | `bfs_state_space` | `bfs_framehash`, `graph_explore` |
| 2 | `avail ⊇ {1,2,3,4}`, no 6, movement probes all ≥50 and uniform | `transform` | `bfs_state_space` | `bfs_framehash`, `click_rare` |
| 3a | `avail ⊇ {1,2,3,4} ∪ {6}`, movement probes **uniform** (ratio ≤ 2), click 0/5 responsive | `movement-hybrid` | `bfs_state_space` | `push_bfs_grid`, `bfs_framehash` |
| 3b | `avail ⊇ {1,2,3,4} ∪ {6}`, movement probes **asymmetric** (ratio ≥ 5), click ≥ 3/5 responsive | `paint-hybrid` | `interactive_grid_toggle` | `sprite_cluster_interaction`, `click_toggle_detect` |
| 3c | `avail ⊇ {1,2,3,4} ∪ {6}`, movement probes asymmetric, click 0/5 responsive | `transform-hybrid` | `push_bfs_grid` | `interactive_grid_toggle`, `bfs_framehash` |
| 4 | `avail == [6]`, probe 6 returns 0 on all 5 coords | `click-rare` | `click_rare` | `interactive_grid_toggle`, `bfs_framehash` |
| 5 | `avail == [6]`, probe 6 ∈ [1..40], responsive ≥ 4/5 | `programming-puzzle` (bit panel) | `interactive_grid_toggle` | `click_rare`, `raster` |
| 6 | `avail == [6, 7]`, probe 6 ≥ 20, responsive ≥ 3/5 | `merge-puzzle` | `sprite_cluster_interaction` | `interactive_grid_toggle`, `click_all_colors` |
| 7 | `avail ⊇ {5, 6}`, no 1-4 | `sort-puzzle` | `sprite_cluster_interaction` | `click_color_order`, `click_rare` |
| 8 | `avail == [6]`, probe 6 ≥ 100 on first click, responsive ≥ 3/5 | `click-paint` | `interactive_grid_toggle` | `sprite_cluster_interaction`, `click_rare` |
| 9 | everything else | `unknown` | `bfs_framehash` | `click_rare`, `interactive_grid_toggle` |

### The four generic inference classes (G1-G4)

Round 5 (2026-04-22) replaced the per-game brittle strategies
(`paint_game`, `lights_out`, `sb26_sort`, `su15_*`, `tn36_*`,
`ka59_sokoban`, `re86_*`, `wa30_*`, `s5i5_*`, `bp35_*`) with four
generic inference strategies that combine probing + frame analysis +
state-space search. None read game-internal sprite tags or attribute
names. See [[strategies/frame_only/]] for individual pages.

| Class | Strategy name | Replaces (brittle) | Mechanism |
|---|---|---|---|
| **G1** | `interactive_grid_toggle` | `paint_game`, `lights_out`, `tn36_frame_only` | probe stride-K grid → classify each cell (executor / palette / toggle) → search singleton/pair/triple click sequences with executor click last |
| **G2** | `sprite_cluster_interaction` | `su15_frame_only`, `su15_vacuum`, paint-launch | flood-fill clusters → same-color-pair midpoint clicks (closest first) → cluster-centroid clicks for select-and-act |
| **G3** | `push_bfs_grid` | `ka59_sokoban`, `wa30_analytical` | one-shot probe to detect player color + step → BFS on (player_pos, hash(non-player pixels)) — push semantics encoded in state hash |
| **G4** | `bfs_framehash` | universal fallback (formerly bail-out role of `tu93_maze`/`tr87_rotation`/`ls20_grid`/`sk48_snake`) | action-set discovery (probe stride-6 click grid if A6 in avail) → frame-hash BFS with cumulative prefix + adaptive depth + HUD auto-mask |

### Why rule 3 splits into 3a / 3b / 3c

Round 3 bench (2026-04-21) measured that collapsing all "`avail ⊇
{1,2,3,4} ∪ {6}`" games into a single `hybrid` bucket loses the
paint-dominant games entirely:

- **Movement-dominant** (uniform probes, dead click) = 3a — player
  moves through a grid, BFS finds the path → `bfs_state_space`.
- **Paint-dominant** (asymmetric probes, responsive click) = 3b — each
  click paints / reveals, the search is over click sequences not paths
  → `interactive_grid_toggle` (G1).
- **Transform-dominant** (asymmetric probes, dead click) = 3c — moves
  trigger level-wide transforms, click is unused. `push_bfs_grid` (G3)
  treats movement as state-changing actions over a frame-hash state
  space.

The probe-ratio + click-responsiveness discriminator is observable —
the LLM does not need the title to tell 3a from 3b from 3c.

### Title hint (secondary, observation-anchored)

The LLM may read `game_title` from the prompt as a hint, but routing
must be recoverable from the probe signature alone. On the Kaggle
private test set, titles are obfuscated or rotated and a rule that
says "pick X when title is Y" breaks. A rule that says "pick X when
the signature shows Z" survives.

If the LLM is confident the env matches a class above, that class wins
even when the title would suggest a different brittle strategy — the
brittle strategies have been removed from the live whitelist (round 5)
and are no longer LLM-pickable.

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
