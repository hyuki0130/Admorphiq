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
| sokoban | `bfs_state_space` w/ push | `sokoban_interact` | `bfs_state_space` w/o push |
| platformer | `bp35_platformer`-style gravity BFS | `explore_interact` | `bfs_state_space` |
| click | `click_rare` | `click_all_colors` | `click_grid` (raster) |
| merge_puzzle | frame-only vacuum planner (target: Phase 8 Step 2b) | `click_rare` near clusters | `click_grid` |
| programming_puzzle | frame-only bit-encoding solver (target: Phase 8 Step 2a) | `seq_search` | `click_grid` |
| sequence | `seq_search` → `seq_repeat` | `pattern_repeat` | `dominant_action` |
| spell_cast | `spell_cast` | `click_grid` | `bfs_state_space` |
| hybrid | `explore_interact` | `bfs_state_space` | `click_rare` |
| unknown | `bfs_state_space` | `click_rare` | `seq_search` → `spell_cast` |

**None of these entries reference brittle strategies.** If the primary match would be a brittle strategy (e.g. `su15_vacuum`), the LLM must instead pick the frame-only equivalent (once implemented) or fall back to `click_rare` / `bfs_state_space`.

## Worked Example — SU15 on v2 (where brittle fails)

1. discovery_phase classifies as `merge_puzzle`.
2. selector would pick the canonical merge solver. On v1 this is `su15_vacuum` (brittle). On v2, brittle throws AttributeError.
3. Frame-to-strategy chain must know brittle is off-limits on an unknown game.
4. Primary: once Phase 8 Step 2b lands, it's the frame-only vacuum planner.
5. Until then: fallback stack runs `click_rare near highest-density cluster` as a crude substitute. Not expected to clear, but non-zero if any level is clickable.

## Worked Example — AR25 (happy path)

1. discovery_phase classifies as `movement` with player + goal + partial wall map.
2. Selector picks `bfs_state_space`.
3. Pre-flight: reachable cells ≈ 200, well within BFS budget.
4. Run BFS with budget 5000. Level cleared in ~30 actions.
5. No fallback invoked.

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
