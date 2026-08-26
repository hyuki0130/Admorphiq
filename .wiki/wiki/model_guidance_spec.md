---
type: spec
status: ACTIVE — the harness layer that turns game features into a tool choice for a specific model
date: 2026-08-27
keywords: [model-guidance, context-budget, gemma4-31b, qwen3.8-27b, gpt-oss-120b, tool-selector, signature, harness, per-model, two-model-rule]
---

# Model guidance spec — how the harness tells a model which tool to use, within its context

> How each candidate offline model is guided to the right tool within its own context budget.

**Where this sits**: [[top_policy]] stage 2. Stage 1 builds the tools ([[tool_set_spec]]); this is
the layer that lets a MODEL pick and configure them on a game it has never seen. Written now, before
the tools exist, so the tools are built with the guidance in mind rather than retrofitted.

## The three models, and why the guidance must differ per model

Measured deploy candidates (R98's model stage, three runs each rising to nine):

| model | R98 SELECT | R98 FILL | note |
| --- | --- | --- | --- |
| `gemma4:31b-it-q8_0` | 9/9 | 0/9 | the long-standing deploy candidate; strong at choosing among given options, weak at filling a slot from evidence |
| `qwen3.8-27b` | 9/9 | 0/9 | matched the contract models at first outing; live candidate |
| `gpt-oss-120b` | 8/9 | 9/9 | the only one that FILLS correctly; its 8/9s are verifier UNKNOWNs on a data-indistinguishable axis, not wrong answers |

⛔ **That split is the design constraint.** Two of three models are reliable at CLOSED-CHOICE
selection and unreliable at open-ended filling. So the guidance must present tool choice as a
**closed multiple choice over a short menu**, never as "describe what to do" — the R95 typed-DSL
finding, applied to tool selection.

⚠️ And per the two-model rule, no verdict comes from one model: a guidance change is judged on at
least two, at three runs each minimum.

## What the guidance must contain, per game, within budget

`harness/context.py:build_context(sig, budget_chars=6000)` already assembles a signature-targeted
wiki slice and hard-caps it. Today it feeds [[tool_selector]] (12.9 KB), which is a DECISION TABLE
written for one tool set. The new guidance replaces its content, not its mechanism:

1. **The observable signature** the harness measured — action set, click availability, board scale,
   region counts, per-action layer burst, nondeterminism. Facts, not conclusions.
2. **The CLASS the signature suggests**, as a closed choice of four (navigate / transport / configure /
   induce), each with the two or three observables that distinguish it.
3. **The tool for that class and its configuration slots**, each slot a closed enum with its options
   glossed — because a glossed closed choice is what took gpt-oss from 0/3 to 3/3 in R98.
4. **The falsification signature** — what to observe if the choice was wrong, and which class to move
   to. A guide that cannot be wrong teaches nothing.

## Context budgets, measured per model

⚠️ **Not yet measured for this content.** `HARNESS_CTX` is the lever and
`scripts/harness_ctx_sweep.py` is the instrument that measures it. What is known: the current default
is 6000 chars, and the existing selector is 12.9 KB, so it is already being truncated at
`assembled[:budget_chars]`. Before any guidance ships, sweep the budget per model — a 27B and a 120B
do not have the same usable window, and truncation mid-table is worse than a shorter table.

## How this is tested

1. **Offline** — does the guidance, given a game's measured signature, name the class the mechanics
   put it in? Scored against [[tool_set_spec]]'s table, which is the ground truth for the 25.
2. **Per model, on GPU** — `notebooks/`'s bench kernels are the established path (`kaggle kernels
   push` does NOT consume a submission slot). Two models minimum, three runs each.
3. **Live** — the model's choice drives the tool and the game is played; the number is levels cleared,
   compared against the same tool forced without a model (`tool_alternatives.py`).

⛔ **The failure mode to watch for**: three models unanimously wrong on the same slot is a PROMPT
defect, not a model verdict — measured in R98, where fixing the prompt took gpt-oss from 0/3 to 3/3 on
both stages. Unanimity is evidence about the question, not the answerers.

## Current position

Spec written; **no guidance content authored, no budget measured**. It waits on stage 1 — guidance
that points at tools which clear nothing would be guidance to nowhere.

## Related

- [[tool_set_spec]] — the four tools this guides toward
- [[top_policy]] — stage 1 before stage 2
- [[tool_selector]] — the current decision table this replaces the content of
- [[rounds/r95_hypothesis-dsl]] — where closed-choice-beats-open-generation was measured
