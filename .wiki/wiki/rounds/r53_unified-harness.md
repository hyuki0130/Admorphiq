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

### ✅ 11/25 SOLID CONFIRMED — full card verified under the final noise stack (2026-07-10 00:12)
reg4 all green (cd82 ft09 tn36 lp85 r11l = 1 each). **DEPLOYED CARD: 11/25
SOLID** — cd82 cn04 ft09 lf52 lp85 m0r0 r11l sp80 tn36 tu93 vc33, at the
deployed config, under: R38 tier gate (+pursuit bypass), hash ladder
(pool1→pool2→object, fire@500), REGION-level rate mask (size-conditional
stability gate). Session arc: 8 → 11. The ported-technique well for the
remaining 14 is DRY (legacy@8000 clears none of them) — next: (1) first-ever
measurement of the remaining 14 under the region mask (unmeasured
combination), then (2) the goal-inference frontier / efficiency axis.

### rem14 sweep: 13 zeros + a surprise sk48 clear (2026-07-10 00:28)
First-ever measurement of the remaining 14 under the final noise stack:
dc22 g50t ka59 sc25 s5i5 su15 wa30 ar25 bp35 ls20 re86 sb26 tr87 all 0
(the goal-inference wall confirmed — noise-stack techniques do not touch it),
but **sk48 = 1/8** — a game legacy@8000 does NOT clear (batch B measured 0):
the first unified-stack-only win (region mask × tier gate × dealias compose
beyond the legacy engine). Replication x2 + a 30k budget probe (ka59/sb26/tr87
— the legacy 30k-100k club) in flight: if 30k clears them, adaptive per-game
budget is a coverage lever for the 25/25 mission (RHAE-neutral).

### ✅ 12/25 SOLID (sk48 replicated) + ka59 opens at 30k + PARALLEL VM verified (2026-07-10 00:38)
nx1: **sk48 1/8 x2 replication → card = 12/25 SOLID** (+ sk48 is a
unified-stack-only win — legacy@8000 = 0). Budget probe: **ka59@30k = 1/7**
(adaptive budget = a real coverage lever for stuck games; RHAE-neutral),
sb26/tr87@30k = 0 (their wall is goal inference, not budget). OPERATIONAL
UNLOCK (user directive): parallel VM execution VERIFIED — 3 concurrent unified
runs (lp85+m0r0+nx1) completed with no arcengine deadlock and correct results;
the old "sequential only" note was an artifact. Multi-model tracks launched in
parallel (gemma4:26b-a4b vs qwen3-coder:30b harness on 6 games each: cd82 tn36
cn04 + su15 ka59 sc25) — role-based model routing / draw ensemble are the next
levers if tracks show complementarity.

### Multi-model track A: gemma4:26b-a4b (15GB MoE) HOLDS the core card (2026-07-10 00:40)
Track A (26b-a4b as harness brain+drawer, 6 games): **cd82 1, tn36 1, cn04 1 —
the draw-dependent and dealias-dependent card games all hold on the 15GB MoE**;
su15/ka59/sc25 stay 0 (the goal-inference wall is model-independent at this
scale). Throughput implication: 26b-a4b is ~2-3x faster per call than 31b-q8 —
if track C (full-card verify, 9 more games) is green, the deployed brain can
downshift for the Kaggle 9h budget. Track B (qwen3-coder:30b) relaunched after
a cwd bug (plain python3 from $HOME — parallel-nohup lesson: put cd INSIDE the
bash -c string).

### Model matrix verdict: card is model-INSENSITIVE, wall is scale-resistant (2026-07-10 00:47)
Track B (qwen3-coder:30b) = exactly track A's pattern: cd82/tn36/cn04 all 1,
su15/ka59/sc25 all 0. Three models (gemma31b-q8, gemma26b-a4b, qwen30b) give
IDENTICAL game-level outcomes on the 6-game probe → (a) the solid card rests
on the graph noise stack, not the LLM (any competent model suffices — the
throughput question goes to track C); (b) **no inter-model complementarity on
the wall games → the draw-ensemble idea is DEPRIORITIZED (measured, not
assumed)**; (c) the goal-inference wall does not yield to same-scale model
swaps — next escalation: gpt-oss:120b as brain on wall games (65GB, needs
VRAM headroom after track C).

### Track C: 26b-a4b holds 10/12 but loses tu93+sk48 — wholesale downshift rejected (2026-07-10 00:52)
Full-card verify on the 15GB MoE: lf52/sp80/m0r0/r11l/ft09/lp85 = 1, **vc33 =
2/7 (second L2 depth event, now under 26b)**, but tu93 0 and sk48 0 (both hold
at 1 under 31b). Wholesale brain downshift would cost 2 card games → rejected.
Open follow-ups: (a) role-split brain=26b / draw_llm=31b (harness already
separates draw_llm — config lever for the 9h budget), (b) tu93/sk48 loss may be
run variance (both are recent marginal unlocks) — variance track E in flight;
(c) track D = gpt-oss:120b (MoE, 5B active — fast despite 65GB) as brain on 5
wall games (su15 ka59 sc25 re86 wa30): the scale-escalation test of the
goal-inference wall.

### Track E: tu93/sk48 loss is model-real → 31b stays deployed brain (2026-07-10 00:57)
26b-a4b repeat: tu93 0, sk48 0 (now 0/2 each under 26b vs solid 1 under 31b).
Not variance — the cheaper brain genuinely loses the two marginal card games.
Deployed brain stays gemma4:31b-q8; the role-split (brain=26b/draw=31b) idea
is parked unless the 9h budget math forces it. Track D (gpt-oss:120b) partial:
su15 0, ka59 0 — scale escalation not biting so far.

### ⛔ MULTI-MODEL CAMPAIGN CLOSED: the wall is not a model problem (2026-07-10 01:00)
Track D final: gpt-oss:120b (largest on hand, MoE 5B-active) = 0 on ALL five
wall probes (su15 ka59 sc25 re86 wa30). Campaign verdict across gemma4:26b-a4b
/ qwen3-coder:30b / gemma4:31b-q8 / gpt-oss:120b, run in PARALLEL on the VM:
- Card (12/25) = graph-noise-stack dominated; model-insensitive EXCEPT
  tu93+sk48 which need 31b (26b loss reproduced 0/2 — model-real).
- Wall (13 games) = INVARIANT under model scale/family. ⛔ Do not buy more
  model-swap experiments on the wall; it needs a different capability class
  (runtime code-synthesis loop / richer goal evidence), not a bigger drawer.
- Draw ensemble: no inter-model complementarity → deprioritized.
- Deployed config unchanged: brain+drawer = gemma4:31b-q8.
- Coverage lever from nx1: ka59 opens at 30k → ADAPTIVE BUDGET policy
  (default 8000; unsolved games get a 30k retry pass if wall-clock allows) —
  deployment-runner design, RHAE-neutral, +1 coverage on the dev proxy.

### Dynamics-context code synthesis: no unlock (6 wall games 0) (2026-07-10 01:08)
Graph-informed code prompts (per-action tries/change-rate/median-cells from the
agent's own 200-transition log) on re86 wa30 sc25 tr87 ls20 g50t — all 0.
⛔ One-shot dynamics stats do not crack the wall either; the code the model
writes still can't state the GOAL. Next code-loop escalations (in order of
cost): (a) execution FEEDBACK loop — show the model its previous block's
observed effect and let it revise (the EWM refinement pattern, never applied
to solver code); (b) richer structure (object-level diffs per action, not just
cell counts); (c) adaptive budget deployment (+ka59, proven). SCALE-OUT: VM #2
(ewm-bench2) cloning launched per user directive — doubles parallel bench
throughput for the wall-research iteration loop.

### Code loop was NEVER exercised — routing starvation found + fixed (2026-07-10 22:20)
Attribution on the dyn/rf wall benches: **pick=code count = 0 across all 6
games** — the model never chooses {"mode":"code"} (the R9 name-preference
pathology, now measured on the harness), and the no-churn policy keeps the
stalled best tool running to the end of the budget. So BOTH "code synthesis
failed" verdicts (dynamics-context, execution-feedback) actually measured
routing starvation; the code work never ran. Fix (mechanical, per the R9→R11
lesson that prompt persuasion does not move this pathology): **deterministic
CODE escalation** — no new-state progress for 3 stall windows → the code path
gets ONE tenure per level; a stalled code tenure retires normally and tools
resume. Full lifecycle pinned by test (683 tests). esc bench in flight (wall 6
+ tu93/sk48 guards) — the first run where dynamics-context + execution-feedback
code synthesis actually executes on the wall.

### Escalation v1: mechanism works, cost exploded — controls added (2026-07-10 23:58)
esc bench: escalation fired 7x across 8 games (the code loop finally executes)
but **7/8 games blew the 1200s per-game timeout** — escalation re-fires after
every level reset/death and each tenure = ~10 LLM calls on a full 80-step stall
window. Only re86 completed: 0 (code ran, no unlock — first real code-loop
measurement). Controls shipped: tenures GAME-scoped (max 2), code stall window
24 steps (~3 blocks/tenure ≈ 6 LLM calls/game worst case). Re-benching.

### Escalation v2/v3 wall-clock holes closed one by one (2026-07-11 01:58)
Two more measured holes after the tenure-cap fix: (a) the "game-scoped"
counter lived in _reset_level, so death/level resets re-armed it (moved to
__init__); (b) a tenure whose code keeps FINDING NOVELTY never stalls — one
LLM call per <=8 actions to the end of the budget (wa30/tr87 still blew 1200s
with fires<=2). Fix: hard block budget _CODE_BLOCKS_MAX=10 per tenure,
force-retire regardless of novelty. Worst case now ~20 LLM calls/game
(2 tenures x 10 blocks). 684 tests. v4 bench in flight (script-file launch —
the new standard for VM batches; inline-quoted ssh nohup launches were the
source of the cwd bug and half the client hangs).

### VM batch ops lesson (2026-07-11 02:12)
Two silent-failure modes found in ssh batch launches: (a) inline-quoted nohup
lost the cwd (plain python3 from $HOME), (b) a chmod in a hung ssh never ran so
`setsid nohup ~/script.sh` failed on permissions with no error surfaced —
launches "succeeded" while nothing started. STANDARD NOW: scp a script file,
launch with `setsid nohup bash ~/script.sh`, and ALWAYS verify by polling for
the script's own log files before trusting the launch. Client-side gcloud ssh
hangs are common and say NOTHING about whether the remote command ran.

### ⛔ CODE-SYNTHESIS AXIS CLOSED — escalation default OFF, card restored (2026-07-11 04:02)
v4 (all wall-clock holes fixed, 8/8 games completed within budget): wall games
**0/6 under the first RELIABLE code-loop measurement** (dynamics context +
execution-feedback refinement actually executing, fires confirmed). Guards:
tu93 1 held; **sk48 0 — and 0/3 total with escalation ON vs 1/2 recovery with
it OFF (fires=0)** — causality pinned: code tenures interrupt sk48's
slow-progress graph path. VERDICT: ⛔ code synthesis at gemma31b scale does not
crack the goal-inference wall, and deterministic escalation is NET-NEGATIVE
deployed (0 unlock + 1 card regression) → HARNESS_CODE_ESC default OFF
(research flag; infra retained: dynamics prompt, refine loop, tenure/block
caps). Card: **12/25 SOLID restored**. Next lever: adaptive budget deployment
(ka59@30k = 13th game), then the efficiency axis / richer goal evidence.

### 30k adaptive-budget sweep: ka59 SOLID (3 samples) + ar25 opens (2026-07-11 04:55)
12-run sweep @30000 (GF_GIVEUP=30000): **ka59 1,1 replication → 3 total samples
= the 13th game** (with the adaptive-budget policy). **ar25 = 1 — NEW**: legacy
needed 100k for ar25; the unified stack (region mask × tier gate × dealias)
opens it at 30k (1 sample, replication chained). All eight others still 0 at
30k (dc22 g50t ls20 re86 s5i5 sc25 su15 wa30 — the goal-inference wall stands;
budget is not their lever). bp35 pending. If ar25 replicates: **14/25** with
the adaptive-budget policy (8000 default + 30k retry pass on unsolved games —
RHAE-neutral, deployment-runner design).

### ✅ 14/25 — ar25 replicated x2 (3 samples); adaptive-budget policy validated (2026-07-11 05:04)
ar25 @30k: 1, 1 replication (3 total samples incl. the sweep) — CONFIRMED.
**Card under the adaptive-budget policy (8000 default + one 30k retry pass on
unsolved games): 14/25** = 12 solid @8000 (cd82 cn04 ft09 lf52 lp85 m0r0 r11l
sk48 sp80 tn36 tu93 vc33) + ka59 + ar25 @30k (both 3-sample). bp35 0 closed
the sweep: budget opens NOTHING else. Remaining 11 (bp35 dc22 g50t ls20 re86
s5i5 sb26 sc25 su15 tr87 wa30) are goal-inference-walled with ALL cheap axes
closed by reliable measurement (budget ⛔ / model scale+family ⛔ / draw
diversity ⛔ / code synthesis ⛔). The one open road: RICHER GOAL EVIDENCE —
which is also the efficiency (RHAE) axis's root (know the target → short
path). Session arc 2026-07-09→11: 8 → 14/25.

