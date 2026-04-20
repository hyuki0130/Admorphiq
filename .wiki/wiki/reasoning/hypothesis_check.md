---
type: reasoning
input_type: current game_type hypothesis + frames seen so far
output_type: keep | revise | escalate
---

# Hypothesis Check

> While a strategy runs, periodically verify that the game_type classification from `[[reasoning/discovery_phase]]` still fits. If evidence contradicts the hypothesis, revise before committing more budget.

## Why check

Classification from the first 20 actions is a cheap guess. As more frames accumulate, the evidence may point elsewhere. Running an inappropriate strategy for 500 actions costs the entire level budget. Cheap verification prevents expensive failure.

## The check (every ~50 actions)

For the current `game_type` hypothesis, evaluate these signals:

### Movement hypothesis
- ✅ Player cluster moves consistently in response to directional actions
- ✅ Walls consistently block movement
- ❌ Level has not progressed after 100 directional moves
- ❌ Goal region never becomes reachable (suggests missing mechanic like pushable block or toggle)

If 2+ ❌ signals appear: revise to `sokoban` (if blocks present) or `hybrid` (if interactive objects present).

### Click hypothesis
- ✅ Specific clicks cause localized state changes
- ✅ Level progresses when a distinct cluster is clicked
- ❌ No click has ever caused a state change
- ❌ Clicks cause frame-wide reset (suggests wrong click semantics; try ACTION5 or ACTION7)

### Merge hypothesis
- ✅ Same-color clusters combine into higher-color after vacuum
- ✅ Enemy-like clusters downgrade fruits on contact
- ❌ Clusters don't move at all in response to clicks (merge_puzzle needs vacuum/attract mechanic)

### Programming-puzzle hypothesis
- ✅ A grid of small cells toggles on click; a distinct button animates a player on click
- ❌ No animation observed from any click (or no clickable cells form a grid)

## Revise-or-escalate decision

```
if hypothesis_matches_evidence:
  continue with current strategy
elif revised_hypothesis_is_clear:
  reset env, switch to new game_type's primary strategy
else:
  escalate to fallback stack under [[game_types/unknown]]
```

**Budget rule**: a hypothesis check happens at every ensemble strategy-switch point. Budget for verification itself is ≤5 actions (just look at accumulated diffs).

## Worked Example — BP35 discovered as movement, revised to platformer

1. Initial classification: `movement` (ACTION1/2 move player lateraly).
2. After 50 actions with BFS: player keeps falling when ACTION1 is held. Goal on upper floor but no ACTION3/4 for UP. BFS stalls.
3. Hypothesis check: gravity signal dominates; ACTION6 can destroy blocks (observed in a probe).
4. Revise to `platformer` → dispatch `bp35_platformer` style solver (gravity-aware BFS with block destruction).
5. Level clears.

## Worked Example — Cannot escape unknown

1. LF52 after 20 actions of discovery: no clear classification.
2. `unknown` fallback stack runs `bfs_state_space` for 5K actions: no progress.
3. Runs `click_rare` for 500 actions: no progress.
4. Runs `seq_search` for 500 actions: no progress.
5. Give up the level, record failure reason. (Does not loop — finite fallback stack is the guard.)

## Pitfalls

- **Sunk-cost fallacy**: don't continue with a failing hypothesis because you already spent budget. The remaining budget is all that matters.
- **Revision thrash**: if you revise every 50 actions, you never exploit. Once revised, commit for at least 100 actions before re-checking.
- **False negatives**: some mechanics need many actions to become visible (e.g. sokoban with a far goal). If no progress but also no contradicting evidence, keep going to the next budget checkpoint.

## Related

- `[[reasoning/discovery_phase]]`
- `[[reasoning/frame_to_strategy_chain]]`
- `[[game_types/unknown]]` — the last-resort fallback stack
- `[[lessons/frame_diff_as_probe]]`
