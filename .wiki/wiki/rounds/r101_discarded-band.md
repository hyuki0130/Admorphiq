---
type: round
round: R101BAND
axis: generic-tools
keywords: [outer band, edge band, board_changed, HUD, counter, deadsig, globally_dead, drop_dead, augmenter, perception, state_key, novelty]
verdict: the band costs zero — its single consumer fires on the one game where the discard is correct
commit: 517f24b6
---

# R101BAND — what does the discarded outer band cost?

> `segment.board_changed` throws the frame's outer band away on purpose. It has exactly **one**
> consumer, that consumer fires on exactly **one** game, on a level that never clears — and on that
> game the band is a pure counter, so discarding it is right.

## Why the question was asked

[[r101_inert-actions]] (rule **7cb**) found games producing their only visible effect in the
discarded band on a large fraction of actions of levels they CLEAR: r11l 39 of 82, bp35 205 of 499,
cd82 28 of 131. If the harness treats those as "did nothing", a game that renders its feedback at the
frame edge is invisible to us — and the eval is 110 unseen games.

## Read the consumer, not the guard

Off `harness/loop.py:715-760` before measuring anything:

```
changed       = (prev != frame).any()        BAND INCLUDED  -> the ACTIVE tool's observe()
board_changed = segment.board_changed(...)   BAND DISCARDED -> tools with augmenter = True
novelty       = base_hash(frame)             BAND INCLUDED  -> _since_progress, stall, retirement
_empty_runs                                  reads NEITHER; it counts propose() returning []
```

**Exactly one tool in the registry sets `augmenter = True`: `deadsig`.** The whole cost flows through

```
deadsig.observe(board_changed) -> _changed_any -> globally_dead -> GraphSearchTool._drop_dead
                                                                   (WITHHOLDS the class)
```

Tenure, retirement and the stall detector consume none of it. `globally_dead` additionally needs
`changed_any == 0` with >= 12 tries from >= 3 distinct states, and one observed change anywhere
revives the class permanently.

## The measurement

`scripts/_band_cost.py`, one arm per game. **25 of 25 reproduce their banked `R101SHIPPED` per-level
counts *and* scores.** Two shadow `DeadSignatureTool` instances — real instances of the real class,
never a re-implementation of its thresholds — are fed the same transitions, one with the
band-discarded flag and one with the raw flag, using the harness's own `_prev_step`.

### The consumer fires on one game

```
_drop_dead calls across all 25:   2049
calls that actually WITHHELD:      918   -> ALL 918 on bp35, all on level 6
                                          -> not one on a level that clears
lf52: 227 calls, 0 withheld.  The other 23 games: graph never holds the board, 0 calls.
```

### And the discard is correct exactly where it is consumed

Classified by BEHAVIOUR at the region level — does the band advance on every action of every class,
or does it depend which action was taken:

```
a counter (rate ~1.0, every class always)   bp35 1.000  r11l 1.000  sb26 1.000
                                            su15 1.000  tu93 1.000  ls20 0.998  ar25 0.955
action-dependent content                    dc22 0.218  sk48 0.260  cn04 0.285
                                            m0r0 0.465  re86 0.485  cd82 0.649
```

bp35 has fifteen action classes and **all fifteen move the band at rate 1.00**. The games whose band
carries real content (cd82 0.61/0.50/0.64 by class, dc22 0.13/0.11/0.19) are exactly the games where
`_drop_dead` is never called at all.

### The per-pixel HUD test is blind to a counter

The observation phase's rule — a pixel changing under >= 80% of probes is a HUD element — returned
**zero HUD pixels on all 25 games**, which reads exactly like "there is no HUD anywhere". It is not:
`segment.py`'s own docstring says why, *"a counter that marches touches each cell once, so no cell
reaches a 'changes under most actions' threshold"*. Ask it at the REGION level and PER ACTION CLASS.

### A second discard exists and is not this one

`GraphSearchTool.state_key` masks pixels changing under `_HUD_FRAC` of observations — behavioural and
position-free — and feeds the harness's progress signal while `graph` is active. **Its mask is never
set on any of the 25** (0 pixels everywhere). The positional band belongs to `board_changed` and
nothing else.

## What this corrects in [[r101_inert-actions]]

⛔ Rule 7cb reported "r11l's 47.6% inert is 0 dead and 39 edge-only, therefore 0% waste". **That is
wrong, in the generous direction.** `edge-only` is not a safe harbour — whether it means a discarded
real effect or "only the counter ticked" depends on whether that game's band IS a counter. r11l's is,
at rate 1.000 on every class, so its 39 edge-only actions are genuinely inert. Cleared-level dead
actions go **68 -> 124 of 6381 (1.07% -> 1.94%)**. The score conclusion does not move — r11l is at 1.0
on every level — but the rate is the part that would transfer.

## Verdict

The band costs **zero**, and not by luck: its only consumer fires where the discard is correct.
⛔ Widening it is **not licensed** (rule 7o; the precedent is `frame_2d`'s stale-layer fix, right
about the mechanism and 0.8962 -> 0.6525 across fourteen games). What survives for the private 110 is
the *shape*, not a repair: a game that renders feedback in the outer band **and** is driven by `graph`
would have its working actions withheld. None of the 25 is that game, and `band_rate_by_class` says in
one command whether a new one is.

Rule **7cf**. Artefacts `scripts/rounds/R101BAND/band_cost.json`.
Related: [[r101_inert-actions]], [[r101_shipped-and-transfer]].
