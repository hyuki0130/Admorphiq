---
type: game_type
examples: [SB26]
refactor_status: brittle_only
---

# Sort Puzzle

> Items at the bottom of the frame must be swapped into target slots matching a color sequence; possibly across multi-frame portal networks.

## Identifying features

- A row of items at the bottom (the "inventory")
- A row of target slots in the middle/top with pre-declared colors
- `ACTION5` scans/verifies; `ACTION6` clicks to select or swap; `ACTION7` undoes
- Portals can redirect between frames (complex variants)

## Discovery protocol

1. Identify inventory row via frame bottom connected components
2. Identify slot row by per-slot color signature
3. Confirm ACTION5 as scan (frame change is minimal but verification marker appears)
4. Confirm ACTION6 as swap (selected item changes slot)

## Canonical strategy

Minimum-swaps sort to match target color sequence; undo on wrong move.

## Games and current results

| Game | v1 | v2 | Strategy |
|------|-----|-----|----------|
| [[../games/SB26]] | 8/8 | n/a | sb26_sort (brittle) |
