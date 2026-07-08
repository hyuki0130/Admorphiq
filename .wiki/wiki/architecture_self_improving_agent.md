---
title: Self-improving tool-orchestrating agent (north-star architecture, 2026-07-08)
type: architecture
keywords: [self-improving, llm-orchestrator, tool-library, graph-frontier, cnn-rl, executable-world-model, repl, hidden-state, original-contribution, qwen3.6-27b]
date: 2026-07-08
description: The mission architecture — an LLM orchestrator that, per unseen game, selects/applies/EDITS a library of our own strong algorithms (graph, CNN-RL, world-model), diagnoses failures, rewrites the code/models, and learns while solving. Beats M1 winners by combining strong priors with full LLM agency over the code.
---

# Self-improving tool-orchestrating agent (north-star)

> Per unseen game, an offline LLM (Qwen 3.6-27B, 96GB) SELECTS and APPLIES a library of our
> own improvable algorithms (graph-frontier, CNN-RL, executable world model, segmentation,
> de-aliasing), OBSERVES failures, EDITS the tool code / retunes the models, and LEARNS while
> solving — a closed apply→diagnose→improve loop. Not a copy of any M1 winner; our original
> contribution. Goal: 25/25 generic clears.

## Why this beats the published SOTA (original contribution)

- **Tufa "Duck" (M1 1st, 1.21%)** = LLM writes Python from scratch in a REPL with MINIMAL
  tools ("hand-crafted tools HURT — they hinder the model's creativity"). Powerful but starts
  cold on every mechanic.
