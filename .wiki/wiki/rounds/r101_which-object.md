---
round: R101ZOBJECT
axis: which object does the paint-order arm bury in g50t and tu93, and which read consumes it
keywords: [z-order, paint-order, occlusion, g50t, tu93, lattice_maze, clonewalk, exit, steered-piece, maze-sprite, detect, existence-read, broken-mutation, zshuf, zrevall, render-only, tape-replay, expected-case]
verdict: THE TWO ZEROS ARE NOT THE SAME FAILURE AND 7ck HAD THEM BACKWARDS. Both mutations are render-only (each game replays its own tape to the same levels). tu93's dependence is REAL and GENERIC — 6 of 7 sampled re-serialisations destroy it, the maze sprite covers the exit, the steered piece and the crowd, and `parse_board` returns ZERO pieces so `detect` declines the board. g50t's is the ARM'S ARTEFACT — all 8 zshuf seeds change zero pixels and score 1.0000; only arms that reorder an ENGINE-CREATED sprite against the authored list hurt it. `_locate`, the repaired site, is never called. Nothing built, no gate run.
commit: pending
supersedes: corrects two verdicts in [[r101_zorder-mutation]] (rule 7ck)
---

# R101 — which object, and why hiding ONE ends the game

> [[r101_zorder-mutation]] measured fourteen of 25 games depending on paint order and showed that
> burial COUNT does not predict cost — r11l loses 7 sprites of 27 and scores identically, g50t
> loses 1 of 18 and falls to zero. It concluded, correctly, that **what matters is WHICH object**.
> It also recorded two verdicts it could not support: g50t *"not classifiable"* and tu93 *"a broken
> mutation"*. This round names the objects, names the reads, and corrects both verdicts.

## The answer in four sentences

⭐ **Both mutations are render-only** — each game replays its own recorded action tape, under the
patch, to the same levels in the same per-level action counts.

⭐ **tu93's dependence is real and generic**: it is a no-sort game, its single full-board **maze
sprite** covers the **exit**, the **steered piece** and the **crowd** on every level, and **six of
seven** sampled re-serialisations destroy it.

⛔ **g50t's is the arm's artefact**: all eight `zshuf` seeds change **zero pixels** and score
**1.0000**, and only arms that reorder a sprite the **engine created during play** against the
authored list hurt it — something no re-serialisation of a game file can do.

⛔ **And the read is not an identity read.** tu93's `parse_board` returns a board with **zero
pieces**, so `LatticeMazeTool.detect` returns 0 and the tool never proposes; `_locate` — the site
[[r101_visibility-identity-census]] censused and [[r101_dead-reckoning-transfer]] found repaired —
is called **zero times**.

## 0. First, the cheapest hypothesis: is the mutation render-only?

`zorder_mutation.py` argues it structurally — `Camera.render` has one caller, game logic reads
`_raw_render`, click resolution reads `Level._sprites`. ⛔ Rule 7g: that is what is POSSIBLE.
`scripts/_zorder_tape.py` records a game's own action tape and feeds it back through
`score_efficiency.run_game` with a tape adapter, clean and mutated:

```
game  tape   record                          replay-clean   replay-MUTATED
g50t   296   [26,31,64,31,52,49,43]          SAME           SAME
tu93   187   [18,10,19,17,29,28,14,23,29]    SAME           SAME
s5i5   692   [13,30,47,39,32,31]             SAME           SAME    <- cross-game POSITIVE
r11l    83   [4,9,11,14,24,21]               SAME           SAME
```

Same actions, same levels, same counts. ⛔ **"tu93 is a broken mutation" is refuted** — nothing
about either game's mechanic moves. The zeros belong to the tools.

⚠️ **The first version of this probe said the opposite, and the control caught it.**
`AdmorphiqAdapter._convert_action` returns `OfficialGameAction.from_id(id)` — an **enum member, a
singleton** — and then calls `set_data({x, y})` on it. Keeping the returned object keeps ONE object
for every click in the run, all showing the last coordinates. g50t and tu93 (movement games, no
coordinates) replayed perfectly while **s5i5 and r11l scored ZERO LEVELS on the CLEAN engine** —
which reads exactly like "those games are not deterministic". The tape now stores coordinates.

## 1. Which object — tu93

`scripts/_zorder_who.py` paints each authored level with the game's own camera rules and names every
sprite that goes from visible to invisible, plus what covers it. tu93, all nine levels, **46
burials**, and the burier is the level's single full-board sprite every time:

| sprite | shape | colours | on | what it is, per `lattice_maze`'s own grammar |
|---|---|---|---|---|
| `0014mzhhvzrazi` | 3x3 | **[14]** — one flat colour | every level | **the EXIT** — *"the one node painted a flat colour of its own"* |
| `0016ihgrljrgpq` | 3x3 | **[4, 9]** — body + facing mark | every level | **the STEERED PIECE** — the odd one out of the crowd |
| `0018…`, `0032…`, `0040…` … | 3x3 | `[8,15]` / `[12,15]` / `[13,15]` | varies | **the OTHER PIECES** — the crowd, sharing facing-mark colour 15 |

⭐ Those are exactly the three entities the tool's docstring builds its board grammar from, and the
mutation paints the maze over all of them. Level 1 has three sprites and two are buried; that is
7ck's "2 of 3".

