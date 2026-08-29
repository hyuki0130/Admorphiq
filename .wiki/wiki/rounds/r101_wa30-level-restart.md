---
round: R101WA30
axis: generic tools — shepherd (haulage/relay family)
keywords: [wa30, shepherd, level restart, action allowance, retry, mover reachability, route not straight line, haul]
verdict: CONQUERED — wa30 0.8000 -> 1.0000 (9/9), levels 1-8 unchanged to the action
commit: see scripts/rounds/R101WA30/COMMIT
---

# wa30 — the last level was never a planning problem, it was eight attempts spent as one

## What was wrong

wa30 scored **0.8000** with eight of nine levels at a perfect 1.0 and every one of them faster than
the human. `(1+2+…+8)/(1+2+…+9) = 36/45 = 0.8`, so the entire gap was level 9 and nothing else.

Level 9 declares `StepCounter: 70` in its own level data
(`environment_files/wa30/ee6fef47/wa30.py`), and on overrun `Wa30.step` calls `lose()`, which
**restarts the level** — it does not end the game. Measured through the real harness: the game
reaches level 9 at action 584 and gets **eight attempts** at it inside a 1091-action run.

    attempt 1     8 of 9 pieces banked, by action 63, SEVEN actions to spare
    attempts 2-7  7 of 9, and byte-identical to each other, action for action
    attempt 8     cut short by the run's own budget

Six of the eight attempts were the same attempt. `propose` watched only `levels_completed`, and a
restart does not move it, so the tool carried a plan for a board that no longer existed, a flag
saying a piece was in hand, and a walker sweep straddling the reset. Attempt 1 was better only
because it inherited different bookkeeping from level 8.

## The two rules, and that both are needed

1. **`_reborn` — a restart is a TELEPORT together with pieces reappearing loose.** Frame-only and
   game-agnostic. The carrier moves at most one cell per action, so a jump is not something play
   produces; a thief takes at most one piece back out of a bay per turn, so two pieces reappearing
   outside the bays in one action is not something the field produces either. ⛔ Neither half alone
   is safe — the reader loses the carrier on the frame's outermost ring, which reads as a jump, and
   a two-thief board can return two pieces at once. What is cleared is everything positional; what
   the GAME taught (which colour walks, which kind the latch removes, which moves the furniture
   refuses) is as true on the retry as on the attempt.
2. **`_start_haul` ranks by the ROUTE to a helper, not the straight line.** The rule `_police`
   already stated for a thief — *judge the threat by the route, not by the picture* — and that
   `_start_haul` did not state for a mover. Level 9's second helper is sealed above a hazard band
   and **moves zero cells in seventy actions**; a straight line puts it four cells from a piece it
   can never reach, so all three pieces on that side ranked as already-taken-care-of and the
   carrier walked away from the only pieces nothing else would ever collect.

⛔ **Measured separately and neither is sufficient** (whole game, real harness, five variants):

| variant | level 9 |
| --- | --- |
| shipped | 8, 7, 7, 7, 7, 7, 7 |
| restart-aware alone | 8, 7, 7, 7, 7, 7, 7 |
| route-distance alone | 8, 7, 7, 7, 7, 7, 7 |
| **both** | **8, then CLEARED on attempt 2** |

Official scorer, private snapshot: **`total_score 1.0`, 9 of 9 levels, 720 actions**, per level
27/58/77/67/120/46/55/134/136 against human 71/119/183/98/368/68/79/442/415 — level 9 in 136 where
the human took 415, and levels 1-8 unchanged **to the action**.

## What the second attempt does differently

After `_reborn` the walker sweep is thrown away, so the first haul of the retry sees no movers at
all and every piece is adrift — which ties, and the tie breaks on the cheapest plan. That opens on
the right-hand cluster (cost 9, then 6, then 15) instead of resuming the first attempt's endgame.
By the third haul the sweep has repopulated and the route distance keeps the ranking honest
(right-hand pieces 11 and 14, left-hand 5 and 7). Under the straight line the carrier turns left
at exactly that point and competes with the one working helper.

## Measured negatives — do not re-try these

* ⛔ **Varying the retries makes it worse.** Shifting the opening choice by the attempt number so
  the eight tries differ scored 8,8,6,4,4,4,4 where the pair alone clears. The retries were not
  failing because they were identical; they were failing because each was the first attempt's
  endgame replayed.
* ⛔ **Learning the allowance from the first death and declining a haul too long to finish is
  inert.** It fires (ten refusals in a run, `allowance_learnt: 69`) and changes the outcome by
  nothing. Not in the code.
* ⚠️ The earlier round's searches — five ranking rules, eight weightings of the mover bias, four
  drop-cell rules, five bay-choice rules, five hand-off caps, 300 randomised target orders, four
  beam searches over whole deliveries using EXACT engine state — all searched **inside one
  attempt**, which is why none of them found this.

## Blast radius

`scripts/_wa30_who.py` reports the acting tool for all 25 games: **`shepherd` acts on wa30 and on
nothing else** (wa30 1091 of 1092 actions; it appears in no other game's histogram). `detect` is
untouched, and `_reborn`/`_start_haul` run only inside `propose`, which only the acting tool is
given. The change cannot reach the other 24 through this tool.

## Two instrument failures paid for on the way

* ⛔ **Five variants returned byte-identical numbers**, which is what an inert branch looks like —
  the restart detector was capturing "the opening" one action late, because `propose` skips its own
  bookkeeping on the frame that reports a level change. Then a patch script deleted the whole
  `propose` override while replacing the method above it, and the *next* five came back identical
  for a different reason. Both were caught only by instrumenting that the branch FIRES
  (`propose_calls`, `restarts_seen`), never by the outcome.
* ⛔ **A private snapshot run with `~/admorphiq/.venv/bin/python` and no `PYTHONPATH` imports the
  SHARED tree's `admorphiq`.** `scripts/score_efficiency.py` and any probe doing
  `sys.path.insert(0, "src")` select the snapshot; bare `pytest` does not.

## Existence was never in doubt

`scripts/rounds/R101WA30/WITNESS.txt` holds a verified 70-action clear of level 9 found by a
schedule search over the real engine, replayed outside the search that found it, plus 66- and
69-action variants in `schedule_search.jsonl`. Those used engine internals as an oracle and are
proof-of-possibility only — not shippable, and not how the tool gets there.

Related: [[.wiki/wiki/sample_games_mechanics]], [[.wiki/wiki/rounds/r101_silent-specialists]]
