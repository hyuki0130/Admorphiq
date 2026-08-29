---
type: lesson
topic: harness-routing
date: 2026-08-30
keywords: [detect, purity, side-effect, railpeg, pegjump, patience, give-up, instrument, r101, r101select]
round: R101SELECT
commit: 7e53372f
---

# Asking a tool whether it recognises a board spends that tool's give-up budget

> `detect` is a question. One tool answers by moving — and what it moves is the counter that
> decides when it hands the board over.

## Symptom

An instrument that called every tool's `detect` every tenth action changed the run it was
measuring: lf52 went from **823 actions to 827**, score identical. Bisected one tool per arm over
the whole registry, with both controls exact (sample nothing -> 823, sample all -> 827), the whole
+4 belongs to **one tool, `railpeg`** — which is lf52's own incumbent for its first five levels.

## Root cause

`RailPegTool.detect` is four lines and two of them mutate. `:1482` advances a high-water mark, and
`:1485` **runs the planner**: `_ensure_plan` returns early only when a plan already exists
(`:1312`), so when the plan is empty — exactly when the tool has just spent it — an extra `detect`
builds and stores a plan against a frame the tool was never asked to act on, and on the way it does
`:1343 self._sincecapture += 1` and `:1402 self._barren += 1`. Both are three-unit counters:
`_sincecapture` gates `stuck` at `:1334` against `_LOCAL_PATIENCE = 3`, and `_barren >= 3` at
`:1370` is the tool's own give-up.

So a question consumes a third of the patience that decides when the tool stops proposing. On lf52
level 5 `railpeg` retires through the EMPTY path, and that is the budget being spent to ask it.

⭐ **The defect is a known one, half-fixed, in the same file by the same author.** The other thing
`detect` calls, `_sync`, already carries an explicit idempotence guard at `:1073` whose comment is
this lesson: *"the harness asks `detect` and then `propose` about the SAME board, and this method
LEARNS — running it twice makes a frame look as if it had settled … and installs a stale board over
a correct model."* `_ensure_plan` was left unguarded.

## Prevention

`socketmerge` is the pattern worth copying and it is already in the tree: its `detect` saves the
state tuple, mutates freely while reading, and restores it in a `finally` — pure by construction
rather than by luck. `scripts/detect_purity_scan.sh` lists every tool whose `detect` reaches a
mutating line (grep-only, no engine): **19 of 49** do.

⚠️ Most of those 19 score a clean 823 on lf52 only because they early-return on a board that is not
theirs. ⛔ The eval is 110 boards nobody has seen and the tool set is the same one, so "clean on
lf52" is not "pure" — a tool that early-returns here can reach its mutating path there.

## Recovery

`scripts/_select_detectfx.py` — one arm per tool, plus a negative control that must return the
baseline and a positive control that must reproduce the perturbation. ⛔ Without both controls an
all-clean fan is indistinguishable from a fan that measured nothing.

## Falsification

⛔ **This does not license making `detect` read-only** (rule 7o). `detect`-then-`propose` on the
same board is the harness's NORMAL call pattern, so `_ensure_plan` running inside `detect` and being
reused by `propose` may be load-bearing for the tool's efficiency — the plan is deliberately built
one call early. A naive purity fix could cost a plan per action. Only a full-25 gate can decide it,
and the tool belongs to whoever owns its game.

The narrow claim that IS established: an instrument that samples `detect` more often than the
harness does is measuring a run it perturbed, and it will not look wrong.

## Related

- [[handover_frame_is_the_only_question_20260830]] — the sampling instrument that exposed this
- [[detect_is_not_a_plan_claim_20260830]] — the other way one number is asked two questions
