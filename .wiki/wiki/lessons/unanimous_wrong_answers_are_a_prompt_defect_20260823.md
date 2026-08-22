---
type: lesson
keywords: [prompt-design, model-facing-contract, unanimity, diagnostic, closed-choice, gloss, persistence, appearance-vs-mechanism, r98, flow-deflection, three-models]
date: 2026-08-23
---

# When independent models agree on the same wrong answer, the prompt is wrong

> Three independent offline models — gemma4-31b, gpt-oss-120b and qwen3.8-27b —
> gave the SAME wrong value in the same three slots across all nine R98 fill runs.
> Unanimity at that rate is not three models failing alike; it is one prompt
> telling them the same wrong thing. The rule: treat cross-model unanimity on a
> wrong answer as a prompt defect until proven otherwise, and look for the
> sentence that licenses it.

## The measurement

R98's fill stage asks the model to choose values for six gated slots describing
how flow behaves. Aggregated over 9 runs × 3 models:

| slot | truth | answers |
|---|---|---|
| `piece_response_direction` | `preserved` | **`outward_turned` 9/9** |
| `sink_response_predicate` | `same_sink_flanks` | **`contact` 9/9** |
| `hazard_response` | `terminate_fatal` | **`terminate_local` 9/9** |
| `piece_response_propagation` | `cellwise_iterative` | correct 8/9 |
| `sink_response_miss` | `spread_like_piece` | correct 7/9 |
| `piece_response_spawn` | (equivalence class) | correct 9/9 |

The last three rows are what make the diagnosis sound: the models were REASONING
from the evidence, not guessing. A guesser does not get three slots right and
three slots unanimously wrong.

The same defect explained a second stage: gpt-oss's select failures picked exactly
the hazard-ignoring and outward-turning candidates — the two misconceptions the
prompt was seeding.

## The three defects, and their shapes

**1. Describing the APPEARANCE instead of the MECHANISM.** The evidence said the
split cells "moved outward one cell per picture". That is what the animation looks
like; it is the opposite of what happens. Flow cells PERSIST, so a filled cell
appearing further out is a NEW cell, not an old one travelling sideways. Every
model dutifully answered `outward_turned`.

Generalisation: when a mechanism produces a misleading visual, the contract must
name the invariant that resolves it ("filled cells persist") AND warn about the
illusion in words ("sideways APPEARANCE is not sideways TRAVEL"). Describing what
a frame looks like is not the same as describing what the rule is.

**2. Closed choices shipped as bare identifiers.** A slot offered
`same_sink_flanks | contact` with no gloss. No model can map `same_sink_flanks`
onto "the flow occupied the notch in the target's top edge" by inference — the
identifier is an internal name, not a description. Every value in every slot now
carries a one-line gloss, and the evidence sentence uses the SAME words as the
gloss so the match is lexical, not inferential.

**3. Two slots whose interaction was invisible.** Hazard behaviour was split
between a flow-level response and an objective-level policy. The prediction is
only right when the two agree, but nothing said so, and the model reasonably put
"the stream stopped" in one and "the attempt can still succeed" in the other. If
two answers must be consistent, the ask has to say it.

## The rule

This is the THIRD independent measurement of the same underlying failure:

- [[prompt_notation_misparse_20260723]] — compact notation misread (R95b)
- R97 — an AST constraint the harness enforced but never stated
- this — an illusion described as fact, unglossed vocabulary, hidden coupling

So the discipline is now: **every constraint the harness enforces must be STATED
in the model-facing contract, in words the model cannot misread**, and any
cross-model unanimity on a wrong answer is a defect report against the prompt, not
a datapoint about the model. The cheap diagnostic is to aggregate answers per slot
across models: unanimity on a wrong value points at the sentence to fix.

## Related

- [[../rounds/r98_flow-deflection]] — the round that measured it.
- [[prompt_notation_misparse_20260723]] — the first occurrence.
- [[false_claim_verification_20260715]] — the sibling discipline: verify before
  recording.
