---
type: lesson
date: 2026-07-14
keywords: [duck, tufa, qwen3.6-27b, code-repl, teardown, fact-extraction, context-eviction, segmentation, world-model-note, weaknesses, design-deltas, reference-only]
description: Measured fact-extraction of the Duck (Tufa, M1 #1) harness — REPL/context/image numbers, exposed variable schema, helper inventory, and their own named weaknesses — with our repl_agent design deltas. Reference-only; provenance-cited.
---

# Duck harness teardown — measured facts + our design deltas (2026-07-14)

> The Duck (Tufa, M1 #1, 1.21%) is a Qwen 3.6 27B FP8 code-REPL agent: the game is
> exposed as Python variables, the model iterates reason→tool→act in a per-toolcall
> REPL, an image + ASCII + segmentation feed perception, and the context is kept
> playable forever by evicting the oldest turns. This page extracts the MEASURED
> facts (with provenance) and our attack surface. REFERENCE-ONLY per
> the reference-only standing rule (memory `feedback-no-copying-winners`) — we BEAT it, never copy it.

## Provenance (sources)

- **Submission wrapper notebook** (infra only; the solver is an attached dataset,
  NOT in the file): session copy `scratchpad/duck_nb/tufa-labs-duck-harness-june-30-milestone-winner.ipynb`,
  17 cells. Cited as `NB:cell N`.
- **Author write-up** (design prose): `.wiki/raw/duck_writeup_discussion_717133_20260714.txt`
  (Kaggle discussion 717133). Cited as `WU:line`.
- ⚠️ Limitation: the deep solver internals (exact prompt text, REPL variable
  implementation, segmentation code) live in the bundled `taaf` dataset
  (`jeroencottaar/taaf-kaggle-source-share`, `NB:cell 6`) which is NOT present —
  so items below are code-verified only for the wrapper; the design items are the
  authors' own prose description, not read from source.

## 1. Measured numbers

| Fact | Value | Provenance |
|---|---|---|
| Base model | Qwen 3.6 27B FP8, served via vLLM | WU:60,74,138; NB:cell 6 dataset refs (`…vllm-h100-wheelhouse…`, `…qwen3-6-27b-fp8…`) |
| Hardware target | RTX Pro 6000 96GB, 9h, 110 games | WU:72 |
| REPL execution timeout | **30 seconds** per toolcall | WU:101 |
| REPL max output | **4096 characters** | WU:101 |
| REPL statefulness | **reset between every toolcall** (stateless) | WU:101 |
| Max context | **64k tokens** | WU:121 |
| Target input context | **~32k tokens**, maintained by evicting oldest user msg + following assistant turns | WU:121 |
| System prompt | always fully retained (never evicted) | WU:121 |
| Image | **4× upscaled** board, injected at the **start of every turn**, latest frame only | WU:132-133 |
| Image encoder | Qwen processes 16×16 pixel patches (upscale chosen to align) | WU:133 |
| Animation | none — only the latest frame (they tried more frames/video; small models fail) → sb26/tn36 suffer | WU:133 |
| Passes | `n_passes = 1` | NB:cell 14 |
| Level reset semantics | `ONLY_RESET_LEVELS=true` (RESET keeps the level) | NB:cell 2 |
| Soft deadline (non-submission) | stop ~`min(600s, budget/2)` before wall budget for graceful exit | NB:cell 14 |
| Gateway wait | poll up to 600s for the competition gateway | NB:cell 14 |
| Eval protocol | 25 public games × **20 tries each** | WU:138 |
| Public-train score | mean **1.6002 ± 0.4475** | WU:139 |
| Leaderboard | **1.21%** official (initially 1.30, retracted; as low as **0.77**; std up to 0.4) | WU:64 |
| Prefix caching | acknowledged NOT optimally used on vLLM | WU:121 |

## 2. Structures (described, not quoted)

- **Exposed REPL variable schema** (WU:107-113): `current_frame` (with `.ascii`,
  `.segmentation`, current level, step), `previous_frame`, `history` (pairs
  `.action` + `.frame`), `transitions` (state-action-state list), a per-action
  `result` object (previous-action count, current level, reward, state, valid
  actions), and the convenience latest values `last_transition`, `last_action`,
  `last_action_result`. Actions offered via `valid_actions`; an `action()`
  function executes one OR many actions (enables loops / object tracking).
- **Action vocabulary** (WU:113): natural names UP / DOWN / LEFT / RIGHT / SPACE /
  MOUSE / RESET. **UNDO is deliberately withheld** — the model undoes large
  batches and wastes actions.
- **World-model note** (WU:115-117): a free-text note carried across turns via a
  `World model:`-style tag; the model copies it into the next user message until
  it chooses to overwrite. Not structured, not falsifiable — a mental scratchpad.
- **Context construction** (WU:119-129): full system prompt always; each assistant
  turn = reasoning + one python toolcall; executing actions appends a new user
  message with updated state (level transitions, valid actions, reset flag).
  Eviction is oldest-user-message-first (plus its following assistant turns) once
  >32k. The per-turn user message REPEATS game state + valid actions + a python-
  tool reminder + the world-model instructions + a "collect evidence before
  acting" reminder.
- **System-prompt topics** (WU:123-125, topic list only): game setup; possible
  actions; the goal (complete as many levels as possible, action-efficiently);
  the REPL environment + every variable + usage recommendations; multimodal usage
  (how to read the scene, that a time bar EXISTS and that minimizing it is NOT the
  goal); the python-tool interface. Many ARC-3-general (not game-specific) hints.
- **Segmentation tool** (WU:135): locates **4-connected components in pixel
  space**, with adjacency AND **parent-child** relationships between nodes.

## 3. Helper inventory (what "hand-crafted tools hurt" referred to)

The model-facing tools are intentionally MINIMAL: the python REPL tool, the
`action()` function, an image (4× upscale/turn), the ASCII grid (`.ascii`), the
segmentation tool (4-connected components + adjacency + parent-child), and the
world-model note mechanism. The authors state that hand-crafting MORE specific
tools did NOT help — it "hinders the creative abilities of the model" (WU:147).
So the winning recipe is: expose rich VARIABLES + a general code tool, not a
library of bespoke solvers. Their biggest gains came from **better base models +
multimodality**, not tools (WU:147).

## 4. Weaknesses / their own future-work (our attack surface)

- **Context management is crude** — oldest-first eviction; the authors explicitly
  want **compaction or curated cross-turn memory** (WU:121,151).
- **Perception gap** — coding models reason over ABSTRACT DESCRIPTIONS, not ASCII
  crops; "transmitting abstract visual information in a useful format is a big
  challenge"; segmentation is only "a first step" (WU:151).
- **No animation feedback** — latest-frame-only breaks animation-dependent games
  (sb26, tn36) (WU:133).
- **Free-text world model** — no prediction, no confidence, no contradiction
  tracking; a plausible early story can persist unchallenged (WU:117).
- **Prompt-only discipline** — heavy prompt tuning needed to stop the model
  treating the energy bar as the goal, inventing nonsensical goals, hallucinating
  Atari/robot sprites, and dumping whole boards (diluting attention) (WU:149).
  Nothing ENFORCES action discipline; UNDO had to be removed entirely (WU:113).
- **REPL not isolated** — arbitrary code execution acknowledged (WU:105).
- **Unablated + high variance** — "not scrutinized and ablated"; same submission
  scored 0.77–1.30 (WU:64,147).
- **Prefix caching not optimized** on vLLM (WU:121).

## 5. OUR DESIGN DELTAS

| Axis | Duck | our `repl_agent` (R55) | Improvement opportunity |
|---|---|---|---|
| Perception | ASCII + 4× image + per-frame 4-conn segmentation (adjacency, parent-child) | segmentation-first turn packet with **stable object IDs across frames** + split/merge/appear/disappear events + containment/adjacency + holes + verified safe_click ([[r55_code-repl-agent]] M2) | add abstract-description perception (their named gap); our cross-frame tracking already exceeds their per-frame segmentation |
| Memory | free-text `World model:` note, overwrite-only | **falsifiable-hypothesis** memory {hypothesis, prediction, confidence, supporting, contradicting, status} + contradiction recovery + structured invariants/dead-interventions/options (M3) | directly implements their "curated memory" future-work; ours DOWNGRADES false theories they entrench |
| Context mgmt | oldest-first eviction, 64k cap / 32k target | **3-tier history** (recent window / event ledger / persistent memory) + token-budgeted turn packet trimming largest section (M3) | event-triggered compaction (their ask) already designed; consider matching their 64k/32k envelope for the growing-chat variant |
| Governance | none — prompt-steering only; drop UNDO | **ActionGovernor**: legal enforcement, repeated state-action prevention, macro gating (per-step precondition+invariant, stop-on-surprise), undo accounting (M5) | we ENFORCE mechanically what they beg the prompt to do → fewer wasted actions, structural not hopeful |
| Replay / iteration | GitHub context viewer; no deterministic replay | **TranscriptReplayer** re-parses + re-governs with no model, localizing harness-vs-model regressions (M1) | enables scientific 1h Kaggle iteration; Duck cannot separate harness bugs from model variance (their 0.4 std) |
| Sandbox | REPL 30s / 4096 chars, reset per call, NOT isolated | **subprocess** sandbox, stdlib allowlist, bounded output, hard timeout+kill, `action()` RECORDS (never executes) (M4) | isolated + safe (their acknowledged risk); RAISE our default timeout toward their 30s to allow in-REPL search; match 4096 output cap |
| Model | Qwen 3.6 27B FP8 / vLLM | model-agnostic `OpenAICompatClient` (vLLM or ollama), config swap (M6) | primary = same Qwen3.6-27B-FP8; our client already supports the exact endpoint |
| Budgeting | soft deadline (~10min pre-budget), n_passes=1, gateway wait 600s | Round-1-second-half (Kaggle side) | adopt their per-game soft-deadline + concurrency; keep RESET-keeps-level semantics (we already do) |

**Net**: three of Duck's own named future-work items — curated memory, better
perception, context compaction — are exactly where `repl_agent` already
differentiates (falsifiable memory, stable-ID tracking, 3-tier history), plus we
add two axes they lack entirely (mechanical governance, deterministic replay).
That is the differentiation to DEEPEN, not converge onto their design.

## Falsification

If we later obtain the `taaf` solver source, code-verify the design items in §2
(they are currently the authors' prose, not read from source). If any measured
number here (30s/4096/64k/32k/4×/20-tries/1.6002) is contradicted by the source
or a later write-up revision, correct it here with the new provenance.

## Related
- the reference-only standing rule (memory `feedback-no-copying-winners`) — the reference-only standing rule.
- [[lb_top_team_research_20260714]] — the M1 top-team survey this deepens.
- [[r55_code-repl-agent]] — our code-REPL agent these deltas steer.
- [[r54_vision-llm-policy]] — the JSON-policy arm (Reki/forge lever).
