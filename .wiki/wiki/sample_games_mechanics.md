---
type: reference
topic: sample-games
date: 2026-08-27
keywords: [sample-games, mechanics, stage-1, action-budget, source-read, generic-tools]
---

# What each sample game actually IS, read from its own source

> ⛔ **The method correction that produced this page.** `OPERATING_RULES.md` rule 0 says stage one
> is "**read each sample game** ... and write the code". The sources are in `environment_files/`,
> obfuscated in their identifier names and perfectly readable in their structure. A whole session
> was instead spent probing games as black boxes — twenty measurements on ONE game, ten of them
> correcting an earlier reading. **One read of `g50t`'s `step()` answered in seconds what eight
> live probes could not.** Regenerate with `uv run python scripts/read_sample_games.py [game...]`.
>
> ⛔ **The line this does not cross.** What is read here is DEV-TIME understanding of *which
> mechanic a generic tool must handle*. The tools stay frame-only. A tool that reads game
> internals is an adapter; adapters are quarantined precisely because they cannot transfer; the
> eval is 110 games whose source we will never see.

## ⛔ THE FINDING: thirteen of twenty-five games carry an explicit per-level ACTION BUDGET

Read straight out of the level data, no engine involved:

```
tu93  StepCounter     = 50,50,35,20,50,60,30,50,50      <- level 4 allows TWENTY actions
lp85  StepCounter     = 13,60,80,150,80,80,80,80        <- level 1 allows THIRTEEN
su15  steps           = 32,32,48,48,32,32,32,48,48
ft09  kCv             = 32,32,96,96,128,128
ar25  StepCounter     = 64,64,128,128,128,320,320,320
vc33  StepCounter     = 50,50,75,50,200,50,200
cn04  MaxSteps        = 75,100,125,125,150,200
sp80  steps           = 30,45,100,120,100,120
ka59  StepCounter     = 100,127,100,127,100,150,200
re86  StepCounter     = 100,100,200,200,250,200,300,...
s5i5  StepCounter     = 50,150,200,100,150,150,200,...
wa30  StepCounter     = 200,70,100,100,125,75,125,150
dc22  StepCounter     = 128,192,192,192,512,1024
ls20  StepsDecrement / Steps
```

**This is why the generic tools score 0.0200 while the adapters score 0.3162.** The tools run at
4,000-8,000 actions per GAME and open hundreds of states per level; the games allow **20 to 320
actions per level** and LOSE on overrun. The stall diagnostic's "1,500 steps, 500 states, zero
levels" was never a search-breadth problem — the game had been lost hundreds of actions earlier
and the searcher was still expanding.

It also explains why the metric is what it is: RHAE scores `(human/agent)²`, and these budgets are
roughly the human envelope. A generic agent that treats the board as something to explore first
and solve second is not slightly inefficient — it is **disqualified before it starts**.

**What "lose" costs, exactly** (`arcengine/base_game.py:301`): `lose()` sets
`GameState.GAME_OVER`. A following `RESET` with a non-zero action count is a **LEVEL** reset, not
a full one, so the levels already cleared survive — but every action spent is still counted, and
RHAE prices a level at `(human/agent)²`. So over-exploring does not merely fail a level; it
converts an eventual clear into a score of approximately zero. tu93's level 4 allows 20 actions;
a run that takes 2,000 and then clears it scores `(20/2000)² = 0.0001`.

**And dying is NOT a free reset.** `scripts/score_efficiency.py:336` keeps
`action_count_this_level` accumulating ACROSS a GAME_OVER restart — it is zeroed only when a
level is actually completed, and the reset action itself is counted. So the retry loop our agents
run (`restart_on_game_over`) does not buy exploration; it spends the level's score on it.

**Verified live**: tu93 reaches `GAME_OVER` after **exactly 50 actions**, which is the
`StepCounter=50` its level data declares. The static reading predicts the engine precisely, which
is the whole argument for reading the data instead of probing it.

⛔ Consequence for stage one: a tool needs to READ the budget off the frame (it is drawn — a
counter, a shrinking bar, a scrolling sprite) and plan inside it. "Explore, then act" has to
become "act within N", and no amount of tool-by-tool strengthening changes that.

The two reusable abstractions this page produced have their own concept pages:
[[concepts/action_budget]] (thirteen games cap their actions and END on overrun) and
[[concepts/swallowed_action]] (an action arriving mid-animation is consumed without effect).

## The fact that changes how every tool must be written

**Several games LOSE when an action budget runs out**, and the budget is drawn on screen:

| game | evidence | budget |
|---|---|---|
| cd82 | `if self._action_count >= self.iewrsdwok: self.lose()` | per level, drawn by `pioabixlyc(remaining)` |
| cn04 | `if self._action_count >= self.ojcsxidcz: self.lose()` | `level.get_data("MaxSteps") or 150` |
| vc33 | `elif not self.heczcoeosi.current_steps: self.lose()` | per level, the shrinking bar on row 0 |
| wa30 | `current_steps` | per level |
| g50t | a timer sprite moves one cell every SECOND action; lost when it leaves the screen | ~2x screen width |
| lf52 | loses at 64 / 64*5 / 64*10 frames depending on level index | per level |

So **exploration is not free on these boards; it is the loss condition**. A generic searcher that
opens hundreds of states before acting has already lost cd82 and cn04 — which is exactly what the
stall diagnostic measured (states in the hundreds, levels zero). ⛔ This also NARROWS an earlier
claim on the r101 round page that "probing is free on all 25": twelve probes are free, a thousand
are not.

## The levels are DATA too — no run required

`scripts/dump_sample_levels.py` imports each game module and walks its `levels` literal: every
level, every sprite, its tags, position and size, plus the level's own `data` dict. **All 25
games, 179 levels, statically.** The engine is never started and no action is spent.

**Worked example — ft09, answered in one command after twenty live probes failed to:**

```
L0: data={'kCv': 32,  'cwU': [9, 8],     'elp': [[0,0,0],[0,1,0],[0,0,0]]}  Hkx:8  bsT:1
L1: data={'kCv': 32,  'cwU': [9, 12],    ...}                                Hkx:13 bsT:2
L2: data={'kCv': 96,  'cwU': [8, 12],    ...}                                Hkx:23 bsT:4
L3: data={'kCv': 96,  'cwU': [9, 8, 12], ...}                                Hkx:18 bsT:3
L4: data={'kCv': 128, 'cwU': [14, 15],   ...}          Hkx:27  bsT:8  NTi:3
L5: data={'kCv': 128, 'cwU': [11, 14],   ...}          Hkx:0   bsT:4  NTi:22
```

* `kCv` is the **per-level action budget** — the on-screen counter;
* `cwU` is the **per-level palette**, and **L3 has THREE colours**;
* `elp` is the single-cell mask, i.e. what `NTi` sprites use;
* `Hkx` toggles its 3x3 neighbourhood, `NTi` toggles only itself, `bsT` is the spec.

⛔ This retires a "wall" recorded earlier on the r101 round page. "Level 5's neighbourhood model
self-contradicts — four tiles demanded in two colours at once" was **a three-colour palette read
by a two-state model**, and the "identical checkerboard tiles" were `NTi` sprites. Neither was a
property of the game; both were the limits of black-box probing, and both were one command away.

## Per game

