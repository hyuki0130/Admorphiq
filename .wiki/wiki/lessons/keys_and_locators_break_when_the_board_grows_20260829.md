---
type: lesson
topic: keys-and-locators
date: 2026-08-29
keywords: [locator, tracking, continuity, positional-key, named-key, unlockable-control, mid-level-change, uniqueness, dc22, gantry, phase_grid]
---

# Two ways a model dies when the board GROWS mid-level, and the rule that survives each

> A board that unlocks a control partway through a level breaks two things that
> look unrelated and are the same mistake: identifying a thing by *uniqueness*,
> and keying state by *position*. Both are exactly right at the start of the
> level and both are silently wrong the moment the board has one more thing in
> it than it did when the rule was written.

## 1. A locator must TRACK, not merely disambiguate

**Symptom.** The tool runs correctly for hundreds of actions, then stops
proposing anything for the rest of the level. Nothing errors; the read simply
returns `None` every turn.

**Measured.** dc22 level 6, action 293. The marker is located as "the unique
square of the avatar's own side". At action 293 a control UNLOCKS and is drawn
as a **second 2x2 in the marker's own colour**:

```
action 292   squares(colour 11, side 2) = [(5,46)]                  -> located
action 293   squares(colour 11, side 2) = [(5,46), (45,51)]         -> None, for ever
```

**Root cause.** Uniqueness is a property of the BOARD, and the board is allowed
to change. A rule that depends on there being exactly one candidate has no
answer the moment the game draws a second.

**The rule that survives.** *The piece is the candidate nearest to where it was
last seen.* The avatar moves one step per action and the marker does not move at
all, so continuity is a property of the PIECE rather than of the board, and no
button drawn elsewhere can break it. Uniqueness stays as the bootstrap — the
first sighting, when there is nothing to be near.

⚠️ Note the two failures are opposite and both real: *too strict* ("this colour
paints exactly one filled square") refuses a board where the marker's colour
also paints a 4x4 control, and the tool latches dead at action 6. *Uniqueness*
survives that and dies at 293. Only size-plus-continuity survives both.

## 2. A key must NAME its members, not COUNT them

**Symptom.** Every measurement is taken correctly, and the planner can use none
of them. The stored table looks right when printed.

**Measured.** The same board's teleport destination depends on the phases of the
other ring controls, so the observation is keyed by those phases. Keyed
positionally:

```
before the aimer unlocks   key = (1,)         3 rings do not exist yet
after  the aimer unlocks   key = (4, 3)       the tuple has changed LENGTH
```

Four destinations were read correctly from frames. Every one taken before the
aimer existed had a key of the wrong arity, matched nothing, and the route
planner fell back to "no warp" — so the tool knew the way off the island and
could not plan it.

**Root cause.** A positional key encodes *the shape of the model at the moment
of measurement*. The model grows. The key does not migrate.

**The rule that survives.** Key by `(control, phase)` PAIRS, and treat a stored
key as matching whenever it AGREES with the current state on the members it
names, preferring the most specific match. An older, shorter measurement then
still applies — it simply says less. Missing members are unknown, not zero.

## Generalisation

Both are the same shape: **a model wrote down something about a world, using a
description that is only valid while the world has the same inventory.** Any of
these is the smell:

- "the unique X" / "the only Y" / `len(found) == 1`
- a tuple, list index, or array offset that indexes *the set of things currently
  known* rather than a named thing
- a cached count, a fixed-width vector, a `enumerate(...)` over a discovered set

⛔ And the trigger is not rare: any tool that reads its controls off the frame
will meet a board that unlocks one. dc22 unlocks two — a colour-cycle aimer
behind a key at (17,6) and a grab button behind a key at (47,34).

## Falsification

If a board's inventory is fixed for the whole level, neither rule is needed and
both cost a little complexity. The claim is about levels that gain a control,
a token or an entity partway through — which is exactly the class of level that
stops a tool that clears every level before it.

## Provenance

Measured 2026-08-29 on dc22 level 6, `scripts/_dc22_percep.py` (the locator) and
`scripts/_dc22_gantryx.py` (the key), traced by `scripts/_dc22_ptrace.py`. The
per-level square tables and the aimed-teleport table are in
`.wiki/wiki/sample_games_mechanics.md`. Related:
[[branch_with_a_comment_never_ran_20260829]].
