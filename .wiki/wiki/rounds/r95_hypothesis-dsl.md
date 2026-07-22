---
type: reasoning
round: R95
axis: agent25 — typed hypothesis DSL (discriminative selection first)
keywords: [agent25, hypothesis-dsl, discriminative-selection, enum-vocabulary, family-sub-banks, equivalence-class, ft09, sc25, oracle-first, fallback-ladder, self-extension, two-model, prereg]
verdict: ROUND CLOSED, CONTRACT COMPLETE (2026-07-23 04:17) — the R95b evaluation contract is fulfilled end to end for gemma4 in BOTH model substages. SELECT mode: CONFIRMED paired (gemma4 6/6 exact-oracle; gpt-oss ft09 2/3 with the verifier catching its wrong stencil pick live + sc25 3/3). FILL mode (generation, no candidates shown): ft09 3/3 across FOUR consecutive rounds (model-generated oracle-identical semantics clears idx0+idx1 at human-baseline efficiency) AND sc25 3/3 after an eight-iteration defect ladder whose final root cause — captured verbatim from the model's own reply via the v7 observability wrapper — was the harness's histogram NOTATION being misparsed (key/value swap), fixed by prose rendering (lesson: prompt_notation_misparse_20260723). MILESTONE within the round: the first fully autonomous agent25 clears (2026-07-22 19:28). The model-stage finale scored 6/6 across both games — the model picked the EXACT ORACLE from live grounding evidence in every fresh run, the verifier PASSed it, and the compiled plan cleared ft09 idx0+idx1 at 4+8 actions (human baseline) and reached sc25 cast+handover, 3/3 each — exceeding the frozen ≥2/3 contract bar with zero adapter code and zero game ids anywhere in the runtime path. Earlier in the round: R95a paired selection confirmation (both models 3/3 exact-oracle on ft09; sc25 chrome defect #125 found via cross-model failure, fixed, gemma4 recovered 3/3), and the full oracle pipeline (schema→grounding→verify→compile→live) proven at both family variants. gptoss twin in flight; step (viii) slot filling remains
commit: [aa8bdfa, d511ed6, 40ee7fd, 7e456dd, 405e754, 82199cf]
date: 2026-07-22
---

# R95 — typed hypothesis DSL: the model hypothesizes, the harness codes

> After R92 (from-scratch authoring: 0), R93 (small-card patching: works
> sometimes), and R94 (family templates don't transfer out-of-family at ANY
> size), R95 moves the model's game-understanding channel to closed-choice
> hypothesis selection over a domain-mined enum vocabulary, verified against
> observed transitions before any execution.

## Design (binding: `docs/design_hypothesis_dsl_r95.md` v2.6)

Two Codex consultations shaped it (session logs `codex_r95_dsl_review.log`,
`codex_r95_vocab_review.log`):

1. **NO-GO v1** — single universal schema under-expressive; 0.8-ratio verifier
   unsound; sk48 invalid first holdout; attribution gap → oracle gate,
   `PASS/CONTRADICTED/UNKNOWN` verdicts, tagged family schemas, and the CHEAP
   pre-test (R95a) before any compiler build.
2. **Vocabulary consult** — family-scoped sub-banks (top-2 union + common
   bank, no irreversible classifier); `reach_mode` as its own closed question;
   typed guard-clause conjunctions for phases; ID-only binding (typed anchor
   IDs, raw (x,y) never model-generated); Q5 composition claim corrected
   (safe gap DETECTION, not expressibility — mode-conditional counterexample);
   R95a family = **ft09 + sc25 pattern phase** (vc33 dropped: not clean
   toggle-family); a 15-game inexpressible-mechanics backlog = the v1
   expansion list.

**Fallback ladder** (user directives 2026-07-22): DSL select → active
identification probes → **DSL self-extension** (model proposes ONE new enum +
fixed-contract definition, verifier-gated; measured basis = EWM R48–R52) →
tool fork-and-patch ([[r93_tool-fork-patch]], demoted to FINAL LLM tier) →
generic-exploration floor. Keep-parent-on-loss at every tier; two-model rule
(gemma4-31b-q8 + gpt-oss-120b at their measured-best configs, paired, no
one-shot verdicts). Self-extension seed test = task #124.

## R95a part 1 — measured (commit 405e754)

`scripts/probe_hypothesis_select.py` + `src/admorphiq/hypothesis_select/`:
per game, 5 templates (decoded ORACLE + hard negatives drawn from
historically-falsified hypotheses), even/odd per-level held-out split,
dynamics axis (predicted changed-cell set) + win axis (TPR/FPR over gold
level-up events and cast-state-excluded negatives), exhaustive replay-ranking
control, behaviour-signature tie detection.

| game | oracle strictly beats | equivalence class | random PASS |
|---|---|---|---|
| ft09 | gf2_stencil (dyn 0.822 vs 0.021), uniform_colour + all_ink_equal (win TPR 1.0 vs 0.0) | + nearest_glyph_only | 0.4 — **primary case** |
| sc25 | neighbour_stencil (dyn 0.571 vs 0.0), absolute_preview (win TPR 1.0 vs 0.0) | + colour_cycle + near_match_threshold | 0.6 — weak case |

Two honest data findings (both verified by dedicated scans, not assumed):

1. **ft09 near-miss states never occur in gold** — 1436 frames scanned, 0
   divergences between all-covering and nearest-only constraint evaluation.
   The distinguishing board (nearest satisfied, farther violated) is exactly
   the L3 coverage-scoping near-miss of
   [[../lessons/ft09_glyph_decode_20260715]], and the gold path skips it.
2. **sc25's trace has zero clean win-axis negatives** — every parse-valid
   gold click is a cast state (auto-cast fires on exact match and the matched
   pattern persists through navigation); the earlier fp=0.60 was CORRECT
   oracle firings mislabeled as false positives. Near-match (≥7/9) is
   provably indistinguishable here: 0 frames at 7–8/9 (distribution
   {5:16, 6:10, 9:464}). Follow-up lever = richer trace recapture, not a
   scoring change.

## Part 2 — frozen prereg + gemma4 result (2026-07-22 15:31 collection)

Neutral shuffled template descriptions (T1..T5, no names), TRAIN-only
observation summary, guided-json choice + confidence + evidence, 3 reps per
game per model, PASS = choice lands in the measured equivalence class,
compared against the no-LLM exhaustive-ranking control. gemma4 + gpt-oss-120b
paired. Kaggle notebook `notebooks/r95a_select_bench.py` (part-2 build
4bf3b6a; one build-time fix mattered: the observation histogram initially
counted PIXELS — one ft09 button = 36 px — which would have biased toward the
stencil negative; fixed to LOGICAL cells before any model run).

**gemma4-31b-it (kernel `admorphiq-r95a-select-gemma4` v1; artifacts
`scripts/rounds/R95/r95a_select_bench_gemma4.json`):**

| game | pass rate | picks | random baseline |
|---|---|---|---|
| ft09 (PRIMARY) | **3/3 PASS** | T4 = the ORACLE itself ×3, confidence high | 0.4 |
| sc25 (weak) | 0/3 FAIL | T5 = neighbour_stencil ×3, confidence high | 0.6 |

Evidence audit (the load-bearing part):

- **ft09**: every rep cites the true discriminating observations — "215/359
  clicks change exactly 1 cell, contradicting the plus-shaped group" +
  the marker-ring structure supporting relational completion over the
  simpler goals. This is genuine discrimination, not a length/position
  artifact: the model picked the strict oracle, not merely the tied class.
- **sc25**: the model's inference is CORRECT GIVEN ITS OBSERVATIONS — the
  histogram genuinely shows multi-cell changes (2/4/5/14), because the click
  CURSOR appears as a second changed region. The build agent PREDICTED this
  exact failure pre-run and did not special-case it. So the sc25 FAIL is an
  OBSERVATION-LAYER defect (cursor/HUD masking — precisely the Codex
  finding-6 binding-layer gap), not a model reasoning failure. First concrete
  entry in the binding-layer backlog: mask transient cursor regions before
  building click histograms.

**gpt-oss-120b (kernel `admorphiq-r95a-select-gptoss` v1, reasoning=high;
artifacts `scripts/rounds/R95/r95a_select_bench_gptoss.json`)**: IDENTICAL
outcome — ft09 3/3 PASS picking the exact oracle T4 (attempts=1, confidence
high, same true-discriminator evidence, one rep even correctly attributing
the multi-cell tail to level redraws); sc25 3/3 FAIL on the same T5
neighbour_stencil with the same cursor-artifact reasoning.

**PAIRED VERDICT (final, per the frozen prereg)**:

1. **Thesis CONFIRMED on the primary case, across models**: both models beat
   the 0.4 baseline 3/3 with the strict oracle and correct evidence. This is
   the first measured demonstration that the offline models can SELECT the
   correct mechanic hypothesis from strong falsified distractors when the
   observation package is honest — the capability R92's free-form authoring
   failure obscured.
2. **sc25 = observation-layer defect CONFIRMED across models**: two different
   model families reasoning correctly from the same corrupted histogram is
   exactly what "the harness, not the model" looks like. First binding-layer
   backlog item: mask transient cursor regions before building click
   histograms (Codex finding-6 made concrete).
3. **No model-capability difference on this bench** — consistent with the R93
   breadth NO-NOMINATION; the patcher-model choice remains open and
   non-load-bearing.
4. **R95b family-compiler gate OPENS** per prereg (model showed selection
   skill on the representable case).

## #125 masked rerun (gemma4 v2, collected 2026-07-22 16:54) — defect chain CLOSED

The #125 fix (commit b3bdcf5; diagnosis CORRECTED during build: the real sc25
artifact is the right-edge click-budget BAR leaking past the col-63 HUD mask
— edge-touch fraction 0.86 vs ft09 0.06 — NOT a relocating cursor; both a
generic HUD-edge rule and a generic relocating-cursor guard were implemented,
the latter inert on both traces and synthetic-proven) changed ONLY the
observation layer: sc25 histogram mode 2→1 cell, ft09 byte-identical,
part-1 frozen numbers untouched (dynamics_heldout_masked == dynamics_heldout
— the pixel-Jaccard axis had tolerated the 2-pixel bar all along; only the
integer histogram the LLM reads was corrupted).