| game | drives | what it is |
|---|---|---|
| **ar25** | 1-4 move, 5, **7 = UNDO** | move a SELECTED sprite; tags restrict some pieces to one axis; ACTION7 pops a state stack |
| **bp35** | 1-4 via a `match` in a helper | frame-driven platformer; win/lose read off a simulation object after its animation drains |
| **cd82** | 1-4 pick, 5 commit, 6 click | pick a basket / paint target, commit; **action budget** |
| **cn04** | 6 select+place, 5 rotate 90° | click a sprite to select; click it again where it aligns to PLACE it; ACTION5 rotates; **MaxSteps** |
| **dc22** | mostly internal | multi-phase; has an `UndoState`; a 14-tick animation gate decides win/lose |
| **ft09** | 6 only | **two clickable classes**: tag `Hkx` toggles its 3x3 NEIGHBOURHOOD, tag `NTi` toggles ONLY ITSELF (mask `[[0,0,0],[0,1,0],[0,0,0]]`); tag `bsT` is the spec/stencil |
| **g50t** | 1=up 2=down 3=left 4=right, 5 special | reach the goal before a timer sprite scrolls off; **an action arriving mid-animation is SWALLOWED** (`if avatar.animating: avatar.step()` — the dispatch is skipped) |
| **ka59** | internal | momentum/launch with explosions and colliders; enemies step after the player settles |
| **lf52** | internal | simulation like bp35; loses on a frame count that scales with level index |
| **lp85** | 6 only | buttons tagged `button_<ring>_<L\|R>` ROTATE a ring; win = every `bghvgbtwcb` has a `goal` at (x+1, y+1) |
| **ls20** | 1-4 | queued animations must drain before the next action registers |
| **m0r0** | 6 selects, 1-4 move | click a `sys_click` marker to SELECT it (it recolours; the others recolour too, so selection is VISIBLE); 1-4 then move that one marker a cell. Click empty space and it flips to ALL mode, where 1-4 move every marker together with per-name MIRRORING. Budget 150 |
| **s5i5** | 6 only | click a button and read its centre pixel: every piece whose own centre pixel is that colour ROTATES. Colour-keyed rotation |
| **r11l / su15 / sk48 / tn36 / sb26 / sp80 / tr87 / tu93 / re86 / dc22 / wa30** | see the table `scripts/read_sample_games.py` prints | regenerate; each is one command |

## What this says about the tools

1. **A tool must know the budget.** It is on screen in at least four games (a counter, a shrinking
   bar, a scrolling sprite). Reading it turns "explore then act" into "act within N".
2. **A tool must handle SWALLOWED actions.** At least two games (g50t, ls20) ignore an action while
   an animation drains. A searcher that records "this action did nothing" during an animation
   learns a false transition — and this is precisely what produced the contradictory action->
   direction readings that could not be resolved by probing.
3. **Selection is a first-class mechanic.** ar25, cn04 and cd82 all have a SELECTED object that
   actions apply to. None of the six current tools models one.
