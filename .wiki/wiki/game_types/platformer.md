---
type: game_type
examples: [BP35]
refactor_status: frame_only_works
---

# Platformer Game

> Gravity acts on the player; horizontal movement plus block-destruction lets the agent fall to or uncover goals.

## Identifying features

- `available_actions` typically includes `ACTION1/2` (lateral) and `ACTION6` (click to destroy)
- Player falls unless on a solid block
- Some blocks are destructible (ACTION6 on the block) — uncovered paths open up
- Goal marker is a distinct-colored cluster (often `+`-shaped)

## Discovery protocol

1. Press ACTION1/2 to find lateral moves; observe player column shift
2. Wait a few frames — detect gravity (player falls without further action)
3. Probe ACTION6 on adjacent blocks; detect destruction via frame diff
4. Find goal by unique color signature

## Canonical strategy

Gravity-aware BFS over (player_x, player_y, destroyed_set). For BP35, the `bp35_platformer` custom solver already works and is frame-only.

## Games and current results

| Game | v1 | v2 | Strategy |
|------|-----|-----|----------|
| [[../games/BP35]] | 1/9 | n/a | bp35_platformer (frame_only) |

## Edge cases

- **Timed falls**: agent must stop moving to let gravity carry player a specific distance
- **Unbreakable blocks**: distinguish destructible from solid via probe
- **Enemies/hazards**: some games introduce obstacles that kill on contact
