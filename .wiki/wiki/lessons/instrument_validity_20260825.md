---
type: lesson
topic: measurement-integrity
date: 2026-08-25
keywords: [instrument-validity, corpus-validation, probe-bias, guard-vs-consumer, sibling-boards, r98, measurement-discipline]
---

# Validate the instrument before the hypothesis

> Six measurement failures in one session, none of them in the thing being measured.
> Four sat in the data-collecting instruments and two in the prompts that asked a
> model to explain itself. Every one was caught by reading the OUTPUT rather than the
> intent — a probe's own docstring is what it meant to do, and the reply is what it
> did.

## The six failures, and what each cost

**1. A corpus that did not describe its own spills.** R98's seventeen frozen boards
paired a layout with a spill that ran on a *different* layout: the capture read the board
before the final plan step and the trajectory after it. The tell was cheap and decisive —
the engine's flow passed through 1 of 1, 2 of 3 and 3 of 4 of the recorded pieces, where
every valid board has **zero**. Cost: two rules fitted to it and reverted, one of which
had passed all five gates because the contract board never exercises the path.

**2. A corpus of failures reported as a corpus.** The capture hook sat past the early
return that fires when a level clears, so it only ever wrote boards from levels that had
just FAILED — and a single overwritten path meant only the last such level survived. Every
conclusion drawn from those boards silently inherited "one level, and only when it lost".

**3. A probe whose event definition was a coincidence.** A walk probe called something an
event only when two flanks appeared on the SAME layer. Relaxing that took the table from
16 rows to 258 and inverted the finding. A second version followed runs through
CONSECUTIVE layers, so a walk that paused and resumed read as a stop: five of nine
"stops" were the probe's own artefact and the survivors were one event seen four times.

**4. A probe that acted on the system.** A game-over check PRESSED the commit action, so
every run carried an extra action and the harness reported 108 where it costs 107 — a
figure already quoted before anyone noticed.

**5. A scored prompt that forbids the thing being diagnosed.** Raw replies were kept in order
to tell "never considered the inference" from "considered and rejected it". The replies came
back as 286 characters of bare JSON, byte-identical across nine runs, because both scored asks
say *"a single JSON object and nothing else"* three times over. The format that makes an answer
parseable is the format that leaves nothing to diagnose, and the probe was inconclusive by
construction.

**6. A diagnostic prompt that withholds the evidence.** The fix — a separate unscored ask — was
built as a fresh system+user pair with no evidence in it, so the model was asked to explain a
choice whose basis it could not see. It answered in incident-management language about "a
critical system failure that could not be contained", describing nothing that happened. Asked
cold about its own answer, a model confabulates; the follow-up has to REPLAY the scored exchange
and the model's own reply, or it is a new question wearing an explanation's clothes.

## What to do instead

- **Validate the corpus before fitting to it.** A fix justified by bad boards passes every
  gate those boards do not touch, so green gates are not evidence the corpus is sound.
  Find one property a valid sample must have (here: flow never occupies a recorded piece)
  and check it.
- **Count EVENTS, not instances.** Sibling boards of one level repeat the same physical
  event; a sweep over them reports confidence proportional to how many siblings were
  captured, which has nothing to do with how much was observed. 67 instances were 14
  events; 30 "stops" were 3, then 1.
- **Read the CONSUMER, not the guard.** A guard reads its signal at its own site while the
  value it protects is consumed somewhere else. A retry loop measured inert at its own
  site — the table it filled was empty before and after — was buying a direction that only
  appeared at plan time. Removing it lost a real capability; MOVING it kept the capability
  for 1 action instead of 32.
- **A probe that acts is a change.** Reading is free; pressing is not. Any diagnostic that
  issues an action belongs behind a flag or nowhere.
- **A diagnostic prompt is an instrument too.** It can forbid the answer it wants (JSON-only)
  or withhold what the answer depends on (no evidence), and both produce confident text that
  measures nothing. When diagnosing a model's choice, continue the exchange rather than opening
  a new one, and verify the scored prompts are byte-identical with the diagnostic on and off.
- **Delete a probe when its question is answered.** Four of this session's nine diagnostics
  were retired the moment they had answered; keeping them hides the signal from the ones
  that still change with the code.

## What it bought

Fixing the instruments, not the model, took R98's replay corpus from 93 cells of error to
**12** and made the propagator exact on three consecutive levels — and the two rules that
had been reverted were never needed. The model was mostly right the whole time.

## Related

- [[../rounds/r98_flow-deflection]] — the round these came out of, entries #89–#112.
- [[false_claim_verification_20260715]] — the same discipline applied to commits and
  numbers rather than to instruments.
- [[unanimous_wrong_answers_are_a_prompt_defect_20260823]] — when several models agree on
  a wrong answer, suspect the question; the instrument-validity analogue for prompts.
