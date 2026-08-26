---
title: Tool selector — observable frame signature → which algorithm to run FIRST
type: reasoning
keywords: [tool-selector, first-pick, observable-signature, graph-frontier, cnn-rl, world-model, paint-flood, de-aliasing, dead-signature, orchestrator]
date: 2026-07-08
description: The local LLM's decision table — map what you OBSERVE in the first frames to the FIRST tool to run, with how-to-use, falsification (when it's failing → switch), and next-best. Perfect first pick within the tight budget.
---

# Tool selector (perfect first pick for the runtime LLM)

You are the brain. These are your hands. Pick the FIRST tool from what you OBSERVE — do not
guess. Run it; if its falsification signature appears, switch to its next-best. Every tool is
generic (triggers on frame features, never game identity).

**Output the tool's exact NAME** from this set: `graph`, `world_model`, `paint`, `toggle`,
`llm_goal`, `dealias`, `deadsig`, or `code`. The decision table's "Run FIRST" column IS that
name. **MEASURED (r53, all 25 dev games): `graph` is the only tool that clears games on its own
(7/25 across every mechanic class — navigation, click-state, transform); every other tool
standalone-cleared 0.** So `graph` is the DEFAULT first pick unless a narrow signature below
matches EXACTLY. The harness draws solved-board targets for graph automatically — you never
pick that. `code` is the LAST resort, never the default.

## Decision table (observe → run first)

