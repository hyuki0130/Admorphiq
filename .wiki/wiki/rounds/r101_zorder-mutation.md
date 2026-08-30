---
type: round
round: R101ZORDER
axis: generic-tools
keywords: [z-order, paint order, draw order, occlusion, sprite list order, transfer, re-render, render mutation, zordergate, zrev, zrevall, instrument validity, refusal path, positive control, s5i5, tu93, g50t, sc25, re86, camera _raw_render]
verdict: BUILT AND MEASURED — the paint-order arm exists, reproduces its known positive exactly (s5i5 L4 39 -> 61), and finds FIVE games that move. re86 is a clean transfer failure (nothing hidden, every level still cleared, 200 extra actions). tu93 is a broken mutation (2 of 3 sprites buried). g50t and sc25 collapse and are NOT classifiable from this evidence. Ten of 25 games cannot exhibit the class at all.
commit: 97aa7b07
---

# R101ZORDER — the mutation that changes which sprite is on top

> Rule **7cd** named the corpus's only measured transfer defect and ended by saying the arm that
> would catch it *"does not exist in the repository yet"*. It does now. **Identity control 0.9082 on
> all 25, reproducing `R101SHIPPED` exactly; the arm reproduces rule 7cd's banked answer on s5i5 to
> the action; five games move and they do not move for the same reason.**

## Why the question was asked

[[r101_render-mutation-transfer]] manufactures a re-render by permuting COLOURS, and the tools are
flat under three independent permutations. ⛔ But a colour bijection **preserves which sprite is
drawn on top**, and a translation does too — so the one defect the campaign has actually measured
([[r101_zorder-rider]], rule 7cd: s5i5's L4 costs 22 extra actions because the archived board lists
the rider before the bar it rides, hiding one cell) is invisible to the newest instrument by
construction. That gap was named in 7ce's own closing paragraph and this round closes it.

## What was built

`scripts/zordergate.sh` + `scripts/zordergate_run.py` + `src/admorphiq/zorder_mutation.py`
(15 contract tests), plus two probes: `scripts/_zorder_census.py` (population) and
`scripts/_zorder_occlude.py` (what a permutation buries).

```
bash scripts/zordergate.sh z2 "identity zrev zrevall zrotall" 10 4000   # the scored round
bash scripts/zordergate.sh z3 "identity zrevall" 10 4000                # + burial accounting
bash scripts/pfan.sh zcensus scripts/_zorder_census.py 25 "" 8          # the population
```

⚠️ Z3 exists because the burial accounting was added after Z2 and a code change must be shown inert
before its output is read: **Z3's `zrevall` scores are identical to Z2's on all 25 games**, and its
identity arm reproduces `R101SHIPPED` again.

⭐ **VALIDITY IS ONE LINE OF THE ENGINE, AND THAT IS THE POINT.** Paint order is not observable —
it is an engine decision — so unlike the colour arm this mutation cannot live at the observation
boundary. It is installed on **`Camera.render`**, which has exactly ONE caller inside arcengine:
`base_game.perform_action` (base_game.py:232), whose return value is the observation frame.

| what a game could read the picture with | where it goes | mutated? |
| --- | --- | --- |
| the observation frame | `Camera.render` ← `perform_action` | **yes** |
| `BaseGame.get_pixels` (game logic asking "what colour is here") | `camera._raw_render` | no |
| click resolution `Level.get_sprite_at` | `Level._sprites`, sorted by layer | no |
| collision `Level.collides_with` | `Level._sprites` | no |

So the game's state trajectory stays a function of the action sequence alone, and no coordinate
conjugation is needed — the mutation moves no pixel to a different place, it only changes which of
two co-located sprites is visible there.

⭐ **AND THE HUMAN DENOMINATOR IS INVARIANT BY MEASUREMENT, NOT BY ARGUMENT.** The two s5i5
serializations differ ONLY in list order (`scripts/_s5i5_srcdiff.py`: same art, same positions, same
`Children`, all eight levels) and ship the IDENTICAL `baseline_actions`
`[20, 89, 106, 54, 162, 38, 86, 83]`. The competition's own re-render of this board changed the paint
order and did not change the human count.

## ⛔ The first arm failed its own positive control, and the reason is a fact about three games

