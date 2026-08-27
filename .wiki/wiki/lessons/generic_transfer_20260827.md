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
