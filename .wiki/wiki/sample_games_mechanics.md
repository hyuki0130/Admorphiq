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
| pads do NOT jump pads on level 6 | the capture compares two same-named `fozwvlovdui`, and the three GREEN pads on screen are not adjacent | ⛔ THIS ONE WAS ITSELF WRONG AND SURVIVED A WHOLE ROUND. There is a FOURTH pad on screen and it is RED; it sits beside the green at grid (2,3), and `ndtvadsrqf` counts by prefix so it counts toward the win. Reading one colour cannot see a two-colour board — see the level-6 section below |

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

## lf52 LEVEL 6 IS SOLVED — 5 levels -> 6, measured live (2026-08-29)

⛔ **THE FOUR BLOCKS THIS REPLACES WERE WRONG, AND THEY WERE WRONG THE SAME WAY: the instrument
only looked at GREEN.** They said level 6 arrives with three pads, that no two are adjacent on any
origin, that one capture would clear it, and that the level was therefore parked on an unexplained
mystery. Every one of those is refuted below by a run.

**The clear**: `scripts/_lf52_l6_play.py` replays a 55-move line and the engine advances
`levels_completed` 5 -> 6 in **91 actions on the level** (budget 640). Deterministic — five of the
eight fan seeds ran it, all 91 actions, all cleared; the other three differ only in which pixel
inside a 6-px cell the click lands on. The line itself is `scripts/_lf52_l6_line.json`.

### What the earlier readings missed

1. **There are FOUR pads on screen, not three. The fourth is RED.** `fozwvlovdui_red` renders in
   colour 8, twelve pixels, at grid (2,2) — right beside the green at (2,3). The win counter
   `ddaguepwkt = len(ndtvadsrqf("fozwvlovdui"))` matches by **prefix**, so the red counts. Reading
   only colour 14 is what produced "no two pads are adjacent"; the adjacent pair was always there.
2. **The board is 28 cells wide and the screen shows about ten of them.** `grid6` holds **7 green +
   1 red = 8 pads**, three `dgxfozncuiz` at (14,3) (17,3) (23,3), and three carts at (7,6) (8,6)
   (23,4). Winning needs the count down to 2, so level 6 needs **SIX captures, not one**. Four of
   its pads and all three of its purple stepping stones start off screen.
3. **A pad moves without capturing — that was the open question and the answer is yes.**
   `cfilhtifcb` removes the midpoint only when `qcerbdpdcl.name == uywtlohliu.name`. Green over red
   and red over green are legal jumps that capture NOTHING, and so is any jump over a
   `dgxfozncuiz`. That is the repositioning verb the level is built on.
4. **`pchvqimdvj` is a DEAD END, not a win.** It greys every pad and spawns the pickup that
   restarts the level; `tdcblgbfxw` is the win. So ACTION5 is not a trap — it is a two-action
   RESTART (measured: green 36 -> 0 -> 36 after ACTION5 then a click in the bottom-left corner).
   ⚠️ On a board that has already MOVED the restart did not restore the root in four attempts, so
   it is not a reliable backtracking primitive.

### The game DRAWS its own legal moves — a free oracle nothing was using

Selecting a pad calls `xpcuvjyrgu`, which tests all four directions with `qikmikecdf` and attaches
a marker two cells out for each that passes. The sprites name their own colours, and both are
measured on the frame:

```
csrvckunbev   20 px DARK_GRAY(3) ring ON the pad     -> this pad has AT LEAST ONE legal move
lgbyiaitpdi    8 px GRAY(2) cross 12 px out          -> that exact landing is legal
```

Measured at level 6 entry: the green at grid (2,3) lit a cross at exactly 12 px UP; the red at
(2,2) lit one at exactly 12 px DOWN; **both isolated greens lit nothing at all**. GRAY is absent
from level 6's palette until a pad is selected, so neither reading is ambiguous.

⚠️ The cross arrives as **four two-pixel blobs**, not one — `" o..o "` is not 4-connected. A blob
filter with a minimum size of four finds nothing and reads as "the oracle does not exist"; that
cost one whole probe. Merge blobs within ~3 px before measuring.

**One click enumerates a pad's entire move set.** That is what makes level 6 affordable inside its
640-action budget, and it is the asset a tool should be spending, not a model of its own.

### The mechanic, corrected

* jump legality is `qikmikecdf` = the MIDPOINT holds a `fozwvlovdui*` or a `dgxfozncuiz`, and the
  LANDING is bare floor OR **a cart** (`posalhhmjq` accepts a cell of exactly two names when one is
  `hupkpseyuim2`);
* the four simple actions drive every cart one cell — `tmhxwcojkh(dx,dy)` moves a cart only when the
  cell it faces holds a `kraubslpehi`, and it drags whatever shares the cart's cell along with it;
* **a green riding a cart sideways drags the CAMERA**: level 6 sets `nybfuxmyrv = (-dx*6, 0)` when
  a pad named exactly `fozwvlovdui` sits on the moving cart, guarded so the view cannot scroll back
  right while the offset is still >= 5. A RED rider does not scroll — the name test is exact.
* two landings scroll it too: (7,6) at offset 5 scrolls -20 px, (18,2) at offset -57 scrolls -44.

⛔ **Arrows are NOT inert on this level, and the earlier note that they are came from a metric that
could not see the difference.** Twelve presses of each direction: ACTION1/2/3 leave the frame
byte-identical, ACTION4 changes it three times and then stops — the carts really do move, they just
leave the ten-cell window. "Nothing moved" and "what moved went off screen" are the same reading to
a whole-frame comparison.

### The line, and why it is shaped that way

Solved by exhausting the model above (`states 384219` with the camera modelled, 935 winning states
without it). The shape is worth carrying because it is what a tool has to be able to WANT:

```
 4 jumps  walk the green at (2,3) down the left column, over the red and back over it
 2 jumps  the first two captures, using the two greens the left region does hold
 5 jumps  walk a green rightwards along row 6 and LAND IT ON THE CART at (8,6)
 5 drives ride the cart right — each press scrolls the camera one cell and reveals new board
 …        climb the rail columns, cross on the purple stepping stones, six captures in all
55 moves / 85 planned actions / 91 measured
```

Eleven jumps and five drives happen before the second capture. A planner that ranks "shortest route
to a capture" and retires after three barren tiers cannot hold a plan of that shape.

### What this leaves for the tool

`railpeg` already models everything named above — carts, riders, uncapturable colours, a board
wider than the screen — and it is NOT failing for want of a mechanic. Instrumented on level 6
(`scripts/_lf52_railpeg_diag.py`, 297 sync calls): it reads 4 pieces, 2 carts, 22 sockets, 9 rails,
sets `_elsewhere = True`, and spends its planning on `win 45 / travel 36 / capture 4 / none 1` with
`why` dominated by `plan:no-capture-reachable 25`. It declares a local win forty-five times on a
board whose visible region cannot produce one, and never puts a piece on a cart.

⛔ **AND IT IS NOT MISPLAYING — it plays the opening CORRECTLY and then has nowhere to go.**
`scripts/_lf52_railpeg_plan.py` logs the colour under every pixel it clicks. Its select clicks land
on colour 14 or colour 8 and its landing clicks on colour 1, which is the protocol exactly; it walks
the green down the left column using the RED PAD AS A LADDER, takes both available captures, and
finishes with **green 36 -> 12 and red 12** — one green and one red, which is precisely its own
`_won` condition. The level does not end, because four pads and three stepping stones are off
screen. Then it has one mobile piece and no partner, and it stops.

Three levers, in order, each with the number that names it:

1. **The local win is a MIRAGE while `_elsewhere` is true.** `_won` counts the colours it can SEE,
   and on this board that condition is reachable in six moves and worth nothing. Measured: 43-45
   win-tier plans, `_elsewhere` already true, and the board really does arrive at the local win.
2. **Travel has to be able to BOARD A CART, not merely ride one.** 32 travel plans, zero boardings.
   The line that clears walks the last green five cells right along row 6 — leapfrogging it with
   the red — and lands it on the cart at (8,6); the five drives after that are what scroll the
   camera and reveal the rest of the board. `_novelty_field` cannot rank that, because the reward
   arrives only after the drive, and the cart cell itself is next to cells pieces have already
   touched.
