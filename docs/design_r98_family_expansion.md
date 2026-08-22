# R98 design — hypothesis-DSL family expansion #3: FlowDeflectionDynamics (PIVOTED)

Status: **v1.2 (AUTHORITATIVE) — CONTRACT FROZEN 2026-08-22.** Schema drafted,
oracle certified LIVE, Codex schema consult landed CONDITIONAL GO with all six
corrections bound and discharged by measurement. Implementation is next.
Earlier drafts are kept below for provenance: v1 (family pivot, Codex CONDITIONAL
GO 2026-07-23) and v0 (PushDynamics, superseded by that pivot).

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

NEXT STEP (done 2026-08-22): the v1.1 schema draft is the section below.

## v1.1 SCHEMA DRAFT — FlowDeflectionDynamics (2026-08-22, SUPERSEDED by v1.2 below; kept for provenance)

Drafted per the v1 NEXT STEP. Ground truth below was re-derived **at dev time
from the engine source** (`environment_files/sp80/589a99af/sp80.py`, loader hash
`sp80-589a99af`) plus the R92/#117 measurements
(`.wiki/wiki/rounds/r92_sp80-l2-premise-correction.md`). None of it enters the
model-facing path — it exists to (a) certify the oracle, (b) pre-certify the
mutant table, (c) bound the contract's budgets.

### Decoded oracle mechanics (dev-time only)

**Two phases, one commit.** CHANGE: `ACTION6` inside a movable piece SELECTS it
(the selected piece is uniquely recoloured); `ACTION1..4` translate the selected
piece by exactly one cell; `ACTION5` COMMITS and enters SPILL. Every non-RESET
change-phase action decrements a per-level step allowance.

**Placement is constrained by two rules, both observable by contrast**: a piece
may not enter the 1-cell halo of any sink (an expanded-AABB test), nor rows above
a fixed top bound; collisions with OTHER MOVABLE PIECES are explicitly permitted
(pieces pass through each other). Everything else blocks.

**SPILL is a deterministic droplet cellular process run to a fixpoint.** Each
droplet has a position and a direction (initially straight down from every
emitter cell). Let `P` be the two cells perpendicular to the droplet's direction
at its CURRENT position. Looking one cell AHEAD:

| ahead cell | engine response |
|---|---|
| empty | advance one cell, same direction |
| existing flow | wait/merge (the droplet persists, no backflow — occupied cells are never re-entered) |
| straight piece | **SPLIT**: spawn a droplet in each empty cell of `P`, each keeping the ORIGINAL direction |
| sink | **satisfy iff BOTH cells of `P` belong to that same sink** (i.e. the droplet is in the sink's mouth notch); otherwise spread around it exactly like a piece |
| angled piece | turn 90° toward the free side; if both/neither side is free, spread like a piece |
| hazard row | mark the attempt FATAL, droplet dies |
| boundary ring | droplet dies harmlessly |

Consequences that matter for the schema: a wide horizontal piece does not turn a
stream — it **walks the stream outward one cell per tick and re-emits it falling
at each outer edge**; and a sink is satisfied by entering its mouth, not by
touching it.

**Settle verdict**: all sinks satisfied AND no hazard contact → level advances.
Otherwise the board flashes (the hazard row and **exactly the unsatisfied sinks**
flash — a free partial-progress signal), then restores: the water is removed and
the sinks/hazard repaint, **but the pieces KEEP their moved positions** and the
origin-nearest piece is re-selected. So a failed commit resets SELECTION and FLOW,
never LAYOUT. Commits are capped (the 5th commit is a terminal loss), and the
step allowance is independent of the commit cap.

**Observability (the reason this family is affordable)**: the entire spill
animation is exposed as successive frame LAYERS of the observation at commit
time, so ONE sacrificial commit reveals the whole trajectory — no tick-stepping.
Measured cost of a sacrificial commit ≈ 2 actions and 1 of the 4 attempts.

**Criterion level (idx0) ground truth**: 16×16, no rotation, one emitter column,
ONE straight piece 5 cells wide, TWO sinks on the same row, a full-width fatal
bottom row. The oracle solution is 3 translations + 1 commit: the piece placed so
that its two outer edges sit exactly one cell outside the two sink mouths, which
splits the single stream into two descending streams that land in both mouths
with zero hazard contact. Human baseline 39 actions; the existing script25
adapter clears it in 10 (efficiency 1.0). idx1 rotates the board 180° (the
per-action deltas invert) and adds multi-piece selection.

### Oracle certification — MEASURED LIVE, not source-derived (2026-08-22 17:33 KST)

`scripts/rounds/R98/oracle_probe_idx0.py` → `oracle_probe_idx0.log`, env
`sp80-589a99af`, repo `b8e4e63`. Three claims, all **PASS**:

1. **The hand-authored oracle clears idx0 in 4 actions** (three translations plus
   the commit). Human baseline 39, so even after spending the full discovery
   budget the level still scores at the per-level cap — the efficiency headroom
   is not a constraint on this contract.
2. **The commit observation carries 20 frame layers** — the whole spill animation
   arrives in one observation, confirming the affordability premise (a sacrificial
   commit is ~2 actions, not a tick-by-tick walk).
3. **The piece response is a direction-preserving perpendicular split.**

Claim 3's evidence is the cell-exact FRONTIER (the cells new in each layer;
the accumulated trail is NOT discriminating because water persists):

