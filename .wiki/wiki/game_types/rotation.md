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
| [[../games/TR87]] | 1/6 | n/a | tr87_rotation (hardcoded L1) |
