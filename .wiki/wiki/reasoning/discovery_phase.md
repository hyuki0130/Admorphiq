---
type: reasoning
input_type: frame + first 10-20 action responses
output_type: game_type classification + entity roles
---

# Discovery Phase

> The first 10–20 actions on any unseen game are a **probing session**, not a solve attempt. The goal is to classify the game and identify its entities, so the downstream solver picks the right strategy.

## Why a discovery phase

The Kaggle-time LLM sees a new game with no prior knowledge of its mechanics. Jumping into a strategy immediately wastes the budget on the wrong approach. The discovery phase gathers evidence cheaply (20 actions out of ~80 per level is affordable) and narrows the hypothesis space.

## Chain: observation → classification → entities

### Step 1 — Observe the opening frame
Record:
- `len(frame)` — number of layers
- `available_actions` — subset of `{1,2,3,4,5,6,7}`
- Color histogram — how many distinct colors, which dominate
- Obvious clusters — connected components of the same color

### Step 2 — Probe each available simple action
For each action in `available_actions` ∩ `{ACTION1..5}`:
- Press it once from the reset state
- Diff the frame
- Classify the action:

| Diff signal | Action interpretation |
|-------------|----------------------|
| A cluster shifted by ≈1 cell in a direction | directional movement |
| A cluster shifted by many pixels or fell | platformer / gravity, see `[[concepts/gravity]]` |
| A localized cell flipped color | toggle (lights-out-like) |
| Multiple clusters moved together with the player | pushable blocks, see `[[concepts/pushable_block]]` |
| Different clusters merged into fewer clusters | merge mechanic, see `[[concepts/merge_mechanic]]` |
| No change | action is no-op in this state; try again later |
| Level_up triggered | action completed the level immediately — record and move on |

### Step 3 — Probe ACTION6 if available
Try 5–10 random `ACTION6(x,y)` clicks at widely-spaced positions. For each:
- Did the clicked cell change? → click-toggle game
- Did a sprite move toward the click? → merge/vacuum game, see `[[concepts/merge_mechanic]]`
- Did a cursor appear at the click? → click-select-move game
- No change most of the time, but one position caused a cascade? → constraint-based click (lights-out-like)

### Step 4 — Classify into `game_type`

Using the Step 2–3 evidence, pick the most likely `game_type`:

| Evidence | Likely type | Page |
|----------|-------------|------|
| Directional actions shift a cluster; walls block | movement | `[[game_types/movement]]` |
| Directional + gravity | platformer | `[[game_types/platformer]]` |
| Directional + pushable blocks | sokoban | `[[game_types/sokoban]]` |
| Clicks change state; no movement | click | `[[game_types/click]]` |
| Clicks merge colored sprites | merge_puzzle | `[[game_types/merge_puzzle]]` |
| Click encodes bits + play button navigates player | programming_puzzle | `[[game_types/programming_puzzle]]` |
| Short action sequences progress state | sequence | `[[game_types/sequence]]` |
| Click 3×3 pattern + exit unlocks | spell_cast | `[[game_types/spell_cast]]` |
| Mixed — movement + click on objects | hybrid | `[[game_types/hybrid]]` |

If no match, use `[[game_types/unknown]]` and fall back to the generic strategy stack.

### Step 5 — Identify entities

Based on type, look for:
- **Player**: the cluster that moved on directional input (movement, sokoban, platformer)
- **Walls**: consistently non-moving cells that block player motion
- **Goal**: persistent region whose color is distinct, often with a `+` or square marker
- **Interactive objects**: non-background clusters that react to ACTION5/ACTION6
- **Changers** (transform games): static cells that modify sprite color on overlap

Record entity positions and colors for the downstream solver.

## Worked Example — AR25 (movement)

1. Opening frame: 1 layer, `available_actions = [1,2,3,4,6]`
2. Probe ACTION1: a color-5 cluster at (16,20) moves to (16,19). → ACTION1 = UP, player color = 5.
3. Probe ACTION2: same cluster moves to (17,20). → ACTION2 = RIGHT.
4. (skip 3,4 — trivially DOWN/LEFT)
5. Probe ACTION6(30,30): no change. ACTION6 not relevant for this game.
6. Classify: **movement**. See `[[game_types/movement]]`.
7. Dispatch: `[[strategies/frame_only/bfs_state_space]]`.

## Worked Example — SU15 (merge_puzzle)

1. Opening frame: multi-layer, dozens of small colored clusters
2. Probe ACTION1-5: all no-op or near no-op. `ACTION6` is the main action.
3. Probe ACTION6(32,32): nearby clusters pull toward (32,32); two same-color clusters overlap and become a single cluster of color+1. → **merge observed**.
4. Another ACTION6 near a different cluster: similar pull. One cluster has a distinct color and behavior (chases another) → **enemy entity**.
5. Classify: **merge_puzzle**. See `[[game_types/merge_puzzle]]`.
6. Dispatch: current brittle solver `strat_su15_vacuum` (will be replaced by frame-only variant in Phase 8 Step 2b).

## Common Pitfalls

- **Noisy animations** cause spurious diffs. Probe multiple times; use majority vote.
- **Lazy ACTION1 mapping**: not every game maps ACTION1 to UP. Always verify by observation.
- **Confirmation bias**: if the first probe suggests movement, don't skip the ACTION6 probe — hybrid games exist.
- **Over-sampling ACTION6**: 5–10 probes is enough; more wastes budget.

## Related

- `[[reasoning/frame_to_strategy_chain]]` — what to do after classification
- `[[reasoning/hypothesis_check]]` — verify the classification before full exploit
- `[[concepts/sprite_cluster]]`, `[[concepts/frame_hashing]]`
- `[[lessons/frame_diff_as_probe]]`
- `[[selector]]` — the dispatch table this feeds into
