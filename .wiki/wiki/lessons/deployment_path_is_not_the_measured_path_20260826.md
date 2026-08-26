---
type: lesson
keywords: [deployment, submission, kaggle, measurement, setdefault, max-actions, dir-mode, invisible-locally, verification]
date: 2026-08-26
verdict: Five defects in one session lived in the deployment path and were INVISIBLE to every local score. The measured path and the shipped path differ by construction, and only exercising the shipped one finds them.
---

# The deployment path is not the measured path

> The benched configuration and the shipped one differ; a number measured on one is not a number about the other.

A local score can be perfect while the submission is broken, because the two do not run the same
code. Five defects in one session, none of which any local number could have revealed:

## 1. The dataset upload dropped the package

`--dir-mode`'s default is **skip** — it IGNORES directories. A version pushed without the flag
uploaded one text file and nothing else, and the kernel died on `ModuleNotFoundError`. `zip` is
correct: Kaggle extracts the archive and strips its top level, which the notebook's own path list
had recorded all along as `# CLI dataset (zip strips src/)`.

## 2. The framework directory was not synced

The deployed wrapper resolves `agents.agent.Agent` from `ARC-AGI-3-Agents/`. A sync carrying
`src scripts tests notebooks kaggle` produced `No module named 'agents'` and **0.0000 on all 25
games** — which reads exactly like a broken card and is not one.

## 3. `setdefault` respects what the runner exported

The wrapper sets `os.environ.setdefault("GF_GIVEUP", "8000")`. The measurement runner exports
`GF_GIVEUP=100000`, so the "shipped" measurement ran a budget twelve times larger. ⛔ The
benched-vs-shipped comparison could not catch it: **both sides inherited the same export, and a
comparison is only as good as the axis it varies.**

## 4. A per-game budget that might have been a run total

Cutting `MAX_ACTIONS` from 100,000 to 4,000 is safe only because the notebook constructs a FRESH
agent per game and `action_counter` is an instance field. Had it accumulated, 4,000 would have
ended the whole submission after the first game or two — and `score_efficiency.py` drives the agent
through its own loop, so no local run would ever have shown it.

## 5. The deployed cap was never executed

Two capping mechanisms exist and only one ships: locally `--max-actions` ends the runner's loop,
while the submission caps inside `KaggleDetectAgent.is_done`. `--agent kaggle_detect` builds
`build_detect()`, which returns the DISPATCHER — the wrapper carrying `MAX_ACTIONS` is never
constructed locally. The budget change was verified against a mechanism that does not ship, until
the deployed path was executed directly (False at 3,999, True at 4,000).

## 6. Nothing bounded the WHOLE RUN, only each game

`MAX_ACTIONS` limits one game. The competition limits the entire submission to **9 hours**, and
no code or check connected the two. The submitted card carries `MAX_ACTIONS = 100,000`:

```
rate measured on our own server run:  51 actions/sec
110 hidden games x 100,000 actions =  11,000,000 -> 59.9 hours
110 hidden games x   4,000 actions =     440,000 ->  2.4 hours
```

The budget was cut to 4,000 for a different reason entirely — "identical score, sixteen times
faster" — AFTER the submission was sent. ⛔ So the card in flight never had that protection, and
the risk assessment written at the time ("the 9-hour limit stops being a risk") was about a card
that had not been submitted.

⚠️ **The 9-hour figure is itself now IN DOUBT.** Submission `55774529` — a CPU kernel
(`enable_gpu: false`) — passed nine hours still PENDING. CLAUDE.md records *"≤ 9 hours (CPU or
GPU notebook)"* from the 2026-06-25 overview, so either that does not apply to CPU kernels, or
the scoring re-run is bounded differently, or a failure had not yet surfaced in the status. ⛔ No
way to measure which from here: Kaggle withholds logs during a run and the rules page is not
reachable offline. The guard's SHAPE holds either way; the CONSTANT is unverified and marked so.

This one is worse than the other five. They break the run in ways that show up as an error; this
one lets a perfectly good agent be killed by the clock, scoring **zero on everything**, while
every card measurement in the repository still reads 0.2772.

## What they have in common

Each is a place where **the measured configuration and the shipped one diverge**, and each was
invisible precisely because the local number stayed correct. A card measured at 0.2772 tells you
nothing about whether the submission imports, whether it stops, or whether it stops at the right
place.

## The rules

1. **Push the KERNEL alone before submitting.** Every build defect above surfaced at zero cost,
   without consuming a daily submission slot. Three separate pushes were needed to get a run.
2. **Name the axis a comparison varies.** "Benched equals shipped" is meaningless if both sides
   inherit the same override; the check must differ in exactly the thing it claims to test.
3. **Execute the deployed path, not an equivalent one.** If the shipping code has a branch no
   local run constructs, it is unverified no matter how many games were scored.
4. **When a deployment reads 0.0000 everywhere, suspect the environment before the card.** Two of
   the five presented that way, and neither was a scoring problem.
5. **Bound what the PLATFORM bounds.** A per-game cap is not a run-time budget. Multiply it by the
   evaluation set size at the measured action rate and check it against the platform's own limit —
   `tests/test_adapter_detection.py` now does, and it rejects the budget that was actually
   submitted.

Related: [[submission_build_defects_20260826]], [[instrument_validity_20260825]],
[[submission_not_reproducible_20260825]], [[../rounds/r99_detection-dispatch]].
