---
type: lesson
topic: transfer
date: 2026-08-27
keywords: [transfer, version-hash, re-render, generic-tools, adapters, r101, r99]
---

# The generic tools hold 91% of their score on a re-rendered board

> Twelve of fourteen re-rendered games score IDENTICALLY — not close, identical. This is the
> first transfer evidence the generic path has, and it is the property the adapter card was
> measured NOT to have.

## Symptom / what was measured

`scripts/rounds/R101XFER` runs `--agent unified` (generic tools alone, zero adapters) against
`environment_files_archive/` — fifteen games whose version hash the ARC Prize API rotated.
Fourteen carry a genuinely different hash; sk48's archive hash equals its live hash and is
kept in the run as a **control**, which must reproduce its live score exactly. It does
(1.0000 both), so the instrument is sound before any conclusion is drawn from the rest.

```
14 re-rendered games   live mean 0.6980    archive mean 0.6365    ratio 0.91
12 of 14 identical     ar25 cn04 dc22 ka59 m0r0 r11l re86 sc25 sp80 su15 tn36 vc33
2 losses               tu93 1.0000 -> 0.2222 (9/9 -> 4/9)
                       s5i5 0.0833 -> 0.0000 (2/8 -> 0/8)
14 of 15 still clear at least one level
```

## Root cause of the contrast with the adapters

A hash rotation re-renders the same game: sprites, colour indices and level layouts move,
mechanics do not. A solver that keys on **the mechanic** is untouched; a solver that keys on
**this rendering of it** dies. That is precisely the split the 2026-04-21 rotation exposed,
when every brittle attribute-reader silently dropped to zero
([[api_hash_rotation_20260421]]).

⛔ **This is still the WEAK form of transfer** and must not be quoted as the strong one. The
eval is 110 games we have never seen; this measures the same game drawn again. CLAUDE.md
already says so about the adapters' 7/7 archived-hash result, and the caveat applies here
unchanged. What this run does establish is a NECESSARY condition: a solver that cannot
survive a re-render certainly cannot survive a new game.

## Prevention — what the two losses say

The failures are the useful part, because both are a conquered-or-scoring tool meeting the
same mechanic drawn differently:

- **tu93** falls from 9/9 to 4/9. Its tool clears the first four levels and then stops, so
  the mechanic is recognised and something level-5-specific is not.
- **s5i5** loses both of the levels it had. It was already the weakest game in the set.

Neither is a routing failure — the tools still engage. Both are a plan that generalises less
far than the detection does, which is the opposite of the usual failure and worth treating as
the sharper signal.

## Re-measured after five new tools landed (same day)

The five tools gated on 2026-08-27 took the live card 0.6733 -> 0.7459. Re-running the archive
gives the honest counterpart, and it is NOT the same number:

```
13 measurable re-rendered games   live 0.7459   archive 0.6541   ratio 0.88   identical 11/13
```

**One of the day's five gains does not transfer at all.** `telescope` takes s5i5 from 0.0833 to
0.4167 on the live board and scores **0.0000** on the re-render — worse in ratio terms than
before the tool existed. So a headline card number can rise while the property that matters
does not, and only the archive run says so.

Diagnosed to the cell. All eight of s5i5's levels are byte-identical between the two boards
(positions, sizes, rotations, mirrors, scale, layer, blocking, visibility, pixels, grid). The
rendered first frame differs by **TWO CELLS out of 4096** — (10,31) 13->14 and (34,10) 13->11 —
and the tool's own bid goes from **0.950 to 0.000**. Its colour-13 census is 10 cells live and 8
archived. On the archive board `graph` runs all 1,223 actions: telescope never bids, so this is
a DETECTION failure, not a planning one.

⛔ **A detector keyed on an exact colour census is not a detector.** The mechanic is what
identifies a family — a relation between parts, a count of STRUCTURES, a ratio with slack. Two
cells is the whole margin a pixel census has. Returned to the tool's author with the two
coordinates rather than loosened centrally, because the fix that merely makes it fire again is
the one that destroys its discrimination.

## Third measurement, and a second KIND of transfer failure (2026-08-27)

Re-run at card 0.7817, after `telescope`'s detector was re-keyed on its mechanic:

```
13 scorable re-rendered games   live 0.8078   archive 0.7461   ratio 0.92   identical 11/13
s5i5   FIXED   0.0000 -> 0.3926   (was the whole of the previous run's loss)
tu93   still  1.0000 -> 0.2222    the physics case, diagnosed separately
re86   EXCLUDED from the ratio — see below
```

**A tool can transfer its ANSWER and not its COST.** Per-action wall clock across all fifteen
archived games is within a factor of 1.3 of the live board — except one:

