---
type: concept
topic: harness
date: 2026-08-27
keywords: [guard, predicate, invalidation, stall, calibration, instrumentation, r101]
---

# A guard that tests our MODEL, not the world, is true forever

> Five instances in one day, in three different layers. Each one reads as obviously correct,
> each one holds a working plan hostage, and none of them is visible without instrumenting the
> guard's own firing.

## Definition

A guard is meant to answer a question about the WORLD: has the board settled, is this tool
making progress, is this adapter worth the budget. It becomes a defect when its condition is
actually a statement about **our model of the world**, or about a **calibration that has since
moved**. In both cases the guard can be satisfied permanently while the thing it protects
against is not happening at all.

## The five, so the shape is recognisable

**About the model.** All three found inside one tool on lf52, by instrumenting every
invalidation site rather than reasoning about them:

* *"the board has not settled"* was a set of statements about the model — the carts are
  conserved. A model merely WRONG about one cart makes it true forever, and the tool waited out
  the level holding a two-jump winning plan. Fixed by scoping it to the three frames after a
  DRIVE, since only a drive moves a cart.
* *"nothing has got better in 3 observations"* retired the tool mid-journey. Riding a cart
  between regions grows neither the known map nor the pair distance for a dozen actions, so the
  progress test expires while progress is being made. Fixed by counting "a piece stood somewhere
  no piece has stood" as progress.
* *"this frame reproduces a state I already left, so it is a lagging animation"* matched an
  EIGHT-deep history. On a level where the tool revisits states, a legitimately diverged frame
  matches an old state and is discarded permanently — the model was caught holding a green where
  the board had a red, uncorrected.

**About a stale calibration.** Both in the harness, both mine:

* the **dispatch bail** hands a board back only when an adapter has cleared NO level in 2000
  actions. Right when the fallback scored 0.0566; once the fallback reached 0.8224 the question
  it asks — "did the adapter clear anything" — stopped being the question that matters, and
  eleven of thirteen adapters became a net loss without any guard noticing
  ([[../lessons/adapters_now_cost_the_card_20260827]]).
* the **no-progress bail** counts ACTIONS since the last level-up, so it cannot see a game that
  is progressing at 1.45 seconds per action. That needed a second guard in wall-clock
  ([[no_progress_bail]]).

## Detection heuristics

Not frame-based — this is about instrumenting our own code:

- **Log why a guard fired, not that it fired.** On lf52 one run over level 6 gave `offscreen`
  377, `install` 42, everything else 0 — 90% of plan deaths were a single predicate, and the
  fix followed immediately. Counting reasons is cheap and it replaces a whole afternoon of
  hypotheses.
- **Ask what would make the condition false.** If the answer involves our own state rather than
  the board's, the guard is about the model.
- **Ask when the threshold was calibrated and against what.** If the thing it was compared
  against has moved, the number is measuring history.

## Falsification

Wrong as a general claim if a guard of this shape is found that cannot become permanently true —
e.g. one whose condition is refreshed from the frame every step and carries no memory. Those
exist and are fine; the pattern is specifically about conditions carrying state or a constant.

## Related

- [[swallowed_action]] — where the lf52 settling rules live, including the measured trap that
  acting on an unsettled frame costs four levels.
- [[no_progress_bail]] — a guard that was right in action-space and blind in wall-clock.
- [[../lessons/adapters_now_cost_the_card_20260827]] — the most expensive instance, 0.29 of card.
- [[../lessons/instrument_validity_20260825]] — the same discipline one level up: validate the
  instrument before the hypothesis.
