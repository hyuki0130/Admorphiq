---
type: game_type
examples: [CD82, FT09, CN04, LP85, VC33]
refactor_status: partial (some frame-only wins, some brittle)
---

# Click Game

> The level advances when the agent clicks specific pixels; movement actions are usually not needed.

## Identifying features

- `available_actions` centers on `ACTION6` (click with coordinates)
- ACTION1-4 often absent or ineffective
- Frame diffs between consecutive states are local (clicked pixel + small neighborhood) when progress is made
- No persistent "player sprite" that navigates

## Discovery protocol

1. Sample `ACTION6` on random grid positions in first ~20 actions
2. For each click, record whether the frame changed non-trivially
3. Clicks that cause persistent change are candidate "live" cells
4. Rare-color pixels are often strong candidates

## Canonical strategies

- [[../strategies/frame_only/click_rare]] — click pixels of the rarest color (works for LP85, VC33)
- `click_cN_(x,y)` variants — coordinate-cached once discovered
- Brittle analytical solvers for structured clicks (FT09 lights-out, CD82 paint game)

## Games and current results

| Game | v1 | v2 | Strategy | Type |
|------|-----|-----|----------|------|
| [[../games/LP85]] | 1/8 | n/a | click_c8_(30,4) | frame_only |
| [[../games/VC33]] | 1/7 | 1/7 | click_c9_(33,60) | frame_only |
| [[../games/CN04]] | 1/5 | 0/6 | zig3_A2A4 | frame_only |
| [[../games/CD82]] | 6/6 | n/a | paint_game | brittle |
| [[../games/FT09]] | 6/6 | n/a | lights_out | brittle |

## Edge cases

- **Constraint-based clicks** (FT09): click changes state of multiple cells; requires analytical planning
- **Ordered clicks** (CD82): sequence matters; wrong order resets progress
- **Color-palette shift**: rare color may differ between versions — detect palette dynamically