4. **Undo exists** (ar25 ACTION7, dc22's `UndoState`), and a searcher that knows about undo can
   explore a punishing board safely.

## Related

- [[rounds/r101_tool-development]] — the round this came out of, including the generic-tools card.
- [[lessons/instrument_validity_20260825]] — the discipline this is an instance of: validate the
  instrument before the hypothesis, and prefer the source of truth over a proxy for it.

## bp35's boards are not in `levels` — they are a runtime tile table (2026-08-27)

`scripts/dump_sample_levels.py` reports one 1x1 sprite on an 8x8 grid for all nine bp35 levels,
which reads as "there is nothing here" and is a true report of the wrong object. The boards live
in a module-level dict of ten entries keyed `grid1`..`grid10`, each an object with `.width`,
`.height`, the board as a list of one-character-per-cell strings, a legend from char to sprite
name, a start cell and an exit.

They are **11 cells wide and 36 to 39 tall**, which settles a question two tool authors were
arguing from pixels: the board really is far taller than the viewport, so a viewport-only planner
cannot see where it is going.

The legend resolves to real sprites and one is NOT obfuscated — `player_right`, alongside
`player_left` and their walk frames. Two facts from it are worth carrying into any tool for this
family: the board holds BOTH the player and a second body-shaped tile, so tagging the player by
silhouette can pick the wrong one; and two distinct legend characters share an identical pixel
signature, so the game separates by something a pixel comparison cannot see.

⛔ Dev-time understanding only. A tool may read pixels and nothing else — the ban is on encoding
a game's identity, not on understanding its mechanic, exactly as with reading `step()`.

## lf52 — one-cell bounce, pads counted down (2026-08-29)

`environment_files/lf52/271a04aa/lf52.py`, engine never started, then confirmed live.

**THE GRID IS 6 PIXELS PER CELL** (line 5566 builds pixels as `grid * 6 + origin`). Every
displacement below is quoted in pixels by the source, so `-dx*6` is ONE CELL, not six.

1. **Goal**: `ddaguepwkt = len(entities named "fozwvlovdui")` — the pads — and the level is won when
   it reaches **1**, or **2 at levels 6 and 7** (line 5572). So the game counts pads DOWN.
2. **Move**: every `hupkpseyuim2` piece attempts one cell in the pressed direction. A piece whose
   target holds a `kraubslpehi` and which stands on a pad is displaced by a level-dependent amount
   INSTEAD (line 5296): `-dx*8` at level 3, `-dx*6` at levels 5 and 6, `-dy*6` at level 8, none at
   levels 1-2 / 7 / 10, both axes otherwise. Opposite the press — a bounce.
3. **The game keeps its own step budget and ENDS on overrun** (line 5771): 64 at level 1, `64*5`
   at levels 2-5, `64*10` at levels 6+. One agent action costs 1.
4. **A death costs 20 of that budget** (line 5805) — thirty-two lose the level by themselves.
5. **ACTION5 rebuilds the level** (`kuexigxyxw` -> `pchvqimdvj`) and **ACTION7 undoes one step**
   (`aphzlzlgni` pops an undo stack). Both were measured changing 167 cells from a stuck position.
6. **A collectible power-up** (`cwyrzsciwms`) is spent by an ACTION6 in the bottom-left 16x16
   corner, dispatched as a distinct branch rather than as a click.

## What the live probes measured — and the FOUR readings they killed

Each of these was written down as a finding before the next measurement removed it. They are kept
because the errors are more instructive than the survivor, and three of the four are the kind that
reads as a confirmed mechanic.

| reading | why it looked right | what killed it |
|---|---|---|
| six-cell launcher | colour centroid moved exactly 6.00 | the grid is **6 pixels per cell** (line 5566), so 6.00 px is ONE cell |
| camera pan | the source applies the shift to a scene object | the background's 2402 cells DO NOT MOVE while one 32-pixel sprite does; a pan moves everything |
| c3/c4 = a budget gauge | they traded 1 pixel per action, summing to a constant | colour 3 is `DARK_GRAY` = `lgbyiaitpdiDING_COLOR`, the SELECTION colour, and it is absent entirely in other states |
| pads jump pads | the capture compares two same-named `fozwvlovdui` | level 6's three pads sit at cells (4,3), (8,2), (9,4) — no two are two cells apart with a third between |

⚠️ Reporting only the MAXIMUM colour shift cannot separate a launcher from a pan from a bounce. The
per-colour breakdown WITH cell counts separates all three in one run, and it is the same cost.

## How lf52 is actually played — the protocol, read off a level the tool WINS

Traced action by action through level 1 (`scripts/_lf52_protocol.py`), logging every action rather
than only the ones that changed something:

```
step 0  click (19,20)          select
step 1  click (31,20)   -12    land TWO CELLS right; the pad at the midpoint is captured
step 2  click (31,20)          select, at the new position
step 3  click (43,20)   -12    land two more cells right
step 4  click (43,20)          select
step 5  click (43,32)   -12    land two cells DOWN
        level clears at 24 green
```

**Select the piece, then click two cells away; the pad at the midpoint disappears.** Each capture is
exactly 12 green pixels, one pad, and the level advances the moment the count reaches 24 = 2 pads
(1 pad on levels other than 6 and 7). Peg solitaire, played with pairs of clicks.

⛔ Logging only the actions that CHANGED the pad count hid the select clicks entirely and made the
captures look like single clicks on odd-numbered steps. Four wrong models of this game were built on
that omission. Log every action first; filter afterwards.

## Level 6, measured end to end

- Arrives with **36 green = 3 pads** at cells (4,3), (8,2), (9,4); winning needs 2, so **ONE
  capture clears it**. ⚠️ This is the board at the MOMENT OF ENTRY — the probe stops the tool as
  soon as `levels_completed` reaches 5 — so nothing here is damage the tool did on the way in.
- **No capture is available.** All twelve pad flanks were enumerated (select one cell to one side,
  land one cell to the other, for all three pads on both axes) and none captures. A 100-cell
  single-click sweep changes nothing either.
- Arrows move a 32-pixel sprite one cell and leave every pad exactly where it was, across 32
  presses in all four directions.
- **ACTION7 does not restore the board** (measured on all four directions), and **ACTION5 wipes the
  pads to zero without winning** — it is a trap, not a lever, because the win is only checked inside
  the capture handler.

**The protocol, confirmed by reading the colour under each click** (`scripts/_lf52_protocol.py`):

```
select click  ->  lands on colour 14 (GREEN)  = a PAD
landing click ->  lands on colour  1          = an empty cell
```

So a capture needs **two ADJACENT pads with an empty cell beyond** — ordinary peg solitaire. Every
earlier enumeration in this round selected an empty neighbour instead of a pad, so no selection ever
happened and the landing click was the second half of an interaction whose first half never ran.

**Level 6 has no capture at entry, and this is now measured rather than inferred**: the pads sit at
cells (4,3), (8,2), (9,4) and the adjacent-pair list is EMPTY. Arming the power-up (click its
sprite, then the bottom-left corner) changes nothing either, and arrows leave every pad in place
across 32 presses.

⚠️ **The one hypothesis left, and it is a real one**: `unfozwvlovdui` is defined with `{"": GREEN}`
— it maps NO character to a colour, so it renders nothing — while carrying `name: "fozwvlovdui"`.
The win test counts entities by NAME, not by pixels. If a level places invisible pads, the visible
count is not the game's count and "three pads, one capture to win" is wrong for level 6. That is the
next thing to check, and it is checkable: the pad count the game uses can be inferred by watching
which capture makes the level advance on a level that DOES clear.

⛔ Also worth carrying: the frame is **27 layers**, and every reading in this round used `frame[-1]`
alone. That happened to be right — the protocol's arithmetic (12 pixels per pad, clears at 24)
matches that layer — but it was never checked until the end, and a pad variant IS declared on a
different layer in the source.

**So the tool is not failing to play the game — it is failing to find a SETUP.** railpeg clears
levels 1-5 with exactly the protocol above, which means it knows the capture; level 6 needs a move
that is not itself a capture before any capture exists, and its plan is built only of captures. That
is the lever, stated precisely, and it is what its 117 refused ACTION1 presses are groping for.

## lf52 level 6 — PARKED, mechanism decoded, one question left (2026-08-29)

Everything about how this game is played is now measured. What is NOT explained is level 6.

**Measured, and each of these is a separate run**: the level clears when the VISIBLE pad count
reaches 2 — confirmed at all five transitions the tool makes, not read off the source. Level 6
arrives with 3. So one capture clears it. And there is no capture: the pad-to-pad offsets are
(4,-1), (1,2) and (5,1) cells, so no two are adjacent **on any origin**. Nor is there a slide (all
six pad-to-empty-neighbour moves refused), nor a power-up effect (armed on every candidate sprite,
then spent in the bottom-left corner), nor any pad motion under 32 arrow presses in four
directions. The board is not transitional either — twelve settling actions leave the pads exactly
where they were, which is the ar25 trap this repository has already paid for once.

**The question that remains**: the visible green blobs may not be the entities the game counts. The
win test counts by NAME, `unfozwvlovdui` renders nothing while carrying the pad's name, and the
empirical clear-at-2 rule differs by one from the source's clear-at-1 for levels 1-5 — a discrepancy
of exactly one entity, which is the size of one invisible pad. Resolving that is the next step and
it is cheap: the game's own count can be recovered by watching WHICH capture advances a level that
does clear.

⛔ PARKED here deliberately. This dig produced a complete protocol, four killed models and two new
instrument rules, and moved the score by ZERO. Rule 7b names this exact failure mode.

## Win predicates read straight from the source — the stuck games (2026-08-29)

Rule 0 pays here the way it paid on lf52: the goal a tool must aim at is one line of the game's own
code, and for three of the eight stuck games it had never been written down.

| game | the level advances when | the level is lost when |
|---|---|---|
| **s5i5** (0.5833) | EVERY sprite tagged `0087vvmblxkzdi` (a target) has a sprite tagged `0064ocqkuqacti` (a mover) at the SAME x,y — cover them all | the level's `current_steps` runs out |
| **dc22** (0.7143) | `self.qnnpcoyzd.x == self.hfuqkxulm.x and .y == .y` — two sprites reach the same cell | a step allowance runs out (`ncuydqtllw()` false) |
| **bp35** (0.2220) | the falling body lands on a gem (`fjlzdjxhant`) | it lands on a spike (`ubhhgljbnpu` / `hzusueifitk`) |
| **lf52** (0.2727) | the pad count reaches 1, or 2 on levels 6 and 7 | the level's own step budget overruns (64 / 320 / 640 by level) |

**bp35's fall is a ten-line simulator** and worth copying exactly (`fsvnqdbzrp`): step along the
gravity axis while the cell is empty or holds only `oonshderxef` / `aknlbboysnc`; stop on anything
else; a gem wins ON the cell, a spike loses, everything else lands on the cell BEFORE it. Gravity is
`-1` when `vivnprldht` is set, which is the reversal the crag tool already recovered from frames
alone — its model and the source agree.

⚠️ s5i5's is the one that matters most: its park was FALSIFIED by an oracle (it was handed the 291
cells it supposedly lacked and did not improve), so the stall is not missing information. A
cover-every-target predicate is a very different search from "reach a goal", and it is the first
thing to check the tool actually optimises.

## The stuck games stop with 80% of their budget UNSPENT (2026-08-29)

Measured on all four of the biggest remaining gaps, at the scored 4000-action budget:

