---
type: lesson
topic: measurement-integrity
date: 2026-08-27
keywords: [snapshot, fan-out, agents, bisect, regression, ghost, registry, r101]
---

# A measurement taken while the code is being edited is not a baseline

> Six bisect runs chased a regression that did not exist, because the number they were measured against came from a tarball taken while that game's own tool was mid-edit.

## Symptom

A full-25 run reported one game down `0.0667 -> 0.0223` after four new tools were registered.
Removing each of the four in turn left it at 0.0223. Removing all four left it at 0.0223. Both the
committed and the working-tree version of that game's own tool gave 0.0223.

## Root Cause

Fifteen background agents were writing into the same working tree while measurements ran. The
sequence that produced the ghost:

1. a tarball was synced to the measurement box — capturing that game's tool mid-edit;
2. the run scored the game at 0.0667 with that intermediate version;
3. the agent kept editing; the file was committed later, in a different state;
4. every subsequent run measured the committed version, which scores 0.0223.

**The committed code was never the measured code.** The "regression" was a difference of TIME, not
of behaviour, and three innocent tools were nearly reverted for it.

The same window produced its mirror image: a tool whose standalone probe improved from 3 levels to
4 scored WORSE in the harness (`0.2143 -> 0.0357`), because a probe drives a tool directly while
the harness routes by `detect`. An agent's own report cannot decide whether its work is kept.

## Prevention

- **Freeze ONE snapshot on the measurement box, then produce every variant by editing
  `registry.py` THERE.** A comparison is like-for-like only when the tool files are identical and
  the registry is the only difference. The final measurement of this round was done that way and
  came back clean: `0.1351 -> 0.1514`, no game regressed.
- Never `git add -A` while agents run — a docs commit swept 393 lines of an agent's in-progress
  tool into itself under a message that mentioned neither.
- Treat a baseline as valid only if it can be REPRODUCED from a committed state.

## Recovery

Re-baseline against a reproducible configuration and compare within it. Do not revert tools on a
number you cannot reproduce.

## Falsification

If a "regression" survives removing every candidate change, it is not caused by them. Re-measure
the baseline itself from the committed tree before attributing it to anything.

## Related

- [[tool_selectivity_20260827]] — the real regressions, where a tool bids on a board it cannot solve.
- [[../parallel_build_protocol]] — the fan-out this happened inside.
- [[instrument_validity_20260825]] — validate the instrument before the hypothesis; this is the
  same rule applied to the BASELINE.
