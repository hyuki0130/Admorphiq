---
type: reasoning
round: R53
axis: harness-architecture
keywords: [unified-harness, self-improving-loop, generic-tools, tool-orchestration, code-agent, minimal-wiki-context, retry-loop]
verdict: built (bench pending)
commit: b533ca4
date: 2026-07-08
description: Re-implemented the 6 tools (graph/world_model/dealias/deadsig/paint/llm_goal) as clean generic frame-only primitives on a shared Tool contract, plus the UnifiedAgent self-improving retry loop — signature → minimal wiki slice → pick tool OR write code → feed transitions back → re-decide on stall; code-agent alone re86=0/8 proves the frontier needs the combined loop
---

# R53 — Unified self-improving harness + 6 generic tools re-implemented

> The runtime general agent as a retry loop: one offline model reads a minimal
> signature-targeted wiki slice, picks a Claude-built generic tool OR writes
> code, runs it, feeds the transition back to every tool, and re-decides on
> stall — until the level clears or the budget is spent.

## Why this round

Prior sessions orchestrated the EXISTING agents (`graph_frontier_agent.py`,
`world_model_agent.py`) as tools. User directive (2026-07-08): the tools must be
RE-IMPLEMENTED generically by Claude, not reuse the legacy implementations that
carry brittle/game-specific baggage. And the runtime must be a genuine retry
loop (tool use + direct coding + feedback), with context injected as an
LLM-wiki slice (not few-shot), trimmed to fit the weak model's window.

## What was built

Clean `src/admorphiq/tools/` package on a shared `base.Tool` contract
(`detect`/`reset`/`observe`/`propose`) + generic frame analysis
(`connected_components`, `base_hash`, `diff_*`). None import the legacy agents;
all six grep-clean of game ids / titles / internal tags.

| Tool | `name` | Signature trigger | Role |
|---|---|---|---|
| graph_search | `graph` | has_movement + high avatar_mobility | frontier-BFS navigation (the ~18/25 core, re-authored) |
| world_model | `world_model` | low nondeterminism, learnable | tabular online dynamics + progress planning |
| dealias | `dealias` | high nondeterminism | augments node hash for aliased hidden state |
| dead_signature | `deadsig` | always (efficiency) | deprioritize inert action classes |
| paint_flood | `paint` | high click_fraction | click-fills-region detection + fill clicks |
| llm_goal | `llm_goal` | low mobility + large recolor_scale | LLM infers the transform target |

Centerpiece — `src/admorphiq/harness/`:
- `base.py` — the Tool protocol + generic frame utils (one implementation).
- `context.py` — minimal signature-targeted wiki retrieval. Computes an
  observable `Signature` (avatar_mobility, click_fraction, nondeterminism,
  recolor_scale, has_movement) from the agent's own transitions, pulls only the
  relevant `tool_selector.md` blocks, hard-caps to `budget_chars` (the
  `HARNESS_CTX` lever the bench sweeps), strips frontmatter.
- `loop.py` — `UnifiedAgent`: signature → minimal context → LLM picks tool or
  code → run → feed transition to every tool's `observe` → re-decide on stall.
  Offline-safe: injected `llm(messages)` callable, degrades to the
  highest-`detect` tool when the model is unreachable.
- `registry.py` — the 6 default tools + an offline ollama callable.
- `--agent unified` registered in `scripts/score_efficiency.py`.

`tool_selector.md` headings rewritten to embed each canonical tool `name` so the
harness parser retrieves all six (was retrieving only 3 — graph/paint/code).

## Measured so far

- **code-agent alone (LLM writes Python), re86 = 0/8** at budget 100–250. The
  frontier transform games are NOT solved by code in isolation → they need the
  tool+code combined loop, which is exactly what R53 builds. (Earlier the
  code-agent bench was silently excluded by a `No module named admorphiq.tools`
  packaging miss — fixed by shipping the package to the VM.)
- Loop control flow verified offline: 655 tests pass (+50 — tool contracts,
  loop orchestration, minimal-context budget/retrieval), ruff clean.

## Measured: LLM-call latency is the runtime budget constraint

VM ollama logs during the `--agent unified` bench show gemma4-31b **re-processes
the full ~2.4K-token prompt on every call** — `forcing full prompt re-processing
due to lack of cache data (SWA)`: gemma's sliding-window attention defeats
prompt caching, so each decision-boundary LLM call is expensive (several
seconds). Across the 9h / 110-game Kaggle budget this makes the NUMBER of LLM
calls the binding cost, not the tool execution. Two direct consequences the
harness already anticipates: (a) keep `HARNESS_CTX` small — smaller context is
both faster and (for a weak model) more accurate (the `harness_ctx_sweep.py`
lever); (b) decide at BOUNDARIES only (queue-empty / stall), never per action —
which `loop.py` does. A per-action LLM call would be untenable here.

## Partial bench (2026-07-08, in progress)

- **re86 = 0/8** (frontier transform) under `--agent unified`, budget 400 — the
  game consumed only ~100 actions before the env stopped progressing. Consistent
  with expectation: re86 is a graph-blocked transform game; the code-agent alone
  also scored 0/8, and the EWM track already flagged this class. NOT evidence of
  a harness bug — no tool/code path fits a target that must be inferred and the
  loop correctly falls through them. (To verify the 100-action stop isn't a
  RESET-loop artefact, compare against the graph_frontier baseline on re86.)
- **ar25** running now — BUT a baseline check corrected the test design: the
  deployed graph_frontier baseline ALSO scores **ar25 = 0/8 at 8000 actions**
  (scripts/rounds/R53/SUMMARY.txt, online-RL track). ar25 is NOT a game the
  graph approach clears, so a harness 0 on it proves nothing about orchestration
  quality — both re86 and ar25 were baseline-zero games, a poorly chosen probe
  pair. The FAIR harness-quality test is on games the baseline DOES clear:
  **R11L (0.0476, best), VC33 (2 levels), CD82, M0R0, CN04, LF52, TN36, SP80,
  FT09, LP85** (all base>0). Next bench targets those — does gemma4-31b pick the
  tool that matches/beats the baseline on games that are actually winnable?

## Decisive bench findings (2026-07-08, base>0 games)

Three loop bugs found+fixed by measurement on games the graph_frontier baseline
DOES clear (so a harness 0 is a real shortfall, not game difficulty):

1. **restart_on_game_over missing** — UnifiedAgent/code_agent didn't set it, so
   the score harness broke at the FIRST avatar death (measured 50–151 actions/
   game, 0 levels). graph_frontier sets it and runs the full budget. Fixed →
   games now run to budget (cd82 100 → 2000 actions).
2. **LLM called every empty queue** — a tool proposing few steps triggered an
   LLM decision per action (untenable under gemma SWA). Split into _redecide
   (LLM, only first/stall) + _continue (same tool, no LLM). Measured: 1 LLM
   call/game when a tool progresses.
3. **"frame changed" ≠ progress** — for cd82 the LLM picked `paint`; paint
   clicks kept changing the frame so the loop NEVER stalled/re-decided and
   wandered 2000 actions on one wrong tool (score 0). Fixed: progress =
   reaching a NOVEL frame-hash; a stalled tool is RETIRED for the level and the
   next decision excludes it (swap-on-failure). Measured after fix: cd82 now
   cycles **all 7 tools** (graph/dealias/world_model/paint/llm_goal/deadsig/
   code), each stalling after 12 steps.

**The remaining gap is TOOL STRENGTH, not routing.** With routing fixed, the
loop correctly tries every tool on cd82, but NONE clears it — while the legacy
graph_frontier clears cd82 L1 at the SAME 2000-action budget (measured 0.0012).
cd82's signature is `avatar_mobility=1.00; nondeterminism=0.77` — high
nondeterminism = frame-hash **aliasing** (a HUD/step element the legacy agent
strips via HUD-masking). The re-authored 293-line `graph` tool lacks that, so
its BFS sees a churning state space and can't navigate. **Next: strengthen the
generic tools to baseline parity — starting with HUD-masking in `graph` (the
highest-leverage, aliasing-driven miss), then `world_model`/`dealias`.** This is
the "Claude solves the games to build strong generic tools" phase; the harness
spine + routing are done and measured.

