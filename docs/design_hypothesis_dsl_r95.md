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

## Retained from v1

- Closed-choice (multiple-choice) slots via guided-json; no free-text escape hatch
  (R93 measured: a free channel collapses structured usage).
- `probe_more` as the explicit "insufficient evidence" selection, feeding the
  active-identification probes (#122).
- Frozen R93 lexicographic metric kept for cross-round comparability, but per
  finding 5 it is now the CONTROL metric, not the thesis metric.
