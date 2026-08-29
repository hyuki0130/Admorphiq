---
type: lesson
topic: harness-routing
date: 2026-08-30
keywords: [handover, selectivity, redecide, feedback, empty-propose, bid-decay, r101, r101select]
round: R101SELECT
commit: 2081eda0
---

# The harness asks the tools exactly once per handover, and its own log names the wrong reason

> Two instrument facts about `UnifiedAgent`, both of which make a reader conclude something the
> code does not do.

## Symptom

Measured over nine games at the re-decide point (`scripts/rounds/R101SELECT`; the run reproduces
the R101WA30 gate baseline to the action, so the instrument is not perturbing what it reads).

**(a) A tool whose confidence peaks BETWEEN decisions is never asked.** The loop evaluates every
tool's `detect` only inside `_redecide`. Sampling every tenth action instead shows bids the router
never sees: `socketmerge` reaches **0.95** on an lf52 frame and is at no decision point; `hop` bids
0.88 on lf52's first frame and 0.00 at both later handovers; `telescope` bids 0.95 on s5i5's first
frame and 0.00 at the only handover. On lf52's wall level, **28 of 50 sampled frames** have some
non-incumbent outbidding the incumbent.

**(b) The harness's stderr feedback line is not the retirement reason.** At s5i5's handover it
printed `feedback='action no new state x3'`, which reads as a stall. The retirement was the EMPTY
counter — `propose` returned `[]` for `_EMPTY_TOLERANCE` (8) consecutive calls. `self._feedback` is
simply the last message any code path assigned; it is a narration string, not a cause. Across all
nine games **every single retirement went through the empty path**: zero stalls, zero death-clock.

## Root cause

(a) is a deliberate cost control — `detect` over ~48 tools is not free per action — but its
consequence is unstated: routing sees a sample of size one per handover, so a mechanic that only
becomes legible part-way into a level is invisible. (b) is a diagnostic string reused as an
explanation.

## Prevention

⛔ **Do not read a retirement reason off `[harness] ... feedback=...`.** Instrument the site that
nulls `_current`: `_fill_from_current` (empty tolerance), `_ledger_observe` (death clock),
`_write_code` (block budget), or a non-None incumbent entering `_redecide` (stall). Anything
concluded from the feedback string is unsupported.

## Recovery

`scripts/_select_handover.py` (reason + all bids at each handover) and
`scripts/_select_overtake.py` (bids every tenth action, so decay and between-decision peaks are
visible). Both subclass `UnifiedAgent`; ⛔ `loop.py` is shared by every concurrent agent and is not
edited for instrumentation.

## Falsification

⛔ "Someone outbids the incumbent" is NOT a defect, and the controls prove it. The same sweep finds
`clonewalk` (0.75) outbid by `graph` (0.80) in 26 of 30 frames on **g50t, which scores 1.0000**, and
`decouple` falling to 0.00 mid-play on **m0r0, which scores 1.0000**. A re-decide triggered on a bid
margin would take both perfect games away from the tools that win them. The between-decision peak is
a real limit of the architecture; it is not a licence for a margin trigger.

⚠️ One honesty note on the instrument itself: the every-tenth-action sweep changed lf52's action
count from 823 to 827 while leaving its score identical, so at least one tool's `detect` is not
side-effect-free. The handover probe, which samples only at decisions, is exact on all nine.

## Related

- [[detect_is_not_a_plan_claim_20260830]] — what the bids at those frames turned out to mean
- [[detect_must_not_spend_the_tool_20260830]] — the tool the side-effect note above names, found by bisecting one arm per tool: `railpeg`, and `detect` spends its give-up budget