- **StochasticGoose (preview 1st)** = pure CNN-RL, no LLM orchestration.
- **Ours** = LLM orchestrates a LIBRARY of strong primitives it can READ, CALL, AND REWRITE.
  This resolves Tufa's tools-hurt finding: their failure was RIGID/opaque tools that CONSTRAIN
  the model. We expose tools as EDITABLE source in the REPL — the model keeps the driver's seat
  (Tufa's principle) while standing on strong priors instead of cold-starting. Nobody published
  "LLM improves a library of strong algorithms per game."

## Division of labor (user-directed, load-bearing)

The weak runtime model CANNOT invent strong algorithms from a cold start — so the capable
DEV-TIME model (Claude) must FIRST build the foundation by actually understanding and solving
games:

- **Claude (dev-time, high-capability) BUILDS THE TOOLS.** Claude plays/studies each game,
  solves it, and from that understanding develops GENERIC algorithms/functions/models (trigger
  on frame features, never game ids) as the reusable library. The strength of the runtime agent
  is bounded by the strength of this library; a weak local LLM orchestrating weak tools solves
  nothing.
- **Local LLM (Qwen 3.6-27B, runtime) ORCHESTRATES + ADAPTS the tools.** It selects which tool
  fits the observed mechanics, applies it, diagnoses failure, and tunes/edits — but it stands on
  Claude's strong generic primitives, it does not invent them.

Implication for THIS effort: the immediate work is Claude hands-on developing generic,
game-solving tools (understand a game → generic mechanism that clears its class → add to the
library, verified by actually clearing it), NOT just orchestration scaffolding.

## The three layers (why the wiki exists)

A complete harness is BRAIN + HANDS + KNOWLEDGE:

- **LLM = brain**: reasoning + orchestration (which tool, diagnose, adapt).
- **Tools (Claude-built, generic) = hands + memory**: the strong algorithms that actually act.
- **Wiki = knowledge**: for EACH tool, the observable frame signature that says "use this
  FIRST", how to call it, the falsification signature ("it's failing → switch"), and the
  next-best tool. This is the whole point of the `.wiki/` LLM-Wiki (Karpathy pattern): a weak
  local model cannot deduce which algorithm fits from a cold start, so the wiki must map
  observable signals → the right tool so the FIRST pick is correct within the tight budget.

The lever for coverage: MAXIMIZE the number of generic algorithms in the library, EACH with a
crisp "when to use" entry in the tool-selector wiki. First-tool-selection accuracy is bounded by
how precisely the wiki maps game signatures → tools. See [[tool_selector]].

## Multi-agent self-improving loop — TWO REGIMES (load-bearing distinction)

The self-improving multi-agent loop is IDEAL at dev-time and CONSTRAINED at runtime; conflating
them produces an unrealizable Kaggle design.

- **DEV-TIME (Claude, now) — full multi-agent.** An orchestrator (Claude) inspects a game,
  dispatches the applicable per-tool BUILDER agents IN PARALLEL (graph-agent, CNN-RL-agent,
  world-model-agent, paint-agent, …); each runs its algorithm on the game, reports feedback;
  the orchestrator forms an improvement plan; each tool-agent edits its own code and re-runs;
  loop until the tool clears the game class generically. This is how the strong, generic tool
  library gets BUILT (realizable now via the Agent/Workflow tools).
- **KAGGLE-RUNTIME (Qwen 3.6-27B, offline) — single brain + parallel TOOL EXECUTION.** One GPU,
  no internet, no second LLM. "Parallel" here = running multiple applicable TOOL CODES
  concurrently (cheap) and having the SINGLE Qwen read their feedback, pick/compose/retune, and
  edit code Tufa-REPL-style. NOT multiple LLM agents. The wiki ([[tool_selector]]) makes Qwen's
  first pick accurate so few tools need running.

Same tool library + wiki feed both regimes; only the orchestrator differs (Claude-multi-agent
dev-time → Qwen-single-brain runtime).

## Components

1. **Tool library (`src/admorphiq/**`, our developed + improvable primitives)** — each exposed
   to the LLM as readable/editable Python, not an opaque black box:
   - graph-frontier BFS (region-masked state hashing, tiered clicks) — the 18/25 depth engine
   - CNN-RL online learner (StochasticGoose-style, test-time) — for reactive/steering games
   - executable world model (LLM-synthesized `predict_next_frame` + goal planning) — R49-R53
   - hidden-state DE-ALIASING state hash (US-11) — the novel primitive no M1 winner has
   - dead-signature / action priors (US-12), segmentation, goal inference
2. **LLM orchestrator (Qwen 3.6-27B, offline)** — per game: reason about which tool(s) fit the
   observed mechanics; apply; read the failure envelope (levels=0, plateau, frame-aliasing,
   fit<gate); then EDIT the tool's parameters or CODE, or compose tools, and retry.
3. **Closed self-improvement loop** (per unseen game, within the action/time budget):
   `perceive → select tool → apply → observe outcome → diagnose failure → modify code/model →
   improve → retry`, carrying a world-model note + reflection memory across turns.
4. **Sandbox** — the ewm.core restricted REPL, widened to expose the tool sources + game state
   as Python variables (Tufa-style), so the model's edits execute safely.

## Non-negotiables (from prior user directives + measurement discipline)

- **Generic only**: no game ids/titles anywhere; every tool triggers on frame observations.
- **Original, not copied**: M1 winners / Duck are BASELINES to beat (attributed, in `baselines/`),
  never shipped as ours ([[lessons/top_solutions_survey_20260708]]).
- **Measured honestly**: full-25, transfer-honest; ship a change only if it beats both our graph
  baseline AND a reproduced-Duck reference; verdict recorded even if null.
- **Metric reality**: leaderboard top ~1.56%, M1 winner 1.21%, us ~0.20% (×100 of our harness
  fraction) — closeable. Depth+efficiency+coverage all count (squared-efficiency RHAE).

## Build order (each a measured PRD story)

- Tools first, each generic + default-OFF + measured: US-11 de-aliasing (novel), US-12
  dead-signature (done), CNN-RL online tool, world-model tool (R49-R53, done).
- Then the orchestrator: LLM REPL that can call + edit the tools, with per-game diagnose→improve.
- Then measure the whole vs baselines; iterate toward 25/25.

**Related**: [[lessons/top_solutions_survey_20260708]] (baselines to beat + metric), [[rounds/r52_ewm-integration]],
[[rounds/r36_graph-frontier-bfs]] (graph tool).
