---
type: round
round: R101PROBE
axis: generic-tools
keywords: [probe fallback, refusal, lf52, railpeg, observe changed flag, instrument validity]
verdict: INERT — reverted; the finding is the keeper
---

# R101PROBE — the stalled tool's waste belongs to the harness

> A fallback that always pressed the lowest-numbered key spent 83 of lf52's 117 refused ACTION1
> presses; the tool blamed for them emits 34, and removing the waste opens no level.

## What was measured

lf52's sixth level, 1000 actions, attributed by a level field carried on every event:

| key | moved | refused | refusal rate |
|---|---|---|---|
| ACTION1 | 21 | 117 | 85% |
| click | 145 | 71 | 33% |
| ACTION3 | 48 | 22 | 31% |
| ACTION2 | 14 | 30 | 68% |

Of the 117 ACTION1 refusals, **83 were issued by `UnifiedAgent._probe`**, which returned
`simple_ids[0]` whenever the active tool proposed nothing. `railpeg`'s own plan emits 34.

## Three corrections this round paid for

1. **The tool-side lever was built and measured inert.** A per-axis refusal memory in `railpeg`
   fired 9 times and moved the score not at all (0.2727 before and after). It was reverted. The
   previous session had named it as the lever on the strength of an aggregate that did not say who
   pressed the key.
2. **`observe`'s `changed` flag cannot see a refusal.** It is `(prev != frame).any()`, and lf52's
   edge counter makes it true for every action. The first counter recorded `fail={}` across 227
   transitions — an inert guard that looked exactly like a measured negative. `board_changed`
   ignores the outer band and is the only reading that works; it needs the next frame, so the
   count settles at the following `propose`.
3. **The level is not budget-starved.** Five levels clear at 500 actions and five at 1000. Removing
   the waste therefore cannot be lf52's lever, whatever else it is worth.

## The change, gated and REVERTED

`_probe` now orders the simple keys by how often each has actually moved the board, then by how
often it has not, then by id. The counters come from the board-level flag the loop already computes
for augmenters. This is generic — it applies to every game where a tool stalls. **Gated on the full 25
(R101PROBE vs R101REACH): 0.8935 -> 0.8935, no game regressed and no game gained.** Inert, so it
was reverted rather than kept: the harness ships in the deployed card, and code that carries risk
without a measured gain does not belong there. The 83 presses it removes are real; they simply buy
nothing, which is the same thing the level itself says by clearing 5 at both 500 and 1000 actions.

## Related

[[lessons/online_rl_sprint_round_log]] · [[lessons/instrument_validity_20260825]]