3. **A cart is being driven into a cell the engine will not accept, 73 times.** ACTION3 (LEFT) is
   proposed **73 times** on level 6 and is inert every time; ACTION4 23, ACTION1 18, ACTION2 6, and
   only ACTION4 moves anything. ⛔ The obvious diagnosis — a mislearned direction map — is REFUTED
   by measuring it: `_dirmap` comes out `{left: 3, right: 4, up: 1, down: 2}`, which is exactly the
   engine's `tmhxwcojkh` dispatch, `_pending` is None and only ACTION1/2 were ever excluded. The
   map is RIGHT. What is wrong is the cart model: `tmhxwcojkh` moves a cart only when the cell it
   FACES holds a `kraubslpehi`, and the cells left of the carts at (7,6) and (8,6) are plain floor,
   so a leftward drive is refused — while `_shunt` believes it is available. Every plan containing
   one desyncs on its first action.

4. **Read the game's markers instead of inferring legality.** One click per piece returns the exact
   move set, and it is right even where the model is wrong — including the case above where a
   select click landed on colour 1 because the model had already advanced past a lagging frame.

## lp85 — the efficiency loss was DISCOVERY, and the game's own data prices it (2026-08-29)

lp85 clears all eight levels and loses nothing to depth. Read off its source, every button is
tagged `button_<ring>_<L|R>` and drives one ORDERED CYCLE of lattice slots; `khartslnwa()` advances
the level when every `bghvgbtwcb` marker has a `goal` sprite at `(x+1, y+1)` and every `fdgmtkfrxl`
has a `goal-o` there. The cycles are DATA (`izutyjcpih`, one integer map per ring per level), so the
shortest solution is computable without playing: `scripts/_lp85_oracle.py <level>` BFSes the goal
sprites' positions under the exact permutations.

```
level      1     2     3     4     5     6     7     8
human     17    38    31    16    41    60    26   159
ORACLE     5     8    16    12     9    21     1     7      <- shortest press sequence that wins
buttons    2     6     4    16     4    36     6    12
controls   2     6     4     4     4    36     6    12      <- level 4 draws FOUR controls SIXTEEN times
```

⛔ **Level 4 is the only level where the human is tight** (16 against an oracle 12), and it was the
only level losing score: 33 actions, 0.2351, against 1.0000 everywhere else. The split, instrumented
press by press (`scripts/_lp85_split.py`, `scripts/_lp85_l4.py`), was **16 first presses + 9
confirming presses + 4 replans + 3 plan presses + 1 nudge**. The sixteen first presses are exactly
`cyclepress`'s "press every control once, the cheapest complete model" rule — and on this board they
are also **net IDENTITY**: four copies each of two rings times two directions cancel exactly, so
sixteen of the thirty-three actions bought only the model. Worse, that model was WRONG: one press
each recovers SIX distinct permutations where four exist, and **no press sequence to the markers
exists until the twenty-sixth action**.

**The fix is an ORDER, not an algorithm: evidence before breadth.** Confirm the controls already
pressed before pressing a new one, stop probing the moment the model on hand yields a plan, and
prefer a control whose LOOK has not been sampled yet. Measured:

```
level          1    2    3    4    5    6    7    8    game
before         7   28   32   33   21   35   25   37   0.9099
after          7   35   19   19   17   40   19   33   0.9677     lp85 +0.0578
```

Level 4 now touches **FOUR of its sixteen buttons** and wins in 19; level 3 goes 32 -> 19. The
remaining 0.032 is level 4 at 19 against a human 16.

⚠️ **Appearance orders the probes and must never adopt a permutation from them.** MEASURED against
the game's own sprite table (`scripts/_lp85_appear.py`): seven of the eight levels draw two or more
DIFFERENT controls with identical pixels — level 6 draws 36 distinct controls in TWO appearances —
and level 4 is the single level where appearance and control coincide. Adopting across a look scores
**0.3296** (three levels lost). The same experiment refutes two other plausible rules: pooling the
evidence of controls a single permutation jointly explains gives 0.8932 (it merges controls that are
not the same and level 4 rises to 55), and stopping at the first plan without confirming it gives
0.8982 (level 1 goes 7 -> 27, because a permutation replaying ONE press always exists).

⛔ **The budget indicator is what makes "confirm first" safe.** Ungated, confirming before breadth
takes level 1 — two controls, THIRTEEN actions of allowance — from 7 actions to 59, because the level
is lost and retried and the score pays for both attempts. Gated on the same indicator the shipped
confirmations already use, level 1 is untouched.

**A control's permutation being the exact INVERSE of another's confirms both**, for no extra press:
the two were recovered from different presses of different controls and had to agree slot for slot.
Alone it takes the eight levels from 219 actions to 189, three boards cheaper and none dearer.

## Win predicates read straight from the source — the stuck games (2026-08-29)

Rule 0 pays here the way it paid on lf52: the goal a tool must aim at is one line of the game's own
code, and for three of the eight stuck games it had never been written down.

| game | the level advances when | the level is lost when |
|---|---|---|
| **s5i5** (0.5833) | EVERY sprite tagged `0087vvmblxkzdi` (a target) has a sprite tagged `0064ocqkuqacti` (a mover) at the SAME x,y — cover them all | the level's `current_steps` runs out |
| **dc22** (0.7143) | `self.qnnpcoyzd.x == self.hfuqkxulm.x and .y == .y` — two sprites reach the same cell | a step allowance runs out (`ncuydqtllw()` false) |
| **bp35** (0.2220) | the falling body lands on a gem (`fjlzdjxhant`) | it lands on a spike (`ubhhgljbnpu` / `hzusueifitk`) |
| **lf52** (0.2727) | the pad count reaches 1, or 2 on levels 6 and 7 — counted by NAME PREFIX over the whole board, so off-screen pads and the RED pad all count | the level's own step budget overruns (64 / 320 / 640 by level) |

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

⚠️ SUPERSEDED for lf52 — level 6 is now SOLVED live in 91 actions (see the level-6 section). What
follows described the dig as it stood before that. This matches the lf52 dig exactly, which is the one stuck level whose board is fully decoded: level 6
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
| lf52 | `railpeg:1252` x11 — more than 8 settle clicks with the board between lattice positions | ⚠️ NOT the whole story: instrumented, railpeg makes 297 sync calls on level 6 and 244 of them are PLACED. It plans (win 45 / travel 36 / capture 4) and never puts a piece on a cart. The settle stall is downstream of a planner that keeps declaring a local win on a board whose visible tenth cannot produce one |

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

### ⛔ RETRACTED — it is NOT a crumbling platform, and it is NOT what stops level 6

The reading above was written from the board table and the sprite list alone, and both halves of the
conclusion it drew are wrong. `gwfodrkvzx` — the CLICK handler, forty lines further down the same
file — dispatches on the clicked cell's sprite name, and `yuuqpmlxorv` is one of its five cases:

```
qclfkhjnaac   -> removed                         (one-shot block)
etlsaqqtjvn   -> copies itself into empty 4-neighbours, then removed
yuuqpmlxorv   -> becomes oonshderxef             (SOLID  -> pass-through)
oonshderxef   -> becomes yuuqpmlxorv             (pass-through -> SOLID)
lrpkmzabbfa   -> `self.vivnprldht = not self.vivnprldht`, then removed   (gravity, ANY distance)
```

**It is a CLICK TOGGLE, in both directions, and the four "shrinking" sprites are that swap's
animation frames** (`["txjcfisalqu", "cvkgqlojfnh", "ltorejwifje", "oonshderxef"]` — the sequence
ENDS on the pass-through sprite). So the record's *"clicking any of them does nothing, because the
change is driven by use, not by clicks"* is exactly backwards: the click is the ONLY thing that
changes it, and nothing in the game consumes it by use.

⚠️ Two consequences that the crumbling reading hid:

- The eleven `oonshderxef` cells on this board are not scenery — each is a block the player can
  BUILD by clicking it, and un-build by clicking it again. Level 6 has twelve toggle cells, not one.
- A `lrpkmzabbfa` click takes `pbsitubcfd(..., qssroarxob=True)`, which SKIPS the "clicked cell must
  be directly below the body" test. Gravity can be reversed from anywhere on screen. The toggle
  cells keep the test, so a toggle click only moves the body when it is the body's own support —
  but it still edits the cell from anywhere.

### The level is SOLVABLE inside its own allowance — measured, and cleared on the real engine

A simulator was built from the game's own board table and differential-tested against the engine —
`scripts/_bp35_sim.py verify 6 40 40` runs 40 random action sequences on both and compares player
cell, gravity, camera, win/lose and every terrain cell: **0 mismatches** (levels 2, 4, 5 also 0;
levels 1 and 3 diverge only on `mylefxfaev`, the rising lava that `if self.qswcochjodb > 3: return
False` restricts to the first three levels). ⚠️ The engine DEFERS every cell mutation, the switch
removal and the camera move into its animation queue; a first version of the check drove the scene
directly, never ticked `scene.render()`, and reported 40/40 mismatching — all of it the probe's own
half-applied actions.

Searching that simulator (`scripts/_bp35_l6_solve.py`, 30-way fan on ceph-build):

