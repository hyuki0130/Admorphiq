---
type: game_type
examples: [SU15]
refactor_status: brittle_only
---

# Merge Puzzle

> 2048-style color merging: same-color sprites that overlap become color+1; secondary entities (enemies) can downgrade.

## Identifying features

- Multi-layer frame with many distinct-color sprites
- `ACTION6(x, y)` creates an attraction or impulse that moves nearby sprites toward the click
- Two same-color sprites merging produces a sprite of color+1 (2048-like)
- Enemy entities chase fruits; contact causes color−1 downgrade

## Discovery protocol

1. Cluster same-color pixels; each cluster is a candidate sprite
2. Probe ACTION6 near a sprite; observe whether the sprite moves toward the click
3. Distinguish fruits from enemies by post-contact outcome (merge vs downgrade)
4. Detect goal zones as static background regions declared in level intro

## Canonical strategy

[[../games/SU15]] — current `su15_vacuum` reads game internals; frame-only variant planned for Phase 8 Step 2b.

## Games and current results

| Game | v1 | v2 | Strategy |
|------|-----|-----|----------|
| [[../games/SU15]] | 9/9 | 0/9 | su15_vacuum (brittle) |

## Edge cases

- **Enemies disrupting merges**: plan enemy avoidance while pairing fruits
- **Multi-target goals**: different colors in different zones; must solve as assignment + routing
- **Vacuum radius**: approximate click placement; must plan for 8-pixel pull radius
