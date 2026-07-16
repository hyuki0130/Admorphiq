---
round: r59
axis: script25 depth (kernel expressiveness) — faithful-sim + learned-operator wave 2
keywords: [m0r0, pressure-plate, gates, bp35, frontier-exploration, su15, enemy-in-sim, re86, separation-by-motion, sk48, lockstep, reachability, lp85, twist-topology, ls20, moving-changer, r59s1, full-25]
verdict: PASS — official card 18.02% → 21.56% (r59s1 @ HEAD 9b8e2e8); post-measurement landings put current HEAD arithmetic ≈ 22.25%
commit: 9b8e2e8 (measurement HEAD); post-HEAD: bc04e63, 6b6ad2e, b2128c9, 36d23cd, 3b6c11c, 0197b8b, fa8e3bc
---

# R59 — depth wave 2 (parallel 6-lane team, 2026-07-16)

> One-day parallel depth sprint on the [[r56_generic-kernels]] base: 6 teammate lanes, each
> a bounded pass with a deterministic-×2 floor, explicit-path commits, and verified hashes.
> Official card **18.02% → 21.56%** (r59s1, all 25 games parallel @5000 on ceph-build,
> HEAD 9b8e2e8, every game matching its lane-reported prediction exactly). Two more clears
> landed after the measurement HEAD (su15 4/9, re86 3/8) → current arithmetic ≈ **22.25%**.

## r59s1 official measurement (2026-07-16 16:23–20:04 KST, ceph-build, @5000)

`games=25 total=5.3893 → 21.56%`. Per-game rows archived in the round log; deltas vs r56s9:

| game | r56s9 | r59s1 | what landed |
|---|---|---|---|
| m0r0 | 0.0057 (1/6) | **0.7143 (5/6, all 1.000)** | offline reconstruction → block clearing → constructive placement → L5 momentary pressure-plate gates (9b3727b); L5 48a vs human 500 |
| bp35 | 0.0000 (0/9) | **0.0145 (1/9)** | first-ever generic clear (a1701f9): faithful sim + BFS + visited-aware frontier exploration; gem=colour-7, px from marker column, cam_y=py*6-36 |
| sk48 | 0.1667 (3/8) | **0.2778 (4/8)** | multi-snake + parser fixes; L4 CLOSED single-control-unsolvable by lockstep-faithful sim + exhaustive 94,921-state reachability (d97c6ae) |
| wa30 | 0.0182 | 0.0667 (2/9) | sim macro-plan |
| re86 | 0.0060 | 0.0328 (2/8) | L2 merged-blob bank → cleared |
| others | — | unchanged | ft09 1.0, cd82 0.98, sb26 0.846, ls20 0.3571, tr87 0.2857, cn04 0.2000 (2/5 @5000 VM), sp80 0.1429, lp85 0.1637, su15 0.1035 … |

## Post-measurement landings (in HEAD, not in r59s1; next full-25 picks them up)

- **su15 3/9 → 4/9 @ 0.1923** (bc04e63): enemy-in-sim — per-sub-step chase+vacuum ported into
  the fruit sim, lockstep 0 mismatches, euclidean-vs-Chebyshev fruit matching fix INVERTED the
  "lure_base=20 starves" belief (model artifact), margin search, pure open-loop. L4 two-enemy
  banked airtight-negative for the single-lure class (3b6c11c): no corner far from all fruits
  with two mid-row independent chasers; joint side-parallel plan class designed.
- **re86 2/8 → 3/8 @ 0.1162** (6b6ad2e): [[../lessons/faithful_offline_simulator_20260715]]
  companion pattern — `kernels.separate_by_motion` (perpendicular probe isolates a merged
  same-colour piece; parallel moves over-include) + `kernels.max_coverage_offset` greedy
  gate-claiming. L4 parked with a decoded+live-validated changer/recolour mechanic (0197b8b).
- **m0r0 L6 bank corrected** (b2128c9): "merge oscillates" was a stale-maze probe artifact
  ([[../lessons/probe_validity_20260715]] family); L6 is a block-pin × gate-coordination ×
  mirror-desync joint problem. Gate-detection fix: zone colour read from letterbox padding
  (hazard-dominated boards broke top-2-in-maze counting). Commit-to-plan merge kept.
- **ls20 L5 moving-changer decoded+validated** (36d23cd): deterministic cyclic track-patrol
  (period 4), steps once per SUCCESSFUL avatar move, undoes on block; phase-aware joint BFS
  finds a 43-action plan. Integration round handed to a dedicated lane.
- **lp85 twist-topology arc** (2aae0d0 → fa8e3bc): L4 wall is NOT same-colour ambiguity but a
  twisted ring loop; observation-first successor kernel (unique colours pin far links) +
  drop-on-fail detection (20 buttons → 2 real rings, 12-move plan). Residual: multi-step
  ordering of same-colour cells → σ/σ² multi-press learner round.

## Method notes (what made the wave fast)

- Every lane: bounded pass, floor deterministic ×2 BEFORE starting, level-signature gating so
  cleared levels stay byte-identical, explicit staged paths, hash+triple verified on receipt.
- "Named blocker on a validated foundation earns one continuation" precedent (bp35, lp85,
  su15 L4 joint plan) — vs "new mechanic → park with decoded spec" (re86 L4, m0r0 L6 initial).
- Hygiene incident: one lane's `git add -A` co-committed another lane's staged r11l work
  (3245b15) — work intact, provenance mixed; explicit-path rule re-broadcast.
- lp85 @5000 takes ~3.7h wall (ring planner searches per action) — the long pole of any
  full-25 parallel run; budget floor checks at @400–600 instead.

## Related

[[r56_generic-kernels]] · [[../lessons/faithful_offline_simulator_20260715]] ·
[[../lessons/probe_validity_20260715]] · [[../lessons/false_claim_verification_20260715]]
