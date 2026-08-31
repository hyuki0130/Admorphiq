## v1.1 SCHEMA DRAFT — FlowDeflectionDynamics (2026-08-22, pre-Codex-consult)

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
| T1 | `piece_absorbs` (on piece → absorb) | CONTRADICTED | the sacrificial commit's layers show two new streams appearing beside the piece; absorb predicts none |
| T2 | `piece_turns_90` (on piece → turn_90) | CONTRADICTED | turn predicts ONE outgoing stream in a perpendicular direction; the layers show TWO, both still descending |
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

NEXT STEP (updated): one Codex consult on THIS schema section only — the open
questions are (a) the near-OOD choice, (b) whether the engine-bounded budget split
is right, (c) whether O2's pre-declared UNKNOWN is acceptable at the criterion
