# Strategy Selector

> Feature-driven dispatch rules used by the Hypothesis Engine LLM (selected LLM (Task #11 winner)).

**Enforcement note.** Rules on this page are read by the LLM as guidance
but are NOT reliably honored at 8B-14B scale under long wiki context.
Every rule this project depends on must also have a Python-level
enforcement (decoder enum, retrieval seed, or hypothesis post-processing)
— see [[architecture#Routing-Rules-Require-Python-Reinforcement]]. The
table below is the shared source of truth for both the LLM prompt and the
Python-side enforcement; when a row changes, both sides update together.
Measured non-compliance: R6 (14B ignored rule 4's fallback_stack update),
R7 round 1 (Qwen skipped title-match on FT09/CD82/SB26/AR25 — see
[[lessons/schema_enforcement_round1_20260421]]), round 2 (Qwen skipped
rule 3 on AR25/CD82/M0R0 — `explore_and_interact` / `click_select_move`
preferred over `bfs_state_space`, `paint_game` left out entirely).

Python reinforcements live in `src/admorphiq/hypothesis/wiki_agent.py`:
- Rule 3 (hybrid): `_augment_hybrid_rule3` — when `avail ⊇ {1,2,3,4,6}`,
  prepend `bfs_state_space`, `paint_game`, `click_toggle_detect` into
  fallback_stack (primary preserved, cap 3).
- Rule 4 (click-rare): `_augment_click_only_rule4` — when `avail == [6]`
  and probe 6 returned 0 everywhere, prepend `lights_out`, `paint_game`.
- Title match: `_augment_with_title_match` — when the title substring
  matches a whitelist entry, seed primary if empty or prepend to fallback.

Input: game classification output (from first 10-20 discovery actions) + frame statistics.
Output: ordered list of strategies to try.

## Classification Features

| Feature | Source | Options |
|---------|--------|---------|
| `available_actions` | `FrameData.available_actions` | subset of {1,2,3,4,5,6,7} |
| `has_action6` | derived | bool |
| `layer_count` | `len(FrameData.frame)` | 1..N |
| `dominant_colors` | histogram | list of color indices |
| `player_candidates` | color clustering + motion diff | 0..k positions |
| `changer_candidates` | static regions after ACTION1-5 | list of regions |
| `grid_like` | regular lattice detection | bool |

## Dispatch Rules (probe-signature → primary_strategy)

Read the DiscoveryReport and match the first rule that applies. Probe keys:
`{aid: pixel_diff}`; key `-6` is the count of responsive click cells out of
the 5-coord sample.

| # | Probe signature | game_type | primary_strategy | fallback_stack |
|---|----------------|-----------|------------------|----------------|
| 1 | `avail` has 1-4, no 6, diffs 1-10 each | `movement` | `bfs_state_space` | `click_rare`, `raster` |
| 2 | `avail` has 1-4, diffs all ≥50 | `transform` | `bfs_state_space` | `paint_game`, `click_rare` |
| 3 | `avail` has 1-4 + 6, mixed diffs | `hybrid` | `bfs_state_space` | `click_toggle_detect`, `paint_game`, `click_rare` |
| 4 | `avail == [6]`, probe 6 returns 0 on all 5 coords | `click` (rare targets) | `click_rare` | `lights_out`, `paint_game`, `click_all_colors` |
| 5 | `avail == [6]`, probe 6 in [1..40], `-6 ≥ 4` (≥4/5 click cells responsive) | `programming_puzzle` (bit panel) | `tn36_frame_only` | `click_rare`, `raster` |
| 6 | `avail == [6, 7]`, probe 6 ≥ 20, most coords responsive | `merge_puzzle` | `su15_frame_only` | `click_rare`, `click_all_colors` |
| 7 | `avail` has 5 + 6, no 1-4 | `sort_puzzle` (SB26-style) | `sb26_sort` | `click_rare`, `click_color_order` |
| 8 | `avail` has 6 only, probe 6 ≥ 100 on first click | `click` (paint) | `paint_game` | `lights_out`, `click_rare` |
| 9 | everything else | `unknown` | `bfs_state_space` | `click_rare`, `lights_out`, `raster` |

**When the title matches a known game** (TN36, SU15, RE86, KA59, S5I5, CN04,
LS20, CD82, FT09, SB26), prefer the corresponding frame-only strategy **only
if that name exists in the Available Strategies list for this run**. Never
invent a strategy name.

## Anti-patterns (do not recommend)

- Any strategy in [[strategies/brittle/]] — only for reference, not execution
- `ml_continuation` as primary — only as continuation after another strategy progressed

## LLM Prompt Template (model-agnostic; target: selected LLM from Task #11)

```
You are a strategy selector. Given:
- Game features: {features}
- Wiki game_type page: {matching_game_type_md}
- Top-3 similar game pages: {top3_game_md}

Output JSON:
{
  "game_type": "<one of movement|click|programming_puzzle|merge_puzzle|sokoban|other>",
  "primary_strategy": "<frame_only strategy name>",
  "fallback_stack": ["...", "..."],
  "rationale": "<1-2 sentences>"
}
```
