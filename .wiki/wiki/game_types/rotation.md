---
type: game_type
examples: [TR87]
refactor_status: brittle_only
---

# Rotation Puzzle

> Rotate pieces to match a reference pattern.

## Identifying features

- Grid or cluster of pieces with distinguishable orientations
- `ACTION1/2` (typically) rotate the selected piece; `ACTION3/4` select the next piece
- A reference pattern displayed in a corner or overlay

## Discovery protocol

1. Identify pieces via color + orientation-sensitive signature
2. Identify reference by its persistent distinct region
3. Probe rotate action to confirm ACTION1/2 cycles orientations
4. Compute per-piece delta between current and reference orientation

## Canonical strategy

Straightforward per-piece correction: iterate pieces, apply minimum rotation count.

## Games and current results

| Game | v1 | v2 | Strategy |
|------|-----|-----|----------|
| [[../games/TR87]] | 1/6 | n/a | tr87_rotation (hardcoded L1) — **misclassified**, see below |

## Edge Cases

- **TR87 does NOT fit this game_type** (measured R53, 2026-07-13): its
  `avail` never includes `ACTION6` (click-only is this page's core
  identifying feature), and `ACTION1`/`ACTION2` step a 7-state CYCLIC DIAL,
  not a geometric rotation (cell count changes between presses; no
  `rot90`/transpose/flip matches). It is left listed here only because no
  better-fitting `game_types/` page exists yet — see
  [[../games/TR87]] and [[../lessons/tr87_dial_match_hypothesis_falsified_20260713]]
  for the actual confirmed mechanic before assuming this page applies to it.

## Related

- [[../games/TR87]]
- [[../lessons/tr87_dial_match_hypothesis_falsified_20260713]]