```
(1,9) → (2,9) → (3,9) → (3,8)+(3,10) → (3,7)+(3,11) → (3,6)+(4,11)
      → (3,5)+(5,11) → (4,5)+(6,11) → …
```

Read: the droplet falls down column 9 to row 3, where the piece (columns 6..10)
blocks it. It does not turn and is not absorbed — it emits a FLANKING PAIR on the
same row, and that pair walks outward one cell per tick until each side clears an
outer edge of the piece (columns 5 and 11), whereupon each resumes descending.
Columns 5 and 11 are exactly the two sink mouths.

This trace is the transition-tuple ground truth the mutant table is certified
against, and it is the reference the trajectory verifier replays.

### Schema — `FlowHypothesis` envelope

Reuses the shared machinery from `hypothesis_select/schema.py` (`Ownership`,
`_own`, `Phase`, guards, `Verdict`, neutral serialization) exactly as
`schema_movement.py` does; adds only flow-specific tagged unions. New module:
`hypothesis_select/schema_flow.py`.

**Objective (tagged union).**

- `CoverAllSinks` *(executable)* — every sink region must end SATISFIED and the
  attempt must be hazard-free.
  - `sink_role_binding` — which harness-shortlisted regions are sinks · **model_selected**
  - `completion` ∈ `all | count(n)` · **model_selected**
  - `hazard_policy` ∈ `fatal_on_contact | neutral` · **model_selected**
- `AnySinkCovered` *(verify-only)* — the any-vs-all negative; nameable by a
  mutant, mapped to UNSUPPORTED by the compiler.

**Transition model (tagged union).**

- `PlaceThenPropagate` *(executable — the discriminative claim)*
  - `control_mode` ∈ `select_then_translate | direct_translate` · harness_measured
  - `piece_deltas` — per-action `(dr, dc)` for the selected piece · harness_measured
    *(this absorbs the idx1 rotation remap without ever naming rotation)*
  - `piece_footprints` — per-piece cell-sets · harness_measured
    *(pieces are multi-cell bars; a one-cell entity assumption is wrong here)*
  - `placement_constraints` — `{ sink_keepout_margin, row_bound,
    pieces_mutually_permeable }` · harness_measured, each admitted only from a
    CONTRAST (same press moves the piece elsewhere), never from a bare
    failure-to-move — the R96 asymmetric-mobility rule
  - `commit_action` · harness_measured
  - `emitters` + `initial_direction` · harness_measured
  - **`propagation_rules`** — the closed-choice response table, **model_selected**,
    one enum per encountered class:
    - on piece: `split_perpendicular | turn_90 | absorb | stop`
    - on sink: `satisfy_iff_flanked | satisfy_on_contact | spread_around`
    - on hazard: `terminate_fatal | terminate_local | pass_through`
    - on own flow: `merge_wait | overwrite | terminate`
    - on boundary: `terminate_harmless | reflect`
  - `epoch` — `settle_to_fixpoint_then_verdict` · harness_measured
  - `observation_channel` ∈ `animation_layers | tick_frames` · harness_measured
  - `failure_semantics` — `{ attempt_cap, restore ∈ layout_persists |
    layout_resets, selection ∈ resets_to_default | persists }` · harness_measured
- `EmpiricalSpillMatrix` *(verify-only)* — a commit→outcome lookup with no
  propagation model; the compiler maps it to UNSUPPORTED so it can never silently
  plan (the `EmpiricalMoveMatrix` precedent from R96).

**Phases**: `change` → `spill`, shared `Phase` guards, terminal `level_advanced`.

**The central design claim**: for this family the transition model *is* the
simulator. The compiler's plan is a pure function of the model-selected
propagation table, so a wrong table produces a plan the live spill falsifies —
which is exactly what makes the mutant table meaningful rather than decorative.

### Field ownership (the answer to Codex #4)

