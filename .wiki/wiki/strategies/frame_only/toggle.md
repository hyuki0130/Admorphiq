---
type: strategy
name: toggle
generalizes: yes
implementation: src/admorphiq/strategies/inferential.py::_plan_toggle
dispatched_from: inferential_agent.PLAN_FNS["toggle"]
---

# toggle (plan fn)

> Click-sequence search over candidate cells (cluster centroids +
> responsive probes + cluster four-corner samples). Optionally appends
> the executor cell to every sequence. Round-7 widened the candidate
> pool because FT09 measured 0/20 responsive on cluster centroids yet
> the brittle solver cleared 6/6 — clicks have effect even when the
> single-probe diff is zero.

## Applies When

- `goal["kind"] == "paint_fill"` AND `palettes` empty — interpreted as
  a lights-out-style mechanic where there's no explicit palette select.
- OR `goal["kind"] == "toggle"` (rare; explicit toggle classification).
- Click action available, dense cluster grid present.

## Algorithm

1. Build candidate coords (deduped, capped at 16):
   - Every cluster centroid in `entity_map["clusters"]`.
   - Every responsive stride-8 click probe (`diff_magnitude ≥ 10`).
   - Four-corner samples of each non-trivial cluster (size ≥ 9).
   - Excludes palettes and executors from the candidate set.
2. Optionally identify `exec_cell` (first executor location).
3. DFS over candidate sequences up to depth 3 (Round-7 raised to 4 for
   sparse-responsive envs).
4. For each sequence: reset, click each cell in order, optionally
   click `exec_cell` last, observe `levels_completed`.
5. Return on first level advance.

## Why It Generalizes

- Candidate pool comes purely from flood-fill + probe responses.
- No sprite tags, no game internals.
- Executor injection works whether executors are present or not.

## Observable Signature

- `goal["kind"] == "paint_fill"` AND `len(entity_map["palettes"]) == 0`.
- `len(entity_map["clusters"]) ≥ 4` (enough cells to form a meaningful
  candidate pool).
- `avail ⊇ {6}` (click).
- Either `click_responsive ≥ 1` OR cluster centroids form a regular
  grid (FT09-style — clicks may be effective even when single-probe
  diff is zero).

## Falsification Signature

- Returns `(0, k_small)` with `k < 50`: candidate pool empty (clusters
  too small or all cells are palettes/executors).
- Returns `(0, k_full)` after exhausting depth-3 enumeration: the
  sequence shape is wrong — try [[lights_out]] for GF(2)-solvable
  toggle structure or [[click_then_move]] for click+move composition.
- Stencil density reads ≥ 0.8 on the top-K candidates (see
  [[../../concepts/gf2_toggle_stencil]]) — every click toggles
  everything, so the candidates are display feedback, not buttons.

## Tunable Parameters

- Candidate cap: 16. Effect: more covers wider grids but explodes
  depth-3 enumeration (16³ = 4096 sequences).
- DFS depth: 3 (default) / 4 (sparse-responsive retry). Effect: deeper
  catches more compositions at exponential cost.
- Cluster size threshold for corner samples: 9. Effect: lower includes
  more sub-cell variants; higher tightens.
- Executor injection: enabled when first executor present. Effect:
  appending changes a 3-click sequence into a 4-click sequence.
- Probe stride for responsive recheck: 4 (down from default 8). Effect:
  see [[../../lessons/ft09_stride_button_drop_20260423]].

## Next-Best

When the falsification signature triggers:

- [[lights_out]] — when candidates form a regular NxN grid AND
  responsive cells map to a GF(2) stencil. lights_out's algebraic
  prediction beats blind enumeration.
- [[paint_fill]] — when palette emerges on retry observation (rare;
  some games show palettes after first interaction).
- [[click_then_move]] — when dir actions are also available; the
  failed mechanic might be click-then-move rather than pure-click.

## Limitations

- Depth-3 enumeration scales as O(C³) where C is the candidate cap.
  Beyond C=16 it becomes infeasible.
- No state pruning — each sequence is tried independently from reset.
- Doesn't model cumulative state (lights-out's commutative XOR
  structure is exploited only by [[lights_out]], not here).

## Related

- [[lights_out]] — sister plan with GF(2) algebraic structure
- [[paint_fill]] — palette-aware variant
- [[../../concepts/gf2_toggle_stencil]] — falsifier signature
- [[inferential_agent]] — outer loop
- [[../../lessons/ft09_stride_button_drop_20260423]] — stride retry pattern

## Sources

- `src/admorphiq/strategies/inferential.py:858-1140`
- R7 candidate-pool widening
- `scripts/probe_ft09.py` — instrumented trace
