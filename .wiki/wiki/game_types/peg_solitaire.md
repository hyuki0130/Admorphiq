---
type: game_type
examples: [LF52]
refactor_status: frame_only
---

# Peg Solitaire Game

> Jump a piece over an orthogonally-adjacent piece into the empty board slot two cells beyond; the jumped piece is CAPTURED and removed. Reduce the board to one piece to win.

## Identifying features

- `available_actions` includes `ACTION6` (a click selects a piece, then a click on a landing cell fires the jump); simple moves may exist but are not required
- Two distinct cell colours on a regular lattice: movable PIECES (the rarer colour) sitting on board SLOTS (the more common colour); an empty slot is a legal landing hole
- A click on empty space triggers a fixed tutorial hint, NOT a game response — do not mistake the hint for the mechanic (see [[../lessons/probe_validity_20260715]])

## Discovery protocol

1. Parse the lattice: `find_regions` → cell-sized colour blobs on a fixed pixel pitch; the rarer lattice colour = pieces, the common one = slots. Drop lone off-lattice markers (selection/animation).
2. Confirm the click semantics with a faithful passive read: click a PIECE (selects), then a legal landing cell two away over a neighbour (jumps and captures).
3. The win is a reduction to one piece; the lose gate is a per-level action budget.

## Canonical strategy

Build a faithful offline simulator (state = frozenset of piece lattice cells) and DFS the jump graph for a sequence reducing to one piece; replay two clicks per jump (piece centroid to select, landing centroid to jump). This is the [[../lessons/faithful_offline_simulator_20260715]] pattern — search offline, replay live.

## Games and current results

| Game | v1 | script25 | Strategy |
|------|----|----------|----------|
| [[../games/LF52]] | 0/10 | 1/10 (L0 @ 0.0182) | `adapters25/lf52.py` — frame parse + DFS reduce-to-one; deeper levels (board scroll, coloured pieces, two-piece win) banked |

## Related

- [[../lessons/faithful_offline_simulator_20260715]] — the offline-search method
- [[../lessons/probe_validity_20260715]] — the tutorial-hint probe trap that mis-parked LF52
- [[../concepts/merge_mechanic]] — capture/reduction win where blind search is insufficient