The brief's rule was **permute SAME-LAYER siblings only** — cross-layer reordering changes an
authored property, same-layer reordering only changes which of two co-located sprites wins a pixel.
That arm ran clean and scored s5i5 **identical action for action**. It had measured nothing.

`scripts/_s5i5_zprobe.py`, painting the way s5i5's own camera paints:

```
level      1    2    3    4    5    6    7    8
same-layer reversal, cells changed   0    0    0    0    0    0    0    3
whole-list reversal, cells changed   2    1    2    1    6    1    6    4
live vs ARCHIVED, cells differing    2    1    2    1    6    1    5    3
   and L4's single cell is (43,31), live 13 -> archived 11   <- rule 7cd's own finding
```

⭐ **s5i5, tu93 and wa30 override `Camera._raw_render` with a version that never sorts.** For those
three the raw list order IS the z-order and `layer` decides nothing about the picture — s5i5's rider
and its bar are on DIFFERENT declared layers, which is why the conservative arm could not reach them.

⭐ **And the wider scope is not wider on the other 22.** `_raw_render` filters by visibility
(order-preserving) then applies a STABLE `sorted(key=layer)`, so a whole-list permutation can only
ever change the order WITHIN a layer there. The round runs both arms so the equality is measured:
**`zrev` and `zrevall` differ on exactly two games — s5i5 and tu93 — and both are no-sort games.**
Twenty-two layer-sorting games agree between the two scopes, action for action.

## The two controls

| control | requirement | result |
| --- | --- | --- |
| negative — `identity` arm | reproduce `R101SHIPPED` at this commit | **0.9082, all 25 identical, zero drift** |
| positive — s5i5 is the known answer | L4 must go 39 -> 61 when the rider goes under the bar | **`[13, 30, 47, 61, 32, 31]` vs control `[13, 30, 47, 39, 32, 31]`, 0.5833 -> 0.5593** |

Every other level of s5i5 is action-for-action identical, exactly as rule 7by measured on the real
archived board. An arm that cannot score its own known positive has measured nothing, and this one
scores it to the action.

## 1. The population: how many of the 25 can exhibit this at all?

`scripts/_zorder_census.py`, 25-way, both controls passing on all 25 (a synthetic same-layer
overlapping pair must read 1, the same pair on different layers must read 0). It counts Z-SENSITIVE
pairs — overlapping opaque pixels AND a colour disagreement somewhere in the overlap, because two
identical sprites stacked on each other render the same either way.

**Statically, on the authored boards: 8 games carry same-layer z-sensitive pairs** — ka59, r11l,
re86, s5i5, sc25, su15, tn36, tu93 — 19 carry them ignoring layer, and 6 carry none at all (bp35,
cn04, lf52, lp85, m0r0, sp80).

⛔ **The static count is a LOWER BOUND and the dynamic one is the authority.** g50t reads 0
same-layer pairs on every authored board and yet the mutation changes **586 of its 2,852 rendered
frames**: its exposure is created at runtime. Conversely bp35 reads 0 because it builds its board
from a module-level table rather than from `levels` — the hole `dump_sample_levels.py` already
documents. The live run's own `frames_changed` is what the verdict uses.

**Dynamically, over the full 25 at 4,000 actions:**

```
applied  14 games — the mutation re-painted at least one frame
inert    10 games — ar25 bp35 cn04 ft09 lf52 lp85 ls20 m0r0 sp80 wa30
                    NOT ONE frame of these games depends on paint order; they CANNOT exhibit it
partial   1 game  — sb26 calls Camera.render itself, as game logic (see the refusal path)
```

⭐ **So the class has population 14 on this corpus, not one.** The most useful sentence available was
going to be "only s5i5 has overlapping pairs, so the public 25 cannot measure this" — it is not the
answer. Fourteen of twenty-five public games render at least one frame whose picture depends on the
order their sprites are listed in.

## 2. The full 25 under the mutation

Identity control 0.9082 (reproduces `R101SHIPPED`, zero drift). Movers under `zrevall`:

