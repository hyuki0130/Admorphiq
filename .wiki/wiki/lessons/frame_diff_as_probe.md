---
type: lesson
symptom: "Need to identify an entity in the frame without reading game internals"
severity: info
first_seen: 2026-04-01 (849f8a1 — frame diff engine first used)
---

# Frame Diff as Probe

> The difference between two consecutive frames is the cheapest, most general signal for classifying entities: what moved is likely the player, what changed locally is likely a toggle, what stays constant is likely background.

## Core idea

After each action, compute a pixel-level diff between `frame_before` and `frame_after`. The diff tells you:

| Diff shape | Likely meaning |
|------------|----------------|
| Connected cluster shifted by a few pixels | **Player moved** (if action was directional) |
| Small isolated pixel change | **Click toggle** (cell state flipped) |
| Multiple clusters moved in same direction | **Pushable blocks** (sokoban) |
| Whole frame shifted | **Viewport scroll** (treat like movement) |
| No diff but level_up incremented | **Trigger event** (ACTION5 on interactive object) |
| No diff at all | **Action was no-op** (walled/blocked) |

## How to use it

### Identify the player (movement games)
1. Compare the frame before and after `ACTION1`, `ACTION2`, `ACTION3`, `ACTION4`.
2. The connected cluster that shifted position between the two frames is the player.
3. Direction vector gives you the action-to-direction mapping.

### Identify walls
1. After many directional actions, collect the set of (from_cell, to_cell) transitions the player attempted.
2. Any destination cell that the player never successfully moved into is either a wall or off-grid.
3. Walls show up as consistently-colored pixels that block the player color.

### Identify interactive objects
1. For each non-player, non-background color cluster:
2. Move the player adjacent to it and press `ACTION5` / `ACTION6`.
3. If the frame changes (the cluster disappears, moves, or changes color), classify as interactive.

### Identify goals
1. A goal is often a region that never changes between frames but whose reaching triggers `levels_completed += 1`.
2. Persistent, distinct-color regions are candidates.

## Relation to concepts

- `[[concepts/sprite_cluster]]` — the detection primitive (connected-component clustering)
- `[[concepts/frame_hashing]]` — how to summarize frames into comparable states
- `[[strategies/frame_only/bfs_state_space]]` — uses frame diff to define state transitions

## Pitfalls

- **Animation frames**: some games have idle animations that cause spurious diffs every frame. Use majority-vote or longer windows to smooth.
- **Gravity**: in platformers like BP35, the player moves on its own between actions; diff is dominated by gravity, not the action. Account for this in per-action diff.
- **Multi-layer frames**: when `FrameData.frame` has N layers, diff per layer before combining.

## Falsification

None expected — frame diff is a universal primitive. Even if ARC-AGI-3 adds 3D rendering or other weirdness, the pixel grid interface persists.

## Related

- `[[concepts/sprite_cluster]]`
- `[[concepts/frame_hashing]]`
- `[[reasoning/discovery_phase]]` — uses frame diff as a key step
- `[[strategies/frame_only/bfs_state_space]]`
- `[[lessons/v2_hash_obfuscation]]` — frame diff is the alternative to reading obfuscated sprite tags

## Sources

- `src/admorphiq/perception/frame_analyzer.py` — `FrameAnalyzer` implementation
- Commit `849f8a1` — frame diff engine first used in ensemble
- `src/admorphiq/agent_diff.py` — DiffAgent built on top
