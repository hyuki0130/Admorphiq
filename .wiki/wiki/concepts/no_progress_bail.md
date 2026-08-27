---
type: concept
topic: harness
date: 2026-08-27
keywords: [no-progress, bail, budget, wall-clock, stall, calibration, r101]
---

# No-progress bail — stop a game that has stopped winning

> Fourteen of the twenty-five sample games spent most of their action budget AFTER their
> last level-up. Ending those games at a measured threshold cut total actions 63% and
> wall-clock 59% with all twenty-five scores byte-identical.

## Definition

A run ends when the actions elapsed since the last level-up exceed `no_progress`
(`src/admorphiq/harness/loop.py`, default **1200**). It is checked in `is_done` alongside
the WIN state and the overall give-up cap, and the counter is **game-scoped** — armed only
by a genuine level-up, never by `_reset_level`, which also runs on death. Arming it on death
would re-arm the budget forever on exactly the death-looping games it exists to stop.

## Why the threshold is 1200 and not a guess

Measured over the full 25 (`scripts/rounds/R101BASE`, `--agent unified` @4000): **the most
expensive level ANY game ever cleared cost 120 actions** — wa30's fifth. Every other clear
was cheaper; most were under 60. So 1200 is a **10x margin over the worst observed clear**,
and it could not have cost a single measured level. That is the same shape of argument as
the detection-dispatch bail, which took its ~40x margin from the slowest first clear among
the dispatched games.

A threshold picked without that measurement is a guess about how long a real clear takes,
and this metric punishes a lost deep level far more than it rewards saved time.

## Why not swap tools instead

Because swapping is measured harmful. `UnifiedAgent._better_alternative_exists` deliberately
keeps a stalled tool running when no non-failed tool bids higher: handing the board to a
weaker tool loses solid clears to churn, measured in the deployed sweep. When nothing better
exists, the choice is between burning the budget and stopping — not between two tools. This
concept is the "a tool with no plan must bid 0.0" rule applied one step later in the loop:
the tool has a plan, the plan has stopped working, and nothing else claims the board.

## Detection heuristics (frame-only)

None needed — it is a property of the run, not of the board: actions since the last
`levels_completed` increase. It never inspects frame content, so it cannot be tuned to a game.

## What it measured

```
                   before      after
total actions      57,885     21,382     -63%
total wall-clock    1,882s       774s     -59%
per-game scores    identical on all 25 (delta 0.0 everywhere)
ka59                 4,000      1,381     866s -> 252s
```

Fourteen games hit the bail. ka59 is the extreme: five levels cleared by action 173, then
3,800 actions on the sixth with nothing to show.

## Falsification

Wrong if a game at a larger budget clears a level more than 1200 actions after its previous
one — that clear would be cut. Re-measure the worst cleared-level cost whenever a tool lands
that plans over a much longer horizon, and raise the threshold to keep the 10x margin.

## Related

- [[action_budget]] — the games' OWN per-level caps, which end the game on overrun; this is
  our cap on ourselves, and the two are independent.
- [[../lessons/tool_selectivity_20260827]] — the same principle one step earlier: a tool
  with no plan must bid zero.
- [[../rounds/r101_tool-development]] — the round that measured it.
