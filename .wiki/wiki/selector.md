# Strategy Selector

> Feature-driven dispatch rules the Hypothesis Engine LLM uses to pick
> `primary_strategy` and `fallback_stack` from a `DiscoveryReport`. This
> page is the single source of truth — Python never second-guesses the
> LLM's pick (see [[architecture#Wiki-First-Routing-no-Python-strategy-selection]]).

Input: `DiscoveryReport` from the first 20 discovery actions (see
[[reasoning/discovery_phase]]).
Output: `primary_strategy` + ordered `fallback_stack` (3 distinct
strategies max, all from the **R23 allowlist** below).

## R23 Allowlist (13 strategies, the only valid picks)

```
adaptive_bfs_solver, bfs_state_space, click_all_colors, click_color_order,
click_rare, click_select_move, click_toggle_detect, explore_and_interact,
ls20_grid, sk48_snake, spell_cast, tr87_rotation, tu93_maze
```

Anything not on this list is invalid and will be dropped by
`_validate_whitelist`. Older docs may mention `interactive_grid_toggle`,
`sprite_cluster_interaction`, `push_bfs_grid`, `bfs_framehash`,
`graph_explore`, `raster` — those were R5/R6 generics retired in R11
when the inferential agent (alias `adaptive_bfs_solver`) absorbed
their dispatch internally. Pick `adaptive_bfs_solver` whenever an old
doc references one of those names.

## How to read the probe signature

**CRITICAL: `avail == [X]` means EXACTLY X, not "X is in avail".** Rule 4
applies only when `avail` is the single-element list `[6]`. If `avail`
contains 1, 2, 3, 4, OR 5 alongside 6, rule 4 does NOT match — pick
based on movement / hybrid rules above (1, 2, 3a, 3b, 3c) or fall back
to rule 9 (`adaptive_bfs_solver`). The same `==` semantics apply to
rule 7 (`avail ⊇ {5, 6}` and no 1-4) and rule 8 (`avail == [6]`).

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
support it?**  A title-specific frame-only strategy (e.g. `tu93_maze`,
`tr87_rotation`, `ls20_grid`, `sk48_snake`) is only a good pick when
the observed signature matches that game's structure. A title alone is
not sufficient — if the title says "TU93" but `avail` doesn't include
1-4, the env is a different game under the same label.

## Dispatch Rules (R23 — all picks from allowlist)

Match the first rule that applies. The discriminators above should be
enough to choose confidently; if two rules overlap, pick the more
specific one (smaller match set). All strategy names below are in the
13-strategy allowlist.

| # | Probe signature | game_type | primary_strategy | fallback_stack (distinct) |
|---|----------------|-----------|------------------|---------------------------|
| 1  | `avail ⊇ {1,2,3,4}`, no 6, movement probes 1-10 each, uniform | `movement` | `bfs_state_space` | `adaptive_bfs_solver`, `tu93_maze`, `tr87_rotation` |
| 2  | `avail ⊇ {1,2,3,4}`, no 6, movement probes all ≥ 50 and uniform | `transform` | `bfs_state_space` | `adaptive_bfs_solver`, `click_rare`, `click_toggle_detect` |
| 3a | `avail ⊇ {1,2,3,4} ∪ {6}`, movement probes **uniform** (ratio ≤ 2), click 0/5 responsive | `movement-hybrid` | `bfs_state_space` | `adaptive_bfs_solver`, `click_select_move`, `explore_and_interact` |
| 3b | `avail ⊇ {1,2,3,4} ∪ {6}`, movement probes **asymmetric** (ratio ≥ 5), click ≥ 3/5 responsive | `paint-hybrid` | `adaptive_bfs_solver` | `click_color_order`, `click_toggle_detect`, `click_select_move` |
| 3c | `avail ⊇ {1,2,3,4} ∪ {6}`, movement probes asymmetric, click 0/5 responsive | `transform-hybrid` | `adaptive_bfs_solver` | `bfs_state_space`, `click_toggle_detect`, `explore_and_interact` |
| 4  | `avail == [6]` EXACTLY (no movement actions 1-4), probe 6 returns 0 on all 5 coords | `click-rare` | `click_rare` | `click_toggle_detect`, `adaptive_bfs_solver`, `click_color_order` |
| 5  | `avail == [6]`, probe 6 ∈ [1..40], responsive ≥ 4/5 | `programming-puzzle` (bit panel) | `adaptive_bfs_solver` | `spell_cast`, `click_toggle_detect`, `click_rare` |
| 6  | `avail == [6, 7]`, probe 6 ≥ 20, responsive ≥ 3/5 | `merge-puzzle` | `adaptive_bfs_solver` | `click_color_order`, `click_toggle_detect`, `click_all_colors` |
| 7  | `avail ⊇ {5, 6}`, no 1-4 | `sort-puzzle` | `adaptive_bfs_solver` | `click_color_order`, `click_rare`, `click_all_colors` |
| 8  | `avail == [6]`, probe 6 ≥ 100 on first click, responsive ≥ 3/5 | `click-paint` | `adaptive_bfs_solver` | `click_color_order`, `click_toggle_detect`, `click_rare` |
| 9  | everything else | `unknown` | `adaptive_bfs_solver` | `bfs_state_space`, `click_rare`, `click_toggle_detect` |

