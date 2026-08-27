---
type: lesson
topic: measurement-integrity
date: 2026-08-25
keywords: [instrument-validity, corpus-validation, probe-bias, guard-vs-consumer, sibling-boards, r98, measurement-discipline]
---

# Validate the instrument before the hypothesis

> Nine measurement failures in one session, none of them in the thing being measured.
> Four sat in the data-collecting instruments, two in the prompts that asked a model
> to explain itself, and three in the CHECKERS built to catch the first six. Every one
> was caught by reading the OUTPUT rather than the intent — a probe's own docstring is
> what it meant to do, and the reply is what it did.

## The nine failures, and what each cost

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

**7-9. The checkers built to catch the others.** Three, in one afternoon, all in code written
specifically to stop this happening:

* the explanation checker convicted a model on its FIRST run for a sentence naming what was
  ABSENT — *"if the animation had ended with a failure screen"* — because it matched words
  instead of claims;
* the fix then excused a genuine claim, *"the targets were not satisfied"*, because the
  counterfactual guard listed "no" and "not" among its markers. **Negation is not
  counterfactual framing**;
* the entry-numbering pin's parser took "a line starting with a digit that has a dot nearby",
  swallowed `0/9 FAIL`, and died on it.

None of these would have been caught by the check passing. Each was caught by running it on
text whose verdict was already known, in BOTH directions — a checker that flags nothing and one
that flags everything each pass a one-sided test.

## A fourth kind: an ad-hoc driver that is not the runner (2026-08-27)

Three throwaway probes were written in one afternoon to count what a real run does — which tool
acts inside each attempt, which tool holds a board while bidding zero. Each drove the game itself
rather than calling `score_efficiency.run_game`, and each was wrong in a way that looked like a
finding about the SYSTEM:

* one reported `bp35` crashing its own engine with `KeyError: 'x'` inside `perform_action`,
  complete with a traceback into the game's obfuscated `step()`. The real runner records **zero**
  such crashes on that game. The runner passes click coordinates as a separate argument —
  `env.step(action, data=action.action_data.model_dump())` — and the probe called `env.step(action)`,
  so every ACTION6 arrived without the `x` the game reads. The engine was right and the probe was
  wrong;
* another passed `[obs]` as the frames list where the runner passes an accumulated one, and so
  measured a tool that never switched when the real loop switches at step 479;
* the third asked a tool for its bid mid-restart and got an exception it reported as a zero.

⛔ **When counting what a real run does, drive it with the real runner.** `harness_probe.py` and
`attempt_probe.py` exist because of this; both wrap the same loop the score uses. An ad-hoc driver
answers a question about the ad-hoc driver.

⚠️ **And that is necessary, not sufficient.** The same question — what kills a game between 2 and
35 actions — took FOUR instrument revisions, each failing differently and each looking plausible:

1. an ad-hoc driver called `env.step(action)` where the runner calls
   `env.step(action, data=action.action_data.model_dump())`, so every click arrived without its
   coordinates and the GAME appeared to crash;
2. calling `run_game` with an `adapter_factory` that built the agent by hand dropped the
   `giveup`/`stall`/`ctx_budget` the runner supplies — score 0.0338 with 2 levels where the real
   run gives 0.1648 with 5. **Using the runner is not the same as letting the runner build the
   agent;**
3. reading the state from the frame handed to `choose_action` reported ZERO deaths, because a
   GAME_OVER the runner resets is never shown to the agent. The env is where that truth is;
4. replacing the class in the runner's module namespace did nothing, because `_make_agent`
   imports it INSIDE the function — so the real agent ran, the score matched perfectly, and the
   spy recorded `None` for all 24 deaths. **A number that reproduces the real one is not proof
   the instrument is attached.**

The one honest measurement to come out of it: bp35 has **24 GAME_OVER transitions** in a
1600-action run, counted at the env boundary. Which tool is acting at each is still unmeasured,
and belongs to whoever owns the tool — instrumenting from inside it avoids all four traps above.

## The single failure behind both halves of 2026-08-27

The day produced two apparently unrelated classes of error, and they are one:

* **guards that decayed** — a bail's stated 10x margin had become 4.7x, a cap's stated 4x had
  become 10x, a "29 specialists" comment had become 38, none of them touched by anyone;
* **parks that overreached** — a level parked as having "nowhere to go" when the measurement only
  supported "nowhere the travel objective scores", and the difference turned out to be a cart
  that cannot REACH the far side but can REVEAL it.

