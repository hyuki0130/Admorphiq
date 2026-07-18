---
round: R85
axis: depth / faithful-obstacle-model + config-space move planner
keywords: r11l, strike-aware, defgjl, body-obstacle, centroid-assembly, leg-separation, camera-identity, misdiagnosis-correction, depth, script25
verdict: r11l 1/6 → 3/6 @ 0.2551 (deterministic ×2); R60c wall-edge/camera bank FALSIFIED; L0 byte-identical
commit: (this round)
---

# R85 — r11l strike-aware drag-assembly planner (task #109, 2026-07-19)

Assigned as the last marginal OPEN-BOUNDED opportunity from the R84 frontier
scan ([[r84_bounded-frontier-scan]]): r11l L1, target 2/6 (~0.14). Delivered
**3/6 @ 0.2551** — a 5.4× game-score jump, well past target — by correcting a
misdiagnosis and modelling the real obstacle.

## What the prior banks got WRONG (engine-truth probes, dev-time passive reads)

R59/R60/R60b/R60c banked r11l L1 as blocked by "wall-edge placement under a
DISPLAY→GRID camera transform near the octagon that frame-only `is_free` can't
match" and stated the `defgjl` body-obstacle was "off-screen on L1". Direct
engine reads falsify both:

- **Camera is IDENTITY** — `display_to_grid(x,y) == (x,y)` for every tested
  point. There is no transform to isolate.
- **Placement space is huge** (3461 wall-free leg cells) and **both L1 creatures
  have 121/121 geometrically-feasible** wall-free arrangements landing the body
  on its target. "Wall-edge placement infeasible" is false.
- **The real wall is the `defgjl` body-obstacle, which IS in-play on L1**: a
  70×36 sprite over rows ~22-58 (with holes). Moving a leg re-centres the body
  to the legs' mean; if that body's FINAL position pixel-overlaps `defgjl`, the
  engine fires a STRIKE and REVERTS the move (5 strikes → lose). The frozen
  greedy driver modelled only leg-vs-wall, so its minimum-displacement moves
  drove the body through the band and thrashed — the true 1/6 cause.

Two terminal-wall banks were measurement artifacts (verify-don't-trust). See
[[../games/R11L]] Notes R85.

## The build (frame-only, colour-agnostic, script25 quarantine intact)

Per creature, a best-first search (A*, cost = #moves, heuristic = body
Manhattan-to-target) over the joint leg configuration finds an ORDERED sequence
of single-leg moves that lands the body inside the target ring's bbox while
EVERY intermediate body centroid avoids the body-hazard. Key elements:

1. **Body-hazard = generic `_hazard_cells`** (all large non-background regions =
   arena wall + the `defgjl` obstacle). Reused colour-agnostically as a BODY
   constraint — the missing piece. Validated 0/N engine-dangerous over the
   produced plans before wiring.
2. **Leg separation `_LEG_SEP`=10** — two legs closer than this fuse under the
   gap-2 region detector; the merged blob exceeds the piece-size gate and is
   dropped, making that leg unselectable (the second measured stall). Creatures
   are planned sequentially with an accumulating avoid set.
3. **Select by the EXACT planned from-cell** — the engine selects the leg whose
   bbox contains the click, robust to detected-region-centroid drift.
4. **Goal = body centroid inside the target bbox** (not a bbox-touch sliver,
   which gives only a 1-cell corner overlap that does not fire the engine's
   pixel-overlap win — measured on pumlzd).

## Result

- **r11l 3/6 @ 0.2551**, deterministic ×2 (`--max-actions` 600 and 3000
  identical), loader `r11l/495a7899`. Per-level: L0 **1.0** (7 actions,
  byte-identical floor), L1 **0.8403** (36a), L2 **0.8920** (54a). The planner
  generalises past L1's two creatures to L2's 4-leg `grhcew`.
- L0 floor sacred: unchanged (single-creature path untouched).
- 1412 tests pass; ruff clean; adapters25 quarantine lint `ok` (imports +
  no-hardcoding); new durable test
  `test_strike_aware_plan_is_body_hazard_free_and_separates_legs`.

## Reopen

L3+ (`dirwzt` variants) unaddressed — a future depth round. The strike-aware
config-space planner is the reusable spine.

Related: [[r84_bounded-frontier-scan]] · [[../games/R11L]] ·
[[../lessons/faithful_offline_simulator_20260715]]
