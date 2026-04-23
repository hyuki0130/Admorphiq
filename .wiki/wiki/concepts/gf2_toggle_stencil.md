---
type: concept
name: gf2_toggle_stencil
audience: inference agent and routing LLM
---

# GF(2) Toggle Stencil

Any click-grid puzzle where each click flips a fixed subset of cells
(independent of their current state) is a linear system over the field
with two elements, GF(2). The stencil matrix `A[i][j] = 1` iff
clicking cell `j` flips cell `i`. Any goal state reachable by clicks
satisfies `A x = b` where `b` is the target flip vector and `x[j] = 1`
iff we click cell `j` in the solution.

Because click order is irrelevant and each click is self-inverse, the
solution is a **subset**, not a sequence. That reduces the candidate
space from `n!` to `2^n`.

## Observable signature

The game is a GF(2) toggle candidate when:

- The only available action is `ACTION6` (click).
- The click-probe sweep shows a grid of cells each producing a
  localized diff on click (`diff_magnitude` ~ 10..100 px).
- Repeating the same click twice restores the previous frame
  (verifiable at measurement time).

When these hold, run `_measure_toggle_stencil` (see
`src/admorphiq/strategies/inferential.py`) to empirically build `A`.

## Falsification criteria

- Stencil density `> 0.8`. When every click flips every cell, the
  grid is a coupled display (HUD / feedback region), not independent
  toggles. The real buttons are elsewhere in the responsive list.
  Fall back to a cumulative single-click sweep over more cells.
- Stencil `A[i][j]` inconsistent across measurement runs. Means the
  toggle depends on the current state (non-linear), invalidating the
  GF(2) model. Abandon this plan; try click-then-move or toggle.

## How to solve

1. Measure `A` via `_measure_toggle_stencil(env, cells)`.
2. Try any of the following target vectors `b` (or all, in
   predicted-homogeneity order):
   - zero vector (stay in base state),
   - all-ones (flip everything),
   - single-cell `e_k` for each `k`.
3. For each `b`, run `_gf2_solve(A, b)`; execute the returned `x`.
4. If none clears the level, enumerate all `2^n` subsets, rank each
   by post-click homogeneity via `_rank_subsets_by_prediction`,
   and execute the top-K via delta-chain trials (no reset between
   trials — self-inverse property keeps state deterministic).

## Provenance

- Concept lifted from the classic Lights-Out puzzle literature; see
  Anderson & Feil, "Turning Lights Out with Linear Algebra" (1998).
- Measured directly against FT09 L1 in round 18 (2026-04-23): stencil
  density 8/64 (identity-like), delta-chain cleared L1 in ~300 clicks.
- Measured against FT09 L2 in round 18: stencil density 91/100 or
  100/100 depending on cell-selection heuristic, confirming the
  falsification-by-density rule (buttons were elsewhere in the
  responsive list).

## Related

- [[../strategies/frame_only/inferential_agent]]
- [[../lessons/gf2_lights_out_stencil_20260423]]
- [[rare_color_click]]
