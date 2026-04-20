---
type: concept
instantiating_games: [KA59, WA30]
detection_frame_only: yes
---

# Pushable Block

> A sprite that moves by one cell when the player moves into it from an adjacent cell, **if** the destination cell is empty. The core Sokoban primitive.

## Definition

In a game with pushable blocks:
- Player at (px, py) presses ACTION in direction (dx, dy).
- If cell (px+dx, py+dy) contains a block, and cell (px+2dx, py+2dy) is empty:
  - Block moves to (px+2dx, py+2dy)
  - Player moves to (px+dx, py+dy)
- If the cell behind the block is occupied or a wall, neither moves.

Blocks often must be pushed onto designated goal cells to clear the level.

## Detection heuristics (frame-only)

Diff two consecutive frames after a directional action:
- If only the player cluster moved → no push (plain movement)
- If both the player and another cluster moved by the same direction and magnitude → **push detected**; the other cluster is a block

Repeat over several moves to accumulate a catalog of block positions and per-block colors.

## Instantiating games

| Game | Role | Notes |
|------|------|-------|
| [[../games/KA59]] | multi-player sokoban | two players coordinate; same push rule |
| [[../games/WA30]] | delivery variant | worker-style pusher carrying items to zones |

## Key abstractions

- **Block** — pushable sprite
- **Goal cell** — static marker that accepts a specific block
- **Deadlock** — a block pushed into a corner with no goal is unrecoverable; detect before committing
- **Multi-block coordination** — some puzzles require pushing in a specific order

## Solver pattern

State = (player_pos, frozenset(block_positions)). Actions produce deterministic transitions (push or plain move). A* with Manhattan-to-goal heuristic works well for small grids (≤30×30).

Deadlock detection: mark any corner cell without a goal as a "dead" cell; prune transitions that push a block onto a dead cell.

## Related concepts

- [[sprite_cluster]]
- [[frame_hashing]]
- [[concepts/gravity]] — contrast: gravity moves sprites passively; pushable blocks move only via player contact

## Related games

- [[../games/KA59]]
- [[../games/WA30]]

## Sources

- `src/admorphiq/agent_ensemble.py` — `strat_ka59_sokoban`, `strat_wa30_analytical`
- KA59 source: `environment_files/ka59/9f096b4a/ka59.py`