```
re86    live 1113 actions in 56s      archive 880 actions in 1011s      23x slower per action
every other game                                                        0.6x - 1.3x
```

re86's archive run scores 0.4183 against 0.8350 live, and that gap is **not the tool's ceiling
— it is our own wall-clock cap**, which stopped the run at 1011s against a 1000s limit. Scoring
it as a level loss would have been wrong, and the tell was one field: `elapsed_s`. The live
board never comes near the cap (56s).

So this is a real transfer defect of a kind the score cannot show: the same search that answers
in 56 seconds on one rendering needs at least seventeen minutes on another. On the eval — 110
games inside a 9-hour cap — a tool like that is not slow, it is fatal, and its score on the
public 25 says nothing about it. ⛔ **Compare wall-clock per action across the two boards, not
only the scores.**

**FIXED the same day, and completely.** Handed to the tool's author with the stack sample and
the instruction to diff the two boards' level data before assuming the archived one is harder:

```
before   880 actions in 1011s   6/8 levels   0.4183   (stopped by our 1000s cap)
after   1107 actions in    5s   8/8 levels   0.8350   — equal to the live board
```

Two hundred times faster, and the transfer loss goes to ZERO. The public card did not move by a
digit either way (0.7935 before and after), which is the whole point: this defect was invisible
to the measurement everyone watches and fatal to the one that decides.

## Fourth measurement — the best yet, at card 0.8224 (2026-08-27)

```
14 re-rendered games   live 0.8675   archive 0.8102   ratio 0.93   identical 12/14
per-action wall clock  0.7x - 1.3x on EVERY game — the 23x cost blow-up is gone
```

Both of the day's transfer defects are closed. s5i5's detector, which two cells used to kill,
now fires on both boards (−0.0240, from −0.4167). re86's cost, which was 23x on the re-render,
is 0.9x and it scores 0.8350 on both. su15's conquest transfers intact at 1.0000.

**The only remaining loss is tu93**, 1.0000 -> 0.2222, and it is the one already diagnosed: the
two boards' level-5 start frames are byte-identical on the layer every tool reads, they respond
differently to the same twenty-action script, and their sole recorded difference is one sprite's
`layer` field. It is not a detector problem and not a cost problem — it is the tool being shown
a board that cannot be told apart from a different one. See [[../concepts/frame_layer_timeline]].

⚠️ The ratio has moved 0.91 -> 0.88 -> 0.92 -> 0.93 across four runs while the card went 0.6733
-> 0.8224. It did not rise BECAUSE the card rose: it dipped when a tool gained on the card
without transferring, and recovered when that tool was fixed. The two numbers are independent
and only one of them is evidence about the private set.

## Fifth measurement, at card 0.8540 — ratio 0.94

```
14 re-rendered games   live 0.9085   archive 0.8513   ratio 0.94   identical 12/14
```

The three conquests of the afternoon transfer INTACT at 1.0000 on the re-rendered boards:
sp80, m0r0 and su15, alongside sc25, tn36, tr87, r11l, vc33, ar25, cn04 and sk48. re86 carries
its 0.8350 across at 1.0x wall clock.

Two losses, and only one of them is a loss:

* **tu93** 1.0000 -> 0.2222, unchanged and already diagnosed — the boards are byte-identical on
  the layer every tool reads, respond differently to the same script, and differ only in one
  sprite's `layer` field. Not a detector problem and not a cost problem.
* **s5i5** -0.0240, which is the same small residual as before and is the tail of a detector
  that was fixed today, not a new failure. ⚠️ It is now **3.4x slower per action** on the
  re-render, the only game above 1.5x — worth watching, since the last time a game showed that
  signature (re86 at 23x) it was a genuine cost defect that a fix took to 1.0x.

Ratio across the five runs: **0.91 -> 0.88 -> 0.92 -> 0.93 -> 0.94**, while the card went
0.6733 -> 0.8540. The dip is where a tool gained on the card without transferring; the recovery
is where that tool was fixed. The two numbers move independently and only one of them is
evidence about the private set.

## Falsification

Wrong if the control stops matching (sk48 live vs archive), which would mean the archive run
differs from the live run for reasons unrelated to the re-render. Also wrong as *evidence for
the private set* if a game is later found that our tools clear live and fail on a genuinely
NEW board while passing its re-render — that would show the re-render is too easy a test.

## Related

- [[api_hash_rotation_20260421]] — the rotation that first exposed brittle attribute-readers.
- [[tool_selectivity_20260827]] — why detection and plan are measured separately; here they
  come apart, with detection generalising further than the plan.
- [[../rounds/r101_tool-development]] — the round.