| slot | owner |
|---|---|
| the 5 propagation responses, sink binding, completion, hazard policy, phase guards | **model_selected** |
| control mode, per-action deltas, piece footprints, placement constraints, commit action, emitters, initial direction, epoch, observation channel, failure semantics | **harness_measured** |
| the placement PLAN — which piece to which anchor, and the select/translate/commit action sequence | **compiler_derived** |

Codex #4's checklist maps as: actor post-state = the piece persists at its new
cell-set (no consumption); destination semantics = `placement_constraints` (sink
halo, row bound, mutual permeability, boundary); entity footprint =
`piece_footprints`; displacement distance = exactly one cell per press (measured,
not assumed); goal interaction = sinks LOCK on satisfaction within an attempt and
repaint on restore; control mode = `select_then_translate`; settling/observation
epoch = `epoch` + `observation_channel`.

### Mutant table (pre-certified against idx0 evidence, transition vs objective separated)

Verdicts are stated against the **contract's discovery evidence set** (below).
Where idx0 offers no discriminating opportunity, the verdict is an honest UNKNOWN
and the contract does not lean on it (Codex #5).

*Transition mutants*

| # | mutant | expected verdict | discriminating evidence |
|---|---|---|---|
| T1 | `piece_absorbs` (on piece → absorb) | CONTRADICTED **(certified)** | the measured frontier emits `(3,8)+(3,10)` at the piece row; absorb predicts an empty frontier |
| T2 | `piece_turns_90` (on piece → turn_90) | CONTRADICTED **(certified)** | turn predicts ONE outgoing cell moving perpendicular; the measured frontier is a symmetric PAIR that later resumes the original downward direction |
| T3 | `sink_on_contact` (on sink → satisfy_on_contact) | CONTRADICTED **iff** the discovery includes a commit whose flow touches a sink's outer wall without satisfying it; otherwise UNKNOWN | contact-without-satisfaction is only observable if a probe routes flow onto a sink corner — the contract makes that probe mandatory |
| T4 | `placement_unconstrained` (no constraints) | CONTRADICTED | a press that produces no displacement next to a sink, while the same press displaces the piece elsewhere (contrast, not bare failure) |
| T5 | `layout_resets_on_failure` (restore → layout_resets) | CONTRADICTED | after the failed sacrificial commit the piece is observed at its post-press position, not its entry position |

*Objective mutants*

| # | mutant | expected verdict | discriminating evidence |
|---|---|---|---|
| O1 | `any_sink_suffices` (`AnySinkCovered`) | CONTRADICTED **iff** a partial-cover commit occurs; otherwise UNKNOWN | the failure flash marks exactly the UNSATISFIED sinks while the level does not advance — the cheapest source of this evidence |
| O2 | `hazard_ignored` (`hazard_policy: neutral`) | **UNKNOWN (pre-declared)** | at idx0 every winning layout consumes all water in the sinks, so "all sinks satisfied AND hazard touched" is not constructible; the pristine commit fails for two reasons at once and cannot attribute |

O2 is deliberately recorded as unattributable at the criterion level rather than
being propped up by a fabricated probe. It is the honest cost of choosing idx0.

### Discovery evidence set (satisfies Codex #6's positive + negative requirement)

1. **Selection** — click inside a candidate region; it changes appearance alone.
2. **Displacement, positive** — a press shifts the whole selected footprint by a
   constant offset; repeated across the four directions to fill `piece_deltas`.
3. **Displacement, negative/blocked** — the same press near a sink produces no
   shift. Costs one action, no commit. This is the blocked comparison.
4. **Sacrificial commit** — one commit whose animation layers expose (a) the
   descending stream, (b) the two-stream split at the piece row, (c) if routed to
   do so, a sink-corner contact WITHOUT satisfaction, (d) the failure flash naming
   the unsatisfied sinks, (e) the post-restore piece position.
5. **Layout persistence** — read the piece position after the restore.

Prose evidence lines only, no notation (the `prompt_notation_misparse_20260723`
lesson, twice measured):

- "Clicking inside the wide region changed that region's appearance and nothing else changed."
- "After the press, every cell of that region moved one cell to the right; no other region moved."
- "The same press produced no movement while the region sat beside the cup-shaped region, and produced a one-cell move elsewhere."
- "When the layout was committed, the animation showed a stream descending one column, and at the row of the wide region two new streams appeared, one cell to each side of it, both continuing downward."
- "Two of the cup-shaped regions briefly flashed and the level did not advance."
- "After the attempt ended, the wide region was still at the position it had been moved to."

### Compiler reality (the Codex #3 analogue — stated before it is claimed)

Existing assets: `kernels/motion.py` — `simulate_flow` (L1090),
`plan_flow_coverage` (L1153), `plan_flow_coverage_multi` (L1208).

**MEASURED GAP (R92, not a guess): `simulate_flow` is NOT faithful.** It tests the
cell AHEAD rather than the current cell's flanks, lets water pass THROUGH a
non-interior sink cell instead of spreading around it, and does not model the
hazard at all. On the L2 board it reports 0 of 3 sinks covered where the engine
covers 2. It is faithful only in the mouth-aligned single-emitter regime that L0
and L1 happen to occupy.

Therefore R98 does **not** reuse `simulate_flow` as its oracle. The compiler gets a
**hypothesis-driven propagator** built from the schema's response table (spread-
around, flank-satisfaction, fatal hazard, occupied-cell no-reentry), plus a
placement search over the single piece's reachable anchors. Reusing the legacy
kernel would silently hardcode the very semantics the model is supposed to select
— it would make every mutant score identically and void the round.

