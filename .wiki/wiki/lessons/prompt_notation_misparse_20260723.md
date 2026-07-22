---
type: lesson
keywords: [prompt-design, notation, misparse, gemma4, observation-summary, prose, histogram, fill-mode, r95]
date: 2026-07-23
---

# Compact notation in model-facing evidence gets misparsed — write prose

> gemma4-31b deterministically misread the histogram notation
> `1cell(s)->5click(s)` as "5 cells change per click" (key/value swap),
> driving a wrong hypothesis pick across FOUR harness iterations until a
> transparent ask/reply echo exposed the misparse verbatim; the fix is
> unambiguous prose ("5 clicks changed exactly 1 cell each").

## Symptom

A model repeatedly makes the same wrong closed-choice pick (sc25 fill mode:
`empirical_effect_matrix`, byte-identical across runs) even as the evidence
CONTENT is progressively cleaned (wording changes, line removals, statistics
fixes). Content-level hypotheses keep failing: R95b fill v3 (wording A), v4
(wording B), v5 (line removed), v6 (histogram cleaned) all left the pick
unchanged.

## Root Cause

The observation summary rendered the click-effect histogram as
`Ncell(s)->Mclick(s)`. On a SPARSE two-entry histogram the model swapped key
and value — its own evidence sentence (captured by the v7 `echoing_llm`
observability wrapper) read: "The fact that 5 cells change upon a single
click indicates an empirical_effect_matrix". A many-entry histogram (ft09,
`1cell(s)->215click(s)`) survived because absurd readings self-filtered; the
sparse case had no such guard. Provenance: `scripts/rounds/R95/`
`r95b_fill_bench_gemma4_v3..v8.json`, root cause commit a9d6828, fix a866c8b.

## Prevention

1. Model-facing evidence lines use UNAMBIGUOUS PROSE naming both quantities
   inline: "<M> clicks changed exactly <N> cells each" — never arrow/colon
   compact notations whose direction a reader must infer.
2. A regression test pins prose-not-arrow
   (`test_footprint_evidence_uses_unambiguous_prose_not_arrow_notation`).
3. Before iterating on evidence CONTENT, gain OBSERVABILITY: echo the exact
   assembled ask and the raw reply at the llm boundary (the transparent
   `echoing_llm` wrapper) — two blind content guesses failed before one look
   at the reply solved it.

## Recovery

If a model's picks are byte-identical across evidence changes, suspect a
PARSING failure of the evidence format, not the evidence content: read the
model's own evidence sentence for what it BELIEVES the observation said, and
compare against the actual prompt line.

## Falsification

If a model reproduces the same wrong pick under the prose rendering while its
evidence sentence correctly restates the observation, this lesson's
diagnosis does not apply — the failure is then genuine reasoning, not
notation.

## Related

- [[../rounds/r95_hypothesis-dsl]] — the round where this was measured
  (fill v3–v8 ladder).
- [[selector_is_advisory_not_enforced_20260421]] — the sibling lesson on the
  OUTPUT side (prompt guidance needs decoder-level enforcement); this page is
  the INPUT side (evidence needs parse-proof rendering).