| game | control | mutated | levels | per-level actions | buried live | reading |
| --- | --- | --- | --- | --- | --- | --- |
| re86 | 1.0000 | 0.9461 | 8 -> 8 | L2 42 -> **242**, L4 59 -> **54** | **0 of 19**, 22 samples | **TRANSFER FAILURE** |
| s5i5 | 0.5833 | 0.5593 | 6 -> 6 | L4 39 -> **61** | 4 of 20 (L4's is 1 cell) | **TRANSFER FAILURE** (rule 7cd) |
| sc25 | 1.0000 | 0.4762 | 6 -> **4** | L5, L6 stop clearing | 2 of 42 | **CANNOT TELL** |
| g50t | 1.0000 | 0.0000 | 7 -> **0** | L1 never clears | **1 of 18** | **CANNOT TELL** |
| tu93 | 1.0000 | 0.0000 | 9 -> **0** | L1 never clears | **2 of 3** | **BROKEN MUTATION** |

The other nine applied games — cd82, dc22, ka59, r11l, sk48, su15, tn36, tr87, vc33 — are identical
action for action with the mutation demonstrably live on them (r11l 350 changed frames, sk48 408,
su15 342, tn36 109, tr87 196, cd82 156, dc22 121, ka59 208, vc33 18).

### ⭐ Burial does not predict score loss — the two games that lose everything hide the LEAST

`_buried()` decides visibility with the camera's OWN painter (a sprite is visible when removing it
changes the picture), sampled every 40th changed frame during the real run. Read the whole column at
once, because the pairing is the finding:

```
game   sprites  buried_max  fraction   score
r11l      27         7        0.26     1.0000 -> 1.0000   identical action for action
tn36     101         6        0.06     1.0000 -> 1.0000   identical action for action
sk48      59         5        0.08     1.0000 -> 1.0000   identical action for action
s5i5      20         4        0.20     0.5833 -> 0.5593
tu93       3         2        0.67     1.0000 -> 0.0000
sc25      42         2        0.05     1.0000 -> 0.4762
g50t      18         1        0.06     1.0000 -> 0.0000
re86      19         0        0.00     1.0000 -> 0.9461
```

⛔ **Three games have objects removed from the picture entirely and do not lose one action.** r11l
loses SEVEN sprites of twenty-seven and plays the identical game. So "the mutation hid something,
therefore the board is broken" is refuted as a general rule, and the burial count cannot be used on
its own to dismiss a mover. It is only decisive at the extremes — at 0 (nothing was hidden, so the
loss is the tool's) and at 0.67 of a three-sprite board.

### re86 — the clean result, and the one worth acting on

Every level still clears, **nothing is buried on any sampled frame of the whole run** (0 of 19, 22
samples, first change at frame 27), and L4 comes back FIVE ACTIONS FASTER — which rules out "the
board got harder". The static probe agrees: 0 sprites lost, 11 cells relocated across all eight
authored boards. The same information is present, painted differently, and level 2 costs **200 extra
actions** for it. That is a tool reading paint order with nothing else wrong, and it is the round's
one unambiguous defect.

### tu93 — a broken mutation, said plainly

tu93's level 1 holds **three sprites** and the mutation buries two of them from frame one; the static
probe says the same for all nine levels (2 of 3, 3 of 4, 5 of 6, ...). At 0.67 of the board it is
2.6x the next-highest fraction, and no shippable re-render can hide most of a game's contents and
stay playable. **NO VERDICT for tu93** — 1.0000 -> 0.0000 there is a property of the mutation. ⚠️ The
conservative `zrev` arm also breaks it (0.2222), because tu93's camera does not sort and even a
same-layer permutation reorders its picture.

### sc25 and g50t — where the evidence stops, and which way it leans

Both collapse and neither can be classified, but the burial column argues AGAINST "the board was
destroyed": g50t never loses more than **one sprite of eighteen** on a sampled frame and goes to
zero, while r11l loses seven of twenty-seven and does not move. sc25 loses at most two of
forty-two — and the static probe locates them exactly: **one 4-cell sprite on level 5 and one on
level 6, which are precisely the two levels that stop clearing.**

What is missing in both cases is whether the level remains solvable with that sprite hidden. Until
that is measured, "the tool depended on paint order" and "the board lost its only evidence" are both
consistent with the number, and rule 7cd's reading of s5i5 is the reminder that the second can be
true: on the archived board the rider is genuinely not in the frame, so the guess is unavoidable and
only its PRICE belongs to the tool.

⚠️ g50t is the sharper unknown for a second reason: its authored boards show **zero cells moved on
level 1** and nothing buried anywhere, yet level 1 stops clearing and 586 of its 2,852 frames change,
the first at frame 48. Its exposure is created at runtime by sprites the static census cannot see.

## 3. What this does NOT say

⛔ A re-painted board is the SAME BOARD with the same mechanic, the same geometry and the same
solution. This rules out one more cheap brittleness — a tool keyed to which of two overlapping
sprites happens to be drawn — and nothing more. The evaluation is 110 games with different
MECHANICS. ⛔ **No ratio from here is a transfer coefficient.**

⚠️ And this arm is weaker than the colour arm in one specific way that must not be lost: a colour
bijection destroys no information, while hiding a sprite under another one DOES. That is why the
burial accounting exists and why two of the five movers get no verdict.

## 4. Two instrument failures paid for in this round

⛔ **The diff rendered twice through `Camera.render`, and `render` runs the camera's INTERFACES.**
bp35 and lf52 draw their whole board from an interface and hold a SINGLE level sprite — a permutation
of a one-element list is the identity — yet the first run reported **272,208 and 102,399 changed
cells** for them, and lf52 came back **two actions faster**. That delta was the extra interface pass.
The diff now goes through `_raw_render`, which builds a fresh array from sprite state and runs no
interface, and the painter's determinism is CHECKED on the first frame rather than assumed. After the
fix both games are correctly `inert` and lf52 is identical.

⛔ **A camera detector fired on its own reference class.** "Is there a `Camera` subclass overriding
`_raw_render`" matched the imported `Camera` itself — `Camera.__dict__` naturally contains
`_raw_render` — so it answered "does not sort by layer" for ALL 25 games and the occlusion probe
happily printed counts painted in an order 22 of them never use. Rule **7z**'s family: a plausible
number for a quantity it is not measuring.

⚠️ **And ceph-build's `environment_files` holds a `._<game>.py` beside every real one** (a macOS tar
artefact — CLAUDE.md warns about it for file-list diffs). It sorts FIRST, it is binary, and importing
it raises `source code string cannot contain null bytes`. The census's first run came back with 24 of
25 games erroring, which reads exactly like "the games cannot be read".
`scripts/dump_sample_levels.py` picks its source the same way and has the same hole.