```
BFS, allowance 64     seeds 1 4 7 10 13    41 actions   5 toggle clicks  3 gravity clicks
BFS, allowance 200    seeds 3 6 9 12       41 actions   5 toggle clicks  3 gravity clicks
greedy best-first     seeds 8 20           46 actions  10 toggle clicks  3 gravity clicks
greedy best-first     seeds 2 5 11 14 17   54-61        16-23 toggles    3 gravity clicks
```

**41 actions is the OPTIMUM** — breadth-first, unit costs, and lifting the allowance to 200 does not
shorten it. Against the game's own baseline of 87 for this level that is `min(87/41, 1)^2 = 1.0`, so
level 6 is worth its full weight (6 of 45) — **bp35 0.2220 -> 0.3553** for the one level.

**Every plan found uses toggle clicks, and every one uses all three gravity switches.** So unlike
dc22's cycling tile — a real mechanic that turned out not to block — this one is LOAD-BEARING: the
route runs over blocks that only exist because they were clicked into existence.

And the plan CLEARS THE REAL GAME (`scripts/_bp35_l6_replay.py`, rule 7g). The shipped harness plays
to level 6 in 233 actions, the plan is replayed action by action, the simulator and the engine agree
on the body's cell at EVERY action, and `levels_completed` goes **5 -> 6** — for the 57-action plan
and again for the 41-action optimum. Tested as `> start`, and the resulting number printed (rule 7f).

### ⛔ crag's SITE RULE excludes every solution — a proof of absence, not a budget

`CragTool._sites` offers the searcher five click candidates: the support, the two cells beside the
body, the two that would hold it one step away — plus every gravity switch on screen. Its docstring
justifies the narrowness with *"every other editable cell on screen can be reached by walking next to
it first, so nothing is lost"*, and records a measurement that adding ONE more candidate took the
tool from three levels to one.

Re-running the same search with the click candidates restricted to exactly that rule
(`_bp35_l6_solve.py <seed> <cap> local`, nine runs, all three search orders):

```
9 of 9   actions=None   states=24644   nodes=74615   secs 24-31   (limit 64 AND limit 200)
```

The reachable state space under crag's own rule is **24,644 states, and it is EXHAUSTED** — the
search ends because the frontier is empty, at 74,615 nodes against a 30,000,000 cap, in half a
minute. **There is no win in it, at any depth.**

And the optimum shows exactly why: replaying it and classifying each click against the rule at the
moment it is made,

```
 0 click (6,25) oonshderxef  body=(3,23)  FAR
 2 click (7,25) oonshderxef  body=(4,23)  FAR
 5 click (6,22) lrpkmzabbfa  body=(6,23)  LOCAL
 8 click (4,31) lrpkmzabbfa  body=(8,31)  FAR   (gravity — crag already offers these)
13 click (5,13) oonshderxef  body=(8,18)  FAR
17 click (6,13) yuuqpmlxorv  body=(5,14)  LOCAL
22 click (8,1)  lrpkmzabbfa  body=(7,7)   FAR   (gravity)
24 click (4,13) oonshderxef  body=(6,8)   FAR
```

**Four non-gravity clicks land on cells the body is nowhere near**, and the docstring's escape —
walk next to it first — does not apply to them: they build the block the body then FALLS ONTO, so
there is nowhere to stand beside them until after the click.

⛔ So bp35's level 6 is not stopped by patience, alignment, thresholds, the stitch, or a mechanic the
tool cannot model. It is stopped by the searcher's own candidate generator and edit cap.

### How far the two knobs have to move — the whole curve, measured

Widening the site rule to "crag's five, plus every editable cell within Chebyshev k of the body,
plus every visible gravity switch" and re-searching (`_bp35_l6_solve.py <seed> <cap> r`, results in
`scripts/rounds/R101BP35/bp35rad.jsonl`):

```
k        best   clicks   states    nodes     verdict
0        --      --       24,644    74,615   EXHAUSTED, no win  (crag's rule exactly)
1        --      --       25,092    82,679   EXHAUSTED, no win
2        43       8      117,145   476,824   win
3        43       8      120,146   562,218   win
none     41       8            --        --   win (the optimum)
```

Every "no win" row is an EXHAUSTION at both allowance 64 and allowance 200, at a hundredth of the
30,000,000-node cap — not a search that ran out.

**And the edit cap is a SECOND, independent wall.** crag spends at most `_MAX_EDITS = 6` clicks on a
route to the exit (`_EXPLORE_EDITS = 2` on a frontier leg). Capping the search at six clicks
(`... c`, `scripts/rounds/R101BP35/bp35clk.jsonl`):

```
6 clicks, sites unrestricted   5,262 states   EXHAUSTED, no win   (limit 64 AND 200)
6 clicks, sites at k=2         2,126 states   EXHAUSTED, no win   (limit 64 AND 200)
```

**No six-click win exists at all.** Every plan ever found here spends 8 (five toggles, three gravity
switches) or more, so `_MAX_EDITS` excludes the level on its own, whatever the site rule does.

So the gap is three numbers, not one:

| knob | now | needed | measured basis |
|---|---|---|---|
| `_sites` reach | crag's five | Chebyshev **2** | k=0 and k=1 both EXHAUST with no win |
| `edits_cap` | `_MAX_EDITS = 6` | **>= 8** | no 6-click win exists at any reach |
| `_MAX_EXPAND` | 40,000 | ~120,000 | a complete k=2 search is 117,145 states |

⚠️ And none of it is free: crag's own docstring records that adding ONE extra candidate — the cell
overhead — took the tool from three levels to one. k=2 multiplies the searched space **4.8x** and
the nodes **6.4x**, so a blanket widening is exactly the change that measurement warns against. What
the two clicks that OPEN the optimum actually are is the design hint: `C(6,25)` and `C(7,25)` with
the body at `(3,23)` build a SAFETY FLOOR two cells in the anti-gravity direction, so that the
gravity reversal three actions later lands the body on them instead of on the spike row at y=26.
They are supports for an axis that is not yet in force. A rule that offers editable cells which
WOULD be supports after a reachable reversal buys the route without buying the whole neighbourhood.

### The rule stated in the mechanic's terms works — and costs exactly the same

The right shape for the widening is not a radius: it is *offer an editable cell when it would be the
SUPPORT after a reversal the body can reach*. Implemented (`_bp35_l6_solve.py <seed> <cap> s`) as
crag's five, plus every gravity switch on screen, plus every editable cell lying on the fall path
that the REVERSED axis would take from any resting place the body can reach by WALKING ALONE:

```
candidate rule                       best   clicks   states     nodes      verdict
crag's five                           --      --      24,644     74,615    EXHAUSTED, no win
+ Chebyshev 1                         --      --      25,092     82,679    EXHAUSTED, no win
+ Chebyshev 2                         43       8     117,145    476,824    win
support-after-reversal                43       8     113,240*   470,000*   win
```

`*` mean of three BFS runs; the two rules agree on the optimum and are within 3% of each other on
both cost columns. The rule does capture the two clicks that open the plan — `C(6,25)` and `C(7,25)`
are on the reversed-axis fall path from `(6,23)` and `(7,23)`, which the body can walk to — and it
names them in terms of the mechanic rather than in pixels, so it should carry to boards where the
distance is different.

⚠️ **But it is NOT cheaper.** Both admitting rules cost about **4.6x the searched states and 6.3x
the nodes** of the rule crag ships. That cost is a property of the ROUTE, not of how the candidate
set is phrased — a searcher that can build a floor it is not standing on has a bigger frontier, and
no phrasing avoids paying for it. So the honest read of the whole curve is that bp35's level 6 is
bought with a 4.6x search, an edit cap raised from 6 to 8, and an expansion cap raised from 40,000
to about 120,000 — and crag's own record (one extra candidate cost it two levels) says that bill
lands on the other twenty-four games, which only a full-25 gate can price.

⛔ A fourth thing has to be true and is not measured yet: crag must KNOW where the exit is before it
will plan a route at all (`_search(targets, "exit", ...)` needs `targets`), and the gem sits eight
rows and two gravity reversals away from the start. Reaching it costs more than the 64-action
allowance, so the map has to be built across level RESTARTS — which crag's docstring says it does,
and which nothing has yet checked on this board.

### ⛔ bp35 LOSES THE LEVEL AT 64 ACTIONS, and that is the game's real shape

`qmjscfjptx.render_interface` draws `hbqwwgceeqp` — a count of every action taken since the level
began — as a bar along frame row 63, and:

```
level 10        hbqwwgceeqp >= 192  ->  lose()
levels 1..6     hbqwwgceeqp == 64   ->  lose()
levels 7..9     hbqwwgceeqp == 128  ->  lose()
```

