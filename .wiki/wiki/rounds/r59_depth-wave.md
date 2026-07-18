---
round: r59
axis: script25 depth (kernel expressiveness) — faithful-sim + learned-operator wave 2
keywords: [m0r0, pressure-plate, gates, bp35, frontier-exploration, su15, enemy-in-sim, re86, separation-by-motion, sk48, lockstep, reachability, lp85, twist-topology, ls20, moving-changer, r59s1, full-25]
verdict: PASS — official card 18.02% → 21.56% → 22.25% → 26.38% → 27.25% → 27.80% → 28.47% → 29.25% → 29.53% → 30.53% (first 30% crossing) → 30.61% → 31.08% → 31.57% → 31.79% → 32.68% → **32.11% (r59s15 ENV-CORRECTION, 2026-07-19 06:21)** — 15 stale env dirs archived, cn04's stale inflation removed (-0.169) + s5i5 recovered (+0.028); lp85 FULLY CONQUERED 8/8 (sixth conquest)
commit: 9b8e2e8 (r59s1 HEAD) / cc1e4dc (r59s2 HEAD) / f8144df-era (r59s3 HEAD); landings: bc04e63, 6b6ad2e, b2128c9, 36d23cd, 3b6c11c, 0197b8b, fa8e3bc, 12bda52, a1701f9, 0abeb0d, 2bdea69, e698ed8(ls20 L5), 02fe3d8, f677aed, 9647858, e536f65
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

## r59s2 official (2026-07-17 00:36 KST, ceph-build, @5000, HEAD cc1e4dc)

`games=25 total=5.5615 → 22.25%` — EXACTLY the arithmetic prediction. Only 2 rows moved vs
r59s1 (re86 0.0328→0.1162, su15 0.1035→0.1923); the other 23 byte-identical across two full
runs. r59s3 launched at the overnight HEAD (m0r0 6/6 @1.0, ls20 6/7 @0.75, su15 6/9 @0.4368,
lf52+g50t first clears, ar25 2/8) — arithmetic prediction ≈ **26.4%**.

## r59s3 official (2026-07-17 00:52 KST, ceph-build, @5000) — **26.38%**

`games=25 total=6.5940 → 26.38%` — the overnight-wave HEAD. Exactly 6 rows moved vs r59s2,
each matching its lane-reported value precisely: ar25 0.0278→0.0833 (geared-copy L1),
g50t 0→0.0357 (FIRST clear, ACTION5 ghost), lf52 0→0.0182 (FIRST clear, peg solitaire),
ls20 0.3571→**0.7500** (L5 pixel push-carry + L6 multi-goal 3-mover, L1-L6 all 1.0),
m0r0 0.7143→**1.0000** (L6 joint block-pin — FULLY CONQUERED), su15 0.1923→0.4368
(spare-sacrifice + idx5). Post-HEAD: tn36 first clear e536f65 (+0.0357 game) → next-run
arithmetic ≈ **26.52%**. **MILESTONE: all 25 games clear ≥1 level** (last zero game tn36
fell at 00:41). Day arc 18.02% → 26.38% (+8.4pp, 1.46×). With the lp85 stall give-up
(7ac5a00) the full-25 wall time dropped from ~3.7h to ~15min.

## r59s4 official (2026-07-17 02:14 KST, ceph-build, @5000) — **27.25%**

`games=25 total=6.8122 → 27.25%` — exact arithmetic match (7th consecutive). Two rows moved
vs r59s3: tn36 0→0.1071 (L0+L1 first clears, opcode-panel program synthesis; L2 parked on the
unfindable tozzsf frame-selector), re86 0.1162→0.2273 (L4 multi-piece recolour-routing FSM;
L5 parked: 3 movables + 3→2 set-cover + mid-edge station). Late-night closes: ls20 L7 parked
(life-gated fog observation — two independent approaches falsified), s5i5 a48e4b1d
rotation-walled (perception fix built + reverted card-neutral), cn04 closed 2/5 (render-kick
artifact), tn36 L2 / g50t L1 / re86 L5 / lp85 σ² parked with complete specs.

