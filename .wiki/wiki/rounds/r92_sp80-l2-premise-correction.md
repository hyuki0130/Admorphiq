---
round: R92
axis: sp80 depth / premise-correction (multi-session Pass 1 decode)
keywords: sp80, sp80-l2, flow-coverage, multi-source, multi-piece, angled-deflector-misdiagnosis, connected-components-merge, piece-tracking, premise-check
verdict: PREMISE FALSIFIED — L2 is straight-block multi-source coverage (NOT angled deflectors); real wall = self-inflicted multi-piece perception/tracking merge; planner + physics OK
commit: (this docs round)
---

# R92 — sp80 L2 premise correction (task #117, Pass 1 decode, 2026-07-19)

> sp80 L2 has NO angled deflectors (premise falsified) — it is straight-block
> multi-source/multi-piece coverage, same physics as L0/L1; the real wall is a
> self-inflicted multi-piece perception merge, and the planner + flow model are
> measured fine. Floor 2/6 @0.1429 untouched.

Assigned as a multi-session build on the R84 "deepest-weight" premise that sp80
L2 needs a NEW angled-deflector flow-rule model. Pass 1 (decode/probe) instead
**falsified that premise** and isolated the real wall. Floor untouched
(sp80 2/6 @0.1429, loader-hash `sp80-589a99af` verified).

## Premise FALSIFIED (source read + live probe)

- The angled-deflector sprite tags the bank cited — `odioorqnkn` / `trurgcakbj`
  — **appear NOWHERE in `environment_files/sp80/589a99af/sp80.py`**.
- `levels[2]` (source comment "Level 3") contains only STRAIGHT blocks:
  **3 water sources** (`liolfvkveqg` colour-6 + `sowlljgtjvn` colour-4 at grid
  `(1,1)/(6,1)/(14,1)`), **4 straight movable blocks** (`plzwjbfyfli-4/-5/-6/-6`,
  all 1-cell-tall horizontal colour-8 bars — same family as L0/L1), **3 cup
  targets** (`repwkzbkhxl` colour-11). Same fall + perpendicular-spread physics
  as L0/L1; `simulate_flow` already models it.
- The only genuinely angled sprites are `tuvkdkhdokr-*` (L-shaped colour-15,
  with real 90°-deflection engine code at `step` ~L787-811) and they are in
  **L5/L6 only**.
- So **L2 = multi-SOURCE (3 streams) multi-PIECE (4 blocks) straight-coverage**,
  not a new-physics level. This is the sixth stale sp80/-family wall killed by
  re-measurement (cf. the sprint's "verify-don't-trust-parks" doctrine).

## Real wall = self-inflicted multi-piece perception/tracking (measured)

Live trace of the current adapter on L2 (`scratchpad/probe_sp80_l2*.py`):

1. Pristine L2 entry board segments into **4 clean block regions** (colour 8/9,
   sizes 64/80/96/96); the pieces are NOT adjacent at start.
2. But the pipeline detects pieces only AFTER `learn` (sacrificial spill) →
   `probe` (moves the auto-selected block) → `restore` (walks it back). The
   restore leaves the auto-selected block one cell off, ADJACENT to a neighbour,
   so `find_regions` (4-connectivity) MERGES two touching blocks into one
   176-cell region → **only 3 "pieces" seen, not 4**.
3. The joint planner (`plan_flow_coverage_multi`) still returns a 3-move
   "covering" plan (even at 500 k states) → **planner + flow model are fine**.
   But that plan moves the phantom merged blob, which is unrealizable: the
   engine moves exactly ONE selected sprite.
4. In `_execute_step`, selecting the blob clicks its centroid, recolouring only
   ONE sub-block to 9; `selected_cells == stored_piece_cells` is therefore
   NEVER true for the 176-cell entry → the executor SPINS re-selecting and
   **commits ZERO spills on L2**, then graph fallback burns the budget
   (2/6 @0.1429 unchanged @3000).

## Build spec (Pass 2/3 — floor-gated)

1. Detect + snapshot the 4 pieces from the PRISTINE change-phase entry board
   (before the sacrificial spill/probe corrupts positions), keyed by identity.
2. Track each piece by the unique colour-9 SELECTED region (stays separable
   even touching colour-8 neighbours); re-snapshot after each move; stop relying
   on colour-8 connected-components once pieces can be adjacent.
3. Plan jointly over the 4 real pieces (`plan_flow_coverage_multi`; may need
   `max_states` up or a per-stream target→piece assignment to stay tractable).
4. VERIFY `simulate_flow` faithfulness on multi-source before trusting a plan
   (L0/L1 prove single-source; 3-stream cup coverage is UNVERIFIED end-to-end).
5. Gate the multi-source path on an L2-class signature (≥3 sources OR ≥4 pieces)
   so L0/L1 stay byte-identical (floor SACRED: L0 1.0 / L1 1.0).

## Faithfulness addendum (measured — changes the build plan)

Ported the engine spill droplet-BFS offline (`scratchpad/sp80_faithful.py`):

- **`simulate_flow` is NOT faithful for L2.** Engine covers 2/3 targets with
  NO blocks (side sources self-satisfy by spreading AROUND the cup corner into
  the mouth); `simulate_flow` reports 0/3 (it flows THROUGH non-interior target
  corner cells + ignores the hazard). So Pass 2 cannot reuse the existing flow
  kernel as the L2 oracle — it needs the faithful spread-around + wall-hazard
  semantics. L0/L1 clear only because their geometry stays in the kernel's
  faithful mouth-aligned regime.
- **Hazard fatal + straight blocks only SPLIT.** Any droplet touching the y=15
  wall fails the level even with all targets satisfied. Water is never absorbed.
  The middle source (x=6, a non-cup column) must be steered into cup1, but a
  straight block SPLITS a stream (only L5/L6 `tuvkdkhdokr` turn one) → the other
  branch heads for a hazard column. A 60k random 4-block search found 0 hazard-
  free 3/3 layouts — but L2 HAS a human baseline so it IS solvable; the 0-wins
  reflects random search being a poor solver over 4 independent blocks (needs
  structured CHANNELING), not hardness. Border `bodekplurlf16` = OFF-grid ring
  only; the fatal wall is the in-grid y=15 `waoewejnqzc` row.

**Pass-2 step 0 (revised):** validate the port against the live engine on the
known L0/L1 winners (reproduce offline), THEN run a proper channeling search
(BFS/greedy over placements) with the faithful oracle — not random — to find the
hazard-free covering layout, then wire perception (pristine 4-piece snapshot +
colour-9 tracking) + execution around it.

## Next-pass state

Pass 2 = the perception/tracking rebuild per the spec above, in a separate
floor-verified commit; verify multi-source physics first, then deterministic ×2
before claiming any L2 clear.

## Related

- [[../games/SP80]] — the "L2 DECODE (R92)" section carries the full bank.
- [[r84_bounded-frontier-scan]] — corrected: sp80 is MULTI-SESSION for
  multi-piece tracking, NOT angled deflectors.
- [[../lessons/faithful_offline_simulator_20260715]] — the sp80 flow kernel is
  a learned-operator + plan instance; the L2 fix is perception/tracking, not
  the operator.
