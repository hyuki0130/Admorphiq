---
type: reasoning
round: R55
axis: code-repl-agent
keywords: [code-repl, duck, qwen3.6, multimodal, transcript-replay, segmentation-tracker, turn-packet, python-sandbox, inspection-api, action-governor, offline-core, controller-persistence]
verdict: building (Round 1 offline core — LLM-free, unit-tested)
commit: pending
date: 2026-07-14
description: R55 builds the offline-testable core of the Duck-style multimodal code-REPL agent per the Codex design consultation — transcript/replay, segmenter+tracker, turn-packet builder, stateless Python sandbox + inspection API, and action governor. All LLM-free and unit-tested (sub-second); the model wiring + Kaggle vLLM bundle is Round 1's second half on Kaggle infra. The R54 vlm_policy JSON-policy arm becomes the Round-2 2x2 ablation's JSON-policy leg.
---

# R55 — Duck-style code-REPL agent (offline core, Round 1)

> A multimodal coding model with a stateless Python REPL and free internal
> computation infers an environment-specific controller that amortizes its
> discovery cost across a game's compositional later levels. This round builds
> the LLM-free, deterministic core so Kaggle iterations are scientific.

## Design source (binding)

`docs/r55_codex_design_consultation_20260714.md` — the Codex consultation that
selected architecture **(b) Duck-style multimodal code-REPL** (+ a narrow
learned-controller reuse), over pure JSON policy (a), discover-then-solver (c),
and baseline-first fallback (d). Key rationale: the REPL gives the model free
internal computation (inspect transitions, test geometric hypotheses, build an
explicit controller) WITHOUT spending environment actions, and reuse happens at
the facts / options / controller-code levels — never exact trace replay.
Complexity has a real tax (forge/Tufa: extra machinery hurt), so Round 1 is
minimal with no elaborate reflection. Related: [[lb_top_team_research_20260714]],
[[r54_vision-llm-policy]] (the JSON-policy arm for the Round-2 2×2 ablation),
[[r53_unified-harness]].

Package: `src/admorphiq/repl_agent/` (generic, no game ids, purely additive —
the deployed guards are untouched). Each module lands with sub-second unit tests
and its own commit.

## Module 1 — Transcript / replay (built)

`src/admorphiq/repl_agent/transcript.py`. Built FIRST per the design doc: the
foundation that makes one-hour Kaggle iterations scientific by separating harness
regressions from model variance.

- `TurnRecord` — one decision boundary's full I/O as a JSONL row: prompt text +
  image hash, raw model output, parsed tool calls, sandbox stdout/errors, action
  taken, frame before/after (+ hashes, grids nullable for lean transcripts),
  board_changed/level_completed/game_over, memory before/after, latency, tokens.
  Lossless JSON round-trip; `from_json` ignores unknown fields (forward-compat).
- `TranscriptRecorder` — append-only JSONL writer (or in-memory when path=None).
- `TranscriptReplayer` — re-runs a recorded transcript with NO model: re-parses
  each recorded `raw_output` via an injected `parse_fn` and re-derives the
  governor decision via an injected `govern_fn`, comparing both to the recorded
  values. A mismatch is localized to the exact turn + field
  (`parsed_tool_calls` / `action`) so parser and governor regressions surface
  independently. The injected callables keep this module dependency-free of the
  later parser/governor modules.

7 unit tests (round-trip, forward-compat, recorder JSONL, replay pass, parser-
regression detect, governor-regression detect), 0.02s, ruff clean.

## Module 2 — Segmenter + tracker (built)

`src/admorphiq/repl_agent/segmentation.py`, built on the repo's generic
`tools/base.connected_components` (reused, not rewritten; `FrameAnalyzer` stays
the complementary action-semantics analyzer).

- `SceneTracker.update(frame) -> Scene` — segments the grid and tracks objects
  with STABLE ids across updates. Primary match key = translation-invariant
  `shape_hash` + colour (a moved object keeps its id); remaining objects matched
  by cell overlap, surfacing recolor (1:1, colour changed), split (1 prev : many
  curr) and merge (many prev : 1 curr). Unmatched current = appeared, unmatched
  previous = disappeared. Emits a CHANGE event list per turn.
- `SceneObject` — id, colour, cells, bbox, centroid, area, `shape_hash`, hole
  count (enclosed-background flood-fill), boundary contact, `contained_by`
  (smallest strictly-enclosing different-colour object), `adjacent`
  ({id, direction, gap}), compact `change_history`, and one VERIFIED interior
  `safe_click` (the on-object cell with the most on-object neighbors — never a
  hole).

8 unit tests (shape-hash translation invariance, stable id across move, recolor
keeps id, split event + new ids, appear/disappear, holes + safe-click, containment,
adjacency direction), 0.79s, ruff clean.

## Module 3 — Turn-packet builder (built)

`src/admorphiq/repl_agent/turn_packet.py`. Assembles the per-turn prompt in the
GAME / LAST_ACTION / CHANGE / SCENE / RECENT_EVENTS / MEMORY YAML shape,
optimized around CHANGES (the full grid stays in the sandbox, not the prompt).

- `TurnPacketBuilder.build(...)` — composes the six sections from the tracked
  `Scene` (+ prev scene, + frame diff via `tools/base.diff_bbox/diff_cells`).
  Deterministic (`yaml.safe_dump(sort_keys=False)`, integer-rounded centroids →
  snapshot-stable) with a token-budget cap that trims the largest section
  (SCENE.objects, smallest-area first) and flags `_meta.truncated`.
- `HistoryTiers` — three-tier history: recent full-transition window (4-8) +
  compact event ledger (20-40); persistent memory is separate.
- `EnvironmentMemory` — goal_hypotheses / action_semantics / invariants /
  dead_interventions / learned_options / unresolved_questions / current_plan;
  surfaces the most-confident non-rejected hypotheses.
- `Hypothesis` — falsifiable {hypothesis, prediction, confidence, supporting,
  contradicting, status}. `support` raises confidence (→ confirmed); `contradict`
  LOWERS it and rejects on sustained contradiction — the contradiction-recovery
  behavior that stops false theories from entrenching.

8 unit tests (six sections, CHANGE reports move + diff bbox, YAML snapshot
stability, token-budget object trimming, history compaction, hypothesis
contradiction recovery, rejected-hypothesis hiding, token estimate), 0.50s, ruff
clean.

## Pending modules (Round 1)

- **M4** — stateless Python sandbox (subprocess, stdlib allowlist, bounded
  output, timeout) + inspection API (objects/crop/ascii/mask/compare/relations)
  + explicit action accounting.
- **M5** — action governor (legal-action enforcement, repeated state-action
  prevention, macro gating with per-step precondition+invariant + stop-on-
  surprise, MOUSE(row,col) convention, undo accounting).

Round 1's second half (Qwen 3.6 FP8 vLLM deployment, latency at 8/12/16
concurrency, one paired public-25 vs ChainedAgent) runs on Kaggle infra.

## Related
- [[r54_vision-llm-policy]] — the JSON-policy arm (Round-2 ablation leg).
- [[lb_top_team_research_20260714]] — the M1 top-team evidence.
- [[r53_unified-harness]] — the current harness; existing generic tools.
- [[index]]