Note: graph_frontier_agent.py is itself GENERIC (grep-clean of game ids) — the
"don't reuse legacy" directive targeted the sprite-tag analytical solvers, not
the frontier engine; the re-authored tools must reach its generic techniques.

## Direct tool-strength probe (2026-07-08, `scripts/probe_tool_direct.py`)

To separate tool strength from harness routing, a new probe drives ONE tool on a
game with no LLM/routing/swap. The re-authored `graph` tool alone, budget 3000:

| game | my `graph` (alone) | legacy graph_frontier baseline |
|---|---|---|
| **vc33** | **1 level ✓** | 2 |
| m0r0 | 0 | 1 |
| cd82 | 0 (hidden-state aliasing, nondet 0.77) | 1 |
| ar25 | 0 | 0 (baseline also 0) |

**First genuine clear by a from-scratch generic tool: vc33 L1.** The harness
spine + one working tool are validated end-to-end. But the 293-line re-authored
`graph` is ~half the strength of the proven 2900-line `GraphFrontierAgent`
(clears vc33 1 vs 2, misses m0r0/cd82 the legacy engine clears). cd82's 0.77
nondeterminism is hidden-state aliasing (dealias territory, not visible HUD), so
HUD masking alone didn't help it — confirmed by the direct probe (0/3000).

**Decision (user, 2026-07-09): option (a) — keep strengthening the from-scratch
tools.** Do NOT wrap the legacy engine; honor "re-implement generically".

### Strengthening pass 1 — HUD masking + de-aliasing composition
The `graph` tool now composes both generic aliasing fixes: HUD masking (freeze a
mask of cells that churn in ≥60% of transitions, hash without them) THEN an
internal `DealiasTool` on the masked frame (split hidden-state collisions by
recent action history). Node identity = `_node_key = dealias.key(masked_frame,
recent)`; clean games get byte-identical keys.

Direct-probe after the composition (budget 3000):

| game | graph before | graph after | legacy baseline |
|---|---|---|---|
| vc33 | 1 | 1 | 2 |
| **m0r0** | 0 | **1 ✓** | 1 (parity reached) |
| cd82 | 0 | 0 | 1 (nondet 0.77 still unsolved) |
| ar25 | 0 | 0 | 0 |

**m0r0 0→1: de-aliasing closed the gap to legacy parity.** cd82 stays 0 — its
0.77 nondeterminism isn't separated by a 4-action-history suffix (it was
historically a paint-hybrid; may need the `paint` tool or deeper tiering, not
just graph).

### Full base>0 direct-probe sweep (graph tool, budget 3000)

| game | my graph | legacy | note |
|---|---|---|---|
| vc33 | 1 | 2 | clears; legacy goes deeper |
| m0r0 | 1 | 1 | ✓ parity (de-aliasing) |
| lp85 | 1 | 1 | ✓ parity |
| cd82 | 0 | 1 | hidden-state aliasing 0.77 |
| cn04 | 0 | 1 | click-heavy |
| lf52 | 0 | 1 | click-heavy |
| tn36 | 0 | 1 | click/program-puzzle |
| sp80 | 0 | 1 | |
| ft09 | 0 | 1 | lights-out (click-toggle) |
| ar25 | 0 | 0 | legacy also 0 |

**Score so far: from-scratch `graph` clears 3/9 of the games legacy clears**
(vc33, m0r0, lp85), up from 1 before this round's HUD+de-alias work.

### Strengthening pass 2 — dense click grid: REVERTED (measured harmful)
Hypothesis: click-only games (lights-out) fail because toggle needs clicking
currently-BACKGROUND cells that have no foreground centroid, so a dense
whole-board click grid (gated to no-movement games) would help. **Measured: it
regressed vc33 1→0 and unlocked none of ft09/cn04/tn36 (all still 0).** vc33 is
click-only too, and the 40-candidate grid diluted its exploration below the
budget. Reverted (commit 089f3b3). Finding: lights-out/toggle games need click
SEQUENCES (combinations), not single-click frontier-BFS — a different mechanism
than the graph tool provides. They belong to a dedicated toggle/paint tool, not
graph. ⛔ Do not re-try dense-grid click bloat on the graph tool.

**Graph tool stable state: 3 clears (vc33, m0r0, lp85), all tested.** Remaining
strengthening is genuine multi-round research per game-class: cd82 (hidden-state
aliasing beyond 4-history), lights-out cluster (needs sequence search — the
`paint`/toggle tool's job, not graph), vc33 depth (1→2).

### Confident-primary ownership (the fix that mattered)
Coarse tenure alone still left m0r0 = 0 in the harness (graph got ONE ~750-action
tenure then stalled on the loop's RAW-hash novelty — which is BLIND to graph's
own masked/de-aliased progress — and was retired). The graph tool given the FULL
3000-action budget clears m0r0 alone. Fix: a tool whose own `detect()` ≥ 0.7 for
the game OWNS it — not retired on a stall, gets the full budget. detect() is a
reliable frame signal; trust it and let the right tool run uninterrupted.
Low-confidence picks still swap-on-failure. Also fixed the routing wiki (decision
table now outputs EXACT canonical tool names + a `code` last-resort row — gemma4
had been picking `code` 9× because the table used non-matching display names).

**RESULT: the full harness now clears m0r0 L1 (0 → 1)** — matching the direct
probe. gemma4 picked `graph`, which owned the game as confident primary and
cleared it. This validates the whole spine end-to-end: LLM routing → confident
primary → owns game → clears. (game_score ≈ 0 because it used ~3000 actions for a
level a human does in 30 — RHAE squares efficiency, so inefficient clears score
near 0; CLEARING is the architecture milestone, efficiency is a later pass.)

### Progress-signal = the active tool's own state_key (click-only games)
The 3-game e2e then revealed the NEXT gap: vc33/lp85 (click-only, so graph.detect
is LOW → not a confident primary) cycled tools, though graph clears them ALONE.
Root cause: the loop's novelty used the RAW frame hash — blind to graph's real
progress (its masked/de-aliased states) — so graph looked stalled on a click game
and was swapped. Fix: the loop measures novelty with the ACTIVE tool's own
`state_key` when it exposes one (graph = HUD-masked + de-aliased key), resetting
the seen-set on tool switch. A tool genuinely exploring by its OWN measure is no
longer falsely retired. Re-measuring vc33/lp85. (This unifies ownership: a tool
owns the game while IT is making progress, regardless of detect — the principled
version of confident-primary.)

### E2E finding — the harness broke the strong tool (coarse-tenure fix)
Full-harness e2e (LLM routing) on m0r0 scored **0/6 — while the graph tool ALONE
clears m0r0**. Diagnosis from the trace: (a) gemma4 picked `code` 9× and `graph`
only 2× (weak routing), and (b) the fine-grained stall-swap + observe-all
**broke the strong tool**: every tool observed every transition, so graph's edge
graph got polluted by other tools' click actions, and graph was retired on a
30-step stall while legitimately BFS-walking to a distant frontier. A tool that
must control the whole action sequence (graph BFS) cannot survive fine-grained
interleaving. Fix (coarse tenure): (1) observe() feeds ONLY the active tool —
each tool's model reflects only its own actions; (2) a tool is reset on switch —
clean start; (3) no-new-state stall raised to 80 — a sustained run. Re-measuring
m0r0 in the full harness to confirm it now matches the direct probe.

## Pending

`HARNESS_CTX` context-size sweep (`scripts/harness_ctx_sweep.py`) once tool
strength clears a couple of base>0 games, so the sweep optimises a real signal.
Full-loop LLM nav bench (m0r0,vc33 @ stall=30) in progress.

### Click-game routing + the remaining efficiency gap (session close)
Made `graph` a click-game candidate (detect 0.4 when ACTION6 offered + a wiki
decision-table row), so gemma4 now DOES pick `graph` on vc33/lp85 (was 0 picks).
BUT the full-harness clear of vc33/lp85 is NOT yet confirmed: graph (detect 0.4 <
the 0.7 primary threshold) is subject to stall-swap, so it gets a tenure then is
swapped — it does NOT get the uninterrupted full-budget run that clears vc33/lp85
in the direct probe. And each tool switch costs a gemma4 call (SWA ~10s), so a
click game where graph is the 4th-5th pick takes 20+ min for ONE game — the
serial-tool-exploration latency is itself a problem for the 9h/110-game budget.

**Two standing next-axis conclusions (measured, do not re-derive):**
1. **Efficiency is the real score lever, not coverage.** Even a CONFIRMED clear
   (m0r0) scores game_score ≈ 0 because it used ~3000 actions vs a human's ~30 —
   RHAE squares efficiency. The graph tool's exhaustive BFS clears but is
   RHAE-worthless. The next axis is SHORT-path solving (goal-directed search),
   not more coverage.
2. **Harness tool-selection latency matters.** Serial LLM-per-switch exploration
   is too slow when the right tool isn't the first pick. Either route the first
   pick better (so graph is picked first on the games it clears) or parallelize
   tool trials.

**Session milestone (validated):** the from-scratch generic tools + self-improving
harness clear a game END-TO-END (m0r0 0→1) — the architecture works. 10 measured
fixes, 661 tests green.

### Full 25-game coverage sweep (`scripts/tool_coverage.sh`, direct probe)
Measured the `graph` tool's coverage across ALL 25 games (budget 3000, direct
probe — no LLM). **graph clears 4/25: lp85, m0r0, r11l, vc33.** (Legacy
graph_frontier ≈ 11-13/25, so a real strength gap remains.) ⚠️ arcengine
deadlocks under PARALLEL probes (Arcade scorecard contention — load 0.00,
cputime 0) — the coverage sweep MUST run sequentially (PAR=1); probe_tool_direct
also fixed to construct only the requested tool (default_tools pulled in the
ollama-backed ones).