```
bp35   5 levels,  741 of 4000 actions used,  last level-up at 232,  GAME_OVER frames 11
lf52   5 levels,  818 of 4000               last level-up at 316                     0
dc22   5 levels,  926 of 4000               last level-up at 424                     0
s5i5   6 levels,  695 of 4000               last level-up at 191                     2
```

**Neither the game's own budget nor our action cap ends these runs.** The harness gives up:
`is_done` returns true once `steps - last_clear_step >= no_progress`, and `no_progress` is 500.

⚠️ There IS a measured justification for 500 in `score_efficiency.py`: "the most expensive level ANY
game ever CLEARED cost 120", a 4x margin. But that statistic is drawn only from levels that WERE
cleared — a level that needs 600 actions of trying cannot appear in it. The comment beside the knob
says it was exposed "so the margin can be measured rather than assumed", and it never had been —
**so it was, and the margin costs nothing.** Seven stuck games at `HARNESS_NOPROGRESS=3000`, six
times the patience:

```
bp35 0.2220   dc22 0.7143   lf52 0.2727   lp85 0.9099
ls20 0.8442   s5i5 0.5833   wa30 0.8000
```

Every one identical to the baseline to four decimals. The tools are not being cut off; they are
EXHAUSTED. They stop early because they have nothing left to propose, and 3,000 more actions of
being allowed to keep trying produce nothing.

**And the models are not the problem.** Read against each game's own win predicate, every tool that
holds a stuck game is aiming at the right thing:

- s5i5 -> swivel: `all(rider_at(cfg, b) == model.places[p] ...)` = the source's cover-every-target
- dc22 -> gantry: routes to a goal cell set = the source's two-sprites-in-one-cell
- bp35 -> crag: gravity axis, settle, pass-through tiles, gem, spike, gravity reversal — all
  recovered from FRAMES ALONE and all agreeing with `fsvnqdbzrp`
- lf52 -> railpeg: peg-solitaire captures, which is exactly the protocol that clears levels 1-5

So the remaining 0.1065 is not a mechanics gap. It is depth — and the first thing to establish about
depth is whether we are cutting it off ourselves.

## The specialists go SILENT, not slow — measured (2026-08-29)

Two patience knobs were tested and both are inert, and then the instrument check showed the second
test never did what it claimed:

- `HARNESS_NOPROGRESS=3000` (six times the give-up allowance): seven stuck games, every score
  identical to baseline to four decimals.
- `HARNESS_STALL=4000`: same seven, same scores — **and a marker proved the knob does not keep the
  specialist in charge at all.** crag is still retired and `graph` still holds bp35's board. That
  run measured nothing about specialist retention, and would have been written up as evidence.

Marking BOTH retirement paths separately settles it:

```
bp35   RETIRE kind=EMPTY tool=crag
s5i5   RETIRE kind=EMPTY tool=swivel
dc22   RETIRE kind=EMPTY tool=gantry, phase_grid
lf52   RETIRE kind=EMPTY tool=railpeg
```

**Every specialist retires through the EMPTY path — it proposes NOTHING.** Not a plan that fails; no
plan at all. The general searcher then inherits the level and spends the remaining budget, which is
why more patience buys nothing: the patience goes to `graph`, and the tool that understands the game
has already fallen silent.

This matches the lf52 dig exactly, which is the one stuck level whose board is fully decoded: level 6
has no two adjacent pads, so railpeg's capture model has NO LEGAL MOVE. It is silent because the
level offers nothing its model recognises.

**So the remaining 0.1065 is a MOVE-VOCABULARY gap, per game, at one specific level** — not depth,
not patience, not mechanics-in-general. The next question for each is narrow and answerable: what
does `propose()` see at that board, and what is the level asking for that the tool has no word for?

## Where each silent tool actually returns empty (2026-08-29)

Marking every `return []` in the four specialists, then the line that sets their dead flag:

| game | silence point | what it means |
|---|---|---|
| bp35 | `crag:1117` x8 — self-mute, and it records its own reason: **"window does not belong to this board"** | the stitched world REJECTS the current camera window |
| s5i5 | `swivel:996` — `_replan()` exhausted every pairing and `_retry_unknown()` was spent | the model is assembled; no click sequence solves it |
| dc22 | `gantry:501` x79, `:516` x47 — `if found is None` | the route BFS finds no path |
| lf52 | `railpeg:1252` x11 — more than 8 settle clicks with the board between lattice positions | it cannot get a stable read |

Two of the four then had their obvious explanation tested and REFUTED:

- **crag's rejection is a symptom, not the cause.** The alignment scores at the moment of "lost"
  are 0.60 and 0.565 against a threshold of 0.82 — not a near miss. Lowering `_ALIGN_FIT` to 0.50,
  which accepts every one of them, leaves bp35 at **0.2220, unchanged**. Accepting the window does
  not give the tool a move.
- **swivel's wall is documented in its own docstring**, measured by its author: "on the seventh
  board it is over 336,000 configurations and still growing when cut off" — and s5i5 stalls on
  exactly level 7. Its cap is `_MAX_OPEN = 120_000`. Raised 33x to 4,000,000 the search does not
  finish in FORTY MINUTES on one game, where the whole 25 normally takes 15.

⛔ So the silence is not one bug with one knob. Each tool goes quiet for its own structural reason,
and the two cheapest explanations — a rejection threshold and a search cap — are now measured rather
than assumed: one changes nothing, the other does not terminate.

## bp35 level 6 — the mechanic, found in the board table (2026-08-29)

Levels 5 and 6 have the SAME legend and the same 11x39 shape, so nothing new is declared. The
difference is which characters the layout uses:

```
grid5  x=14  g=2  2=2   u=6   v=7  +=1
grid6  x=0   g=3  2=11  u=10  v=7  +=1   1=1     <- one instance of a character level 5 never uses
```

`1` is `yuuqpmlxorv`, and it has **four sprite variants that shrink in stages**:

```
.oxxxo.        o...o          o   o         o   o
.xxxxx.   ->   .xxx.    ->     ...     ->
.xxxxx.        .xxx.           .x.
```

**It is a CRUMBLING PLATFORM**, and level 6 places exactly one, in the middle of a row of
pass-through tiles (`oo2222122oo`).

That single tile explains the whole bp35 investigation:

- crag classifies terrain by PIXEL SIGNATURE, so one crumbling entity presents as FOUR kinds — which
  is exactly the "4 of 7 unclassified" measured on that board.
- Clicking any of them does nothing, because the change is driven by use, not by clicks — which is
  why the two the probe did reach were both learned as `inert`.
- The route depends on a platform that disappears, so the frontier the tool computes is not the
  frontier the board has.

⛔ **The tool's model is static terrain plus click-driven change. This board needs terrain that
degrades on its own.** No amount of threshold, patience, vocabulary or alignment work reaches that,
which is precisely what eleven measured interventions found the hard way.

## ls20 declares a STEP BUDGET, and it reframes the efficiency target (2026-08-29)

Read from `environment_files/ls20/9607627b/ls20.py` after three pixel-based attempts to size ls20's
routing gap failed in three different ways. The source answers in one read what the frames could not:

- Every level carries **`"StepCounter": 42`**, and `StepsDecrement` defaults to **2** (line 1792),
  so the budget is worth about **21 actions**.
