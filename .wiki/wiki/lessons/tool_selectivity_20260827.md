---
type: lesson
topic: tool-architecture
date: 2026-08-27
keywords: [selectivity, harness, perception-grammar, feedback-loop, regression, r101]
---

# A tool in a shared harness must be a perfect detector before it is a good solver

> Asked directly, after a day of it: "you have all the game data and you still cannot solve them —
> why?" Three of the four reasons are method, and they are written here so the next session does
> not pay for them again.

## What happened, in numbers

Two rule-recovery tools were built and each works alone: `StencilTool` clears ft09 4/6 (its first
level in 4 actions against a human baseline of 43), `TrackAlignTool` clears lp85 level 1 in 5
actions (budget 13, human 17, the searching path 924). Registered together, the generic card went
0.0200 -> 0.0211.

Then the track tool's ring reader was loosened so it could see a three-ring board. Measured on the
full 25:

```
ft09  0.4762 -> 0.0476     lp85 unchanged     MEAN 0.0211 -> 0.0037
```

**A 20x net loss, and the tool that lost it was still perfect on its own game.** The standalone
ft09 probe scored 4 levels throughout. What changed was that the track tool started BIDDING on
ft09's lattice and taking turns from the tool that could solve it.

## The four reasons

1. **Knowing the mechanic is not having a perception grammar.** The data says lp85 is a ring
   rotation. The tool still has to recover, from 64x64 pixels, what a tile is, what the pitch is,
   and which blocks form a ring. Every failure today was in that recovery, not in the mechanic.
2. **In a shared harness a tool's mistake is not its own.** It steals the turn from a tool that
   would have solved the board. So each tool must be general enough to fire on its mechanic AND
   narrow enough never to fire elsewhere — a harder constraint than solving the game, and the one
   that actually broke.
3. **The feedback loop was the wrong one.** Six or seven iterations on ONE level of ONE game, each
   looking like progress under a single-game probe. The full 25 takes **two minutes** on
   ceph-build at PAR=25 and is the only measurement that can see a net loss. It was run too late.
4. **The perception grammar is being invented per game.** Block size -> pitch -> cycle -> shell ->
   contiguity -> isolation filter: six heuristics, each justified by one board, stacked inside one
   tool. That is not a grammar, it is a pile, and each layer added is a new way to fire wrongly.

## What to do instead

- **Measure the full 25 after every tool change, before keeping it.** Two minutes. A single-game
  probe cannot see the cost.
- **Score a tool by its NET effect on the card, never by its own game.** "lp85 0 -> 0.0278" was
  true and irrelevant next to "ft09 0.4762 -> 0.0476".
- **A tool with no plan must bid ZERO.** Returning a consolation confidence for "the shape is
  vaguely right" is how both regressions started.
- **Put the perception grammar in ONE tested place**, not re-derived inside each tool. Segmentation
  (tiles, pitch, lattice, ring) is shared machinery and should be pinned with its own tests, so a
  fix for one board cannot silently loosen every tool at once.

## Related

- [[../rounds/r101_tool-development]] — the round, with both tools and every measurement.
- [[instrument_validity_20260825]] — the same discipline one level down: validate the instrument
  before the hypothesis. This is validate the CHANGE before keeping it.
- [[../sample_games_mechanics]] — what the data does give: mechanics, budgets, win conditions.
