---
type: game_type
examples: [KA59]
refactor_status: brittle_only
---

# Sokoban Game

> Movement with pushable blocks; blocks slide one cell when player moves into them (if destination is empty); goal requires pushing blocks to marked cells.

## Identifying features

- `available_actions` includes directional `ACTION1..4`
- One or more "block" sprites that move in response to player movement
- Persistent marked cells (goal zones) that accept specific block colors

## Discovery protocol

1. Identify player via motion diff after directional action
2. Identify blocks: sprites that move *with* the player when the player moves toward them, but not in other directions
3. Identify walls: non-moving pixels that block player movement (try moving into every adjacent cell)
4. Identify goals: static pixels with a border or marker pattern

## Canonical strategy

A* search over (player_pos, tuple(block_positions)) state space, with pushes as operators. Fall back to BFS if state count is small.

## Games and current results

| Game | v1 | v2 | Strategy |
|------|-----|-----|----------|
| [[../games/KA59]] | 4/7 | 0/7 | ka59_sokoban (hardcoded push sequences) |

## Edge cases

- **Multi-player sokoban** (KA59): two player avatars share the level; action may move only one
- **Pushable-only-in-some-directions** blocks: detect via probing
- **Deadlock detection**: block pushed into a corner with no goal is unrecoverable
