---
round: R101ZORDER
axis: name the one render-dependent read left in the whole 25 — why s5i5 level 4 costs 22 more actions on a re-render
keywords: [transfer, re-render, archived-hash, s5i5, telescope, swivel, rider, z-order, paint-order, occlusion, brittleness, generalisation, xfergate, oracle-intervention]
verdict: NAMED AND PROVED BY INTERVENTION — the tool reads object identity out of PAINT ORDER. One occluded pixel on level 4's opening frame turns a pinned rider into nine candidate bars; injecting the rider evidence back, and nothing else, returns the level to 39 actions and the game to 0.5833. No repair shipped, and the reason is measured.
commit: pending
supersedes: nothing — this is the follow-up [[r101_shipped-and-transfer]] asked for
---

# R101 — the twenty-fifth game: z-order as evidence

> [[r101_shipped-and-transfer]] measured that twenty-four of twenty-five games are action-for-action
> IDENTICAL on an archived re-render, and that exactly one level of one game moves: s5i5 L4, 39 ->
> 61 actions, still clearing. This round is what that level is made of. It matters far more than the
> 0.024 of dev score it represents, because it is the only place in the whole sample set where
> render-dependence is measurable at all — and the eval is 110 boards rendered like nothing here.

## The answer in one sentence

⭐ **A frame-only tool that identifies an object by whether it is DRAWN is reading paint order, not
mechanics.** `TelescopeArmTool` learns which bar carries the rider it must deliver from whether that
rider's marker cell survives into the frame. The archived serialization lists the rider before the
bar it rides, the bar paints over it, and the tool loses the only evidence it had — so it guesses
among every bar and pays for the wrong guesses in clicks it has already spent.

## The three hypotheses, enumerated first and fanned together (rule 7h)

| | hypothesis | verdict |
|---|---|---|
| H1 | nondeterminism — the count varies run to run and there is no defect | ⛔ **REFUTED.** `scripts/_s5i5_xfer.py`, three runs per board: live `[13,30,47,39,32,31]` 3/3, archived `[13,30,47,61,32,31]` 3/3. Both boards are deterministic and they differ by exactly 22 actions on one level. |
| H2 | the rider set — identity read from whether the rider is drawn | ⭐ **CONFIRMED**, and proved by intervention below. |
| H3 | something else in the reading — bars, destinations, marker colour, widget order | ⛔ **REFUTED.** Both boards read the same marker colour (13), the same widget count, the same piece count and the same **nine bars** on the level in question. |

## The board is identical by construction

`scripts/_s5i5_srcdiff.py` canonicalises both `s5i5.py` files with the names taken away — each
sprite replaced by a signature of its own pixels and flags, each level by the (signature, position)
list it places:

```
sprites: live 92  arch 92        art signatures identical as a SET: True
L1..L8:  same_placements = True  on every level;  same_LIST_ORDER = False on every level
```

Same art, same positions, same `Children` links, same `StepCounter`. **Only the order of the sprite
list differs** — the archived file names its sprites differently and lists them alphabetically. That
is not cosmetic: `arcengine.Camera.render` sorts by `layer` with a STABLE sort, so within a layer
the list order IS the z-order.

## What that costs, at the pixel

The opening frame of each level, dumped from **the layer the tools actually read**
(`_layers(obs)[-1]`, not `frame_2d`) and compared cell by cell:

```
level 1: 2 cells differ   marker cells live=10 arch=8
level 2: 1 cell           live=5  arch=4
level 3: 2 cells          live=10 arch=8
level 4: 1 cell           live=5  arch=4     <- (43,31): live 13 (marker), arch 11 (a bar)
level 5: 6 cells          live=10 arch=4
```

⭐ **On the level that costs 22 extra actions, exactly ONE cell of the board differs**, and it is the
rider, painted over by the bar that carries it.

## What the tool does with it

`telescope.py:1179`, which is what plays s5i5's first six levels — `swivel` delegates to it on every
level with no one-way control (measured from inside the loop: `owners` says `swivel` for all six,
and `SwivelArmTool._begin` never fires below level 5):

```python
pinned = [b for b in bars if tip_centre(self._pieces[b[0]].box, b[1]) in drawn]
riders = pinned if len(pinned) >= len(m.places) else bars      # else: EVERY bar is a candidate
```

`scripts/_s5i5_tele.py`, both boards, levels 1-5:

```
             drawn riders   bars      riders used   plans      pairings refuted   actions
live           2 1 2 1 2    2 4 4 9 5   2 1 2 1 2   1 1 1 1 1     0 0 0 0 0       13 30 47 39 32
arch           0 0 0 0 0    2 4 4 9 5   2 4 4 9 5   1 2 1 9 2     0 1 0 4 0       13 30 47 61 32
```

