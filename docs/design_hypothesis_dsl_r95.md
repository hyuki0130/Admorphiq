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

1. For ONE family with decoded ground truth (toggle family: vc33 + ft09 —
   vc33's mechanic is representable; ft09 doubles as the hard in-family case),
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
(sc25 cast, cn04) · `teleport_portal` (sb26) · `record_replay_ghost` (lf52
ACTION5) · `undo` (ACTION7) · `phase_advance` (confirm/submit; cd82/sc25 —
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

### Open design questions (for Codex consult, this round)

- Bank sizing: 17 entity roles / 18 effects is near the 8B-context comfort
  limit — group into family-scoped sub-banks (only show toggle-family roles
  when the family classifier says toggle) or keep flat?
- Q3 sub-form resolution for T1 (click vs move) — separate question or
  planner-side branch?
- Guard vocabulary for phases (what observable predicates may gate a phase
  transition) — needs the same mining pass over sc25/cd82/lf52 traces.
- Binding format: per-role object-ID pick lists vs free (x,y) anchors —
  pick lists are closed-choice but may not contain the right candidate.

## Retained from v1

- Closed-choice (multiple-choice) slots via guided-json; no free-text escape hatch
  (R93 measured: a free channel collapses structured usage).
- `probe_more` as the explicit "insufficient evidence" selection, feeding the
  active-identification probes (#122).
- Frozen R93 lexicographic metric kept for cross-round comparability, but per
  finding 5 it is now the CONTROL metric, not the thesis metric.
