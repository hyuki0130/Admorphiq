---
round: R101BP35SEE
axis: can crag SEE bp35's level 6 at all — what it reads, what it refuses, and why the refusal never teaches it anything
keywords: [bp35, crag, perception, stitch, alignment, volatile, crumbling-platform, level-6, align-fit, reanchor, depth, contrast, lane-collision]
verdict: crag gets FOURTEEN turns on level 6 and never bids again — all eight quits are `_stitch` returning `lost` through the SCORE threshold (best 0.60 against 0.82), never the physics gate, never too-few-cells. The orthogonal defect is a SEQUENCING one — `_volatile` is populated only inside `_absorb`, which runs only after a stitch SUCCEEDS, so a glyph that changes enough to break alignment can never be learned as volatile. Level 3 learns 2 and clears; level 6 learns 0. ⛔ My reading of WHY the 0.60 is low is NOT established — a peer's in-flight `_reanchor` explains the same number as a spurious off-strip overlap and my data cannot separate them. Nothing built, no gate: another agent had 103 uncommitted lines in the same function.
commit: pending
supersedes: nothing — this is the perception lane of the bp35 push
---

# R101 — what `crag` can and cannot see on bp35

> bp35 is the largest gap in the corpus: **0.24556**, worth **+0.0302** of the mean. It clears five
> of nine levels and the loss is DEPTH — roughly **507 of its 726 actions** go on level 6 alone. The
> recorded reading was *"a tool that cannot read the board, not one that was interrupted."* This
> round is what it actually sees.

## The whole answer is one table

`scripts/_bp35_see.py`, on a run reproducing the banked `R101SHIPPED` bp35 exactly — 0.24556,
per-level `[18, 87, 45, 23, 46]`, `BANKED_MISMATCH` false:

```
level  turns  steps  quits  stitch outcomes   world  rows  vocab  VOLATILE  edits  idle   result
1         18     18      0  grow 18             260    10      4       0        4     0   18/21 = 1.0000
2         85     85      0  grow 83, home 2     370    10      7       0       19     0   87/48
3         45     45      0  grow 45             310    10     12       2       13     0   45/44 = 0.9560
4         23     23      0  grow 23             320    10     13       0        6     0   23/38 = 1.0000
5         45     45      0  grow 44, home 1     300    10     14       0        9     0   46/33
6         14      6      8  grow 6, LOST 8      100     9     15       0        1     8   never cleared
```

⭐ **crag gets fourteen turns on level 6 and never bids again.** `_idle` reaches 8 against its own
`_GIVE_UP` of 16 and `_mute` stays 0, so **it never retires itself** — the harness stops offering it
the board. `GraphSearchTool` then takes **382 actions** and clears nothing. And `edits_max` is **1**
on level 6 against 4-19 on every other level: it barely acts at all before it goes quiet.

⚠️ **"15 known cells" was a misread field.** `_known` is `_vocabulary()` — the number of named glyph
KINDS, and 15 is the largest it ever reaches, so nothing is wrong with it. The MAP is
`len(self._world)`: **100** on level 6 against 260-370 on every level that clears.

## Which branch refuses, and which do not

Every quit on level 6 is `"window does not belong to this board"`, i.e. `_stitch` returning `lost`.
That has three exits and they demand different repairs, so `scripts/_bp35_lost.py` replays the scan
read-only after each refusal and counts them:

| | | |
|---|---|---|
| **C1** every shift refused by `_admissible` | the PHYSICS gate | ⛔ **not this** |
| **C2** every shift had `total < _ALIGN_MIN` (16) | too few comparable cells | ⛔ **not this** |
| **C3** best agreement below `_ALIGN_FIT` (0.82) | the score threshold | ⭐ **all eight** |

```
act  6   allow = -1     refused_by_physics 66   too_thin 60   scored  42   best 0.565 / 69 cells
act  7   allow = None   refused_by_physics  0   too_thin 68   scored 100   best 0.600 / 20 cells
act  8 .. act 13        ... identical to act 7, all seven ...
```

⭐ **Acts 7-13 are byte-identical** — the same twenty comparable cells, the same eight
disagreements, the same 0.600, seven times over. That is not seven attempts; it is one frozen state
re-evaluated seven times, because nothing is absorbed so nothing can change.

## The defect that survives either explanation

