# R98 design — hypothesis-DSL family expansion #3: FlowDeflectionDynamics (PIVOTED)

Status: v1 (Codex CONDITIONAL GO 2026-07-23 12:25 — the v0 PushDynamics
draft is PIVOTED per the review; v0 kept below for provenance; full review
scratchpad/codex_r98_design_review.log).

## Codex v1 binding corrections (2026-07-23)

**Family/oracle validity was the dominant v0 defect (60-70% risk class,
the R96-v0 pattern repeated)**: the 15-game backlog contains NO clean
classic-sokoban row, and none of the three proposed oracles certifies
one-cell contact push — ka59 is a SELECTED-MOVER MOMENTUM LAUNCH
(multi-cell displacement, settling ticks, terrain-crossing;
adapters25/ka59.py:216), ls20 is a STATIC CONTACT LAUNCHER (the push-wall
shoves the avatar; no movable box), sk48 changes body topology (excluded).
A ka59 clear under PushStep would certify the WRONG transition model.

1. **PIVOT: R98 = SP80 FlowDeflectionDynamics, oracle sp80 idx0** (the
   Codex readiness-ranked #1): one coherent backlog transition family with
   existing measured assets (learned flow operators, simulation, coverage
   planning — kernels from R56 #45/#65) and a super-human live idx0
   oracle. The two-phase CHANGE→SPILL structure must be explicit in the
   schema. (Readiness ranking, not a private-110 frequency claim.
   Runners-up recorded: RE86 RecolourOnContact — strongest depth evidence
   but 3-level prefix to the criterion; WA30 CarryDelivery idx0;
   OneCellContactPush deferred until a matching live oracle exists.)
2. **ONE transition variant only** — never union push/momentum/static-
   launch/carry/grow-retract into a broad family.
3. Compiler claims must match reality: kernels/paths.plan_push searches
   (box, pusher) for ONE box — multi-entity planning must be built and
   certified or scoped out.
4. Schema must state: actor post-state, destination semantics (walls/
   blocks/actors/hazards/bounds/goals/state-dependent occupancy), entity
   footprint, displacement distance, goal interaction (persist/lock/
   transform/consume), control mode, settling/observation epoch.
5. Every mutant pre-certified against exact train/held-out transition
   tuples; honest UNKNOWN where evidence lacks discriminating
   opportunities; transition vs objective mutants reported separately.
6. Thresholds frozen separately: oracle gate 3/3; model substages ≥2/3.
   CRITERION LEVEL ONLY — do not copy "idx0+idx1 in sequence"
   mechanically; oracle evidence must include both a successful effect and
   a blocked/negative comparison that discriminates the mutants.
7. Near-OOD control = a mechanically CONFUSABLE negative for the chosen
   family (per Codex: e.g. WA30 carry), not m0r0 by default; far-OOD tu93.

Additional risk-register items (bound): movable-vs-static classification
must be ASYMMETRIC (coherent observed movement = strong positive; failure
to move = weak evidence — the R96 transient-evidence lesson); unlabeled
position MULTISET for interchangeable same-looking entities (no unstable
identities); **probe destructiveness** near the top — discovery needs
reset-separated probe episodes or a certified-safe probe locus (a probe
can irreversibly corner an entity). Post-pivot risk allocation: ~40%
grounding/state reconstruction, 25% compiler/search, 20% verifier
discriminability, 10% model, 5% live/settling.

NEXT STEP: draft the FlowDeflection schema (change→spill phases, deflector
semantics from the sp80 decoded mechanics + #117's L2 findings) as v1.1,
one more Codex consult on the schema only, then freeze the contract.

## v0 draft (SUPERSEDED by the pivot — kept for provenance)

Status: v0 draft (2026-07-23, pre-Codex). Successor to R96
(`design_r96_family_expansion.md`, ROUND COMPLETE — ControlledGridDynamics
measured end-to-end) and R97 (`design_r97_self_extension.md`, CONFIRMED
SEED-PASS both models). Applies the proven pipeline — family schema →
grounding → verifier → compiler → live oracle gate → model select+fill —
to its THIRD family, chosen from the 15-game inexpressible backlog.

## Family choice: PushDynamics (actor pushes movable blocks)

From the backlog, the push/delivery cluster is the R96-anticipated next
investment ("grid grounding/occupancy/path search are prerequisites for
future push/delivery families" — the prerequisites now EXIST and are
measured: two-actor grounding, typed occupancy with confidence/context/
epoch, joint BFS, online wall/hazard learning, observation-trumps-inference
invalidation, the transient-evidence model).

Core transition claim: the actor moves per directional keys; a MOVABLE
block in the actor's path moves one cell in the push direction iff its
destination cell is free (else both stay); walls block both; objective =
block(s) on goal cell(s) (sokoban-class) or actor-reaches-X-with-block-
state (variant).

## Oracle candidates (Codex to rank — oracle-first doctrine)

1. **ka59 idx0** (sokoban proper): L1 CLEARED, push mechanics DECODED
   (generic push-planner kernel, task #49; multi-round settled). Criterion
   level = idx0, exactly the R96 m0r0-idx0 pattern. Risk: only 1/7
   conquered — deeper levels lack gold; the criterion stays idx0-only.
2. **ls20** (fully conquered 7/7 @1.0, offline reconstruction incl. the L5
   sprite-pixel push-carry model + L1-L4 pushwall fixtures): richest gold,
   but the mechanic is COMPOSITE (push + refill + fog + entry-conditioned
   mutation) — risks conflating the push family with game-specific
   composition, the exact v0 mistake Codex corrected in R96.
3. **sk48 side-push grow/retract** (backlog entry): a DIFFERENT push
   variant (body extension, not block displacement) — likely a separate
   family; flagged so Codex can confirm exclusion.

## Schema sketch (PushHypothesis envelope — reuses the shared machinery)

- `objective`: tagged `BlocksOnGoals { goal_binding: harness-shortlisted
  goal cells; completion: all | count(n) }` | (variant: ActorAtWithBlocks).
- `transition_model`: `PushStep { actor_deltas (harness_measured),
  block_response: displaced_iff_destination_free (the discriminative
  claim), chain_push: none | single | multi (closed enum — whether a block
  can push another block), occupancy: typed as R96 }`.
- Mutants (frozen table with expected verdicts, R96-style): block-never-
  moves (pure wall) · block-moves-with-actor (carry, not push) ·
  chain-push-when-none · pull-instead-of-push · goal-is-actor-cell ·
  blocks-vanish-on-push.
- Field ownership per doctrine: model selects objective kind + completion
  + chain_push claim; harness measures deltas, occupancy, block identity/
  tracking; compiler derives the plan (push-planner kernel exists —
  kernels/ push search from task #49; the joint (actor, blocks) state
  space is the known sokoban cost, budget-capped).

## Pre-declared risks (Codex to re-estimate)

1. **Block-state grounding** (the R96-lesson analogue, likely dominant):
   tracking N movable blocks through pushes/occlusion; block-vs-wall
   classification from probe evidence (a block MOVES when pushed — the
   behavioural discriminator; static walls never do).
2. State-space cost: (actor × blocks) joint planning explodes with block
   count — budget-capped search + the R56 push-planner kernel as the
   engine, not a fresh BFS.
3. ka59's deeper levels are unconquered — the contract floor must be
   idx0(+idx1 attempt per the R96 "in sequence" precedent), NOT deep
   levels.
4. Evidence prose for pushes must be exact per-entity tuples (the twice-
   measured lesson: state every constraint and quantity in prose).

## Contract skeleton (to freeze post-Codex)

- Oracle game + criterion level per Codex ranking; fresh-reset; discovery
  ≤30, solve ≤150/level; 3 runs, ≥2/3; both models; select + fill
  substages; leakage prohibitions as R95/R96/R97; controls = near-OOD
  (a non-push movement game, e.g. m0r0) + far-OOD (tu93).
- Falsification clause: oracle-gate failure on block-state grounding =
  the pre-declared pivot to grounding work (the R96 pattern).