Scope, per Codex #2 (one variant only): v0 = single emitter, straight splitter
pieces, mouth satisfaction, fatal hazard, one movable piece. `turn_90` is
REPRESENTABLE (so a mutant can name it and so the deeper levels stay expressible)
but is **verify-only at idx0** and must not be reported as measured. Multi-emitter
and multi-piece are representable and explicitly OUT of the criterion.

### Pipeline reuse vs new work

| component | reuse | new for R98 |
|---|---|---|
| contract | R95/R96 template (fresh reset, leakage, both models) | engine-imposed budget clause (below) |
| schema | envelope / ownership / guards / serialization | `schema_flow.py` unions above |
| grounding | service frame, epoch/rebind, UNKNOWN discipline | piece identity by SELECTED appearance (never by connected components of the idle colour — the R92 merge bug), emitter + sink-mouth geometry, animation-layer decoding into a trajectory |
| verifier | verdict machinery, episode splits, mutant gate | trajectory-consistency check: replay the hypothesised propagator against the observed layer sequence, cell-exact |
| compiler | plan stepper, typed failure surfaces | hypothesis-driven propagator + placement search |
| live driver | warm-up / discovery / gate flow | commit-budget-aware discovery (below) |
| model stage | select + fill substages, both models | flow candidate instances + the 5 response slots |

### Contract deltas to freeze (do NOT copy R96's numbers)

