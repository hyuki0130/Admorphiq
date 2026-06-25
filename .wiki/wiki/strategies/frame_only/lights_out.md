---
type: strategy
name: lights_out
generalizes: yes
implementation: src/admorphiq/strategies/inferential.py::_plan_lights_out
dispatched_from: inferential_agent.PLAN_FNS["lights_out"]
---

# lights_out (plan fn)

> GF(2) toggle stencil + delta-chain trial enumeration. Measures the
> empirical toggle stencil `A[i][j]` (click cell `j`, observe which
> cells `i` change patch-mode color), solves linear systems over
> GF(2) to predict subset effects, ranks candidate subsets by
> homogeneity score, and tries the top-K via XOR-delta chaining
> instead of reset-then-replay-each. R18 prefaces the stencil with a
> cumulative single-click sweep over 40 cells to catch games whose
> top-diff cells are coupled display feedback.

## Applies When

- `goal["kind"] == "paint_fill"` (interpreted as lights-out variant)
  OR explicit `goal["kind"] == "lights_out"`.
- Regular grid of clickable cells (cluster centroids forming a uniform
  NxN pattern, e.g., 8 px spacing on FT09).
- `avail = [6]` or `avail ⊇ {6}` with sparse direction usage.

## Algorithm

1. **Cumulative sweep** (R18) — single-click each of the top 40
   diff-magnitude cells *without* resetting between clicks. Catches
   "click the right button" games where the post-sweep state already
   clears the level.
2. **Stencil measurement** (R16) — pick top-N cells (default 10) by
   diff_magnitude. For each, reset, click, capture
   `_extract_cell_class(frame, cx, cy, patch_radius=2)` for every
   cell. Build `A[i][j] = (toggled_classes[i][j] != base_classes[i])`.
3. **Predictive ranking** (R17) — for every non-zero subset
   `x ∈ {0,1}^N \ {0}`, compute predicted post-state
   `predicted = base ⊕ (A · x mod 2)`, score by homogeneity (count
   of identical neighbors). Sort subsets by descending score.
4. **Delta-chain trials** (R18) — for each ranked subset:
   - First trial: reset, click cells where `x[j] = 1`.
   - Subsequent trials: click only the XOR-delta from prior `x_{k-1}`
     (lights-out clicks are commutative + self-inverse).
   - On any trial, if `levels_completed > base_levels`, return success.
5. Fallback to naive `2^N` enumeration if delta-chain exhausts the
   ranked top-K without success.

## Why It Generalizes

- Stencil measurement uses only frame-color extraction
  (`_extract_cell_class` mode of (2r+1)² patch).
- GF(2) solve is universal linear algebra — no game-specific encoding.
- Delta chaining exploits the algebraic structure (commutative,
  self-inverse) which is generic to lights-out games.

## Observable Signature

- `avail ⊆ {6}` or `avail = {6}` (click-only).
- Cluster centroids form a regular grid (8 px / 4 px stride alignment
  detectable).
- Cumulative-sweep pre-pass measurably changes the frame (otherwise
  the cells are fully inert — different mechanic).
- Stencil density (post-measurement, on the top-N cells) is in
  `[0.05, 0.6]` — neither identity (every cell toggles only itself)
  nor saturated (every click toggles everything).

## Falsification Signature

- Stencil density > 0.8 on top-N cells: those cells are coupled
  display feedback, not buttons (FT09 L2+ pattern, see
  [[../../lessons/gf2_lights_out_stencil_20260423]]).
- All ranked subsets predict identical post-states (rank-1 stencil) —
  prediction is uninformative, fall back to enumeration.
- Naive `2^N` enumeration exhausted with `levels_cleared = 0` — the
  goal isn't a homogeneous subset; constraint indicators encode the
  target pattern that the homogeneity heuristic can't capture.
- Cumulative sweep produces zero frame change — clicks have no effect;
  classification was wrong.

## Tunable Parameters

- `cumulative_sweep_size`: 40. Effect: more covers off-target buttons
  at higher pre-stencil budget cost.
- `stencil_n` (top-N cells): 10. Effect: bigger stencil captures more
  structure but `2^N` enumeration grows exponentially.
- `patch_radius`: 2 (`_extract_cell_class` reads (2r+1)² = 25 px).
  Effect: larger radius gives stabler class assignments on noisy cells
  but blurs adjacent buttons.
- `top_K_ranked` for delta chain: 50-100. Effect: more trial subsets
  before naive fallback.
- Stride for candidate pool: 4 (R14, see
  [[../../lessons/ft09_stride_button_drop_20260423]]). Effect: 8 misses
  grid-aligned button cells; 2 quadruples probe cost.
- Naive enumeration depth cap: typically 2^10 = 1024. Effect:
  controls worst-case budget.

## Next-Best

When the falsification signature triggers:

- [[toggle]] — broader candidate pool (every cluster centroid + corner
  samples) without GF(2) structural assumption. Use when stencil
  density is degenerate.
- [[click_then_move]] — when dir actions also produce diff (sometimes
  lights-out variants have a "next puzzle" arrow as a hidden movement
  trigger).
- Constraint-indicator detection (no plan fn yet) — the proper next
  for FT09 L2+. Read non-toggling cells as the target vector `b`,
  solve `A x = b` instead of optimising homogeneity.

## Limitations

- Top-N cell selection is by `diff_magnitude` only. On display-feedback
  envs the most-diffed cells are the *output*, not the *buttons* —
  classic FT09 L2 trap.
- Goal vector inference is heuristic (homogeneity score). Constraint-
  indicator pattern matching not implemented.
- Patch-class assignment is mode-of-pixels in a 5x5 window — robust
  to single-pixel noise but degrades on sub-cell sprites.

## Related

- [[../../concepts/gf2_toggle_stencil]] — formal definition
- [[../../lessons/gf2_lights_out_stencil_20260423]] — R16-R18 history
- [[../../lessons/ft09_stride_button_drop_20260423]] — stride retry
- [[toggle]] — fallback when GF(2) structure is absent
- [[../../games/FT09]] — canonical instantiation

## Sources

- `src/admorphiq/strategies/inferential.py:1142-1311`
- R16 commit `377ca48`, R17 `009a6be`, R18 `8c41623`, R14 `173b399`
- `tests/test_inferential_stencil.py` — primitives unit tests
- `scripts/probe_ft09.py` — instrumented trace
