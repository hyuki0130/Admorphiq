---
round: R101VISCENSUS
axis: how many tools identify an object by whether it is DRAWN — the population of the class rule 7cd named from one exemplar
keywords: [visibility, identity, paint-order, z-order, occlusion, census, drawn, fallback, candidate-set, telescope, swivel, blastclock, slotlaunch, tether, lattice_maze, cover_targets, transfer, brittleness, ast-instrument, import-hook]
verdict: THE POPULATION IS NOT ONE — five sites carry 7cd's exact fallback shape (three live on the 25), and the class's worst instance has no fallback at all and was already repaired for the same reason three days earlier. Both arms reproduce all 25 banked scores; no repair built, no gate run.
commit: pending
supersedes: nothing — this is the population count [[r101_zorder-rider]] left open
---

# R101 — the visibility-identity census

> [[r101_zorder-rider]] proved, by intervention, that `TelescopeArmTool` learns which bar carries a
> rider from whether that rider's marker cell survives into the frame, and that one occluded pixel
> costs s5i5 level 4 twenty-two actions. Rule **7cd** turned that into a named CLASS. A class with a
> population of one is a tool repair; a class with a population of many is a doctrine. Nobody had
> counted. This round counts it.

## The answer in three sentences

⭐ **Five sites carry 7cd's exact shape** — a candidate set cut down by what is currently painted,
with a fallback to the unfiltered set — **in four files and three distinct mechanics**, because
`telescope`/`swivel` are the same two lines and `blastclock`/`slotlaunch` are the same two lines
against the same `Piece.clickable`. **Three of the five fire on the 25**; two are unreachable on this
corpus for two DIFFERENT reasons, which is itself a finding.

⭐ **And the fallback is the symptom, not the defect.** The class's most expensive recorded instance
— `lattice_maze.py:484`, which cost that tool **9 levels in 188 actions -> 4 in 1288** on an archived
re-render — has no fallback anywhere in it, carries no word this campaign's vocabulary would match,
and was found and repaired independently on 2026-08-27 without anyone connecting it to 7cd.

## Method: a grep, then a run (rule 7g)

Two instruments, both with their controls compiled in.

**`scripts/_viscensus_ast.py`** — a static census. It looks for three spellings of "filter, then fall
back": `sel if cond else CANDS`, `if cond: sel = CANDS`, and `sel or CANDS`, where `sel` is a
single-generator comprehension over `CANDS`. It then CLASSIFIES the predicate, because the structure
alone is not the defect: `visibility` (membership in a set of cells read off the current frame),
`colour` (rule 7ce's already-measured-harmless class), `remembered` (a property read now compared
for equality against one stored on `self`), `other` (geometry, arity, budget, learned state).

