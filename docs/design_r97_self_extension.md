# R97 design — tier-2 DSL self-extension seed test (task #124)

Status: v1 (Codex CONDITIONAL GO 2026-07-23 06:26, 10 binding corrections
below — the v0 draft is kept underneath for provenance). Successor to the R95
fallback-ladder
design (`design_hypothesis_dsl_r95.md` §ladder tier 2); the seed test that doc
pre-registered as "its own round after R95a/b". User directive origin
(2026-07-22, paraphrased): "let the model handle the simple additions itself —
new enum values / questionnaire entries and small working code — and test
that separately later."

## Codex v1 binding corrections (2026-07-23)

Two v0 validity traps found by code inspection, then 10 binding corrections:

- **Trap 1 — no causal use**: the compiler dispatches on canned classes and has
  NO extension node; `PatternXorPlan` assumes one-click flipping without
  consulting any transition function, so a live success could occur WITHOUT the
  authored code ever executing. R97 must build an `AuthoredCellUpdate` plan
  node that invokes the generated function for planning AND action-time
  prediction (log source hash + invocation count; substituting a known-wrong
  function must break parity — causal-use proof).
- **Trap 2 — the verifier cannot certify the hole**: the existing verifier
  checks only the modal changed-cell footprint and treats BinaryFlip and
  OrderedCycle identically. R97 needs a new EXACT colour-transition verifier.

Corrections (all binding):

1. **Oracle-certify each hole pre-model**: with the exact verifier, every
   offered candidate must be CONTRADICTED, the ablated oracle PASS, evidence
   non-UNKNOWN.
2. **Case structure fixed**: binary_flip IS ordered_cycle(k=2) — sc25+ft09 are
   ONE cyclic-successor capability, not two successes. sc25 becomes the
   NO-HOLE equivalence control; absent a genuinely non-isomorphic second
   operator, the verdict is capped at **SEED-PASS**, never general tier-2
   CONFIRMED.
