---
type: round
round: R101RENDER
axis: generic-tools
keywords: [render mutation, transfer, colour permutation, palette, translation, camera pan, full-bleed board, sprite rename, version hash rotation, v2 hash, instrument validity, refusal path, xfergate, rendergate]
verdict: the tools are colour-blind on all 25 games; translation is not constructible because 24 of 25 boards are full-bleed; the archive covers 14 games, not 15
commit: 2bf1a472
---

# R101RENDER — a transfer test that MANUFACTURES the re-render

> Three independent colour relabellings of every board, full 25 each, against an identity control at
> the same commit: **mean 0.9082 in all four arms**, and **one action of one level** moves in the
> whole set. The tools read structure, not pixels. ⚠️ And a relabelled board is still the same board.

## Why the question was asked

Rule [[r101_shipped-and-transfer]] / **7by** is the repository's only generalisation evidence:
substitute the archived re-render of each game, re-score the 25, and 24 of them come back
action-for-action identical. It has two limits. The first — a re-render is the SAME GAME — is not
fixable. The second is: **the archive only exists for some of the games**, and bp35, cd82, ft09,
g50t, lf52, lp85, ls20, sb26, tr87 and wa30 have no transfer evidence of any kind. Four of those ten
are among the six games still short of the cap.

⭐ **And the archive is thinner than recorded: it covers FOURTEEN games, not fifteen.**
`environment_files_archive/sk48` is version hash `41055498`, which is the hash the live tree already
holds, byte-identical (`diff` reports no lines). Substituting it substitutes a game for itself. Rule
7by's "all fifteen archived re-renders" should read fourteen. (Unrelated to rule **7bu**'s sk48
duplicate, which was a second hash `d8078629` on the box; that one is archived and measured inert.)

## What was built

`scripts/rendergate.sh` (+ `rendergate_run.py`, `rendergate_compare.py`,
`src/admorphiq/render_mutation.py`, 11 contract tests). It mutates the AGENT'S OBSERVATION and never
the game.

```
bash scripts/rendergate.sh r1 "identity cperm cperm2 cpermbg" 8 4000
```

⭐ **Why the observation and not the source.** The instrument's own validity is the deliverable: a
mutation that changes the MECHANIC produces a lower score that means nothing and looks exactly like a
transfer failure. Mutating a game's source cannot be shown safe without reading every line of it —
ka59 is 41,463 lines. Mutating the observation is safe by construction:

* the game object never sees a mutated frame — the mutation is applied to a copy, strictly after
  `env.step()` returns;
* the action that reaches the engine is mapped back into the game's own coordinates;
* so the game's state trajectory is a function of the action sequence alone, the level structure and
  the win predicate are untouched, and `baseline_actions` is still the right denominator.

`environment_files/` is SYMLINKED into the snapshot, never copied and never written.

The residual assumption, stated rather than hidden: that the **human** baseline is invariant. For a
colour permutation it is — a human never sees a colour INDEX, only a palette, and a bijection maps a
palette onto another palette of equally distinct colours.

## The measurement — colour permutation, full 25, at `d3247b37`

`--agent unified` @4000 on ceph-build, PAR 8, out of a private snapshot of HEAD.

```
identity (control)          mean 0.9082   reproduces R101SHIPPED on all 25 — zero code drift
cperm    c -> (7c+3) % 16   mean 0.9082   24 of 25 IDENTICAL ACTION FOR ACTION
cperm2   c -> (5c+1) % 16   mean 0.9082   25 of 25 identical action for action
cpermbg  cperm, bg pinned   mean 0.9082   the same lone cd82 difference
```

The only difference in 100 game-runs:

```
cd82   1.0000 -> 1.0000    control [50, 6, 33, 14, 13, 16]
                           mutated [50, 6, 34, 14, 13, 16]      level 3, one extra action
```

Mutation accounting, per arm, all 25 games `applied`, zero violations, zero inert:

```
frames mutated 16,810      cells relabelled 211,464,192      colour alphabet observed 0..15
```

Both permutations are **fixed-point-free**, so every colour any game shows was moved; "identical"
cannot be the luck of which labels happened to swap. `cperm` and `cpermbg` differ only in where the
background goes and produce the SAME cd82 deviation, so cd82's extra action is a colour-ORDER
tie-break, not a dependence on the background value.

⭐ **The mechanism is visible in the source and it is small.** Eight sites under
`src/admorphiq/tools/` order a colour set by its index (`crag`, `gantry`, `decouple` ×2, `ledge`,
`mirror`, `shaft`, `stencil`). And of the **229** numeric `== 0..15` comparisons across the tool set
and harness, not one has a colour-named quantity on its left — they are sizes, counts, indices and
action ids. `base.py` derives the background as the modal value rather than as `0`, and nothing
downstream names a colour. ⚠️ The grep is corroboration; the three flat arms are the evidence.

## Translation: NOT CONSTRUCTIBLE, and the measurement says why

A rigid shift is meaning-preserving only if the board already carries a **uniform margin of at least
the shift on both the leaving and the entering side**. Anything weaker moves content across the
canvas edge: requiring only that the OUTGOING band be uniform background deletes one wall row from a
walled board and leaves the opposite side open — that was the first version of the rule, and it was
wrong.