### Why every ambiguous rule routes to `adaptive_bfs_solver`

`adaptive_bfs_solver` IS the inferential agent. Internally it runs:
observation → entity detection → goal inference → plan synthesis →
learning loop. It picks one of the six internal plans
([[strategies/frame_only/navigation]], [[strategies/frame_only/merge]],
[[strategies/frame_only/paint_fill]], [[strategies/frame_only/toggle]],
[[strategies/frame_only/lights_out]],
[[strategies/frame_only/click_then_move]]) per inferred goal, and
swaps on falsification (see [[debug/plan_failure_signatures]]).

For paint-hybrid (3b), transform-hybrid (3c), programming-puzzle (5),
merge-puzzle (6), sort-puzzle (7), click-paint (8), unknown (9) — the
correct primary is `adaptive_bfs_solver`. The peer strategies in the
fallback_stack provide a backstop when the inferential agent's plans
all return 0 levels.

For pure movement (rules 1, 2, 3a) the BFS-only path
(`bfs_state_space`) is faster than the full inferential overhead, so
it wins as primary; `adaptive_bfs_solver` becomes the first fallback.

For click-rare (rule 4), `click_rare` is the canonical primary because
its lights-out-style enumeration is the closest match for "click-only,
zero-responsive" envs. Adaptive falls back when click_rare exhausts.

### Why rule 3 splits into 3a / 3b / 3c

Round 3 bench (2026-04-21) measured that collapsing all "`avail ⊇
{1,2,3,4} ∪ {6}`" games into a single `hybrid` bucket loses the
paint-dominant games entirely:

- **Movement-dominant** (uniform probes, dead click) = 3a — player
  moves through a grid, BFS finds the path → `bfs_state_space`.
- **Paint-dominant** (asymmetric probes, responsive click) = 3b — each
  click paints / reveals; the search is over click sequences, not
  paths → `adaptive_bfs_solver`'s `paint_fill` / `click_then_move`
  plans.
- **Transform-dominant** (asymmetric probes, dead click) = 3c — moves
  trigger level-wide transforms; click is unused.
  `adaptive_bfs_solver` routes to `navigation` with frame-hash state.

The probe-ratio + click-responsiveness discriminator is observable —
the LLM does not need the title to tell 3a from 3b from 3c.

### Title hint (secondary, observation-anchored)

The LLM may read `game_title` from the prompt as a hint, but routing
must be recoverable from the probe signature alone. On the Kaggle
private test set, titles are obfuscated or rotated and a rule that
says "pick X when title is Y" breaks. A rule that says "pick X when
the signature shows Z" survives.

If the LLM is confident the env matches a class above, that class wins
even when the title would suggest a different strategy. Title-specific
generics (`tu93_maze`, `tr87_rotation`, `ls20_grid`, `sk48_snake`) are
peer fallbacks for movement signatures only — never bypass the
signature check.

## Anti-patterns (do not recommend)

- Any strategy in [[strategies/brittle/]] — reference only, not for
  execution (they depend on game-internal attribute reads that break
  when the API rotates hashes; see [[lessons/api_hash_rotation_20260421]]).
  These are not in the allowlist anyway, so the schema enum will reject
  them.
- Any strategy NOT in the R23 allowlist above — `interactive_grid_toggle`,
  `sprite_cluster_interaction`, `push_bfs_grid`, `bfs_framehash`,
  `graph_explore`, `raster` are old retired names. Pick
  `adaptive_bfs_solver` instead.
- Duplicate fallback entries — `fallback_stack` MUST be three distinct
  strategy names. Python post-process drops duplicates anyway, but
  picking three different strategies gives the runtime more options.
- `ml_continuation` as primary — it's not in the allowlist either.

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
  "primary_strategy": "<allowlist name, chosen per the dispatch table>",
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
- [[debug/plan_failure_signatures]] — what to do when the picked plan
  returns 0 levels
- [[strategies/frame_only/inferential_agent]] — the agent behind
  `adaptive_bfs_solver`
- [[llm_context/decision_tree]] — compact same-rules reference