**Per-tool coverage (direct probe, budget 3000, all 25 games):**
- `graph` = **4/25** (lp85, m0r0, r11l, vc33)
- `world_model` = **0/25** — the tabular passive-dynamics learner is INERT as a
  standalone solver (no strong planner); it adds nothing to the union. ⛔ Do not
  route to world_model as a primary until it has real goal-directed planning.
- `toggle` (NEW GF(2) lights-out solver) — measuring the click/toggle subset.

**New tool built (2026-07-09): `toggle`** (`src/admorphiq/tools/toggle.py`) — a
generic GF(2) lights-out solver (learn click stencils → solve A·x=b for a uniform
board). Correct + tested, BUT measured **0/12 on the click subset** even with a
centroid-aligned probe.

### ⛔ PIVOTAL LESSON — inspect the mechanic BEFORE building the tool
`scripts/inspect_game.py` (new) dumps what actions actually DO. Running it on the
games the toggle tool assumed were lights-out:
- **ft09**: **7 colours**, click-only; most clicks inert, but clicks in the
  bottom-right region flip ~38 cells and introduce a NEW colour → a
  **palette-select / region-recolor** game, NOT a 2-colour lights-out.
- **cn04**: 5 colours, movement+click; ACTION1-5 each transform LARGE regions
  (145-198 cells) — a **whole-region transform**, not avatar navigation.
- **lf52**: 6 colours; movement nudges a 1-cell cursor at row 0, clicks paint
  21-29-cell regions → a **cursor-move + click-to-paint** game.

None are lights-out. The `toggle` tool was built on an ASSUMPTION and cleared 0.
Kept (clean + generic, valid for real lights-out in the private 110) but it does
not match these 25.

**Strategic conclusion (measured, load-bearing):** the mechanical generic tools
(graph/toggle/paint) cover only the *searchable* games (graph 4/25). The MAJORITY
of the remaining games are **transform / recolor / palette-select** games whose
level-clear needs the TARGET configuration INFERRED — this is the **goal-inference
frontier bottleneck** the project has hit repeatedly (r51, r52). Those games are
the domain of `llm_goal` (LLM infers the target) + `code` (LLM writes the
transform), NOT more mechanical solvers. Future coverage work MUST run
`inspect_game.py` first and route transform games to goal-inference, not guess a
mechanical tool. Do not build another mechanical tool on an unverified mechanic.

## Related

- [[r52_ewm-integration]] — the EWM runtime hook this generalizes into a tool.
- [[r36_graph-frontier-bfs]] — the graph core re-authored here as `graph`.
- [[index]]

### Budget is NOT the graph gap — it's a real strength gap (2026-07-09)
graph @8000 (legacy's budget) on the 5 navigation games (dc22/g50t/lf52/sb26/tu93)
= **0/5**. Legacy graph_frontier clears several of these (lf52/cd82/cn04/tn36/sp80
in the online-RL base 11/25) at the same budget. So the re-authored 293-line
`graph` is fundamentally weaker than the 2900-line legacy engine — more budget
does not close it. The gap is in the EXPLORATION TECHNIQUE (frontier tiering /
prioritization / click handling), not budget or the aliasing fixes already
ported. Next: identify the specific legacy technique that clears lf52 and port it.
The 25-game taxonomy (`.wiki/raw/game_taxonomy_20260709.txt`): 5 navigation, 5
select/toggle, 8 transform(move-recolors), 3 transform/paint, 3 mixed, 1 inert —
graph's 4 clears span 4 classes, so class doesn't predict solvability; the 11
transform games remain the goal-inference frontier.

### CRYSTALLIZED: goal-inference is THE 25/25 bottleneck (2026-07-09)
promise-frontier scoring kept all 4 graph clears (vc33/m0r0/lp85/r11l = 1) but
added ZERO nav games (dc22/g50t/lf52/sb26/tu93 still 0/5 at 5000). Combined with
budget=8000 also 0/5: **blind graph search PLATEAUS at 4/25 regardless of budget
or frontier strategy.** The games it fails (incl. "navigation"-classified ones
like lf52 = cursor+paint) need the agent to know the TARGET configuration —
graph explores blindly and never discovers a goal it can't recognize. This is
the goal-inference frontier the project has circled since r51/r52.
- **The lever for 25/25 is GOAL INFERENCE, not more search.** The `llm_goal` tool
  + `planner.goal_inference` already define a generic goal vocabulary (FILL_COLOR,
  ORDER, ON_TARGET, MIN/MAX_OBJECT_COUNT). The work: make the LLM infer the right
  GoalSpec per game AND make the planner drive to it (current `_pick_click_target`
  is heuristic). This needs gemma4-31b + VM measurement per game (slow).
- promise-frontier kept (harmless, may help other budgets / the private set).
- ⛔ Do NOT keep tuning blind graph search for coverage — it is a ~4-13 ceiling.

### Complete coverage matrix + TWO-GAP analysis (2026-07-09)
All tools measured on the 25 (direct probe): graph **4**, world_model 0, toggle 0
(no lights-out), llm_goal 0 (transform games), code 0 (re86). Current-tools
ceiling = 4/25. BUT legacy graph_frontier clears ~11-13 (cd82/lf52/cn04/tn36/sp80
+ the 4). So the gap decomposes:
- **Gap 1 (my graph 4 → legacy ~13): SEARCH TECHNIQUE, portable & bounded.**
  Legacy has click-candidate TIERS (interactivity-ranked clicks) + GF_GOAL_RANK
  (heuristic goal-proximity frontier ranking) that my re-authored graph lacks.
  Porting these should recover ~7-9 games. THIS IS THE NEXT CONCRETE LEVER.
- **Gap 2 (legacy ~13 → 25): true GOAL INFERENCE, the open frontier.** The ~12
  games legacy also fails need the target inferred (LLM goal / code) — r51/r52
  circled this; all current mechanisms (llm_goal coarse GoalSpec, code-agent)
  measure 0 on it.
Plan: close Gap 1 by porting click-tiers + goal-ranking to `graph` (bounded),
then attack Gap 2 (goal inference) as the research frontier.

### Gap-1 progress: click-tiering added tn36 (graph 4 → 5/25) (2026-07-09)
Ported legacy's interactivity-tiered click candidates (area/rarity/contrast) →
**tn36 0→1** (a select/toggle sparse-click game), vc33/m0r0 kept (no regression).
graph now clears 5/25 (vc33, m0r0, lp85, r11l, tn36). cd82/lf52/cn04/sp80 still 0
— next port: legacy's GF_GOAL_RANK (heuristic goal-proximity frontier ranking via
planner.goal.score_goal). Confirms the two-gap plan: porting legacy search
techniques IS recovering games (unlike promise-frontier alone, which was inert).

