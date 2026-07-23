---
type: reasoning
round: R97
axis: agent25 — tier-2 DSL self-extension (model authors a missing enum + working definition)
keywords: [agent25, hypothesis-dsl, self-extension, tier-2, authored-cell-update, exact-transition-verifier, ast-sandbox, certify-hole, ft09, seed-pass, two-model, prereg]
verdict: ROUND COMPLETE — CONFIRMED SEED-PASS BOTH MODELS (2026-07-23 11:54): gptoss hole 2/3 + no-hole 3/3; gemma4 (R97b v2) hole 3/3 + no-hole 3/3; all controls abstain (no leakage, calibrated). Both models DETECT the vocabulary hole and AUTHOR verified working rules — tier-2 DSL self-extension is measured-real at seed scope (cap honoured: ONE cyclic-successor capability, not general tier-2)
commit: [fb78a64, 2b517ce, 4eb845e, 42bc851]
date: 2026-07-23
---

# R97 — tier-2 self-extension seed test

> Can the offline model, facing a deliberately ablated enum vocabulary,
> (a) recognize that no offered value fits and (b) author the missing rule
> as a small verified function — re-deriving `ordered_cycle` from prose
> transition evidence alone? Verdict cap = SEED-PASS (one cyclic-successor
> capability, per the Codex correction that binary_flip IS ordered_cycle(k=2)).

## Design (binding: `docs/design_r97_self_extension.md` v1 + frozen contract)

Codex CONDITIONAL GO exposed two validity traps in v0: the compiler had no
extension node (a live pass could occur WITHOUT the authored code executing)
and the footprint verifier could not discriminate flip-vs-cycle. Both became
build prerequisites, alongside a dedicated AST sandbox (the EWM loader is
measured-insufficient). Scoring separates DETECTION (hole recall ≥2/3 AND
no-hole specificity ≥2/3, per model) from AUTHORING (code validity, TRAIN
fit, held-out exactness, extensional equivalence, compiler parity, live).

## Build log

- **Prerequisites BUILT** (2b517ce, parallel r97-build lane): exact
  colour-transition verifier (`exact_transition.py`, per-source-colour
  next-colour with train/held-out splits + `certify_hole`); dedicated AST
  sandbox (`authored.py`, one-function validation + resource-capped
  subprocess execution); AuthoredCellUpdate compiler node (causal use in
  planning AND action-time confirmation, wrong-function parity-break
  proof). 34 tests.
- **Contract FROZEN** (4eb845e): SEED-PASS cap; 4-case structure (hole /
  no-hole / evidence-blind / insufficient-evidence); exclusive
  select/extend/abstain output union; pre-model oracle certification;
  falsification attribution matrix.
- **Pre-model oracle-certification gate PASS** (42bc851). LOAD-BEARING
  FINDING: **ft09 is a per-level 2-state toggle with level-specific colour
  pairs; the genuine k=3 ordered cycle first appears at idx4 (8,12,9)**
  (measured 3/3 deep fresh-reset runs). Case-1 hole evidence therefore
  comes from the k≥3 level — on a 2-state board binary_flip is correctly
  NOT contradicted (idx0 doubles as the honest no-hole control); contract
  amended accordingly. Certification: hole CERTIFIED on idx4 held-out
  evidence; the hand-authored generic cyclic-successor `update()` passes
  AST → TRAIN fit → held-out exactness → extensional equivalence → LIVE
  ft09 clear at [4,8] actions (= human baselines) through the causal-use
  node; all 6 definition mutants fail (colour_hardcode caught by
  extensional equivalence on a neutral palette — the one that survives
  held-out). Harness fixes confined to AuthoredCellUpdatePlan:
  guard-name-agnostic reveal-trigger (decoy levels) + ordered-palette from
  the grounding's acquired cycle.
- **Paired Kaggle bench MEASURED (02a8761, ba91afa)**:
  **gptoss = SEED-PASS** — hole recall 2/3 (`extend` chosen all 3 runs;
  two authored `cyclic_palette` definitions pass TRAIN + held-out),
  no-hole specificity 3/3 (select binary_flip, zero false positives),
  evidence-blind = abstain (NO leakage), insufficient = abstain
  (calibrated). **gemma4 = NOT SEED-PASS (hole recall 0/3) — attribution
  = un-communicated-constraint HARNESS defect**: detection was PERFECT
  (`extend` 3/3, controls clean) and the authored rule was SEMANTICALLY
  EXACT-ORACLE (`{8:12, 12:9, 9:8}` + `.get`), rejected ONLY by the AST
  sandbox's attribute-access ban — a restriction the contract prompt
  never stated. Per the frozen attribution matrix, prompt iteration = a
  NEW sub-round: **R97b in flight** (state the allowed-syntax list in
  the definition contract, identical across all four cases; re-run
  gemma4 only — the gptoss verdict stands). The tier-2 thesis takeaway
  so far: BOTH models detect the hole and author semantically-correct
  rules; the residual gap is syntax-surface communication, not
  capability.
- **R97b v2 (df6a443 syntax-contract fix): gemma4 = SEED-PASS PERFECT —
  hole recall 3/3 (extend cyclic_three_state, every authored definition
  passes TRAIN + held-out), no-hole 3/3, controls abstain. The
  un-communicated-constraint fix flipped 0/3 → 3/3, confirming v1's
  attribution exactly.**
- **ROUND COMPLETE: CONFIRMED SEED-PASS BOTH MODELS.** The tier-2 thesis
  is measured-real at seed scope: both offline models recognize a
  vocabulary hole from prose transition evidence alone, refuse to force
  an offered rule, author a working definition under the fixed contract,
  and pass exact held-out verification — with clean no-hole specificity
  and leakage/calibration controls. The residual lesson mirrors R95b's
  notation misparse: every constraint the harness enforces must be
  STATED in the model-facing contract (un-communicated constraints
  masquerade as capability failures). Next: family expansion #3 per the
  15-game inexpressible backlog.

## Related

- [[r95_hypothesis-dsl]] — the closed round whose select/fill machinery
  this extends with the authoring tier.
- [[r96_controlled-grid-dynamics]] — the parallel family-expansion round;
  its model stage shares the Kaggle bench pattern.
- [[../lessons/prompt_notation_misparse_20260723]] — prose-evidence
  doctrine applied to the transition tuples.
- [[index]]