Both are **a claim calibrated against a measurement, then carried further than the measurement
reached.** The guard was true when written and the world moved; the park was true of what was
measured and the sentence covered more than that. Neither needed anyone to be careless — they
needed only time, or one word doing more work than the evidence.

⛔ So the rule is not "measure more". It is: **when you write down a conclusion, write down what
it was measured against**, because that is what lets the next reader — often yourself, hours
later — notice it no longer holds. Every one of the five corrections above was found in one
command, and only because the original claim had named its own basis.

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
- **A checker is an instrument, and the last one anybody validates.** Run it on input whose
  verdict you already know, in both directions, before running it on the input you care about.
  Every checker this session built was wrong on its first run and right after one measurement.
  ⛔ **2026-08-26 — this rule was ON THIS PAGE and I did not apply it.** A recolour probe was
  written to ask whether four detectors read structure or palette, run straight at the four
  whose answer was unknown, and its verdict reported: "ft09 and ls20 key on colour values, so
  their footing is weaker." Only afterwards was it run against the five ports whose transfer is
  already MEASURED — and three that FAIL recolouring (re86, su15, sk48) demonstrably fire on
  archived version hashes and solve them. The probe is invalid as a transfer proxy and the
  conclusion had to be withdrawn. **A recorded rule that is not applied costs exactly what a
  missing rule costs**, and the order is the whole rule: validate FIRST, then read.
- **A field means what it RECORDS, not what its name suggests.** Three conclusions this session
  were built on data read as something it was not, and each was caught only by opening the raw
  values:
  * a run directory missing games was read as a run with zero-scoring games — an unfinished
    measurement reported as a finished one, twice;
  * `SUMMARY.txt` was quoted while its own `games/*.json` said otherwise — the live aggregator
    never re-ran, so the file claimed 21/25 and 0.0650 where the data held 25/25 and 0.0566;
  * `per_level` was summed as "actions spent" when it only records actions on levels that were
    CLEARED — a game burning 56,000 actions and clearing nothing contributes 0, which turned
    "our card CLEARED a level the old one never did" into "our card is 61% slower", the exact
    opposite.
  ⛔ Before a number becomes an argument, print the raw values for one case whose answer you
  already know. All three took one command to expose and each had already been written up.
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

## A fifth kind: two machines, two trees — "both dirty" is not "both the same dirty" (2026-08-27)

A game measured **0.7500 five times out of five** on the shared box and **1.0000 three times out of
three** on the laptop, same command, same agent, same `run_game`. Neither side was flaky: each was
deterministic to the step count. Two deterministic answers to the same question is not
nondeterminism — it is two different questions.

```
                              blastclock.py        ka59
laptop (= git HEAD)           d33922ec2452...      1.0000  (7/7, 3 of 3 runs)
ceph-build (tarball extract)  ef0dafdf96a2...      0.7500  (6/7, 5 of 5 runs)
```

**`~/admorphiq` on the box is a TARBALL EXTRACT, not a checkout.** It holds whatever the last sync
carried. An agent editing a tool after that sync leaves the box measuring code the repository no
longer has — and because the box is deterministic, it returns the same wrong number as often as you
ask, which reads as confirmation.

⛔ **The tell that should have prompted the hash check earlier**: the two sides disagreed on a
BINARY outcome while agreeing on everything else, and repeats on each side were byte-identical.
Repeating a measurement on ONE machine cannot detect this; it makes the wrong number more
convincing. **Hash the files, not the verdict.**

⚠️ **The trap has an inward-facing half that cost a false commit.** The gate synced at its START,
the tool changed on the laptop DURING the run, and the result was committed as "the measured tree".
It had never been measured. A guard that samples the tree once cannot see it move; `gate_tool.sh`
now hashes every tool before and after the run, refuses the verdict if any moved, **and refuses if
the box's bytes differ from the ones just sent**.

⛔ Until those hashes match, **no cross-machine number is quotable** — not a round's mean, not a
card, not a per-game score. This is cheap: one `shasum -a1` over `tools/*.py harness/*.py`.

### And the corollary about lessons themselves

This entry was nearly written as something else. On the strength of the same disagreement — cause
unknown — the parent instructed an agent to record *"letting the runner build the agent is not the
same as using the runner's loop"* as a new trap. The agent **declined**, on the grounds that the
evidence pointed the other way, then settled it by running `run_game` itself and getting 294 actions
against its own probe's 295. The loops agreed all along.

**A plausible lesson that the evidence does not support is exactly what this page warns against, and
it was nearly added to this page.** Refusing to write it — against an instruction — is the discipline
working. Write down what a claim was measured against, and if the answer is "a disagreement whose
cause we have not found", it is not a lesson yet.