- It is refilled on the level-set path (`wbcenorpju` -> `nzukewekzr`, lines 1790-1798), not per
  attempt.
- **Exhausting it does NOT end the level.** Line 1972 computes `not step_counter.mfyzdfvxsm()` and
  merely SKIPS a branch when the budget is gone; the game continues. Which is consistent with the
  agent spending 302 actions on level 7 and still clearing it.
- Level 7 is the only level with **`"Fog": True`**.

⚠️ So the three numbers on this level — a 21-action budget, a human baseline of 186, and the tool's
302 — cannot all mean the same thing, and what the budget actually GATES is not yet established.
That is the next thing to read, and it matters: if running the counter down disables something the
tool depends on, "take fewer actions" is not merely an efficiency preference on this board.

⛔ Three frame-diff attempts to measure ls20's routing floor failed: a centroid mistaken for the
avatar (floor of 12, absurd), an avatar-tracker whose small-blob premise is false on a fog board
(20 usable steps of 302), and a re-crossing statistic that turned out circular. The source read cost
one command.

### ls20 is a FUEL game — the complete model (2026-08-29)

Following the budget through the source settles what it gates and why 302 actions can clear a level
whose counter is worth 21:

| fact | source |
|---|---|
| budget 42 units, **2 per action** = ~21 actions | `"StepCounter": 42`, `StepsDecrement` default 2 (line 1792) |
| touching a **`npxgalaybz`** sprite REFILLS it to full and makes that step un-killable | line 1888-1891 (`yubyobdoss = True` + `kbkdzqocik(full)`) |
| exhausting it costs a LIFE, of **three** | lines 1982-1984, `self.aqygnziho = 3` at line 1843 |
| a life loss returns the avatar to START, restores collected items, refills the budget | lines 1990-2005 |
| the loss also paints a **full-screen overlay** (`set_scale(64)`, `set_position(0,0)`) | line 1988-1990 |
| level 7 is the only fogged level | `"Fog": True` |

So ls20 is a fogged maze with a **fuel budget and refuel pickups**, three lives, and restart-to-start
on empty. 302 actions on level 7 is the tool detouring for fuel; the human's 186 is a better route
through it.

⛔ **And the full-screen overlay is what broke three of my instruments.** "A single step re-renders a
large part of the frame" was true and I read it as a property of fog; it is the death flash. An
avatar-tracker that assumes the avatar is the only small moving thing cannot survive that, and the
centroid floor of 12 was computed across it.

**The lever for ls20's efficiency, named**: `fogscout` models exploring the fog and has NO notion of
fuel. Its route ignores the constraint the level is built around, and survives only because pickups
happen to fall on its path.

**And the fuel IS binding — verified live.** Counting frames that repaint more than half the board
(the death overlay, now a meaningful detector rather than the noise that broke three instruments):

```
level  steps  death overlays
  1-6   15..101      0
   7      303        2
```

**Level 7 runs dry TWICE**, spending two of its three lives, and clears on the third attempt. Every
other level never runs dry. So a large part of the 302 is re-walking from the start after two failed
attempts — and the game is cleared with ONE life in hand, meaning a slightly worse draw loses the
level outright rather than merely scoring badly.

That sizes ls20's efficiency target and makes it concrete: **do not run dry.** The route has to be
planned through the `npxgalaybz` pickups, which is precisely the constraint `fogscout` does not
model.

**Level 7 carries SIX pickups, more than any other level** — at (30,21), (50,6), (15,46), (40,6),
(55,51), (10,6), against two or three on levels 1-6. It is the only fogged level AND the most heavily
fuelled one, which is what a level designed around fuel management looks like.

The pickup is frame-visible and distinctive: a **3x3 ring of colour 11** with a transparent centre
(`sprites["npxgalaybz"]`, line 341), `collidable=False`, `layer=-1`. So a fuel-aware router needs no
privileged information — it needs to look for that ring, treat each as a refill node worth ~21
actions, and plan a tour that never lets the counter reach zero.

**Everything ls20 needs is now known**: the budget (42 at 2 per action), the refill (touch the ring),
the penalty (one of three lives, back to the start, items restored), the detector (a full-screen
repaint), and the six pickup positions. What does not exist is a tool that uses any of it.

### What a fuel-aware ls20 tool can actually SEE (2026-08-29)

Colour 11 is BOTH the gauge and the pickups, which cost one instrument before the split was made.
Separated by position — a bar pinned to the frame edge versus rings out on the board:

```
step:   1    2    3    4    5    6    7    8    9   10
gauge: 80   76   72   68   64   60   56   52   48   44      -4 every action, max 84, min 0
board: 17   18   18   18   18   18   18   18   18   18      a ring is 8 px
```

- **The fuel level is directly readable** from the edge gauge and falls exactly 4 pixels per action,
  which is `StepsDecrement=2` rendered two pixels per unit. A tool does not have to infer its fuel;
  it can measure it every frame.
- **Pickups are visible, but only two or three of the six at a time** (interior colour-11 runs 17-24
  pixels against 8 per ring). The fog hides the rest until the avatar gets near.

So the lever is real but BOUNDED: a router can aim at the pickups it can see and must still explore
to find the others. "Plan a tour through all six" is not available from the frame; "never let the
gauge reach zero, and divert to a visible ring when it gets low" is.

⛔ Two more instrument failures on the way here, both already-known kinds. The counter was wiped by
the final level-up so the script reported "level 7 not observed" — the exact bug fixed earlier in
this same round, in a different file, because the fix lived in a script instead of a shared helper.
And the pickup counter was reading the fuel gauge, because both are colour 11.

### ⛔ CORRECTION — fogscout ALREADY models the fuel

The previous entry ended "what does not exist is a tool that uses any of it" and named the lever as
"fogscout has NO notion of fuel". **That is false.** Reading `src/admorphiq/tools/fogscout.py`:

- `_bar_runs` / `_bar` / `_read_bar` (lines 449-807) read the drawn budget every frame, and identify
  which of the strip's two colours is the tank **by behaviour** — the one that SHRINKS — with a
  docstring recording the exact trap of picking the longer run and reading every refill inverted.
- `moves_left()` exposes the remaining budget.
- `refill_marks` (line 554) is a learned set of the glyphs that top the tank up, and line 1105 notes
  the design that makes "a board of eight refills cost one probe instead of eight".
- It even separates a DEATH from a move: "the budget went back to full and the avatar is not where a
  step could have put it — it was thrown home" (line 1390).

So ls20 is played by a tool that reads its fuel, knows its refills, and detects its own deaths — and
it still spends 302 actions and two of three lives on level 7. **The gap is the QUALITY of the fuel
routing, not its absence.**

⚠️ Second time this round I declared a tool lacked something it already had — crag's vocabulary
probe was the first. Both times the claim came from reading the tool's OUTPUT (it behaves as if it
has no fuel model) instead of its SOURCE. The tools in this repo carry their measured history in
their docstrings; reading them first is cheaper than inferring their design from a trace.

### The fuel model exists and is EMPTY — measured at every level boundary

Built the obvious repair — carry the refill vocabulary across a level change, since the glyphs are a
property of the game and not of the level, the same argument crag records for its lattice pitch.
Measured on ls20: **0.8442 -> 0.8442, unchanged.**