## r59s5 official (2026-07-18 17:03 KST, ceph-build, @5000) — **27.80%**

`games=25 total=6.9511 → 27.80%` — 8th consecutive exact arithmetic match. ONE row moved
vs r59s4: re86 0.2273 → **0.3662 (5/8)** via the L5 multi-piece recolour-routing solve
(d63c823): flood-drive discovery (a move DURING a recolour flood drives the piece — the
"geometric wall" was the flood-wait carrying the body into station-14), ACTION5-as-flood-wait,
push-into-corner (same-colour overlap never re-floods), rightward centre-waypoint ascent.
Loader lesson strengthened (6e9ca3e): re86 is the INVERSE confirming instance of the s5i5
short-name-vs-scoring-path divergence — attribute scores only from the run's own loaded-hash
log line. Post-r59s5 state: g50t L1 = camera-lock scrolling SLAM park (107f3f9); re86 L6-L8
frontier recorded; remaining queue all multi-session parks with complete specs.

## r59s6 official (2026-07-18 18:31 KST, ceph-build, @5000) — **28.47%**

`games=25 total=7.1178 → 28.47%` — 9th consecutive exact arithmetic match. ONE row moved
vs r59s5: re86 0.3662 → **0.5329 (6/8)** via the L6 reshape-and-place solve (c5247ec):
per-piece mechanic split (outline = perimeter-conserving reshape vs cross = bar-shift in a
fixed frame — the tag-list difference resolved the prior "unreachable branch" mystery),
corridor bar-control placer with deliberate-collision sequencing, L6 at 68a vs human 139 =
capped 1.0 at weight 6. re86 sprint arc: 1/8 → 6/8, level with the brittle solver's
historical ceiling, pure frame-only. L7 decoded as a recolour+reshape+place HYBRID (1caf774,
queued); L8 unopened.

## r59s7 official (2026-07-18 20:31 KST, ceph-build, @5000) — **29.25%**

`games=25 total=7.3122 → 29.25%`. ONE row moved vs r59s6: re86 0.5329 → **0.7273 (7/8)** via
the L7 recolour+reshape+place hybrid (d1c5e1c) — PAST the brittle solver's historical 6/8
ceiling, frame-only. Method: a faithful offline simulator of the engine's cross-collision
handler + BFS'd push sequences (22/22 live-validated), the occlusion-vs-flood identity
breakthrough (cycle-index identity + occlusion-safe drive), width-aware recolour. L8 probed
+ decoded (a64eda5: SIMPLER than L7 — two outlines, no crosses) — build in flight for
**8/8 = 5th full conquest**.

## r59s8 official (2026-07-18 22:05 KST, ceph-build, @5000) — **29.53%**

`games=25 total=7.3836 → 29.53%`. ONE row moved vs r59s7: g50t 0.0357 → **0.1071 (2/7)** —
the first-ever g50t L1 clear (87c48bb), resolving the EIGHT-lane saga with one perception
root-cause: TWO colour-9 blobs (moving player + static goal); every prior diagnostic's
min()-selection locked onto the GOAL, manufacturing the fake camera-lock, fake lag-2, fake
offset-instability, and fake "no reachable plate" (all now ⛔-marked SUPERSEDED in G50T.md).
Real model: fixed camera, lag-1, plain frame-readable maze; reactive barrier gating (barrier
state IS frame-observable, colour 5/8 — no ghost-clock arithmetic). N-ghost architecture
landed (15dc74c); L2 decoded to its real question (no reachable plate — ghost-path pressing,
this time measured with CORRECT tracking) and parked.

## r59s9 official (2026-07-19 00:42 KST, ceph-build, @5000) — **30.53%, FIRST 30% CROSSING**

