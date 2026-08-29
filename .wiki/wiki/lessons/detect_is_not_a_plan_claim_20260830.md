---
type: lesson
topic: harness-routing
date: 2026-08-30
keywords: [detect, selectivity, handover, primary-owner, graph, crag, bid, r101, r101select]
round: R101SELECT
commit: 2081eda0
---

# A `detect` score answers "is my mechanic here", but the harness reads it as "I have a plan"

> One number is asked two questions, and the two disagree at exactly the moment that matters —
> the frame where a specialist's planner has given up.

## Symptom

Measured at the harness's own re-decide point over four stuck and five control games
(`scripts/rounds/R101SELECT`, instrument reproduces the R101WA30 gate baseline to the action):

- **`crag` still bids 0.50 on the very frame its `propose` returns `[]`** for the eighth
  consecutive call and it is retired — the identical bid it gave on frame 0 of the game.
- **`graph` bids 0.80 on the wall boards it cannot clear.** `_PRIMARY_CONF` in
  `src/admorphiq/harness/loop.py` is 0.70, so 0.80 latched `_primary_owns` and the stall path could
  no longer retire it: it held bp35 for **486 actions** and lf52 for **366**, clearing nothing. Its
  own frame-0 bid on those same boards is 0.45.

## Root cause

`CragTool.detect` is a board-SHAPE test — the control scheme plus "readings exist" — and never
consults whether the planner has a move. `GraphSearchTool.detect` returned 0.80 as soon as any
observed transition changed a small localized region, which is the signature of *an avatar exists*,
not of *this board is solvable by me*. Both are honest answers to "is my mechanic present". Neither
is an answer to the question the harness actually asks, which is "should you be given this board".

The repository already states the rule — **a tool with no plan must bid 0.0** — and three
violations of it were found in one earlier round, the last of which took a game from 0.58 to 1.00
when removed. These are two more live violations. They cost nothing on the measured boards only
because something else outbids them.

## Prevention

A bid is a claim to have a plan. Where a tool distinguishes "my mechanic is present" from "I can
act on this board", the second is what `detect` must return; a tool that has exhausted its ideas on
a level should fall to 0.0 there, as `railpeg` and `swivel` correctly do. Where a tool cannot tell,
its bid must stay below `_PRIMARY_CONF` so the harness can still take the board away.

⛔ And the threshold lives in a DIFFERENT FILE from the bid, which is the two-homes shape that
silently overrode the no-progress bail. `tests/test_graph_ownership.py` pins the pair and fails if
either moves.

## Recovery

`scripts/_select_handover.py` prints every tool's bid at every re-decide frame with the retirement
reason beside it, so a `detect` that stays high while `propose` goes empty is visible in one run of
nine games. Sub-class the agent; do not edit `loop.py` — it is shared.

## Falsification

The claim is that these bids overstate plan availability, NOT that lowering them raises the score.
⛔ Rule 7o: a measurement of a mechanism does not license a change of behaviour. Only a full-25 gate
against `scripts/rounds/R101WA30` (0.9069) can say whether denying `graph` ownership helps — and the
same round measured the reason to doubt it, in [[handover_frame_is_the_only_question_20260830]]: on
g50t, which scores 1.0000, `graph` at 0.80 outbids the winning specialist `clonewalk` at 0.75 in 26
of 30 sampled frames. A rule that "the higher bid should hold the board" would take a perfect game
away from the tool that solves it.

## Related

- [[handover_frame_is_the_only_question_20260830]] — the other half of the same round
- [[generic_transfer_20260827]] — why a mechanic-keyed bid is the property worth protecting
