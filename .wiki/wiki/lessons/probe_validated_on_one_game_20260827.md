---
type: lesson
topic: measurement-integrity
date: 2026-08-27
keywords: [probe-validity, run-game, stepping-loop, frames-argument, game-over-revive, fingerprint, false-confirmation, measurement-discipline]
---

# A probe validated on one game reads as sound

> Two divergences from `run_game` lived in a hand-written loop that had twice been checked and
> twice believed faithful: they changed NOTHING on six of seven games and changed the seventh's
> score by 0.16 — so every check that happened to pick one of the six returned "agrees".

## Symptom

A probe drives a game to count what a real run does. Its scores match `score_efficiency.run_game`
on game after game, so it is treated as faithful. Then one game disagrees, and the disagreement is
read as a finding about that game — nondeterminism, a stale tree, a tool regression — because the
instrument has already been validated.

Measured shape, one probe against the runner on seven games:

```
game   runner actions / score      probe steps     agrees?
g50t      296 / 1.0000                 297          yes
ka59      294 / 1.0000                 295          yes
dc22      925 / 0.7143                 926          yes
ls20      920 / 0.7500                 921          yes
wa30     1091 / 0.8000                1092          yes
lf52      819 / 0.2727                 820          yes
s5i5      694 / 0.5833                 926          NO
```

Six agree to within one step. The seventh differs by 232 actions and 0.16 of score, and its
per-level costs differ by a factor of eight on one level — a claim was published off that row and
had to be withdrawn.

## Root Cause

Two independent defects, neither reachable on most games:

1. **The per-level counter was incremented after the level-transition check.** `run_game`
   increments first, so the action that CAUSES a level-up is charged to the level it completed.
   Incrementing after a `continue` drops exactly one action per level — a uniform `-1` against the
   runner on all six of ka59's levels. It flatters every efficiency ratio, and efficiency is the
   quantity the metric squares.
2. **The loop did not revive the env on GAME_OVER.** `run_game` does `env.step(GameAction.RESET)`
   and keeps counting, because `UnifiedAgent.restart_on_game_over` is True. A loop that stops
   there measures a different game — and only on games that die.

Both are invisible unless a game dies or its per-level costs are read closely. That is the whole
danger: **the divergence is silent, so the validation is silent too.**

⛔ This is the INVERSE of the trap already recorded in
[[instrument_validity_20260825]]: *using the runner is not the same as letting the runner build the
agent*. Here the agent WAS built by the runner's own `_make_agent`, and the loop around it was
hand-written. Both halves have to come from the runner.

⚠️ **And a wrong cause was published before the right one.** The first diagnosis blamed the
`frames` argument — the probe passed an accumulating list where `run_game` passes `[]`. That was a
real difference, it was changed, s5i5's trajectory changed, and the causal claim was made on that
single coincidence. It was wrong; `UnifiedAgent` never reads the parameter. One variable was
changed, one difference was observed, and the wrong name was attached to it.

## Prevention

- **Copy the loop; do not re-derive it.** The probe's stepping loop should be a literal copy of
  `run_game`'s with instrumentation added and nothing else changed. Re-deriving "the same" loop
  failed twice in one afternoon, each time after a check that returned agreement.
- **Validate on a game that DIES.** `bp35` dies 11 times on its sixth level; `lf52` dies on its
  level 6; `ls20` on its level 7. A probe that agrees on a game with no deaths has not been tested
  against the revive path at all.
- **Compare per-level counts, not totals.** A uniform off-by-one is invisible in a total and
  obvious in a per-level list.
- **Check that the instrument does not perturb what it measures.** Run once with every engine read
  disabled and compare. Here it did not perturb — but that was measured, not assumed.

## Recovery

Re-derive every number the probe produced, and say which half survives. Numbers that depend on how
a run ENDS (levels cleared, score, per-level actions) are void until re-measured. Numbers taken
per-action from the engine — a hit-test under each click, an object-state delta — do not depend on
the loop's stopping rule and survive. Separating the two salvaged the useful half of seven rows.

## Falsification

This lesson is wrong if a hand-written loop can be shown faithful by construction rather than by
agreement — for instance if `run_game`'s loop is factored into a callable that a probe can drive
with a per-step callback. Then copying is unnecessary and the rule reduces to "call the shared
loop". Until that exists, agreement on N games is not evidence, and the correct N is unknown.

## A second instance, on the fix itself

`scripts/measure_frozen.sh` was written the same evening to stop the tree moving under a
measurement: it copies `src/` and prints a tools+harness fingerprint BEFORE the run. Two runs of
it, minutes apart, on one machine:

```
[frozen] fingerprint 0684c6da8458   HEAD ecaa384d   ka59  7/7  1.0000  290 actions
[frozen] fingerprint 2e71f56f8a24   HEAD ecaa384d   ka59  7/7  1.0000  290 actions
```

**Different fingerprints, same result.** Other agents' uncommitted edits landed between them. The
agreement is real and means nothing about the code, because the two runs measured different code —
a false confirmation that repetition cannot catch, since repeating is exactly what produces it.
The fingerprint is what makes the two lines distinguishable at all; without it they read as one
number confirmed twice.

⚠️ Note what this does NOT say. Determinism within a machine is not reproducibility — see
[[wall_clock_budget_20260827]] for a tool whose search budget is wall-clock, which makes each
machine internally stable and the two machines permanently disagree.

## Related

- [[instrument_validity_20260825]] — the parent page; this is its inverse case
- [[wall_clock_budget_20260827]] — why identical code still disagrees across machines
- [[../concepts/guard_about_the_model]] — a guard whose evidence does not survive the absence
  it detects
