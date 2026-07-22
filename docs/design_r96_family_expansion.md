# R96 design — hypothesis-DSL family expansion: ControlledGridDynamics

Status: v1 (Codex CONDITIONAL GO after narrowing, 2026-07-23 04:24 — log
`codex_r96_design_review.log`. BINDING corrections below; the v0 draft is
kept underneath for provenance).

## Codex v1 corrections (binding)

1. **Family/oracle mismatch was the dominant defect (65% of risk as drawn)**:
   the v0 draft conflated the WIN-PREDICATE family (T1 reach) with a
   TRANSITION family (single-avatar grid steps) — and neither oracle fits
   single-avatar GridStep: m0r0 is COUPLED two-actor motion ending in an
   actor–actor MERGE; dc22 is a click-mutated passability PRODUCT GRAPH.
   Family renamed **ControlledGridDynamics**, v0 variant =
   **CoupledActorMerge**. R57's "12+ T1 games" is a goal-detector count, NOT
   GridStep expressibility — never read it as coverage.
2. **Contract floor = m0r0 idx0+idx1 ONLY.** idx0 proves coupled motion +
   exact merge; idx1 proves full-map grounding, intentional divergence, and
   independent collision/desync (rejects naive greedy convergence). dc22
   drops to v1 as a labelled near-OOD/schema-expansion control (expected
   UNSUPPORTED/UNKNOWN pre-execution — it is a SECOND transition family:
   mutable passability + interleaved click operators; clicks-then-walk was
   falsified). tu93 stays the far-OOD control. Budget note: reconcile
   "≤27 actions" — the documented dc22 plan is 20 actions vs 78 historical
   live discovery+execution; the frozen contract must state whether
   discovery probes count and cite the qualifying run.
3. **Schema v1** (replaces the v0 sketch):
   - `objective: ActorRelation { actors: [role_a, role_b], relation:
     same_cell | adjacent | overlap }` — m0r0 oracle = same_cell (exact
     merge, NOT adjacency).
   - `transition_model: CoupledGridStep { actors, per_action_deltas
     (PER-ACTOR, harness_measured — symmetric/antisymmetric), collision_policy:
     independent_stay, occupancy: StaticOccupancy (TYPED — StaticOccupancy |
     ObservedEdgeGraph | StateDependentOccupancy, with confidence +
     observation context + layout epoch; a bare blocked-cell set is unsafe),
     terminal_cells: hazard_soft_reset }`.
   - No-displacement probes are "no observed displacement" evidence, NOT
     automatically blocked cells (no-op attribution: wall / dropped input /
     settle / terminal-reset / inert must stay distinct).
   - `EmpiricalMoveMatrix` is VERIFY-ONLY: it may check transitions but
     compiles to UNSUPPORTED (a fixed matrix cannot represent
     collision-dependent desync; never silently BFS).
4. **Frozen m0r0 mutant set (6)**, each with an expected-verdict entry
   (honest UNKNOWN where traces lack discriminating evidence): adjacent-not-
   same_cell · static-goal/partner-initial-cell-not-relation · single-actor ·
   same-delta-both-actors · all-or-nothing-blocking · hazard-as-wall.
5. **Per-actor prose evidence** (R95 lesson applied to relational motion):
   e.g. "On three settled action-1 probes, actor A moved one cell left twice
   while actor B moved one cell right twice; on the third probe A stayed and
   B moved."
6. **Risk register additions** (10 items — multi-actor identity through
   crossing/merge, probe destructiveness incl. hazard resets, map
   completeness vs online learning (m0r0 was solved by FULL frame parsing
   after reactive passability failed), context-dependent passability, no-op
   attribution, terminal-evidence thinness (merge-vs-adjacent needs
   near-terminal negatives), verifier/compiler mismatch, split budget caps,
   stale T1 coverage accounting). **Residual risk after narrowing: ~55%
   grounding/state reconstruction** (full occupancy parsing + stable
   two-actor tracking through blocking/crossing/adjacency/merge), 20%
   verifier discriminability, 15% model selection, 10% compiler/live loop.
7. Inexpressible-in-v0 bank (recorded, no scope creep): m0r0 L3
   selection-mode arrows, L5 momentary pressure gates, L6 joint
   (actor0, actor1, block) planning; dc22 L1 sprite collision + walk-on
   triggers + click-opened barriers.

## R96 EVALUATION CONTRACT (step i — FROZEN 2026-07-23 04:26)

- **Game & levels**: m0r0 idx0 and idx1 (the model criterion level = idx0,
  oracle-proven first; idx1 in sequence within the same run).
- **Fresh-reset procedure**: new env + RESET per run; every action resolved
  through the grounding service at action time; no replayed sequences.
- **Budgets (split caps, per the risk register)**: discovery probes ≤30
  actions/run; solve ≤150 actions/level; hazard soft-resets consume the
  level budget (they are real actions); wall-clock ≤20 min/run incl. LLM.
  Discovery actions COUNT toward the run's action total but are reported
  separately.
