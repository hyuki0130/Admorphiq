---
type: strategy
name: spell_cast
generalizes: partial
implementation: src/admorphiq/agent_ensemble.py
dispatched_from: strat_spell_cast in agent_ensemble.py
---

# spell_cast

> Click cells of a fixed 3x3 spell-slot grid in known boolean patterns, then move toward the exit. The grid geometry is computed from display coordinates (frame-only); the spell patterns and exit directions are hardcoded constants tuned to SC25.

## Applies When

- A `spell_cast`-type game (see [[../../game_types/spell_cast]]): a 3x3 grid of clickable slots plus directional movement.
- Progression requires casting a specific spell (a subset of the 9 slots) then walking to an exit.
- `ACTION6` plus at least one directional action are in `available_actions`.

## Algorithm

(from `strat_spell_cast` in `src/admorphiq/agent_ensemble.py`)

1. Compute the 3x3 slot display coordinates: `(25 + col*5, 50 + row*5)` for row/col in 0..2. This geometry is derived, not tag-read.
2. Use known spell patterns (slot-index subsets): teleport `[0,1,4]`, size `[1,3,5,7]`, fireball `[1,4,7]`.
3. Confirmed per-level path: L1 cast `size` then move LEFT (after a 22-step demo animation that the first input triggers); L2 cast `teleport` then move UP; L3+ try all spell/direction combinations.
4. `_cast(pattern)` clicks each slot in the pattern via `ACTION6`. `_move(action_id, steps)` presses a direction until the level clears or the game ends.
5. On `levels_completed` increase, record `name = "spell_cast"` and stop moving to cast the next spell.

## Why It Generalizes (and where it does not)

- **Generalizes**: the slot grid geometry is inferred from pixel display coordinates, not from sprite tag names — so the click targets survive version-hash re-obfuscation.
- **Does not generalize**: the three spell patterns, the per-level spell choice, and the exit directions (L1=LEFT, L2=UP) are hardcoded constants observed from SC25's source. A new spell-cast game with different patterns or exits would need its own discovery; L3+ falls back to brute-forcing all combinations.

## Games Cleared

| Game | v1 | v2 |
|------|-----|-----|
| [[../../games/SC25]] | 2/6 | 2/6 |

## Observable Signature

The plan is the right pick when at DiscoveryReport time:

- A small regular grid of clickable cells is visible (3x3 swatch cluster).
- `ACTION6` plus directional actions are both in `avail`.
- Clicking a slot produces a small local diff (slot highlight), not a whole-frame change.

## Falsification Signature

The plan has failed AND should be swapped when after execution it returns 0 levels AND:

- The hardcoded L1/L2 spell+exit path did not clear (the env is a spell-cast game with different patterns/exits).
- No 3x3 slot grid is present — the env was misclassified.
- L3+ combination search exhausts budget without progress (combinatorial blow-up on a wider grid).

## Tunable Parameters

- `budget`: default 3000, range 600-6000. Effect: more spell/direction combinations tried at L3+.
- demo-clear step count: L1 uses 22 LEFT presses to clear the demo animation. Effect: adjust if a variant's demo length differs.
- spell patterns: the three slot-index subsets. Effect: add observed patterns for a new spell-cast variant.

## Next-Best

When the falsification signature triggers, try (in priority order):

- [[explore_interact]] — when the grid/exit structure is unknown and must be discovered by probing.
- [[bfs_state_space]] — when directional movement dominates and the spell grid is incidental.
- [[../brittle/internal_method_call]] — refactor reference; the hardcoded spell constants are the brittle part to replace with frame-based pattern discovery.

## Related

- [[../../game_types/spell_cast]]
- [[../../games/SC25]]

## Sources

- `src/admorphiq/agent_ensemble.py` — `strat_spell_cast` implementation
- 2026-04-20 regression: SC25 2/6 on both v1 and v2