| If you observe … | Run FIRST (exact name) | Because |
|---|---|---|
| ANY game where actions produce discrete repeatable state changes — movement OR clicks, navigation OR transform | **`graph`** | the measured default: exact transition graph + promise-frontier + multi-goal ranking + auto-drawn targets. Clears games in every mechanic class; nothing else clears any alone. |
| A click (ACTION6) FLIPS a small local set of cells on a TWO-colour grid, goal is a uniform board (true lights-out) | **`toggle`** | exact GF(2) solve. ⚠️ CORRECTED 2026-08-26: this row used to read "NONE of the 25 dev games is one" and "measured 0 elsewhere". Both are refuted by **vc33**, where `toggle` clears **2 levels in 113+143 actions** against `graph`'s 1 in 2,335 — 20x the efficiency plus a level graph never reaches (R100, full 20x5 sweep). Prefer it over `graph` on vc33-shaped boards; everywhere else in the 25 it still scores 0. |
| A click (ACTION6) verifiably FLOOD-FILLS a region with one colour (watch a click do it first) | **`paint`** | fill planning; only on verified fill mechanics — measured 0 when guessed |
| Same frame + same action gives DIFFERENT next frames (`nondeterminism` high) | **`dealias`** (then `graph`) | augmentation: de-alias the hash so graph stops corrupting (graph composes it internally too) |
| You have STRONG evidence a monotone progress measure exists AND graph already failed a full run | **`world_model`** | measured 0/25 standalone — a follow-up probe only, never first |
| Big regions recolor with no avatar AND graph already failed a full run | **`llm_goal`** | measured 0 standalone (the harness's auto target-draw supersedes it) — follow-up only |
| Every tool above failed a full run on this game | **`code`** | write Python to inspect the frame and queue actions (true last resort; measured 0 so far) |
| ANY game, always on (efficiency) | **`deadsig`** | stop re-probing action classes that never change anything |

## Per-tool: when to use / falsification / next-best

### graph  — graph-frontier BFS  ([[rounds/r36_graph-frontier-bfs]])
- **Observable signature**: discrete state changes; a movable avatar; repeatable frames.
- **Tool name**: `graph` (high avatar_mobility + has_movement).
- **How to use**: let it build the transition graph and walk promising frontiers by tier.
- **Falsification**: `recent_distinct` collapses to 1–2 while `bfs_fail/random` climb, or the same
  (frame,action) yields different next frames → the graph is aliasing; switch.
- **Next-best**: de-aliasing state hash (partial observability) or the world-model tool.

### toggle  — lights-out GF(2) solver  (`src/admorphiq/tools/toggle.py`)
- **Tool name**: `toggle` (a click flips a small local cell set on a 2-colour grid).
- **Observable signature**: clicking flips ~1-5 cells (itself + neighbours / a line),
  board is basically on/off, goal is a uniform board (all-off or all-on).
- **How to use**: it learns each click's flip stencil from your probes, then solves
  A·x=b over GF(2) and clicks exactly the solution cells — no brute force.
- **Falsification**: clicks repaint large regions (not a toggle) or the board has
  many colours → not lights-out; detect stays low, switch.
- **Next-best**: `paint` (if a click FILLS rather than toggles) or `graph`.

### paint  — paint-flood tool  (`src/admorphiq/tools/paint_flood.py`)
- **Tool name**: `paint` (high click_fraction; a click floods a region with one color).
- **Observable signature**: an ACTION6 click turns a background region into one color
  (measured su15: `0→5`, 30–50 cells/click); palette small; static between clicks.
- **How to use**: segment target vs filled; choose click points that flood uncovered target cells.
- **Falsification**: clicks stop changing the fill fraction, or fill overshoots the target.
- **Next-best**: executable world model (learn the exact fill rule) then plan.

### dealias  — de-aliasing state hash  (US-11; novel, no M1 winner has it)
- **Tool name**: `dealias` (high nondeterminism; augmentation, consulted by graph — not a mover).
- **Observable signature**: identical visible frame + same action → different outcome (hidden
  timer/off-screen entity). Diagnostic: high nondeterminism under frame-hash (dc22/g50t/wa30/sc25).
- **How to use**: augment the node hash for detected-aliased nodes with a bounded action-history
  k-gram so true-states separate; then run graph-frontier.
- **Falsification**: state count explodes (every step a new node) → the augmentation is too wide.
- **Next-best**: shrink the k-gram; or CNN-RL if the game is reactive.

### world_model  — online world model + goal planning  ([[rounds/r52_ewm-integration]])
- **Tool name**: `world_model` (low nondeterminism; deterministic learnable dynamics).
- **Observable signature**: deterministic transitions learnable from ~tens of probes; a clear
  progress measure (object count / ordering / fill / on-target).
- **How to use**: learn the per-game transition table from your own probes; roll out candidate
  actions toward the progress measure (foreground-object count, level-up bonus).
- **Falsification**: model stays too sparse, or planning picks moves that don't raise the measure.
- **Next-best**: graph (cheap exhaustive) or llm_goal (infer the target first).

### llm_goal  — LLM goal inference  (`src/admorphiq/tools/llm_goal.py`)
- **Tool name**: `llm_goal` (low avatar_mobility + large recolor_scale = transform/arrangement).
- **Observable signature**: big regions recolor or rearrange; no clear avatar; the TARGET pattern
  must be inferred, not searched (re86-class). Blind search plateaus here.
- **How to use**: once per level, serialize frame + observed transitions, ask the offline model
  "what is the level-complete target?"; then prefer actions reducing distance to that goal frame.
- **Falsification**: LLM unreachable (degrade to empty), or inferred goal never guides progress.
- **Next-best**: code (LLM writes bespoke solving Python) or world_model.

### CNN-RL online learner  ([[rounds/r36_graph-frontier-bfs]] era spine)
- **Observable signature**: reactive/timing dynamics, dense small frame changes, sparse level reward.
- **How to use**: online test-time RL (fresh per game, reset per level).
- **Falsification**: no level cleared after the convergence budget; reward flat.
- **Next-best**: graph-frontier or world-model.

### deadsig  — dead-signature prior  (US-12; always-on efficiency)
- **Tool name**: `deadsig` (always useful; augmentation that reorders, never removes).
- **Observable signature**: an action class repeatedly produces no hash change.
- **How to use**: deprioritize that class within its tier (never remove; one change revives it).
- **Falsification**: none — it only reorders; a wrong guess costs one probe.
- **Next-best**: n/a (composes with every tool).

## Notes for the orchestrator
- Prefer the CHEAP tools first (dead-signature always; graph-frontier for movement) — they cost
  few actions and the squared-efficiency metric rewards short solutions.
- Reserve the LLM-heavy tools (world model, code edits) for where cheap tools plateau.
- Maximize tool COVERAGE: the more well-characterized algorithms here, the more games get a
  correct first pick. Add a row + a per-tool block whenever a new generic tool is built.

**Related**: [[architecture_self_improving_agent]] (the 3-layer brain/hands/knowledge harness),
[[lessons/top_solutions_survey_20260708]] (baselines to beat).

## Measured note (2026-07-08): paint_flood ≠ su15 live mechanic
Built `paint_flood` tool + `PaintFloodAgent` (LLM-free) and benched on su15: 0/9. Diagnosis
(300 live steps): the flood mechanic is NEVER detected live (fill_color stays -1) even with
background-centroid probing — so su15's `0→5` transitions in the OFFLINE dataset are a side-effect
of a different mechanic (historical "vacuum/merge"), NOT click-to-fill. The paint_flood tool is a
valid generic primitive (detects/rejects flood correctly on synthetic + offline data) but su15 is
the WRONG target for it. Lesson: a transition-diff color-flip pattern (0→C) does NOT by itself
prove a click-to-fill mechanic — verify the tool ELICITS the effect LIVE before trusting it.
su15 needs its true mechanic reverse-engineered (a distinct tool). Do not keep tuning paint_flood
against su15.

## Measured note (2026-07-08): de-aliasing engages SAFELY but isn't sufficient alone
Built GF_DEALIAS (hidden-state de-aliasing, US-11) + tests (default-OFF byte-identical to the
18/25 baseline — guaranteed). dc22 bench: base 0/0 vs dealias 0/0 (no clear yet), BUT the
mechanism WORKS — on dc22 it flagged 5 aliased bases live and split them by action-history with
NO state explosion (graph 431 states). So the novel primitive (no M1 winner has it) detects
partial observability and separates true-states surgically; it just doesn't single-handedly clear
the hardest game — it must COMPOSE with exploration/goal work. Valid tested library primitive;
keep default-OFF; compose, don't expect solo clears on the frontier games.

## Finding (2026-07-08): the frontier bottleneck is GOAL INFERENCE, not action mechanics
Deep transition analysis of re86: ACTION1-4 each recolor ~48 cells among {5,9,11} (a
TRANSFORM/arrangement mechanic — regions swap color, not object translation, hence
avatar_mobility=0), ACTION5 = small commit. Board ~95% color 5. re86 is a color-arrangement
puzzle: the actions are LEARNABLE, but clearing needs the TARGET pattern to search toward.
This is the recurring wall across the hard games (also R53 ft09: world-model fit=1.0 but the
inferred goal was wrong → 0 clears). => The highest-value NEXT tool is GOAL INFERENCE — use the
offline LLM to infer the level-completion target (fill-to-color / match-pattern / sort-order /
symmetry) from observations, then feed goal_directed_plan (planner/goal.py) + the world model.
Heuristics can't infer arbitrary goals; the LLM's unique value here is reasoning "what is this
level asking for?". Build: LLM goal-inference tool -> goal_directed_plan, measured on re86/ft09/
transform-class games. Do NOT keep adding action-mechanic tools without a goal signal.

## Decisive finding (2026-07-08): pre-built tool orchestration ≈ baseline; frontier needs LLM-WRITTEN code
Measured the full toolkit + LLM orchestration:
- Orchestration loop (gemma4-31b picks config, runs, adapts) reaches ~the graph baseline: on
  ar25/sb26/sp80/tu93/lf52 it clears (self-improvement recovery proven on sp80: WM fail -> graph
  clear), but the FRONTIER transform games (re86/dc22/sc25) are 0 under EVERY tool: graph,
  graph_dealias, graph_deadsig, paint_flood, world_model, AND graph_llmgoal (LLM-inferred goal).
- So GOAL inference is necessary but NOT sufficient: even with the right goal, graph BFS can't
  converge on the huge color-arrangement transform space within budget.
- CONCLUSION: orchestrating PRE-BUILT generic tools plateaus at ~baseline (18/25). Beating it on
  the frontier games requires the LLM to WRITE bespoke solving code per game (Tufa's insight:
  "the model's creativity", the M1-winning REPL code-agent at 1.21%) — not select among fixed
  tools. Next lever = full LLM code-agent (extend llm_policy into a Tufa-style REPL where the
  model writes+executes game-specific Python), NOT more fixed tools.
Do NOT keep adding fixed tools for the frontier transform games; they need LLM-authored code.

## Rule-recovery tools (round R101, 2026-08-27)

Each recovers ONE mechanic from the frame and then acts, instead of searching. Together they
took the generic path from 0.0200 to 0.2143 over the 25 sample games. Pick by the observable
signature. Naming the wrong one costs a turn, not a game: every one of them declines a board
it cannot plan.

### assemble

**Observable Signature.** Assemble tool — loose pieces carrying seam marks, moved and re-formed until the seams meet.

The mechanic, recovered from frames: the board holds a handful of rigid pieces. One is SELECTED at a time; a click on a piece selects it, the four simple actions slide the selected piece one cell, and the fifth RE-FORMS it. Every piece carries a few MARKER cells — lone cells of a colour the

**Falsification Signature.** It proposes nothing here — `detect` returns 0.0 unless its
own mechanic is present AND it has a plan for this board.

**Tunable Parameters.** None at runtime; every constant it uses is derived from the frame.

**Next-Best.** `graph`, the general searcher, when no rule-recovery tool claims the board.

### cover_targets

**Observable Signature.** Slide skeleton pieces until their arms cover a board's pinned target marks.

The family this reads: the board carries a handful of small MARKS, each a 3x3 ring of one flat colour with a differently-coloured pip at its middle, and PIECES — thin skeletal shapes (a cross, an X, a bar, a rectangle outline) drawn in the pip colours. The level is won when

**Falsification Signature.** It proposes nothing here — `detect` returns 0.0 unless its
own mechanic is present AND it has a plan for this board.

**Tunable Parameters.** None at runtime; every constant it uses is derived from the frame.

**Next-Best.** `graph`, the general searcher, when no rule-recovery tool claims the board.

### haul

**Observable Signature.** Haul tool — take hold of a cargo piece, drag it into its bay, and let go.

The mechanic, recovered from the frames: one carrier under the four move keys walks a lattice; a fifth key LATCHES whatever sits in the cell the carrier faces and LETS GO of it again. A latched piece keeps its offset from the carrier, so it is towed rather than pushed, and it may be towed in

**Falsification Signature.** It proposes nothing here — `detect` returns 0.0 unless its
own mechanic is present AND it has a plan for this board.

**Tunable Parameters.** None at runtime; every constant it uses is derived from the frame.

**Next-Best.** `graph`, the general searcher, when no rule-recovery tool claims the board.

### keymaze

**Observable Signature.** Keyed-lock maze: walk an avatar to a lock whose KEY the avatar must first mint.

The family this tool recovers, stated only in what a frame shows: * the board is a lattice of equal square cells; most are one flat colour (floor or wall), and the avatar occupies exactly one and translates one whole cell per action;

**Falsification Signature.** It proposes nothing here — `detect` returns 0.0 unless its
own mechanic is present AND it has a plan for this board.

**Tunable Parameters.** None at runtime; every constant it uses is derived from the frame.

**Next-Best.** `graph`, the general searcher, when no rule-recovery tool claims the board.

### ledge

**Observable Signature.** Ledge tool — a side-view faller: two lateral controls, gravity, and a click that edits terrain.

Recovered from frames alone. The mechanic, in the order the tool has to derive it: * the board is a lattice of equal square cells, one sprite drawn per cell; * control is LATERAL ONLY — exactly two of the four movement actions exist, and that is what

**Falsification Signature.** It proposes nothing here — `detect` returns 0.0 unless its
own mechanic is present AND it has a plan for this board.

**Tunable Parameters.** None at runtime; every constant it uses is derived from the frame.

**Next-Best.** `graph`, the general searcher, when no rule-recovery tool claims the board.

### linkage

**Observable Signature.** Reach a ring marker with a dot marker by driving framed two-way controls.

The mechanic this recovers, stated in frame terms only. A board carries two kinds of small marker in one rare colour: a LONE CELL (the thing that moves) and a DIAMOND of four cells around an empty centre (the place it must reach). Elsewhere sit framed widgets — a rectangle

**Falsification Signature.** It proposes nothing here — `detect` returns 0.0 unless its
own mechanic is present AND it has a plan for this board.

**Tunable Parameters.** None at runtime; every constant it uses is derived from the frame.

**Next-Best.** `graph`, the general searcher, when no rule-recovery tool claims the board.

### maze

**Observable Signature.** Maze tool — walk a body to a marked exit, and recruit a replay clone when a plate gates it.

of states on these boards and clears nothing, because the games END on their own timer. A walk planned on a map read from the frame costs the length of the path and nothing else. The board grammar this tool recovers, all of it from pixels:

**Falsification Signature.** It proposes nothing here — `detect` returns 0.0 unless its
own mechanic is present AND it has a plan for this board.

**Tunable Parameters.** None at runtime; every constant it uses is derived from the frame.

**Next-Best.** `graph`, the general searcher, when no rule-recovery tool claims the board.

### mirror

**Observable Signature.** Mirror tool — two coupled actors under shared controls, brought together.

The mechanic, recovered from frames: a small number of identical actors sit in mirrored halves of the board; the simple actions move ALL of them at once, one cell per press, with the horizontal sense MIRRORED between halves; the level clears when they meet.

**Falsification Signature.** It proposes nothing here — `detect` returns 0.0 unless its
own mechanic is present AND it has a plan for this board.

**Tunable Parameters.** None at runtime; every constant it uses is derived from the frame.

**Next-Best.** `graph`, the general searcher, when no rule-recovery tool claims the board.

### pattern_cast

**Observable Signature.** Reproduce a pattern the board is SHOWING you, then walk the avatar to its exit.

The mechanic, recovered frame-only: a compact panel carries a complete k x k lattice of equal square cells. Most sit at one neutral colour; a minority are painted in a second. That minority is not decoration — it is an INSTRUCTION. Clicking each painted cell arms

**Falsification Signature.** It proposes nothing here — `detect` returns 0.0 unless its
own mechanic is present AND it has a plan for this board.

**Tunable Parameters.** None at runtime; every constant it uses is derived from the frame.

**Next-Best.** `graph`, the general searcher, when no rule-recovery tool claims the board.

### phase_grid

**Observable Signature.** Phase tool — an avatar walked to its marker over terrain that PANEL BUTTONS re-phase.

The mechanic, recovered from frames. A board sits beside a side panel of buttons. One small square is the avatar (the simple actions move it one lattice step), another square of the same size is its destination, and the level clears when the avatar's cell IS the destination cell.

**Falsification Signature.** It proposes nothing here — `detect` returns 0.0 unless its
own mechanic is present AND it has a plan for this board.

**Tunable Parameters.** None at runtime; every constant it uses is derived from the frame.

**Next-Best.** `graph`, the general searcher, when no rule-recovery tool claims the board.

### reflect_cover

**Observable Signature.** Cover a stencil of goal cells with a shape and its MIRROR IMAGES.

The family this fires on draws a board on which a few movable shapes are reflected through one or two full-span mirror lines, and asks that every goal cell be covered by the shape or by one of its reflections. The board renders three things the tool needs and nothing else:

**Falsification Signature.** It proposes nothing here — `detect` returns 0.0 unless its
own mechanic is present AND it has a plan for this board.

**Tunable Parameters.** None at runtime; every constant it uses is derived from the frame.

**Next-Best.** `graph`, the general searcher, when no rule-recovery tool claims the board.

### rule_rewrite

**Observable Signature.** Read a rewrite grammar off the board and spell the translated string.

The mechanic, recovered from the frame alone (verified against the sample board this was built on, 2026-08-27): * Every piece on the board is a FRAMED TILE: a solid square of one colour with a

**Falsification Signature.** It proposes nothing here — `detect` returns 0.0 unless its
own mechanic is present AND it has a plan for this board.

**Tunable Parameters.** None at runtime; every constant it uses is derived from the frame.

**Next-Best.** `graph`, the general searcher, when no rule-recovery tool claims the board.

### slotlaunch

**Observable Signature.** Slot-launch tool — park every loose piece inside the outline cut for it.

The mechanic, recovered from the frames and confirmed against the engine's own dispatch: * The board carries **outlines** — closed rings of one colour whose hollow interior is exactly the shape of one piece, inset by a single cell. A level clears when EVERY outline holds its piece.

**Falsification Signature.** It proposes nothing here — `detect` returns 0.0 unless its
own mechanic is present AND it has a plan for this board.

**Tunable Parameters.** None at runtime; every constant it uses is derived from the frame.

**Next-Best.** `graph`, the general searcher, when no rule-recovery tool claims the board.

### socketmerge

**Observable Signature.** Vacuum-merge boards: pull like pieces together, then park them in the sockets.

RECOVERED MECHANIC (measured on a live sample board, 2026-08-27). A click inside the playfield opens a short vacuum: every piece whose bounding box lies within a fixed reach of the click is dragged so that its CENTRE lands exactly on the clicked cell. Pieces that

**Falsification Signature.** It proposes nothing here — `detect` returns 0.0 unless its
own mechanic is present AND it has a plan for this board.

**Tunable Parameters.** None at runtime; every constant it uses is derived from the frame.

**Next-Best.** `graph`, the general searcher, when no rule-recovery tool claims the board.

### stencil

**Observable Signature.** Stencil tool — paint a small instruction glyph onto a lattice of equal tiles.

Recovered from frames alone in round r101 and measured on ft09 (levels 1-4, 62 actions, zero game constants). The mechanic: * the board is a lattice of equal square tiles, all one colour to begin with;

**Falsification Signature.** It proposes nothing here — `detect` returns 0.0 unless its
own mechanic is present AND it has a plan for this board.

**Tunable Parameters.** None at runtime; every constant it uses is derived from the frame.

**Next-Best.** `graph`, the general searcher, when no rule-recovery tool claims the board.

### subroutine

**Observable Signature.** Subroutine tool — assemble a program out of loose tokens, then run it once.

The mechanic, recovered from frames on one sample game: the top strip is a row of hollow boxes whose OUTLINE colour spells a target sequence; the middle of the board holds one or more wide rectangles, each a numbered strip of equally-spaced square slots; the bottom holds a tray of loose

**Falsification Signature.** It proposes nothing here — `detect` returns 0.0 unless its
own mechanic is present AND it has a plan for this board.

**Tunable Parameters.** None at runtime; every constant it uses is derived from the frame.

**Next-Best.** `graph`, the general searcher, when no rule-recovery tool claims the board.

### track

**Observable Signature.** Track tool — bring the marked item to the marked slot on a rotating track.

The mechanic, recovered from frames: a closed loop of equal square tiles, each a flat colour; a STATIC marker drawn beside one slot; and controls that rotate the whole loop one slot per press. The level is won when the tile whose colour matches the marker sits in the marked slot.

**Falsification Signature.** It proposes nothing here — `detect` returns 0.0 unless its
own mechanic is present AND it has a plan for this board.

**Tunable Parameters.** None at runtime; every constant it uses is derived from the frame.

**Next-Best.** `graph`, the general searcher, when no rule-recovery tool claims the board.

### tube_order

**Observable Signature.** Extendable-tube tool: a nozzle on a rail that must swallow tiles in a demanded order.

The mechanic, recovered from one sample board and written here in the terms a frame can supply. A PANEL below the board shows a second tube already holding a run of coloured tiles; that run is the demand. On the board a NOZZLE sits one cell OUTSIDE the play

**Falsification Signature.** It proposes nothing here — `detect` returns 0.0 unless its
own mechanic is present AND it has a plan for this board.

**Tunable Parameters.** None at runtime; every constant it uses is derived from the frame.

**Next-Best.** `graph`, the general searcher, when no rule-recovery tool claims the board.
