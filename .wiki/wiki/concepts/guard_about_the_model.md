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

## The sharpest instance: a tier gated on a condition that can never be false

Measured on lf52's level 6 by logging which TIER produced each plan:

```
tiers DURING level 6: {'win': 728}
```

The travel tier fired **not once in 728 planning decisions**. Every one was a claimed WIN: the
tool believed it was one plan from finishing the level, seven hundred and twenty-eight times,
played it, the level did not end, and believed it again.

Travel sat behind *"no capture is reachable"* — and on a PARTIAL map a local win is always
reachable, so the tier that would have gone looking was unreachable **by construction**. Two
rounds had been spent tuning a tier that was never running.

⛔ **A guard can be permanently satisfied by the SHAPE of what it observes, not only by a stale
model or a stale constant.** "No capture reachable" is a statement about the world and still
never becomes true, because the map it is evaluated over only ever contains what has been seen.
The tell is not the predicate's wording; it is that the branch behind it has never executed.
**Count how often each branch runs before tuning any of them.**

The fix used evidence already in the harness rather than new sensing: the harness resets a tool
on a level-up, so *still being alive after the winning plan was played out* IS the refutation —
a win that did not win is proof of pieces that cannot be seen. 728 planning decisions became 16.

## Detection heuristics

Not frame-based — this is about instrumenting our own code:

- **Count how often each branch RUNS, before tuning any branch.** A tier that never fires cannot
  be improved by improving it, and it looks identical to a tier that fires and does nothing.
- **Log why a guard fired, not that it fired.** On lf52 one run over level 6 gave `offscreen`
  377, `install` 42, everything else 0 — 90% of plan deaths were a single predicate, and the
  fix followed immediately. Counting reasons is cheap and it replaces a whole afternoon of
  hypotheses.
- **Ask what would make the condition false.** If the answer involves our own state rather than
  the board's, the guard is about the model.
- **Ask when the threshold was calibrated and against what.** If the thing it was compared
  against has moved, the number is measuring history.

## The counter also refutes YOUR OWN DESCRIPTION of the bug

The rule is usually stated as "count instead of guessing". It is stronger than that: the count
refutes the account you would have acted on, including the one you wrote after already
instrumenting once.

lf52, round five. The handover said *"travel refuses a target it has aimed at before"* — a
confident description of a real-looking bug. Breaking the `none` bucket down by reason:

```
travel:no-gain 510   probe:nowhere-new 510   plan:no-pair 510   approach:no-pair 503
plan:no-capture-reachable 33   approach:no-gain 7
travel:all-visited   0        <- the described cause, never once
```

The visited set had never blocked anything. The real causes were "the piece cannot get further
from where pieces have been" and "only ONE capturable piece is known at all". A whole round would
have gone into the visited set.

⚠️ **And then the fix the data DID support also failed** — twice, informatively. If a piece sits
at the frontier with no gain available, the obvious unlock is that a cart may only be driven onto
cells already known to be track, so a rail running off screen is a road the tool refuses. Making
the shell past known track drivable: travel 26 -> 4 plans, idle 509 -> 1075, elapsed +74%.
Tightening it to "only where the track actually RUNS" returned to parity and still cleared no
level. Both reverted. **A count tells you which branch to look at; it does not tell you the
branch is the reason the level is unsolved.**

## The inverse: a guard measuring the WORLD where it should measure the TOOL

Every instance above is a guard whose condition is about our model when it should be about the
world. The stall detector is the mirror image and it cost 401 actions of one game's score.

`UnifiedAgent` decides a tool has stalled when it stops reaching states it has not seen, keyed by
default on the raw frame — a fact about the BOARD. That is right while a tool is following a
plan. It is wrong the moment a tool has NO plan: it proposes nothing, the actions it declined are
filled by probes, those shuffle pieces into frames never seen before, novelty never runs out, and
a tool that has already bid **0.00** holds the level to the end of its allowance.

Measured on a board whose level asks for shapes that are not translations of anything present, so
no plan exists and none ever appears:

```
8 of 8 targets uncovered across 480 consecutive proposals, 463 of them EMPTY
held 200 actions, lost; held 201 more, lost; another tool then cleared it in 63
```

The fix belongs in the tool, because the harness cannot know what progress means for one:
`loop.py` already calls a `state_key` hook, so a tool can answer "the board" while it has a plan
and "no progress" when it does not.

### But "held while bidding 0.00" is not itself a cost — the ceiling is

The signature that cost re86 401 actions is easy to find once you know to look: count actions
where the acting tool's own `detect` returns 0.00. Swept across the eight games with headroom:

```
lf52  825 held at bid 0.00   (hop 664, railpeg 82)      dc22  275   (phase_grid 138, gantry 137)
g50t  142   ls20  87   s5i5  59   wa30  52   ka59  21
```

lf52 looks like the worst case by a wide margin. It is not a case at all: removing `hop` from the
registry leaves lf52 **byte-identical — 0.2727, the same five levels at the same per-level costs,
zero binned**. Those 664 actions are spent on a level that is never cleared under any
configuration, so they cost nothing anyone was going to be paid for.

⛔ **This is the same trap as counting binned actions**, where wa30 bins more than re86 and has
zero recoverable. A held-while-silent count and a binned-action count are both proxies; the only
number that decides is what the game would score if the waste were removed. Measure that — by
`attempt_probe`'s ceiling column, or by removing the tool and re-running — before naming anyone's
work as a cost.

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