- **Criterion level = sp80 idx0 ONLY.** idx1 may run as a NON-GATING observation.
  R96's "idx0 + idx1 in sequence" is a level-count coincidence, not a rule
  (Codex #6, criterion-level-only).
- **Budgets are engine-bounded, not template-bounded.** idx0 permits ~30
  change-phase actions and at most 4 committed spills; exceeding either is a
  terminal loss. So the R96 "discovery ≤30 / solve ≤150" template is INVALID here.
  Proposed split: discovery ≤12 actions AND ≤1 sacrificial commit; solve ≤18
  actions AND ≤3 remaining commits; ≤30 change actions total. This is a new
  contract clause created by this pass.
- Oracle gate 3/3; model substages ≥2/3 per model per substage; CONFIRMED = both
  models (gemma4-31b-q8 + gpt-oss-120b).
- **Near-OOD control — the one open slot for the consult.** Codex #7's "WA30
  carry" example was written for the push family and does not transfer: nothing
  about carry-delivery is confusable with two-phase flow. Candidates that ARE
  mechanically confusable (a committed action triggering a scripted propagation):
  **re86 idx0** (contact-driven colour propagation) or **sk48 idx0** (a
  propagating body). Preference re86; to be settled by the schema consult.
  Far-OOD = tu93, unchanged.
- **Falsification**: oracle-gate failure on GROUNDING (piece footprint/identity,
  emitter or sink-mouth geometry, animation-layer decoding) = the pre-declared
  40% outcome → the round pivots to grounding work, not to schema or model
  changes.

### Risk register updates from this pass

- **Probe destructiveness is real but bounded, and differently shaped than
  feared**: a sacrificial commit is non-destructive (the level restores) but
  consumes 1 of 4 attempts; a TRANSLATION is semi-destructive because piece
  positions persist across failed commits. Grounding must therefore re-read the
  piece position after every restore instead of assuming an entry-state board —
  this is precisely the R92 measured defect (a restore left the piece one cell
  off, two pieces became adjacent, 4-connectivity merged them into one phantom
  176-cell region, and the executor spun forever committing nothing).
- **Never identify pieces by connected components of the idle colour.** Track the
  selected piece by its distinct selected appearance, which stays separable even
  when pieces touch.
- Multi-piece selection and multi-emitter interference are the idx1/idx2 burdens
  and are OUT of the criterion; recording them here keeps the expansion path open
  without widening the contract.

NEXT STEP (done 2026-08-22): the consult landed CONDITIONAL GO; its corrections
are bound in the v1.2 section below, which supersedes this draft.

## v1.2 — Codex-bound schema revision (2026-08-22, AUTHORITATIVE)

Codex schema consult verdict: **CONDITIONAL GO** — "the idx0 core is faithful,
but the present contract would permit both false passes and false fails"
(`scratchpad/codex_r98_schema_review.log`). Six binding corrections, all bound
below. Two of the review's open questions were then CLOSED by measurement rather
than by argument (`scripts/rounds/R98/evidence_probe_idx0.py` → `evidence.txt`).

### New measurements that settle open questions (2026-08-22 17:39 KST)

An exhaustive sweep of every reachable placement of the single piece (12
horizontal positions plus row variants), each committed and read to its settle
verdict, env `sp80-589a99af`:

| placement | sinks filled | deepest flow row | advanced |
|---|---|---|---|
| −3 … +1 | 0 | 14 | no |
| **+2** | **2 (all)** | **14** | **no** |
| **+3** | **2 (all)** | **13** | **yes** |
| **+4** | **2 (all)** | **14** | **no** |
| +5 … +8 | 0 | 14 | no |
| (+2,+2) (+2,+5) | 2 (all) | 14 | no |
| (+3,+2) (+3,+5) | 2 (all) | 13 | yes |

1. **O2 (hazard fatal) is now CERTIFIED, not a pre-declared UNKNOWN.** Placement
   +2 fills EVERY sink and still fails; +3 fills the same sinks and advances. The
   pair differs only in whether the flow reached row 14, so the failure is
   attributable to hazard contact alone. This answers the review's D(c): idx0 DOES
   support a fatal-hazard claim, and `hazard_policy` may be gated after all.
2. **O1 (all-vs-any) is UNKNOWN with a PROOF OF ABSENCE.** No reachable placement
   fills a strict subset of the sinks — the sweep is exhaustive, so no probe can
   rescue this mutant at idx0. The v1.1 justification ("the failure flash names the
   unsatisfied sinks") was WRONG, exactly as the review said: the pristine spill
   covers zero sinks, so both flash and `any` predicts failure too.
3. **T3 (contact vs mouth) is CERTIFIED.** In the +2 trace, at layer 12 the flow
   occupied `(12,10)` with the sink cell `(13,10)` directly ahead; it did NOT
   satisfy the sink there but spread to `(12,9)` and `(12,11)`, and the sink only
   became satisfied once the flow reached its mouth column. Contact is not
   satisfaction — measured, not asserted.
4. **Row-independence is measured, not assumed**: the same horizontal placement at
   three different rows produces an identical outcome, so the emergent columns are
   a function of the piece's columns alone.
5. A trap worth recording: water NEVER OCCUPIES the hazard row — a droplet dies on
   contact — so "flow reached the bottom row" is always false and is a broken
   detector. The correct signal is the row ABOVE it. A colour-based failure-flash
   detector is also unusable because the HUD paints the same colour every frame.

### Bound correction 1 — type-shape fixes (review A)

- **Step allowance is now typed**, not folded into `attempt_cap`:
  `budget = { step_allowance, consuming_actions, exhaustion ∈ terminal_loss |
  no_op }`. Which actions consume it is part of the type.
- **`failure_semantics` states every reset**: `{ attempt_cap, layout ∈ persists |
  resets, flow ∈ resets | persists, sink_satisfaction ∈ resets | persists,
  selection ∈ resets_to_default | persists }`. Without the flow and satisfaction
  fields, a cumulative-progress-across-commits model stays representable and
  therefore unfalsified.
- **`on_sink` is a pair, not a single enum**: `{ satisfy_predicate ∈
  same_sink_flanks | contact, miss_behavior ∈ spread_like_piece | stop | absorb }`.
  v1.1 left the miss behaviour untyped.
- **`on_piece` decomposes into three sub-slots** so that accidental fits become
  distinct choices: `{ spawn ∈ empty_flanks_only | both_flanks | none, direction ∈
  preserved | outward_turned, propagation ∈ cellwise_iterative | edge_teleport }`.
  Under v1.1's single `split_perpendicular` token, an edge-teleport model and an
  outward-turn model both fit the observed trace by accident.
- **Placement gains static semantics**: `blocked_by ∈ { board_bounds,
  static_entities, sink_halo(margin), row_bound }` as an explicit set. "Everything
  else blocks" was prose, not type.
- **Piece responses are keyed by piece CLASS.** The review is right that a single
  global `on_piece` cannot represent a level mixing straight and angled pieces, and
  that v1.1's claim "deeper angled levels stay expressible" was FALSE. Corrected:
  v0 is scoped strictly to the straight-piece variant, and the response table is
  keyed by an observed piece class so the mixed case is a future EXTENSION, not a
  present capability. The false expressibility claim is withdrawn.

### Bound correction 2 — ownership (review B)

Causal rules move out of `harness_measured`:

- `on_hazard`, `on_own_flow`, `on_boundary` are **model_selected but NON-GATING at
  idx0 unless certified**. `on_hazard` IS now certified (measurement 1 above) and
  may be gated; `on_own_flow` and `on_boundary` have no discriminating evidence at
  idx0 and are therefore forced to UNKNOWN — never a closed choice from absent
  evidence.
- `placement_constraints`, `control_mode` and the reset fields are declared
  **measured premises**: the harness may supply them, but they are explicitly
  EXCLUDED from model credit, and each one that cannot be established from the
  contract's discovery trace (mutual permeability, the row bound, the attempt cap)
  is marked as an unestablished premise rather than a measurement.
- `completion` is ungrounded at idx0 by measurement 2 and is therefore NOT gated.

### Bound correction 3 — mutant table v2

*Certified against observed transitions*

| # | mutant | verdict | evidence |
|---|---|---|---|
| T1 | piece absorbs | CONTRADICTED | frontier emits `(3,8)+(3,10)`; absorb predicts none |
| T2 | piece turns 90° | CONTRADICTED | the frontier is a symmetric pair that resumes the original direction |
| T3 | sink satisfied on contact | CONTRADICTED | `(12,10)` faces sink cell `(13,10)`, spreads instead of satisfying |
| T6 | split with outward-turned directions | CONTRADICTED | both branches keep descending after clearing the piece |
| T7 | edge teleport (re-emit at the piece edges) | CONTRADICTED | the frontier walks one cell per tick along the piece row |
| O2 | hazard ignored | CONTRADICTED | the +2 / +3 pair differs only in hazard contact |

*Honest UNKNOWN — no discriminating opportunity at idx0*

| # | mutant | why |
|---|---|---|
| O1 | any sink suffices | no reachable placement fills a strict subset (proof of absence) |
| T8 | mouth predicate correct but stop/absorb on non-mouth contact | the observed non-mouth contact spreads, which T8 also permits at the level of what is visible |
| T9 | halo margin 0 or 2 | the contract's discovery trace does not exercise the halo boundary at two widths |
| T10 | sink satisfaction persists across failed commits | requires two commits with a partial cover, which measurement 2 proves unreachable |
| T11 | overwrite / re-entry on existing flow | no observed event distinguishes wait-merge from overwrite |
| T12 | boundary reflect | the flow never exits sideways at idx0 |

*Demoted*

| # | mutant | status |
|---|---|---|
| T4 | placement unconstrained | SMOKE CONTROL ONLY — trivially killed, and it does not distinguish the sink halo from board bounds, static collision, or a wrong halo width |
| T5 | layout resets on failure | kept, but scoped strictly to LAYOUT persistence; it says nothing about flow or satisfaction resets |

`AnySinkCovered` is never counted as killed merely because its compiler path is
UNSUPPORTED (review C, final line).

### Bound correction 4 — model-facing prose must expose every enforced rule

The twice-measured lesson, now applied preemptively. The model-facing contract
must state, in prose: same-sink flanking as the satisfaction condition; spreading
as the non-mouth response; direction preservation under splitting; the behaviour
on already-occupied flow; every reset that a failed commit performs; and the
action-budget accounting (which actions consume the allowance and what happens at
exhaustion). Anything the verifier enforces but the contract does not state is a
harness defect that manufactures a false negative.

### Bound correction 5 — every gated enum must change a prediction

Before the contract freezes, each gated slot must be shown to change either the
verifier's predicted trajectory or the compiler's plan on at least one reachable
idx0 placement. A slot that changes neither is decoration: the simulator's
hardcoded semantics would carry the run and produce a FALSE PASS. Slots that fail
this test are demoted to UNKNOWN/non-gating rather than being kept for
completeness.

### Bound correction 6 — budgets frozen against the PERSISTED layout

The engine-bounded approach stands, but the 12/18 split does not. Replace with:

- one **pre-certified** discovery action sequence, including the contact probe,
  with its exact action count;
- the shortest solve **from the layout that persists after that probe** — not from
  the entry layout, because a failed commit does not restore piece positions;
- a single exact cumulative cap counting selection, translation and commit actions
  alike, rather than an approximate total with an arbitrary sub-split.

The oracle measurement bounds this comfortably: the clear itself is 4 actions
against a human baseline of 39, so the level still scores at the per-level cap
even after a full discovery budget.

### Bound correction 6, DISCHARGED — the discovery sequence is certified (2026-08-22 17:44 KST)

`scripts/rounds/R98/discovery_probe_idx0.py` → `discovery.txt`. Every step follows
a rule derivable from observables, so this is a certified sequence rather than a
hand-picked one:

| phase | rule | actions | what it establishes |
|---|---|---|---|
| select | click the candidate movable region's own centroid | 1 | the region takes a distinct selected appearance and nothing else changes |
| displacement contrast | press one direction, then keep pressing to the bound | 3 | a press displaces the whole footprint; a later press at the bound does not — the CONTRAST that licenses a constraint claim |
| align over emitter | translate until the region's column span covers the emitter column | 2 | the only placement class that makes the flow interact with the region at all |
| sacrificial commit | commit once | **1** | 28 layers of trajectory, plus T3 contact-vs-mouth, plus the O2 pair, plus layout persistence |
| solve | replan from the PERSISTED layout, commit | 2 | the level advances |

- **discovery = 7 actions, solve = 2, cumulative = 9**, against an engine
  allowance of 30 change-phase actions and 4 commits (2 used).
- **A commit costs ONE action, not two.** The settle, the failure flash and the
  restore all run inside a single action's internal ticks. This corrects the
  wiki's "~2 actions" estimate for a sacrificial spill.
- The alignment rule lands exactly on the placement that carries the richest
  evidence (the `+2` case that certifies T3 and O2). The evidence set is not
  something the contract has to hope for — it falls out of the one probe an agent
  would run anyway.
- RHAE headroom: 9 actions against a human baseline of 39 leaves the level at the
  per-level cap with room to spare.

**Frozen budget clause (replaces the v1.1 12/18 split)**: ONE cumulative cap of
**20 actions**, counting selection, translation and commit actions alike, and at
most **3 commits**. That is 2.2× the certified path, stays inside the engine's own
bounds, and still scores at the per-level cap. The solve is planned from the
layout that PERSISTS after the probe, never from the entry layout.

### Bound correction 7 — near-OOD must be certified, not asserted

re86 remains provisional. The control only counts as near-OOD if it FIRST survives
the same grounding and typing path as `PlaceThenPropagate` and only THEN fails on a
mechanics-specific transition mismatch. A control rejected immediately on palette
or entity shape is not near-OOD and must be replaced. This certification is a
prerequisite of the freeze, not a post-hoc label. Far-OOD stays tu93.

### Bound correction 5, DISCHARGED — faithfulness proven, two slots demoted (2026-08-22 18:06 KST)

`scripts/rounds/R98/reference_propagator.py` implements the response table AS the
simulator; `gated_enum_test.py` → `gated_enums.txt` runs it against the live
engine.

**Faithfulness: PASS.** The oracle response table reproduces the engine's
outcome on ALL 12 reachable placements, and reproduces the CELL-EXACT trajectory
on both probe placements (`+2`: 20 steps, `+3`: 17 steps, no divergence). The
decoded model is therefore not an interpretation — it is the engine's behaviour,
and this propagator is the verifier's core.

**Discriminability**, measured by flipping one slot at a time and counting the
placements where the prediction changes:

| slot | verdict | effect |
|---|---|---|
| `piece_spawn` | DISCRIMINATING | `none` changes 5 trajectories / 3 outcomes |
| `piece_direction` | DISCRIMINATING | `outward_turned` changes 5 / 3 |
| `piece_propagation` | **TRAJECTORY-ONLY** | `edge_teleport` changes 5 trajectories, 0 outcomes |
| `sink_predicate` | DISCRIMINATING | `contact` changes 2 / 2 |
| `sink_miss` | DISCRIMINATING | `stop` and `absorb` each change 2 / 2 |
| `hazard` | DISCRIMINATING | `terminate_local` 0 / 2, `pass_through` 11 / 2 |
| `own_flow` | **INERT** | both alternatives change nothing, anywhere |
| `boundary` | **INERT** | `reflect` changes nothing, anywhere |

Consequences, all binding:

1. **`own_flow` and `boundary` are demoted to non-gating UNKNOWN.** Independent
   confirmation of the review's correction 2 — it predicted exactly these two
   from the absence of evidence, and the measurement agrees.
2. **`piece_propagation` is gated at the VERIFIER only, never at the compiler.**
   It changes what the trajectory looks like but never who wins, so scoring it
   through outcomes would be scoring noise.
3. **`piece_spawn: both_flanks` is data-indistinguishable from the oracle** at
   idx0 (0 trajectory and 0 outcome differences) because the flanks are always
   empty when a split occurs. A model choosing it must be scored CORRECT, as an
   equivalence class — the R95a ft09 precedent, where
   `{glyph_constraints, nearest_glyph_only}` was genuine data-indistinguishability
   rather than a wrong answer. The scoring key records the class, not one member.

### Bound correction 7, DISCHARGED — the controls swap, by measurement (2026-08-22 18:08 KST)

`scripts/rounds/R98/near_ood_screen.py` → `near_ood.txt`. The family's observable
tell is that ONE action triggers a scripted consequence the engine exposes as many
frame layers at once. Measured across candidates (every simple action twice, plus
a click grid):

| game | max single-action layer burst |
|---|---|
| sp80 (oracle) | **22** (on the commit action) |
| **tu93** | **8** (on two movement actions) |
| sk48 | 2 |
| re86, ls20, wa30, tn36, cn04 | 1 |

- **re86 is REJECTED as near-OOD.** Every action returns a single frame, so no
  agent would reach for a place-then-propagate model there; it is unrelated, not
  confusable. The review's suspicion that neither proposed candidate was certified
  was correct.
- **tu93 becomes the NEAR-OOD control.** One action produces an 8-layer scripted
  consequence — the family's exact tell — while the mechanics are actor
  corridor-motion with no source, no placement phase and no coverage objective. An
  agent could plausibly select this family from the observable signature and be
  wrong on the mechanics, which is the definition of near-OOD.
- **re86 becomes the FAR-OOD control** (cn04 recorded as the alternate).

So the two controls SWAP relative to v1.1, and both roles are now measured rather
than asserted. Full certification still runs through the grounding service when it
exists; this screen is the precondition, and it is now a discriminating one.

## R98 EVALUATION CONTRACT — FROZEN 2026-08-22 18:10 KST

- **Family**: FlowDeflectionDynamics, variant v0 `PlaceThenPropagate`, straight
  splitter pieces only. Mixed straight/angled boards are OUT (the response table is
  keyed by piece class so they remain a future extension, not a present claim).
- **Oracle & criterion level**: sp80 **idx0 only**. idx1 may be run as a
  NON-GATING observation. Fresh env + RESET per run; every action resolved through
  the grounding service at action time; no replayed sequences.
- **Budget**: ONE cumulative cap of **20 actions**, counting selection,
  translation and commit alike, and at most **3 commits**. The certified path is 9
  actions. The solve is planned from the layout that PERSISTS after the probe.
- **Thresholds**: oracle gate 3/3. Model substages 3 runs per model per substage,
  success ≥2/3. CONFIRMED = both models (gemma4-31b-q8 and gpt-oss-120b).
- **Substage order**: canned-instance selection (oracle + the frozen mutant table,
  serialized neutral) → variant-first slot filling.
- **Gated slots**: `piece_spawn`, `piece_direction`, `sink_predicate`, `sink_miss`,
  `hazard` at the outcome level; `piece_propagation` at the verifier level only;
  `own_flow` and `boundary` NON-GATING UNKNOWN. `piece_spawn: both_flanks` scores
  as an equivalence-class member of the oracle answer.
- **Controls**: near-OOD **tu93** (expected UNSUPPORTED/UNKNOWN pre-execution),
  far-OOD **re86**. Neither gates.
- **Prohibited leakage**: as R95/R96/R97 — no adapter code, wiki, game ids,
  provenance labels or gold sequences reach the model; evidence is PROSE only.
- **Model-facing contract must state**: same-sink flanking as the satisfaction
  condition, spreading as the non-mouth response, direction preservation under
  splitting, the behaviour on already-occupied flow, every reset a failed commit
  performs, and the action-budget accounting. Anything the verifier enforces but
  the contract omits is a harness defect that manufactures a false negative — the
  lesson measured twice, applied preemptively.
- **Non-counting**: UNKNOWN never executes; manual or oracle-assisted clears are
  recorded but not counted.
- **Falsification**: oracle-gate failure on GROUNDING (piece footprint/identity,
  emitter or sink-mouth geometry, animation-layer decoding) is the pre-declared
  40% outcome and pivots the round to grounding work — not to schema or model
  changes.

### Remaining before the freeze

All four are DONE and the contract above is FROZEN:

1. ~~Pre-certify the discovery action sequence~~ — 9 actions; cap 20 / 3 commits.
2. ~~Gated-enum prediction test~~ — faithfulness PASS; `own_flow` and `boundary`
   demoted; `piece_propagation` verifier-only; `both_flanks` an equivalence class.
3. ~~Certify or replace the near-OOD control~~ — controls swapped by measurement:
   near-OOD tu93, far-OOD re86.
4. Implement `schema_flow.py` against the frozen contract — IN PROGRESS.

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