## The refusal path

`rendergate_compare.py` (shared with the colour arm) reports NO VERDICT for three states, and they
are not decoration — 10 of 25 games land in them:

* **inert** — the mutation changed no cell of any frame. An identical score there says nothing about
  the tools; it says the board has no contested pixel.
* **partial** — the game calls `Camera.render` ITSELF as game logic. sb26 does, eight times: it
  snapshots the render into a sprite's pixels. Mutating that call would change what the game STORES
  rather than what the agent SEES, so the instrument refuses it and the board is then partly mutated
  and partly not — rule **7ce**'s all-or-nothing lesson, which was learned when a partial rename made
  three games diverge for a reason about the instrument.
* **invalid** — the permutation lost or gained a sprite, or the game's own painter is not
  deterministic.

## Open work

1. **g50t** — find the runtime sprite whose paint order the tools depend on. `frames_changed` says
   586 of 2,852; the static census says nothing moves on the authored boards.
2. **sc25** — decide whether levels 5 and 6 are solvable with the 4-cell sprite hidden. Until that is
   measured its 1.0000 -> 0.4762 is not attributable.
3. **re86 L2** — the only mover that is unambiguously the tools' problem, and it is worth 200
   actions on one level. ⛔ Rule **7o** stands over any repair: a measurement of a MECHANISM does not
   license a change of BEHAVIOUR, and any fix is gated by `snapgate.sh` on the full 25 AND by
   `xfergate.sh`.
4. A mutation that hides a cell **without burying a sprite** would separate "the tool reads paint
   order" from "the board lost evidence" everywhere, instead of only where nothing is buried.
5. **sb26 is the one game with no evidence of any kind** — it consumes `Camera.render` as game logic
   and the instrument refuses to mutate that call. Reaching it needs a different construction, not a
   looser one.

Related: [[r101_zorder-rider]] (the defect this arm was built to catch) ·
[[r101_render-mutation-transfer]] (the colour arm that cannot) · [[r101_shipped-and-transfer]] (the
archived re-render, rule 7by) · rules **7ck**, 7cd, 7ce, 7by.
