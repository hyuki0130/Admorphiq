---
type: lesson
date: 2026-04-23
rounds: R16-R18
status: partial — infrastructure complete, multi-level still open
---

# GF(2) Toggle Stencil for Lights-Out (R16-R18)

## What

Rounds R16-R18 added a GF(2) linear-algebra layer to
`_plan_lights_out`:

- **R16** measured the empirical toggle stencil `A[i][j]` via
  `_measure_toggle_stencil` — click cell `j` alone, record which
  cells `i` changed patch-mode color.
- **R17** added `_gf2_solve` (Gaussian elimination over GF(2)),
  `_homogeneity_score`, and `_rank_subsets_by_prediction` — predict
  every subset's post-click state offline, rank by homogeneity, try
  the top-K in the env before falling back to naive enumeration.
- **R18** replaced the per-trial reset-then-replay with **delta
  chaining** (trial `k+1` = `x_k XOR x_{k+1}` clicks from the prior
  trial's state). Also added a cumulative 40-cell single-click
  sweep BEFORE stencil measurement to catch games where the top-10
  diff-magnitude cells are coupled display (stencil density 91%+).

## Why it matters

Brute-force subset enumeration is `O(2^n)` subsets × `O(n)` clicks,
each preceded by a full reset-then-replay. For a grid of `n=10`
cells with a 374-click prefix (FT09 L1), one attempt costs ≈ 385
env steps. A complete 2^10 sweep would cost 4 × 10^5 — blowing
through every budget. Delta chaining drops this to ≈ 5 × 10^3 total
for the same search space.

## Observed outcomes

- **FT09 L1**: cleared by the stencil + delta-chain path. The
  8-cell toggle grid is effectively identity-stencil, so any
  single-cell target is trivially reachable.
- **FT09 L2+**: not cleared. Two distinct failure modes surfaced:
  1. `diff_magnitude`-sorted top-10 cells show stencil density
     91/100 — they are display feedback cells, not buttons.
  2. The cumulative-sweep pre-pass disrupts the env state enough
     that a subsequent stencil measurement shows 19/100 density,
     but even with `2^10` predictive enumeration through delta
     chain the predicted post-states don't match the L2 goal —
     the goal is likely a constraint-indicator pattern our
     homogeneity heuristic doesn't capture.

## Decision

The stencil + GF(2) + delta-chain infrastructure stays — it is a
proper mathematical model for any game satisfying the
[[../concepts/gf2_toggle_stencil]] observable signature. Multi-level
clears beyond L1 on games with explicit constraint indicators
(target-pattern puzzles) need an additional observation primitive:
identify non-toggling "indicator" cells and use their state as the
target vector `b`, not the homogeneity heuristic.

## Falsification

If a new game satisfies the GF(2) signature but our code makes it
worse than a uniform random click baseline, this lesson is wrong.
Measured worst case so far: a dense-stencil game where the
predictive rank fails and the full enumeration is exhausted before
any subset clears — equivalent to uniform-random performance.

## Related

- [[../concepts/gf2_toggle_stencil]]
- [[../strategies/frame_only/inferential_agent]]
- [[../games/FT09]]
