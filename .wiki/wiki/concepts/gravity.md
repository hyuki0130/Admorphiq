---
type: concept
instantiating_games: [BP35]
detection_frame_only: yes
---

# Gravity

> The player falls passively between actions unless supported by a solid block. Actions provide lateral movement and (sometimes) block destruction or upward motion. The core platformer primitive.

## Definition

In a gravity game:
- Each game tick (or at regular intervals) the player moves one cell down if the cell below is empty.
- Lateral actions (ACTION1/2) adjust player column.
- Some actions allow upward movement (jump) or block manipulation (destroy, create).

Detection signal: between two consecutive actions, the player's row changes even if the action was lateral.

## Detection heuristics (frame-only)

1. Identify the player cluster (color that moves on ACTION1/2).
2. Wait one frame *without* pressing anything (if the environment supports idle actions) — if the player falls, gravity confirmed.
3. If no idle is possible, observe: after ACTION1 (horizontal move), did the player also descend? If yes, gravity is acting between action ticks.

## Instantiating games

| Game | Role | Notes |
|------|------|-------|
| [[../games/BP35]] | canonical | lateral + ACTION6 block destruction; goal in distinct `+` cluster |

## Key abstractions

- **Solid block** — supports player; blocks fall
- **Destructible block** — ACTION6 removes; makes player drop
- **Hazard** — cells that end the level on player contact
- **Goal** — marker the player must reach; often requires creative falling

## Solver pattern

Gravity-aware BFS over (player_x, player_y, set_of_destroyed_blocks). Transitions:
- Lateral move: `(px±1, py)` if target cell empty; then apply gravity until supported
- Destroy: remove adjacent block; apply gravity
- End state: player occupies goal cell

Gravity makes the state space non-trivial because the "rest position" depends on world state. BP35's current `strat_bp35_platformer` handles this already in a frame-only way.

## Related concepts

- [[sprite_cluster]]
- [[pushable_block]] (contrast: pushable blocks move horizontally via player contact; gravity blocks move vertically passively)

## Related games

- [[../games/BP35]]

## Sources

- `src/admorphiq/agent_ensemble.py:2842-...` — `strat_bp35_platformer`
- Commit `31fe1fc` — BP35 L1 first cleared
