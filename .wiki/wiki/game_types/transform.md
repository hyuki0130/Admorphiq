---
type: game_type
examples: [RE86]
refactor_status: brittle_only
---

# Transform Puzzle

> Multiple movable sprites must be routed to target positions; intermediate "changer" tiles modify sprite color en route.

## Identifying features

- Multiple sprites of varying colors
- Static target regions with pre-set color requirements
- Color-changing tiles that alter sprite color on overlap
- Multi-sprite-same-color constraints

## Discovery protocol

1. Identify movables via per-action movement diff (sprites that move on directional input)
2. Identify static tiles via no-response-to-action; among static tiles, identify changers by observing sprite color after overlap
3. Identify targets by distinct markers or pre-declared color at positions

## Canonical strategy

Bipartite matching (sprite → target) + per-pair routing through appropriate changer. When color mismatch, insert a changer detour.

## Games and current results

| Game | v1 | v2 | Strategy |
|------|-----|-----|----------|
| [[../games/RE86]] | 6/8 | 0/8 | re86_analytical (brittle) |

## Edge cases

- **Multiple changers with different color deltas**: choose shortest detour
- **Two sprites needing the same target**: must deliver sequentially without blocking
