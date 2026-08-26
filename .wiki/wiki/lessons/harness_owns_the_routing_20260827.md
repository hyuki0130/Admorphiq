---
type: lesson
topic: harness-routing
date: 2026-08-27
keywords: [routing, detect, level-up, signature-default, tool-set, r101]
---

# The biggest losses were in the harness, not in any tool

> Two routing defects cost more than every tool improvement of the day combined, and no tool author could have found either — one was found by a tool author measuring MY code.

## Symptom

Tools that solved their game outright scored almost nothing through the harness. One cleared
ar25 8/8 with `GameState.WIN` under its own probe and scored **0.0278** — exactly one level of
eight — in the full-25 run. The same gap appeared three times in one session, on three different
tools, and was misread each time as "the tool needs work".

## Root Cause 1 — a level-up handed the board away

`_reset_level()` cleared `_current`, so the next action forced a re-decide. That decision is made
on the TRANSITIONAL frame, where the tool that just solved the level frequently scores 0: the next
board has not been drawn yet. Traced step by step on ar25 — the tool cleared level 1 in 16 actions,
the general searcher took the board on the level-up, and spent the remaining 384 actions clearing
nothing.

**Clearing a level is the strongest evidence of fit that exists. It must outrank a `detect()` score
taken mid-transition.** With the tool kept, the same run clears 8/8 in 269 actions. A tool that
then stalls is still retired by the normal stall path, so nothing is lost.

## Root Cause 2 — a bid of 0.0 won the board

`_signature_default` started at `best = -1.0`, so `0.0 > best` held. A board that **no** tool
claimed went to whichever tool was FIRST in registration order — meaning every tool added silently
re-assigned games none of them bid on. Found by the author of a tool that had measured **zero bids
across 9,600 frames** of foreign games and still saw one of them change hands when it registered.

With nobody claiming the board, the general searcher is now the deliberate fallback.

## What it was worth

```
full 25, generic tools alone, frozen snapshot, registry unchanged
  0.1525 -> 0.2143
  ar25  0.0278 -> 1.0000   conquered
  sb26  0.8334 -> 1.0000   conquered
  re86  0.0278 -> 0.2685
  wa30  0.0223 -> 0.1333
  sc25  0.1905 -> 0.2440
no game regressed
```

## Prevention

- When a tool's standalone probe and its harness score disagree, suspect the ROUTING first. A
  probe drives a tool directly; the harness routes by `detect`.
- Selectivity and ownership are properties of the tool SET. No agent can see them, so a fan-out
  must reserve them for the integrator — [[../parallel_build_protocol]].
- ⛔ Take a peer's measurement seriously and CHECK IT. The `best = -1.0` defect arrived as a claim
  from a subordinate agent about the parent's code, and it was correct.

## Falsification

If a routing change is worth nothing, it will show as a byte-identical full-25. The zero-bid fix
did exactly that (0.1525 -> 0.1525, all 25 identical) and was kept anyway, because "first in the
dict wins" is an accident of ordering rather than a decision.

## Related

- [[tool_selectivity_20260827]] — the mirror image: a tool bidding on a board it cannot solve.
- [[moving_target_measurement_20260827]] — why the baselines in this round needed freezing.
- [[../rounds/r101_tool-development]] — the round.
