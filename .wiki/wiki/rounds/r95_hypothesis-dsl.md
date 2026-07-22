---
type: reasoning
round: R95
axis: agent25 — typed hypothesis DSL (discriminative selection first)
keywords: [agent25, hypothesis-dsl, discriminative-selection, enum-vocabulary, family-sub-banks, equivalence-class, ft09, sc25, oracle-first, fallback-ladder, self-extension, two-model, prereg]
verdict: IN PROGRESS — design v2.6 frozen (twice Codex-consulted); R95a part-1 MEASURED (405e754): exhaustive ranking finds the oracle on both games; ft09 equivalence {glyph_constraints, nearest_glyph_only} is GENUINE data-indistinguishability (1436-frame divergence scan, 0 divergences); sc25 is a WEAK case (zero clean win-axis negatives — all 14 gold clicks are cast states; old fp=0.60 was mislabeled correct positives). Part-2 LLM ask (gemma4 + gpt-oss, x3 reps, equivalence-class PASS rule) in build
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

## Part 2 (in build) — frozen prereg

Neutral shuffled template descriptions (T1..T5, no names), TRAIN-only
observation summary, guided-json choice + confidence + evidence, 3 reps per
game per model, PASS = choice lands in the measured equivalence class,
compared against the no-LLM exhaustive-ranking control. gemma4 + gpt-oss-120b
paired. Kaggle notebook `notebooks/r95a_select_bench.py`.

## Related

- [[r94_adapter-template]] — the refuted family-template road this replaces.
- [[r93_tool-fork-patch]] — the patching tier the ladder retains (final LLM tier).
- [[r57_win-condition-typology]] — Q3 goal bank source (T1–T8).
- [[r53_unified-harness]] — the tool/harness spine the DSL compiler reuses.
- [[index]]
