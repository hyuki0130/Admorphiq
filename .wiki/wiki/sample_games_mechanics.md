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

## lf52 — recoil launcher, read from the game's own source (2026-08-29)

`environment_files/lf52/271a04aa/lf52.py`, engine never started. Three facts that a frame probe had
only narrowed, and that together explain why level 6 stalls with actions to spare:

1. **Contact with a `fozwvlovdui` entity DISPLACES, and the displacement is per-level** (line 5296):

   | level | displacement on contact |
   |---|---|
   | 1-2 | none |
   | 3 | `(-dx*8, 0)` |
   | 4 | `(0, 0)` when `grid_y >= 11` |
   | 5, 6 | `(-dx*6, 0)` |
   | 7, 10 | `(0, 0)` |
   | 8 | `(0, -dy*6)` |
   | other | `(-dx*6, -dy*6)` |

   `dx`/`dy` is the direction of the move that made contact, so the board throws the piece SIX CELLS
   BACK along the axis it was travelling. A lattice model that assumes a move advances one cell
   predicts the wrong cell on every contact — which is what the harness sees as a refused action.

2. **The game keeps its own step budget and ENDS on overrun** (line 5771): level 1 allows 64,
   levels 2-5 allow `64*5 = 320`, levels 6+ allow `64*10 = 640`. One agent action costs 1.

3. **A death costs 20 of that budget** (line 5805), so thirty-two of them lose the level outright
   regardless of what else is played.

4. **There is a collectible power-up** (`cwyrzsciwms`, placed by `cncmupctrp`): picking it up sets a
   flag, and it is spent by an ACTION6 in the BOTTOM-LEFT 16x16 corner (`x < 16 and y > 48`), which
   is handled as a distinct branch rather than as a click.

⛔ The waste this level shows (117 refused ACTION1 of 138) is a SYMPTOM of fact 1, not a cause:
removing the wasted presses was gated on the full 25 and moved nothing.