Rerun (`r95a_select_bench_gemma4_v2_masked.json`): **sc25 0/3 → 3/3 PASS,
picking the exact oracle** (evidence: "4 of 7 clicks changed only 1 cell,
contradicts T5" — the masked histogram is what flipped it), confidence
medium (honest — sc25 evidence is thinner). ft09 replicated 3/3 exact-oracle,
byte-identical observations. The full loop — cross-model failure observed →
mechanism predicted → harness fixed generically → picks recover — is the
first CLOSED defect chain through the hypothesis channel.

**gpt-oss v2 (paired closure, collected 17:14;
`r95a_select_bench_gptoss_v2_masked.json`)**: ft09 3/3 exact-oracle
replicated. sc25 STILL 0/3 — but the failure MODE changed, which is itself
evidence the masking worked: rep0 anchored on the honest 13-cell
level-transition example (T5); reps 1/2 read the dynamics CORRECTLY
(single-cell) but misinterpreted the completion evidence as absolute-preview
(T2). **First model difference in R95**: with corrected observations gemma4
recovers fully, gpt-oss scatters across strictly-dominated negatives on
sc25's thin evidence (9 clicks, 4 win events, one outlier example). Per the
tuning-ladder rule this is one bench config, NOT a nomination — recorded as
a paired divergence. Root cause of the residual failure = sc25 evidence
THINNESS (the prereg's known weak-case limitation), for which the honest
lever remains richer trace recapture, not scoring or prompt changes.
#125 itself is COMPLETE: the chrome defect is fixed, validated (histogram
mode 2→1, ft09 byte-identical), and closure is demonstrated on gemma4.

## R95b build progress (Codex CONDITIONAL GO plan v1; live log)

- **(i) evaluation contract FROZEN** (34553c5): ft09 idx0/idx1 + sc25 idx0
  cast; fresh-reset + grounded clicks only; ≥2/3-runs success rule; leakage
  prohibitions; grounding-failure falsification clause.
- **(ii) schema BUILT** (3c1b142): tagged objective union (cross-products
  unrepresentable by type), OrderedCycle transition model, 11-clause guard
  vocabulary, ownership table (`model_selected` = exactly 4 semantic slots),
  ft09/sc25 oracle instances, 6-mutant expected-verdict table shipped as data.
- **(iii) grounding service BUILT** (925d26f): colour-independent stable IDs
  (epoch-namespaced), materialized cells/glyphs/incidence, action-time click
  resolution, rebind events, honest-UNKNOWN + min-probe cycle acquisition.
  Family parse LIFTED out of the quarantined adapters (1685-frame byte
  parity) — the hypothesis channel now has zero adapter dependency. Two
  honest findings: gold traces cannot complete the ft09 cycle (minimal-click
  play never shows the closing edges → live gate needs bidirectional
  probes), and L3 shows a 12→8 edge CONTRADICTING the documented [9,8,12]
  cycle — under investigation before the verifier freezes expectations.
- **(iv) verifier BUILT** (05b5b0c): PASS/CONTRADICTED/UNKNOWN over grounded
  evidence (footprint transition axis — level-invariant; held-out-episode
  objective axis; honest relaxation-UNKNOWN); **mutant verdict matrix
  reproduced EXACTLY 8/8** vs the frozen step-ii table, no forcing. The L3
  cycle anomaly RESOLVED as cause (a): all six 12→8 edges were decoy→reveal
  wholesale redraws misattributed as same-cell transitions (first click of
  each episode, intra_wholesale=True) — documented cycle intact, wholesale-
  skip guard added + pinned.
- **(v) compiler BUILT** (25a129a): tag-only dispatch (grep-guarded — zero
  game ids / adapter imports), GlyphConstraintPlan (cycle-distance clicks
  with per-click confirmation) + PatternXorPlan (base-XOR-preview flip set,
  guard-gated cast), typed failure surfaces DIVERGED / GROUNDING_INCOMPLETE
  / UNSATISFIABLE. **Offline gate PASSED with the headline number of the
  round: the ft09 L0 oracle plan clicks EXACTLY 4 cells — the human
  baseline — reaching 32/32 constraints satisfied.** The hypothesis→
  grounding→compile path is human-efficient by construction on the fixture.
  sc25 flip set matches the XOR diff exactly (synthetic fixture; gold has no
  unsolved pattern-phase sequence — the known trace degeneracy).
- **(vi) live oracle gate — FIRST LIVE CLEARS through the hypothesis channel**
  (driver d8f3421; measurement `scripts/rounds/R95/r95b_gate_ft09.json`,
  2026-07-22 17:52): **ft09 idx0 CLEARED 3/3 fresh-reset runs at EXACTLY 4
  actions each — the human baseline — fully deterministic** (discovery 15
  actions closes the cycle gold could not, every run; responsiveness-adaptive
  bidirectional probing after a blind fixed-cell probe measured inert on
  already-satisfied cells). Gate verdict as specified (idx0+idx1) = FAIL:
  idx1 is a decoy→reveal board the single-phase oracle instance
  under-models — plan-DONE without a clear is recorded DIVERGED (honest),
  3/3 consistent. sc25 live pattern read DIVERGED at start (smoke). Both
  walls assigned: principled phase/guard extension for the reveal trigger +
  live pattern-read diagnosis. Re-gate after fixes.
- **(vi) RE-GATE, ft09: PASS 3/3** (fixes 8f637de; measurement
  `r95b_gate_ft09_v2.json`, 18:21): idx0+idx1 cleared in EVERY fresh-reset
  run at 4+8 actions, discovery 19, one rebind (the decoy→reveal transition)
  per run — fully deterministic. The reveal wall was closed the PRINCIPLED
  way (schema reveal phase + trigger-then-resolve + per-board cycle reset),
  and the sc25 start-divergence was diagnosed to the BASE SNAPSHOT (majority
  read spuriously matching the start board) and fixed. sc25's deeper
  post-cast EXIT-NAV phase is outside the frozen contract (navigation
  excluded) — banked as follow-up; the driver's sc25 criterion is being
  aligned to the contract (cast + guard handover), then sc25 re-gates.
- **(vi) COMPLETE — BOTH oracle gates PASS** (sc25 criterion aligned to the
  frozen contract c6f82ed; measurement `r95b_gate_sc25_v2.json`, 18:27):
  sc25 3/3 CAST_HANDOVER (genuine flip clicks + cast colour observed +
  StableForReads∧RolesStateEqual on the committed grid; levels honestly 0 —
  navigation is contract-excluded; post-cast exit-nav banked as follow-up).
  Combined with ft09's 3/3 idx0+idx1, the ENTIRE oracle pipeline — schema →
  grounding → verify → compile → live — is proven on both family variants.
- **(vii) canned-instance model stage BUILT + LAUNCHED** (9dd2eb9; kernel
  `admorphiq-r95b-model-gemma4` v1, 18:43): per fresh run — warm-up →
  discovery → selection ask over 4 serialized neutral instances (oracle + 3
  same-game mutants, deterministic shuffle, leak-guarded; observation
  context = the run's OWN live grounding evidence) → verifier gate
  (CONTRADICTED never executes; objective mutants pass pre-solve — no win
  evidence — and are arbitrated by execution) → compile → live execute via
  the SAME execute_instance path the oracle gate used. Success = ≥2/3 runs
  (ft09 idx0+idx1 clear; sc25 cast_and_handover). A pass = the first fully
  autonomous agent25 clears through the hypothesis channel. gptoss twin
  after gemma4.
- **(vii) MODEL STAGE: 6/6 PASS — THE MILESTONE** (gemma4, collected 19:28;
  `scripts/rounds/R95/r95b_model_bench_gemma4.json`): in EVERY fresh run the
  model selected the exact oracle instance from the run's own live grounding
  evidence (ft09: I3 ×3, refuting the stencil mutant via the measured
  1-cell footprint; sc25: I1 ×3), the verifier PASSed it, and the compiled
  plan cleared ft09 idx0+idx1 at 4+8 actions and reached sc25 cast+handover
  — 3/3 each vs the ≥2/3 bar. **The first fully autonomous agent25 clears:
  model-chosen hypothesis → verifier → compiler → live clear at
  human-baseline efficiency, zero adapter code.** gptoss twin launched
  (`admorphiq-r95b-model-gptoss` v1) for the paired record.
- **(vii) PAIRED RECORD — CONFIRMED** (gptoss collected 20:11;
  `r95b_model_bench_gptoss.json`): gpt-oss PASSES both games per the frozen
  ≥2/3 rule — ft09 2/3 (runs 1–2 exact-oracle → 2 levels each), sc25 3/3
  cast+handover. Two textured findings inside the pass:
  1. **The verifier gate saved a wrong pick, live**: gpt-oss run 0 chose the
     STENCIL mutant → verifier CONTRADICTED → never executed (zero actions
     wasted) → the run failed SAFELY. First live demonstration of the safety
     layer doing its job inside the model loop.
  2. **sc25 picked the absolute-preview MUTANT ×3 yet passed**: on idx0 the
     base is uniform, so absolute and XOR interpretations produce the SAME
     flip set — execution-equivalent on this level (the R95a thin-evidence
     signature again, now at the execution layer). gemma4 picked the true
     oracle 6/6; gpt-oss's sc25 selection weakness persists — second soft
     divergence, still not a nomination (tuning-ladder rule).
  **Overall verdict per the frozen contract: CONFIRMED — both models pass
  both games.** The hypothesis channel is end-to-end real on the cell-state
  family.
- **(viii) slot filling — BUILT + v1 measured + fixes in v2** (ef5b33e →
  735d76a): two-stage generation (ASK1 variant, ASK2 that variant's
  model_selected slots only; harness fills every measured field per
  OWNERSHIP; from_json error-feedback retry). **Fill v1 (gemma4): sc25 3/3
  PASS — the model GENERATED the hypothesis (no candidates shown) and cast
  every run.** ft09 v1 = ERROR exposing two harness defects, both fixed:
  (1) an unsupported variant combination crashed instead of a typed
  UNSUPPORTED_COMBINATION failure; (2) ASK1 lacked cycle-vs-flip evidence —
  and the FIRST proposed discriminator ("repeated clicks show 3 colours ⇒
  cycle") was MEASURED-INVERTED by the build agent before shipping (ft09's
  third cycle colour is latent → observably a 2-state toggle; sc25 shows 3
  colours via the transient selection colour) → replaced with the
  correctly-oriented click-style evidence (selection-step vs
  direct-change) + auto-pairing of the genuinely unobservable
  {ordered_cycle ↔ binary_flip} pair, BOUNDED so effect_matrix picks stand
  and fail typed (the verifier/compile-guard safety layer is preserved).
  Fill v2 kernel in flight.

## Fill-mode finale (v3–v8 defect ladder → CONTRACT COMPLETE, 2026-07-23 04:17)

The generation substage closed after an eight-iteration ladder in which every
iteration attributed and removed a DISTINCT defect (never a re-roll):
crash-on-unsupported-combination → cycle-evidence gap (proposed discriminator
MEASURED-INVERTED by the build agent pre-ship) → evidence-line wording ×2 →
line removal → cast-commit contamination theory (self-falsified live) →
**v7 observability (echoing_llm) captured the true root cause verbatim from
the model's own reply: the `Ncell(s)->Mclick(s)` histogram notation was
misparsed with key/value swapped** → v8 prose rendering fixed it
([[../lessons/prompt_notation_misparse_20260723]]).

**Final fill result (v8, `r95b_fill_bench_gemma4_v8.json`)**: ft09 3/3
(FOURTH consecutive round — model-generated oracle-identical semantics,
idx0+idx1 at human baseline) AND sc25 3/3 (pattern_reference + binary_flip →
cast+handover every run). Both ≥2/3 → the frozen evaluation contract is
fulfilled for gemma4 in BOTH substages (select 6/6 + fill 6/6). Honest note:
sc25's preview_interpretation lands on absolute_exact, execution-equivalent
to xor_exact on idx0's uniform base — the known thin-evidence signature,
unresolvable without richer traces.

## Related

- [[r94_adapter-template]] — the refuted family-template road this replaces.
- [[r93_tool-fork-patch]] — the patching tier the ladder retains (final LLM tier).
- [[r57_win-condition-typology]] — Q3 goal bank source (T1–T8).
- [[r53_unified-harness]] — the tool/harness spine the DSL compiler reuses.
- [[index]]
