---
type: round
round: R101SILENT
axis: generic-tools
keywords: [silent tool, empty propose, retirement, revival, patience, alignment threshold, search cap]
verdict: five axes closed by measurement; score unchanged at 0.8935
---

# R101SILENT — why the last eight games stop, and five explanations that are not it

> Every stuck game retires its specialist because the tool proposes NOTHING, and five separate
> cheap explanations for that silence have now been measured and refuted.

## The finding

At the level that stops each game, the specialist is retired through the EMPTY path — it returns no
steps at all — and the general searcher inherits the board for the remaining ~500 actions.

```
bp35   crag       s5i5  swivel      dc22  gantry, phase_grid      lf52  railpeg
```

Their MODELS are correct, checked line by line against each game's own win predicate: swivel
optimises s5i5's cover-every-target, gantry routes to dc22's goal cell, crag's gravity/settle/gem/
spike/reversal model agrees with bp35's `fsvnqdbzrp` despite being recovered from frames alone, and
railpeg plays exactly the peg-solitaire protocol that clears lf52's first five levels.

## Five explanations, all measured, all refuted

| explanation | test | result |
|---|---|---|
| not enough patience | `HARNESS_NOPROGRESS=3000`, 6x | seven games, all identical to four decimals |
| the specialist is swapped out too early | `HARNESS_STALL=4000` | identical — **and a marker proved the knob never kept the specialist at all** |
| crag's window-alignment threshold is too strict | `_ALIGN_FIT` 0.82 -> 0.50, accepting every rejected window | bp35 unchanged at 0.2220 |
| swivel's search cap is binding | `_MAX_OPEN` 120k -> 4M | ONE GAME does not finish in forty minutes; the whole 25 normally takes fifteen |
| the silence is the instance's own history | give each tool one revival per level (reset instead of retire) | REVIVE fired, bp35 unchanged at 0.2220 |

The revival test was the most promising and the most instructive. A FRESH instance of crag bids
**0.50 and proposes a step** on the very board its live instance went silent on — so the board is
not structurally beyond it. Given that fresh start in the harness, it explores, fails to place its
window again, and re-mutes. The bid was real; the progress was not.

## What this round changed

Nothing in the tree. Two candidate changes were built, measured and reverted (a harness probe-order
memory, gated on the full 25 at 0.8935 -> 0.8935; and this revival). The score is 0.8935, seventeen
games at the cap, cumulative regressions zero.

⛔ **The instrument check earned its place five times.** `HARNESS_STALL` would have been written up
as evidence that patience is not the answer, when it never applied the treatment. Every claim here
that an intervention did nothing is backed by a marker showing the intervention happened.

## Related

[[lessons/instrument_validity_20260825]] · [[rounds/r101_probe-fallback]]
