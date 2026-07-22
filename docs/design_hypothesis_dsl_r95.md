# R95 design — typed hypothesis DSL (v2, post-Codex NO-GO revision)

Status: v1 (single universal schema + 0.8-threshold verifier + sk48-first bench)
was reviewed by Codex 2026-07-22 and rejected **NO-GO as written** with 7
findings (log: session scratchpad `codex_r95_dsl_review.log`). This v2 adopts
the required corrections. The thesis is unchanged — the model's reliable
competence is OBSERVATION → HYPOTHESIS, not code integration (measured
R92–R94), so give it a closed-choice hypothesis channel, not a code channel —
but the falsification path is restructured to be cheaper and attributable.

## Codex findings driving this revision (condensed)

1. **P0 schema under-expressive**: one shallow universal schema cannot express
   CD82 (palette/canvas/operators), FT09 (glyph constraint satisfaction, NOT
   neighbourhood GF(2) — explicitly falsified), SC25 (phase-conditioned
   sequences), sk48 (selection/grow/push/undo). It even claimed paint coverage
   without compiling `paint_core`. → Tagged FAMILY schemas, not one object.
2. **P0 verifier unsound**: fixed 0.8 replay ratio over raw pixel diffs
   conflates effect with HUD/animation/dropped inputs; ignores sample size and
   dependence; the wall exemption is circular. → `PASS / CONTRADICTED /
   UNKNOWN`, minimum independent probes, held-out transitions, HUD masking +
   settling + phase filtering BEFORE verification.
3. **P0 attribution gap**: rejection telemetry cannot separate model / schema /
   binding / verifier / compiler failure. → oracle self-reproduction gate
   (attribution ladder) before any model bench.
4. **P0 sk48 invalid first holdout**: its known method is faithful-sim + A*;
   schema cannot express it; it would test generic exploration, not
   hypothesis quality. → sk48 demoted to explicit OOD control.
5. **P1 metric too permissive**: R93's exploration-delta "wins" are not
   mechanic-understanding evidence. → dual verdicts (hypothesis verdict vs
   control verdict); level clears first-class, exploration deltas descriptive.
6. **P1 missing binding layer**: stable object IDs / HUD masks / settled
   frames / phase boundaries must be harness-supplied before verification.
7. **P1 cheaper falsification exists** → adopted as R95a below.

## R95a — discriminative selection test (BEFORE any compiler build)

The cheapest experiment that tests the thesis:

1. For ONE family with decoded ground truth (v2.2 correction: the
   **cell-state family = ft09 + sc25's pattern phase** — vc33 was dropped as
   not a clean toggle-family member; see Codex resolutions §7 below),
   hand-author a FINITE candidate set of hypothesis templates per game:
   the known-correct template + 3–5 hard negatives (plausible mechanics the
   family admits but the game refutes: wrong stencil, wrong target rule,
   wrong entity binding).
2. Harness supplies the stabilized observation package (HUD-masked, settled,
   phase-filtered transitions + candidate object IDs from
   `kernels/regions.py`) — the binding layer of finding 6, built once here.
3. The model's ONLY job: select the template + bind observed object IDs
   (guided-json, closed choices).
4. Score on HELD-OUT transitions: does the selected (template, binding)
   predict action effects better than the alternatives?
5. **Baseline control**: exhaustive replay-ranking of the same finite
   candidate set (no LLM). If exhaustive ranking matches or beats the model,
   the LLM adds no value at this layer and R95b is not built.

Deliverable: `scripts/probe_hypothesis_select.py` + per-case telemetry
(selected template, binding, held-out prediction accuracy, exhaustive-ranking
baseline). No live execution, no compiler, no sandbox — offline over recorded
transitions from the existing R93/R94 traces.