3. **Evidence = exact colour-transition prose tuples** ("colour X became Y
   after clicking this cell"), episode/epoch-split, held-out must cover every
   relevant source colour + the wrap edge; feedback from TRAIN only.
4. **Exclusive output union**: `select(candidate_id)` | `extend(name, source)`
   | `abstain(insufficient_evidence)` — mixed "pick but flag misfit" is
   INVALID, not partially credited.
5. **Controls**: full-vocab NO-HOLE (extension = false positive even if
   correct); evidence-blind (success = leakage); insufficient-evidence
   (expected abstain); hand-authored oracle definition through the exact
   sandbox/verifier/compiler/live path; mutant definitions (identity, reverse
   order, constant, missing wrap, colour hard-coding, k=2-only).
6. (= Trap 1 fix) AuthoredCellUpdate compiler node with causal-use proof.
7. **Extensional equivalence replaces plan identity**: exhaustive finite
   fixtures + emitted-behaviour comparison on grounded plan fixtures.
8. **Dedicated AST-validating sandbox** (the R49 loader allows imports and
   module-level execution — insufficient): exactly one function; reject
   imports/top-level statements/globals/decorators/dangerous attributes; cap
   AST size, subprocess time, memory, output; validate return ∈ palette and
   input non-mutation.
9. **Score detection separately from authoring**: hole recall, no-hole
   specificity, abstention accuracy, code validity, TRAIN fit, held-out
   exactness, metamorphic tests, compiler parity, live result. Overall
   success requires ≥2/3 hole recall AND ≥2/3 no-hole specificity per model.
10. **Falsification attribution matrix**: blind-control success = leakage;
    no-hole pass + hole fail = escape calibration; valid proposal failing
    held-out = synthesis; offline pass + live fail = compiler/grounding
    integration. Prompt iteration after frozen runs = a new sub-round. Live
    targets must be spelled out per game (ft09 budgets; sc25 cast+handover),
    not "same as R95".

Full review: scratchpad `codex_r97_design_review.log` (session-lived; the
corrections above are the durable record).

## R97 EVALUATION CONTRACT (FROZEN 2026-07-23 09:26)

Instantiates the 10 binding corrections. Prerequisites BUILT (2b517ce):
exact colour-transition verifier + `certify_hole`, AST sandbox
(`authored.py`), AuthoredCellUpdate causal-use compiler node.

- **Capability under test**: ONE cyclic-successor operator (binary_flip IS
  ordered_cycle(k=2)); verdict cap = **SEED-PASS**, never general tier-2
  CONFIRMED.
- **Cases (per model, 3 runs each, success thresholds per case)**:
  1. HOLE (ft09 evidence): vocabulary minus `ordered_cycle`, plus the
     extend escape hatch. Success = `extend` proposed AND the authored
     definition passes TRAIN fit + held-out exactness. ≥2/3 = hole recall.
  2. NO-HOLE control (sc25 evidence): FULL vocabulary offered. Success =
     correct offered rule selected; ANY `extend` = false positive even if
     behaviourally correct. ≥2/3 = no-hole specificity.
  3. EVIDENCE-BLIND control (1 run/model): transition lines withheld.
     Successful reconstruction = LEAKAGE (invalidates case 1).
  4. INSUFFICIENT-EVIDENCE control (1 run/model): thinned evidence
     (single transition). Expected `abstain`; invention = calibration
     failure (recorded, does not gate).
- **Pre-model oracle certification (gate on the harness, not the model)**:
  `certify_hole` must show every offered candidate CONTRADICTED + the
  ablated oracle PASS on case-1 evidence; the hand-authored oracle
  definition must traverse sandbox → verifier → compiler → LIVE ft09 clear
  (4+8-action budgets, the R95b criterion); the 6 definition mutants
  (identity, reverse order, constant, missing wrap, colour hard-coding,
  k=2-only) must each fail held-out or parity. Any miss = fix the harness
  BEFORE model runs.
- **Output union (exclusive)**: `select(candidate_id)` |
  `extend(name, source)` | `abstain(insufficient_evidence)`. Mixed
  responses INVALID (one retry with the format error, as R95b).
- **Authoring scope**: one `update(colour, click_index, palette) -> int`
  through the AST sandbox; whole-solver authoring stays banned.
- **Scoring, detection separate from authoring**: hole recall / no-hole
  specificity / abstention accuracy // code validity / TRAIN fit /
  held-out exactness / extensional equivalence vs the ablated oracle /
  compiler parity (causal use) / live ft09 result. OVERALL SEED-PASS per
  model = hole recall ≥2/3 AND no-hole specificity ≥2/3; CONFIRMED
  SEED-PASS = both models (gemma4-31b-q8 + gpt-oss-120b at measured-best
  configs).
- **Leakage prohibitions**: as R95 (no game ids, adapter code, wiki,
  provenance labels; no hint of the missing rule's shape); prose-only
  evidence as exact colour-transition tuples ("colour X became Y after a
  click on that cell"); echoing_llm ask/reply from run 1.
- **Venue**: Kaggle kernels `admorphiq-r97-ext-{gemma4,gptoss}` per the
  R95b pattern; dataset-race 90s+ wait.
- **Falsification attribution (frozen matrix)**: blind-control success =
  leakage → prompt/evidence redesign, new sub-round; no-hole pass + hole
  fail = escape-hatch calibration; valid proposals failing held-out =
  synthesis capability (tier-2 leans on fork-and-patch); offline pass +
  live fail = compiler/grounding integration. Prompt iteration after
  frozen runs = a new sub-round, never a silent retry.

## Question under test (v0 draft below — superseded where corrections apply)

When the canned enum vocabulary has a HOLE (no offered `update_rule` value
predicts the observed transitions), can the model (a) recognize that no
offered value fits instead of forcing a wrong pick, and (b) propose ONE new
enum value with a small executable definition under a fixed contract that
passes transition verification — re-deriving the ablated entry from prose
evidence alone?

This is the tier-2 escalation of the ladder, tested in isolation with ground
truth available (oracle-first doctrine): we KNOW the missing entry, so both
failure modes (forced wrong pick; unverifiable definition) are measurable.

## Method (ablation seed cases)

Two symmetric cases on the PROVEN cell-state family (R95 contract complete):

| case | ablated entry | evidence game | model must re-derive |
|---|---|---|---|
| A | `binary_flip` | sc25 | 2-state toggle rule |
| B | `ordered_cycle` | ft09 | k-colour ordered cycle |

Per case: the fill prompt offers the vocabulary MINUS the ablated entry, plus
a `propose_new_rule` escape hatch. Evidence = the same prose transition lines
as R95b (prompt_notation_misparse lesson: prose only). The model either picks
an offered value (counted as FORCED-WRONG unless it also flags misfit) or
proposes `{name, definition}`.

## Fixed definition contract

- `def update(colour: int, click_index: int, palette: list[int]) -> int` —
  pure function, no imports, no state, ≤ 20 lines; executed in the R49
  sandbox (same guard rails as EWM synthesis).
- Verification: transitions split train/held-out per the R50b leakage lesson
  (feedback and fit from TRAIN only); ACCEPT iff held-out transitions predict
  exactly. Accepted definitions enter the normal compiler path; the offline
  equivalence check is plan-identity vs the canned entry's plan; the gold
  gate is a live clear (3/3 fresh-reset, same as R95 oracle gates).
- UNKNOWN/unverified never executes (unchanged doctrine). No incumbent exists
  for the hole, so keep-parent-on-loss reduces to: rejection falls through to
  the next ladder tier, never to executing the unverified definition.

## Evaluation contract (to freeze post-Codex)

- Models: BOTH gemma4-31b-q8 and gpt-oss-120b at measured-best configs (the
  two-model rule); 3 runs per case per model; success = ≥2/3.
- CONFIRMED = both models pass both cases at ≥2/3; PARTIAL verdicts recorded
  honestly per model per case.
- Leakage prohibitions as R95 (no game ids, adapter code, wiki, provenance
  labels; the prompt must not hint the missing rule's shape).
- Instrumentation: echoing_llm ask/reply wrapper from run 1 (R95 v7 lesson —
  observability BEFORE content iteration).
- Venue: Kaggle kernels per the R95b pattern (admorphiq-r97-ext-{model}).
- Falsification: if both models force a wrong offered value in ≥2/3 runs, the
  escape-hatch prompt design is the defect (iterate prompt, not schema); if
  proposals appear but fail held-out verification, tier-2 authoring at this
  scope is measured-unreliable and the ladder leans on tier-3 fork-and-patch.

## Non-goals

- No new family coverage (that is R96+); the cell-state family is the fixed
  substrate precisely because its pipeline is contract-complete.
- No whole-solver authoring (R92 measured 0; scope stays banned).
- No promotion of accepted definitions into the permanent banks within this
  round — accepted extensions are LOGGED as schema-gap candidates only.