`games=25 total=7.6336 → 30.53%`. ONE row moved vs r59s8: ls20 0.75 → **1.0000 (7/7 —
FULLY CONQUERED, 5th full-conquest game, 377 total actions, every level per-level 1.0)** via
the L7 Fog clear (1e5cb6f): the refill-chained observation post angle, which REFUTED the two
prior passes' "no reachable cell sees the whole track" wall (posts (49,15)/(49,20) see all
six track cells — the real blocker was push-wall-aware navigation to REACH the column).
Second game in two days whose terminal wall was a prior pass's measurement artifact (after
g50t's goal-tracking bug). Full-conquest roster: ft09 1.0 · m0r0 1.0 · ls20 1.0 · cd82 0.98 ·
sb26 0.846.

## r59s10 official (2026-07-19 02:03 KST, ceph-build, @5000) — **30.61%**

`games=25 total=7.6513 → 30.61%`. ONE row moved vs r59s9: lp85 0.1637 → **0.1814 (4/8)** via
the σ² conflict resolution (0a8b08a): the conflict was REAL under-determination (6 colours /
20 cells — 2-press pair signatures collide); fix = learn from the FULL colour TIME-SERIES
over K presses (σ(a) = the cell whose series is a's delayed one step; certify only at K≥8 —
a single press can yield an all-exact single-cycle that is WRONG). New generic kernel
learn_successor_from_series. su15 idx6 closed at 6/9 (winnability PROVEN — 8-click oracle;
both oracle-free routes fail on ONE ±1-step root cause; lag-compensating predictor = reopen).
lp85 L5 probed: blocker = corner-target detection at render scale (queued #91).

## r59s11 official (2026-07-19 02:25 KST, ceph-build, @5000) — **31.08%**

`games=25 total=7.7696 → 31.08%`. ONE row moved vs r59s10: lp85 0.1814 → **0.2997 (5/8)** via
the scale-robust detection fix (5551b78): L5's 27×32 grid renders sprites ~4× so EVERY fixed
pixel threshold mis-fired at once; fix = derived tile unit u with relative thresholds that
EQUAL the old constants at u=4 (L2-L4 byte-identical) + Jaccard ring grouping + coarse-board
multipress gate. Bonus: L1 improved 18a/0.892 → 8a/1.0 (disclosed deviation, KEPT — strict
deterministic improvement). New transfer lesson: scale_relative_thresholds_20260719 ("fixed
pixel thresholds are scale debt", sibling of the colour-constant lesson). lp85 ladder mapped:
L6 = dedicated wall (27+ rings, dests mismatch), L7 likely cheap after L6, L8 = L6's class.

## r59s12 official (2026-07-19 03:44 KST, ceph-build, @5000) — **31.57%**

`games=25 total=7.8921 → 31.57%`. ONE row moved vs r59s11: lp85 0.2997 → **0.4222 (6/8)** via
the L6 occlusion-robust coupled-map build (e5913ad): 36 rings = 7 coupled press-cells;
temporal-mask goal-occluded samples + inject each goal's OWN motion as the authoritative edge
for its occluded cell; class-aware joint 3-token BFS, 70 of 80 budget (56 learn + 14 plan);
L6 70a/human60 = 0.735. L7 banked with the runtime-coupling-probe gate spec (frame-count-
identical to L3 — lowering the static gate would regress L2/L3 from 1.0; §R72). lp85 sprint
arc: 3/8 → 6/8 across four rounds (time-series learner, scale-robust thresholds,
corner-square extraction, occlusion-robust coupled maps — four generic perception/learning
upgrades).

## r59s13 official (2026-07-19 04:06 KST, ceph-build, @5000) — **31.79%**

`games=25 total=7.9468 → 31.79%`. ONE row moved vs r59s12: lp85 0.4222 → **0.4769 (7/8)** via
the L7 failure-triggered coupled retry (a26a20f): L7 is frame-count-identical to L3, so
instead of the banked prophylactic coupling probe, the coupled path arms ONLY when the
single-press planner returns None — "did the normal planner fail?" IS the discriminator.
L2/L3/L5 win on single-press and never reach the retry (byte-identical, zero extra presses);
L7 clears in 49a = 0.282. Design principle worth naming: **prefer failure-triggered fallback
over prophylactic probing when the failure itself is observable and cheap**. lp85 session arc
R70–R74: 3/8 → 7/8. L8 attempted (R74, bank a7b1cc8): footprint-adaptive K learned 44/45
cells with PERFECT reconciliation and a GT 18-press solution EXISTS under budget, but the 3
coupled rings (D=14/E=16/F=15) are spatially INTERLEAVED + colour-duplicated — separation
defeats K=20 and gap-4 clustering; both fixes measured card-neutral and REVERTED (clean 7/8,
zero dead code); multi-session bank with three candidate directions. Also the THIRD
stale-frame park refuted by settled-frame verification (L8's "movers=3/dests=2" was an
artifact) — verify-don't-trust-parks again.

## r59s14 official (2026-07-19 05:54 KST, ceph-build, @5000) — **32.68% — lp85 FULLY CONQUERED (sixth)**

`games=25 total=8.1691 → 32.68%`. ONE row moved vs r59s13: lp85 0.4769 → **0.6992 (8/8)** via
the L8 open-chain geometric repair (3e5ca3a): the R77 insight — the colour bijection's own
cycle decomposition IS the ring separator (no spatial separator needed; the three banked
spatial candidates retired) — implemented as `_repair_open_chain` with a
complete-vs-incomplete-PERMUTATION gate (heads=keys−values, tails=values−keys; both empty →
unchanged), floor-safe BY CONSTRUCTION and measured no-op on every L1-L7 coupled map. The
R77 "fixed point" trigger was found INERT at build time (fragmentation renders as chain
heads/tails, never m[c]==c self-loops) — gate-check-first discipline caught it pre-splice.
Open-chain cells rebuilt by learn_cyclic_successor (position-based, immune to within-ring
colour periodicity), goal-injection fills the occluded 16th cell, spliced → complete
[16,15,14] map → _cb_build_plan finds the plan. **L8: 47a vs human 159 = per-level 1.0
SUPER-HUMAN.** Deterministic ×2 (@400/@700 identical), L0-L6 byte-identical
(8/17/24/40/45/70/49). su15 idx6 closed in parallel this night (R75-R75d): vacuum-pin
ORACLE-VALIDATED (run_pin --danger 16, @10 ×2) but FOUR frame-only perception routes
measured-falsified — the wall is the integer 64×64 observation space itself (the oracle
merge click is 1px-unplaceable) → parked at the sub-pixel-perception wall. g50t L2:
source-decoded (3 plate→barrier→block chains), colour-11 premise self-falsified pre-build,
parked at the ghost-reachability wall. Conquest roster: ft09 1.0 · m0r0 1.0 · ls20 1.0 ·
cd82 0.98 · sb26 0.846 · **lp85 0.6992**.

## r59s15 ENV-CORRECTION official (2026-07-19 06:21 KST, ceph-build, @5000) — **32.11%**

`games=25 total=8.0278 → 32.11%`. NOT a single-diff run BY DESIGN: this is the measurement-
integrity correction after the duplicate-game_id audit (see
[[../lessons/env_metadata_duplicate_game_id_20260719]]). 15 of 25 games carried a stale
old-hash dir whose metadata.json claimed the NEW game_id; arc_agi resolves duplicate ids by
rglob filesystem order, so ceph-build (ext4) had been loading OLD content for FIVE games
(cn04/s5i5/sc25/tn36/tu93) while reporting the new game_id — found via the s5i5
zero-recovery round (a83d82d) + a full loader-line audit of r59s14. All 15 stale dirs
archived to environment_files_archive/ on both machines; r59s15 loader lines verified
current-content for all five. Diff vs r59s14 — exactly two rows moved:
- **cn04 2/5 @ 0.2000 → 1/6 @ 0.0309** (stale-content inflation removed; the historical
  "budget-conditional cn04 1/6@1000 local vs 2/5@5000 VM" anomaly is hereby CLOSED as
  content divergence, not budget)
- **s5i5 0/8 → 1/8 @ 0.0278** (recovery predicted by R79)
- sc25/tn36/tu93: identical scores on current content (adapter behavior transfers).
32.68 → 32.11 is an integrity correction, not a regression: the card now measures the
API-current content deterministically on any filesystem.

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