### Gap-1 progress cont'd: goal-ranking added lf52 (graph 5 → 6/25) (2026-07-09)
Ported legacy GF_GOAL_RANK (heuristic no-LLM FILL goal + score_goal frontier
blend) → **lf52 0→1**, all 5 prior clears kept (no regression). graph now clears
**6/25** (vc33, m0r0, lp85, r11l, tn36, lf52). Two legacy search-technique ports
(click-tiering→tn36, goal-ranking→lf52) each recovered one game — the Gap-1 plan
is validated. cd82/cn04/sp80/ls20 still 0 (transform move-recolors — the FILL
goal doesn't capture their target). Running full 25-game re-sweep to confirm.

### Full re-sweep: graph = 5/25 @4000 (6/25 @5000, lf52 marginal) (2026-07-09)
Definitive 25-game sweep at budget 4000: **graph clears 5** (lp85, m0r0, r11l,
tn36, vc33). lf52 clears at 5000 but NOT 4000 — a budget-marginal clear. So the
ported search techniques took graph 4→5 solidly (tn36 via click-tiering) + lf52
marginally (goal-ranking, needs ~5000). Both ports validated but with diminishing
returns (~1 game each, slow measurement). The remaining ~7 games legacy clears
(cd82/cn04/sp80/ls20/…) resisted both ports — they are transform(move-recolors)
games whose target the heuristic FILL goal can't capture. **Decision: incremental
graph-technique ports are diminishing (2 done = +1-2 games); the bulk of remaining
coverage (the ~12 transform games incl. the ones legacy also fails) is GAP 2 =
goal inference. That is the real lever and the next focus.**

### Gap-2 attempt 1: code-agent goal-reasoning prompt — cd82 still 0 (2026-07-09)
Strengthened the code-agent prompt (state the TARGET must be inferred, step-by-step
object→goal→action reasoning, compact colour/object summary) and measured on cd82
(transform, legacy-clearable): **still 0** (100 actions). ALL current goal-inference
mechanisms now measured 0 on transform games: llm_goal (coarse GoalSpec) 0,
code-agent (bespoke Python) 0. Gap-2 is genuinely unsolved — the project's core
open problem. Also confirmed: the code-agent's LLM-every-turn design is very slow
(gemma SWA ~15s/call), a concern for the 9h/110-game budget.
- Untried Gap-2 idea for next session: HYBRID — llm_goal infers a RICH goal
  (ON_TARGET / MATCH_SUBREGION, not just FILL) and feeds it to `graph`'s new
  goal-ranking (score_goal) so LLM goal inference steers graph's search. Builds on
  the goal-ranking infra added this round.

### Gap-2 breakthrough: multi-goal tracker cracked cn04 (transform!) (2026-07-09)
Replaced the FILL-only heuristic goal with GoalMeasureTracker (scores the WHOLE
candidate-goal family — FILL/COUNT/ORDER/ON_TARGET — and adopts the goal whose
measure is most consistently increasing), throttled to every 6th state for speed.
**cn04 0→1** — a transform(move-recolors) game FILL-only could NOT crack — with
vc33/lf52 kept (no regression). graph now clears up to 7 (vc33, m0r0, lp85, r11l,
tn36, lf52, cn04). This is real Gap-2 progress: richer HEURISTIC goal inference
(no LLM) in graph unlocks some transform games. cd82 still 0 (its target may not
be in the candidate-goal family). Confirms the path: keep enriching the
frame-only goal family; the LLM is only needed for goals the family can't express.

### CONFIRMED full sweep: graph = 7/25 @5000 (2026-07-09)
Definitive 25-game sweep: **graph clears 7** (cn04, lf52, lp85, m0r0, r11l, tn36,
vc33) — up from 4 at session start (+75%). The three enrichments each held in the
full sweep: click-tiering→tn36, FILL goal-ranking→lf52, multi-goal tracker→cn04.
Validated path confirmed. Next enrichment target: cd82 (legacy clears, mine 0 —
its goal isn't in the candidate-goal family yet).

### COMPLETE union (2026-07-09): harness = 7/25, graph carries all of it
Measured every tool on all 25 (direct probe): graph **7**, world_model 0, toggle
0, paint **0**, llm_goal 0, code 0. **Union = 7/25 — graph is the sole working
tool.** The other 5 are currently dead weight (each 0). Honest state of the R53
harness: architecture validated (routing, self-improve loop, m0r0 e2e clear) and
the graph tool enriched 4→7 (+75%) via clean technique ports (click-tiering,
FILL+multi-goal ranking). Path to more coverage is PROVEN and incremental:
1. Keep enriching graph's frame-only goal family (each new goal type / search
   technique recovers ~1 game; cd82/sp80/ls20/dc22/g50t/… are the queue).
2. The hardest games (target not expressible frame-only) need LLM goal inference —
   currently 0 (llm_goal coarse GoalSpec, code-agent both fail); that is the deep
   open frontier (r51/r52). 25/25 is a multi-cycle research program on this path.

### Strategic close (2026-07-09): graph 7/25 ≈ legacy ceiling; rest is the frontier
Cross-referencing the online-RL base 11/25: the Gap-1 games legacy clears (CD82,
CN04, LF52, M0R0, R11L, SP80, TN36, VC33) are now MOSTLY recovered by the enriched
graph (cn04/lf52/m0r0/r11l/tn36/vc33 = 6 of them). Remaining Gap-1: cd82, sp80
(their targets aren't in the frame-only goal family — multi-goal still 0). So the
re-authored graph at **7/25 is at ~legacy's realistic ceiling**. The other ~14
games are ones legacy ALSO fails — the Gap-2 GOAL-INFERENCE frontier: their target
config must be inferred and no approach (legacy graph, EWM, llm_goal, code-agent)
has cracked them. **25/25 = solving that frontier, a genuine multi-session research
problem.** This round's deliverable: the from-scratch generic harness + graph tool
at legacy-parity coverage (7/25), the complete measured map, and the validated
incremental enrichment method — the foundation the frontier work builds on.

### Frame-only goal family EXHAUSTED at its ceiling — CLEAR_COLOR regressed (2026-07-09)
Added CLEAR_COLOR to candidate_goals (it was scoreable but not a candidate).
Measured on 11 failing games: unlocked NONE and **REGRESSED cn04 1→0** — the extra
candidate diluted the multi-goal tracker's best_trend selection so it adopted a
worse goal. Reverted. Finding: the multi-goal tracker's family is DELICATELY TUNED
at 5 types (FILL/MIN/MAX_COUNT/ON_TARGET/ORDER); adding types REGRESSES. So the
frame-only goal lever is at its safe ceiling — **graph 7/25 is the frame-only
maximum** (≈ legacy). ⛔ Do not add more candidate-goal types hoping for coverage
— measured harmful. The remaining ~18 games (incl. ones legacy also fails) require
LLM goal inference (target not expressible frame-only) — the unsolved frontier
where llm_goal + code-agent both measure 0. 25/25 = a research breakthrough there.

### Gap-2 hybrid (LLM goal → graph) built but TIMED OUT — inconclusive (2026-07-09)
Built the hybrid infra: `graph.set_external_goal()` (inject an LLM-inferred goal,
used exclusively so no tracker dilution) + `probe_tool_direct --hybrid` (warmup →
LLM infer GoalSpec → inject). Measured on 8 transform games: **ALL TIMEOUT** at
250s — including vc33 which graph clears fast normally. So the hybrid PATH is the
problem (the ollama goal call blocks, and/or injected-goal + per-state score_goal
is too slow), not the concept. Inconclusive — needs perf debugging (async/timeout
the LLM call; cache score_goal; cap frame storage) before it can be evaluated.
The hybrid remains the most promising untried Gap-2 lever and its infra is ready.

### DEFINITIVE: LLM goal inference ≤ frame-only heuristic — the GoalSpec vocab is the wall (2026-07-09)
Fixed the hybrid shipping bug (set_external_goal wasn't on the VM — the first
"all TIMEOUT" was a crash) and re-measured: hybrid (LLM-inferred GoalSpec injected,
tracker disabled) = vc33 kept but ALL transform games 0, and it **LOST cn04 1→0**
(the LLM's coarse GoalSpec was WORSE than the frame-only trend tracker's pick). So
every goal-inference mechanism measured this session — llm_goal 0, code-agent 0,
hybrid ≤ frame-only — is NO BETTER than the frame-only heuristic. ⛔ Do not deploy
the hybrid as default (it regresses cn04); graph's frame-only multi-goal tracker
(7/25) is the best config.
**Root cause of the 25/25 wall: the GoalSpec vocabulary (FILL/CLEAR/COUNT/ORDER/
ON_TARGET/MOVE/MATCH) cannot express the transform games' true targets, so neither
heuristic trend-tracking NOR LLM inference within it can steer to them.** The
frontier for 25/25 is a RICHER goal representation — an arbitrary target frame /
executable rule (the EWM r48-r52 direction, Tufa's code-writing) — plus a planner
that reaches it. That is the genuine open research problem; 7/25 is the ceiling of
everything expressible in the current goal vocabulary.

### Parameter sweep confirms the ceiling: goal-weight 0.30 INERT (2026-07-09)
Swept _GOAL_WEIGHT 0.05→0.30 (stronger goal-proximity steering): cn04/vc33/lf52
kept, transform games (cd82/sp80/ls20/ar25) still 0 — INERT, reverted to 0.05.
Combined with budget-8000 inert and every other lever, this CLOSES the sweep:
**7/25 is the airtight measured ceiling for all frame-only + coarse-GoalSpec
approaches** (search enrichment, goal-family, goal-weight, LLM inference — every
one measured). 25/25 = the EWM / richer-goal-representation research frontier
(r48-r52 track), which is where the graph 7/25 base + hybrid infra hand off.

### 🎯 BREAKTHROUGH: target-grid (LLM draws solved board) CRACKS cd82 (2026-07-09)
The richer-goal representation BREAKS the GoalSpec-vocabulary wall. `--targetgrid`:
after warmup the LLM is shown the current 8x8 downsample and asked to DRAW the
SOLVED board as an 8x8 grid; it's injected via graph.set_target_frame and graph
ranks frontiers by downsampled-frame distance to it. Result: **cd82 0→1** — the
transform game that resisted EVERY prior approach (frame-only multi-goal, hybrid
GoalSpec, budget 8000, goal-weight sweep all 0). cn04/vc33 kept. sp80/ls20/ar25/
sc25 still 0 (gemma's target for those was likely wrong, or graph couldn't reach
it). **The 7/25 "ceiling" was the COARSE-goal ceiling; richer goal representation
(an arbitrary LLM-drawn target FRAME, not a GoalSpec enum) is the lever that
breaks it — cd82 is the proof.** graph + targetgrid clears 8 (the 7 + cd82). Next:
strengthen the target extraction (better prompt / per-level re-draw / stronger
model) to unlock more transform games. THIS is the validated 25/25 frontier path.

### Target-grid full sweep: +1 (cd82 only) — breakthrough real but NARROW (2026-07-09)
Ran --targetgrid across all 18 graph-failing games: **only cd82 clears** (the
others — sp80/ls20/ar25/re86/sk48/sc25/s5i5/su15/tr87/wa30/ka59/bp35/dc22/g50t/
sb26/tu93/ft09 — all 0). So the richer-goal lever WORKS (cd82 proves the vocab
wall is breakable) but its current form (gemma draws an 8x8 target) cracks only 1
more game. **graph frame-only = 7/25; graph + targetgrid fallback = 8/25.** The
new bottleneck is TARGET-EXTRACTION QUALITY: for most games gemma's 8x8 solved-
board drawing is wrong, or graph can't reach the drawn target. Targetgrid should
be a FALLBACK (LLM cost) invoked when frame-only stalls, not the default. Next
frontier work = better target extraction: higher-res target, per-level re-draw,
show the LLM more context (observed transitions, not just the 8x8), a stronger
model, or validate/repair the drawn target. cd82 is the proof-of-concept that
this is THE path past the coarse-goal 7/25 ceiling.

### Target extraction is DELICATE — richer prompt regressed cd82, reverted (2026-07-09)
Enriched the targetgrid prompt (observed transitions + histogram + reason-then-grid,
parse last-64): cd82 went 1→0 and nothing new cleared — the richer prompt / last-64
parsing made gemma draw a WORSE target. Reverted to the simple prompt (8x8 current
→ solved, parse first-64) which gives cd82=1. **HONEST FINAL: graph = 8/25**
(frame-only 7 + simple-targetgrid cd82). The richer-goal frontier lever is REAL
(cd82 breaks the coarse-goal wall) but broadening it is DELICATE — target-drawing
quality is the sensitive bottleneck, and small prompt changes swing it. Getting
gemma to reliably draw correct targets for more games needs sustained careful work
(stronger model, target validation/repair, higher-res, per-level re-draw) — the
research direction past 8/25. Infra ready (set_target_frame + probe --targetgrid).

### Validation + per-level redraw: cd82 kept, no new unlocks (2026-07-09)
Added target validation (reject degenerate / identical / hallucinated-palette
draws, 1 retry — invalid means NO injection, falling back to the proven frame-only
base) + per-level target redraw. Measured: **cd82=1 kept (no regression), sp80/
ls20/ar25/sc25/re86 all still 0.** Validation is a KEEP (pure downside protection
for the private set) but broadening needs a stronger TARGET SOURCE, not plumbing.
Next measured experiment: swap the target-drawing model (TARGETGRID_MODEL env;
gpt-oss:120b available on the VM — target-DRAWING is a spatial-imagination task,
distinct from EWM rule induction where gemma won, so it must be measured fresh).

### Target-drawer model swap: gpt-oss:120b — no gain so far (2026-07-09)
TARGETGRID_MODEL=gpt-oss:120b on the failing set: sp80/ls20/sc25 = 0 (same as
gemma, model warm for those). cd82 showed 0 but is AMBIGUOUS — it was the first
game and the 65GB model load likely timed out its LLM calls (no injection →
frame-only → 0, consistent). Warm-model cd82 re-run in flight to resolve. So far
the stronger-param model does NOT draw better targets than gemma4-31b — the
target-drawing bottleneck is not raw model size on this pair.

### Model verdict: gemma4-31b wins target-drawing too (2026-07-09)
Warm-model cd82 with gpt-oss:120b: **both draw attempts failed format** (<64
integers in the reply — the reasoning model burns tokens on prose and doesn't
emit the plain 8x8 grid) → no injection → 0. Combined with sp80/ls20/sc25 = 0
warm: **gpt-oss:120b ≤ gemma4-31b for target-drawing** (mirrors the R50b EWM
verdict). gemma4-31b-q8 is the confirmed drawer; model size is not the lever.

### Targetgrid parameter space CLOSED: res=16 regressed cd82 (2026-07-09)
TARGETGRID_RES=16 (gemma): all 6 games 0 INCLUDING cd82 (1 at res=8) — higher
resolution makes gemma's drawing worse, not better. The targetgrid lever is now
FULLY swept: prompt enrichment (regressed), validation+retry (safe, no gain),
per-level redraw (no gain), model swap gpt-oss:120b (format-fails, gemma wins),
resolution 16 (regressed). **Optimal measured config: gemma4-31b, simple prompt,
8x8, first-64 parse, validation guard = graph 8/25.** Every cheap variation is
measured; further gains need a genuinely different goal source (EWM executable
rules — a dedicated research cycle). Next: PRODUCTIZE the breakthrough into the
deployed UnifiedAgent (it currently lives only in the probe) so the harness
itself clears 8/25.

### CORRECTION: the cd82 targetgrid clear is STOCHASTIC (~2/4 runs) (2026-07-09)
Reproducibility check (3rd probe run): cd82 = **0**. Across 4 total runs (probe
1, 1, 0; harness-with-verified-injection 0) the clear rate is ~50% — ollama fp
nondeterminism at temp=0 varies the drawn target run-to-run, and the clear
depends on drawing a good-enough target. The earlier "breakthrough" declaration
violated the 3-seed rule; corrected: **the richer-goal lever is REAL (0% under
every coarse-goal approach vs ~50% with targetgrid) but single-draw quality is
the noisy bottleneck.** The harness "integration gap" was a mirage — same
variance. Stabilization lever (next): multiple draws per level (redraw every ~400
steps, up to 3) — at ~50%/draw that's ~87%/level, 2 extra gemma calls max.

### Blind periodic redraw REGRESSED (last-draw-wins); fixed with feedback gating (2026-07-09)
Multi-draw v1 (redraw every 400 steps unconditionally): harness cd82 **0/4** vs
single-draw probe 2/3 — each redraw OVERWROTE the pursued target ("last draw
wins"), killing pursuit time; a good draw needs long uninterrupted pursuit.
Fix: graph traces its own pursuit progress (best current-board→target proximity
per propose) and exposes `target_stalled(window)`; the harness redraws ONLY when
the current target stopped improving for 300 propose-calls. Upside-only: good
targets pursued to the end, dead ones replaced. This is the self-improving
feedback pattern applied to the goal itself. Measuring unified cd82 ×2.

### Harness-vs-probe cd82 differential: suspects excluded one by one (2026-07-09)
Harness cd82 with feedback-gated redraw: still 0/2 (cumulative harness 0/8 vs
probe 2/3). Excluded by trace: (a) tool propose() exceptions — none (the silent
handler is now traced); (b) draw-LLM params — aligned to the probe config
(dedicated draw_llm, num_ctx 8192 / predict 400), no change; (c) graph retirement
— exactly 1 decision/run, graph owned all 5000 actions; (d) injection — 3 valid
injections/run (targets kept stalling per the pursuit trace). Mechanical paths
now match the probe. Remaining hypothesis: the probe's 2/3 overstated the true
base rate (small-sample luck) and 0/8 is the same low-rate distribution — probe
×4 base-rate measurement in flight to decide.

### FINAL base rate: cd82-targetgrid ≈ 30% stochastic, not a solid clear (2026-07-09)
Probe ×4: 0/4. Cumulative probe record: 3 clears in the first 4 runs, 0 in the
last 5 (≈33% overall); harness 0/8 is the same low-rate distribution, not an
integration gap — every mechanical suspect was excluded by trace. CORRECTED
HONEST STATE: **graph = 7/25 solid; cd82 clears ~30% of runs via targetgrid**
(upside-only fallback, kept as deployed default: ≤3 LLM calls, never harms the
frame-only base). The targetgrid deep-dive is CLOSED — every cheap parameter was
measured (prompt, validation, redraw policy, model, resolution, LLM params);
draw quality at ~30% is the gemma-scale ceiling. Past it = richer target sources
(EWM executable rules / stronger drawer), a dedicated research cycle. ⛔ Do not
re-grind targetgrid parameters.

### Architect verification: REJECT → all defects fixed (2026-07-09)
Adversarial architect review (criteria: genericity/contract/offline-safety/state-
hygiene/correctness) PASSED 1-4 but found 6 ranked defects; verdict REJECT.
Fixed: (HIGH) confident-primary ownership was INERT — every runner passes
frames=[], blinding detect()'s transition-evidence branches so graph could never
reach 0.8; the loop now maintains _recent_frames and feeds them to every detect()
call, and ownership is re-evaluated LIVE at stall time (it was frozen at the
evidence-free step-0 value). (MED) context.py off-by-one dropped ACTION4 from
avatar_mobility (act<=4); (MED) click_fraction counted ACTION7 as a click (a==6).
(LOW) failed target draws no longer exhaust MAX_DRAWS (slots vs injections split,
5-slot cap). (LOW×2, accepted) HUD-freeze transient novelty optimism; LLM
callable must be time-bounded (documented contract). 667 tests green.

### Post-fix validation: deployed harness 6/7 solid games (2026-07-09)
With the architect fixes deployed (live evidence-fed ownership, no-churn stall
policy, signature fixes, world_model prior cap, aligned tool_selector): the
deployed UnifiedAgent clears **cn04, lp85, m0r0, r11l, tn36, vc33 (6/7)** — lp85
recovered (was lost to churn), only lf52 remains 0 (it is budget-MARGINAL even in
isolation: clears at exactly 5000, not 4000; harness overhead tips it under).
**Deployed ≈ isolated performance: productization complete.** Honest deployed
card: 6 solid + lf52 marginal + cd82 ~30% stochastic ≈ 7±1 of 25.

### Verification chain complete (2026-07-09): architect APPROVE + deslop + regression
Re-verification after fixes: **APPROVE** (one MEDIUM residual — llm_goal.detect
filtered raw ndarrays via has_frame() and always returned 0.0 with the harness's
_recent_frames — fixed with a raw-tolerant _grid_of reader mirroring graph's
_obs_grid). Deslop pass (behavior locked by tests): deleted the measured-dead
--hybrid probe path (coarse-GoalSpec injection, inferior to frame-only;
set_external_goal kept as the API for future richer goal sources) and stripped
the inert parallel scaffolding from tool_coverage.sh. Post-deslop regression:
**667 passed**. Deployed card being finalized: 6/7 solid + cd82 ~30% + lf52
under full-budget re-test (8000).

### ✅ FINAL DEPLOYED CARD (2026-07-09): 7/7 solid at deployment budget
lf52 clears at the real deployment budget (GF_GIVEUP=8000): **the deployed
UnifiedAgent clears ALL 7 solid isolated games** — cn04, lf52, lp85, m0r0, r11l,
tn36, vc33 — plus cd82 ~30% stochastic via targetgrid. Deployed = isolated tool
performance: the productization of the from-scratch generic-tool harness is
COMPLETE and architect-approved (667 tests). R53 deliverable finalized. The
mission continues past it on the goal-representation frontier (EWM executable
rules / richer target sources) — the measured path beyond ~7-8/25.

### Goal-representation ladder CLOSED: inference accuracy, not expressiveness, is the wall (2026-07-09)
Third rung measured: executable goal scorer (LLM writes goal_score(frame);
sandbox-compiled/validated, graph.set_external_scorer). After fixing the
numpy-import rejection (gemma reflexively imports numpy; stripped safely — first
sweep had 0 injections), 9 scorers injected cleanly across 8 games: **no new
unlocks, and cn04 REGRESSED 1→0** (gemma's scorer replaced and underperformed the
frame-only trend tracker — the exact pattern of the coarse-GoalSpec hybrid).
vc33 kept. ⛔ Do not deploy goalcode as a default (regresses cn04); infra kept
(set_external_scorer is sound for a future better goal source).
**COMPLETE LADDER VERDICT (all three rungs measured): enum GoalSpec = 0 & lost
cn04; static target frame = +cd82 ~30% only; executable scorer = 0 & lost cn04.
The binding constraint is the LOCAL MODEL'S GOAL-INFERENCE ACCURACY, not the
representation's expressiveness — richer forms just express wrong goals more
precisely. Path to 25/25 = better goal EVIDENCE/inference (e.g. cross-level
observation of what changed on a clear, stronger models, or learning the goal
from the game's own reward structure) — genuine research, not representation
plumbing.** ⛔ Do not add a fourth representation rung without a better
inference source.

### Efficiency baseline quantified (2026-07-09): the next mountain, in numbers
Actions-to-clear on the 7 deployed clears vs human baseline: tn36 266/32 (8×),
r11l 562/22 (26×), lp85 809/17 (48×), m0r0 2824/30 (94×), cn04 3361/29 (116×),
lf52 5108/32 (160×), vc33 1902/7 (272×). Summed RHAE contribution ≈ 0.0006 —
**exhaustive-exploration clears are worth ~nothing under the squared-efficiency
metric** (standing conclusion #1, now quantified). Efficiency is inseparable from
goal inference: to clear in ~human actions on the FIRST traversal the agent must
know where it is going. tn36/r11l (8-26×) show the graph CAN be near-efficient
when its goal-ranking matches the game. The R53 deliverable ends here: coverage
productized (7/7 deployed + cd82 ~30%), verification complete, both next-axis
walls (goal-inference accuracy, efficiency) measured and quantified for the next
research cycle.

### Goal-evidence cycle, measurement 1: cross-level clear evidence — L2 still locked (2026-07-09)
Built the cross-level clear-evidence lever (level-up captures the just-solved
board game-scoped; later levels' target draws cite its downsample as an analogy —
L1 draws unchanged). Deployed measurement on the three fastest L1-clearers at
8000 (tn36 8×, r11l 26×, vc33): **all still 1 level.** The mechanism works (L2
ran with multiple evidence-cited draws + stall-gated redraws; tn36's L1 took only
266 actions so ~7.7k budget remained for L2) — so the block is either (a) the
analogy-drawn target is still wrong for L2, or (b) L2's mechanics/search-space
defeat graph exploration regardless of goal. Next diagnostic: dump the L2 board
and the drawn target side-by-side on tn36 to see WHICH. Lever kept (upside-only,
no regression: all three L1s intact).

### 🎯 Dominant steering flips cd82 to 2/2 — the inert-steering diagnosis was right (2026-07-09)
With explicit-target proximity now DOMINATING the frontier ranking (weight 50 vs
the provably-inert 0.05): **cd82 cleared BOTH runs** (harness history was 0/8!)
and all four regression games held (tn36/r11l/vc33/m0r0). The grid-dump→inert-
steering→dominance chain is validated: gemma's drawn targets were often GOOD and
simply never pursued. MAJOR CAVEAT ON PRIOR VERDICTS: the "targetgrid cracked
only cd82" full-sweep AND the ~30%-stochastic base-rate were measured UNDER
INERT STEERING — targetgrid's true potential is unmeasured. Re-running the
failing set with dominant steering. tn36 L2 stayed locked (plausible target +
real steering — its block is deeper: combinatorial click space or full-res
target mismatch).

### Dominant-steering scope pinned: deployed-cd82 fix real, no new games (2026-07-09)
Full failing-set probe re-sweep under dominant steering: **all 18 games 0 —
including cd82 at probe@5000**. Reconciliation: the deployed harness cleared cd82
2/2 at 8000 with THREE stall-gated draw chances; the probe has one draw per level
at 5000. So the win condition is the COMBINATION: dominant steering × multi-draw
× full budget — steering makes a good draw count, multi-draw buys ~3 chances at
the ~30-50% draw quality. The "inert steering masked other games" hypothesis is
REFUTED: the other 17 games' draws are genuinely wrong/unreachable (the
inference-accuracy wall stands for them). Deployed card: 7 solid + cd82 (2/2 at
the deployed config; firming with 2 more samples).

### ✅ cd82 FIRMED 4/4 — deployed card promoted to 8/25 SOLID (2026-07-09)
Runs 3-4 also cleared: **cd82 = 4/4 at the deployed config** (dominant steering ×
3 stall-gated draws × 8000 budget). The diagnostic chain (grid-dump trace →
inert-steering discovery [proximity ±0.05 vs integer promise] → dominance fix
[weight 50]) converted cd82 from 0/8 to 4/4. **DEPLOYED CARD: 8/25 SOLID** —
cd82, cn04, lf52, lp85, m0r0, r11l, tn36, vc33. Session arc: 4 isolated (start)
→ 8 deployed solid. Remaining 17: the inference-accuracy wall (their targetgrid
draws are genuinely wrong — re-verified under real steering) + the L2+ depth
problem (tn36's plausible L2 target still unpursued to completion → combinatorial
click space or full-res mismatch; next research thread).

### Zero-gradient hypothesis REFUTED — 8x8 proximity is load-bearing (2026-07-09)
tn36 L2 diagnosis chain: pursuit trace showed best_prox frozen at the initial
diff (-0.141 = exactly the starting 9/64 blocks) for 1200+ calls → hypothesized
the 8x8 block-majority was a zero-gradient metric for fine-grained (~1 cell/
action) games → implemented full-res per-pixel proximity. MEASURED: cd82
**4/4 → 0** (regression), tn36 still 1 with best_prox -0.385 frozen (zero pixel
progress), r11l unchanged. Root cause of the regression: per-pixel diff vs the
kron-blocky target is dominated by block-interior TEXTURE NOISE (diff floor
-0.38/-0.78 vs -0.14 at 8x8), distorting the proven frontier ordering. REVERTED
byte-identical (commit 0d2afb2). Verdicts: (a) the 8x8 block-majority proximity
is load-bearing for cd82 — ⛔ do not replace it with full-res compare against an
upsampled target; (b) **tn36 L2's block is NOT metric granularity** — zero pixel
progress under a gradient-capable metric means the drawn target region is
UNREACHABLE in its combinatorial click space (programming-puzzle class). tn36 L2
leaves the targetgrid thread. (c) NEW LEAD: r11l L2's pursuit DID move
(best_prox -0.282 → -0.235 across draw windows) — gradient alive, undershot the
budget → budget-scaling probe is the right next experiment for r11l/vc33 depth.

### Budget-scaling depth probe: L2 wall = DRAW QUALITY, not budget (2026-07-09)
r11l/vc33 @16000 (2x deployed budget): both still 1. But the pursuit traces
split the L2 wall cleanly: **r11l L2 best_prox converged -0.235 → -0.172 →
-0.109** (gradient alive, steadily closing — the residual ~7 blocks are the
DRAW'S OWN ERROR, so no budget reaches a clear), while **vc33 L2 froze at
-0.469 across 3 windows** (tn36-class wrong/unreachable draw). Both point at
draw quality → implemented **redraw diversity** (r51 config-UNION applied to
draws): first draw = the measured simple prompt (cd82 path byte-stable), each
stall-gated redraw adds the agent's own observed action→effect medians
(`_action_evidence` in loop.py, `action_evidence` in targetgrid.py). A redraw
only fires when the prior draw's pursuit already stalled, so the extra config
is a free chance exactly where the simple config failed.

### Redraw diversity batch 1: prompt-structure sensitivity found (2026-07-09)
First diversity measurement (cd82/vc33/r11l @deployed): cd82 held (1), no L2
unlocks, and a clean failure mode — **every evidence-carrying redraw was
rejected "degenerate (single colour)"**. Inserting the evidence block between
the board and the OUTPUT instruction breaks gemma4-31b's grid output entirely
(the r51-era "richer prompt regressed cd82" finding is now explained: it is
PROMPT-TAIL DISRUPTION, not evidence content). Tune-before-discard: evidence
moved BEFORE the board so the validated board→instruction tail stays
contiguous; re-measuring vc33/r11l. ⛔ Never insert prose between the current
board grid and the OUTPUT instruction in targetgrid prompts.

### Redraw diversity DISCARDED after 2-config sweep (2026-07-09)
Config 2 (evidence before board) fixed the degenerate rate (~44% of enriched
redraws inject) but produced ZERO new levels and no L2 unlocks (vc33/r11l);
enriched draws are no better than simple ones and reject more often — a net
risk to cd82's proven multi-simple-draw win condition. Code reverted
byte-identical (simple draws restored); the ⛔ prompt-tail lesson above is the
durable takeaway. ⛔ Redraw-diversity-via-transition-evidence is measured
no-gain — the draw-quality wall is gemma's goal-inference accuracy, and citing
the agent's own action->effect medians does not move it. Next thread: the
legacy-vs-new graph strength gap on the remaining navigation games.

### Gap-1 @8000 pinned + R38 tier gate ported — ft09 closed (2026-07-09)
Legacy graph_frontier @8000 on the 10 FINAL2-only games: **ft09 1, sp80 1,
tu93 2; the other 7 (ar25 bp35 ka59 ls20 sb26 sk48 tr87) are 0** — their legacy
clears need 30k-100k budgets (RHAE-worthless; not port targets). Ported the R38
GLOBAL TIER GATE into tools/graph_search.py (legacy-faithful interactivity
tiers: score thresholds 2.0/1.0, backdrop bg-frac>0.6 demotion; frontier
promise + local pick count only in-gate untried; global unlock when no in-gate
untried is reachable). Unified bench interim: **ft09 0 → 1 (CLOSED by the
gate)**; sp80/tu93 unchanged 0 — their legacy technique is elsewhere (both
movement games; obj-hash ladder / band masking are the next candidates).
Solid-8 regression guard in flight.

### Tier-gate bench final: ft09 CLOSED, 7/8 solid held, cd82 in replication (2026-07-09 23:01)
Full tier-gate bench (11 games @deployed): **ft09 0→1 (the gate's win)**; solid
card held on vc33/r11l/tn36/lp85/m0r0/cn04/lf52; sp80/tu93 still 0 (expected —
their legacy technique is not click-gating; the R45 object-hash ladder is
implemented+committed locally, measuring next). **cd82 = 0 (was 4/4)** — the
gate changes exploration order, which can starve the draw-pursuit's graph
edges; 2-run replication in flight before any verdict. If cd82 reproduces 0,
candidate fix: exempt the target-pursuit path from the gate (steering ranks
IN-GATE frontiers only — a gated-out click that the drawn target needs would
never be walked to).

### ✅ 9/25 SOLID — gate exemption fixed cd82; object ladder inert (2026-07-09 23:14)
tg2: **cd82 2/2 recovered** (tier gate bypassed while an explicit target/scorer
is active — the gate had starved the drawn-target pursuit) and **ft09 held at
1** → deployed card promoted to **9/25 SOLID**: cd82 cn04 ft09 lf52 lp85 m0r0
r11l tn36 vc33. The R45 object-hash ladder closed none of its 3 candidates
(sp80/tu93/ar25 all 0, 1 sample) — next: fire-trace to distinguish "guards too
strict, never armed" from "armed but the object graph is equally stuck".

### Object-ladder attribution: tu93 fires-but-stuck, sp80 never fires (2026-07-09 23:25)
Fire-trace runs: **tu93 armed the ladder** (explosion: new_frac=0.50,
distinct=30) yet finished 0/9 — the object graph is equally stuck, so tu93's
legacy win is NOT the object rung. **sp80 never armed** (guards unmet at
STALL=80 ownership churn or its pixel states recur more than assumed). Legacy
source note: TU93 was the game that needed the pool=1 DOWNSHIFT (pooling
collapsed its real moves) — we already hash full-res, so tu93's legacy clear
rests on some OTHER technique (region/band masks, frontier dist 12 vs our 40,
visit/path penalties, recency bonus). Instead of guessing: GF_DEBUG legacy runs
on tu93/sp80 in flight to observe the active rungs at clear time.

### GF_DEBUG attribution: tu93/sp80 legacy clears rest on pool=2 hashing (2026-07-09 23:30)
Legacy debug runs: tu93 cleared L1/L2 at **effpool=2, mode=pixel, masked=126**
(pool=1 downshift only fired later on L3); sp80 cleared L1 at **effpool=2 with
a ~2800-cell region mask** (68% of the board — far above our per-cell mask's
size/3 cap, which silently disables masking on such games). Ported the missing
rung: hash ladder now escalates full-res -> 2x2 max-pool -> object (one rung
per broken-signature fire, re-locked per level; solid-9 default untouched).
Bench in flight (tu93/sp80 targets + vc33/m0r0 guard). If sp80 stays 0, the
next lever is the REGION-mask port (large-region rate masking above the
per-cell cap) — pre-registered.

### Pool-2 rung: no-gain at fire=1500; early-fire sweep + dealias diag (2026-07-09 23:29)
pool2 bench: tu93 0/9 (fired pool2 then object — **new_frac stayed 0.64 at
pool2**, so tu93's explosion is NOT sub-cell jitter; prime suspect = dealias
history-suffix forking, diagnostic added to the fire trace), sp80 0/6 (ladder
never fires — its lever is the region mask, pre-registered), vc33/m0r0 guards
held at 1 (fires occurred during L2 pursuit, harmless). Tune-before-discard:
_OBJ_MIN_STEPS 1500→500 (a fired rung rebuilds from scratch; at 1500 the level
budget was half-spent) — pool2b in flight (tu93 + guards).

### Band-mask port (the tu93 lever) — pool2b attribution chain (2026-07-09 23:38)
pool2b: early fire (500) changed nothing; **aliased=0 refuted the dealias
hypothesis**. The surviving explanation for "explodes at pool2 AND object mode":
a MOVING BAND — some component's centroid drifts every step (timer/scanline),
invisible to per-cell change-rate rules (each cell changes rarely) and to the
object hash (centroid = part of the token). This is exactly legacy's
monotone-moving-band detector, and legacy tu93's masked=126 was that band.
Ported verbatim (thin<=3 / drift>=6 / density>=0.5 / monotone>=0.7 / window
48/16 / dilate 1, frame-shape generic): confirmed track masked from node keys,
mask grows with the marker, graph rebuilt at confirmation. 679 tests. band1
bench in flight (tu93/sp80 + vc33/m0r0/lf52 guards).

### Band mask REVERTED (measured harmful); REGION mask ported instead (2026-07-09 23:44)
band1: tu93 never confirmed a band (hypothesis wrong — re-reading the legacy
debug, tu93 ran with **band=none**; its masked=126 was the REGION mask), sp80
confirmed one but stayed 0, and **vc33 regressed 1→0** (false-positive row-0
band + graph drop). Reverted. ⛔ moving-band masking on this stack: measured
net-negative, do not re-add without a target game that actually shows the
signature. Ported the actual converging lever: **legacy GF_REGION_MASK**
(per-cell rate > 0.05 → components → mask those with aggregate any-cell rate
> 0.7, spare components > 30% of board, dilate 1, sticky refresh every 16 from
a 32-window; graph dropped on first confirmation). Both remaining Gap-1 games'
legacy clears rest on it (tu93 masked=126, sp80 masked=2776). 679 tests. reg1
bench in flight (tu93/sp80 + vc33/m0r0/lf52/cn04 guards).

### 🎉 REGION MASK closes BOTH Gap-1 games + deepens vc33 (2026-07-09 23:53)
reg1: **tu93 0→1 (mask 41→92 cells), sp80 0→1 (masked play-adjacent widgets),
vc33 1→2 (L2 depth — first ever)**; m0r0/lf52 held. One regression: cn04 1→0 —
a 515-cell FIRST-refresh mask (transient early animation) swallowed its play
field (pool2 sink loop=0.70 distinct=1). Fix: 2-consecutive-refresh stability
gate (persistent widgets re-qualify every window; one-off animations never
enter the sticky union). reg2 verify in flight (cn04 + the three new wins).
If it holds: **11/25 SOLID** (cd82 cn04 ft09 lf52 lp85 m0r0 r11l sp80 tn36
tu93 vc33) + vc33 depth 2. The per-cell >=60% HUD rule + REGION-aggregate rule
+ tier gate + pursuit-gate-bypass now mirror the legacy engine's load-bearing
noise stack, re-derived by measurement.

### Size-conditional gate verified — reg3 all green (2026-07-10 00:04)
reg3 (6 games): cn04 1 (repair holds), tu93 1 (regained), sp80 1, vc33 1,
m0r0 1, lf52 1. The size-conditional region-mask gate (small masks <=128 cells
trusted on sight, larger additions need 2-consecutive-refresh stability) keeps
every win. Note: vc33's reg1 depth (2/7) did NOT reproduce in reg2/reg3 —
record it as a stochastic depth event, solid vc33 = 1. reg4 in flight to
re-verify the 5 solid games (cd82 ft09 tn36 lp85 r11l) never re-measured under
the region-mask code; if green → **11/25 SOLID** promotion.
