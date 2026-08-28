---
type: lesson
topic: deployment
date: 2026-08-28
keywords: [submission, generic-tools, kaggle-wrapper, adapters, dispatch, doctrine, r101]
---

# The generic tools had no route to a notebook, and that is why 0.33 of card sat unshippable

> Six Kaggle wrappers existed. **None wrapped the generic tool harness.** So the axis rule 7a
> names — clear the sample games with `--agent unified` — could not be shipped at all, while the
> notebook went on shipping thirteen adapters that are now measurably WORSE on 23 of 25 games.

## Symptom

`notebooks/kaggle_submission.py` ships `KaggleDetectAgent` (detection dispatch over adapters).
Grepping it for `harness`, `UnifiedAgent` or `default_tools` returns **zero** matches. Measured on
ceph-build, @4000, same tree, full 25:

```
--agent kaggle_detect  (as SHIPPED: 13 adapters + generic fallback)   0.5335
--agent unified        (generic tools alone, zero adapters)           0.8874
```

## Root cause

The adapters were written when the generic fallback scored **0.0566**, and both routing guards were
calibrated against that. Neither can see that the fallback has since overtaken them. Nothing broke;
a constant stopped being true, which is the same decay
[[../concepts/guard_about_the_model]] records for guards generally.

The missing piece was purely mechanical: `src/admorphiq/kaggle_*_agent.py` covered BC, online-RL,
chained, world-model, detection dispatch and graph-frontier. The one thing the axis actually
develops had no wrapper.

## Prevention

`src/admorphiq/kaggle_unified_agent.py` now exists, and `--agent kaggle_unified` measures it.

⛔ **The wrapper MIRRORS `scripts/score_efficiency.py:_make_agent("unified")` line for line** —
same tools, same llm wiring, same `giveup`/`stall`/`ctx_budget`, and `no_progress` deliberately
NOT defaulted (it belongs to `UnifiedAgent`; duplicating it once created two homes and the wrong
one won). Diverging here is how a card drifts from its own scoreboard, and a hand-built agent that
omitted what the runner supplies has already cost this project a measurement — 0.0338 where the
real run gives 0.1648.

**Verified the wrapper changes nothing**: `lp85` 0.9099 and `ka59` 1.0000 under both
`--agent unified` and `--agent kaggle_unified`.

## Recovery

`bash scripts/kaggle_bench.sh {status|results|push}` is the whole Kaggle flow in one command —
slug, venv-only CLI path, and which files carry the numbers. ⛔ No `--submit` path by design.

## Falsification

Re-measure both agents on the full 25. If `kaggle_detect` ever exceeds `kaggle_unified`, the
adapters have stopped costing and this lesson needs revisiting per game — the one board that still
earned its adapter as of 2026-08-27 was `ls20`.

## What is NOT settled

**Whether the submission notebook switches** is submission-affecting and the user's call. And the
hidden score of the generic path is **UNMEASURED**: the only calibration point in existence is an
adapter card at public 0.2772 -> hidden 0.18, and that ratio describes how much of a PUBLIC-TUNED
card survives 110 unseen games — it is not evidence about a path that reads no game id, no title
and no sprite tag. ⛔ Do not quote 0.65 × the public number as a prediction.

## Related

- [[adapters_now_cost_the_card_20260827]] — the per-game table showing 23 of 25 worse.
- [[generic_transfer_20260827]] — transfer 0.9981 across re-rendered games (same game, new hash;
  weaker evidence than a different game).
- [[../rounds/r101_tool-development]] — the round.