MEASURED, not read (rule 7g): 64 consecutive ACTION7s from a fresh game give
`action 63 used=63 state=NOT_FINISHED` / `action 64 used=64 state=GAME_OVER`. The branch fires.

Against the game's own `metadata.json` baselines `[21, 48, 44, 38, 33, 87, 86, 131, 163]`:

- levels 1-5 are all inside 64, so a human clears each in ONE attempt;
- **level 6's baseline of 87 EXCEEDS its 64-action allowance**, and so do levels 8 (131) and 9 (163)
  against their 128 — those baselines already contain a RETRY.

This is what bp35's attempt headroom (+0.1283, `scripts/attempt_probe.py`) has been made of all
along: a level lost on its allowance is silently restarted with a fresh one, the score keeps paying
for the actions, and the run reads as one slow clear. The measured `L2 87 actions vs 48 human`
(0.304) is not a slow attempt — 87 > 64, so it is two attempts.

⚠️ And the allowance is FRAME-VISIBLE: row 63 is a bar exactly `hbqwwgceeqp` pixels long. A
frame-only tool can read its own remaining budget off the bottom row — which is the same edge band
`tools/segment.board_changed` deliberately ignores, so nothing currently looks at it.

### What this leaves for the tool

crag's vocabulary is already right — it has `_vanish`, `_swap`, `_flip` and `_inert`, and `_swap` is
precisely this toggle. What it does not have is the SEARCH: `_sites` offers only the support cell and
the two beside it, and the cheapest measured plan clicks **ten** toggle cells, most of them nowhere
near the body, to build a walkway across the spike rows. A 46-to-57 action plan with 13 to 24 clicks
in it is not reachable from a four-candidate frontier two clicks deep, whatever budget it is given.

⛔ So the standing conclusion — *"this board needs terrain that degrades on its own"* — is withdrawn.
Nothing degrades on its own. The board needs a searcher that will click a cell it is not standing on.

## TWELVE games declare a per-level ALLOWANCE, and the HUMAN BASELINE exceeds it on 26 levels (2026-08-29)

Found while closing bp35, and it generalises well past that game. Eleven games carry a
`"StepCounter"` or `"MaxSteps"` literal in their level data; bp35 carries the same thing as a bare
constant in `render_interface` instead. Set each level's allowance beside the baseline the metric
scores us against (`metadata.json: baseline_actions`):

```
game   lvls  levels whose HUMAN BASELINE is ABOVE the level's own allowance      worst
wa30      9  L2 119/70  L3 183/100  L5 368/125  L8 442/150  L9 415/70            5.93x
ls20      7  L2 123/42  L3 73/42  L4 84/42  L5 96/42  L6 192/42  L7 186/42       4.57x
tu93      9  L4 42/20  L5 123/50  L6 80/60  L9 111/50                            2.46x
cn04      6  L4 300/125  L5 208/150                                              2.40x
lp85      8  L1 17/13  L8 159/80                                                 1.99x
ka59      7  L7 326/200                                                          1.63x
re86      8  L7 424/300                                                          1.41x
bp35      9  L6 87/64  L8 131/128  L9 163/128                                    1.36x
vc33      7  L4 61/50                                                            1.22x
s5i5      8  L5 162/150                                                          1.08x
ar25      8  (none)
dc22      6  (none)
```

**26 of those 92 levels have a baseline larger than the level's own allowance**, and a baseline
larger than the allowance cannot be a single attempt. ⛔ **So the human baselines already contain
RETRIES on ten of the twelve games**, and the consequences run the other way from the obvious
reading:

- On those levels, "match the human" does NOT mean "solve it inside the allowance". The human died
  too. wa30's level 9 allows 70 and the baseline is 415 — that is roughly six attempts.
- Because a lost level is silently restarted while the score keeps every action already spent, the
  lever on these games is **the NUMBER of failed attempts**, not the length of the winning one.
  That is what `scripts/attempt_probe.py` prices, and it is why bp35's headroom (+0.1283) is an
  attempt problem: its L2 cost 87 actions against an allowance of 64, so it is two attempts, not
  one slow one.
- And it says what the first attempt is FOR on a level nobody clears in one: mapping. A tool whose
  world map survives the restart is playing the level the way its baseline was set.

⚠️ ar25 and dc22 declare allowances that no baseline exceeds, so they are the control: an allowance
existing is not the same as an allowance biting (rule 7g, and wa30's declared 70 was measured NOT to
fire at all on level 9 — the branch never ran). Which of the twelve actually END on overrun has to
be measured per game, and bp35's is the only one shown firing so far
(`action 63 NOT_FINISHED / action 64 GAME_OVER`).

## ⛔ REFUTED — the allowance is NOT frame-readable except on bp35 (2026-08-29)

I proposed a frame-only "allowance reader" off the back of bp35's row-63 bar, and argued it would be
one asset serving the ten games whose baselines exceed their allowance. **Measured on all 25 (one
process per game on ceph-build, 1200 actions each, shipped harness), that is wrong.**

The test: for each of the four outer bands, count the cells differing from the band at the start of
the current attempt, and ask whether that count equals `actions // s` for some small integer scale
`s` — scale 1 is bp35's rendering and is not a law, so a 30-pixel bar for an 80-action allowance
still scores.

