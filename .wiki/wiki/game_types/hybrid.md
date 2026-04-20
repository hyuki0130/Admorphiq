---
type: game_type
examples: [G50T]
refactor_status: frame_only_works
---

# Hybrid Game

> Combines movement with interactive objects; progression requires both navigation and targeted interaction (`ACTION5`, specific clicks).

## Identifying features

- Mixed action set: directional + ACTION5 and/or ACTION6
- Objects scattered on the grid that respond only when interacted with
- Player sprite navigates between interactions

## Discovery protocol

1. Identify player via motion diff
2. Identify interactive objects: static sprites that react to ACTION5 when player is adjacent
3. Separate static-only background from interactive targets via probe

## Canonical strategy

[[../strategies/frame_only/explore_interact]] — explore, interact with candidate objects, memoize what worked.

## Games and current results

| Game | v1 | v2 | Strategy |
|------|-----|-----|----------|
| [[../games/G50T]] | 1/7 | n/a | explore_interact (frame_only) |