⭐ **THE CONTRAST IS THE FINDING** (rule 7b). The fallback fires on **all five** levels of the
archived board and is **free on four of them** — level 2 even has a pairing refuted and still lands
on 30 actions, the same as live. It costs only where the candidate set is large: nine bars for one
destination, five pairings tried, four knocked down by the board, and each refuted pairing's plan
had already been clicked.

## The proof: change that one fact and nothing else

`scripts/_s5i5_oracle.py` — three runs in ONE process, same planner, same budget, same boards. On
the archived arm the rider cells the live board draws are put back into `read_markers`'s `movers`
**for the duration of `_begin` only** (`_agrees` re-checks drawn movers against the model's own
predictions on every action, so injecting there would be feeding the verifier its answer):

```
live,  recording        [13, 30, 47, 39, 32, 31]   0.583333
arch,  untouched        [13, 30, 47, 61, 32, 31]   0.559296    <- the control reproduces the gate
arch,  riders injected  [13, 30, 47, 39, 32, 31]   0.583333    <- the whole gap, gone
```

and the rider set the tool ends up holding on the level in question:

```
live    1 rider,  tip (43,31)
arch    9 riders, tips (22,46) (16,52) (13,52) (16,10) (19,46) (25,19) (43,31) (28,19) (19,10)
oracle  1 rider,  tip (43,31)
```

## No repair, and the price of one

⛔ **This is not a bug in the tool and there is no one-line fix.** Its own docstrings already say
riders are optional evidence and that the pairing is a hypothesis the board must knock down;
`_targets` already chooses by FEASIBILITY rather than proximity and already retires refuted pairings
cheapest-first. On the archived board the rider is genuinely absent from the frame, so the guess
cannot be avoided — only its PRICE can, by discriminating between candidate pairings with something
shorter than the pairing's own full plan. That is a redesign, it has to be gated on the full 25, and
four of the five levels it would touch are already optimal (rule 7o: a measurement of a MECHANISM
does not license a change of BEHAVIOUR).

## Why this is worth more than 0.024

⚠️ The dependence is **quantitative, not binary**: the same tool, missing the same evidence, is free
at two candidates and costs 22 actions at nine. Nothing bounds the candidate count on a board we
have never seen. ⛔ So [[r101_shipped-and-transfer]]'s ratio of 0.9989 is a floor measured where the
candidate sets happen to be small, not a forecast — and any tool carrying the shape *"where it IS
drawn it pins the choice for free; where it is not, everything is a candidate"* has this exposure.
`swivel._begin` carries the identical two lines and its own comment naming the archived re-render.

⛔ **AND [[r101_render-mutation-transfer]]'s `rendergate.sh` CANNOT CATCH THIS ONE** — which is the
natural place to assume it does, since it manufactures a re-render for all 25 games where only 15
have an archived one. It permutes colours and renames identifiers on the OBSERVATION, and a colour
permutation is a bijection: it preserves which sprite is on top. The evidence this defect destroys
is not a colour, it is a cell that is not there. A mutation that would catch it has to change the
PAINT ORDER, and nothing in the repository does that yet.

⚠️ **The instrument nearly lied, in the usual direction.** The first frame dump read `frame_2d`
(layer 0) where every tool in this family reads the LAST layer, and reported ten differing marker
cells on the level whose true difference is one — a plausible number for a quantity it was not
measuring (rule 7z). It was caught because the tool's own reader said `movers=1` where the dump
implied two destinations.

Rule: **7cd**. Probes: `scripts/_s5i5_xfer.py`, `scripts/_s5i5_owner.py`, `scripts/_s5i5_tele.py`,
`scripts/_s5i5_oracle.py`, `scripts/_s5i5_srcdiff.py`, `scripts/_s5i5_framecmp.py`.

## Follow-up: the population of the class

⭐ **[[r101_visibility-identity-census]]** answers the question this round left open — *how many
tools read identity from visibility?* **Not one.** Five sites carry this exact shape (three of them
firing on the 25), `swivel.py:734` is the identical two lines, `blastclock.py:631` and
`slotlaunch.py:755` are the identical two lines against a `clickable` property that reads a piece's
centre pixel — and the class's **most expensive** recorded instance, `lattice_maze.py:484`, has no
fallback at all and cost that tool **9 levels in 188 actions -> 4 in 1288** on its own archived
re-render, a 6.9x blow-up against the 1.56x measured here. Rule **7cl**.
