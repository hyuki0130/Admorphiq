---
type: concept
topic: measurement-integrity
date: 2026-08-28
keywords: [portability, cross-machine, reproducibility, card, kaggle, r101]
---

# The card must score the same on two machines before it can predict a third

> Measured 2026-08-28: all 25 games score **identically** on ceph-build and on the laptop —
> mean 0.8867, zero games differing. That property was FALSE the day before, and one tool was
> the whole of it.

## Why it matters more than the number

The card is measured on ceph-build; the competition runs on Kaggle hardware. A tool whose result
depends on the machine produces a third number there, and nothing in the repository says why. So
portability is not hygiene — it is the precondition for the card meaning anything about the
leaderboard. Clearing all 25 sample games with a machine-dependent tool set would not transfer.

## The measurement

Same frozen snapshot, run through the snapshot's own runner on both machines:

```
ceph-build (64 cores, PAR=20)   mean 0.8867 over 25
laptop     (PAR=3)              mean 0.8867 over 25
games differing:                0
```

The day before, `ka59` scored 1.0000 on one and 0.7500 on the other from the same committed file.
The fix — an uncommitted `blastclock` that had been reported as a regression — closed it: 290
actions and 7/7 on both. See [[../rounds/r101_tool-development]] and
[[../lessons/wall_clock_budget_20260827]] (whose original causal claim is withdrawn there).

## How to check it

```
bash scripts/measure_frozen.sh --agent unified --titles <game> --max-actions 4000
```
on each machine, then compare per game rather than by mean — **a mean can match while two games
cancel.** The check above compares all 25 individually for that reason.

⛔ Before attributing any difference to the machine, hash the code on both sides with
`LC_ALL=C sort` (locale ordering has already buried a one-file difference under dozens of
artefacts) and prove the instrument is attached.

## A second thing the run exposed

Both machines log `[harness] target draw failed: HTTP Error 404` — the LLM-backed goal tool is
reaching a model endpoint that answers 404, so it silently falls back. The laptop has ollama
running and ceph has none, and **the scores are identical to the digit**, which means every number
on this page is the LLM-free path. That matches the standing note that the LLM path's 25-game
performance is unmeasured; it is not evidence about that path either way.

## Related

- [[../lessons/instrument_validity_20260825]] — attach the instrument before reading it.
- [[../rounds/r101_tool-development]] — the round.
