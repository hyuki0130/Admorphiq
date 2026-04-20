---
type: game_type
examples: [SC25]
refactor_status: frame_only_works
---

# Spell-Cast Game

> Click a spell pattern on a small grid, wait for animation, then navigate to exit.

## Identifying features

- Small (often 3x3) sub-grid with distinct cells
- Correct click pattern per level (sometimes order-sensitive)
- Exit opens after correct spell

## Discovery protocol

1. Identify spell grid by uniform lattice of same-sized cells
2. Probe clicks; observe whether frame signals cast (distinct animation pattern)
3. After cast, identify exit location via color change in navigable area

## Canonical strategy

[[../strategies/frame_only/spell_cast]] — iterate plausible 3x3 subsets, wait after each, check exit state.

## Games and current results

| Game | v1 | v2 | Strategy |
|------|-----|-----|----------|
| [[../games/SC25]] | 2/6 | 2/6 | spell_cast (frame_only) |