`scripts/_render_margin.py`, 25-way, each run carrying its own positive control (a synthetic 4-wide
border, which reads 4 in all 25 runs):

```
24 of 25 games: uniform margin 0, at the opening frame AND over a 120-action random walk
tn36 alone:     margin 1
```

**The ARC boards are full-bleed.** They reach the canvas edge on all four sides, so there is nowhere
to pan to.

⛔ **And the one game that could be tried is the reason the refusal path exists.** tn36 under
`shift1`: the per-frame content check passed on all 1,053 frames, and the score fell
**1.0000 -> 0.1071**. It means nothing — four of the agent's clicks landed at y=0, inside the
synthetic band, where no game coordinate exists. `rendergate_compare.py` prints NO VERDICT for it
rather than a 90% transfer loss. A broken mutation and a brittle tool produce the same lower number.

## The identifier rename — the API's own rotation

The ARC Prize API rotates a game's version hash and with it every sprite key, `name=` and
game-specific tag. That rotation broke twelve brittle solvers in April 2026 (CLAUDE.md's v1-vs-v2
table), so it is the transfer question with the longest history here.

`scripts/_render_idrename.py` renames all of them in a private copy and compares **rendered frames**
over a fixed 60-action sequence, not scores. Frames because the tools are frame-only (grep-verified:
nothing under `tools/` or `harness/` reads a sprite name, a tag or a game attribute), so byte-identical
frames prove the rename inert for ANY frame-only agent — a stronger statement than one identical
score, and it costs minutes rather than a full-25 round.

```
14 games render BYTE-IDENTICALLY under a full rename (ar25 bp35 cn04 ft09 g50t lp85 ls20
                                                      re86 s5i5 sk48 sp80 tu93 vc33 wa30)
 1 of those 14 — bp35 — has a FAILING negative control (only one poisonable pixel constant,
                 and the recoloured copy renders identically), so its result is unmeasurable
 1 game  sb26 — first 3 frames identical, then the run ends 57 frames early. That is
                BEHAVIOUR, so the rename is not render-only there: a broken mutation
10 games not constructible, each with a stated reason:
     prefix families    cd82 dc22 ka59 lf52 m0r0 r11l sc25 su15 tn36
     engine vocabulary  tr87  (a sprite key is literally "background")
```

⛔ **TWO EARLIER VERSIONS OF THIS RENAME WERE BROKEN AND BOTH FAILED THE SAME WAY — by renaming PART
of a whole.** The first renamed attribute ACCESSES without their definitions, so `self.foo()` lost
its `def foo` and **all 25 games diverged at frame ZERO**, four of them unable to construct at all.
The second selected keys by a name pattern, which matched 7 of cd82's 13 sprite keys and 26 of
sc25's 50; a partially renamed board splits prefix families (`clcbko-1`, `clcbko-2`), and cd82, sb26
and sc25 came back DIFFERENT for that reason and no reason about the tools.

⚠️ **A column of DIFFERENTs reads as a spectacular transfer failure and was twice a bug in the
instrument.** The tell both times: the divergence was UNIVERSAL and at index 0. A real render
dependence is patchy and late; a broken mutation is total and immediate.

## What this does not prove

⛔ A recoloured board is the SAME BOARD — same mechanic, same geometry, same solution. This rules out
the cheapest brittleness (a tool keyed to a literal colour value or a sprite name) and nothing more.
The evaluation is 110 games with different MECHANICS, and **1.0000 is not a transfer coefficient**.
What it buys: rule 7by's evidence now covers all 25 games rather than 14, and a future tool that
scores well on the card and collapses under `cperm` is caught for the price of one run.

⛔ **AND ONE GAP IS ALREADY NAMED BY MEASUREMENT — rule 7cd, [[r101_zorder-rider]].** A colour
permutation is a bijection, so it preserves WHICH SPRITE IS DRAWN ON TOP, and so would a
translation. The one defect the archive actually found — s5i5 L4, the only level that moves under
7by — is a PAINT-ORDER read: one rider cell the re-render does not draw, and `telescope._begin`
falls back from 2 pinned riders to all 9 bars. Every arm here returns s5i5 identical because none
of them can HIDE a cell. ⚠️ A flat result from this instrument is evidence about colour and naming
and about nothing else. The arm that would close the gap — permuting same-layer draw order — does
not exist in the repository yet, and it is the obvious next build on this axis.

## Artefacts

* `scripts/rendergate.sh`, `scripts/rendergate_run.py`, `scripts/rendergate_compare.py`
* `src/admorphiq/render_mutation.py`, `tests/test_render_mutation.py` (11 contract tests, both
  directions: a structure-reading fake agent must be unaffected, a colour-keyed one must be affected)
* `scripts/_render_margin.py`, `scripts/_render_idrename.py`
* `scripts/rounds/R101RENDERR1/{identity,cperm,cperm2,cpermbg}/games/*.json`
* `scripts/rounds/R101RENDERTNSHIFT/{identity,shift1}/games/tn36.json`
* Rule **7ce** in `OPERATING_RULES.md`

Related: [[r101_shipped-and-transfer]] (rule 7by, the archived re-render), [[r101_inert-actions]].