**Controls hold**: r11l reports **7** buried (7ck's banked count) and re86 reports **0** on all
eight levels (7ck: *"0 of 19, nothing ever hidden"* — and it still loses 0.0539 of score).

## 2. Which read — an EXISTENCE read in `detect`, not an identity read

`scripts/_zorder_read.py` counts every registered tool's `detect`/`propose` and instruments
`lattice_maze`'s own board parse and `_locate`:

```
tu93 clean       LatticeMazeTool proposes 187/187   parse_none 0  pieces_max 9  locate_calls 187
tu93 zshuf00     identical to clean on every count                                (NEGATIVE control)
tu93 zrevall     LatticeMazeTool proposes ZERO      parse_none 0  pieces_max 0  locate_calls 0
                 GraphSearchTool inherits 468 actions, clears nothing
```

`parse_board` still returns a board — the lattice IS the maze, and the maze is what is now on top —
but with **no pieces at all**. `detect` therefore returns 0 on every frame, the harness never picks
the tool, and the general searcher spends the budget.

⛔ **`_locate` is called ZERO times.** The dead-reckoning repair is not what fails here; it never
gets the board. That closes the branch [[r101_dead-reckoning-transfer]] left open — this is not a
failure of the repair.

⭐ **And it is a NEW shape, not one of the census's five.** 7cd's class is about *choosing among
candidates* when the evidence that would pin one is not drawn. This is about there being **no
candidates at all**: the tool's admission ticket is that the mechanic's entities are visible, and
burying them makes the tool decline a board it can still play. Call it an **existence read**.

## 3. Which object — g50t, and why its zero is the arm's artefact

⭐ **`_zorder_who.py` finds ZERO burial among g50t's authored sprites on all seven levels**, while
the live run under the arm reports `buried_max = 1`. So the buried sprite is **not in the authored
list** — the engine created it during play.

That predicts which arms can hurt g50t, and the prediction is measured. `RandomOrder` (`zshufNN`)
keys each sprite by `(frame first seen, tie-break)`, so everything present when a level opens is
shuffled among itself and **anything created later keeps its arrival order at the end** — exactly
as a re-render of the same file would place it. `zrev` / `zrot` have no such notion:

```
g50t  zrev · zrevall · zrot        11,435 cells changed   buried_max 1   score 0.0000
g50t  zrotall · zshuf00..zshuf07        ZERO cells        buried_max 0   score 1.0000   (9 arms)
      every zshuf arm REORDERED the list on 3,333 of 3,333 renders
```

⛔ The nine harmless arms are not inert instruments — they permute every single frame and still move
no pixel. **The only orderings that hurt g50t are the ones that move an engine-created sprite
relative to the authored list, and a re-serialisation of a game file cannot do that.**

⚠️ **Two burial metrics nearly read as a contradiction.** `_zorder_occlude.py` reports g50t
`total_cells_moved = 39` on the authored boards while `ZOrderPatch` reports `cells_changed = 0`
under every `zshuf`. The first counts **ownership** changes, the second **pixels**, and two sprites
of the same colour swapping owner move no pixel. Both numbers are right and they answer different
questions — `visible_cells`'s own docstring says it paints an owner map deliberately.

## 4. Are the two failures the same? No.

```
tu93 under the arm   the tool DECLINES the board   proposes 0 of 187   -> a routing loss
g50t under the arm   the tool TAKES the board      proposes 25 of 296  -> then withdraws to
                     GraphSearchTool (429) and MazeRunTool (34)
```

Different failures, and only one of them is real. **tu93's is generic** — six of seven sampled
re-serialisations destroy it (0.0667 / 0.0222 / 0.0222 / four at 0.0000, 15,867–66,740 cells
changed) because a no-sort game's raw list order IS its paint order. **g50t's is one arm's
artefact.**

## What this changes about the instrument

⛔ A paint-order arm should model a **re-serialisation of the authored list**. `zshufNN` does;
`zrev` / `zrevall` / `zrot` do not, because they reorder sprites the engine appended during play.
⚠️ So **7ck's headline "14 of 25 games depend on paint order" is a worst-case count and includes at
least one game that no re-render can touch.** The expected-case number is the one the 110 private
games pose, and for these two games it is: tu93 yes, g50t no.

**Nothing was built and no gate was run** — there is no repair here to gate (rule 7o). What tu93
would need is not a perception fix but an admission rule that does not require every entity to be
drawn, and that is a change to `detect` on a game currently scoring 1.0000, which is precisely the
shape 7o exists to stop.

## Artefacts

```
scripts/_zorder_tape.py                          render-only? replay the game's own tape
scripts/_zorder_who.py                           which sprite is buried, and by what
scripts/_zorder_expect.py                        worst case vs expected case, + a permute counter
scripts/_zorder_read.py                          which tool, which read, clean vs mutated
scripts/rounds/R101ZOBJECT/{ztape2,zwho,zexp,zexp2,zread,zoccl2}.jsonl
```

Related: [[r101_zorder-mutation]] (the arm; two of its verdicts corrected here) ·
[[r101_visibility-identity-census]] (the five identity sites — this is a sixth shape, not one of
them) · [[r101_dead-reckoning-transfer]] (`_locate` is never reached, so the repair is not at
fault) · [[r101_zorder-rider]] (s5i5, the cross-game positive control).
