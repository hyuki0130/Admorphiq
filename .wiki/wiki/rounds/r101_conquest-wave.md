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

## ⛔ Three games CLOSED with proofs (2026-08-30) — do not re-open without NEW evidence

- **bp35 = 0.2456.** Its 87-action board decomposes with no slack in any attempt: 7 spike discovery
  (irreducible — nothing in the frame says which of the ten drawn kinds kills), 34 building 140 of
  the board's 370 map cells, 44 clearing in **43 against a human 48**. `_stranded` refuted (the run
  strands TWICE, body in the pocket for ONE turn); a pre-entry veto has nothing to key on (a dead end
  cannot be asserted over an incomplete map); the flat turns TRAVERSE and revisiting is
  ANTI-correlated with the score. ⚠️ The human clears in ONE attempt, so the gap is entirely "does
  not die to the spike, does not get walled in".
- **s5i5 = 0.5833, out of reach for `swivel` as built.** Thirty arms, five fans, all 0.5833. An
  engine A* with nothing banned wins in 45 clicks **opening by moving a rider that is already home** —
  a move `swivel`'s decomposition can never propose, because each subproblem gets only the controls
  touching its own bar. All 41 runs banning that control are EXHAUSTED. Banked instead: a margin
  bound worth **219s → 45s of wall clock**, score and all six per-level counts identical.
- **dc22 = 0.7143.** Crane fully decoded — 4 plates measured 1:1 over 69 presses, zero cross-talk,
  precondition frame-visible. ⛔ The blocker is OURS: `phase.py:430` condemns a tile if ANY pixel is a
  banned colour, and every plate sprite contains colour 0. Censused across the 25 it reaches ONE
  game; the proof is one cell, **(55,34) condemned at turn 582 and stood in at turn 680**.

## ⭐ Three findings that are not about their games

- **"Unobserved space is empty" is every frame-only planner's prior, and it is wrong** (rule 7ap).
  Fingerprint: plans found in seconds → executed cleanly for a dozen actions → REFUSED → nothing
  findable at any budget.
- **Asking a tool whether it recognises a board can SPEND ITS GIVE-UP BUDGET** (rule 7ah).
  `railpeg.detect` runs the planner and advances two counters whose threshold is three. 19 of 49
  tools have a `detect` that reaches a mutating line; the count is now pinned by a test.
- **A mechanism correctly described does not tell you which edit removes it** (rule 7am). The repair
  I specified for the above was built, validated in both directions, measured INERT, and reverted.

## Related

[[r101_wa30-level-restart]] · [[r101_bp35-attempts]] · [[r101_allowance-ledger]] ·
[[r101_silent-specialists]]
