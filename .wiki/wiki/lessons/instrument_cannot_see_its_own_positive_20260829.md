---
type: lesson
topic: measurement-integrity
date: 2026-08-29
keywords: [known-positive, instrument-validity, false-negative, probe-validation, equality-across-frames, layer-selection, re86, lf52, dc22, r101]
---

# An instrument that cannot see its own known positive measures nothing

> Six versions of one probe. **Five of them scored the board the probe was written from at ZERO** —
> and every one of those zeros was a publishable-looking sentence: *"no other game has re86's
> problem"*. The failure direction is the whole danger: an instrument that lies **towards "there is
> nothing here"** produces a clean negative, and nobody re-checks a clean negative.

## What happened

re86 level 2 cost 46 actions against a human 42. The cause was found by hand and is not in dispute:
the level-transition frame carries the **old** level's board in layer 0 and the **new** level's in
layer 1, `frame_2d` returns the first layer, the tool recognises nothing, proposes nothing, and
`UnifiedAgent._probe` fills the turn with `simple_ids[0]`. Verified by reading the palettes — layer 0
held colour 11 (level 1), layer 1 held 12 and 13 (level 2's pieces).

The follow-up question was how many of the other twenty-four games pay the same tax, so a probe was
written to count it. **Any correct version of that probe must report re86.** Here is what six
versions reported:

```
v1  layer 0 held still while a LATER layer moved since the last frame
    -> re86 emits ONE layer until the transition, so prev[1:] is empty; the clause CANNOT fire.
       Reported 0 for re86 and 0 for 18 of 20 games.
v2  a later layer showed what layer 0 did not, AND the next frame's layer 0 is exactly that
    -> an ACTION happens between the two frames and moves a piece, so the equality never holds.
       Reported 0 for re86 — and 150 for g50t, on an ANIMATION SETTLING, which is not staleness.
v3  at a transition, layer 0 identical to the previous frame's layer 0
    -> the level-CLEARING move changed the board, so again never equal. 0 for re86.
v4  v3 with the seeded first frame removed
    -> the seed had been adding a CONSTANT 1 to every game's count, which reads exactly like a
       finding. Removing it left 0 for re86.
v5  a COMPARISON, not an equality: is the LAST layer CLOSER than layer 0 to the board handed back
    next?  -> re86 answers 7, exactly its number of level transitions. First honest version.
v6  v5 widened off the transitions, where the real claim lives.
```

**Every failed version was an EQUALITY, and an equality cannot survive a frame boundary**, because
an action happens there and moves something. The fix was not a better threshold; it was changing the
question from "is X the same as Y" to "is X closer to Y than Z is".

## What the working instrument then said

Not "re86 alone" — the opposite. `trans_stale` equals `levels − 1` for **every game measured**:
every level transition of every game hands the tool the board of the level it has just left, and
1591 of 1927 multi-layer frames (83%) are read stale away from transitions too. Four of the five
broken versions would have been written up as *"re86 is the only game affected"*, which is as wrong
as a measurement can be while still being a number.

## The rule

⛔ **Before reading a probe's output, run it on input whose verdict you already know — in BOTH
directions.** A known positive it must report, and a known negative it must not. This is already in
[`OPERATING_RULES.md`](../../../OPERATING_RULES.md) rule 7b (*"prove the instrument is attached
before reading it"*) and in [[instrument_validity_20260825]]; what this round adds is the sharpest
form of the failure and the reason it recurs:

**A broken instrument almost always fails towards ZERO.** A filter that is too strict, a clause that
cannot fire, an equality that cannot hold — all of them return "nothing found", and "nothing found"
is the one answer that gets accepted without a second look. A false positive announces itself; a
false negative is indistinguishable from a real negative and reads as a finding.

## Three of these landed the same day

* **this one** — five versions of a layer probe, each scoring its own known positive at zero.
* **lf52** — a blob filter with a minimum size of 4 hid the oracle, which was four two-pixel blobs.
* **dc22** — a level test written `levels_completed != 5` read a COLLAPSE to level 0 as a clear, and
  three commits were built on the wrong side of it before the direction was named
  (rule 7f; see [[../sample_games_mechanics]]).

The first two failed towards "nothing here". The third failed towards "we won" — the favourable
reading, which is the *other* direction nobody checks. Together they are one rule with two faces:
**name the direction the instrument can be wrong in, then feed it a case that would expose it.**

## Related

* [[instrument_validity_20260825]] — the nine-failure version of this from R98, including checkers
  that were themselves wrong on their first run.
* [[../sample_games_mechanics]] — the re86 section (what the layer defect costs) and the
  `frame_2d` section (what the corrected instrument measured across all 25).
* [`OPERATING_RULES.md`](../../../OPERATING_RULES.md) rules 7b, 7e, 7f, 7g.