⭐ **`_volatile` is populated only inside `_absorb`, and `_absorb` runs only after a stitch
SUCCEEDS.**

`_stitch` skips any cell whose signature is in `self._volatile` — the tool's own concept for *"this
glyph changes, do not align against it"*. That set is filled at the bottom of `_absorb`, on the
`clashes >= 3` rule. And `_absorb` is reached only on the `grow` and `home` paths:

```python
if best is None or best[0][0] < _ALIGN_FIT:
    ...
    return "lost", first[2], first[3], first[4]      # <- returns WITHOUT _absorb
...
self._absorb(board, body, shift)
return "grow", board, inks, body
```

⛔ **So a glyph that changes enough to BREAK alignment can never be learned as volatile: the
learning sits on the far side of the gate it just failed.**

**And it is not dead code — the contrast proves it fires when it can.** Level 3 learns **2** volatile
signatures and clears at 0.9560. Levels 1, 2, 4 and 5 need none and clear. Level 6 learns **zero**
and is the only level whose frames are ever refused. Whatever else is true of level 6, this is a
property it does not share with any level that passes.

## ⛔ What I got wrong, and why it is the round's real lesson

I read the 0.60-over-20-cells refusal as **"the board changed under the map"** — a crumbling
platform making terrain non-static, which the game's own source supports (level 6 adds one crumbling
platform whose four shrinking sprites read as four glyph kinds), and which the data appears to show:
at the first refusal 25 compared cells all read one NEW signature `((3, 2), (5, 14))` where the map
held several different old ones.

The `game-bp35` agent's in-flight `_reanchor` reads the **same numbers** the other way: the window
has travelled entirely off the mapped strip, and the 0.60 is *"twenty cells of rock"* matching rock
at a spurious shift. It has independent evidence mine does not — the camera moves 9.7 cells through
a ten-row window, so one reversal can carry the body a whole window clear of everything the map
holds.

⛔ **My data cannot separate them.** At every refusal **68 candidate shifts were dropped as too
thin**, and an off-strip shift is exactly what lands in that bucket. A wrong shift compared against
unrelated map cells produces the same "one new signature against several old ones" picture as a
board that changed. **The C1/C2/C3 split is measured. The interpretation of the 0.60 is not.**

⚠️ This is rule 7b's trap in its purest form and it is the fourth time this campaign has met it: a
property of the failing level that is equally consistent with two mechanisms is not a cause. The
contrast that saved the rest of this round — `_volatile` empty on 6, non-empty on 3 — is a statement
about where LEARNING is wired, not about this frame, which is why it survives the ambiguity.

## What bounds the repair that is in flight

`_reanchor` returns `None` when `allow is None`, and **`allow` is None on seven of the eight
refusals** — only act 6 names a direction. As written it gets one attempt, at act 6. ⭐ It calls
`_absorb` on success, so if that attempt lands it also reopens the volatility path as a side effect,
which may matter more than the placement itself.

## Nothing was built, and the reason is rule 8

⛔ `crag.py` carried **103 uncommitted insertions** from `game-bp35` at the exact line I was about to
edit. Two agents editing one function is the failure rule 8 names, so I stood down and sent them the
findings instead.

⚠️ **My numbers do not ride on that edit, and I checked rather than assumed**: all four probe
snapshots on the box contain **zero** `_reanchor`, so every measurement here describes committed
HEAD (`fbeaeaed`), which is also where the banked 0.24556 comes from.

⭐ **One fact worth having before anyone designs the repair**: across the full 25, `crag` is selected
on **bp35 and no other game**. The blast radius of a `_stitch`/`_absorb` change is one game — which
makes this a cheaper gate than most, though `snapgate.sh` on the full 25 with the canaries still
decides it (rule 7o).

## Artefacts

```
scripts/_bp35_see.py                              crag's perception state per turn, per level
scripts/_bp35_lost.py                             the three `lost` exits, separated on a run
scripts/rounds/R101BP35SEE/bp35see3.jsonl         the per-level table above
scripts/rounds/R101BP35SEE/bp35lost2.jsonl        the eight refusals, with their disagreements
```

Related: [[r101_bp35-attempts]] (the dynamics lane) · [[r101_visibility-identity-census]] (crag is
one of the eight index-ordered colour sites, and `crag:1352` cuts candidates to one 70 times on
bp35) · [[r101_inert-actions]] (bp35 41% inert actions at the wall).