```
game  band   scale   hit    what it is
bp35  row63    1    0.996   an EXACT action counter; max 64 = its declared allowance; 18 resets
tr87  row63    2    0.778   a real clock at two actions per pixel — and tr87 declares NO allowance
g50t  row63    2    0.456   its scrolling timer sprite, partial
lp85  row0     8    0.333   \
ar25  row0     8    0.273    |  scale 8 is the DEGENERATE fit: the band barely moves while
cn04  row0     4    0.252    |  `t // 8` is also small, so the two agree by staying near zero.
sc25  row0     8    0.210    |  Not a counter.
...   ...      8   <0.20   /
```

⛔ **Of the twelve games that DECLARE a per-level allowance, exactly ONE draws it readably.** And
the two games that do draw a clock — tr87 and g50t — declare no allowance at all. The declared set
and the drawn set are disjoint apart from bp35, so a pixel reader is a one-game asset, which is
precisely what I argued it was not.

### The cheaper mechanism the refutation points at: learn it by DYING once

The reader does not have to read anything. `obs.state` reports `GAME_OVER` directly, so attempt
boundaries are already free, and the action count at that moment IS the allowance whenever the game
ends on overrun. If a level's deaths are all the same length, ONE death teaches the number for every
later attempt at that level — frame-independent, and available on every game rather than on the one
that happens to draw a bar.

That is what `scripts/_deathclock_probe.py` measures: attempts split at `GAME_OVER` and at level
changes, their lengths, and whether the deaths on a level agree with each other. Scattered death
lengths would mean the game ends for some other reason (a hazard, a lost life) and the learned
number would be a fiction; zero deaths on a game that declares an allowance would mean the allowance
does not bite there, which is rule 7g and has already caught wa30 once.

⚠️ **Instrument note, because it nearly became a finding.** The first version of the reader probe
capped the frame history at 8 to save memory, and ls20 — which normally clears six levels — ended
the run on level 0 with seventeen restarts. The tools read their own history out of that list, so
trimming it changes the run being measured. Uncapped, ls20 still ends on level 0 at 1200 actions,
so the depth figure is a budget difference and not the trim; but the trim would have been reported
as a property of the game. The second defect was the opposite kind: the engine returns `frame=[]`
while a game sits in `GAME_OVER`, which is exactly the moment this probe exists to observe, and
indexing it crashed the runs on the games that die most.

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

### The refuel rule arrived with an EMPTY TANK — 303 -> 237 actions on level 7 (2026-08-29)

`_refuel` diverted only when `left <= dist + 1`: a route that reaches the pickup with nothing
in the tank and no margin for the walk being one step longer than the map predicts. Measured
across three fan-outs of 24 runs each (`scripts/_ls20_fuelfan{,2,3}.py`, twelve policies twice
over; **every variant returned byte-identical numbers on both runs, so ls20 is deterministic
and one run is a measurement**):

```
slack 1 (as written)   303 actions   dry 5   7/7
slack 2 3 4 5 6        237-239       dry 4   7/7      <- one plateau, not a curve
refuel REMOVED         506           dry 7   6/7      <- the clause is LOAD-BEARING
```

Shipped as `dist + max(3, full // 5)` — written against the tank so a smaller one is not
over-served, and chosen from the middle of the plateau rather than its best point, because a
2-action difference across slack 2..6 is not a tuning surface. **ls20 0.8442 -> 0.9039**
(level 7 `(186/237)^2 = 0.6157`), **+0.0024 on the 25-game mean**.

⛔ **THE OVERLAY DEATH DETECTOR UNDERCOUNTS 5-TO-1.** The entry above this one sized level 7 as
"runs dry TWICE" from frames repainting more than half the board. Reading the tool's own
`moves_left()` instead: the tank reaches **ZERO at ticks 10, 32, 54, 143 and 225** — five dry
deaths, of which the full-screen test sees one. On a fogged board a large repaint is ambiguous
and the tank is not; `moves_left() == 0` is the honest detector and costs nothing.

⛔ **AND THREE OF THE FIVE HAPPEN BEFORE THE TOOL CAN POSSIBLY REFUEL.** The first cell it knows
to be a refill appears at **tick 73**, because `refill_marks` is learned by standing on one and
watching the bar jump. Until then `_refuel`'s candidate set is EMPTY and no threshold on it can
matter. So the deaths split cleanly: three are the price of not yet knowing what a refill is,
two are the ones slack recovers.

**Where the 303 actually went**, attributed by the tool's own clause, split at the first death:

```
attempt 1  155 actions   map 59, tread 56, mark 21     stood   1 -> 65
attempt 2  136 actions   win 87, refuel 30, press 11   stood  65 -> 65   (ZERO new cells)
```

⛔ **LEVEL 7 IS NOT A DISTANCE PROBLEM, AND THAT RETIRES THE WHOLE "PLAN A TOUR THROUGH THE
PICKUPS" IDEA.** Taking the map the tool itself finished with — 140 open cells, a 21-move tank,
its two known refills — and solving start-to-goal as a fuel-constrained BFS over (cell, fuel)
gives **10 actions**. The goal is ten steps from the start. Every one of the remaining 237 is
discovery under fog plus the token puzzle, so no routing improvement can approach the human's
186 by shortening the walk.

**Measured and REJECTED, each twice:**

| idea | result |
|---|---|
| gauge-colour prior: the pickup is drawn in the gauge's OWN colour, so a ring is a refill on sight | finds one at tick **4** instead of 73, dry 4 -> 3, and **costs 26 actions** (263) — it then diverts all game, refuel 43 vs 17 |
| the same prior BOUNDED to "only until one is confirmed" | **263, identical** — the cost is not the prior's lifetime |
| the prior at baseline slack | **502, level LOST** |
| top up whenever a refill is one step away and the tank is not full | 382 |
| refuel first when the goal is further than the tank (`_search` never sets `_plan_dist`, so the win walk is committed to unpriced) | 241 alone, **281 when combined with slack** — the two interfere |
| an absolute feasibility rule (plan longer than tank + refill in range -> always go) | inert, identical to control |
| `_PURSUIT_CAP` 15 or 60, `_SIGHT_RETRY` 100, `_STALE_LOOK` 120 | all inert |
| `_STALE_LOOK` **30** | **502, level LOST** — re-looking twice as often is a cliff, not a dial |

⚠️ The rejected rows matter more than the accepted one: FOUR of them lower the death count or
look strictly more informed, and every one of them costs actions or loses the level. Fewer
deaths is not the objective; **arriving with slack is**.

**What is left, and why it is not a fuel question.** At 237 the clauses are map 59, tread 56,
win 38, mark 22, press 17, refuel 17, look ~28. `win` is tried FIRST in `_plan`, so map and
tread only ever run *because no winning route exists yet* — they are not waste by construction.
Closing the last 51 actions to the human's 186 means making the win route available sooner,
which is a question about learning the target token, not about fuel.
**Where the other 227 go — measured, not reasoned (`scripts/_ls20_where227.py`, 24 runs).** The
instrument asks, every tick, whether a winning (cell, token) route EXISTS and how long it is —
the same joint search `_plan` runs, so it cannot disagree with the planner:

```
237 actions  =  12 handover to keymaze  +  170 DISCOVERY  +  55 EXECUTION
   a winning route first exists at tick 170, and it is THIRTY-THREE steps long
   route length from there: 33 -> 25 -> 23 -> 15 -> 17 -> 9 -> 5   (clean, no oscillation)
   discovery: map 59, tread 56, mark 21, press 15, look 15   execution: win 38, refuel 15, press 2
   goal AND target known at tick 55 · first refill known at 73
   changer tables closed at ticks 67, 69 and 138 — the THIRD is the critical path
```

⛔ **THE WINNING ROUTE IS 33 STEPS, NOT 10.** The ten-action lower bound above ignores the token,
and the token is the level: the route has to detour through three changers to arrive holding
what the target demands. Execution spends 55 actions walking a 33-step route with 15 refuels in
it — that is near-optimal, and there is nothing to win in the second half of this level.

⛔ **AND EXPLORING LESS LOSES THE LEVEL — SIX INDEPENDENT WAYS.** Capping `map` at 40 actions,
capping `tread` at 30, stopping `tread` at 60 cells stood, stopping it at 45, and biasing the
frontier toward the known goal ALL end 6/7 at ~502 actions with 7-11 dry deaths. The only
variants that hold 237 are the two that turn out to be inert (skip the patrol while a win
exists — looks only happen when none does; explore only within reach of a refill — never
fires). So the 170 discovery actions are not slack, and "explore toward the goal" is actively
harmful here: the third changer is not near the goal, and a frontier that prefers the goal
never reaches it.

⚠️ That makes ls20 the clearest case in this file of a level where the tool is ALREADY near its
own floor and the remaining loss is structural. The one measured gap worth a future look is the
**32 ticks between the third changer's table closing (138) and the first winning route (170)** —
everything the route needs is known at 138 and the search does not return one until 170.


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

## ⛔ dc22 LEVEL 6 IS SOLVED — 141 actions, dc22 goes 0.7143 -> 1.0000 (2026-08-29)

**MEASURED, twice, and once through the shipped harness path:**

```
scripts/_dc22_planverify.py  level 6 alone   {"result":"CLEARED","direction":"UP","state":"WIN","actions":141}
scripts/_dc22_oracle_full.py  full game    levels_completed 6/6, total_actions 566, game_score 1.0000
  per level  L1 31/59  L2 53/102  L3 59/67  L4 87/98  L5 195/324  L6 141/578   every level 1.0
```

Levels 1-5 are the generic tools' own play (425 actions, unchanged); level 6 is a fixed
141-action plan. **Deterministic: three repetitions on ceph-build return 6/6 levels, 566 actions
and game_score 1.0000, identical** (`scripts/_dc22_oracle_rep.py`). **dc22 0.7143 -> 1.0000 is +0.0114 on the 25-game mean** — the target is real
and its size is confirmed. ⚠️ The plan is an ORACLE: it was derived from the game's source and
executed as a script. **No generic tool clears this yet**; what follows is the mechanic and the
exact two model gaps that stop `gantry`.

### The control scheme, and why every sweep so far measured nothing

Read from `environment_files/dc22/*/dc22.py` and confirmed by running:

| entity | what it does |
|---|---|
| `njvd-rolo` (4 of them) | **PRESSURE PLATES.** `yuonzbouxb()` makes every `buezna` carrying the plate's single-character tag VISIBLE+INTANGIBLE while the avatar OVERLAPS the plate, and INVISIBLE otherwise |
| `crzsjq-up/lersnf/riidpd/lersnf-2` | the four crane-drive buttons — each gated by one plate (b=up, e=left, a=right, h=down) |
| `piyqze` keys | walking over one sets every `buezna` with its letter permanently INTANGIBLE. Level 6 has two: **'d' at (6,18)** unlocks the colour-cycle button, **'g' at (34,48)** unlocks the crane's grab button. Both start `visible=False` |
| `sprite-6` at (53,5), letter 'f' | shifts a three-row staircase of `moxubw` bars 2px right per press, **period 6** — the only thing that ever connects the avatar's start island to the left of the board |
| `buezna-matkhq` at (48,23), letter 'c' | **TELEPORT.** Standing exactly on a `tewfut` tile moves the avatar to the tile sharing its prefix, and swaps every group-c form (period 2) — including the 20x20 `brixto` platform, whose two forms differ in shape |
| tile at (18,48), `tewfut-color-cycle` | the teleport's **DESTINATION SELECTOR**. The 'd' button re-prefixes it through `[pibpar, refgps, yefmyf, blrmbx]` and the teleport goes to the tile with the matching prefix: (32,52) / nowhere / (4,4) / (34,58) |
| `brixtocrzsjq-1` at (22,30) | a crane on a `vcha` rail. With the grab button unlocked it picks up the 20x20 INTANGIBLE `brixto` platform (its centre must equal the crane anchor) and carries it; parked at the rail's top it bridges the gap to the goal platform |

⛔ **THE ORDER IS MOVE-THEN-CLICK, AND EVERY PREVIOUS dc22 SWEEP HAD IT BACKWARDS.** The 4,096
click-then-move sweep clicked from a fixed position at which the four crane buttons DID NOT EXIST
— `xodizggcom` skips INVISIBLE sprites, so those clicks were no-ops by construction. A sweep that
enumerates clicks from one standing position cannot see a plate-gated control at all.

⛔ **AND A CONTROL SET RE-READ FROM THE FRAME IS STILL NOT ENOUGH.** Control:
`scripts/_dc22_livesearch.py`, 12 seeds x 4,000 actions on ceph-build, action set = the four moves
plus one click per sprite that is LIVE at that instant. **Zero clears**, 583-781 distinct boards
per seed (blind cell-sweeping reached ~130 in 900). Random play does pick the 'g' key up
(`crzsjq-grawwq-1` appears in every seed's live set) and never the 'd' key.

### The plan, and the search that found it

`scripts/_dc22_model.py` mirrors the engine's own `sxnzvaqltp` (support) and `collides_with`
(blocking) predicates and **verifies them cell by cell against the live engine first: 0 mismatches
over all 1024 even cells** (rule 7b — prove the instrument is attached). It then BFSes the joint
state `(bar phase 6 x group-c parity 2 x cycle prefix 4 x crane rail cell x platform position x
two keys x avatar cell)`, 297,307 states expanded, and returns a 141-action plan
(`scripts/_dc22_plan.json`). The shape of it:

```
walk left + 4x 'f'         descend onto the shifting staircase and cross to the left of the board
'c'                        the platform's OTHER FORM is what opens the climb up the left side
walk up                    take the 'd' key at (6,18)      -> the colour-cycle button goes live
'c' back, 'd' x3, 'c'      re-aim the teleport and ride it to the plate cluster at (34,58)
plates + crane drives      walk the crane left to the platform, GRAB, carry it to the rail's top
'c','d' x3,'c'             re-aim again and teleport to (4,4)
walk right                 cross the carried platform to the goal at (46,6)
```

Each leg was measured on its own before the whole: the joint `(bar phase x cell)` graph reaches
57 cells and NO landmark; adding the group-c parity takes it to 120 cells and makes the 'd' key
reachable in **42 actions, executed and confirmed live**.

### ⛔ Why `gantry` retires EMPTY — measured on the live frame, and it is ONE field

`scripts/_dc22_gantrygeom.py` plays to level 6 with the generic tools and dumps the tool's own
perception of that frame:

```
split (42,42)   board = columns 0-41    panel = columns 42-63    detect = 0.86
goal (goknoi-dokmdr, colour 11) at rows 6-7, columns 46-47
colour-11 pixels: 3 on the board, 44 in the panel
```

**gantry routes over columns 0-41 and dc22 level 6's goal is at column 46 — inside what the tool
calls the control panel.** There is no goal cell in the board it searches, so its route BFS
returns nothing and it takes the `gantry:501 if found is None` exit. That is exactly the retire
signature already recorded for this game, and it is not a search failure: the tool never had the
goal. Levels 1-5 clear because their goal is on the board side.

⛔ **AND NO VERTICAL SPLIT CAN WORK HERE — the controls and the goal share the same band.**
Columns 42-63 hold the four crane buttons (x45-56), the teleport control (x45-57), the staircase
control (x53-59), the colour-cycle control (x49-52) AND the goal platform (x42-49, y4-11) with the
goal itself at (6,46). The tool's own output shows the collision already: one of the seven "panel
buttons" it lists is **(7,45)**, which is a floor tile of the goal platform, not a control. So the
repair is not a better split column; it is that the board must be the WHOLE frame and controls must
be identified as controls rather than as "everything right of a column".

⚠️ Fixing the split alone will NOT clear the level. `gantry` already carries the right vocabulary
— phase rings, warps, and a driven gantry with a rail — and **two model gaps remain, both nameable**:

1. **The warp map is static where this board's is aimed.** `self._warps[(click, pos)] -> landed`
   is keyed on the press and the cell it was pressed from. On dc22 level 6 the SAME press from the
   SAME cell lands somewhere else after the 'd' control has been pressed, because that control
   re-prefixes the tile the avatar is standing on. A warp destination that is a function of
   another control's phase cannot be expressed.
2. **A drive can be gated on where the avatar STANDS.** The rail walk presses drives to learn
   `_edges[off][click]`, but each of the four drives here only exists while the avatar is on its
   own plate. The panel is correctly re-read when it changes (`gantry:636`), so the buttons are
   seen; what is missing is that reaching a rail cell requires walking to a specific board cell
   between presses, which makes the rail walk a joint (rail, avatar) search rather than a rail one.

### ⛔ Four earlier dc22 claims, corrected

- **"the tool arrives in a POCKET of three boards."** WRONG. The avatar's start component is
  **18 cells** (x18-28, y48-52). The "three boards" came from pressing up, down, left, right in
  that order — an inverse-pair test that never measured down-from-start or right-from-start.
- **"the board is COMPLETELY INERT outside rows 0-32."** WRONG as stated. Two controls are live
  from the first frame at (53,5) and (48,23), and five more at rows 17-46 become live once their
  gate is satisfied. What is true is that no single click from the start position visibly moves
  anything else.
- **"the colour-cycling tile is NOT the blocker."** Half right. Pressing it and handing the board
  back clears nothing — correct, and the test was worth its four runs. But the tile is
  load-bearing: it AIMS the teleport, and the plan presses it six times.
- **"the level-6 goal carries an extra `buezna` tag that a frame-only tool cannot see."** That tag
  is INERT. `goknoi-dokmdr` has no single-character tag, so `swmjqbirpa` returns None and clicking
  it does nothing at all. It is not what stops the level; the board/panel split is.

Artefacts: `scripts/_dc22_model.py` (model + search), `scripts/_dc22_plan.json` (the 141 actions),
`scripts/_dc22_planverify.py` (executes it on the engine), `scripts/_dc22_oracle_full.py` (full game
through the harness), `scripts/_dc22_gantrygeom.py` (what gantry sees),
`scripts/_dc22_livesearch.py` (the live-click blind control).


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

### ⛔ RETRACTED — wa30 is NOT lost on its budget; the budget never bites

⛔ **AND THIS RETRACTION IS ITSELF WRONG — see "wa30 LEVEL 9 IS CLEARABLE IN 70 ACTIONS" below.**
The budget DOES bite: nine GAME_OVERs in a 700-action run, every policy, and the raw engine reaches
`GameState.GAME_OVER` on action 70 under a constant press. The section below stands; everything in
this one that follows from "the branch never fires" does not.


Last tick I concluded wa30's level 9 is "an EFFICIENCY problem, not a missing mechanic", because the
level declares 70 steps and shepherd spends 508. Measuring what those 508 actually are:

```
attempts on level 9 (actions, actions that moved the board): [(507, 506)]
```

**One unbroken attempt.** No restart, no repaint, and 506 of the 507 actions change the board. So the
declared allowance of 70 is not enforced here — `elif not current_steps: self.lose()` does not fire —
and wa30's last level is not lost on time.

Which withdraws the whole reading: shepherd plays 507 effective actions on a level it never loses and
still cannot clear it. That is the same wall as dc22, bp35 and lf52, not a different and cheaper one.

⚠️ And it removes the case for wiring `BudgetReader` into shepherd. The reader is real, 6/9 accurate
and used by one tool of forty-seven — that finding stands — but the game it was going to be wired
for does not enforce the budget it reads. **A working asset is only a lever where the thing it
measures actually binds.**

⛔ Third retraction of the round, and all three share a shape: a number read from the game's SOURCE
(a declared StepCounter, a lose() branch) taken as a description of what the game DOES, without
checking that the branch runs. The source says what is possible; only the run says what happens.

## ⛔ wa30 LEVEL 9 IS CLEARABLE IN 70 ACTIONS — witness verified, and the budget DOES bite (2026-08-29)

Both of the round's earlier readings of this board were wrong, and the second one — the retraction —
was the more expensive, because it turned a solved-looking efficiency problem into a "capability
wall" and sent the next tick looking for a missing mechanic.

```
retracted claim   "one unbroken 507-action attempt, no restart -> the branch never fires"
MEASURED          every policy, 700 actions, level 9:  losses 9, attempts 10
                  the raw engine reaches GameState.GAME_OVER on action 70 under a constant press
                  the shipped harness: attempt 0..5, "70 actions" each, every one
```

`elif not self.kuncbnslnm.current_steps: self.lose()` **fires, on the seventieth action, every
time.** What the earlier probe read as one long attempt was ten attempts of seventy: a
`level_reset` restores the board, which keeps "the board changed" true, so counting frame changes
cannot see an attempt boundary. ⛔ Split attempts on the game's OWN state (`_state ==
GAME_OVER`, or the step counter returning to its maximum), never on whether the frame moved.

**And the level clears.** `scripts/_wa30_search.py` hill-climbs the CARRIER'S SCHEDULE — which
pieces it takes, in what order, into which bay, how long it stands still first — replaying every
candidate in the real `Wa30` object for the full 70-action allowance. Eleven of twelve seeds found
a clear; the best takes **66 actions with four to spare**. One witness replayed independently
outside the search: 9 of 9 resting, `GameState.WIN`, on action 70 of 70.

```
seed  4: CLEARED  66 actions   311 candidates
seed  5: CLEARED  66 actions 11346
seed  6: CLEARED  68           2966       clears at 66,66,68,68,69x5,70,70
seed  1: CLEARED  70            863
```

⚠️ **So wa30 is worth the FULL +0.0080, not a fraction of it.** The human baseline for this level
is 415 actions against an attempt of 70 — the human lost about five times before clearing — and
RHAE pays `min(415/ours, 1)^2`. A tool that clears on its fifth attempt (350 actions) still scores
**1.0000** on the level. The efficiency question is settled before it is asked; only the clear is
missing.

### What the board is, in cells

```
   0123456789012345      p piece (9)      B bay cell (13, two sealed)
 0 .........#......      M mover (2)      D den cell (4)
 1 .........#.M....      T thief (1)      X no-go   # wall/occupied
 2 .........#...BB.      C carrier
 3 ..p..BBB.#XXXXXX
 4 .....BBB.#......      pieces  (1,5) (1,7) (1,8) (2,3) (2,7) (3,5) | (11,5) (12,7) (14,8)
 5 .p.p.BBB.#.p....      bays    3x3 at cols 5-7 rows 3-5, plus (13,6),(14,6)
 6 .........#...BB.      sealed  (13,2),(14,2) above the no-go band — unusable
 7 .pp.M....#..p...      den     (1,7),(2,7),(1,8),(2,8) — THREE pieces start inside it
 8 .pD.....C.....p.
 9 ................      row 9 is the only way between the two halves
10 ..#.############
11 ..#.#...#...#...      the thief starts at (15,14), deep in this comb
12 ..#.#.#.#.#.#.#.
13 ..#.#.#.#.#.#.#.
14 ..#.#.#.#.#.#.#T
15 ..#...#...#...#.
```

The wall at column 9 spans rows 0-7 only, so the two halves meet on rows 8-9. The second mover at
(11,1) is sealed above the no-go band with the two unusable bays and **moves zero cells in seventy
actions** — the board has one working mover, and eleven usable bays for nine pieces. `shepherd`'s
docstring already had all of this right; what it did not have is that the level is winnable.

### What FAILS, and it is the interesting half

Every one of these ran in the exact engine, so none of them is a modelling artefact:

```
policy sweep, 6 policies x 5 seeds, 700 actions each   best coverage in ONE attempt
  carrier passes (movers work alone)                     4 of 9
  carrier kills the thief, then passes                   5
  carrier acts at random                                 4-5
  carrier hauls greedily, nearest first                  8
  the shipped harness (shepherd)                         8
  kill the thief first, then haul                        5
eight FIXED ranking rules x three thief policies         max 7  (never 8)
primitive-action beam, exact engine, width 150-1000      max 8
beam over whole DELIVERIES, width 60-500, 1-3 bays each  max 8
schedule hill-climb, exact engine                        9 — CLEARS
```

⛔ **No fixed ranking rule reaches even the incumbent's eight.** Dearest-drag-first, dearest-total-
job-first, farthest-from-the-mover-first, our-half-only, orphans-only — the eight rules tried top
out at seven. And the two beams fail for a shared reason worth naming: **they rank a partial
schedule by what it has banked so far**, and the delivery that decides this board is the piece on
the far side of the split wall, which costs about sixteen actions and returns one. A search that
prefers the cheapest next delivery spends the allowance on near pieces and strands it — which is
exactly the failure `shepherd`'s own park predicted, in those words, before any of this was run.

⚠️ The eleven winning schedules **do not agree on an order**. Their first target is the far-left
column piece in four of eleven and the far-right piece in four; their pauses (0-7 actions before a
target, and standing still is a real move because the mover retargets to the nearest free piece)
are scattered. Every one of them handles the thief — kill radius 2, 4 or 6, never 0. So what is
recoverable as a RULE is only "take the awkward ones, let the mover have the middle, deal with the
thief"; the schedule that actually fits into seventy is found, not derived.

### The next step, stated as work

`shepherd` cannot run this search: it needs to score a candidate schedule before committing, and
the only scorer used here is the engine. But the three actors it would have to model are the three
it **already reads correctly** (its docstring records the hazard band, both bay shapes and the
thief region all checked against the engine), and their rules are small: a mover walks to the
nearest free piece by breadth-first search, grips it when adjacent, walks so the piece lands on a
bay, lets go; the thief is the same toward the den; a grip costs the actor its whole turn.

So the build is: a forward model of movers-and-thief inside the tool, and the hill-climb above run
against it offline — median 3,000 candidates, which is seconds of compute, not actions. ⛔ It
cannot be run against the LIVE board instead: a candidate costs 70 actions there, and 3,000 of them
is 210,000 actions for a level whose baseline is 415.

Probes, all committed: `scripts/_wa30_l9.py` (six policies), `_wa30_last.py` (which piece is left,
and whether it is reachable — always "reachable"), `_wa30_beam.py`, `_wa30_macro.py`,
`_wa30_plan.py`, `_wa30_search.py` (the one that clears).

⚠️ **`scripts/pfan.sh` destroyed this round's first 30-way fan** — it wrote to a fixed
`/tmp/pfan.jsonl` and `rm -f`'d it at launch, so a peer's fan wiped mine and I read back somebody
else's game. Fixed since to `/tmp/pfan_<name>.jsonl`; the lesson is the general one, that a shared
scratch path between concurrent agents is a silent data corruption, not a collision that announces
itself.

## s5i5 level 7 is ONE target away — and the count never moves (2026-08-29)

s5i5's win is the game's own predicate: every `0087vvmblxkzdi` target must have a `0064ocqkuqacti`
mover at the same x,y. Instrumenting that predicate during a real run (rule 7g: the source said what
the condition is, this is what happens):

```
level 6 -> 7 after 31 actions
  level 7: 1/2 targets covered at action 1
stopped on level 7 after 503 actions; best coverage (1, 2)
```

**There are only TWO targets, and one is already covered when the level starts.** Clearing the game's
seventh level means covering one more — and across 503 actions the count never rises above 1, not
once.

That makes s5i5 different from dc22 and wa30, where nothing at all opens: here the distance to a win
is a single target, and the tool spends five hundred actions without ever moving it. The handover is
visible too — `swivel` gives way to `linkage` on "action no new state x3".

⚠️ It also sharpens what to measure next, and it is not "why is this level hard". It is: **what is the
second target, where is the mover that must reach it, and is that mover reachable at all** — three
questions with concrete answers, on the game that is closest to a clear of any stuck game on the
board.

## re86 — CONQUERED, 0.9908 -> 1.0000, and all four actions were the SEAT and the FIRST FRAME (2026-08-29)

re86 cleared every level already; its whole shortfall was **level 2 at 46 actions against a human
baseline of 42** (`(42/46)^2 = 0.834`, and level 2 carries 2 of the 36 weight, so the game read
0.9908). It is now **1.0000, 8/8, 696 actions**, measured with the official scorer
(`--agent unified --titles re86 --max-actions 4000`), and the per-level counts are
`[25, 42, 49, 59, 113, 139, 101, 168]` against human `[26, 42, 86, 108, 189, 139, 424, 241]` —
identical across three runs.

### What the 46 actions actually were

`scripts/_re86_l2.py` answers six different questions in one parameterised probe (mode 1 trace,
2 ground truth, 3 optimal, 4 attempts, 5 fallback, 6 repeat, 7 which-branch-emitted), run together
rather than one at a time. The classification, from engine truth on every action:

```
46 actions:  move 40   select 6   INERT 0   refused 0   attempts 1 (never lost, never retried)
by branch:   _walk 34   _discover 7   _cycle 4   harness fallback 1
```

⛔ **Every action was effective — the "every action is EFFECTIVE" pattern holds here exactly.** There
is nothing to prune. The gap is that the tool's route was 46 where the same final placement is
reachable in 36: the three pieces need 34 moves (level 2's ground truth — pieces at (16,7), (30,21),
(35,29) walked to (7,37), (12,3), (14,35), 3 pixels a move) plus **2** presses of the cyclic select
control. `_walk` spent exactly 34. **All ten extra actions were spent choosing WHAT to drive and
WHICH WAY to nudge it, not on the route.**

### The three defects, each generic, each measured

1. **The discovery nudge was direction-blind.** A piece must be moved on both axes before its shape
   is measured, and `_toward` took whichever action came first in the learned control map. On this
   board that is ACTION1 (up) while two of three pieces had to go down — and every such move is paid
   for twice, once going out and once coming back. The nudge now heads for the middle of the
   still-uncovered marks wearing the piece's own colour. ⚠️ The NEAREST such mark was tried first and
   is worse (level 3: 52 against 50) — a piece usually covers several marks, so the middle is the
   heading.
2. **The very first move of a level had no heading at all**, because no piece is measured yet, so the
   choice fell to `known[0]` — again ACTION1. `_heading` uses the odd-coloured cell the driven piece
   wears at its middle to find which blob is in the seat, and pushes toward that colour's marks.
   ⛔ **Only before ANY piece is measured.** Offered on every wheel-less turn instead, it took the
   game from eight levels to four: with a piece known, the same choice recurs deep in a level where
   an action that closes on a mark can be one the board REFUSES, and three refusals retire a control
   the tool still needs.
3. **The plan was taken cheapest-move-first, and the select control is a RING.** The tool cycled past
   a piece that still had work and cycled back for it later: four presses where two would do. It now
   serves whoever is in the seat and still has a move, and only hands the controls on when the seated
   piece is finished. This is what took level 2 from 44 to 42.

### What IS carried from level 1, and what cannot be

Measured at the first frame of level 2: `cover_targets._effect` already holds all four direction
vectors — `{1: (-3,0), 2: (3,0), 3: (0,-3), 4: (0,3)}` — and `_select` is already 5. **The control
map is carried and costs nothing.** What cannot be carried is WHICH BLOB IS A PIECE: objecthood on
these boards comes from motion, the pieces are new every level, and a piece is only measured once it
has moved on both axes. That is the 7 discovery actions, and at 2 moves plus a seat change per piece
they are close to their own floor. ⛔ So "it re-establishes the controls each level" was a plausible
cause and is FALSE — the cost is the direction of the nudges, not the fact of them.

### The one action nobody in the tool can fix

⛔ **Action 0 of level 2 is issued by the HARNESS, not by the tool, and it pushes a piece the wrong
way.** The level-transition frame carries the OLD board in layer 0 and the new board in layer 1;
`frame_2d` reads layer 0, `_marks` finds fewer than two marks on it and returns None, the tool
proposes nothing, and `UnifiedAgent._probe` fills the turn with `simple_ids[0]` = ACTION1 — which
moved a piece three cells up on a board where it had to go down. The tool's next action undoes it, so
**the cost is 2 actions, on every level**. This is rule 7c's "the fallback presses the lowest-numbered
key" in a second guise.

⚠️ Parking on the select control instead (the tool's own `_park`, whose docstring already argues for
exactly this) was MEASURED and is WORSE here: it hands the seat to a different piece and level 2 went
to 49. And parking on every unreadable frame rather than only the first cost four of the eight levels.
The fix is not in this tool: either `frame_2d` picks the layer that carries the new board, or the
harness probe prefers an action that moves nothing. Both are shared files.

### What the probe is for, beyond re86

`scripts/_re86_l2.py` mode 7 tags **which method of the tool emitted each action**. It was written
after the first heading fix moved two other levels and left level 2 byte-identical: without the tag,
"the nudge is direction-blind" is a reading of the source, not of the run (rule 7g). It is the same
instrument `scripts/trace_attribute.py` exists for, at tool-method granularity, and it is what turned
"four actions somewhere" into "one harness fallback, one blind first move, two ring detours".

## ⛔ `frame_2d` READS THE OLDEST SUB-FRAME — and every level transition in every game is stale (2026-08-29)

`frame_2d` is documented as "the (64, 64) int grid of the observation's **first layer**", and every
generic tool reads the board through it. An ARC-AGI-3 observation is not one grid: when an action
has a scripted consequence the engine returns **several layers, oldest first**. So the tool reads
the state the engine emitted FIRST — before the consequence — and never the settled board.

Measured across the set with `scripts/_layer_stale.py` (21 of 25 games at the time of writing; the
remaining four are the slow ones, and the pattern is 21 for 21):

```
game     acts  lvls  multi  behind  trStale        multi   = frames carrying >1 layer
ar25      269     8      7       7        7        behind  = of those, the LAST layer is closer
bp35      741     5    740     493        5                  than layer 0 to the board handed
cd82      133     6     43      38        5                  back NEXT — layer 0 is behind
cn04      262     6      5       5        5        trStale = the same, at a LEVEL TRANSITION
dc22      926     5     36       5        5
ft09       80     6      5       5        5
g50t      297     7    293     293        6
lp85      190     8      7       7        7
ls20      652     7     46      28        6
m0r0      189     6      5       5        5
r11l       84     6     43      43        5
re86      697     8     25      22        7
sb26      125     8     65      65        7
sc25      146     6     28      25        5
sk48      271     8    250     232        7
sp80      113     6      5       5        5
su15       90     9     88      85        8
tn36      138     7     26      18        6
tr87      146     6      5       5        5
tu93      188     9    186     186        8
vc33      200     7     19      19        6
TOTAL    5937   144   1927    1591      125
```

⛔ **`trStale` is `levels − 1` for EVERY GAME.** Not a subset, not a family — **every level
transition of every game hands the tool the board of the level it has just left.** And away from
transitions, 1591 of 1927 multi-layer frames (83%) are read stale; on `tu93`, `g50t`, `sk48`,
`bp35` and `su15` that is most of the run.

**Where it COSTS anything is much narrower, and that is the second measurement.** A stale read only
turns into a wasted action when the tool cannot make sense of it and returns nothing, because then
`UnifiedAgent._probe` fills the turn with `simple_ids[0]`:

```
fills = turns the tool did not propose      trFill = of those, on a transition frame
  dc22 16 (14 inert)   lf52 13 (8 inert)   bp35 8 (4 inert)   ls20 8 (8 inert)
  ft09 5 (5 on transitions)   re86 5 (5 on transitions)   ar25 1 (1)
  the other fourteen games: ZERO
```

Two different defects wearing one face:

* **transition fills** — ar25 1, ft09 5, re86 5, lf52 1. These are the layer question. On re86 each
  cost TWO actions, the push and the undo, because ACTION1 moved a piece the wrong way.
* **inert fills** — dc22 14 of 16, ls20 8 of 8, lf52 8 of 13, bp35 4 of 8. Mid-level, nowhere near a
  transition: the probe presses a key the engine refuses. The layer choice would not touch these.

⚠️ **Reading the LAST layer is the obvious repair and this measurement does not license it.** What is
proven is the ORDER — layer 0 is the oldest emitted state. What is NOT measured is whether the last
layer is the board a tool wants: on animation-heavy boards it may be a frame caught mid-consequence
rather than a settled one, and 14 of 21 games have no fills at all, so most tools read stale boards
today without paying for it. The change belongs in the harness, behind a full-25 gate.

### ⛔ THE INSTRUMENT TOOK SIX VERSIONS, AND FIVE OF THEM SCORED THE KNOWN POSITIVE AT ZERO

re86's transition frame was verified BY HAND first — layer 0 carried colour 11 (level 1's palette),
layer 1 carried 12 and 13 (level 2's pieces). Any correct instrument must report it. Five did not:

```
v1  layer 0 held still while a LATER layer moved since the last frame
    -> re86 emits ONE layer until the transition, so prev[1:] is empty and it can never fire
v2  a later layer showed what layer 0 did not, and the NEXT frame's layer 0 is exactly that
    -> an ACTION happens in between and moves a piece; and it fired 150x on an animation settling
v3  at a transition, layer 0 identical to the previous frame's layer 0
    -> the level-CLEARING move changed the board, so again never equal
v4  v3 with the seeded first frame removed
    -> that seed had been adding a constant 1 to every game and reading exactly like a finding
v5  COMPARISON, not equality: is the LAST layer closer than layer 0 to the board handed back next?
    -> re86 answers 7, exactly its transition count. The FIRST version that sees its own positive.
v6  v5 widened off the transitions, where the real claim lives
```

⛔ **Every failed version was an EQUALITY, and an equality cannot survive a frame boundary** — an
action happens there. The rule is the one rule 7b already states, paid for again: **run the checker
on input whose verdict you already know, in both directions, before reading its output.** A zero
from a detached instrument is indistinguishable from a measured negative, and four of these would
have been written up as "no other game has re86's problem".