### Efficiency diagnostic + sb26 world_model lead (2026-07-11 05:10)
Actions-to-clear across the card (from existing bench jsons): most L1 clears
are exhaustive-search stumbles — cd82 5786, sk48 6945, cn04 3361, m0r0 2951,
vc33 1902, tu93 1413 actions vs human baselines ~10-55 → squared-efficiency
≈ 0 each. TWO outliers: **ar25 clears EFFICIENTLY (L1 in 30 actions, 2 levels
/310 total, game_score 0.083 — more than the rest of the card combined)**, and
a forgotten 7/8 probe json shows **world_model clearing sb26 L1 in 9 actions**
(orch_sb26_world_model.json — the unified harness routes sb26 to graph, so the
tool that clears it never gets a turn; also contradicts the "world_model 0/25
standalone" note — that sweep likely mis-measured it). Replication x2 in
flight. If real: 15th game + an efficient clear + a routing-table fix
(tool_selector row for its signature).

### sb26 mechanism identified: the R28 WorldModelAgent's arrangement planner (2026-07-11 05:20)
The 7/8 mystery json traced to orchestrator_loop.py's "world_model" config =
`--agent worldmodel` = the R28 **WorldModelAgent** (object-centric online
world model + arrangement planner `plan_descend_and_sweep`), NOT the r53
world_model tool. Reproduced x2: **sb26 L1 in 259 actions, deterministic,
game_score 0.028**. R07's recorded caveat ("world-model is sample-specific")
was about deploying it as THE spine; as one mechanic-class solver in a
fallback chain it is frame-only/game-id-free. Wall sweep (10 games @2000) in
flight to measure its full coverage before choosing integration: fallback
pass in the adaptive policy vs technique port into the world_model tool.

### 🎉 WorldModelAgent fallback opens THREE walls efficiently (2026-07-11 05:15)
Wall sweep @2000: **su15 = 2 LEVELS in 58 actions (0.067), ls20 = 1 in 88
(0.036)** on top of sb26 (259 acts, 0.028); the other 7 walls 0 at trivial
cost (50-200 actions each — the agent's giveup is cheap). If su15/ls20
replicate: **17/25** under the 3-pass fallback policy (unified@8000 →
unified@30k → worldmodel@2000), and these three clears alone add ~+0.5%p RHAE
(several times the rest of the card). The R28 agent's object-centric planners
(arrangement descend-and-sweep, selection modes) are mechanic-class solvers
the r53 tools lack — port queue after replication.

### ✅ 17/25 CONFIRMED — 3-pass fallback policy; RHAE ~0.9% (2026-07-11 05:16)
su15 2/58 x2 and ls20 1/88 x2 replications (deterministic; 3 samples each incl.
the sweep). **CARD: 17/25** under the 3-pass per-game policy: (1) unified@8000
→ 12 games, (2) unified@30k retry → ka59 ar25, (3) worldmodel@2000 retry →
sb26 su15 ls20. Remaining walls: 8 (bp35 dc22 g50t re86 s5i5 sc25 tr87 wa30).
RHAE proxy total jumps from ~0.03% to **~0.9%** (ar25 0.083 + su15 0.067 +
ls20 0.036 + sb26 0.028 dominate — efficient clears, exactly what the squared
metric rewards) — past the online-RL deployed card (0.51%), approaching M1
winner (1.21%). Deployment note: the Kaggle runner must implement the 3-pass
chain with wall-clock awareness (pass 2 only if time remains; pass 3 is cheap
— 50-260 actions — and can even run FIRST as a fast probe). Session arc
2026-07-09→11: **8 → 17/25**.

### MEASURED policy total: 0.915% (25-game, best-pass-per-game) (2026-07-11 05:18)
Exact sum over all 25 games from bench jsons: **0.2286 → 0.915%** on the
leaderboard scale (vs online-RL card 0.51%, M1 winner 1.21%, top ~1.56%).
Top contributors are ALL efficient clears: ar25 0.083 (lv2 — and its best
record is ALSO WorldModelAgent, cheaper than the 30k unified pass), su15
0.067 (lv2), ls20 0.036, sb26 0.028, tn36 0.0065; the exhaustive graph clears
contribute ≈ 0 each, as the squared metric dictates. POLICY OPTIMIZATION NOTE:
run the cheap worldmodel pass FIRST (50-260 actions; it may replace the 30k
retry for ar25-class games entirely). Session: 8→17 coverage, 0.03%→0.915%
score.

### ChainedAgent shipped — the 3-pass policy as one artifact (2026-07-13 09:26)
`--agent chained` (src/admorphiq/chained_agent.py): worldmodel probe first
(banks the efficient arrangement-class WINs; self-terminates cheaply
elsewhere), unified harness owns the remaining budget on handover. Pass order
is score-critical under RHAE (all actions on a level count) — probe-first
costs the graph clears nothing (they score ~0) and keeps the efficient clears
intact. ka59 stays a runner-level 30k budget choice (not in-agent). Full-25
single-artifact measurement in flight — the honest deployable number vs the
0.915% best-pass-per-game estimate.

### ✅ SINGLE-ARTIFACT NUMBER: chained@8000 = 15/25, 1.076% (2026-07-13 09:46)
Full-25 measurement of `--agent chained` after the restart-flag fix: **15
games cleared, TOTAL 1.076%** — one deployable agent, no per-game policy
outside it. vs anchors: online-RL card 0.51% (x2.1), M1 winner 1.21% (89%),
top ~1.56% (69%). The probe banks the efficient clears (ar25 .083, su15 .067,
ls20 .036, ft09 .029, sb26 .028, tn36 .015, tu93 .008, lp85 .002) and the
unified handover recovers the graph card (cd82 cn04 lf52 m0r0 r11l sp80 vc33).
Deltas vs the 17/25 policy card: ka59 needs the runner-level 30k retry (in-
agent budget is the runner's choice), and **sk48 is chain-fragile** (unified
solo 1, chained 0 — the probe prefix perturbs its marginal path; score impact
zero, coverage follow-up). Session totals since 2026-07-09: coverage 8→15
single-artifact (17 with policy), RHAE 0.03% → 1.076% measured.

### 🎯 NO-LLM chained = 14/25, 1.072% — the LLM is nearly free to drop (2026-07-13 11:20)
Full-25 on the Mac (OLLAMA_HOST dead → offline-safe signature routing, no
draws): **14 cleared, 1.072%** vs the LLM stack's 15/1.076%. The entire LLM
contribution at the deployed scale = +1 game (cn04) and +0.004%p. cd82 cleared
WITHOUT draws (1 sample); vc33 reached L2. DEPLOYMENT IMPLICATION: the
first Kaggle notebook can ship LLM-FREE (numpy-only WMA probe + graph stack) at
~1.07% — 89% of the M1 winner with ZERO offline-LLM packaging risk; the
gemma stack becomes a v2 upgrade, not a blocker. GCP no longer needed for this
track (free trial ended 7/12; all billable resources deleted 7/13 — instance,
disks, snapshots; setup playbook recorded for any future GPU work).

### ✅ Kaggle v1 submission artifact VERIFIED offline (2026-07-13 12:30)
`KaggleChainedAgent` (official-interface wrapper, LLM-free chain) + notebook
switch + verify-script update: **end-to-end offline verification passes on the
Mac** (su15 cleared 2 levels through the OFFLINE Arcade, valid scorecard
JSON). The v1 submission is numpy-only — no weights dataset, no model mount,
no LLM runtime. Remaining ceremony (user-side / kaggle CLI): re-upload the src
dataset with current code, `kaggle kernels push` (free validation), then
`kaggle competitions submit` (consumes the daily slot). Measured expectation
on the dev proxy: 14/25 cleared, 1.072%.

### Kaggle ceremony step 1-2 DONE (2026-07-13 12:35)
`admorphiq-src` dataset uploaded (1.6M, numpy-only — no weights needed) and
the kernel pushed: kaggle.com/code/jaehyukhyun/admorphiq-arc-agi-3-chained-llm-free
(server-side free validation running; `kaggle kernels status` to poll). Step 3
(competitions submit, consumes the daily slot) awaits the validation result +
user go. Parallel local thread: no-LLM chained @30k sweep on the 11 unsolved
games (Mac, ~1000 steps/s — faster than the VM was).

### Local 30k sweep (Mac): sk48 recovered; ka59/cn04 are LLM-dependent (2026-07-13 12:50)
no-LLM chained @30000 on the 11 unsolved: **sk48 = 1** (the chain-fragility
dissolves with budget — no-LLM card = 15/25 with a 30k retry pass), ka59 0 and
cn04 0 (their earlier unlocks needed the gemma stack — the only two
LLM-dependent games), all 8 walls 0 (budget is not their lever, re-confirmed
locally). Kaggle: kernel v2 pushed after two mount fixes (competition data
nests under the competition slug via CLI; the dataset zip strips src/) + a
409 id/slug mismatch; server validation in flight.

### Kernel v4 RUNNING — import chain cleared (2026-07-13 13:17)
v4 (ARC_AGENTS_DIR shim override + dataset v2) has been RUNNING 10+ minutes on
Kaggle — every prior version died in 1-2 min at import. The offline Arcade
loop is playing the 25 games server-side. Fix genealogy: v1 blind → v2 layout
dump (CLI mounts nest under /kaggle/input/{competitions,datasets}/) → v3
walk-resolver (admorphiq imports) → v4 shim env override (agents imports).
Parallel local thread: paint_flood + general legacy agents sweeping the 8
walls @2000 (the WMA-discovery pattern extended to the other registered
mechanic-class agents).

### ⛔ Legacy-agent well is DRY for the 8 walls (2026-07-13 13:20)
paint_flood + general @2000 on bp35 dc22 g50t re86 s5i5 sc25 tr87 wa30: all 0
(16 genuine runs, agents self-terminate in 50-200 actions). Combined closure
for the 8 walls: budget ⛔ (30k), model scale/family ⛔, draw diversity ⛔,
code synthesis ⛔, every registered mechanic-class agent ⛔ (WMA/paint_flood/
general). These games need a capability that does not exist in the repo yet —
the genuine research frontier. Next candidates (unmeasured): per-game mechanics
study via scripts/inspect_game.py on each wall (what IS the win condition?),
then purpose-built mechanic solvers the way R28 built arrangement.

### Wall anatomy #1 — s5i5 decoded: attempt-limited rotation puzzle (2026-07-13 13:28)
Full-probe (inspect_game, no summary): click-only; most clicks only decrement a
row-63 ATTEMPT COUNTER (1-2 cells); exactly two widget cells produce real
11-cell rotation changes. Structure: rotate pieces to a target configuration
within a move budget — waste is punished, so efficiency-blind frontier search
fails BY DESIGN (explains every 0 across budgets/models). The purpose-built
solver shape (R28-arrangement pattern): detect rotatable pieces + reference
pattern, compute required rotation counts, click exactly. Next: same anatomy
pass on the other 7 walls, then build the first wall-class solver.

### Wall anatomy #2-8 — the walls are MOVE-LIMITED games (2026-07-13 13:40)
Full-probe on the remaining 7: **five of eight walls tick a bottom-row (row
63) attempt/move counter on (almost) every action** — s5i5, bp35, dc22, g50t,
wa30 (sc25's clicks are fully dead; re86/tr87 are large-region transforms).
Structural reframe: these are BUDGETED puzzles that punish waste, so
efficiency-blind frontier search self-destructs by design — the shared root
cause behind the "goal-inference wall" for the counter class. Solver
implications: (a) the per-cell HUD mask absorbs the counter for HASHING but
not for the GAME's own limit; (b) restart_on_game_over grants retries and the
graph accumulates across attempts, so the missing piece is DEPTH-LIMITED,
plan-first play per attempt (act only on a computed short plan, never probe-
sweep). Per-game table: bp35 move[3,4]+click(8,8)=39c; dc22 nav 8-9c moves,
clicks dead/counter; g50t only ACTION3 real (48c); re86 ACTION1-4 60c
transforms; sc25 ACTION3 36c, clicks 0; tr87 rotations 13-29c; wa30 ACTION1-4
32c + ACTION5 counter. Next: purpose-built counter-class solver design.

### dc22 diag: not an accumulation failure (2026-07-13 13:55)
graph-only @8000: levels=0, no GAME_OVER observed in the probe window (the
counter exists but exploration dies of exhaustion-of-ideas first, not of the
move limit). REGION mask 34 cells applied. dc22 keeps 10 colours — key/door
navigation suspected; needs its own mechanic study rather than the generic
counter-class treatment. Kernel v4: still RUNNING (~60 min server-side).

### 🏁 KAGGLE SERVER VALIDATION COMPLETE — score 1.0721, submission-ready (2026-07-13 14:10)
Kernel v4 COMPLETE (~2h server-side, well under the 9h cap): **submission.json
generated, score = 1.0721** — matching the local dev-proxy measurement
(1.072%) EXACTLY. 25 environments, 19 levels, 245,867 total actions. The
LLM-free chained v1 artifact is fully validated end-to-end on Kaggle
infrastructure (free kernels-push validation; the daily submission slot is
UNTOUCHED). Step 3 (`kaggle competitions submit`) awaits the user's go.
Optimization queued: switch the kernel to CPU (numpy-only agent — saves the
weekly GPU quota; GPU only needed for the v2 LLM stack).

### REAL submission protocol decoded + v5 pushed (2026-07-13 14:35)
The 400 body + the actively-submitting Duck v12 notebook revealed the actual
protocol: submissions must be generated by kaggle_evaluation — on a rerun a
LOCAL GATEWAY (ARC_BASE_URL http://gateway:8001/) serves the HIDDEN 110 games
and writes submission.parquet from the agent's actions; the offline
scorecard-JSON is validation-only (the M1-era SUBMISSION.md mechanism was
never a valid submission). v5 adds the rerun branch (wait-for-gateway →
COMPETITION Arcade) while keeping the offline path for free validation.
IMPORTANT HONESTY NOTE: every score so far (1.0721 included) is the PUBLIC
25-game dev proxy; the hidden-set number exists only after a real submission.

### s5i5 rotation-solver DESIGN (from the measured layout) (2026-07-13 14:40)
Board anatomy (offline dump): TWO stacked 5x5 pieces (color-4 frames, rows
36-40 and 42-46, cols 22-26, color-11 interiors) = the ROTATABLE pieces; the
color-14 shapes top-centre (size-14 at rows 9-11 + two size-7 at rows 20-22)
= the REFERENCE pattern; widget clicks at (40,24)/(24,40) rotate (11-cell
deltas); every other click burns the row-63 attempt counter. Solver sketch
(counter-class, plan-first): (1) segment pieces (compact multi-colour blocks
with distinct interiors) + reference (isolated same-palette shapes elsewhere);
(2) for each piece, simulate 0-3 rotations of its interior pattern and compare
to the reference orientation; (3) click that piece's widget exactly the needed
number of times; (4) never click anything else (attempt budget). Open
questions for implementation: widget->piece mapping (probe ONCE each — 2
attempts spent), rotation direction, and whether the reference maps 1:1 by
shape or by position. Implementation is the next bounded cycle.

### Rotation-plan family shipped; s5i5 needs INTERACTIVE disambiguation (2026-07-13 15:20)
rotation.py + WMA integration landed (12 new tests, 701 total, guards exact).
s5i5 verdict: the board's decorative colour-4 rings around reference glyphs
are statically identical to real piece frames — four static discriminators
each proven non-separating on the live board. ⛔ static single-frame piece
detection cannot crack s5i5; the follow-up is interactive probing (click a
candidate widget once, watch WHICH ring's interior rotates) — infrastructure
for that (widget probe attribution) already exists in the new _rotate_step.

### Submit precondition #2 decoded — placeholder parquet (v6) (2026-07-13 15:30)
v5 validated COMPLETE (65 min) but submit 400'd again: "Did not find provided
Notebook Output File" — the precondition checks the kernel version's OUTPUT
for submission.parquet by name. Duck v12's interactive branch writes a
PLACEHOLDER parquet ("offline run isn't scored, but Kaggle still expects a
submission.parquet output") — v6 mirrors it. Watcher auto-submits v6 on
COMPLETE with -f submission.parquet.

### ⚠️ DISCIPLINE LESSON + s5i5 truth: it's a SLIDER (the wiki knew) (2026-07-13 15:40)
Interactive disambiguation landed (validated general; 703 tests) and its live
trace overturned the design premise: 4 of 8 widgets DO respond, but they SHIFT
marker pixels ~3 cells along an axis — s5i5 is the SLIDER puzzle that
`.wiki/wiki/games/S5I5.md` documented all along (`game_type: slider_puzzle`,
"Clicking a slider moves its goal marker by 3 units along slider axis"). The
r53 "rotation-solver DESIGN" mis-modeled it from probe interpretation without
consulting the game page — a direct violation of the look-it-up-first rule;
cost: one full implementation cycle building the wrong physics. rotation.py
stays as a general capability (correct for genuine rotation mechanics; tests
prove it). NEXT: sibling slider module reusing the piece/widget-probe infra —
detect tracks/markers/goals, clicks-needed = axis distance / per-click step
(measured 3), click exactly.

### 🎉 FIRST WALL FALLS — s5i5 L1 via the slider family, BEATS the human baseline (2026-07-13 15:55)
slider.py + WMA integration: **s5i5 L1 = 19 actions vs human 20 → per-level
score 1.0 (capped), game_score 0.0278, deterministic x2**. The counter-class
plan-first thesis validated end-to-end: measure the step from ONE probe click,
compute clicks_needed, click exactly. Methodology notes that made it work:
positional (not colour) marker filtering (tip notch and goal share a colour),
raw-pixel tip scanning (components fragment at same-colour markers), slide
gate ordered before rotate (rotation's ambiguous fallback would claim slider
boards). Card: **16/25 in the chained artifact** (s5i5 flows in via the WMA
probe automatically) + su15 2/58, sb26 1/259 guards exact; 717 tests. Open:
s5i5 L2 (~150 actions spent without progress after the L1 bank — geometry
differs; next trace).

### s5i5 L2 traced: a REVEAL into a 4-pair matching puzzle (2026-07-13 16:05)
Clean replay-then-click trace: L2 starts at L1's end state; the four L1
grow/shrink buttons go fully inert; the previously-inert divider (42,21)
triggers an 862-cell REVEAL (new colour 15, bottom half fills with a new
structure): 4 button-PAIRS (interior colours 10/11/12/14), a glyph legend
cluster (rows 36-41), two colour-15 canvas blocks. detect_slider_puzzle
correctly returns None on it; the deployed agent's L2 behaviour is safe
fall-through (169-action smoke confirmed). Needs its own dedicated round —
banked for later; breadth (other walls) first. Trace data preserved here for
that future cycle.

### 🎉 SECOND WALL FALLS — re86 L1 at human-beating efficiency (2026-07-13 16:20)
transform_route.py (6th family member): **re86 L1 = 24 actions vs human 26 →
level score 1.0, game_score 0.0278, deterministic x2**. Records-first worked:
legacy re86_analytical's LOGIC (cover ring+dot required points with matching
sprites; ACTION5 cycles active) mined without its sprite-tag reads; all
constants measured live. One real bug (active-sprite bbox scan misreading
nearby markers) found, fixed, regression-pinned. Card: **17/25 chained**
(cd82 cn04 ft09 lf52 lp85 m0r0 r11l re86 s5i5 sb26 sk48* sp80 su15 tn36 tu93
vc33 + ar25; sk48 via 30k pass). Walls remaining: 6 (bp35 dc22 g50t sc25 tr87
wa30) + depth. NEXT: re86 L2+ — the changer tier; legacy reached 6/8, the
deepest RHAE pool of any wall (levels 1-6 = up to 0.58 game_score).

### re86 L2 falls — 2 levels at perfect efficiency (2026-07-13 16:40)
L1 24/26 + L2 40/42, both level score 1.0, game 0.0833, reproducible. L2's
mechanic: 3 distinct-shaped sprites for 3 colours (no changer yet). Three
measured bugs fixed en route (render-lag settle frame after level-up;
step-multiple offset preference; active marker = exactly-1-foreign-cell),
each regression-pinned — this family's "measure, fix, pin" loop is the
engine. 730 tests. L3+ dispatched (legacy ceiling 6/8).

### 🏁 FIRST-EVER SUBMISSION ACCEPTED (2026-07-13 16:41 KST)
Submission #54637991 (submission.parquet, v6 kernel) — **SubmissionStatus.
PENDING**: Kaggle is rerunning the notebook against the HIDDEN 110 games via
the gateway path. The project's first submission since the competition began
(the June "0 submissions" gap closed). Daily slot consumed; next slot resets
00:00 UTC (09:00 KST). The pending rerun includes the LLM-free chained agent
as of dataset v2 — NOTE: today's slider/transform_route/re86-depth work is
NOT in this submission (dataset uploaded before them); tomorrow's slot can
carry the updated card (s5i5 + re86x2 add ~+0.14 to the public-25 proxy →
~1.21, exactly the M1-winner anchor).

### re86 L3 wall + staleness fix banked (2026-07-13 17:00)
Fingerprint-gated staleness detection committed (solved boards keep their
markers visible → detection can SUCCEED on a stale frame — worse than None;
the unconditional-settle variant measurably regressed L2 via ACTION5 side
effects, evidence that settling must be evidence-gated). L3's wall: decoration
in the SAME colour as the sprite, 1-Chebyshev-step dots chain through
gap-bridging into a 132-cell pseudo-sprite, corrupting calibration AND offset.
Next cycle dispatched: MOTION-based classification (press one calibration
move, keep only cells that moved) — the let-the-env-discriminate pattern that
already won twice in this family.

### re86 BANKED at 2/8 (geometric proof); motion classification committed (2026-07-13 17:15)
Motion-based sprite classification works (L3 calibration fully recovered:
dy=-3.000 exact, dir_map clean) and is committed as family capability (735
tests, guards byte-identical). L3's true wall is GEOMETRIC, proven by
unconstrained offset search: no single translation of its 1-row bar covers 8
points across rows 6-39 — the "one sprite, one translation" model can't
represent it (multi-placement / changer / sequential — future scope). re86
banked at 2 levels, both 1.0. NEXT: wa30 (recorded delivery mechanic).

### 🎉 THIRD WALL FALLS — wa30 L1 at 30/71 actions (2026-07-13 17:50)
delivery.py (7th family member): pick-carry-drop with measured step=4 grid,
context ACTION5, fixed carry offset. Level score 1.0 (agent used 42% of the
human count). Card: **18/25 chained** — walls remaining: bp35 dc22 g50t sc25
tr87 (5) + banked depth (s5i5 L2 matching, wa30 L2 colour-12 entity, re86 L3
multi-placement, su15 L3). public-25 proxy now ~1.23. 752 tests.

### wa30 L2 = autonomous patrol actor — banked; tr87 round begins (2026-07-13 18:15)
colour-12 is a solid 4x4 actor moving once per player action on its own clock
(measured patrol: 3 right, 1 up, pause, 5 left — deterministic back-and-forth,
NOT collision-responsive). Correct handling needs timing-aware BFS (predict
actor position at each planned tick) — a genuinely different planner class;
banked with trace data for a future cycle. wa30 stays 1/9 at level score 1.0.
tr87 next: recorded mechanic is a ROTATION puzzle — the family rotation.py was
originally built for; agent checking whether the existing detector fits as-is
(baseline 0/6 @128 actions).

### tr87 traced: select-then-rotate GRID-MATCHING (new module scope) (2026-07-13 18:30)
Not a rotation.py fit on two measured grounds: control scheme is simple-actions
-only (opposite of the click-only gate), and the board is a 3x4 grid of ~12
unique pattern blocks + a lower control panel (two bars holding target glyphs
at matching column positions) — not isolated-piece-plus-reference. Controls
measured clean: ACTION1/2 rotate the SELECTED piece in place (13-15 cell
diffs), ACTION3/4 move a selection bracket between columns (28-cell border
jumps, opposite directions). Design: pair upper-grid pieces to lower-panel
targets BY COLUMN, rotate each to match, cursor-navigate between them. The
wiki's "target in a corner" note is stale (target data spans the panel).
Module cycle dispatched.

### tr87 mechanism decoded; win-rule hypothesis batch offline (2026-07-13 18:35)
Deep trace: 5-column control panel, each column a 7-STATE CYCLIC DIAL
(ACTION1=+1/ACTION2=-1, byte-identical return at press 7), bracket cursor via
ACTION3/4 (wrapping), bar1 = static per-column targets, upper 12-piece grid
unchanged across all presses. The natural win rule (dial mask == own-column
target) EXHAUSTIVELY disproven offline: 35 captured states x 5 targets, zero
matches in any pairing. Move counter confirmed (row 63) → remaining
hypotheses dispatched as OFFLINE computation on the captured masks: dihedral
equality, complement, count equality, upper-grid-as-key, side-channel scan of
the existing press traces.

### tr87 offline hypothesis batch (a)-(e): ALL FALSIFIED — banked (2026-07-13 18:50)
Zero live actions spent — pure offline recomputation on the single 35-state
capture. (a) dihedral equality (8 transforms x target, vs all 35 dial
states): zero matches. (b) complement equality (+dihedral): zero matches.
(c) colour-cell COUNT equality per column: columns 0/1/4 have ZERO dial
states matching their target's count at all (only cols 2/3 have any) — a
solvable per-column rule should clear this weak bar everywhere, so this is
evidence AGAINST same-column matching, not just inconclusive. (d) upper
12-piece grid as answer key (+dihedral): matches found but a red herring —
exactly 5 of 12 upper patterns each matched ONE state per column UNIFORMLY
across all 5 columns (decorative palette reuse, not an encoded answer).
(e) side-channel scan of all 35 press-transition frame pairs (outside the
dial box + HUD row): none found. Full elimination table recorded at
[[../lessons/tr87_dial_match_hypothesis_falsified_20260713]] (also updates
[[../games/TR87]] and flags the [[../game_types/rotation]] misclassification)
so a future session doesn't re-spend a live-trace cycle re-deriving this.
tr87 banked at 0/6 (mechanism decoded, win condition open). Card holds at
18/25 chained (wa30 L1 fresh); moving to dc22 next.

### dc22 MYSTERY SOLVED — back-and-forth toggle maze; BFSSolver gap found (2026-07-13 18:50)
The toggle-state x movement matrix cracked it: room2's toggle opens the box's
top wall; the REAL winning sequence (extracted live from the legacy
bfs_state_space path, 20 actions) toggles the SAME button on, uses the
opening, then toggles it OFF to open a different path — a backtracking toggle
maze no greedy explorer finds. ARCHITECTURE GAP: the proven general tool
(planner/bfs_solver.py + dense-grid click discovery, 40k states/90s) is not
referenced anywhere in the current agent stack — the legacy 1/6 vs current 0/6
difference in one finding. Integration dispatched as a GATED LAST-RESORT phase
(hybrid signature only, after all mechanic modules decline, per-level action
cap, RHAE-honest coverage backstop) + family check on g50t/sc25/bp35.

### BFSSolver is contract-incompatible; region-mask suspicion on the deployable stack (2026-07-13 19:00)
Pre-build check caught it: BFSSolver drives env.step()/env.reset() directly —
the official contract is is_done/choose_action only, so a literal port could
never ship (dev-only tool). The contract-compliant equivalents (legacy
graph_frontier AND the unified graph tool) BOTH fail dc22 0/6. Live hypothesis
with one supporting data point ([graph] REGION mask: 52 cells on dc22): the
region mask may be eating the TOGGLE-STATE pixels — masking frequently-toggled
GAME STATE as if it were HUD, collapsing exactly the state distinction the
winning sequence depends on. If confirmed this is a GENERAL masking bug.
Dispatched: diagnose (mask dump vs toggle cells), then fix = ACTION-CORRELATED
masking (many distinct action keys → HUD; one specific key → game state),
with tu93/sp80 (mask-dependent unlocks) as critical guards.

### Action-correlated masking LANDED; confined-avatar gap is the next cycle (2026-07-13 19:10)
The fraction-based action-correlation fix is committed (753 tests; tu93/sp80
masks byte-identical; off-by-one action attribution caught pre-ship). The
REMAINING root cause for the box-confinement family (dc22 g50t sc25 bp35): a
CONFINED avatar churns the same few cells under all movement keys → same
high-action-diversity signature as HUD → the avatar's own region masks and
in-box positions hash identically. Consistency check: free-roaming avatar
games (tu93/lf52/m0r0) never trip this because per-cell rates stay low across
a large board. Next cycle dispatched: per-key diff-set similarity (HUD changes
the same cells regardless of key; an avatar's changed cells DIFFER by key —
Jaccard across per-key unions), composed with the fraction rule.

### Confined-avatar discriminator: 2 more formulations measured and FALSIFIED — axis banked (2026-07-13 19:40)
Per-key diff-set Jaccard (mean pairwise Jaccard of per-key changed-cell unions,
live-measured dc22 1200 steps): row63 (HUD ground truth) min=0.16 max=1.00
mean=0.68 vs box (avatar ground truth) min=0.35 max=0.78 mean=0.47 — ranges
overlap heavily, no threshold separates cleanly. Root cause: dc22's counter is
a MONOTONICALLY-ADVANCING bar, not a repeating digit — the same key pressed at
different points in the bar's progression touches different cells, so even
same-key self-similarity is low sometimes, breaking the "HUD repeats regardless
of key" assumption itself.

Per-key displacement vector (arrived-centroid minus vacated-centroid per key,
mean pairwise cosine similarity across keys — local-background-aware, not
global, since a walled sub-scene has its own floor colour): WORSE than
falsified — UNUSABLE for row63 (0 valid samples across the whole 600-step
trace; a monotonic bar never vacates a cell, so "arrived minus vacated" is
undefined for the one ground-truth HUD case that matters here) and, for the
box, showed HIGH cross-key cosine similarity (0.62-0.99) — the OPPOSITE of the
"an avatar's direction differs by key" hypothesis — with individual per-key
vectors internally inconsistent across refresh windows (the SAME key showing
different, sometimes physically-backwards directions call to call).

Three formulations tried on this axis: (1) raw distinct-action COUNT — broke
an existing test, fixed into (2) a FRACTION of the window's distinct actions
— this one LANDED (see above) and is the real, tested, deployed gain. (3)
per-key diff-set Jaccard similarity and (4) per-key displacement-vector cosine
similarity were both measured live against dc22 and neither separates HUD
from a confined avatar. Full elimination table + why each failed:
[[../lessons/dc22_confined_avatar_discriminator_falsified_20260713]].
Axis banked — the confined-avatar gap (dc22/g50t/sc25/bp35 all still 0 with
the fraction fix alone) stays open for a future session with a fresh angle.
Moving to su15 L3 (WMA clears L1-2 in 58 actions; L3 unexplored).

### su15 legend decoded LIVE: merge chain = the legend's own ORDER (2026-07-13 19:35)
Dynamic decode (one live merge each tier): 10+10 -> 6, 6+6 -> 15 — the merge
target is the NEXT swatch in the board's own top-left legend sequence
(10→6→15→11), NOT colour+1 arithmetic (which would silently produce the wrong
target). Mixed starting tiers confirmed (3 colour-6 pre-placed); two goal
containers exist but detect_drag_layout currently sees one; goal-acceptance
rule = the one open question (probe dispatched, then the merge/multi-goal
extension builds on full evidence).

### su15 goal-acceptance probe: BOTH tiers rejected at near-zero distance — naive proximity hypothesis FALSIFIED (2026-07-13 20:10)
Bounded 2-data-point live probe against `su15-1944f8ab` L3 (both using the
real `next_merge_click`/`_step_toward` walk mechanics, not a simplified
stand-in, so the click behaviour matches what the shipped agent would do):

- **Data point 1 — colour-6 (non-terminal tier)**: walked toward goal A
  `(9.0, 50.0)` for 20 clicks. Reached `dist=0.7` from the goal centroid at
  clicks 5, 12, and 14 (three separate times, not a fluke) — closer than
  `_GOAL_REACH_PX` (6.0) and closer than the tile's own bounding radius.
  Never consumed: no level-up, tile persists every time, oscillates around
  the goal instead of settling. The goal container's OWN measured pixel
  size dropped 69→65 (exactly the tile's size, 4px) while the tile
  overlapped it — consistent with the tile rendering ON TOP of / occluding
  container edge pixels, not being absorbed into a hole.
- **Data point 2 — colour-11 (terminal tier, the true end of the
  10→6→15→11 chain)**: built via `next_merge_click` run to natural stall
  (same stall as
  [[../lessons/merge_drag_stall_causes_game_over_20260713]] — two
  unresponsive leftover tiles at click 16), which already produced one
  genuine colour-11/size16 tile by click 10. Walked that tile toward the
  SAME goal for 20 clicks. Reached `dist=0.7` at click 8 and `dist=1.6` at
  clicks 6/10/17 — same near-zero pattern as data point 1. Never consumed
  either.

**Conclusion**: the naive "drag centroid to goal centroid, any tier or the
terminal tier, and it gets accepted on overlap" hypothesis is FALSIFIED for
BOTH tiers — this rules out both "any tier delivers" and "only the terminal
tier delivers" as simple proximity rules. The goal-acceptance mechanism is
NOT proximity-based in the way `next_drag_click`'s `_GOAL_REACH_PX` model
assumes. Leading unconfirmed candidates for a future probe: (a) delivery
requires landing on an EXACT container pixel/slot rather than a computed
centroid-ward step, which may overshoot the diamond shape's narrow interior
every click before the tile can settle; (b) a precondition — e.g. the
wiki-documented enemy-downgrade interaction — must fire before either goal
accepts anything, independent of tile tier; (c) the two containers require
a specific tier-to-goal ASSIGNMENT not yet tested (both data points here
only tried goal A). None of these were tested — the probe budget (2 data
points) was spent confirming the negative result, per instruction, not
chasing a third hypothesis live. Reported back rather than building a
speculative delivery mechanism on an unconfirmed rule (repo Implementation
Discipline: no speculative logic without evidence).

**What IS safely buildable from this round without more live-env budget**:
the legend-order merge chain (`10→6→15→11`, confirmed live twice, generic
by legend-swatch position/size rather than hardcoded colours) and detecting
BOTH goal containers (straightforward connected-component filter, unlike
`detect_drag_layout`'s current single-largest-cluster assumption). The
delivery/acceptance step is NOT safely buildable yet. Landed as
`detect_merge_chain` / `detect_goal_containers` in `merge_drag.py`, both
pure/unwired, 4 new tests (757/757 suite green), verified live against the
real board (`[10, 6, 15, 11]`, both goal centroids).

### su15 delivery follow-up: legacy-code mining + a second live round — enemy hypothesis REJECTED for L3, diamond-shape-precision is the new lead (2026-07-13 20:40)
Per dispatch: mined `strat_su15_vacuum` (`agent_ensemble.py:6171-6781`, the
brittle v1 solver) for the DOWNGRADE mechanic's shape before any more live
probing, then ran one more bounded live round.

**Mechanic mined (shape only, not copied into any new implementation)**:
downgrade is NOT "enemy touches fruit" passively — the solver actively
SUCKS the over-target-coloured fruit TOWARD the nearest enemy
(`_suck_toward(downgrade_fruit, ex, ey)`), gated behind `if need_downgrade
and game.peiiyyzum:` (a non-empty enemy list). Delivery uses an internal
containment predicate (`game.epvtlqtczz(sx, sy, gz)`), and a same-purpose
inline check elsewhere is an explicit AABB test — `_in_gz = (fx < gz_right
and fx+size > gz_left and fy < gz_bottom and fy+size > gz_top)` — i.e.
delivery is a bounding-box question, not a centroid-distance one.
Critically: level indices 0/1/2 (L1/L2/L3) have NO hardcoded block in this
solver — they fall through a GENERIC downgrade→merge→deliver path, so the
solver's own author also treated L3 as "possibly needs downgrade,
possibly doesn't" rather than a known special case.

**Ground-truth read (diagnosis only, one-shot, not built into any shipped
path)**: the legacy attribute names (`peiiyyzum`/`hmeulfxgy`/`rqdsgrklq`)
resolve to `None`/empty on this v2 hash (`su15-1944f8ab`) — the well-known
v2 obfuscation problem ([[../lessons/v2_hash_obfuscation]]) blocks even
read-only diagnosis via those names. Fell back to the generic
`Level.get_sprites()` API and enumerated ALL 17 sprites on L3 by hand:
6× colour-10 tiles, 3× colour-6 tiles, 2× colour-9 diamond goals (9x9,
transparent corners — genuinely diamond-shaped, not square), 2×
background panels, and — the new finding — a 1-row legend-template sprite
at `(1,1)` encoding `[10, 6, 15, 11, 12, 8]` (six tiers, though only the
first four render visibly on screen; 12 and 8 may be off-screen/clipped,
unconfirmed), PLUS two solid, static, unaccounted-for blocks: a 4x4
colour-11 block at `(30,3)` and a 3x3 colour-15 block at `(36,4)`, sitting
in the top decorative band right next to the legend. **There is no enemy
sprite anywhere in the 17-sprite list.** This REJECTS the enemy-downgrade
hypothesis for L3 specifically — whatever blocks the two leftover tiles,
it isn't a missing enemy interaction (at least not one visible to
`get_sprites()`; a sprite gated behind some other list was not ruled out,
but the natural `peiiyyzum`-equivalent-by-tag search found nothing enemy-
shaped).

**New lead**: the two solid top-band blocks are the SAME colour AND SAME
size as the two "stuck" tiles (colour-11/16px, colour-15/9px) — a strong,
frame-observable (no internals needed — plain `connected_components` on
the top band finds them) candidate for PER-GOAL TARGET INDICATORS rather
than decoration. `detect_goal_containers`/`detect_merge_chain`-adjacent
detection of these could plausibly resolve which tier each goal wants.

**Second live round** (reused the natural chain-build stall, ~30 clicks,
then 3 delivery attempts):
- colour-11 → goal B (untested goal from the earlier round): reached
  `min_dist_seen=0.7` (same near-zero pattern as goal A) but the 20-click
  budget ran out before 4 consecutive stalled clicks confirmed rejection —
  result INCONCLUSIVE, not a clean accept or reject. Goal-B acceptance of
  colour-11 is NOT ruled out.
- colour-15 → goal A: **GAME_OVER at click 3** — much faster than the
  stall-driven GAME_OVER measured earlier (that took ~22 clicks). The walk
  path from the colour-15 tile at `(28,38)` toward goal A `(9,50)` likely
  passes near/through the colour-11 tile at `(15.5,34.5)` — plausibly a
  DIFFERENT failure mode (the solver's own docstring: "different-colour
  overlap = flash/undo, wastes steps with penalty" — this round did not
  confirm whether that penalty is what escalated to GAME_OVER here, or
  something else). This is a NEW, distinct GAME_OVER trigger, not yet
  understood — flagged for a future round, not chased further this round
  (budget discipline).

  **Zero-live-cost follow-up (post-hoc arithmetic on already-collected
  data, no new clicks spent)**: recomputed the first delivery click from
  `_step_toward((28,38), (9,50), 7.0)` = `(22, 42)` — the EXACT same point
  that was the dead-click target for the colour-11 tile in the original
  stall trace
  ([[../lessons/merge_drag_stall_causes_game_over_20260713]]). Distance
  from `(22,42)` to the colour-11 tile `(15.5,34.5)` is `9.92px`, just
  outside the legacy solver's stated `RADIUS-1=7px` pull distance —
  suggestive of the two-tile collision hypothesis but not conclusive (the
  actual live grab radius on this env may differ from the legacy `RADIUS`
  constant, which itself came from an obfuscated attribute
  `game.qjlubdgly` that may not resolve the same way here). Flagged, not
  confirmed.

**Honest state**: the diamond-shaped goal geometry (transparent corners in
the sprite pixel data — not a solid square) combined with the AABB-style
internal acceptance check mined from the legacy code is now the leading
hypothesis for why centroid-distance walking never triggers acceptance
even at `dist=0.7`: a step-computed click can land the tile's small
bounding box over a TRANSPARENT corner cell of the diamond rather than a
solid interior cell, so "close by centroid" does not imply "AABB-overlaps
the goal's actual solid pixels." This was not tested directly (would need
pixel-level tile-vs-diamond overlap tracking, a further probe). Per-goal
tier assignment (colour-11↔goal-A vs colour-15↔goal-B, matched to the
indicator positions) also remains untested in either direction conclusively.
Not building delivery logic on this yet — still short of a confirmed rule.

### su15 diamond-transparency hypothesis REFUTED by direct pixel geometry — precondition/tier-assignment is now the leading lead (2026-07-13 22:27)

Per the fallback pivot from AR25 L3 (banked above, `1dd5e1a`), tested the
leading "diamond-shape-precision" candidate directly rather than continuing
to reason from centroid distance alone — two near-zero-cost pixel dumps, no
delivery-walk budget spent (the earlier rounds' click budget for actual
delivery attempts is untouched):

1. **Goal diamond pixel mask** (`su15-1944f8ab` L3, both goal instances,
   identical): 9x9 bbox, confirmed genuinely non-square —

   ```
   ..#####..
   .#######.
   #########
   #########
   #########
   #########
   #########
   .#######.
   ..#####..
   ```
   81 bbox cells, 69 solid / 12 background-transparent — the transparent-
   corner geometry from the round-page hypothesis IS real. But the solid
   region is large: a guaranteed-solid 5x5 core (rows 48-52, cols 7-11
   relative to centroid (9,50)) plus a 7-wide band one ring out.

2. **Tile pixel mask** (colour-11 size-16 and colour-15 size-9, built via
   the same natural chain-build stall used in every prior round — no new
   mechanic exercised): both are **perfect solid squares**, 4x4 and 3x3
   respectively, zero transparent cells. The tile shape is not the
   irregular one.

**Conclusion: the transparent-corner-precision hypothesis is REFUTED by
geometry, not just untested.** A solid 4x4 or 3x3 tile centered within the
measured `dist=0.7px` of the goal centroid sits entirely inside the
diamond's guaranteed-solid 5x5+ core — there is no computed click position
at that distance whose tile footprint could land exclusively on a
transparent corner cell. So "the tile overlaps a transparent pixel instead
of a solid one" cannot be why delivery was rejected at `dist=0.7` in the
earlier rounds' live data. This is a genuine elimination, not an inference
gap — both shapes were read directly from the live frame's pixel data, no
internals.

**What remains standing from the round page's candidate list**: (b) a
precondition independent of tile tier, and (c) per-goal tier assignment
(colour-11↔goal-A vs colour-15↔goal-B via the top-band indicator blocks) —
neither refuted, neither confirmed. (a) is now closed. No further live-click
budget spent this round on (b)/(c) — the geometric elimination was the
disciplined stopping point matching this round's established 2-data-point
budget norm; a live test of (b)/(c) is the next session's lead, not
continued here.

### su15 attempted completion of the tier x goal matrix — false alarm, re-derived an ALREADY-FIXED stall pattern by bypassing the fix (2026-07-13 22:30, corrected 22:35)

Attempted the one still-untested cell of the pairing matrix — colour-15 →
goal B — to close out hypothesis (c) cleanly, using a custom bare-loop
probe script that calls `next_merge_click` directly. Hit `GAME_OVER` at
click 22, reproducibly (4/4 runs, exact same click count and exact same
dead click `(22, 42)` repeated 5 times immediately before it), across two
different env-loading paths.

**This was initially mis-logged here as a "new chain-build reliability
regression."  It is not new — it is an exact re-derivation of
[[../lessons/merge_drag_stall_causes_game_over_20260713]]'s own documented
"Baseline (`next_merge_click` called in a bare loop, no caller-level
guard)" trace**, which recorded the identical symptom (dead click at
`(22,42)` repeated 5x, GAME_OVER at click 22) in exact numeric agreement.
That lesson page also records that a fix already LANDED the same day (grep
`_MERGE_DRAG_STALL_LIMIT` in `world_model_agent.py`, confirmed present at
lines 230/786/1872+): `WorldModelAgent._merge_drag_step` caps consecutive
no-progress walk clicks at 3 and falls through to the interaction pipeline
instead of repeating a dead click toward GAME_OVER. My probe script,
written fresh this session without first checking the existing lesson
pages, called the pure `next_merge_click` function in its own custom loop
— exactly bypassing the stateful stall-detection wrapper the fix lives in
— so it necessarily reproduced the pre-fix baseline, not current agent
behaviour. The su15 guard (`2/9, 58 actions`, unchanged across this whole
session) already confirms the real agent path is unaffected.

**Corrected takeaway**: no new regression. The underlying capability gap
the lesson page identifies — SU15 needs a downgrade-then-merge sequence for
the two leftover tiles that neither `next_merge_click` nor
`next_drag_click` implement — remains the actual open blocker, unchanged
by this probe. The tier×goal delivery-acceptance question (hypotheses b/c
from the section above) is UNTESTABLE via this bare-loop methodology at
all — any future live probe of delivery-acceptance must drive through
`WorldModelAgent`'s actual `_merge_drag_step`/interaction path (or
explicitly re-implement the same stall guard in the probe script), not
call `next_merge_click` in a raw loop, or it will hit this same false
floor. Lesson for the wiki-authoring habit: check `.wiki/wiki/lessons/`
for the exact symptom BEFORE writing up a "new" finding — this cost one
extra round-trip that a `grep -r "GAME_OVER.*click 22"` over `.wiki/`
would have caught immediately.

### Day wrap: v2 submission assets staged (2026-07-13 19:51)
Dataset v3 (all of today's modules) + kernel v7 pushed — validating overnight
with the 18/25 card (public-25 proxy ~1.23). Submission #54637991 (v6 card,
1.072 proxy) still PENDING on the hidden set. NEXT-SESSION CHECKLIST:
(1) check #54637991's publicScore (`kaggle competitions submissions`),
(2) check v7 validation COMPLETE + its interactive score in the kernel log,
(3) submit v7 when the daily slot resets (00:00 UTC / 09:00 KST):
`kaggle competitions submit arc-prize-2026-arc-agi-3 -k
jaehyukhyun/admorphiq-arc-agi-3-chained-llm-free -v 7 -f submission.parquet
-m "..."`. su15 L3 delivery banked with AABB/transparent-corner + indicator-
block recovery leads; every remaining wall has a documented elimination table.

### Depth survey: sb26 / ls20 / ar25 L2+ blockers (2026-07-13 20:55) — same shape, different scope; sb26 is the near-free pick
Per dispatch: worldmodel @ 3000 actions on each of the three families whose
L1 (or L1-2) already clears efficiently, to check whether the next level is
near-free (the re86 precedent — three small measured fixes cleared L2) or
genuinely new. All three replicated their exact banked baselines at 3000
actions (not budget-starved), then were traced for phase transitions and the
PRISTINE next-level board (captured immediately at the level-up, before any
`interact`-phase clicks could corrupt it — the first pass mistakenly analysed
a post-237-click corrupted sb26 L2 frame and had to be redone).

**sb26 (1/8 levels, 259 actions unchanged)**: `sort_match`'s own detector,
`detect_match_layout`, correctly identifies L2 on the PRISTINE board — live-
verified: a full 6-colour reference/pool layout (`reference=[(10,12),
(18,15),(24,8),(32,9),(46,11),(52,6)]`, matching `pool`). So the family DOES
re-fire on L2 (phase bookkeeping resets correctly per level). The blocker is
downstream: `_sort_match_step` (`world_model_agent.py:1740`) drains the
placement plan **open-loop** — pops and fires each `("click", x, y)` /
verify action with NO per-placement check before advancing to the next
swatch (`plan_match_placement` in `sort_match.py`). Phase trace shows the L2
attempt ran ~14 actions (consistent with a 6-swatch plan: 6 clicks + verify
overhead) then fell to `interact` — "plan exhausted without a level-up," the
documented on-failure behaviour. L1 apparently has fewer colours (worked
first try); L2's larger 6-swatch instance is where blind, unverified
placement drift/misattribution first breaks the level. **Same mechanic,
bigger instance, execution not robust to scale — not a detection gap.**

**ls20 (1/7 levels, 88 actions unchanged)**: NOT slider-family as
hypothesised — L1 clears via `execute` (movement/navigation) in 22 actions.
Traced the first 20 steps of L2: `_nav_attempted` and `_move_disc_done` are
BOTH already `True` by the very first post-level-up step — the reset-then-
reattempt DOES fire fresh (same pattern as sb26), but plan-building fails
within that single call and falls straight to blind `interact`, which then
triggers `GAME_OVER` three times (steps 88/155/222) before `is_done()` gives
up at 273. Pristine L2 board dump: a substantially more complex multi-room
maze — several separated rooms joined by narrow (1-cell) corridors, plus
**two** candidate goal-marker shapes (matching small 3x3 "frame with hole"
cross patterns at different rooms, `bXb`/`bbb` in the raw-grid dump) rather
than a presumably single clear target on L1. Leading hypothesis: either the
BFS can't find/complete a path through the multi-room structure, or the
goal-selection heuristic picks the wrong one of the two candidate markers.
**Same shape as sb26 (mechanism re-fires, single blind attempt insufficient
for a harder instance) — not confirmed which of path-finding vs goal-
selection is the exact failure point (would need one more targeted probe).**

**ar25 (2/8 levels, 317 actions unchanged)**: a movement+arrangement HYBRID
per level (`execute` then `arrange`, confirmed both L1 and L2's clears went
through this same two-stage sequence). L3's trace differs qualitatively from
sb26/ls20: `probe→execute→arrange→probe→interact` — BOTH mechanisms were
re-attempted fresh, plus an extra `probe` cycle, before giving up (more
fallback structure than the other two games' single-attempt-then-abandon).
Pristine-ish stall board (captured at give-up, not immediately post-level-up
— lower confidence than the other two) shows a board bisected by a
horizontal colour-10 band (rows 33-35, full width) into two regions with
MIRRORED colour-11/5/4 blobs above and below (cy≈6.6/49.4, 28.4/26.0,
39.4/42.0) — a two-region, possibly cross-region-coordination structure,
unlike L1/L2's presumably single-region layout. **Least well-scoped of the
three — two systems interact (execute + arrange) and which one specifically
fails, and why, was not pinned down at survey depth.**

**Cross-cutting architectural observation** (not asked for, but load-bearing
for the pick): every specialized phase in `WorldModelAgent` follows the same
documented policy — "tried once per level; on failure the phase abandons to
`interact` for the rest of the budget" (see `_sort_match_step`'s and
`_merge_drag_step`'s own docstrings). This is a deliberate budget-safety
policy, and all three surveyed games hit it: the mechanism correctly
re-detects and re-attempts each level, but a SINGLE blind pass (open-loop
plan drain for sb26, one-shot BFS/goal-pick for ls20, one execute+arrange
pass for ar25) has no recovery path when that pass doesn't fully succeed.
This is a plausible single lever across all three, not a per-game
coincidence — but it's a bigger, riskier change (touches the core dispatch
policy) than a single-game fix, so it's flagged, not proposed as the pick.

**Pick: sb26.** Cleanest, most surgical diagnosis of the three — the fix
shape is narrow and localized (`_sort_match_step`/`plan_match_placement`:
verify each placement before advancing, retry a misplaced swatch instead of
draining blindly), doesn't require new detection logic (the detector already
works), and doesn't touch a second interacting system the way ar25's
execute+arrange hybrid does. Closest match to the re86 precedent (small,
localized, near-existing-logic fixes).

**Guards untouched** — survey was read-only on code (only new probe scripts
in the scratchpad, no `src/` edits this round). No commit.

### sb26 build cycle: the "near-free" pick was wrong — it's a portal-graph traversal puzzle, not a placement-robustness gap (2026-07-13 21:20)
Per doctrine, traced ONE failing L2 placement before coding anything.
Result overturned the survey's diagnosis entirely and the pick was
abandoned mid-cycle — recorded here so a future session doesn't retry the
same "just add verification" plan.

**What the live trace showed**: the existing `plan_match_placement` click
target — `(ref_x, placement_y)`, the reference frame's own column at the
arithmetic midpoint between reference-row-y and pool-row-y — has ZERO
effect on L2. Tested 9 different y-values at the reference column
(spanning both visible mid-board structures) after selecting a swatch:
none moved anything. A simpler alternative hypothesis — "select all 6
pool swatches in reference order, then verify, no physical placement
needed" — was also tested live and falsified (no level-up).

**What actually moves a swatch**: two rail-bordered boxes on the L2 board
(one on L1), each containing small uniform "22"-coloured 2x2 slot
markers, structurally separate from BOTH the reference row and the pool
row. Selecting a pool swatch then clicking one of these slot markers DOES
physically relocate the swatch there (pixel-confirmed, repeatable, 100%
success rate once the slot's true centroid is used — a
`connected_components`-based detector in the mid-band, excluding
reference/pool colours, grouped into boxes by y-proximity then ordered
left-to-right, found all 7 L2 slots precisely).

**Why L1 "worked" under the old code**: L1's board has the identical
structure — ONE rail box with exactly 4 slots for its 4 colours. The old
arithmetic `placement_y` numerically lands inside that single box's
y-range by coincidence, and the reference frame's x-position happens to
sit close enough to a real slot's x-position for L1's simpler single-box
layout to register a hit (or close enough for the env's click-grab
radius). On L2 (two boxes, 6 colours, 7 slots), that coincidental
alignment breaks down completely — confirmed: zero of 9 candidate clicks
at the naive column landed on anything.

**Mapping probe (2 live attempts, both pixel-confirmed placements, both
failed verify)**: (1) reference order → natural slot order (box1's 3
slots left-to-right, then box2's 4): all 6 swatches landed exactly where
targeted, `verify` (ACTION5) did not clear the level. (2) reference order
→ box2-first slot order: same outcome. No per-slot correctness feedback
(flash/undo/colour-change) was observed distinguishing a right placement
from a wrong one in either attempt.

**Legacy-code mining (`strat_sb26_sort`, `agent_ensemble.py:5016-5300+`)
revealed why both attempts were structurally doomed, not just wrongly
ordered**: SB26 is a **portal-graph traversal puzzle**. Frames (what this
round's probes called "box1"/"box2" — genuinely two separate FRAMES, not
decoration; their distinct border colours 8 and 14 are frame identity
markers) each expose N slots, N baked into the frame's own name/identity.
Slots may hold either a plain colour item OR a **portal** sprite that
redirects traversal to a DIFFERENT frame (matched by border colour). The
level's target colour sequence (`game.wcfyiodrx`, internal — no frame-only
equivalent found) is consumed via a **DFS traversal starting at frame[0]**,
following portal links; a "revisit" (a portal loop returning to an
already-visited slot) must match the colour seen on FIRST visit, not
consume a fresh target. Some pool items are themselves portal pieces
needing placement (`bottom_portals`), visually indistinguishable (so far)
from plain colour swatches. The legacy solver does a full
`itertools.permutations` search over candidate portal-slot placements,
simulates the traversal for each, and only commits once a permutation's
traversal-consumed colour sequence matches `targets` exactly.

**Why both mapping attempts failed**: neither used a portal at all — both
filled all 7 physical slots with plain colour items in a screen-order
sequence. The correct order is determined by graph topology (frame →
portal → frame, DFS), not left-to-right screen position, and is
structurally unreachable by "guess a screen-order permutation" regardless
of which permutation is tried.

**Verdict**: the original survey's "sb26 = nearest to existing family
logic, near-free pick" was wrong — it never looked past the top-level
reference/pool row into the mid-board slot structure, let alone the
portal graph underneath. A frame-only equivalent needs, at minimum: (1)
frame + slot detection as an entity distinct from reference/pool rows
(landed this round, reusable — `connected_components` in the mid-band,
excluding ref/pool colours, grouped by y-proximity into boxes/frames), (2)
portal-vs-plain-item disambiguation for pool pieces (no frame-only signal
found yet — may be genuinely invisible without internals, or may need a
probe-and-observe approach: place a candidate piece, see if it changes
traversal-visited slots elsewhere), (3) the true traversal-consumed target
order (no frame-only equivalent found for `game.wcfyiodrx`), (4) a
permutation/traversal solver over portal placements. This is comparable
to or harder than ar25's execute+arrange hybrid — **not** a small,
localized fix. Pivoted off sb26 this cycle; banked here so a future
session with more budget (or a cleverer frame-only portal-detection idea)
doesn't have to re-derive any of this from scratch.

**Guards**: no `src/` changes this cycle (mining + probing only). No
commit.

**Related**: [[../lessons/merge_drag_stall_causes_game_over_20260713]] —
another case this session where "records-first" legacy-mining revealed
the true mechanic only after live probing had already falsified the naive
model; same lesson, different game.

### ls20 build cycle: one real bug found and fixed (stale completion-colour override), but a deeper connectivity issue remains (2026-07-13 21:45)
Pivoted from sb26 per the portal-graph finding above. Legacy-mined
`strat_ls20_grid` (`agent_ensemble.py:3831`) first — confirmed it is fully
generic brute-force BFS (full reset-and-replay per candidate, frame-hash
dedup, zero game-internal reads, zero special mechanic knowledge). This
rules out an sb26-style hidden mechanic for ls20; it is a straightforward
maze.

**Root cause traced precisely**: `infer_goal` (`world_model_agent.py:453`)
prefers a colour remembered from a PAST level's completion
(`EffectModel.completion_target_colors()`) over the general rarest-colour
heuristic when picking the navigation goal. Measured live: L1 completed via
a colour-0 event, so on L2 the goal was force-set to `target_color=0` — but
L2's only colour-0 cluster is a 3px decorative speck, not a reachable goal.
The ORIGINAL initial-nav-attempt code (`world_model_agent.py:1289-1298`, pre-
fix) computed exactly ONE `plan_navigation` call with this forced target and,
on an empty result, fell straight through to `interact` WITHOUT ever
reaching `_execute_step`'s already-built multi-candidate rotation system
(`enumerate_goal_cells` / `_advance_goal` — infrastructure that already
existed for "a collection level with several plausible targets," see its own
docstrings, but was unreachable from the FIRST nav attempt because that
attempt never set `_phase = _PHASE_EXECUTE` on an empty plan).
`enumerate_goal_cells` carries NO target_color bias at all, so it was
already immune to this exact bug — it just needed to be reachable from the
first attempt, not only from a stuck-detection retry mid-plan.

**Fix landed** (`world_model_agent.py`, `_nav_attempted` block): enter
`_PHASE_EXECUTE` unconditionally whenever `goal.kind == "navigate"`, and let
`_execute_step`'s own `_plan_to_current_goal` / `_advance_goal` build the
first plan (trying every enumerated candidate in turn) instead of computing
one biased plan here and bailing to interact on failure. Verified this is
BEHAVIOR-PRESERVING for the working case (`plan_navigation`'s priority order
already has `goal_cell_override` win over `target_color` — confirmed by
reading the exact line, `goal_cell = goal_cell_override or
pick_goal_cell(..., target_color=goal.target_color)`). New regression test
`test_nav_attempt_recovers_via_goal_rotation_when_remembered_target_is_unreachable`
in `tests/test_world_model_agent.py` — a synthetic frame with a wall-colour
barrier isolates a "remembered" decoy goal from a genuinely reachable one;
confirmed the test FAILS on the pre-fix code (`phase == 'interact'` instead
of `'execute'`) and passes with the fix. 758 tests green, ruff clean.

**Honest result — the fix alone does NOT unlock L2.** Live smoke
(`score_efficiency.py --agent worldmodel --titles ls20 --max-actions 3000`)
post-fix: still `levels=1/7`, `actions=89` (was 88) — no L2 clear. Traced
further: even using the CORRECT floor-colour-aware walkability model
(`floor_colors_from_probes`, which the real `plan_navigation` already uses
internally — a first diagnostic pass mistakenly built a walkability grid
WITHOUT floor colours via a wrong attribute name and got a misleadingly
fragmented picture, corrected before drawing conclusions) L2's multi-room
maze structure still defeats BFS reachability for most/all of the 12
enumerated candidates in the traced run. This is a SEPARATE, deeper issue
from the completion-colour bug — not yet root-caused. Candidates for a
future session: (a) some "walls" in the learned model may actually be
openable doors/gates requiring an interaction first, which a static
walkability grid structurally cannot represent; (b) the floor-colour
learning (23 move-probes observed in the traced run) may need a longer
discovery budget on this specific multi-room layout to correctly classify
enough of the floor.

**Guards** (all confirmed exact/unchanged, live @2000-3000 actions):
su15 `2/9, 58 actions` ✅, s5i5 `1/8, 169 actions` ✅, re86 `2/8, 264
actions` ✅, wa30 `1/9, 100 actions` ✅ (unaffected — no code path overlap).
ls20 itself: `1/7, 88→89 actions` (structurally different code path, same
outcome — the +1 action reflects the extra rotation attempt before falling
back, not a regression). Suite 758/758 (was 757, +1 new test), ruff clean.

**Not committed** — reported per doctrine; landed source change is
`src/admorphiq/world_model_agent.py` (the `_nav_attempted` block) +
the new test, both verified as described above. *(Update: the
`_nav_attempted` fix + test were subsequently committed — 758 tests. See
the follow-up entry below for the final quick-try result and disposition.)*

### ls20 quick-try: discovery-budget bump FALSIFIED, banking with door/gate as the recovery lead (2026-07-13 22:05)
Per dispatch, tried the one authorized quick option before banking: bumped
`MOVE_PROBE_BUDGET` 16 → 40 (2.5x more per-level movement-discovery probes,
giving `floor_colors_from_probes` far more data to work with) and re-ran the
live smoke.

**Result: byte-identical to baseline.** `levels=1/7, actions=89` — the EXACT
same outcome as the un-bumped run, not even a partial improvement. Suite
stayed 758/758 green with the change in place. Reverted immediately
(confirmed via `git diff` showing zero remaining delta on the constant) — no
reason to keep a global tunable that measurably didn't help and costs
budget on every other game using this discovery path.

**Why this matters**: an *identical* result under 2.5x more probes is
stronger evidence than a merely "still failing" one — if the issue were
under-sampled floor colours, MORE probes should have found MORE floor and
changed the walkability grid enough to shift at least one candidate's
reachability, even if not enough to fully clear the level. Getting the
exact same numbers instead points AWAY from "insufficient discovery budget"
and TOWARD the other standing hypothesis: some cells the static
`frame_to_cells` model marks as permanent WALL are actually interactive
doors/gates that require an action to open, which no amount of passive
floor-colour sampling can discover — the walkable-vs-wall classification
would stay the same regardless of budget because openable doors render
identically to solid walls until acted on.

**Disposition**: banking ls20 here. `door/gate hypothesis` is now the
confirmed-by-elimination recovery lead for a future session (not probed
further this round, per dispatch — would need: detect a candidate
door/wall cell, try an interaction/movement-into-it action, re-check
walkability after, and see if previously-unreachable candidates open up).
The `_nav_attempted` stale-completion-colour fix from the entry above
remains landed and committed regardless of this outcome — it is an
independent, confirmed-real bug fix, not contingent on ls20 L2 clearing.

### 🚀 v7 VALIDATED: server score 1.6054, 23 levels / 25 envs (2026-07-13 21:05)
The 18/25 card's Kaggle validation: **1.6054** (v6: 1.0721, 19 levels) — the
perfect-efficiency wall clears (s5i5 19/20, re86 24/26+40/42, wa30 30/71, all
level score 1.0) lift the public-25 proxy ABOVE the top anchor (~1.56) and
well past M1 (1.21). Placeholder parquet present → submit preconditions ready.
CEREMONY (next session or 09:00 KST slot reset): `kaggle competitions submit
arc-prize-2026-arc-agi-3 -k jaehyukhyun/admorphiq-arc-agi-3-chained-llm-free
-v 7 -f submission.parquet -m "Admorphiq v2: +slider/transform/delivery
families, public-25 proxy 1.605"`. v6 (#54637991) hidden-set rerun still
PENDING — its publicScore remains the first transfer datapoint.

### Depth survey #2: ft09/tn36/tu93/cn04/lp85/r11l/vc33/sk48 — a bigger finding than any single blocker (2026-07-13 22:20)
Per dispatch: worldmodel @3000 for the WMA-family (ft09/tn36/tu93/lp85), `chained`
agent with `OLLAMA_HOST=127.0.0.1:1` (dead-LLM config) @3000 for the graph-family
(cn04/r11l/vc33/sk48), confirm banked L1 replicates, then L2 blocker
characterization. **The replication step itself is the headline finding this
round** — 4 of 8 games did NOT cleanly replicate, and the reason is architecturally
important, not per-game noise.

**Confirmed `target draw failed: HTTP 404` is a harmless, BY-DESIGN artifact** of
the dead-LLM config — `harness/loop.py:_maybe_draw_target`'s own docstring: "Offline-
safe: any failure/invalid draw means no injection (frame-only base kept)." r11l
cleared L1 (1/6) despite the identical 5x "target draw failed" spam other games
showed, proving it doesn't block anything. Do not mistake this log line for a bug
in future rounds.

**WMA-family (worldmodel agent) — replication + a GAME_OVER-CYCLING pattern found
in 3 of 4:**

| Game | L1 replicated? | L2 signature |
|---|---|---|
| ft09 | ✅ 1/6, 93 actions | `probe` phase stuck (avail=[6], click-only), 4x repeated `GAME_OVER` cycles before `is_done()`'s `POST_CLEAR_STALL` finally cuts it off |
| tn36 | ✅ 1/7, 110 actions | SAME shape: `probe` stuck, avail=[6], 4x `GAME_OVER` cycles |
| lp85 | ✅ 1/8, 311 actions | `probe` stuck, avail=[6], but NO `GAME_OVER` — just unproductive wandering to stall (the benign R1-survey shape) |
| tu93 | ❌ **0/9 in both the 3000-budget scoring run AND a 401-action extended trace** — never clears L1 at all | N/A — genuine non-replication, not a scoring artifact |

**The GAME_OVER-cycling pattern (ft09, tn36, and tu93's own repeated failure) is a
SCORING METHODOLOGY GAP, not just a game blocker.** `score_efficiency.py`'s scoring
loop (`if obs.state == GameState.GAME_OVER: if not restart_on_game_over: break` —
line ~290) BREAKS THE WHOLE EPISODE on the first `GAME_OVER` unless the adapter sets
`restart_on_game_over=True`, which `WorldModelAgent` does not. But
`WorldModelAgent.choose_action` itself ALREADY handles `GAME_OVER` internally (emits
`RESET` and continues) — so the REPORTED "0/9, 50 actions" for tu93 looks like an
instant crash, but an EXTENDED trace (bypassing `score_efficiency.py`'s early break,
calling `choose_action`/`env.step` directly in a loop) reveals the true behaviour:
tu93 cycles through the identical ~51-action failure pattern **seven times**
(`GAME_OVER` at steps 50, 101, 152, 203, 254, 305, 356) before the trace's own stall
detector cuts it off at step 401 — never once reaching level 1. ft09 and tn36 show
the same cycling shape but AFTER clearing L1, so `score_efficiency.py`'s scoring is
merely misleading there (undercounts the true action cost / attempt count), not
outright wrong about level completion. **Any future measurement of a `WorldModelAgent`
game that reports a suspiciously small action count with 0 or a low level count
should be re-checked with an extended trace before concluding "instant failure" —
it may be a cycling failure the standard scoring harness truncates at the first
data point.**

**Root architectural link**: this is the SAME "tried once per level, abandon to
[interact/probe] on failure, no recovery" pattern flagged in Depth Survey #1
(sb26/ls20/ar25) — but here it's measurably worse: on these 3 games the
unstructured fallback doesn't just waste budget, it actively walks the env into
`GAME_OVER` repeatedly. This raises the cross-cutting lever (flagged, not built,
in survey #1) from "efficiency/coverage improvement" to "this can turn an
otherwise-clearable level into a hard failure or a misleadingly-scored one."

**Chained-family (graph, dead-LLM) — 3 of 4 did NOT replicate their banked L1
clear under this exact protocol:**

| Game | L1 replicated? | Notes |
|---|---|---|
| r11l | ✅ 1/6 | Only one of four to replicate under dead-LLM; L2 not deeply characterized this round (time budget went to the replication-failure investigation above) |
| cn04 | ❌ 0/6, full 3000-action budget | `[graph] HASH-LADDER -> pool2` progress logged (state exploration active, not crashed) but never converts to a clear |
| vc33 | ❌ 0/7, full 3000-action budget | `[graph] REGION mask: 41 cells` found, no further progress logged before budget exhaustion |
| sk48 | ❌ 0/8, full 3000-action budget | `[graph] REGION mask: 309 cells` found, no further progress logged |

**Open question, not resolved this round**: whether cn04/vc33/sk48's banked L1
clears genuinely depend on a WORKING LLM (target-draw injection actually landing,
not just being attempted) that the dead-LLM protocol removes — which would mean
they are NOT "graph-family, no-LLM-needed" as assumed going into this survey — or
whether this is single-run non-determinism / a real regression unrelated to the
LLM. r11l replicating under the identical protocol argues against "the protocol
itself is broken," but doesn't rule out that these three specifically lean on the
LLM more than r11l does. Needs a follow-up: rerun one of the three (e.g. cn04) with
a REAL Ollama connection to see if it clears L1 with the LLM available, isolating
whether the dead-LLM config specifically is the cause.

**No pick for tonight's build cycle from this survey** — the two originally-
highest-priority games (tu93, vc33) both turned out to be non-replication cases
requiring further diagnosis before any build makes sense, and forcing a "nearest
to existing family logic" pick on a game that doesn't even confirm L1 would be
premature. Recommend: next session either (a) resolves the chained-family LLM
question first (cheap, one rerun with a real Ollama connection), or (b) picks up
the GAME_OVER-cycling architectural lever (a genuine fix, not a diagnosis — add a
cycling-detector to the unstructured interact/probe fallback that bails to
`is_done()` after N consecutive `GAME_OVER`s instead of blindly retrying the same
losing pattern, mirroring the `_MERGE_DRAG_STALL_LIMIT` precedent from earlier
today), whichever the next session has budget for.

**Guards untouched** — survey was read-only on code. No commit.

### GAME_OVER-cycling guard landed (2026-07-13 22:40)
Team-lead corrected four of this survey's "non-replications" with recorded
facts this session's context had lost — tu93's card clear is GRAPH-family
(unified's region mask, not WMA-alone: 0/9 was expected), cn04 is measured
LLM-DEPENDENT (dead-LLM 0/6 is the known result, not a regression), sk48
chain-fragile at 3000/8000 but clears via the 30k retry pass, and vc33's
no-LLM baseline was measured @8000 (this survey ran @3000, under-budgeted).
No protocol mystery, no LLM rerun needed. The genuinely NEW finding —
ft09/tn36's L2 GAME_OVER-cycling — got a fix this cycle.

**Fix**: `world_model_agent.py` — new `GAME_OVER_CYCLE_LIMIT = 3` (mirrors
the `_MERGE_DRAG_STALL_LIMIT` precedent from earlier today) + a per-level
`self._game_over_count` counter, incremented on every `GAME_OVER`, reset in
`_reset_level()` (so it tracks CONSECUTIVE same-level cycling, not a
lifetime total — a death on an already-cleared earlier level never counts
against a later one). `is_done()` now returns `True` once the count reaches
the limit, alongside the existing WIN / `POST_CLEAR_STALL` / `MAX_ACTIONS`
checks. Deliberately has NO `levels_completed >= 1` precondition (unlike
`POST_CLEAR_STALL`), so it also protects a level that never clears at all —
`POST_CLEAR_STALL` structurally cannot reach that case since its own
precondition never fires.

**A measurement nuance worth recording**: `score_efficiency.py`'s own
scoring loop ALSO breaks on the first `GAME_OVER` unless the adapter sets
`restart_on_game_over` (which `WorldModelAgent` does not) — so the standard
smoke tool cannot directly OBSERVE the cycling-prevention behaviour; it can
only confirm no regression to the existing baseline (which it did: ft09
1/6-93, tn36 1/7-110, lp85 1/8-311, all byte-identical to pre-fix). The
fix's real target is the CONTINUOUS-episode harness (the actual Kaggle-style
loop, where `GAME_OVER` -> `RESET` -> keep playing within the same
scored attempt, matching `WorldModelAgent.choose_action`'s own internal
handling) — this is exactly the scoring-methodology gap flagged earlier in
this survey (small action count + low level count on a `WorldModelAgent`
game should get an extended-trace recheck, not be read as "instant
failure"). Validated instead via two new unit tests that exercise
`is_done()`/`choose_action()` directly against a synthetic `GAME_OVER`
frame sequence — confirmed to fail via `ImportError` on the pre-fix code
(the constant didn't exist) and pass with the fix, via `git stash` both
ways.

**Guards** (all confirmed exact, live @2000-3000): su15 `2/9, 58` ✅, s5i5
`1/8, 169` ✅, re86 `2/8, 264` ✅, wa30 `1/9, 100` ✅, ft09 `1/6, 93` ✅, tn36
`1/7, 110` ✅, lp85 `1/8, 311` ✅ — all seven byte-identical to their pre-fix
baselines (fully expected: the standard scoring harness never reaches a
second `GAME_OVER` cycle within a single scored episode, so this fix cannot
change ANY of these numbers by construction — see the measurement nuance
above). Suite 760/760 (was 758, +2 new tests), ruff clean.

**Not committed** — reported per doctrine.

### v6 scorecard ANALYSIS — official scale + reset-waste data (2026-07-13 21:45)
Full per-game scorecard (user-provided from the kernel output) confirms:
(a) per-level cap = 115 OFFICIAL (our local 100-cap UNDERSTATES beat-the-human
clears — sb26 9a vs 18 human shows 115.0); (b) game score = level-weighted
mean on the 0-100+ scale, total = mean/25 (1.0721 ✓); (c) score concentration:
ar25 8.33 + su15 6.67 + ls20 3.57 + ft09 2.91 + sb26 2.78 + tn36 1.52 + tu93
0.78 ≈ 99% of the total — exhaustive-search clears (cd82 et al) are ~0 as
predicted; (d) RESET WASTE measured: tu93 893 resets, bp35 494, r11l 489,
sc25 315, sp80 287 — the GAME_OVER-cycling guard (in flight) targets exactly
this. PRIORITY ORDER from this data: (1) cycling guard → ft09/tn36 L2 retry,
(2) ar25 L3 (top scorer, hybrid cycle), (3) efficient-depth games first,
exhaustive-coverage games last.

### ar25 L3 build cycle: full root cause found, half the fix landed and verified safe, the other half not yet safe to land (2026-07-13 22:10)
Full live-instrumented investigation, several rounds of "trace → contradiction
→ re-trace" per doctrine. Corrects survey #1's framing entirely: **ar25 L3 is
NOT an execute+arrange hybrid gap** — it is a single-entity 2D navigation
level whose BFS planner is corrupted by one bad movement-discovery probe.

**Arrangement is exonerated.** Instrumented `_abandon_arrange` /
`learn_selection_modes` / `plan_descend_and_sweep` directly: on L3 the
primary entity (colour5) has FULL 4-directional movement within a SINGLE
selection mode (`mode_maps={0: {1:(0,-3), 2:(0,3), 3:(-3,0), 4:(3,0)}}` in
a clean session) — no mode-switching, no second entity needed. `horiz -
primary` (arrangement.py:365) correctly returns empty because there
genuinely is no separate alignment entity; `sweep_len=0` is the CORRECT
signal, not a bug. The ACTION7 hypothesis (untested probe action) was
tested live and falsified — zero movement across 4 attempts.

**The real defect, found via live instrumentation of `_execute_step`/
`_plan_to_current_goal` (offline reconstruction repeatedly gave
contradictory results — non-deterministic sessions genuinely differ, this
required several live re-traces to pin down, exactly matching the pattern
team-lead flagged: "offline state reconstruction is exactly the failure
mode that produces these contradictions"):**

The FIRST goal candidate tried (in one session, `(2,31)`) has a genuinely
valid 45-action BFS plan when `blocked_cells` is empty. The agent commits
and executes ONE step. The move's "did the player's grid cell change as
predicted" check (the blocked-move detector, `_execute_step`) fires
falsely, learning a SPURIOUS wall at `(31,16)`. That one cell turns out to
be a chokepoint — with it blocked, ALL 10 enumerated candidates return
empty plans (`plan_len=0` for every one, all sharing the identical
`blocked={(31,16)}`), collapsing straight to `arrange` (which, per above,
correctly finds nothing either) then `interact`.

**Why the false wall**: traced via raw per-probe shift instrumentation
(`_candidate_shifts` inside `infer_direction_map`,
`general_agent.py:247`). In the corrupted session, one action's recorded
shift was `(-2, -18)` — compare the OTHER three actions, cleanly
`(0,-3)/(0,3)/(3,0)`. This is not RE86's small-cross-axis-residual class
(`snap_to_axis`'s fix target) — BOTH components are large and wrong,
consistent with a probe whose before/after frame pair straddled something
other than a clean single-step move (animation/level-transition timing).
Two downstream consequences from this one bad reading:
1. `_step_cell_size` (`general_agent.py:411`, "smallest non-zero
   magnitude") picked up the outlier's `2` instead of the dominant `3` —
   `cell=2` instead of `cell=3` in the corrupted session.
2. `step_dirs()`'s `_unit()` (pure sign function) turns `(-2,-18)` into a
   DIAGONAL unit step `(-1,-1)` for that action, when the level only has
   cardinal movement — corrupting the BFS's understanding of what that
   action actually does, which is what makes the blocked-move detector
   misfire on execution (the agent expects a diagonal shift, the game
   delivers a cardinal one, mismatch reads as "wall").

**Fix landed (half)**: `_step_cell_size` changed from raw MINIMUM to MODE
(most common magnitude, ties toward the smaller value) — robust to exactly
one outlier reading, identical to the old behaviour whenever the data is
clean (which is every previously-passing case; there was no existing test
pinning the "minimum" choice, and no rationale in the docstring for why
minimum specifically was needed). **Empirically verified NOT sufficient
alone** — live ar25 re-run post-fix: still `2/8, 317 actions`, byte-
identical to baseline. This is expected given the analysis above: fixing
`cell` alone doesn't fix the corrupted `step_dirs()` entry for the bad
action, which is the actual trigger for the spurious wall during
EXECUTION, not merely during grid construction.

**Fix NOT landed (the other half)**: correcting the corrupted per-action
DIRECTION itself (not just the cell-size estimate) needs `infer_direction_map`
to reject or re-derive an outlier reading — e.g. cross-check a newly
recorded shift against the dominant magnitude/axis pattern already
established by OTHER actions before trusting it, or discard a reading
whose recorded axis-pattern doesn't match the level's established cardinal-
vs-diagonal signature. This is a genuinely bigger, riskier change to a
function used by EVERY WorldModelAgent game's movement discovery (not
scoped to ar25), and was NOT attempted this cycle given the depth of
verification a correct version would need and the approaching submission
timebox — landing an under-verified fix to a widely-shared function is a
worse outcome than banking a well-diagnosed, well-scoped gap.

**Guards (7-guard byte-check, all confirmed exact, live @2000-3000)**: su15
`2/9, 58` ✅, s5i5 `1/8, 169` ✅, re86 `2/8, 264` ✅, wa30 `1/9, 100` ✅, ft09
`1/6, 93` ✅, tn36 `1/7, 110` ✅, lp85 `1/8, 311` ✅ — the landed `_step_cell_size`
change is confirmed SAFE to keep (no regressions anywhere) even though it
does not by itself unlock ar25 L3. Suite 760/760, ruff clean.

**Not committed.** Recovery lead for next session: implement outlier-
rejection in `infer_direction_map`'s per-action shift recording (candidates:
cross-reference against the dominant established axis pattern; require N≥2
consistent readings before trusting a NEW action's direction; or detect an
implausibly-large magnitude relative to already-known actions and re-probe
instead of recording it). Verify with the SAME 7-guard set plus ar25 @8000,
since this touches the shared discovery path every WMA game depends on.

## Follow-up (2026-07-13, later same day): outlier-rejection landed, AR25 STILL blocked — real cause is a third, deeper defect

Implemented exactly the recovery lead above, as two fixes (commit `1dd5e1a`):

1. `WorldModelAgent.step_dirs()` — a quantised `(ucol, urow)` with BOTH
   components nonzero (non-cardinal) is now DROPPED rather than fed to
   `grid_bfs` as a diagonal edge. Every game in this repo is
   4-connected-cardinal only, so a diagonal quantisation is always a probe
   artefact, never a real mechanic.
2. `infer_direction_map` (`general_agent.py:247`) — readings for the SAME
   action id across multiple probes are now resolved by MAJORITY VOTE
   instead of last-write-wins. This is the "cross-reference against the
   dominant established pattern" lead above, generalised: rather than
   comparing a new reading against OTHER actions' directions, compare it
   against that SAME action's own reading history (simpler, and directly
   analogous to the `_step_cell_size` mode fix). 2 new unit tests
   (`test_step_dirs_drops_non_axis_aligned_probe_reading`,
   `test_infer_direction_map_outvotes_single_bad_reading_for_same_action`).

**Methodology correction — the earlier trace was against the WRONG env
hash.** `Arcade(OperationMode.NORMAL/OFFLINE).make("ar25")` (title lookup)
resolves to `environment_files/ar25/0c556536/ar25.py`. But
`scripts/score_efficiency.py` calls `OFFLINE.make(env.game_id)` where
`env.game_id` is the string `"ar25-0c556536"` from `get_environments()` —
and THAT call deterministically resolves to a DIFFERENT local file,
`environment_files/ar25/e3c63847/ar25.py` (confirmed reproducible across 3
repeated calls). These are genuinely different game versions (diffed —
different sprite names/data). **All prior AR25 L3 diagnosis in this file
was traced against 0c556536, a game version score_efficiency.py never
actually scores.** Lesson for future live-tracing: always call
`OFFLINE.make(env.game_id)` with the exact id string from
`get_environments()`, never `make(title)`, or the trace and the scored run
silently diverge. (Related: [[../lessons/api_hash_rotation_20260421]] — a
different mechanism, live API version rotation, but the same failure
shape: local dev tooling and the actual scored artifact drift apart
silently.)

**Re-traced against the TRUE scored hash (e3c63847) with both fixes live**:
`move_map[3]` at L3 now correctly recovers `(-3, 0)` (was the corrupted
`(-2, -18)` on this hash too — same defect class, independently confirmed
on a second game version). `step_dirs()` is fully cardinal:
`{1: (0,-1), 2: (0,1), 3: (-1,0), 4: (1,0), 7: (0,1)}`. `_blocked_cells`
never gets corrupted (stays `set()` throughout the L3 attempt). **Both
fixes work exactly as designed.**

**AR25 live score is unchanged: 2/8, 318 actions, byte-identical across 2
runs at the 8000-action budget.** Direction inference was never the actual
L3 blocker on this hash. Instrumented `grid_bfs`'s own inputs directly:

```
L1/L2: walkable.shape=(21,21) true_count=410/441  start_walkable=True
L3:    walkable.shape=(21,21) true_count=57-58/441 start_walkable=FALSE
```

At L3 the player's OWN current grid cell is marked unwalkable, and the
walkable set collapses from 93% of the board to ~13%. Every one of the 10
enumerated goal candidates is unreachable — not because of a learned wall,
not because of a bad direction, but because `frame_to_cells`'s floor-colour
classification (fed by `floor_colors_from_probes(model._move_probes, ...)`)
does not recognise L3's floor colour as walkable. `_move_probes` is
game-scope (never cleared on level-up, confirmed by reading
`_reset_level`'s docstring), so this isn't a stale-reset bug — it's that
NO probe has yet revealed L3's floor colour via a successful player-vacates-
a-cell observation, plausibly because the player hasn't moved yet this
level (chicken-and-egg: can't learn the floor by moving, can't plan a move
because the model thinks nowhere is walkable).

**This is a third, distinct defect from the (now-fixed) direction/cell-size
outlier class.** Banked (not fixed) this cycle — priority was verifying the
direction fixes honestly rather than opening a fourth investigation in one
sitting. Recovery lead for next AR25 L3 attempt: make `plan_navigation`
(or `frame_to_cells`) fail open when `start_walkable is False` — e.g. force
the player's own current cell walkable unconditionally (mirrors the
existing `walkable[goal_cell] = True` force already done for the goal
marker at `world_model_agent.py:581`), or detect an entirely-different
floor colour under the player at level start and seed it into `floor`
before the first BFS attempt rather than waiting for a probe to reveal it.

**Follow-up (same session, 2026-07-13 22:40): the "force start walkable"
half of the recovery lead is a DEAD END — implemented, then reverted after
proving it changes nothing.** Added the mirror of the goal-cell force
(`walkable[start] = True`) and re-ran the live L3 trace: `start_walkable`
correctly flips to `True`, but `plan_len` is STILL `0` for all 10 goal
candidates — completely unchanged. Root cause of the no-op, confirmed by
reading `grid_bfs` (`general_agent.py:510`): it seeds `visited={start}`
and the BFS queue with `start` unconditionally BEFORE any walkability
check — walkability is only ever tested on a cell being expanded INTO
(a neighbour), never on `start` itself, and `visited` guarantees `start`
is never re-examined as someone else's neighbour either. So
`walkable[start]`'s value is provably inert to `grid_bfs`'s output —
confirmed with a minimal repro (`grid_bfs` with `walkable[start]=False`
vs `=True` on an otherwise-identical grid returns the byte-identical
plan both times). Reverted the change and its test rather than keep
dead code (repo Implementation Discipline: no branches that don't affect
behaviour). **This means the true blocker is NOT "the start cell is
marked False" per se — it's that the surrounding cells the BFS would
need to expand THROUGH are ALSO misclassified** (only 57-59/441 cells
walkable at L3 vs 410/441 at L1/L2), so no path exists in the walkable
grid regardless of the start cell's own flag. The second half of the
recovery lead — seeding the floor colour from what's directly under the
player at level start, rather than waiting for a probe to reveal it via
`floor_colors_from_probes` — is therefore the ONLY remaining candidate
fix, not the start-cell force. Not attempted this session (bigger,
riskier change to a function every WMA game's navigation depends on;
needs its own careful verification pass, consistent with why the
direction-inference fixes earlier in this file were scoped narrowly and
verified before landing).

**Guards re-confirmed** (same 7-guard set, unchanged from the block above):
su15 `2/9, 58`, s5i5 `1/8, 169`, re86 `2/8, 264`, wa30 `1/9, 100`, ft09
`1/6, 93`, tn36 `1/7, 110`, lp85 `1/8, 311` — all exact. Suite 764/764
(was 760; +4 new tests), ruff clean. **Committed** as `1dd5e1a` — the two
direction-inference fixes are real, tested, verified-safe hardening even
though they don't move AR25's score; they close the exact gap this file's
prior section flagged as the recovery lead, and the same corrupted-reading
class was independently reproduced on BOTH ar25 hashes (0c556536 and
e3c63847), so they likely protect other games/other hash rotations even
where AR25 itself needed a further fix.

### AR25 L3 occupancy-invariant fix — landed, verified safe, moves plan discovery substantially but does NOT clear L3 (2026-07-13 22:52)

Implemented the floor-colour half of the recovery lead, guided by a
direct reading of `floor_colors_from_probes`'s own docstring: *"the
background is always implicitly floor and is excluded from the returned
set (callers add it separately)"*. Neither call site in the codebase
(`world_model_agent.plan_navigation`, `general_agent`'s internal nav
path) was actually adding it — a documented-contract violation, not a
speculative guess.

**First attempt (reverted): blind `| {bg}`.** Fixed AR25 outright —
`floor_colors={9,10,11}` (background + the two learned colours) gave
`walkable=441/441` on the L3 grid, up from 57-59/441. But it broke
**ls20 live**: `1/7, 89 actions` (baseline) → `0/7, 131 actions`
(regressed). This is the EXACT ls20-class failure `frame_to_cells`'s own
comment warns about — background is genuinely a WALL colour on some
boards once other floor is known, and blanket-including it inverts
walkability there. Confirmed by directly stashing/unstashing the change
and running both games back-to-back on the live env.

**Landed version: `_occupancy_floor_colors`** (`general_agent.py`).
Samples only the colour(s) touching the player's OWN footprint in the
CURRENT frame (4-connected neighbours of every player-occupied pixel,
excluding player cells themselves; returns the single most common
neighbour colour, not every colour touched, so straddling a wall corner
can't leak the wall colour in as a false floor signal). This is a
direct-observation invariant — the player is physically standing next to
these pixels right now — orthogonal to `floor_colors_from_probes`'s
vacate-based one, and it can never claim a colour the player isn't
actually touching, so it can't reproduce the ls20 regression: ls20's
player presumably isn't observed adjacent to its wall-classed background
the way AR25's is.

**Verification — full battery, twice**:
- Suite 764/764, ruff clean (both files).
- **ls20 live-reconfirmed unregressed**: `1/7, 89 actions`, byte-identical
  to baseline — the ls20-class case this fix could have broken is intact.
- **All 7 corroboration guards byte-identical**: su15 `2/9, 58`, s5i5
  `1/8, 169`, re86 `2/8, 264`, wa30 `1/9, 100`, ft09 `1/6, 93`, tn36
  `1/7, 110`, lp85 `1/8, 311`.
- **AR25 @8000 ×2 (determinism)**: `2/8, 326 actions` both runs —
  identical to each other, but NOT identical to the pre-fix baseline
  (`2/8, 318 actions`) — the fix genuinely changes behaviour, just not
  enough to clear a level.

**What actually changed, traced live**: pre-fix, EVERY one of the 10
enumerated goal candidates returned `plan_len=0` immediately (walkable
grid too sparse to route anywhere). Post-fix, MULTIPLE candidates now
get real, non-empty BFS plans (`plan_len=11`, `plan_len=20` observed) —
the walkable-grid connectivity is fixed. The agent commits to one, walks
part of it, and the corroboration-gated wall-learning from R-earlier this
session (`1dd5e1a`) correctly confirms TWO genuine walls
(`{(21,11),(20,10)}`) from real execution mismatches (not spurious single
readings — both required 2 consistent readings to commit, exactly as
designed). Execution now reaches step 117 before exhausting reachable
candidates, versus step 80 before. **Still 2/8** — the newly-reachable
candidates, once actually walked, run into real walls that make them
unreachable too, or the level genuinely needs a different goal / a
different navigation model entirely.

**Committed** as `c048d83` — real, safe, well-verified improvement to a
function every WorldModelAgent/GeneralAgent navigation game depends on.
Kept regardless of AR25's own outcome per the explicit call: guards +
suite green is sufficient to land an invariant that is correct on its own
terms.

**Live lead for the NEXT AR25 attempt, found but not yet chased this
session**: a standalone diagnostic (not the shipped fix — a separate
probe script) revealed that at L3, `model.player_color` (5) matches
THREE distinct on-screen components: a 63-pixel decorative bar spanning
the entire bottom row (`cy=63`, clearly a HUD/counter element, not a
character), plus two other blobs (56px at `(15.6,28.4)`, 48px at
`(50.5,29.0)`). All three pass the `_MAX_PLAYER_SIZE=64` filter, and
`plan_navigation`'s `player = max(player_comps, key=lambda c: c["size"])`
picks the LARGEST — the 63px HUD bar, not the true player. This means
`start` (the BFS origin) may be anchored to the wrong on-screen entity
entirely, which would explain why even a fully-open walkable grid still
fails to route to a meaningful destination: the "shortest path" computed
is shortest FROM THE HUD BAR'S POSITION, not from where the real
character is. Not chased this cycle (out of time-boxed scope for this
attempt, and disentangling "real player" from "same-coloured HUD
element" generically — e.g. by excluding components pinned to a board
edge, or requiring the player candidate to have shown responsiveness to
move-actions specifically — is its own scoped investigation). This is
the leading candidate for what the occupancy fix alone couldn't close.

### SU15 L3 tier-assignment CONFIRMED, general fix landed and safe, but a sub-pixel divergence still blocks the live clear (2026-07-13 22:57-23:08)

Corrected the su15 scope from the stale "enemy-downgrade" lead (see the
lesson-page correction, commit `6f01426`) to the ACTUAL leading candidate:
per-goal tier assignment via the top-band indicator blocks. Rather than
building indicator-reading logic first, tested the underlying hypothesis
directly and cheaply: drove the REAL `WorldModelAgent` end-to-end (so the
existing stall guard is live) and monkeypatched `merge_drag.detect_drag_layout`
to force delivery toward goal B instead of whatever it naturally picks.

**Result: L3 CLEARED in 21 total actions, reproducible twice.** This
confirms definitively — SU15 L3 was never a missing-capability problem
(no enemy-downgrade, no impossible geometry); `detect_drag_layout`'s
default single-largest-cluster goal pick is simply the WRONG one of the
two containers for this level, and the existing merge/gather logic
solves it cleanly once correctly targeted. Flagged to team-lead
immediately per standing instruction.

**General fix implemented** (commit `1e77d2c`), NOT hardcoded to "goal B":
1. `merge_drag.py`: `detect_drag_layout` / `next_drag_click` /
   `next_merge_click` gain an optional `goal_override` parameter — any
   caller-supplied goal instance (e.g. from `detect_goal_containers`)
   overrides the default largest-cluster pick.
2. `world_model_agent.py`: new `_try_next_merge_goal` retries the
   merge-drag phase against an untried goal instead of permanently
   falling through to `_interact_step` on probe failure, stall, or
   "gather complete without level-up" — wired into both abandon points
   in `_merge_drag_step`.
3. **Found and fixed a LATENT bug this exposed**: the existing
   `_MERGE_DRAG_STALL_LIMIT` guard (from
   [[../lessons/merge_drag_stall_causes_game_over_20260713]]) used
   `_last_changed` (full-frame equality) as its stall signal. SU15's
   board has a HUD/resource-counter region that changes on every click
   regardless of whether the tracked tile moved, so the guard's own
   trigger condition was silently never true in practice — the EXACT
   "dead click x5 → GAME_OVER" pattern that lesson diagnosed kept
   recurring THROUGH the supposedly-fixed guard. Replaced with
   `_merge_drag_tile_snapshot`: a rounded `(colour, size, cx, cy)` tuple
   set over `detect_drag_layout`'s own tiles, compared before/after each
   click — immune to unrelated HUD-region noise, exactly matching that
   lesson's own "Falsification signature" section, which had already
   named this precise failure mode as a caveat without it being applied
   to the actual guard implementation.

**Verified safe**: full suite 764/764, ruff clean, all 7 corroboration
guards unregressed (su15 `2/9, 59` [+1 action, same level count], s5i5
`1/8, 169`, re86 `2/8, 264`, wa30 `1/9, 100`, ft09 `1/6, 93`, tn36
`1/7, 110`, lp85 `1/8, 311`), ls20 live-reconfirmed unregressed
(`1/7, 89`).

**Honest gap — does NOT yet clear L3 through the standard live path.**
The retry mechanism correctly detects the default goal's probe failure
and switches to the SAME goal the monkeypatch proved works, but still
hits GAME_OVER. Root-caused via a click-by-click comparison between the
clean monkeypatch run and the real retry run: the first 12 clicks are
BYTE-IDENTICAL (both are merge-phase clicks combining same-colour tiles,
which don't consult `layout.goal` at all, so they're naturally
goal-independent). They diverge for the first time at click 13 — the
first GATHER-phase click, the first one that actually uses the goal
coordinate — by a single pixel: monkeypatch clicks `(47, 27)`, the real
retry clicks `(46, 26)`. This one-pixel difference compounds over
subsequent clicks (each click's target depends on the tile position
resulting from the PREVIOUS click, so any offset cascades) until the
retry run dead-clicks a stuck position `(21, 33)` three times running and
eventually GAME_OVERs, while the monkeypatch's unperturbed sequence
reaches the goal cleanly 6 clicks later. The most likely cause: the
monkeypatch captures `goal_b`'s coordinate ONCE, upfront, from a single
clean frame before any clicking begins; the real `_try_next_merge_goal`
re-detects the goal at the MOMENT of switching (mid-sequence, after the
merge phase has already run some clicks), and `detect_goal_containers`'s
centroid computation for the same physical container may differ by a
sub-pixel amount between those two moments (worth checking: does a goal
container's rendered centroid drift by <1px depending on animation
frame, or is this an off-by-one in the rounding either fix applies?).
Not chased further this cycle — landing the two real, generalizable
fixes now (per the standing "guards+suite green = commit" call) rather
than opening a fourth investigation layer in one sitting; the next
session's lead is precisely this coordinate-capture-timing question, not
a new hypothesis.

**Follow-up test of the leading candidate (2026-07-13 23:10) — NEGATIVE,
reverted.** Tested the "coordinate drift between capture moments"
hypothesis directly: captured every goal instance's centroid ONCE at
`_PHASE_MERGE_DRAG` entry (matching the monkeypatch's "once, upfront"
pattern exactly) into a new `_merge_drag_all_goals` list, and had
`_try_next_merge_goal` consume that frozen list instead of re-querying
`detect_goal_containers` at switch-time. Result: **zero measurable
change** — `su15 2/9, 59 actions`, byte-identical to the pre-change run.
Since the fix produced no observable behaviour difference at all (not
even a shifted action count), it is very likely inert for this specific
divergence, matching the earlier `walkable[start] = True` pattern in this
same file (a plausible-sounding invariant that turns out not to be what
`grid_bfs`/here the click sequence actually depends on). Reverted rather
than keep unproven code (suite reconfirmed 764/764 after revert). The
1-pixel click-13 divergence therefore has SOME OTHER cause, not simply
"which frame the goal centroid was read from" — possibly the retry path
issuing its OWN fresh probe click (`drag_probe_target`) that the
monkeypatch path never issues (monkeypatch forces the goal from click 1,
so its "probe" and its first real merge click may coincide; the retry
path's probe-then-switch sequence issues an actual extra environment step
even when `_last_changed` is credited). Next session should compare
action-by-action, not just click-target-by-click-target, to check for an
extra or missing step between the two paths.

### SU15 L3 CLEARS — reset-then-retry on goal switch, live, deterministic (2026-07-13 23:17)

Root cause of the 1-pixel divergence, finally settled: **the board is
disturbed, not the coordinate.** The live retry path tries the default
(wrong) goal first, drags tiles toward it for ~20 clicks until the stall
guard fires, and only THEN switches to the correct goal — gathering from
a board where tiles have already moved, not the pristine layout the
monkeypatch's forced-goal-B-from-click-1 test started from. Confirmed by
a direct tile-position dump at the exact moment of the goal switch: the
colour-15 tile sits at `(25.0, 44.0)` — nowhere near its phase-entry
position — by the time goal B becomes the target. No sub-pixel env
mystery; a fully accounted-for consequence of trying the wrong goal
first.

**Fix**: `_try_next_merge_goal` (`world_model_agent.py`) now issues
`GameAction.RESET` when switching to an untried goal, before ever
clicking toward it — so the new goal's gather sequence starts from the
level's pristine layout, matching the monkeypatch's advantage exactly. A
new `_merge_drag_reset_pending` flag tells the following `_merge_drag_step`
call to issue the new goal's probe click directly, skipping the
`_last_changed` check (which would otherwise read the credit for the
RESET action itself, not a real probe).

**Load-bearing assumption verified BEFORE landing, not after**: does a
DELIBERATE mid-level RESET (issued by the agent's own choice, not
triggered by `GameState.GAME_OVER`) behave the same as the
already-confirmed GAME_OVER→RESET case (preserves `levels_completed`,
restores the pristine current-level layout)? Dedicated probe: reached
L3, ran 5 merge clicks to disturb the board, issued a bare
`GameAction.RESET` mid-level (state was `NOT_FINISHED`, not
`GAME_OVER`), and confirmed — `levels_completed` stayed `2`, and the
resulting tile layout was BYTE-IDENTICAL to the L3 phase-entry snapshot.
This was flagged as an unverified assumption before the fix was even
written; verifying it first (rather than discovering a violated
assumption after landing something built on it) is exactly right for a
change to shared, every-game-touching nav code.

**Verified, full battery**: suite 764/764, ruff clean. SU15 via the
STANDARD `score_efficiency.py` path (not a monkeypatch or custom probe)
×3 for determinism, per merge-drag's known session-variance history —
all three runs byte-identical: `levels=3/9, actions=152,
game_score=0.0935` (previous baseline: `2/9, 58-59 actions`, roughly
`0.0667`). All 6 OTHER corroboration guards unchanged (s5i5 `1/8, 169`,
re86 `2/8, 264`, wa30 `1/9, 100`, ft09 `1/6, 93`, tn36 `1/7, 110`, lp85
`1/8, 311`), ls20 unregressed (`1/7, 89`).

**Committed** as `317d4b3`. This is the first new-level clear of the
session — SU15 is a 6.67%-weight game on the 25-game proxy, so this is a
genuine card improvement, not just a diagnostic win. The fix is fully
generic (any board with multiple goal-coloured regions benefits; no
game-id, no hardcoded colours or coordinates) and composes cleanly with
both earlier fixes in this thread (the `goal_override` plumbing from the
retry mechanism, and the tile-snapshot stall-detection fix that made the
retry trigger reliably in the first place).

**Open**: SU15 is now `3/9` — levels 4-9 remain unexplored under this
architecture. Worth a future round once other priorities clear.

### AR25 mobility-shape player selection — landed, verified safe, engages correctly, does NOT clear L3 (2026-07-13 23:22-23:26)

Implemented the standing AR25 lead from earlier in this file (the
player-color HUD-bar hijack): `select_player_component`
(`general_agent.py`) excludes any same-colour candidate whose bounding
box spans `>= 90%` of the board's width or height before falling back to
the largest remaining. First attempt used an EXACT "touches both
opposite edges" check and measurably failed to exclude the HUD bar — the
bar spans columns 0-62 of a 64-wide board (one pixel inset from the true
edge), so `max(cols) == w - 1` (62 == 63) was False. Switched to a
span-FRACTION threshold, which correctly catches the real-world inset;
confirmed via live trace that the BFS start position moved off the HUD
bar's grid cell for the first time.

**Verified safe**: suite 766/766 (+2 new tests), ruff clean, ls20
live-reconfirmed unregressed (`1/7, 89`) — this change's exact risk
class, given it touches shared player-identification logic every
WorldModelAgent/GeneralAgent game depends on. All 7 guards unchanged
(su15 `3/9, 152` — the new post-reset-retry baseline — s5i5 `1/8, 169`,
re86 `2/8, 264`, wa30 `1/9, 100`, ft09 `1/6, 93`, tn36 `1/7, 110`, lp85
`1/8, 311`).

**AR25 @8000 ×2**: `2/8, 326 actions` both runs — deterministic, level
count unchanged. But the fix demonstrably engages: L2's own action count
shifted from `37` to `45` (a different, still-successful navigation
path — confirms player selection changed somewhere in L2 too, not just
L3), and the live BFS-input trace confirms the start position moved off
the HUD bar for the first time. L3 still does not clear. Committed as
`41118e2` per the standing "guards+suite green = commit" call — this is
the third real, safe, verified AR25 fix this session (direction-inference
hardening, occupancy-invariant floor colour, now mobility-shape player
selection) that each individually moves the mechanism correctly without
yet compounding into an L3 clear. The remaining blocker is not yet
identified; each fix has closed exactly the gap it targeted.

### AR25 L3 fresh trace with all three fixes stacked — genuine progress, new structural lead (2026-07-13 23:27)

Re-traced L3 with direction-inference hardening + occupancy floor colour +
mobility-shape player selection all active together. The picture is
substantially better than any single-fix trace this session: multiple
goal candidates now get real non-zero BFS plans (`plan_len` 10, 12, 13
observed, vs universally 0 at the start of the session), 5 walls get
learned via the retry-corroboration mechanism (each required 2 matching
readings before commit — genuine walls, not spurious single-probe
artefacts), and execution reaches step 139 before exhausting every
candidate (up from step 80 at session start, step 117 after the floor-
colour fix alone).

**Still does not clear L3** — once all 10 enumerated goal candidates are
blocked by the 5 learned walls, the agent falls to `phase=arrange`. This
is a new, structurally different signal from anything measured earlier
this session: `arrange` is the multi-entity ARRANGEMENT phase (the same
one AR25's OWN L2 uses). One plausible reading: **AR25 L3 may need
arrangement-style multi-piece solving, not single-player point-to-point
navigation at all** — consistent with the 5 walls collectively blocking
every single-path candidate rather than any one wall being an isolated
false negative. Not investigated further this session (would need to
understand what `_arrange_enabled`/`_enter_arrange` actually do when
reached from this state, and whether they engage meaningfully or also
fail). Flagged as the next AR25 lead: check whether the arrange-phase
fallback is doing anything useful here, or is itself another dead end
needing its own fix.

### LS20 L2: door/gate hypothesis FALSIFIED directly; the true goal structure found precisely, fix not yet confirmed (2026-07-13 23:29-23:33)

Per dispatch (records-first: read the depth-survey, build-cycle, and
quick-try sections above, plus `games/LS20.md`), ran the ONE authorized
active probe the banked recovery lead called for: reach L2, identify wall
cells bordering the player's reachable region and an isolated region, and
test whether moving INTO one changes anything (a door opening) versus a
static wall.

**Door/gate hypothesis directly falsified.** `available_actions` at L2 is
`[1, 2, 3, 4]` only — movement, no distinct interact/click action exists
in this game at all, so a "bump a wall to open a door" mechanic requiring
a SEPARATE interaction action is structurally impossible here (there is
no such action). Confirmed live: navigated the player to `(7,3)`, adjacent
to the wall cell `(8,3)` (a candidate door — it borders BOTH the player's
57-cell reachable region and a 1-cell isolated region at `(9,3)`), then
issued the movement action toward `(8,3)` three times. Zero effect each
time: player stayed at `(7,3)`, and the raw pixels at `(8,3)`'s grid cell
were byte-identical before and after all three attempts. A genuine static
wall, not a door.

**Follow-up — the enumerated goal candidates are mostly false positives.**
`enumerate_goal_cells` returned 12 candidates (rarest-colour-cluster
heuristic); connectivity analysis of the walkable grid found the
player's own 57-cell region contains a walkable, one-tile disconnected
region (1 cell), and a second disconnected region (4 cells) — plus 5 of
the 12 candidates are ON wall-classified cells (unreachable regardless),
2 are in the isolated 4-cell region (unreachable), and 5 ARE in the
player's own reachable region. Walked the player to every reachable
candidate (`(9,10)`, `(8,6)` [= the player's own start position — almost
certainly a false positive from the heuristic], `(10,8)`, `(5,7)`, plus
an aborted attempt at `(3,3)`) — **none triggered `levels_completed` to
advance.** This confirms the generic rarest-colour heuristic is landing
on decorative clusters, not the true goal marker, and any budget spent
walking to them is wasted.

**The true goal structure, found and pixel-dumped precisely.** Raw pixels
around grid rows 7-10 / cols 2-4 (the same area as the falsified door
candidate) show a distinct, deliberate shape: a colour-3 (a LEARNED FLOOR
colour) rectangular FRAME/border, 9x9 raw pixels, surrounding a colour-5
(wall) interior, with colour-9 pixels forming a small marker pattern
inside (3 pixels in an L/cross arrangement). This is precisely the
"frame with hole" cross pattern the earlier depth-survey entry described
by eye without pixel-level confirmation. Because the frame is 9 raw
pixels wide/tall against a `cell=5` grid, it straddles TWO grid cells per
side — the coarse dominant-colour classification `frame_to_cells` uses
(≥75% of a 5x5 block) puts some of the frame's own floor-coloured border
cells on the WALL side of the boundary depending on exactly how the
interior's wall pixels split across grid cells. This is a genuine
grid-RESOLUTION artefact, not a door mechanic and not (only) a goal-
selection bug: the frame's outer ring IS floor-coloured and in principle
walkable, but the coarse grid can misclassify parts of it.

**Not yet confirmed — what exactly triggers completion.** Touching the
frame's TOP border (at `(7,3)`, during the door-bump test) did NOT
trigger a level-up, so simple proximity to the frame isn't the win
condition either; the true trigger may require the player to occupy a
SPECIFIC cell (adjacent to the colour-9 marker specifically, not any
point on the frame) or may require the isolated single-cell region
`(9,3)` itself to be reached (which — if it's genuinely part of the
frame's interior access point — the coarse grid may be wrongly marking
as both isolated AND inside a wall simultaneously). Ran out of the
bounded-probe budget for this cycle before pinning the exact trigger
down further.

**Disposition**: banking here, no code change landed this cycle (probe/
diagnosis only — read-only on `src/`, no commit needed there). Door/gate
is now CLOSED as a hypothesis (directly falsified, not just
circumstantially eliminated). The confirmed next-best lead: the
`enumerate_goal_cells` false-positive problem (decorative rare-colour
clusters being tried before the true frame-marker) combined with the
grid-resolution misclassification at the frame's boundary. A future
session should either (a) detect this specific "coloured frame around a
distinct interior marker" shape directly as a higher-priority goal
candidate than plain rarest-colour clusters, or (b) use a finer
sub-cell/edge-aware walkability model near frame-shaped structures
(similar in spirit to the existing `corridor_color_from_probes`/
`edge_grid_bfs` machinery built for TU93's interleaved-pitch maze class)
so the frame's own floor-coloured border is correctly walkable at
pixel-accurate resolution.

**Guards**: none touched, no `src/` changes this cycle.

### LS20 L2 frame: closed with GROUND TRUTH, not just the coarse grid — genuinely sealed, banking (2026-07-13 23:37)

Per dispatch: the earlier "can't physically enter" conclusion was drawn
from the coarse walkability grid, which was already proven unreliable at
this exact boundary — the live env, not the grid, is ground truth. Ran
the requested 4-side entry test.

**North side (the only grid-reachable approach): tested twice,
independently, both showing zero penetration.** Two different BFS
approach targets — `(6,3)` and `(8,2)` — both routed the player to the
SAME accessible cell, `(7,3)` (grid-adjacent to the frame's top border).
From there, 3 consecutive push attempts toward the frame interior each
time: player position never changed (`(7,3)` before and after every
attempt), across BOTH approach routes (6 total push attempts). One route
showed a small constant 4px frame delta per push (matching the su15-class
HUD/counter-noise pattern already documented this session — NOT player
movement) while the other showed zero delta; neither ever translated the
player.

**South/west/east sides: could not be tested — genuinely unreachable
from the player's connected region.** `grid_bfs` returns no plan at all
to any candidate cell near those three sides; this isn't "blocked when
tried," the player's 57-cell region has no path there whatsoever. Since
testing those sides "from the outside" requires already standing near
them, and testing "from the inside" requires already being inside the
sealed structure, there is no way to probe them further without first
solving the very reachability question being asked.

**Combined with the earlier pixel-level finding** — the raw frame
structure is a fully closed colour-3 ring on all four raw-pixel edges,
no gap — this is now closed with two independent lines of evidence
(live ground-truth movement AND raw pixel geometry), not one. **This is
a genuinely sealed decorative structure, not a mislabeled entrance.**
Banking here per the outcome-(b) disposition: door/gate closed, frame
question closed, no fix attempted (none would be evidence-based).

**Disposition**: `enumerate_goal_cells` still needs the frame-shape
detection lead from the prior entry for OTHER games with this same
"coloured frame + interior marker" pattern (it may be a decorative
tier/counter indicator rather than a goal at all, given it's provably
unenterable) — but LS20 L2 itself needs a different explanation for its
true win condition, not this structure. No `src/` changes this cycle
either.

### FT09 L2: GAME_OVER-cycle-limit fix implemented, then PROVEN INERT and reverted — the real mechanism is a pre-existing, unrelated handoff (2026-07-13 23:39-23:47)

Per dispatch: WorldModelAgent instrumented trace of FT09 L2 (survey #2's
own characterization: `probe` phase stuck, `avail=[6]`, repeated
`GAME_OVER` cycles). Live trace confirmed 4 GAME_OVER cycles at steps
93/154/200/256 before termination at step 306, matching the survey.

**Hypothesis (plausible, wrong): the `dc89aa5` GAME_OVER-cycle-limit
fix (landed earlier tonight, before this session) unconditionally
terminates the WHOLE episode via `is_done()` once
`_game_over_count >= GAME_OVER_CYCLE_LIMIT` (3) — with no
`levels_completed >= 1` precondition. That commit's own docstring notes
`score_efficiency.py`'s scorer already breaks on the FIRST GAME_OVER for
this agent, so the guard is invisible to every dev-time guard check
regardless of correctness — it specifically targets the continuous-
episode (Kaggle) harness.** Reasoned that 3 cycles (~150-180 actions for
FT09) fires well before `NO_PROGRESS_FALLBACK` (650 actions), so under
the continuous harness the guard could pre-empt `_activate_fallback()`
— documented as the actual solving mechanism for FT09/TN36 (GeneralAgent's
GF(2) toggle/paint primitives) — from ever engaging.

**Implemented**: changed the GAME_OVER-cycle-limit path to hand off to
`_activate_fallback()` directly (instead of `is_done()` ending the
episode), with `is_done()`'s own cycle check exempted once the fallback
is active. Updated the affected unit test to match. Suite 766/766, ruff
clean.

**PROVEN INERT before shipping — reverted.** Added debug instrumentation
(`agent._fallback is not None` at every GAME_OVER) to the SAME live
trace and discovered `fallback_active=True` from the very FIRST logged
cycle (step 93) — meaning `GeneralAgent`'s fallback was ALREADY active
well before any GAME_OVER cycling could occur. Confirmed the fix changed
NOTHING by re-running the identical trace with the fix `git stash`ed:
byte-identical output (same 4 GAME_OVER steps, same termination at step
306) with or without the fix in place.

**Root cause of the misdiagnosis, found**: a THIRD, pre-existing
`_activate_fallback()` call site (`world_model_agent.py:1516-1519`,
predating this session) already hands off to `GeneralAgent` IMMEDIATELY
once movement discovery finds `model.player_color is None` — i.e. the
instant a click-only/no-player game like FT09 is recognised as such,
BEFORE any structured click probing or GAME_OVER cycling ever happens
under `WorldModelAgent`'s own phases. This is a deliberate, already-
correct design (its own comment: "the world model has no nav plan here
and its blind click interaction is BOTH ineffective AND can trip a
lose-state before any action-count stall is ever detected... hand off
NOW"). So the GAME_OVER cycles observed at steps 93/154/200/256 are
`GeneralAgent`'s OWN cycles during its OWN exploration of FT09 L2, not
`WorldModelAgent`'s structured-loop cycling — a completely different
code path (`general_agent.py`) than the one the `GAME_OVER_CYCLE_LIMIT`
fix touches. My fix was solving a problem that does not exist for this
game; reverted cleanly (`git checkout`, confirmed 766/766 green after).

**What this means for FT09 L2 (the actual open question)**: the real
blocker is inside `GeneralAgent`'s own click-probing/toggle-solving
pipeline repeatedly walking FT09's L2 board into `GAME_OVER` without
ever finding the correct GF(2) toggle sequence — a `general_agent.py`
investigation, not a `world_model_agent.py` one. Not investigated this
cycle (ran out of time budget after the misdiagnosis chase). The
`GAME_OVER_CYCLE_LIMIT` fix MAY still be valid/useful for the games its
original commit measured (tu93/bp35/r11l — all under the `chained`/
graph-frontier agent architecture, not `WorldModelAgent`'s click-only
handoff path), which this investigation did not touch or invalidate.

**Lesson for next session**: "click-tier gate" as referenced by dispatch
is `tools/graph_search.py`/the `chained` agent's mechanism — a DIFFERENT
architecture than `WorldModelAgent`, which is what this entire session's
guards (`su15`/`s5i5`/`re86`/`wa30`/`ft09`/`tn36`/`lp85`/`ls20`) and
fixes have exclusively touched. Before investigating "ft09 L2" again,
first confirm which agent architecture is actually deployed/relevant for
that specific game — this session's own `ft09 1/6@93` guard number comes
from `--agent worldmodel`, separate from the `chained`-agent tier-gate
work described earlier in this same file (`Gap-1 @8000... ft09 closed`).

### FT09 L2 in the DEPLOYED chained agent: chaining policy confirmed correct, graph stack tries and doesn't converge — likely a genuine capability gap, not a bounded bug (2026-07-13 23:49-23:56)

Resolved the architecture question directly rather than searching stale
archives: no local `scripts/rounds/` directory has a `chained`-agent FT09
result (all found `games/ft09.json` files are the OLD `graph_frontier`
standalone runs, `1/6, 6325 actions`, RFINAL2-era — exactly the trap the
dispatch warned about). Ran the ACTUAL deployed agent directly instead:
`score_efficiency.py --agent chained --titles ft09 --max-actions 8000`.

**Chaining policy CONFIRMED CORRECT — no defect.** `ChainedAgent` (WMA
probe first → unified handover, `chained_agent.py`) explicitly sets
`restart_on_game_over = True` at the wrapper level (its own comment:
"the runner ends the game on the first GAME_OVER unless the agent opts
into restarts... the chain must opt in for BOTH phases"). Live log
confirms: `pick=graph ... feedback='cleared level 1'` at the very first
harness step — WMA's efficient L1 clear banked, handover to the
unified/graph stack happens immediately and correctly. The GAME_OVER-
cycling misdiagnosis from the earlier FT09 entry tonight (proven inert,
reverted) was ENTIRELY about bare `WorldModelAgent`, which does NOT set
`restart_on_game_over` — irrelevant to this deployed path.

**The unified/graph stack DOES get its full shot at L2 and does NOT
converge within the 8000-action budget.** Log shows real, escalating
exploration: `[graph] REGION mask: 66 cells` then
`[graph] HASH-LADDER -> pool2 ... aliased=1` then
`[graph] HASH-LADDER -> object ... aliased=3` — the hash-ladder's
own instability-escalation mechanism fired twice, moving from raw pixel
hashing through 2x2 pooling to object-level state hashing, exactly as
designed when a signature proves unstable. Final result: `levels=1/6,
actions=8000` (the full budget spent, all on L2, no further clear).

**Historical corroboration this is a standing capability gap, not new**:
this file's OWN earlier entries (`Gap-1 @8000 pinned + R38 tier gate
ported — ft09 closed`, 2026-07-09) record the tier-gate's contribution
as `ft09 0 → 1` — i.e. even the R38 tier-gate's dedicated, purpose-built
improvement for FT09 only ever got the graph-exploration approach from
0 to 1 LEVEL. No configuration measured in this file's history has ever
cleared FT09 L2 via graph/frontier exploration. FT09/TN36's win
condition is a lights-out/GF(2) toggle puzzle (per the STALE-but-
mechanically-accurate `games/FT09.md` page); the legacy BRITTLE solver
that once cleared 6/6 did so via genuine linear-algebra solving over the
puzzle's constraint structure, not frontier-BFS/hash-ladder exploration.

**Assessment, not a fix**: did not attempt a code change this cycle.
Ran out of the "one bounded trace, fix only the measured defect" scope —
what's measured here isn't a narrow, fixable bug (like the su15
disturbed-board or the merge-drag stall-detection issues fixed earlier
tonight); it's that the current EXPLORATION-based approach to click
puzzles has no mechanism analogous to GF(2)/lights-out linear-algebra
solving, and REGION-mask + hash-ladder escalation — while real,
correctly-firing machinery — isn't a substitute for that. A genuine fix
here is a feature build (a frame-only lights-out/toggle-constraint
solver reachable from the graph stack), not a bounded diagnosis-and-
patch. Flagging for a prioritization call rather than guessing at a
narrow patch this late in a long session.

**No `src/` changes this cycle.**

### TN36 L2 corroborates FT09 exactly — same chaining-correct, graph-doesn't-converge shape (2026-07-13 23:54)

Per dispatch ("tn36 L2 next after ft09"), ran the same direct check:
`score_efficiency.py --agent chained --titles tn36 --max-actions 8000`.

**Identical shape to FT09**: `pick=graph ... feedback='cleared level 1'`
at step 0 (chaining correct, WMA's L1 clear banked, immediate handover);
`[graph] REGION mask: 50 cells` fires (real exploration engaging); no
hash-ladder escalation this time (TN36's instability never crossed the
threshold that triggered FT09's pool2/object rungs — a difference in
degree, not in kind). Final: `levels=1/7, actions=8000` — full budget
spent on L2, no clear.

**This corroborates the FT09 assessment across two independent games,
not one.** TN36 is documented elsewhere in this wiki as a bit-encoding
puzzle (`concepts/bit_encoding.md`), a different surface mechanic from
FT09's lights-out/GF(2) toggle grid, but the SAME shape: a constraint-
satisfaction puzzle that graph/frontier exploration can search but not
solve within a bounded action budget, because there is no domain solver
(linear algebra / constraint propagation) in the current tool stack —
only state-space discovery. Two-for-two strengthens the "genuine
capability gap, not a per-game bounded bug" read from the FT09 entry
above.

**No `src/` changes.** Consolidated recommendation for the next
prioritization decision: if FT09/TN36-class L2+ depth is worth pursuing,
it needs a genuine feature build — a frame-only constraint/bit-pattern
solver reachable from the graph/unified stack (the closest existing
precedent is the legacy brittle `lights_out`'s GF(2) linear-algebra
approach, which this repo's Phase 8 direction has been migrating away
from toward frame-only generalization, not toward reintroducing game-
specific solvers) — not another bounded-trace-and-patch cycle on either
game.

### FT09 L2 in GeneralAgent's OWN click-probe pipeline: root cause found precisely, real fix landed, doesn't clear L2 — the gap is candidate GENERATION not recovery (2026-07-13 23:56–00:05)

Corrected course per dispatch: the assigned investigation was
`WorldModelAgent`/`GeneralAgent`'s OWN toggle-solve pipeline (where the
GF(2) lineage — R16/R17 `_gf2_solve`/toggle-stencil — already lives, and
which produced FT09's efficient L1 clear), not the graph/chained stack.
Instrumented `general_agent.py`'s pattern-toggle state directly (not
just phase transitions) across the full L2 attempt.

**Precise mechanism, confirmed step-by-step**:
- Steps 56-88: MEASURE sub-phase runs CLEANLY, zero deaths — probes 18
  candidate cells, confirms 13 real toggle buttons via local-flip
  detection, undoing each (self-inverse) to keep the base state intact.
- Step 88: transitions to SOLVE with a fully-built candidate list.
- Step 93 (~5 actions into SOLVE): the FIRST candidate flip-set's
  execution is LETHAL — `GameState.GAME_OVER` fires mid-delta-chain.
- **Root cause of what happens next**: `GeneralAgent.choose_action`'s
  GAME_OVER branch (`if _state_name(latest_frame) == "GAME_OVER"...:
  return self._emit(GameAction.RESET)`) touched NOTHING of
  `_pat_delta`/`_pat_applied`/`_pat_cand_k`. RESET restores the level's
  PRISTINE layout (confirmed elsewhere this session — deliberate RESET
  behaviour), but the interrupted candidate's bookkeeping survived
  unchanged, so the NEXT call resumed assuming cells were already
  toggled that the real (now-pristine) board had never touched — a
  state desync corrupting every subsequent click. The unrelated
  `_PATTERN_BAIL_LIMIT` timer then eventually wiped the ENTIRE toggle
  attempt (all 13 measured buttons, the whole candidate list) to
  `_PHASE_EXPLORE`, where the remaining 3 GAME_OVER cycles this session
  already traced happen in undirected, unstructured exploration.

**Fix landed** (`53f6469`): GAME_OVER during the toggle SOLVE sub-phase
now advances to the NEXT candidate flip-set with `_pat_applied`/
`_pat_delta` reset cleanly, instead of resuming with stale bookkeeping
or letting the bail-timer discard the measured stencil. 1 new unit test
pins the exact scenario. Verified safe: suite 767/767, ruff clean, all
7 guards + ls20 byte-identical (this scope is inside GeneralAgent's
fallback recovery, narrower than any guard's coverage — none of the
guard games hit this exact toggle-solve-death path).

**Live-verified the fix's actual mechanism with a second, finer-grained
trace — it works exactly as designed, but doesn't unlock L2.**
`_pat_cand_k` correctly advances `0 → 1` with `_pat_applied`/`_pat_delta`
reset on the death. But `_pat_delta` immediately came back EMPTY —
because **FT09's candidate list only ever had ONE entry total**: no
indicator-based flip-sets fired (`indicator_flip_sets` found nothing),
and the GF(2) homogeneity solve (`plan_toggle`/`build_stencil`) either
deduplicated against the "flip every cell" candidate or produced nothing
distinct. With `len(candidates) == 1`, advancing past index 0 has
nowhere to go — `_toggle_solve_step`'s own pre-existing exhaustion check
fires immediately after (`self._pat_cand_k >= len(self._pat_candidates)`)
and falls to explore just 2 actions later than before.

**Honest conclusion, narrowed precisely**: the fix is real, correct,
and would recover ANY game where a lethal EARLY candidate is followed
by a genuinely DIFFERENT untried one in the measured stencil — a real,
generically-useful hardening, landed regardless of FT09's own outcome
(same "verified-safe, keep it" call as several other fixes tonight).
FT09 L2's remaining gap is NOT in recovery-from-death; it is that
**the single hypothesis the pipeline generates ("flip every measured
button to make the board uniform") is the wrong target**, and there is
no fallback hypothesis to try instead. This is now a genuinely narrower,
better-scoped question than "why does FT09 L2 cycle GAME_OVER": either
(a) `indicator_flip_sets` should be firing but isn't (worth checking
whether FT09 L2's board actually has indicator sprites this heuristic
should detect), or (b) the win condition isn't simple homogeneity at
all, and a different target-inference is needed. Both are real next
leads, neither chased further this session — this closes the assigned
investigation with a precise, falsifiable, evidence-backed answer
rather than a guess.

**One further cheap read narrows lead (a) precisely, without
implementing anything.** `indicator_flip_sets`'s own docstring
(`primitives/pattern_match.py:205`) names its calibration case
explicitly: *"ft09: an 8-cell ring around one clue"*. The function
computes exactly ONE central indicator position — `cix`/`ciy`, the
AVERAGE centroid of every toggle cell — then partitions cells by the
marker colour found near that single point. L2 has **13** confirmed
toggle buttons (not a clean single 8-cell ring), and the earlier pristine-
board dump this session found the 13 colour-9 blocks arranged with 2
"missing" grid positions occupied by small unrelated colour-0/colour-2
clusters — a layout shape that doesn't obviously match "one ring around
one central clue." **Working hypothesis, not yet confirmed**: L2 may
have a DIFFERENT indicator topology than the single-ring case this
function was built for (e.g. a larger grid, an off-center indicator, or
multiple indicator points), and averaging all 13 cells into one centroid
would misplace the marker-lookup point for such a layout, correctly
explaining an empty `indicator_flip_sets([])` result. A genuine fix (if
confirmed) is a real, scoped feature addition — generalising the single-
centroid marker lookup to detect and handle a non-ring indicator
topology — not a one-line patch; NOT attempted this session, flagged as
the most promising concrete next step for whoever picks this up.

### WA30 L2: render-lag settle-frame bug found and fixed (real, precedented), L2 still open — patrol-actor lead now testable in isolation (2026-07-13 00:08–00:20)

Records-first check of the three WMA-family leads (re86 L3 multi-
placement, wa30 L2 patrol actor, s5i5 L2 reveal-matching) picked wa30 as
most likely to hide a bounded defect under its "patrol actor" framing —
re86's wall was already PROVEN geometrically impossible, s5i5 needs a
whole new matching-puzzle solver; wa30's delivery family already exists
and its patrol pattern is fully deterministic (measured earlier: "3
right, 1 up, pause, 5 left").

**Live trace found something upstream of the actor question entirely.**
Comparing the FIRST live `detect_delivery_puzzle` call's frame against a
freshly-reached, fully-settled L2 pristine board (both via direct pixel-
histogram diff): 288 pixels differ. Item-ring pixel count 36 vs the
settled 60; the level's own moving actor (colour 12, confirmed 16px)
entirely ABSENT (0px) from the live call's histogram. The FIRST
detection call returns only **3 items**, not the true **5** — under-
detection, not failure. This is the exact same render-lag/settle-frame
class already measured and fixed for RE86/transform_route earlier
tonight (`_transform_settle_tried`), simply not yet applied to the
delivery family.

**Fix landed** (`a3b9c3c` + test `74fa233`): one settle press (ACTION5)
before the FIRST delivery-detection attempt on any level reached via a
transition, bounded via a new `_delivery_settle_tried` flag — same shape
as the transform precedent. One measured difference from transform's
exact preconditions: transform gates on `spent == 0`, but live tracing
showed an EARLIER probe-phase check already consumes one action before
delivery's gate is ever reached on the level's first pass (`spent=1` at
the point delivery detection actually runs, confirmed via a temporary
debug print) — so the `spent == 0` copy of transform's condition NEVER
held true and the fix had ZERO observable effect until this was caught
and corrected (relying on the block's own pre-existing `not
self._delivery_attempted` one-shot gate instead, which is sufficient and
correct without an action-count precondition).

**Verified safe, does not clear L2.** Suite 768/768, ruff clean, all 7
guards + ls20 byte-identical (WA30's own guard number, unavoidably, since
`score_efficiency.py`'s scorer breaks the whole episode on the FIRST
GAME_OVER for this agent — the same observability gap already documented
for FT09/TN36 tonight). Live-traced the fix's actual mechanism: the
settle press correctly delays the delivery gate by one call (confirmed
via a timing shift, 32→33), but the delivery phase now runs even SHORTER
before bailing to interact (4 actions vs 11 before the fix) — item-count
detection is no longer the confounding variable, but SOMETHING else
still causes an early bail. Landed anyway per the standing "verified-
safe, real measured defect, keep it" call: this render-lag class is
real, independently corroborated (exact match to RE86's precedent), and
worth having even though it alone doesn't solve WA30 L2.

**Disposition**: banked. Now that item-count under-detection is
eliminated as a confound, the ORIGINAL "patrol actor interferes with the
open-loop delivery queue" hypothesis from the earlier banked lead is
finally testable in ISOLATION — was not re-tested this cycle (time
budget exhausted). Next session: trace whether the actor's live position
during Stage-1 queue-draining (open-loop, no re-verification against the
live board per action — confirmed by reading `_delivery_step`'s own
Stage 1 code) coincides with the shortened bail point.

### FT09 L2 indicator topology CONFIRMED via live trace — falsifies the "generalise the centroid" lead; real mechanic is 2 glyph clues with unknown decoding on a lethal board (2026-07-14 01:05–01:25)

Records-first: this page's 2026-07-13 00:05 ft09 section flagged the *working
hypothesis* that L2 has a non-ring indicator topology and that generalising
`indicator_flip_sets`' single-centroid marker lookup is "the most promising
concrete next step." Doctrine mandates a live trace before implementing. One
bounded instrumented capture of `GeneralAgent._begin_toggle_solve`'s inputs on
L2 (base layer + the measured toggle cells) plus an ASCII map of the region
CONFIRMS the topology and FALSIFIES the simple version of the lead.

**Measured L2 layout.** The 13 toggle buttons form a 3×5 grid: x∈{22,30,38},
y∈{16,24,32,40,48}, pitch 8, each an 8×8 colour-9 block on a colour-4 field.
Two center-column positions — (30,24) and (30,40) — are NOT buttons; they are
the "gaps," and each holds a discrete 6×6 GLYPH sprite built from colours 0/2/12
(colour 12 central in both, colours 0/2 forming distinct surrounding patterns —
the two glyphs differ from each other). The single centroid `indicator_flip_sets`
computes is (30,32) — dead center — which lands ON the central toggle button
(colour 9); every one of the 13 cells therefore reads the same marker (9) at
`off=2`, so there is no 2-marker split and the function correctly returns `[]`.

**Why "generalise the centroid to a grid" does NOT fit.** The ring-case
mechanic reads a per-cell marker from ONE central clue — each ring cell looks
inward and sees a 2-valued marker. L2 has NO per-cell marker: the buttons are
uniform colour-9 and the only clue signal is 2 separate glyph sprites whose
mapping to a 13-button target flip-set is an UNKNOWN code (a 6×6 colour-0/2/12
glyph does not obviously encode a 3×5 flip pattern). A centroid generalisation
(multiple centroids / nearest-clue marker reads) would still find no clean
per-cell marker field to partition on.

**Why implementing anyway would be speculative, not generic.** The only way to
verify a candidate flip-set on FT09 is to EXECUTE it, and a wrong flip is LETHAL
(`GameState.GAME_OVER` mid-delta-chain, already measured this session; RESET
restores pristine). Generating guessed partitions from the glyph sprites and
trying them is brute-force guessing on a lethal, move-limited board — it has no
principled reason to hit the right target, it is RHAE-hostile, and it is exactly
the "speculative safety net" doctrine forbids. So this is banked, NOT implemented.

**Disposition.** Feature-scale with UNKNOWN decoding — the real next step is a
dedicated research round to decode how the 2 glyph clues (colours 0/2/12 at the
center-column gaps) specify the target button configuration, which is a genuine
game-mechanic reverse-engineering problem, not a generalisation of the existing
per-cell-marker primitive. The record's earlier "generalise the single centroid"
framing is superseded by this confirmed measurement. Guard ft09 1/6@93 unchanged
(no code touched).

### s5i5 L2 matching-rule characterised via controlled probe — permutation puzzle, feature-scale confirmed, thread STOPPED (2026-07-14 00:50–01:05)

Records-first (this page's 2026-07-13 16:05 s5i5 L2 bank) already scoped L2 as
a reveal into a 4-pair matching puzzle needing its own round. Guard reconfirmed
byte-identical this session (s5i5 1/8@169 — the delivery fix does not touch the
slider path). Added value: ONE bounded controlled-probe trace (drive WMA to L2
at ac=19, then click each button component once, log the diff) to characterise
the MATCHING RULE so the future dedicated round is implementation-ready.

Measured L2 board: colour 5 is the revealed canvas (3421px); colour 15 = two
canvas blocks at (43,29.5) 90px and (40.5,13.5) 117px; button-pair interiors
10/11/12/14 (~20px each, 3 components apiece). The buttons sit mostly in a
BOTTOM ROW at y=57 (7px each) plus a few legend-area cells at y≈37-40. Clicking
a bottom-row button produces a CASCADING multi-colour diff (measured: 36px, 19px,
49px, 10-11px changing colours 5/3/10/11/12/14 together) — i.e. one click
PERMUTES/CYCLES several coloured tiles at once, not a single toggle. Clicking the
legend-area cells (y≈37-40) is inert (diff 0-1px), so those are the reference
pattern, not controls. The glyph legend (rows 36-41) + the two colour-15 canvas
blocks are the presumed target arrangement.

Verdict: FEATURE-SCALE confirmed — a matching/permutation solver family (learn
the per-button permutation from probes → search a click sequence that maps the
button row onto the legend/canvas target). Not a bounded defect; NOT attempted.
Thread stopped per the queue's "bank verbatim and stop" instruction. Next
dedicated round starts from this characterisation.

### WA30 L2: patrol-actor CORRUPTS motion calibration (measured, fixed) — delivery now reaches 4/5 items; last-item stuck is the new isolated lead (2026-07-14 00:24–00:50)

Records-first (this round page's prior WA30 section + git log) said the
settle-frame fix (`a3b9c3c`) eliminated item under-detection but delivery
now bailed at 4 actions, and the banked next step was "trace whether the
patrol actor's live position during Stage-1 queue-draining coincides with
the shortened bail point." One bounded instrumented LIVE trace through
`score_efficiency.py` (never `arcade.make` — the offline-hash trap) found
the actor interferes UPSTREAM of queue-draining, at motion CALIBRATION.

**Measured root cause (live, colour-decomposed).** On L1 (distractor-free)
calibration cleanly derives `dir_map {1:(0,-4),2:(0,4),3:(-4,0),4:(4,0)}`,
`step_size=4`, player colours `{0,14}`, body 14. On L2 the same
`_delivery_step` Stage-0a calibration produced garbage
`dir_map {1:(2,0),3:(0,9),4:(-1,0)}`, `step_size=1`, body 12 — then judged
every one of the 5 items unreachable and bailed to interact at ac=36,
wandering to GAME_OVER. Decomposing each L2 calibration diff by colour:
the diff contains THREE independent movers — the player (colour 14 +
accent 0, near x≈13) AND a 16-cell patrol actor (colour 12, ≈(35,35),
pattern right/up/PAUSE/left) AND a 12-cell indicator (colour 5, ≈(37,29)).
`detect_mover_by_motion` unions every non-item changed cell into ONE
centroid, so the average of three clusters moving different directions is
the meaningless delta. The player is stably colour 14 on both levels
(object permanence).

**Fix landed (`a43f952`, generic).** Player identity is game-scope: the
colour set learned on the first distractor-free level
(`_delivery_known_player_colors`, placed in `__init__` next to
`_transform_prev_puzzle_key` so it survives `_reset_level` — the initial
attempt WRONGLY put it inside `_reset_level`, so it was cleared every
level-up and the L2 seed stayed None; caught by re-running the trace and
seeing L2 still derive `{0,12,14}`) is reused on later levels as a new
`include_colors` hint to `detect_mover_by_motion`, restricting its scan to
the player's own colours. Verified against the measured centroids: L2 now
calibrates identically to L1 (`step_size=4`, body 14) and delivers 4 of 5
items (was 0). Suite 769 (+1 distractor-isolation pin), ruff clean, all 8
WMA guards byte-identical (wa30 still 1/9@100, deterministic ×2).

**New isolated lead — last-item stuck + move-limit GAME_OVER (feature-scale,
banked).** With calibration fixed, the L2 GAME_OVER trace shows the delivery
delivers items 0–3 methodically (items_rem drops to `[4]` by ac=87), then
the player FREEZES at cell (13,25.5) from ac=87 through ac=100 while carrying
the last item — its open-loop directional moves no longer change its position
(blocked, most likely by the 4 already-delivered items now walling the target
zone; `bfs_path` blocks only the REMAINING items, not delivered ones or the
target occupants). GAME_OVER fires at exactly ac=100 (a move limit; L1 cleared
at 30, L2 entered at 32). So the proximate killer is the open-loop delivery not
detecting a blocked/no-op move and re-planning the same stuck route until the
budget expires. Fix direction (next cycle): closed-loop delivery — after a
queued move, verify the player actually shifted; on a no-op, treat the delivered
items + target occupants as obstacles and replan, or abandon that leg. This is a
new capability (blocked-move detection + dynamic obstacle set), NOT a one-line
defect, so it is banked here rather than attempted this cycle.

## Related
- [[../lessons/api_hash_rotation_20260421]]
