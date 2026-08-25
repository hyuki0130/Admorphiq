---
type: lesson
keywords: [adapters25, submission, detector-gated, dispatch, game-id, port, ceiling, gap-table]
date: 2026-08-25
verdict: The adapter port is a DISPATCH change, not a rewrite — every adapter is already frame-only; only the registry is keyed by game_id. Measured card 0.0554 vs ceiling 0.3296 (6x).
---

# The 6x gap, and why closing it is cheaper than it looked (2026-08-25)

## The measured gap

Both cards measured the same afternoon on ceph-build, 25 games each, in parallel
(`scripts/rounds/SUBCAND1` = the shipped agent, `scripts/rounds/CEILING1` = script25 adapters):

```
                     mean game_score    levels
shipped card            0.0554            27
adapter ceiling         0.3296            87        <- 6x, and 60 more levels
```

Per game, largest gap first — this ordering IS the port priority:

```
ft09   card 0.0000 (0 lvl)   ceiling 1.0000 (6)     gap 1.0000
m0r0   card 0.0000 (1)       ceiling 1.0000 (6)     gap 1.0000
ls20   card 0.0327 (1)       ceiling 1.0000 (7)     gap 0.9673
sb26   card 0.0796 (2)       ceiling 0.8460 (8)     gap 0.7664
lp85   card 0.0000 (0)       ceiling 0.6992 (8)     gap 0.6992
re86   card 0.0833 (2)       ceiling 0.7273 (7)     gap 0.6440
su15   card 0.0000 (0)       ceiling 0.4368 (6)     gap 0.4368
```

Three games the adapters CONQUER (1.0000) score **zero** on the card.

## Why the port is a dispatch change

The obvious reading of "quarantined by design" is that the adapters cheat and would have to be
rewritten to ship. **Measured: they do not cheat.** Every adapter's entry point takes no game
identity at all —

```
ft09.Adapter.__init__(giveup=_GIVEUP_DEFAULT)
m0r0.Adapter.__init__(giveup=_GIVEUP_DEFAULT)
ls20.Adapter.__init__()
```

— and the only `GAME_ID` references under `adapters25/` are the registry in `__init__.py` and one
comment in `ka59.py`. The AST lint already forbids an adapter from importing anything but stdlib,
`admorphiq.kernels`, and `adapters25.base`, so no adapter can smuggle in a legacy brittle solver.

So the game-specific part is **the registry mapping, and nothing else**. What blocks shipping is
that `script25.py` selects an adapter by `game_id` substring. The fix is a `detect(frames)` hook on
`GameAdapter` and dispatch by detection — the logic underneath is untouched.

**The precedent already ships.** `world_model_agent.py` gates its cd82 solver on
`ring_paint.detect_paint_layout(layer, background)`, whose docstring is pure geometry — *"a ~10x10
uniform CANVAS block in the lower half + a patterned 10x10 TARGET in the top-left + top-row
swatches"* — with no game identity anywhere. That gate is why cd82 scores 0.9463 on the card
instead of 0.

## What this does NOT establish

⚠️ Frame-only is not the same as general. An adapter that never reads the game id can still encode
one game's layout constants, and a detector that fires on the wrong private game spends actions for
nothing. The quarantine exists for that risk and the port does not dissolve it — it converts it
into a per-adapter question with a measurable answer: **how specific is this detector?**

The failure modes are asymmetric and that is what makes the port worth doing. On the 110 private
games, a detector that does not fire costs nothing (the generic agent proceeds), while one that
fires correctly on a genuinely similar game is pure gain. The thing to guard is the middle case,
and it is guarded per adapter, at port time, by measurement.

⛔ Do not port by pattern-matching what the adapter knows about ONE board. Port the detector from
the mechanic's observable signature, the way `detect_paint_layout` does, and measure the false
positive rate against the other 24 games before shipping it.

Related: [[submission_not_reproducible_20260825]], [[faithful_offline_simulator_20260715]].