- **Repetitions & aggregation**: oracle gate 3/3; model substages 3 runs per
  model per substage, success = ≥2/3; CONFIRMED = both models.
- **Substage order**: canned-instance selection (oracle + the 6 frozen
  mutants, serialized neutral) → variant-first slot filling.
- **Controls**: dc22 idx0 = near-OOD (expected UNSUPPORTED/UNKNOWN
  pre-execution); tu93 = far-OOD. Neither gates.
- **Prohibited leakage**: as R95 (no adapter code, wiki, game ids, provenance
  labels, gold sequences); prose-only evidence (R95 notation lesson).
- **Non-counting**: UNKNOWN never executes; manual/oracle-assisted clears
  recorded but not counted.
- **Falsification**: oracle gate failing on grounding (two-actor tracking /
  occupancy parsing) = the pre-declared 55% outcome → round pivots to
  grounding work, not schema/model changes.

## v0 draft (superseded by v1 above — kept for provenance) Successor to R95 (`design_hypothesis_dsl_r95.md`,
round CLOSED with the contract complete on the cell-state family). R96 applies
the PROVEN R95 pipeline — family schema → grounding service → verifier →
compiler → live oracle gate → model substages — to the SECOND family, chosen
for maximum coverage.

## Family choice: movement / reach-coincidence (T1)

- Largest family in the R57 typology: 12+ of 25 public games cite T1
  (ar25, m0r0, dc22, bp35, sp80, tu93, ls20, cn04, sk48, s5i5, lp85, vc33).
- Kernel support exists: `kernels/paths.py` (BFS/A*), `kernels/motion.py`,
  `track_objects`, the graph-frontier experience, and the GoalLedger arrival
  detector.
- Per the R95 Codex correction, `reach_mode` is its own closed question:
  `click_locus | move_actor | move_non_actor | unknown`. R96 v0 scopes to
  **move_actor** (walk the avatar to a goal) — the simplest, most common
  sub-form.

## Oracle games (decoded ground truth, per the oracle-first doctrine)

- **m0r0** — FULLY CONQUERED (1.0, offline reconstruction + joint BFS): the
  primary oracle game; mechanics fully decoded.
- **dc22** — conquered at idx0 (efficient discovery ≤27 actions); the second
  variant game (movement + obstacle elimination flavour).
- OOD control (labelled, not gating): tu93 (corridor-follow motion — known
  NOT expressible as straight grid steps; expected honest UNKNOWN/DIVERGED).

## Schema sketch (MovementHypothesis envelope)

- `objective`: tagged union
  `ReachGoal { goal_selector (harness-shortlisted role), arrival_predicate }`
  | (future variants: ReachAllGoals, ReachThenReturn).
- `transition_model`: tagged
  `GridStep { dir_map (harness_measured from probe moves), passability
  (learned: blocked-cell set, harness_measured) }`
  | `StepUntilBlocked` | `EmpiricalMoveMatrix` (the discriminative
  multi-effect claim, verifier-checkable via move footprints).
- `phases`: same typed guard vocabulary (level_advanced terminal; future:
  key/door phases).
- Ownership per R95: model selects SEMANTICS (which shortlisted region is the
  goal, arrival predicate kind, guards); harness measures dir_map,
  passability, player identity, move footprints; compiler derives the path.

## Pipeline reuse vs new work

| component | reuse from R95 | new for R96 |
|---|---|---|
| contract | template (levels, fresh-reset, 2/3, leakage) | m0r0 idx0+idx1 + dc22 idx0 targets |
| schema | envelope/ownership/guard machinery | movement union above |
| grounding | service frame, epoch/rebind, UNKNOWN discipline | PLAYER tracking (mobility identity), dir_map + passability acquisition from probe moves |
| verifier | verdict machinery, episode splits, mutant-table gate | movement mutant set (wrong goal selector, wrong arrival predicate, move-matrix negative) |
| compiler | plan stepper contract, typed failure surfaces | GridStepPlan = paths.py BFS over learned passability, per-move confirmation |
| live driver | warm-up/discovery/gate flow, echo instrumentation | directional probe discovery (ACTION1-4 sweep), PROSE evidence lines from day one (the R95 lesson) |
| model stage | select + fill substages, both models rule | movement candidate instances + slots |

## Evidence lines (prose from day one — lesson prompt_notation_misparse)

- "Pressing <dir> moved the small region by <dx,dy> in <k> of <n> probes"
- "<M> directional presses produced no change (blocked)"
- "A distinct region of colour <c> did not move under any press" (goal
  candidate context, harness-shortlisted)

## Pre-declared risks

1. Player identity on multi-mobile-region games — grounding's mobility
   ranking must pick the controlled region; UNKNOWN if ambiguous (probe:
   does it move under EVERY direction?).
2. Passability learning is per-game online (like R95's cycle acquisition);
   budget-capped, GROUNDING_INCOMPLETE when the goal is unreachable in the
   learned graph.
3. dc22's elimination flavour may need a second objective variant — if so,
   scope v0 to m0r0 only and record dc22 as the first expansion candidate
   (no scope creep against the contract once frozen).
