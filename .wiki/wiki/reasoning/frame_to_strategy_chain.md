---
type: reasoning
input_type: classified game_type + entity positions (from discovery_phase)
output_type: primary strategy + fallback stack
---

# Frame → Strategy Chain

> Given a classified game_type and identified entities, how to pick a primary strategy and an ordered fallback stack. Used after `[[reasoning/discovery_phase]]` completes.

## The chain

```
discovery_phase output:
  game_type = "movement"
  player_at = (16, 19)
  walls_known = {...}
  goal_at = (45, 30)   # or None if not yet located
  action_mapping = {1: UP, 2: RIGHT, 3: DOWN, 4: LEFT}

↓

selector lookup ([[selector]]):
  game_type = "movement" → primary = bfs_state_space

↓

pre-flight:
  is the reachable state space small enough for BFS? (heuristic: connected walkable cells ≤ 1000)
  if yes: run bfs_state_space with budget 5000
  if no: try graph_explore (sampling search)

↓

if primary stalls after budget:
  escalate to fallback_stack[0]
  repeat
```

## Mapping game_type → primary strategy

| Game type | Primary | Fallback 1 | Fallback 2 |
|-----------|---------|-----------|-----------|
| movement | `bfs_state_space` | `graph_explore` | `wall_avoid` |
| movement-hybrid (rule 3a) | `bfs_state_space` | `graph_explore` | `click_rare` |
| paint-hybrid (rule 3b) | `paint_game` | `click_toggle_detect` | `bfs_state_space` |
| transform-hybrid (rule 3c) | `paint_game` | `bfs_state_space` | `click_rare` |
| sokoban | `bfs_state_space` w/ push | `sokoban_interact` | `bfs_state_space` w/o push |
| platformer | `bp35_platformer`-style gravity BFS | `explore_interact` | `bfs_state_space` |
| click-rare | `click_rare` | `lights_out` | `paint_game` |
| click-paint | `paint_game` | `lights_out` | `click_rare` |
| merge_puzzle | frame-only vacuum planner (target: Phase 8 Step 2b) | `click_rare` near clusters | `click_grid` |
| programming_puzzle | frame-only bit-encoding solver (target: Phase 8 Step 2a) | `seq_search` | `click_grid` |
| sequence | `seq_search` → `seq_repeat` | `pattern_repeat` | `dominant_action` |
| spell_cast | `spell_cast` | `click_grid` | `bfs_state_space` |
| unknown | `bfs_state_space` | `click_rare` | `seq_search` → `spell_cast` |

**None of these entries reference brittle strategies.** If the primary match would be a brittle strategy (e.g. `su15_vacuum`), the LLM must instead pick the frame-only equivalent (once implemented) or fall back to `click_rare` / `bfs_state_space`.

## How to choose between movement-hybrid and paint-hybrid

Both have `avail ⊇ {1, 2, 3, 4} ∪ {6}`. The discriminator is the
**probe-ratio** and **click-responsiveness** pair — see
[[concepts/probe_signature]] for the definitions. Short version:

1. Compute `ratio = max(probe_diffs[1..4]) / max(1, min(probe_diffs[1..4]))`.
2. Read `click_responsive_cells` (the `-6` key).
3. Apply:
   - ratio ≤ 2 AND responsive ≤ 1 → **movement-hybrid** (`bfs_state_space`).
   - ratio ≥ 5 AND responsive ≥ 3 → **paint-hybrid** (`paint_game`).
   - ratio ≥ 5 AND responsive 0-2 → **transform-hybrid** (`paint_game`).
   - intermediate → request more discovery before committing.

Round 3 measured that collapsing these into a single "hybrid" bucket
loses the paint-hybrid class (CD82, class of games where `paint_game`
recovers 6/6 but `bfs_state_space` gets 0/6 because the level-clear
condition is "click the right cells", not "walk the right path"). The
split above is the structural fix.

## Worked Example — SU15 on v2 (where brittle fails)

