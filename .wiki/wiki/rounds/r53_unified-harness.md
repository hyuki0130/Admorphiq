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

## Related

- [[r52_ewm-integration]] — the EWM runtime hook this generalizes into a tool.
- [[r36_graph-frontier-bfs]] — the graph core re-authored here as `graph`.
- [[index]]