Data feasibility VERIFIED (2026-07-22): `data/traces/{ft09,sc25}.npz` both
carry `actions + coords_x/coords_y + frames/next_frames + level_index +
is_gold + episode_id` — everything a held-out transition split needs. ft09:
718 transitions across all 6 levels (436 gold); sc25: 249 across levels 0–2
(53 gold; pattern-phase clicks present in L0's 51 rows). sc25 depth caveat:
only the 3 adapter-cleared levels are captured.

### R95a candidate template sets (v2.5 — drafted from decoded ground truth)

Design principle: hard negatives are HISTORICAL wrong hypotheses that were
measured-falsified wherever possible — the strongest available distractors,
because they fooled real solvers for months.

**ft09** (ground truth: `games/FT09.md` constraint rule, gold-verified 6/6):

| # | template | status |
|---|---|---|
| O | glyph-constraint satisfaction: every covered cell must equal (ink-0) / differ (ink-2) from EACH covering glyph's center colour, ALL simultaneously; click walks the measured colour cycle one step | ORACLE (byte-verified vs gold) |
| N1 | GF(2) neighbourhood-toggle stencil, solve linearly | hard negative — the historical `lights_out` hypothesis, falsified after years |
| N2 | nearest-glyph-only constraint scoping | hard negative — the measured "coverage-scoping near-miss" |
| N3 | uniform-colour goal (all cells one colour) | naive negative |
| N4 | match-displayed-preview template (sc25-style) | cross-family negative |

**sc25 pattern phase** (ground truth: `games/SC25.md` mechanics):

| # | template | status |
|---|---|---|
| O | binary cell flip; goal = grid EXACTLY equals `base XOR preview`; first action eaten by settle redraw | ORACLE (live-verified) |
| N1 | cells walk a colour cycle (ft09-style multi-state) | cross-family negative |
| N2 | near-match threshold goal (≥k cells matching suffices) | hard negative — the game HIGHLIGHTS near-matches; this defeated the earlier blind-search adapter |
| N3 | click flips the cell AND its neighbours (stencil) | plausible negative |
| N4 | preview read as ABSOLUTE colours (no base-parity XOR) | hard negative — the real subtle bug the R56 adapter had to solve |

Discrimination is HELD-OUT-transition prediction: e.g. ft09 N1 predicts a
click changes MULTIPLE cells (observed: one cell steps its cycle); sc25 N4
mispredicts every level whose base parity is nonzero. If gemma4 cannot beat
exhaustive replay-ranking on THESE sets — where the negatives are this
strong and the evidence this clean — the hypothesis-selection thesis is dead
at this model scale, cheaply.

### R95a part-2 PRE-REGISTRATION (LLM selection stage — frozen 2026-07-22 before any model run)

What the model sees (per game, ONE completion, guided-json):
- The five template DESCRIPTIONS in neutral language, shuffled order, neutral
  ids (T1..T5) — no names, no oracle hints, no historical labels.
- An observation summary computed from TRAIN transitions ONLY: per-action-type
  counts, per-click changed-cell-count histogram, 3 example click transitions
  (xy, before-cell colours, changed cells), the win-moment full-block diff
  summary per R57, and the parse skeleton (ring/lattice cell count). No
  held-out data, no scores, no per-template accuracy.
- Ask: "which template best explains these observations?" → `{"choice":
  "T1".."T5", "confidence": "low|medium|high", "evidence": "<=2 sentences"}`.

Scoring (per game × model):
- **PASS** = choice lands in the oracle EQUIVALENCE CLASS (oracle + templates
  tied with it under exhaustive ranking, as reported by part-1's
  `tied_with_oracle`). Picking a strictly-dominated negative = FAIL.
- Report alongside: the exhaustive-ranking winner (the no-LLM control). The
  LLM adds value at this layer ONLY if it PASSES where ranking is available
  anyway — i.e. the interesting comparisons are (i) PASS-rate vs random
  (1/5-ish baseline adjusted for class size), (ii) whether model evidence
  cites the actual discriminating observation (dynamics multi-cell vs single-
  cell for ft09 N1; win-state mismatch for N3/N4).
- Models: gemma4-31b-q8 AND gpt-oss-120b (reasoning high, 20K budget), same
  asks, paired per game. 3 repetitions each (sampling variance check). No
  one-shot verdicts.
- MEASURED equivalence classes (part-1 final, commit 405e754 — slots filled,
  prereg now fully frozen):
  - ft09 class = {glyph_constraints, nearest_glyph_only} — GENUINE data-
    indistinguishability (1436-frame divergence scan, 0 divergences; the
    discriminating "nearest-satisfied-but-not-all" near-miss never occurs in
    gold). Random PASS = 2/5 = 0.4. **ft09 is the primary case.**
  - sc25 class = {binary_flip_xor, colour_cycle, near_match_threshold} —
    trace supplies ZERO clean win-axis negatives (all 14 gold clicks are cast
    states; the old fp=0.60 was correct positives mislabeled as negatives),
    and near_match is provably indistinguishable (0 frames at 7–8/9 match;
    distribution {5:16, 6:10, 9:464}). Random PASS = 3/5 = 0.6 → sc25 is a
    WEAK case and cannot carry the verdict alone.
  - Follow-up lever if ft09 alone proves insufficient: recapture richer
    traces (pre-match sc25 pattern-phase frames; ft09 near-miss states) —
    a data-collection round, not a scoring change.

## R95b — family compiler (ONLY if R95a shows model selection skill)

- **Tagged family schemas** (finding 1): `toggle` schema = board cells,
  controls, empirical effect matrix, state representation, target
  source/constraint. `paint` schema = canvas, reference, palette, actuators,
  comparison mask. Composition = ordered phases with observable entry/exit
  guards. NO universal schema.
- **Sound verifier** (finding 2): verdicts `PASS / CONTRADICTED / UNKNOWN`
  with minimum-probe counts and held-out testing over the stabilized
  observation package; toggle claims verified by controlled click-twice /
  same-base probes.
- **Oracle gate** (finding 3) before any model run: (i) hand-authored oracle
  hypothesis representable in the schema; (ii) passes verifier on clean
  evidence, rejects seeded wrong alternatives; (iii) compiled core reproduces
  a declared floor (level clear, else the unmodified card arm); (iv) model
  scored against oracle + held-out prediction; (v) only then fresh execution.
- **Dual verdicts** (finding 5): hypothesis verdict (oracle-slot accuracy +
  held-out prediction) reported separately from control verdict (level clears
  first; exploration deltas descriptive unless pre-declared margin +
  replication).
- sk48 runs only as the labelled OOD/exploration control arm.

### R95b BUILD PLAN v1 (Codex CONDITIONAL GO, 2026-07-22 16:42 — v0 corrected;
### log `codex_r95b_plan_review.log`. BINDING for the build.)

Codex corrections applied on top of v0 (v0 kept below for provenance):

1. **Revised order with per-layer oracle outputs** (v0's single late oracle
   gate cannot localize failures): (i) FREEZE the evaluation contract first
   (exact levels, fresh-reset procedure, budgets, repetitions, aggregation,
   prohibited leakage); (ii) schema + canonical oracle instances + invalid
   instances + mutant fixtures; (iii) Observation v2 as a runtime GROUNDING
   SERVICE (stable IDs across recolouring, click resolution at action time,
   rebind on layout replacement, confidence, UNKNOWN on identity loss) —
   validated against labeled fixtures; (iv) verifier with an explicit
   expected-verdict matrix (data-indistinguishable mutants stay UNKNOWN, not
   required-rejected); (v) compiler offline on grounded fixtures (dispatch on
   schema tags ONLY, never game id, no adapter imports); (vi) live oracle
   gate through the exact production pipeline; (vii) CANNED serialized
   schema-instance selection (intermediate model substage); (viii) free slot
   filling, verifier-gated.
2. **One family, one envelope, tagged objective union**:
   `objective: GlyphRelational{...} | PatternReference{...}` — source and
   target coupled inside the union so invalid cross-products (glyph source +
   XOR target) are unrepresentable; `transition_model` separately tagged
   (ordered cycle | binary flip | empirical effect-matrix). ft09 needs the
   ORDERED colour transition function (not just cycle length), overlapping
   incidence, no-cell semantics, control-button behaviour; sc25 needs base-
   snapshot timing, XOR-vs-absolute, two-read stability, settle behaviour.
3. **Field ownership tags on every schema field**: `harness_measured` |
   `model_selected` | `compiler_derived`. The model selects SEMANTICS
   (coverage quantifier, ink/operator mapping, preview interpretation,
   guards); the harness materializes repeated structures (cell enumerations,
   incidence graphs) — top-K shortlists are for SINGULAR roles only.
4. **Floor gates**: ft09 oracle clears the first two evaluation levels in
   sequence, 3/3 fresh-reset runs, freshly grounded (no replayed
   coordinates); sc25 oracle reaches a genuine L0 cast + guard handover 3/3.
   ft09 6/6 is a family-coverage RELEASE gate, not the entry gate.
5. **Verifier splits by episode/level** (not adjacent even/odd); minimum
   probes per claim.
6. **Success criterion with repetition rule**: per-model success = a
   verifier-PASS model schema clears the fixed ft09 level in ≥2/3 fresh
   runs; overall CONFIRMED = both models, PARTIAL = one. Clears from
   UNKNOWN/manually-repaired/oracle-assisted schemas do NOT count.
   Codex risk estimate: ~60% of residual risk is ft09 grounding/parameter
   acquisition, ~25% coherent slot filling, <15% mechanic selection.

### R95b EVALUATION CONTRACT (step i — FROZEN 2026-07-22 16:44, before any
### schema/compiler code)

- **Games & levels**: ft09 levels idx0 and idx1 (the oracle floor pair; the
  model criterion level = idx0, which must be oracle-proven first). sc25
  level idx0 pattern phase (cast + guard handover only; navigation excluded).
- **Fresh-reset procedure**: every run starts from a new env instance +
  RESET; no state reuse across runs; no replayed coordinates — every click
  is resolved through the grounding service at action time.
- **Budgets**: ft09 ≤150 actions/level (matches `_LEVEL_ACTION_BUDGET`);
  sc25 pattern phase ≤60 actions. Wall-clock per run ≤20 min incl. LLM calls.
- **Repetitions & aggregation**: oracle gates = 3/3 required. Model stage =
  3 fresh runs per model per substage; per-model success = ≥2/3 clears from
  a verifier-PASS schema; overall CONFIRMED = both models, PARTIAL = one.
- **Substage order**: (vii) canned-instance selection (5 serialized
  instances: oracle + 4 mutants from the expected-verdict table) → only on
  substage success (viii) variant-first slot filling (objective variant
  choice, then that variant's `model_selected` slots + singular-role
  shortlist bindings).
- **Prohibited leakage**: the model never sees — adapter code, wiki pages,
  game ids, template/mutant provenance labels, verifier internals, gold
  action sequences, or any held-out split. Prompt content = grounding-service
  output + neutral serialized instances only (R95a leak-guard test pattern
  extended to the new prompts).
- **Non-counting clears**: UNKNOWN-verdict schemas never execute; a clear
  obtained after ANY manual repair or oracle assistance is recorded but does
  not count toward the criterion.
- **Falsification**: if the ORACLE gate itself cannot pass (grounding cannot
  acquire the ordered cycle / full glyph coverage within budget), that is the
  60%-risk outcome — recorded as a GROUNDING failure, and the round pivots
  to grounding work, not schema/model changes.

### R95b BUILD PLAN v0 (superseded by v1 above — kept for provenance)

Scope: ONE family — the CELL-STATE family R95a validated (ft09 + sc25 pattern
phase). Components, in build order, each with its own gate:

1. **Cell-state family schema** (tagged, per v2.2 §1): board cells (with
   measured colour-cycle length), controls (stateful buttons), constraint
   sources (marker/preview: read as glyph-relational OR as pattern-reference —
   the schema's key discriminated union), target rule (all-constraints /
   exact-pattern-xor), phase guards (from the typed clause bank). The R95a
   template set becomes INSTANCES of this schema — selection now fills slots
   instead of picking a whole canned template.
2. **Observation package v2**: the R95a summary + #125 chrome masking +
   role-conditioned candidate shortlists (measured top-K≈8) + settled-frame
   windows. This is the harness-owned binding layer (Codex finding 6).
3. **Verifier**: PASS/CONTRADICTED/UNKNOWN per dynamics claim with
   minimum-probe counts + held-out testing (v2 correction §2); win-rule
   verified against gold level-up events where available, else UNKNOWN.
4. **Compiler**: schema instance → executable core in the SAME sandbox
   contract as R93/R94 cards (current_frame/transitions/act). ft09 compiles to
   the constraint-solve plan (colour-cycle click counts per cell); sc25
   compiles to XOR-diff clicks + guard-gated navigate handover.
5. **Oracle gate** (v2 correction §3, run BEFORE any model selection): the
   hand-authored oracle schema instance must (i) pass the verifier on clean
   evidence, (ii) reject seeded wrong instances, (iii) its compiled core must
   reproduce a declared floor LIVE — ft09 ≥ the adapter's 6/6 path on at
   least L1-L2 within budget; sc25 ≥ pattern-phase cast on L0. Only then the
   model's selected/filled schema runs.
6. **Model stage**: guided-json slot filling over the family schema (the R95a
   ask generalized from 5 canned choices to schema slots), both models, reps,
   dual verdicts (hypothesis accuracy vs oracle; control = level clears).

Success criterion (pre-declared): the model-filled schema, compiled and run
live, clears ≥1 ft09 level end-to-end without the adapter — the first
agent25 LEVEL CLEAR through the hypothesis channel. Failure telemetry keeps
the schema/binding/verifier/compiler/model attribution separable (the whole
point of the ladder).

## Enum vocabulary v0 — domain-mined question banks (v2.1, 2026-07-22)

Directive: enum choices must be MINED from the 25 public games' decoded
mechanics (not invented), and unseen private mechanics must remain
expressible by COMPOSITION rather than by enum membership. Sources: R57
win-condition typology (`rounds/r57_win-condition-typology.md`, T1–T8),
`explanation/goal_ledger.py` (6 of 8 types already executable), the 25
`games/*.md` mechanic summaries, and the kernel library inventory.

### Q1 — entity roles (what is on screen?)

Mined roles, each with ≥1 source game and a harness-side binding procedure
(the model BINDS observed object IDs to roles; the harness supplies candidate
IDs per finding 6):

`player_avatar` (ar25/m0r0/dc22/tu93/bp35) · `cursor_selector` (sk48 select,
s5i5) · `movable_piece` (s5i5 rigid sprites, ar25 glyphs) · `pushable_block`
(ka59, ls20 push-carry) · `carryable_item` (wa30) · `enemy_patrol` (lf52
deterministic wall-follower, su15) · `goal_marker` (T1 games) · `canvas`
(cd82) · `reference_preview` (cd82 reference, sc25 preview) · `palette_control`
(cd82) · `toggle_cell` (ft09, vc33) · `control_button` (ft09 control-toggles,
lp85 ring buttons) · `portal` (sb26) · `mirror_axis` (ar25 bar) ·
`hud_counter` (excluded from state by masking) · `wall_static` · `unknown`

### Q2 — action effects (what does each action do?)

Mined effect classes. CRITICAL design rule (from Codex finding 1): the enum
names the CLASS; the parameters are MEASURED empirically by the harness, never
enumerated (e.g. `toggle_stencil` does not enumerate stencil shapes — the
effect matrix is learned from probes, the enum only claims "clicking flips a
cell set deterministic in the click location").

`move_step` (grid step; ar25/m0r0/dc22/tu93) · `move_until_blocked` (slide) ·
`rotate_piece` (tr87, s5i5) · `ring_rotate` (lp85 button → ring cycle) ·
`push_contact` (ka59 momentum-push) · `pick_or_drop` (wa30) · `select_cycle`
(sk48 selection, cd82 palette) · `grow_retract` (sk48 snake) ·
`toggle_stencil` (ft09/vc33: click flips measured cell set) · `paint_apply`
(cd82 operators) · `colour_cycle` (ft09 multi-state cells) · `spawn_launch`
(sc25 cast, cn04) · `teleport_portal` (sb26) · `record_replay_ghost` (g50t
ACTION5; corrected 2026-07-22 — lf52 is peg-solitaire select+land clicks) ·
`undo` (ACTION7) · `phase_advance` (confirm/submit; cd82/sc25 —
own diff near zero, full-block diff carries the effect, per R57) · `inert` ·
`unknown_probe_more`

### Q3 — goals (win predicate) = R57 T1–T8, verbatim

`reach_coincidence` (T1, 12+ games; sub-form question: click-target vs
movement, per R57 caveat 4) · `elimination` (T2) · `multiset_assignment`
(T3) · `delivery` (T4 = T1+T2 composition) · `paint_match` (T5, full-block
diff) · `toggle_parity` (T6) · `repeat_threshold` (T7, needs ≥3-repeat
trend) · `rewrite_derivation` (T8, honestly: zero frame-only evidence path
yet — selecting it routes to probe_more, not to a compiled plan) · `unknown`

### Q4 — plans (how to solve, given Q1–Q3)

Each value maps 1:1 to an existing verified kernel/planner: `shortest_path`
(paths.py) · `gf2_solve` (gf2.py) · `assignment_match` (multisets/arrangement)
· `sim_search` (faithful-sim family, simdfs) · `delivery_compose`
(delivery planner) · `repeat_until` (T7) · `paint_plan` (solver_core) ·
`probe_more` (active identification, #122)

### Q5 — composition (the unseen-mechanics mechanism)

Private games with unseen SURFACE mechanics are covered three ways, in order:
1. **Phase composition**: a hypothesis is an ORDERED LIST of (guard, Q1–Q4
   block) phases with observable entry/exit guards (sc25 = preview-match →
   auto-cast → navigate). Novel games are usually novel COMPOSITIONS of seen
   primitives — this is the main generality lever.
2. **Measured parameters**: effect classes carry no fixed geometry; stencils,
   step sizes, ring memberships, push rules are all learned from the game's
   own transitions. An unseen stencil shape is NOT an unseen enum value.
3. **Honest escape**: every bank ends in `unknown`/`probe_more`, which routes
   to active-identification probes (#122) and verifier verdict UNKNOWN — never
   a forced wrong fit. A recurring `unknown` cluster in telemetry = a named
   schema gap for v1, logged not improvised.

### Codex vocab consult resolutions (v2.2, 2026-07-22 — supersedes the open
### questions below; full log in session scratchpad `codex_r95_vocab_review.log`)

Verdict: **NO-GO for vocabulary v0 as a complete 25-game vocabulary or as
proof of Q5 expressivity; conditional GO for R95a narrowed to ONE coherent
family.** Central distinction: `unknown/probe_more` is safe ABSTENTION, not
EXPRESSIBILITY; measured parameters generalize geometry but not
state-dependent / relational / concurrent / simulated dynamics.

1. **Q1/Q2 incompleteness is broad**: a 15-game table of decoded-but-
   inexpressible mechanics (ar25 coupled reflected motion, bp35
   destroy+gravity-settle, g50t plate→gate circuits, lf52 jump-capture, ls20
   entry-conditioned mutation, r11l drag+centroid-follow, re86
   recolour-on-contact, sb26 place/swap+DFS traversal, sk48 side-push
   grow/retract, sp80 simulate_flow, su15 radial-pull/merge/downgrade, tn36
   execute_program, tu93 corridor-follow, vc33 counter/connector, wa30
   autonomous co-agent). Also: FT09's goal is glyph-derived
   equality/difference constraints, NOT plain `toggle_parity`; R57's shallow
   labels for r11l/sk48 are superseded by the decoded wiki mechanics. This
   table = the v1 expansion backlog, per-family, added only when that family
   is built.
2. **Bank sizing**: family-scoped tagged sub-banks, but NO irreversible
   single classifier — select top-2 candidate families + unknown, present the
   UNION of their sub-banks + a small common bank (movement, selection, undo,
   inert, unknown); below a confidence floor route to probe_more. (17–18
   labels is a semantic-confusion problem, not a context-length problem.)
3. **T1 sub-form**: a separate closed question `reach_mode = click_locus |
   move_actor | move_non_actor | unknown` — hiding it in the planner would
   convert model classification errors into apparent planner failures.
4. **Phase guards**: shallow CONJUNCTION of typed clauses, no free-form
   logic: `stable_for_reads(n)`, `role_present/absent`, `role_count_delta`,
   `role_signature_changed`, `roles_state_equal(lhs, rhs, mask?)`,
   `selection_attached`, `affordance_markers_present`, `layout_replaced`,
   `level_advanced`, `unknown_guard`. Mined mappings: sc25 pattern-phase exit
   = `stable_for_reads(2) ∧ roles_state_equal(toggle_grid, preview)`; cd82
   terminal = `level_advanced`; lf52 jump exit = `role_count_delta(peg, -1)`.
   No game-named guards.
5. **Binding**: object-ID pick lists PRIMARY, plus harness-generated typed
   anchor IDs (`grid_cell_id`, `slot_id`, `region_anchor_id`+`anchor_kind`)
   for empty cells/slots; raw (x,y) is NEVER model-generated (camera/
   animation/click-transform attribution trap); `unknown_binding` escape →
   re-segmentation. Consistent with the measured top-K shortlist conclusion.
6. **Q5 claim corrected**: composition covers many surface recombinations and
   SAFELY DETECTS gaps — it does NOT make unseen mechanics expressible.
   Constructed counterexample: a plate-CONDITIONED ring button (hold plate →
   button rotates ring A, else ring B) uses only seen primitives yet needs a
   mode-conditional operator + revisitable alternation, which an ordered
   phase list cannot encode. v1 candidates if telemetry demands: conditional
   operators + a phase GRAPH (loops/branches) instead of a list.
7. **R95a family corrected**: one-family subsets ONLY (full banks would test
   family classification + long-list handling simultaneously and destroy
   attribution). Replace the vc33+ft09 pair with **FT09 + SC25's pattern
   phase** (cell-state family: cells, previews/constraint glyphs, colour
   cycles, coupled toggles, exact-constraint match, board reveal, inert,
   unknown). vc33 is NOT a clean toggle-family member (counter/decoy L0,
   connector-alignment L1) — deferred to a later control-alignment family
   test.

### Open design questions (RESOLVED above — kept for provenance)

- Bank sizing: 17 entity roles / 18 effects is near the 8B-context comfort
  limit — group into family-scoped sub-banks (only show toggle-family roles
  when the family classifier says toggle) or keep flat?
- Q3 sub-form resolution for T1 (click vs move) — separate question or
  planner-side branch?
- Guard vocabulary for phases — MINED DRAFT (2026-07-22, from sc25/cd82/g50t
  pages; to be merged with the Codex proposal):
  `pattern_match_complete` (editable region-set exactly equals a
  reference/preview → sc25 auto-cast; exact match, near-match redraws are the
  measured false-positive hazard) · `selection_indicator_change` (highlight
  marker appears/moves → cd82 swatch, sk48 selection) · `effect_shift` (the
  SAME action's measured effect class changes → sc25 pre-cast clicks toggle /
  post-cast moves move; detected by probe re-verification, this is the
  strongest phase evidence) · `role_instance_appear_or_disappear` (tracked
  role spawns/vanishes → g50t ghost spawn on ACTION5, lf52 piece consumed) ·
  `barrier_state_colour` (a gate region flips between two colours → g50t
  barrier open/closed is directly frame-observable) · `level_transition` /
  `reset` (harness-detected engine boundaries).
- Binding format: per-role object-ID pick lists vs free (x,y) anchors —
  pick lists are closed-choice but may not contain the right candidate.
  MEASURED INPUT (2026-07-22, `find_regions` over first/mid/last frames of all
  25 gold traces): per-frame region counts median 28, p90 71, max 224 (bp35
  191–224, tn36 88–186). → a flat all-regions pick list is infeasible for the
  heavy tail; the viable shape is ROLE-CONDITIONED SHORTLISTS — the harness
  pre-ranks candidates per role from role-relevant evidence (mobility for
  player_avatar, click-responsiveness for controls, size/static for canvas)
  and the model picks from top-K (~8) with a mandatory `none_of_these` escape
  that routes to probe_more. This keeps binding closed-choice at 8B scale
  while the escape prevents forced wrong bindings.

## Fallback ladder — when composition cannot express the game (v2.3)

Directive (user, 2026-07-22): priority #1 is maximally generic primitives, but
the schema WILL meet inexpressible games (Codex constructed one from public
primitives alone). The response is a runtime ESCALATION LADDER over channels
whose capabilities are already measured, ordered by cost and safety:

| tier | channel | measured basis | when entered |
|---|---|---|---|
| 0 | DSL hypothesis (this design) | R95a/b to measure | default |
| 1 | active identification probes (#122) | design pending | verifier UNKNOWN persists / `unknown` selected / `none_of_these` binding |
| 2 | **DSL self-extension** (v2.6, user directive 2026-07-22): the model proposes ONE new enum value (effect class, guard clause, or role selector) PLUS its small executable definition with a FIXED contract (e.g. `predict(frame, action, xy) -> effect`), which enters the SAME transition-consistency verifier — accepted only if it predicts held-out transitions; then the normal compiler uses the extended vocabulary. Every accepted extension is logged as a named schema-gap candidate for dev-time promotion into the permanent banks. | **EWM R48–R52**: gemma4 measurably synthesizes small transition-predicting functions selected by train fit (honest 0.133 exact-frame) — the SAME task shape | probes narrowed the mechanic but no existing enum value predicts the observed transitions |
| 3 | **tool fork-and-patch** (R93 loop, now the FINAL LLM tier per the same directive): model copies the nearest tool/card, makes a TARGETED edit, matched replay, keep-parent-on-loss | R93: paint×cd82 PATCH_WINS ×2; mechanism 11/20 breadth cases; safe by verdict rule | self-extension failed verification, but a NEAR-FAMILY tool exists |
| floor | generic exploration (graph frontier agent) | deployed card baseline | all tiers exhausted or budget cap |

Tier-2 rationale: it subsumes the old "bounded free-code micro-programs" tier
in a STRICTLY safer shape — the authored code is a typed slot implementation
under a fixed contract, verified against transitions BEFORE any use, version-
managed, and reusable by the compiler for the rest of the game. Whole-solver
authoring stays banned (R92 measured 0). Follow-up measurement is planned as
its own round AFTER R95a/b (task #124): seed test = remove one known vocab
entry (e.g. sc25's binary flip), give the model the gap, measure whether it
re-derives the entry + working definition from transitions alone.

Design rules for the ladder:

1. **Monotone safety**: every tier inherits R93's keep-parent-on-loss —
   escalation may only replace the incumbent behaviour after beating it on a
   matched replay. The floor (generic exploration) is always retained, so the
   ladder can never score below the deployed card.
2. **Escalation triggers are telemetry, not vibes**: repeated verifier
   CONTRADICTED on all candidate hypotheses, `unknown` cluster growth,
   zero-progress stall counters — the same signals that name v1 schema gaps.
   Every escalation event is logged with its trigger so dev-time rounds see
   exactly WHERE the schema was too narrow (the gap list IS the expansion
   backlog).
3. **Budget caps per tier**: tiers 2–3 are expensive (LLM latency); each gets
   a per-game action/wall-clock allowance so one inexpressible game cannot
   starve the other 109 in the 9h Kaggle budget.
4. **Authoring scope guard**: model-authored code (tier 2 definitions, tier 3
   patches) may only be a SMALL piece wired into an otherwise-verified frame
   (a guard predicate, an effect operator, a targeted tool edit) — R92
   measured whole-solver authoring at 0; that scope stays banned.
5. **Two-model comparison (user directive 2026-07-22)**: every ladder-tier
   measurement (R95a selection, tier-2 self-extension, tier-3 patching) runs
   BOTH gemma4-31b-q8 AND gpt-oss-120b, each at its own measured-best config
   (gpt-oss: reasoning_effort=high + 20K completion budget), under the frozen
   R93 pre-registered paired-scoring protocol (f53a82e) — no one-shot model
   verdicts (tuning-ladder rule, `memory/feedback_codex_review_gate`).
6. **Dev-time counterpart**: priority #1 remains widening the primitive set
   (the 15-game inexpressible backlog from the v2.2 consult) so the ladder is
   entered less often; runtime escalation telemetry decides WHICH family gets
   built next.

## Active identification (#122) — tier-1 probe design (v2.4)

What `probe_more` / verifier `UNKNOWN` actually triggers (Codex R93 lever #2,
now tier 1 of the fallback ladder). Two rules, both harness-computed —
the model never picks probe coordinates freely:

1. **No-repeat-no-op**: an (action, state-context) pair observed inert is
   never re-issued in that context; the probe budget is spent on UNTRIED
   pairs first. Context = the harness state key (frame hash tier), so an
   action inert in one phase may still be probed after a guard fires —
   which is exactly how `effect_shift` phase evidence is obtained.
2. **Disagreement probes**: while ≥2 candidate hypotheses survive the
   verifier, rank each executable action by how many surviving candidates
   its predicted outcomes SPLIT (maximum expected elimination). Execute the
   top splitter, feed the observed transition back to the verifier, repeat.
   A probe that all candidates predict identically is worthless and never
   chosen; a probe where candidates disagree is worth one bit or more.

Termination: single surviving candidate (→ execute its plan) · probe budget
exhausted (→ escalate to tier 2) · all candidates CONTRADICTED (→ log schema
gap, escalate). The probe count per game is a pre-registered constant, not
model-controlled, so runaway probing cannot eat the action budget the RHAE
metric squares.

R95a interaction: the discriminative pre-test scores SELECTION on recorded
transitions only (no live probes); disagreement-probe VALUE can still be
computed offline there — "had the agent been allowed one probe, which action
would have split the candidates, and do the recorded transitions contain it?"
— giving #122 its first measurement for free.

## Retained from v1

- Closed-choice (multiple-choice) slots via guided-json; no free-text escape hatch
  (R93 measured: a free channel collapses structured usage).
- `probe_more` as the explicit "insufficient evidence" selection, feeding the
  active-identification probes (#122).
- Frozen R93 lexicographic metric kept for cross-round comparability, but per
  finding 5 it is now the CONTROL metric, not the thesis metric.