**`scripts/_viscensus_run.py`** — the run. A meta-path finder serves each of those modules from
REWRITTEN source: every site becomes a call that logs which branch was taken and how big the other
one was, then the game is played through `score_efficiency.run_game` — the scorer's own loop, not a
hand-rolled one (rule 7aj#1). A meta-path hook rather than pre-importing by hand because `swivel`
imports from `telescope`, and any hand-ordered install can pull an uninstrumented copy in first.

⛔ **The un-taken branch is evaluated only when it is a pure read.** `harness/loop.py:569`'s fallback
is `self._probe(...)` — a call that acts on the board. An instrument that runs it early to learn its
length has changed the run it claims to observe. Those sites log `unknown` instead.

```
bash scripts/pfan.sh viscen scripts/_viscensus_ast.py 1 "" 1     # the static census
bash scripts/pfan.sh viscrun scripts/_viscensus_run.py 25 "" 8   # the fallback arm, full 25
VIS_SHAPES=all bash scripts/pfan.sh viscf scripts/_viscensus_run.py 25 "" 8   # + filters
```

## The static census — 63 sites

At `HEAD`, over `src/admorphiq/tools/` and `src/admorphiq/harness/`:

```
63 sites total     visibility 18 · colour 27 · remembered 8 · other 10
14 carry the FALLBACK-TO-UNFILTERED structure     (7cd's exact shape)
49 are a visibility / colour / remembered FILTER with NO fallback
```

The fourteen fallback sites, with the predicate that decides them:

| site | predicate | is it a paint read? |
|---|---|---|
| `telescope.py:1183` | `tip_centre(...) in drawn` | ⭐ YES — 7cd's exemplar |
| `swivel.py:734` | `rider_at(self._cfg, i) in drawn` | ⭐ YES — the identical two lines |
| `blastclock.py:631` | `board.pieces[i].clickable` | ⭐ YES, one hop away |
| `slotlaunch.py:755` | `board.pieces[i].clickable` | ⭐ YES — the same two lines, same property |
| `tether.py:413` | `w["pip"] in b["colours"]` | ⭐ YES |
| `tube.py:777` | `len(members) == 1` over colour groups | ⚠️ colour identity, not occlusion |
| `stamppaint.py:197` | `int(g[c]) == fill` | ⚠️ colour read; fallback structurally dead |
| `llm_goal.py:282` | `c["color"] != goal.color` | ⚠️ colour; never runs (the LLM draw 404s) |
| `graph_search.py:907` | `not deadsig.globally_dead(...)` | no — learned state |
| `dead_signature.py:164` | `not self.is_dead(...)` | no — learned state |
| `keymaze.py:416` | `a in unknown` | no — probe memory |
| `slotlaunch.py:679` | `c not in tried` | no — attempt memory |
| `loop.py:569` | `self._legal(...)` | no — legality |
| `blastclock.py:260` | `(was[r] != now[r]).any()` | no — a near-miss; not a fallback at all |

⚠️ **NOT IN THIS COUNT, AND DELIBERATELY SO: rule 7ce's eight colour-ORDER sites** — `crag`,
`gantry`, `decouple` x2, `ledge`, `mirror`, `shaft`, `stencil`, each of which orders a colour SET by
its index. 7ce measured them with two fixed-point-free colour permutations over the full 25 and
exactly ONE action moved in the whole corpus. Colour ORDER is not visibility: a permutation is a
bijection and preserves which sprite is on top. **The evidence this class destroys is not a colour,
it is a cell that is not there.** Where those files appear below it is for a DIFFERENT line.

⛔ **`clickable` is the one the vocabulary cannot see.** It is `bool(Piece.marks)`, and
`slotlaunch._marker()` builds `marks` by reading the piece's CENTRE PIXEL out of the frame — *"the
colour a piece wears at its own MIDDLE, when that is not the colour it is made of"*. So
`blastclock.py:631` and `slotlaunch.py:755` are 7cd's shape exactly, and a classifier keyed on names
puts both in `other`. **The automated arm found 3 of the 5; the other 2 came from reading.** That is
the census's false-negative rate on the part of it that can be checked.

## The run — full 25, `--agent unified` @4000, on ceph-build

⭐ **Both arms reproduce every banked `R101SHIPPED` score, 25 of 25, `BANKED_MISMATCH` false
everywhere** — bp35 0.24556 · lf52 0.272727 · s5i5 0.583333 · dc22 0.714286 · ls20 0.912085 · lp85
0.97668 · nineteen at 1.0000, mean 0.9082. The rewriting is behaviour-neutral, which is what makes
the counts below counts of the real run.

### Arm 1 — the fallback sites

```
site                 game   eval  filter  fallback  narrowed  same  widest
telescope.py:1183    s5i5      5       5         0         4     1   1 <- 9    ⭐ POSITIVE CONTROL
swivel.py:734        s5i5      2       2         0         2     0   1 <- 6
blastclock.py:631    ka59     33      24         9        14    19   1 <- 2
slotlaunch.py:755      —       0       —         —         —     —   never evaluated
tether.py:413          —       0       —         —         —     —   never evaluated
tube.py:777          sk48      9       9         0         1     8   1 <- 3
stamppaint.py:197    cd82    184     184         0       184     0   fallback NEVER fires  ⭐ NEGATIVE
keymaze.py:416       ls20      4       3         1         1     3
graph_search.py:907  bp35   1699    1534       165      1083   616   1 <- 14
graph_search.py:907  lf52    162     162         0         0   162
loop.py:569         all 25   7049    6979        70        70     0   counterfactual not measurable
dead_signature.py:164  —       0       —         —         —     —   never evaluated
llm_goal.py:282        —       0       —         —         —     —   never evaluated
slotlaunch.py:679      —       0       —         —         —     —   never evaluated
```

⭐ **The positive control lands on the known answer.** 7cd's own table for the LIVE board reads
`bars 2 4 4 9 5` against `riders 2 1 2 1 2` — four levels where the drawn rider narrows the choice
and one (level 1) where it does not. The instrument reports exactly that: five evaluations, four
narrowed, widest 9 -> 1.

⛔ **"NEVER EVALUATED" IS TWO DIFFERENT FINDINGS.** The instrument also counts `propose()` per tool
class, and they separate cleanly: **`SlotLaunchTool` never proposes on any of the 25** (it is
registered — `registry.py:116` — and simply never wins a board), while **`TetherCentroidTool`
proposes 6 times on r11l** and does not reach line 413. Likewise `LLMGoalTool` proposes 8 times on
lf52 and never sets a goal, because the harness's model draw 404s in this environment.
⚠️ Neither is evidence that the site is harmless. It is evidence that THIS CORPUS cannot measure it,
and on 110 private boards the tools that never win here are exactly the ones that might.

### Arm 2 — visibility filters with NO fallback

49 static, **39 evaluated on at least one game**. The discriminator is not "does it narrow" — nearly
every filter does — but how: cutting MANY candidates to exactly ONE is an identity assigned from
paint; cutting to ZERO is the object lost, with nothing to soften it.

```
site                       games   eval    -> exactly ONE   -> ZERO
lattice_maze.py:484        tu93     187            163           0     ⭐
cover_targets.py:393       re86    1669            693         856
cover_targets.py:457       re86     886            316         553
cover_targets.py:644       re86     409            327           0
crag.py:1352               bp35     204             70         134
sigilgate.py:602           sc25     145             35          68
reforge.py:507           8 games    291             23          63
sluice.py:957              sp80      23             11           0
tether.py:805 / :327       r11l      22             12           2
stencil.py:374           7 games     17              5           6
cover_targets.py:854       re86     232              0         105
decouple.py:396            m0r0 1141854              0        1114
```

⚠️ **That is an EXPOSURE MAP, not a defect list.** A filter that cuts to zero is very often giving
the right answer — "nothing of that kind is on this board". What the map bounds is where the class
COULD bite, and it is much wider than the fallback structure suggests.

## The finding that changes the scope

⭐ **`lattice_maze.py:484` is the class's worst recorded instance and 7cd's shape cannot see it.**

```python
same = [c for c, (body, _) in board.pieces.items() if body == self._body]
```

No fallback. No word any vocabulary would match. Its own docstring carries the measurement, taken
2026-08-27 on that game's archived re-render:

> *"the maze sprite is drawn at a different z-order in the two renders, so it COVERS that second
> piece on one copy and not on the other … The board went from 9 levels in 188 actions to 4 in
> 1288."*

That is a **6.9x** action blow-up against telescope's 1.56x, and it is a game currently at 1.0000. It
still scores 1.0000 because it was already repaired — identity is now dead-reckoned from the last
known node plus the known effect of the action spent, and the colour read is only a disambiguator.
**The repair predates rule 7cd by three days and was never connected to it.** On the run it fires
187 times on tu93 and pins one candidate out of up to nine on 163 of them.

⛔ It was recovered only after adding a STRUCTURAL arm — a predicate comparing something read now
for equality against `self._<remembered>` — because the vocabulary arm scores it `other`. Two
independent sub-shapes, then: *"is it drawn where I expect"* and *"is its colour still the one I
remember"*, and only the first has a word for it.

## Sites the class has already learned to survive

Three more, found by reading, all mitigated and all worth keeping visible because they show what a
repair looks like:

* `telescope.py:1278` — the model verifier checks **only the drawn riders**, guarded by
  `if marks is not None`: *"On a board that paints its riders under their bars there are none to
  check, and demanding a match there is the same mistake as demanding one to detect the board."*
* `cover_targets._at_the_wheel` — *"Only a hint: the cell is invisible when it happens to lie under a
  mark. What actually moved always wins."* The paint read is demoted below motion evidence.
* `slotlaunch._held` — which piece the board holds, from a unique drawn marker; **returns `None` when
  ambiguous** and the plan pays for one explicit click rather than guessing. Widening costs one
  action instead of a search.

⭐ **All three do the same thing: keep the paint read as EVIDENCE and refuse to let it be IDENTITY.**
That is the shape of any repair, and it is not what removing a filter does.

## No repair, and rule 7o is the reason

⛔ Nothing was built and no gate was run. 7cd already measured the counterfactual: the unfiltered
fallback fires on all five archived levels and costs NOTHING on four of them, so deleting the filter
takes the tool to the unfiltered set everywhere — which IS the 61-action behaviour. A repair here
means discriminating between candidate pairings with something cheaper than the pairing's own plan,
on five sites in three mechanics, and four of the five levels it would touch are already optimal.

What this round changes is the SCOPE: it is not one tool, the worst case is not the exemplar, and
any repair must be gated with `snapgate.sh` on the full 25 plus `xfergate.sh` for s5i5, with the five
at-exactly-human canaries (re86 L2/L6, sc25 L2, tu93 L7/L8) holding.

## What the instruments cost, in both directions (rule 7z)

⛔ **TWO MORE INSTRUMENTS THAT LIED TOWARD "THERE IS NOTHING HERE"**, the ninth and tenth of this
campaign, and the second one is the more expensive kind.

1. **The static detector's first version returned ZERO over the whole tool set — including its own
   exemplar.** It compared raw source text, and `swivel.py:734` iterates `range(len(reading.bars))`
   while falling back to `list(range(len(reading.bars)))`. Had the exemplar not been transcribed in
   as a control, the reported answer would have been *"the population is one"* — which is what the
   round was expected to find, so nothing would have questioned it.
2. **The comprehension arm injected `_VIS` and `_VISOR` into the rewritten modules and not `_VISF`.**
   Every wrapped comprehension raised `NameError` inside tools that catch `Exception` broadly, so
   they proposed nothing and **eleven games scored ~0.0 while the run reported cleanly** — cd82
   0.0064, ft09 0.0, ls20 0.0, m0r0 0.0, re86 0.0, sc25 0.0, vc33 0.000018. A column of collapsed
   scores reads as a spectacular brittleness result. It was caught only by comparing every game to
   its banked number, which is now a `BANKED_MISMATCH` field computed inside the instrument against
   `scripts/rounds/R101SHIPPED/games/*.json` rather than a habit somebody has to remember.

**Controls, in both directions, compiled in.** `selftest()` refuses to census at all unless it scores
7cd's exemplar, swivel's differently-spelled twin and lattice_maze's vocabulary-free predicate, and
unless a fallback with a *geometric* predicate comes back classed `other`. The negative that RUNS is
`stamppaint.py:197`: 184 evaluations on cd82 and its fallback fires **zero** times, exactly as its
structure requires — the filter colour IS that region's modal colour, so the filtered list can never
be empty. And **29 of the 59 modules under `tools/` carry no site of any class**, so **18 of the 25
games report only the harness's own `loop.py:569`** — ar25, cn04, dc22, ft09, g50t, lp85, m0r0, r11l,
re86, sb26, sc25, sp80, su15, tn36, tr87, tu93, vc33, wa30. A tool without the shape comes back
clean, which is the other half of the control an all-clean fan cannot supply on its own.

## Artefacts

```
scripts/_viscensus_ast.py                        the static census, controls compiled in
scripts/_viscensus_run.py                        the import-time rewriter + run
scripts/rounds/R101VISCENSUS/static_census.jsonl 63 sites
scripts/rounds/R101VISCENSUS/fallback_arm.jsonl  25 games, the 14 fallback sites
scripts/rounds/R101VISCENSUS/filter_arm.jsonl    25 games, + the 49 no-fallback filters
```

Related: [[r101_zorder-rider]] (the exemplar, proved by intervention) ·
[[r101_render-mutation-transfer]] (colour permutation is inert; a colour bijection preserves which
sprite is on top, so `rendergate.sh` cannot catch this class) ·
[[r101_shipped-and-transfer]] (24 of 25 games identical on a re-render — the floor this class bounds)
· [[r101_owner-ablation]] (what an unseen game's floor looks like when no tool claims the board).