1. discovery_phase classifies as `merge_puzzle`.
2. selector would pick the canonical merge solver. On v1 this is `su15_vacuum` (brittle). On v2, brittle throws AttributeError.
3. Frame-to-strategy chain must know brittle is off-limits on an unknown game.
4. Primary: once Phase 8 Step 2b lands, it's the frame-only vacuum planner.
5. Until then: fallback stack runs `click_rare near highest-density cluster` as a crude substitute. Not expected to clear, but non-zero if any level is clickable.

## Worked Example — AR25 (movement-hybrid, rule 3a)

1. discovery_phase produces:
   ```
   avail = [1, 2, 3, 4, 5, 6, 7]
   probe_diffs = {1: 109, 2: 109, 3: 109, 4: 109, 6: 0, -6: 0}
   ```
2. Signature read: `avail ⊇ {1..4} ∪ {6}` (rule 3 family). Move-probe
   ratio = 109/109 = 1 (uniform). Click responsive = 0/5 (dead). This
   is **rule 3a — movement-hybrid**.
3. Selector picks `bfs_state_space` primary.
4. Pre-flight: reachable cells ≈ 200, within BFS budget.
5. Run BFS with budget 5000. Level cleared in ~30 actions.
6. No fallback invoked.

## Worked Example — CD82 (paint-hybrid, rule 3b)

1. discovery_phase produces:
   ```
   avail = [1, 2, 3, 4, 5, 6]
   probe_diffs = {1: 1, 2: 1, 3: 201, 4: 201, 6: 1, -6: 5}
   ```
2. Signature read: `avail ⊇ {1..4} ∪ {6}` (rule 3 family). Move-probe
   ratio = 201/1 = 201 (extremely asymmetric — probes 3 and 4 each
   rewrite a third of the frame while probes 1 and 2 barely change it).
   Click responsive = 5/5. This is **rule 3b — paint-hybrid**.
3. The temptation at 8B scale is to see "movement actions present" and
   pick `bfs_state_space`. Resist. The asymmetric probes mean the
   "movement" actions are really level-wide transforms, not player
   motion. `bfs_state_space` would spend the whole budget enumerating
   transforms it can't characterize. `paint_game` reads the responsive
   click grid directly.
4. Selector picks `paint_game` primary; fallback_stack =
   `[click_toggle_detect, bfs_state_space]`.
5. Level cleared by executing the paint-color routine discovered from
   the responsive cells.

## Worked Example — FT09 (click-rare, rule 4)

1. discovery_phase produces:
   ```
   avail = [6]
   probe_diffs = {6: 0, -6: 0}
   ```
2. Signature read: `avail == [6]`, probe 6 = 0 on every sampled cell.
   This is **rule 4 — click-rare**.
3. Selector picks `click_rare` primary; fallback_stack =
   `[lights_out, paint_game]`. The fallbacks exist because rare-click
   games often turn out to be lights-out-style toggles once the first
   click lands — `lights_out` can then finish the board, and
   `paint_game` covers the subset where the rare target causes a
   paint cascade.

## Worked Example — LF52 (unknown recovery)

1. discovery_phase: can't clearly classify — movement-like but no clear player motion on directional probes.
2. Selector dispatches `unknown` → fallback stack: `bfs_state_space` → `click_rare` → `seq_search`.
3. None clear level 1.
4. If no strategy in fallback stack progresses, mark game as "unsolved in this run" and move on. Do NOT loop forever.

## Pitfalls

- **Over-eager primary**: if BFS runs for 50K actions without progress, the game is probably not a state-enumeration problem. Cut off early (budget 5K) and fall through.
- **Fallback starvation**: each strategy in the stack must have an explicit budget. Without it, the first fallback eats all remaining budget.
- **Cycle**: two strategies may repeatedly fail-pass-fail if the agent resets improperly between them. Always `env.reset()` between strategy switches.

## Related

- `[[reasoning/discovery_phase]]` — produces the input classification
- `[[reasoning/hypothesis_check]]` — how to confirm/reject a classification while a strategy runs
- `[[selector]]` — the dispatch table
- `[[strategies/frame_only/bfs_state_space]]` — the most used primary
- `[[lessons/hardcoded_is_anti]]` — why brittle strategies are never in the chain