Because there is nothing to carry. Printing what the tool holds at each of the thirteen resets in a
full ls20 run:

```
RESET carrying refills=0 kinds=0 bar=None      (x13, every one)
```

**fogscout finishes seven levels having learned nothing** — no refill glyphs, no glyph kinds, not
even the gauge's colour. And yet at the moment it dies on level 7 it reports `bar_len=42 full=42
drop=2`, so `_read_bar` is working *within* a level. Both facts together say the learned state is
already empty before the reset, not wiped by it.

So the diagnosis moves once more, and it is now sharper than "the routing is poor": **the tool's fuel
model runs, reads the gauge correctly, and accumulates nothing that outlives the moment.** Where
that state goes is the next thing to find, and it is a question about fogscout's own bookkeeping, not
about ls20.

⚠️ Third time this round the repair I built was aimed at a stage downstream of the real defect —
after crag's alignment threshold and its vocabulary probe. The pattern is the same each time: I
inferred the gap from behaviour, built for it, and the measurement showed the gap was further back.

### Why the fuel model is empty: fogscout NEVER PLAYS the easy levels

Attributing every action to the tool that issued it, per level:

```
levels 1-6   keymaze   408 actions, all of them
level 7      fogscout  291   keymaze 9
```

**The tool that owns the fuel model arrives for the first time on the fogged level.** It has never
seen this game when it takes over: no gauge colour, no refill glyphs, no glyph kinds — which is
exactly what `refills=0 kinds=0 bar=None` at every level boundary was reporting. The state was not
lost; it was never built, because fogscout was not playing.

And the level it debuts on is the one that punishes learning time with death: about 21 actions of
fuel, and `_read_bar` needs four frames of watching a colour fall before it can even find the gauge.

So ls20's efficiency gap is a TENURE problem, not a routing or bookkeeping one. The fix is not inside
fogscout — it is that the tool holding the model for a mechanic should meet that mechanic before the
level where it is fatal.

⚠️ This also retires two of my own repairs from this round: carrying the vocabulary across a level
(nothing to carry) and not resetting a tool that returns mid-level (fogscout has exactly one tenure
on ls20, so there is no return). Both were aimed at preserving a state that was never created.

### ⛔ CORRECTION — fogscout's detector is RIGHT; it is a fog specialist

"The tool that owns the fuel model never gets tenure" reads as a selection defect. It is not.
`fogscout.detect` returns **0.0 unless `fog_view(g)` finds a fog** (line 630), and levels 1-6 carry
`"Fog": False`. It declines those levels correctly — bidding on a board it does not own is the false
positive this repo gates at 0/24.

So the sharpened statement is:

- the **fuel mechanic is on every level** — every level has a gauge and two or three pickups
- the **tool that models fuel plays only the fogged level**, correctly, because that is its mechanic
- tools do not share state, so nothing keymaze sees on levels 1-6 can reach fogscout
- therefore the fuel model must be learned INSIDE the one level where running dry is fatal, and
  `_read_bar` alone needs four frames of watching a colour fall before it can locate the gauge —
  four of about twenty-one actions.

That is the real shape of ls20's remaining 0.1558, and it is not fixable by changing who plays what.
Either the gauge must be identifiable in fewer frames, or fuel knowledge has to be a property of the
harness rather than of one tool.

⚠️ Three of my repairs this round now stand retired by the same measurement: carry the vocabulary
(nothing to carry), do not reset a returning tool (no return), and let the fog tool learn earlier
(it correctly declines those levels). Each was built on a mechanism I had not yet checked.

### Identifying the gauge one frame sooner: measured, inert

Of the two routes the correction above left open — make the gauge cheaper to find, or move fuel
knowledge into the harness — the first is a two-line change and was measured first.

`_read_bar` waits for **four** frames of history before naming the tank colour. But the tank falls a
fixed four pixels every action, so three frames of a MONOTONE fall identify it just as safely (the
monotone test is what replaces the fourth frame's evidence). Implemented, and verified to take
effect: `GAUGE found after 3 frames`, where it previously reported four.

**ls20: 0.8442 -> 0.8442.** One action of twenty-one is about 5% of a tank, and it does not survive
the squaring. Reverted.

That leaves the second route as the only one with a plausible size: fuel knowledge as a property of
the HARNESS rather than of whichever tool happens to hold the fogged level. That is not a two-line
change, and this round has now established what it would have to carry — the gauge colour, the
refill glyphs, and the fact that a full tank plus a teleport means a death.

## dc22 level 6 — COLOUR-CYCLING TILES, and it is the round's best target (2026-08-29)

Ranked by what one more level is worth, dc22 leads at **+0.0114** — its next level is its LAST, so
clearing it takes the game from 0.7143 to 1.0000. Read from `environment_files/dc22/*/dc22.py`:

- The levels differ in exactly one setting: `StepCounter` 128, 192, 192, 192, 512, and **1024 for
  level 6**. The game itself budgets level 6 at five times level 1.
- Comparing sprite families per level, **ten appear only on level 6**, and three of them are one
  group: `tewfutpibpar`, `tewfutyefmyf`, `tewfutblrmbx` (plus `tewfutrefgps`).
- Those are 2x2 checkerboards of colours 9 and 10 in two phases, `collidable=True`, tagged
  `tewfut-color-cycle`, and `mzuiagpcmy` advances one to the NEXT entry of

```
awhuyiogsr = ["tewfutpibpar", "tewfutrefgps", "tewfutyefmyf", "tewfutblrmbx"]
```

**So level 6 introduces tiles that cycle through four types in a fixed order.** They exist on no
earlier level, which is why the five levels before it clear and this one does not: `gantry` routes
to a goal cell over static terrain and has no model of a tile whose type advances.

⚠️ Same shape as bp35's crumbling platform, found the same way and in the same number of reads: the
level that stops a game introduces exactly one mechanic the tool has never met. That is now TWO for
two — worth treating as the first thing to check on any stuck level.

### dc22 level 6's cycle is a SWITCH, not a clock — and it turns on one tile

Verified before building anything, which is the discipline this round arrived at late:

- **The cycle does not advance on its own.** Twelve inert actions on level 6 change exactly one
  pixel, at row 63 column 0 — the step counter. Nothing on the board moves.
- **Only ONE tile cycles.** `on_set_level` gives the `tewfut-color-cycle` tag to exactly one sprite,
  and only on level 6: `if self.level_index == 5: ... if vukjorzngu.x == 18 and vukjorzngu.y == 48`.
  Every other `tewfut` on the board is static.
- **The trigger is a `buezna` interaction.** Activating one reads its single-character tag as a group
  selector, calls `ilvrmetiiv(tag, sprite)`, and when the sprite carries `tewfut-color-buezna` the
  cycle advances one step through
  `["tewfutpibpar", "tewfutrefgps", "tewfutyefmyf", "tewfutblrmbx"]`.

So the level is: **a switch that advances one tile's colour through four states**, with the win still
being the game's usual "two sprites reach the same cell". The tool has to notice that a particular
interaction changes a particular cell's type, and that the right type is a precondition for the route.

⚠️ `gantry` routes to a goal over static terrain, which is why levels 1-5 fall and this one does not.
But note what is NOT required: no timing, no clock, no hazard. One switch, one tile, four states.

### dc22 level 6 — the switch is REACHABLE, and the target is fully specified

Sweeping the board at four-pixel spacing and watching the neighbourhood of the tile the source
names, (row 48, col 18):

```
click (24,48): 4 px changed at the tile, 120 on the whole board
click (24,52): 4 px changed at the tile, 121 on the whole board
```

**Exactly two clicks drive the switch**, and four pixels is precisely a 2x2 tile flipping phase. So
the mechanic is not only real but reachable from the frame with no privileged information.

**dc22's remaining level is therefore fully specified** — the most valuable single target on the
board at **+0.0114**, and the only stuck game whose next level is its last:

| what | value |
|---|---|
| win condition | two sprites reach the same cell (`qnnpcoyzd` == `hfuqkxulm`) |
| the obstacle | one tile at (18,48) whose type must be right for the route |
| the switch | a click at (24,48) or (24,52) advances it one step of four |
| the cycle | `["tewfutpibpar", "tewfutrefgps", "tewfutyefmyf", "tewfutblrmbx"]` |
| the tool's gap | `gantry` routes over STATIC terrain; its BFS returns no path and it goes silent |
| the game's budget | 1024 steps, five times level 1 — not a constraint |

What a tool needs is small: notice that a click changes one cell's type, treat that cell's type as
part of the search state, and plan over (position, tile-state) instead of position alone.

⚠️ Every claim here was checked before anything was built — the discipline this round learned after
thirteen repairs that were built first and measured inert.

### ⛔ AND THE SWITCH IS NOT THE BLOCKER — the payoff test, before any build

The mechanic is real, reachable and fully specified. The one thing left unverified was whether
DRIVING it opens the level. Pressing the switch k times and handing the board back to the tools:

```
switch pressed 0x -> levels_completed 5
switch pressed 1x -> levels_completed 5
switch pressed 2x -> levels_completed 5
switch pressed 3x -> levels_completed 5
```

**No tile state clears the level.** All four were tried; the game does not advance in any of them.

So dc22's cycling tile is a real mechanic that gantry genuinely cannot model — and modelling it would
not have cleared the level. A tool built on this specification would have been the round's fourteenth
wasted repair, and the test that prevented it cost four runs and no code.

**What this leaves**: dc22's level 6 stops the game for a reason still unfound. The tile was the only
thing the source singles out about that level (`if self.level_index == 5:` appears exactly once), so
the next question is what ELSE differs — nine other sprite families appear only there, and none has
been looked at.

⚠️ Note the shape, because it recurs: a mechanic that is genuinely new, genuinely unmodelled, and
genuinely NOT the blocker. bp35's crumbling platform has not been tested this way, and the same
question is open there.

### dc22 level 6's GOAL is also a switch — and it is pixel-identical to every earlier goal

The win is `jfva` reaching `goknoi`'s cell. Level 6 does not use the `goknoi` sprite the first five
levels use; it uses `goknoi-dokmdr`, which appears nowhere else:

```
goknoi          pixels=[[11,11],[11,11]]   tags=["goknoi"]
goknoi-dokmdr   pixels=[[11,11],[11,11]]   tags=["buezna", "goknoi"]
```

**Identical pixels. Different tags.** The level-6 goal is ALSO a `buezna` — the entity class whose
activation drives the colour cycle. So the goal cell is dual-purpose, and reaching it runs the switch
machinery before the win check.

⛔ **A frame-only tool cannot see this difference at all.** The two sprites are the same four pixels
of colour 11. Whatever separates them, it is not visible — which is the same fact already recorded
for bp35, where "two distinct legend characters share an identical pixel signature, so the game
separates by something a pixel comparison cannot see". Two games, same trap.

That is a much better candidate for what stops dc22 than the cycling tile, which was tested and does
not block. The next check is whether the goal is reachable at all — `gantry`'s BFS returns no path,
and a goal that behaves as a switch when touched may not register as reached.

### dc22 level 6 resists blind search — 54,000 actions, zero clears (2026-08-29)

With every tool-set explanation closed, the board was attacked directly: sixty parallel searches,
900 mixed moves and clicks each, on ceph-build.

```
searches      60          actions   54,000       clears  0
distinct boards reached per search:  max 130, and most far below
```

**130 distinct states in 900 actions** is the load-bearing number. Nearly every action returns to a
board already seen, so level 6 is a NARROW state space, not a large one that search merely failed to
cover. Compare lf52's level 6, where 600 random moves reach about 300 distinct boards.

Geometry, for whoever builds next: the level holds **four colour-11 2x2 blocks**, clustered
top-right at (5,53), (6,46), (8,53) and (8,56) — the goal is one of them, and they are pixel-identical
to each other and to every earlier level's goal.

So dc22's level 6 does not open by exploring. Something specific has to be done, the board barely
moves under anything else, and the two things the source singles out — the cycling tile and the
dual-purpose goal — are the only candidates left standing.

### dc22 level 6: the tool arrives in a POCKET of three boards (2026-08-29)

Testing whether the game has a restoring undo produced something more useful than the answer (it does
not — neither ACTION5 nor ACTION7 restores):

```
move 1 (up)    78fdaf6a -> ea6e0a1b
move 2 (down)  ea6e0a1b -> 78fdaf6a      exactly back
move 3 (left)  78fdaf6a -> 0cbb687d
move 4 (right) 0cbb687d -> 78fdaf6a      exactly back
```

**Up and down are exact inverses; so are left and right. From where the tool arrives, the four
direction keys reach exactly THREE distinct boards.** That is the whole explanation for the blind
search reaching only ~130 states in 900 actions: the mover is in a pocket one cell wide in each
direction, and no amount of moving leaves it.

So dc22's level 6 is not a hard search problem. It is a position from which movement alone can do
nothing, and the escape — if there is one — has to be a CLICK. That is a much narrower question than
"why does gantry find no path", and it is the one worth answering.

⚠️ It also explains the shape of `gantry`'s failure honestly: its route BFS returns no path because
from this pocket there IS no path by movement. The tool is right; it simply has no vocabulary for
getting out.

**And clicking does not escape it either.** Sweeping all 1024 cells of the board from the arrival
position, counting distinct boards reached:

```
swept 384/1024, distinct boards 6
swept 512/1024, distinct boards 7
swept 640/1024, distinct boards 7
swept 896/1024, distinct boards 7      converged
```

Three boards by movement, **seven in total including every click on the board**. dc22's level 6, from
where the tool arrives, is a pocket that no single action leaves.

⛔ **That relocates the problem entirely.** The question is no longer "what does level 6 need" — it is
**how the tool ARRIVES here**, because this position is already lost. Level 6 is entered after level 5
is cleared, so the entry state is whatever the engine builds plus wherever the mover is placed; and
sixty blind searches, 47 solo tools and every pairing all inherit the same pocket.

The next measurement is therefore about level 6's ENTRY, not its interior: whether the pocket is the
level's designed start (in which case the escape is a specific action nobody has found) or an
artefact of how the tool finishes level 5.

**The pocket is not a transitional-frame artefact.** Every measurement of it was taken at the instant
`levels_completed` reached 5, and this repository has already paid once for reading a board on a
level-up frame (ar25 went from 1 level to 8/8 when that was fixed). Letting it settle first:

```
after  0 settling actions: 3 distinct boards from 24 moves
after  4 settling actions: 3 distinct boards
after 12 settling actions: 3 distinct boards
```

Identical. So the pocket is the real arrival state, and dc22's remaining question is exactly one:
**is that pocket the level's designed opening, or where this particular route through level 5 leaves
the mover?** The game rebuilds each level from a clean copy in `on_set_level`
(`self.current_level._sprites = copy.deepcopy(self._clean_levels[self.level_index]._sprites)`), which
argues for designed — and if so, the escape is one specific action that 54,000 blind actions, 1024
clicks and 47 tools have all missed.

### ⛔ RETRACTED — dc22 level 6 was NOT cleared; the run FELL BACK to level 0

A sweep reported `LEVEL CLEARED from position 0 by a click at (26,8)`, and it was wrong. The test was
`levels_completed != 5`, which is true both when the level advances AND when the run collapses. Made
to name the direction, the same sweep says:

```
FELL BACK to level 0 from position 0 by a click at (26,8)
```

**That click restarts the game.** It did not open level 6; it threw the run back to the beginning.

⚠️ Everything built on the false reading is withdrawn: "dc22's level 6 is winnable from where the
tool arrives" and "what opens it is a sequence" were both inferences from a collapse misread as a
clear. What survives is what was measured directly:

- from the arrival position, the four directions reach exactly **three** boards, and settling for 0,
  4 or 12 actions does not change that
- a click can leave that pocket, but the one found leaves it DOWNWARD, to level 0
- sixteen prefix replays of the sweep, with and without its interleaved return moves, clear nothing
- sixty blind searches, 54,000 actions, clear nothing

⛔ **The lesson is the cheap one and I paid full price for it**: a test written as "did the level
number change" answers a different question from "did we win", and the difference is invisible until
something forces the direction to be named. Three commits and two probes were built on the wrong
side of it.

### dc22 level 6: every click-then-move combination, and where the board actually responds

4,096 combinations — click each of 1,024 cells, then try all four moves — swept in eight parallel
bands, with the direction of any level change named explicitly (rule 7f), so a collapse cannot be
read as a clear:

```
rows  8-16   18 boards reached      <- the only band that opens the state space
rows  0-8     9
rows 24-32    6
all other bands   3                 (16-24, 32-40, 40-48, 48-56, 56-64)
```

**No clear, and no collapse either.** Outside rows 0-32 the board is completely inert: clicking
anywhere and then moving reaches the same three boards the pocket already had.

So the level's responsive machinery sits in a narrow band across the TOP of the board, and rows 8-16
carry most of it — 18 distinct boards against the pocket's 3. That is where the four colour-11 blocks
are too, at rows 5-8.

⚠️ What this does NOT show is a way out: 18 boards is still a small closed set, and none of them is a
win. The honest statement is that dc22's level 6 responds to a small region and nothing found so far
escapes it — 4,096 click-move pairs, 54,000 random actions, 47 solo tools, 9 tool combinations and
16 prefix replays, all clearing nothing.

## wa30's last level is lost on the BUDGET, not on the mechanic (2026-08-29)

Ranked second in the depth work at +0.0080, and never opened until now. Its levels differ in one
setting, and the stuck level has the tightest allowance in the game:

```
level        1    2    3    4    5    6    7    8    9
StepCounter 200   70  100  100  125   75  125  150   70
shepherd     26   58   77   67  120   46   55  134  508   <- actions actually spent
```

**Overrunning LOSES the level** — `elif not current_steps: self.lose()` — unlike lf52, where the
counter runs out and play continues. So every one of those numbers has to fit under the one above it.

They barely do: level 3 spends 77 of 100, level 5 spends 120 of 125, level 8 spends 134 of 150. The
margin shrinks the whole way down, and at level 9 the tool spends **508 actions against a budget of
70** — seven times over.

**So wa30's last level is an EFFICIENCY problem, not a missing mechanic**, and that is a completely
different repair from dc22's. `shepherd` plays every level and understands the game well enough to
clear eight; it simply cannot do the ninth in seventy moves.

⚠️ Which also predicts fragility above it: a level cleared at 134 of 150 is one unlucky draw from
failing, so wa30's 8 levels are not as safe as the score suggests.

### wa30 draws its budget plainly — and BudgetReader reads 19 of 25 games, ACCURACY UNCHECKED

`src/admorphiq/tools/budget.py` holds a complete `BudgetReader` whose docstring records that
thirteen of the twenty-five games declare a per-level budget and END on overrun. **Exactly one tool
imports it** (`reforge.py`). shepherd — which plays every wa30 level and spends 508 actions against
level 9's allowance of 70 — does not, and its own docstring lists reading the drawn budget as "still
untested".

wa30 draws it as plainly as a game can (`render_interface`):

```python
frame[63, x] = 7 if x < round(64 * current_steps / total) else 4
```

The whole last row, repainted as a ratio bar — colour 7 remaining, colour 4 spent.

⛔ **I first reported the reader returns None on wa30 and that was WRONG** — I asked it only at level
boundaries. Surveyed across all 25 games, asking after every action:

```
games surveyed                                  25
games where the reader EVER returns a total     19
cn04 86 · cd82 101 · dc22 96 · wa30 217 · g50t 132 · sp80 23 · re86 103 · tu93 49
```

**It reads nineteen games, wa30 among them.** But wa30's declared budgets are 200, 70, 100, 100,
125, 75, 125, 150, 70 — and the reader says **217**. It produces a number on most of the set and
nobody has ever checked whether the numbers are right.

So the real state is not "no reader" and not "a reader that cannot see this style". It is **a reader
used by one tool out of forty-seven, returning unverified values on nineteen games**. Verifying it
against the declared StepCounter per game is a small measurement with a large blast radius, and it
has to come before any tool is wired to trust it.

### BudgetReader's accuracy, measured for the first time (2026-08-29)

Ten of the twenty-five games declare a `StepCounter` in their level data. Comparing the reader's
total against the declared budget of the level it was reading:

```
game   declared L1   reader   verdict
ka59          100      102    MATCH        (within 10%)
lp85           13       12    MATCH
re86          100      103    MATCH
s5i5           50       52    MATCH
tu93           50       49    MATCH
wa30          200      217    MATCH
ar25           64      179    wrong
dc22          128       96    wrong
ls20           42       71    wrong
vc33           50     None    no reading
```

**Six of the nine that both declare a budget and produce a reading are right to within 10%.**

⚠️ Two corrections to my own claims, both from the last two ticks. "BudgetReader returns None on
wa30" was wrong — I asked only at level boundaries. "wa30's 217 is a wrong value" was also wrong — I
compared it against level 9's allowance of 70 while the reading came from level 1, whose budget is
200. The reader is accurate there.

So the position is: **a working, unverified-until-now budget reader with 6/9 accuracy, imported by
one tool out of forty-seven** — while thirteen games END THE GAME on overrun and wa30 loses its last
level by spending 508 actions against 70. That is exactly the shape CLAUDE.md records for every gain
this project has actually made: an asset already present and not being used.

⛔ Before wiring: the three wrong readings matter. ar25 reads 179 against 64 and ls20 reads 71
against 42 — both nearly 3x and 1.7x too generous, and a tool told it has more budget than it does
will plan past the end of the level. Any use must be gated on the reader agreeing with itself across
frames, not just on it returning a number.
