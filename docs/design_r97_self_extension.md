# R97 design — tier-2 DSL self-extension seed test (task #124)

Status: v0 draft (2026-07-23, pre-Codex). Successor to the R95 fallback-ladder
design (`design_hypothesis_dsl_r95.md` §ladder tier 2); the seed test that doc
pre-registered as "its own round after R95a/b". User directive origin
(2026-07-22, paraphrased): "let the model handle the simple additions itself —
new enum values / questionnaire entries and small working code — and test
that separately later."

## Question under test

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
