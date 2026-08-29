---
round: R101CONQUEST
axis: generic tools, per-game parallel agents
keywords: [conquest, re86, wa30, gate, snapshot, transfer, selectivity, instrument-validity]
verdict: 0.8935 -> 0.9069, nineteen games at the cap, cumulative regressions zero
commit: 2efb7cfe
---

# R101 — the conquest wave, and nine instruments that lied

> Eight parallel per-game agents took the generic tools from 0.8935 to 0.9069 in a day, conquering
> re86 and wa30; the more durable output is the measurement discipline that survived it.

## What moved, all gated on the full 25

```
re86   0.9908 -> 1.0000   CONQUERED 8/8   cover_targets: head for the piece's own uncovered marks,
                                          read the seat cell on the first move, serve the piece
                                          already in the seat (the select control is a RING)
wa30   0.8000 -> 1.0000   CONQUERED 9/9   shepherd: see the level RESTART, and rank by the ROUTE
ls20   0.8442 -> 0.9121                   fogscout: refuel slack, then report the route's LENGTH
lp85   0.9099 -> 0.9677                   cyclepress: evidence before breadth
graph  ————— -> —————                     denied the harness's primary-owner latch (0.80 -> 0.69)
```

Nineteen of twenty-five games are at the 1.0 cap. Remaining: lf52 0.2727 · bp35 0.2220 ·
s5i5 0.5833 · dc22 0.7143 · lp85 0.9677 · ls20 0.9121.

## ⭐ The finding that generalises: a level that RESTARTS is invisible

wa30's last level was never short of moves — **it was short of ATTEMPTS.** Its `StepCounter` of 70
restarts the LEVEL rather than ending the game, so the harness gets eight tries, and SIX of them were
byte-identical replays: `propose` watched only `levels_completed`, which a restart does not move, and
carried a stale plan, a stale held-piece flag and a walker sweep straight across the reset.

The s5i5 agent found the same blindness independently within the hour — its allowance bar is RENDERED
on frame row 63 and REFILLS twice inside one 500-action window while the level number sits still.

⛔ Two corrections followed immediately, and both matter more than the original:
- **The MODEL-level version of the test is unsound on any board that scrolls** — lf52's detector fired
  on its own piece count rising and was measuring DISCOVERY, not restarts.
- **The RAW-FRAME opening hash cannot detect a restart either** — zero recurrences on a level that
  dies 58 times, because a death RESETs to level 0 so the level's opening can never recur while
  `levels_completed` still reads it. `obs.state == GAME_OVER` is the only reliable signal.

## Two transfer facts

- **The gains reach the submission path**: `--agent unified` 0.9069 and `--agent kaggle_unified`
  0.9069 over 25, none differing.
- **The tools do not overfit their version hash**: against `environment_files_archive/` — a different
  hash of 15 games, re-rendered with different sprite tags and coordinates — **twelve of fifteen are
  identical ACTION FOR ACTION on every level**. re86 differs by one action; s5i5's whole -0.0240 is
  level 4 going 39 -> 61. ⚠️ Weak evidence: a re-render is the same game, and the thirteen
  hand-written adapters passed this same test 7/7 while moving the hidden score by nothing.

## ⛔ Closed by measurement — do not reopen

- **`frame_2d` reading the settled layer.** The measurement was TRUE (layer 0 is stale at 100% of
  level transitions in all 21 games) and the one-line fix cost **0.8962 -> 0.6525, fourteen games**.
  The last layer is a frame caught mid-consequence, not a settled board.
- **The give-up budget.** `HARNESS_NOPROGRESS` 500 -> 3500 gives five stuck games ~7x the actions on
  their wall level and clears NOTHING. An uncleared level scores zero however long it runs, so this
  was pure upside if it worked.
- **The level-transition handover tax.** 0.36 inert actions per transition over 149 transitions;
  seventeen games at exactly zero.
- **Routing.** No handover was ever lost to a tie, and none can be — three ties all broke by
  REGISTRATION ORDER and `registry.py` puts every specialist ahead of `graph` (43rd of 48).
  41–43 of ~48 tools bid 0.00 at every decision point.
- **A margin trigger** ("re-decide when a non-incumbent outbids the incumbent") fires on 26 of 30
  g50t frames and 8 of 19 m0r0 frames — it would hand three CAPPED games to the general searcher.
- **lf52's stall position**, by forcing every legal move the tool's own successor function offers:
  six moves, the best opens ONE cell, all four drives open zero, and no boarding move EXISTS.

## ⚠️ Nine instruments lied, and the direction was always the same

Every one failed toward **"there is nothing here"** — the direction nobody double-checks because it
feels like diligence. A minimum-blob-size-4 filter hid a game's own rendered move oracle (its markers
are two-pixel blobs). A `!=` level test read a collapse to level 0 as a clear and survived three
commits. A staleness instrument took SIX versions, five of which scored its own KNOWN POSITIVE at
zero. A fill counter keyed on `_current is None` could not see 7 fills in 8. A restart census did not
break on WIN and reported a 1.0000 game with 143 GAME_OVERs. A control arm that forces nothing
printed its variable's initial value beside six real zeros. A box-load hook reported "IDLE" at load
65, then "OVERLOADED" at load 21 — a count of processes is not a count of work.

⛔ **Run every checker on input whose verdict you already know, in BOTH directions**, and prefer a
quantity that is what it measures (load, `GAME_OVER`) over a proxy that stands in for it.

## The gate itself was the contamination

`scripts/rounds/gate_tool.sh` syncs the SHARED `~/admorphiq`, so a gate shipped every agent's
work-in-progress and the tree moved under it — both of its own documented traps are that one cause.
`scripts/snapgate.sh` archives HEAD into a private directory on the box: two gates run at once, a
rider cannot ride, and the verdict names a commit. `ptest.sh` and `pfan.sh` followed.

⚠️ And a comparison with nothing to compare printed **"no game regressed"** over 25 missing games.
A guard that cannot see must SAY SO.

## Related

[[r101_wa30-level-restart]] · [[r101_bp35-attempts]] · [[r101_allowance-ledger]] ·
[[r101_silent-specialists]]
