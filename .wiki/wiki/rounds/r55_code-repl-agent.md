---
type: reasoning
round: R55
axis: code-repl-agent
keywords: [code-repl, duck, qwen3.6, multimodal, transcript-replay, segmentation-tracker, turn-packet, python-sandbox, inspection-api, action-governor, offline-core, controller-persistence]
verdict: Round 1 offline core COMPLETE (6 modules incl. loop assembly, 46 tests, LLM-free; --agent repl fails fast offline, model wiring = client swap on Kaggle infra)
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

## Module 4 — Python sandbox + inspection API (built)

`src/admorphiq/repl_agent/sandbox.py` + `_sandbox_worker.py`. The model writes
Python that INSPECTS the scene (free internal computation — no env actions
spent) and REQUESTS actions; each call runs in a throwaway subprocess.

- `ObservationStore` — all frames + tracked scenes; `to_payload()` serializes
  into the subprocess (raw frames stay available to code, not the prompt).
- `Inspector` — the API bound into the sandbox namespace: `objects(t)`,
  `crop(region, t)`, `ascii(region, t)`, `mask(id, t)`, `compare(t1, t2)`,
  `relations(id, t)`, and `action(kind, row, col)` which RECORDS a request
  (explicit accounting — never touches the env). Usable in-process for fast
  tests; the subprocess shares the same class (one implementation).
- `run_code(code, store, timeout, max_output)` — spawns
  `python -m …_sandbox_worker`, which binds the API onto a restricted namespace
  (stdlib-allowlist builtins reused from `ewm.core._safe_builtins`), execs the
  code with stdout captured + bounded, and returns `{stdout, error, actions}`.
  A hard subprocess-level timeout+kill stops runaway loops (one hung generation
  can't starve the run); syntax/runtime errors are reported, never crash.

8 unit tests (objects/relations, crop/mask/compare, ascii shape, action
accounting, subprocess action round-trip, syntax-error report, disallowed-import
block, hard-timeout kill), 3.1s (subprocess spawns), ruff clean.

## Module 5 — Action governor (built)

`src/admorphiq/repl_agent/governor.py`. Sits between the model's requested
actions and the env, enforcing the design's action discipline so the model can't
damage RHAE with reactive/repeated moves. Deterministic (model-free) so the
replayer can re-derive every decision.

- **Legal-action enforcement** — requested action must be in the current legal
  set; MOUSE(row, col) must be in bounds (row = y, col = x, zero-based).
- **Repeated state-action prevention** — the same action in the same state
  (frame hash) is rejected the second time.
- **Macro gating** — a 2-8 step macro is admitted ONLY if every step states a
  precondition AND a predicted invariant; it arms + returns step 1, executes
  step-by-step, and ABORTS on surprise (unexpected change / unexpected no-change
  / level completion / game over / signature mismatch). `observe_after` returns
  continue / macro_done / macro_aborted:<reason>.
- **Undo accounting** — UNDO is charged as one env action (probe+undo = two);
  `total_actions` / `undo_count` track it.

9 unit tests (illegal reject, legal accept, MOUSE bounds + missing coords,
repeated state-action, undo accounting, macro length gating, precondition+
invariant required, arm + stop-on-surprise, complete + level-complete abort),
0.02s, ruff clean.

## Module 6 — ReplAgent loop assembly (built)

`src/admorphiq/repl_agent/agent.py`. Wires the five modules into one
harness-contract agent so the Kaggle LLM wiring is a pure client swap:
`SceneTracker.update → TurnPacketBuilder → LLMClient.complete → parse (code block
or action/macro JSON) → sandbox inspection → ActionGovernor-vetted actions →
TranscriptRecorder`. Decisions happen at boundaries only (queue empty / macro
end), never one LLM call per action.

- `LLMClient` protocol + two impls: `MockLLM` (scripted, offline tests) and
  `OpenAICompatClient` (thin `/chat/completions` for vLLM-serve OR ollama;
  endpoint/model via `REPL_LLM_BASE_URL` / `REPL_LLM_MODEL`; constructing without
  the URL raises immediately so `--agent repl` fails fast offline).
- `parse_model_output` / `normalize_parse` — deterministic routing of a reply to
  code / actions / macro / none, and the replay-stable `parsed_tool_calls` form.
- `ReplAgent` — the loop with an action queue (macros advance via the governor's
  `observe_after`, stop-on-surprise clears the queue and forces a re-decide),
  online `SceneTracker`/`ActionGovernor`/`EnvironmentMemory`/`HistoryTiers`, and
  a safe fallback when no governed action is available. Model-facing names
  UP/DOWN/LEFT/RIGHT/SPACE/UNDO/MOUSE map to ACTION1-7 (fixed default; learned
  per-game mapping is a later round).
- `--agent repl` registered in `scripts/score_efficiency.py` (additive).

6 end-to-end tests driving the full loop offline via MockLLM: parse routing,
code inspection round-trip + governed action, JSON action governed, illegal
action rejected → safe fallback, macro stop-on-surprise (continues on change,
aborts + re-decides on no-change), transcript record→replay equality. 1.6s
(subprocess sandbox), ruff clean. Fail-fast verified.

## Round 1 offline core — COMPLETE

All six LLM-free modules built, unit-tested (46 tests total, ruff clean),
committed one per module. The package `src/admorphiq/repl_agent/` is generic (no
game ids) and purely additive — the deployed guards are untouched. This is the
"exact offline replay" + perception + governed-action spine the design doc calls
for; the loop is assembled and the Kaggle LLM wiring is now a pure client swap
(`OpenAICompatClient` against a vLLM/ollama endpoint). It makes one-hour Kaggle
iterations scientific.

**Round 1's second half runs on Kaggle infra (team-lead's side)**: Qwen 3.6 27B
FP8 vLLM deployment, model-facing prompt wiring (image-before-text for Gemma /
turn packet), P50/P95 latency at 8/12/16 concurrency, zero parser/serving
crashes, and one paired public-25 result vs ChainedAgent. The R54 `vlm_policy`
JSON-policy agent is the Round-2 2×2 ablation's JSON-policy arm against this
code-REPL arm.

## Related
- [[r54_vision-llm-policy]] — the JSON-policy arm (Round-2 ablation leg).
- [[lb_top_team_research_20260714]] — the M1 top-team evidence.
- [[duck_harness_teardown_20260714]] — measured teardown of the #1 Duck harness; the design deltas steering this agent.
- [[r53_unified-harness]] — the current harness; existing generic tools.
- [[index]]

## Kaggle serving PREFLIGHT: PASS end-to-end [2026-07-14 11:27 KST]

Kernel `jaehyukhyun/admorphiq-qwen-vllm-preflight` v1-v7 debugging chain (each failure root-caused,
per the observability directive):
- v1: normal CLI kernel = **Tesla P100 16GB** (27B impossible there).
- v3: `kaggle kernels push --accelerator NvidiaRtxPro6000` → **NVIDIA RTX PRO 6000 Blackwell,
  97,887 MiB** — the 96GB GPU is CLI-selectable (enum name measured, not documented in the SDK).
- v4: vLLM install fixed via kernel_source `philipvonderlind/vllm-deps` (the official example's
  source) → **vLLM 0.19.1**; in-process LLM() fails on spawn-bootstrap → use api_server subprocess.
- v5: server healthy @131k ctx (28.51GiB weights, 50.73GiB KV = 415,520 tok, 12.18x concurrency,
  90.8GiB used) but first inference 500: **flashinfer ninja-JIT fails offline**.
- v6: backend env sweep still 500 → root cause: **--kv-cache-dtype fp8 + head_dim 256 FORCES the
  flashinfer prefill kernel** regardless of VLLM_ATTENTION_BACKEND.
- v7 ✅: drop fp8 KV (bf16) + TRITON_ATTN + VLLM_USE_FLASHINFER_SAMPLER=0 →
  **first inference OK. SHORT P50=6.00s / P95=6.02s (200 out-tokens); LONG prompts 8k/24k/48k
  chars all ≈6.0-6.2s (prefill nearly free on Blackwell). KV 207,760 tokens; 6.2x concurrency
  @131k; model supports 262,144.**

DEPLOY CONFIG (measured): Qwen3.6-27B-FP8 weights (Kaggle model michaelpoluektov/qwen3-6-27b-fp8)
+ vllm-deps kernel source + api_server subprocess `--max-model-len 131072 --enforce-eager
--gpu-memory-utilization 0.92` + env VLLM_ATTENTION_BACKEND=TRITON_ATTN,
VLLM_USE_FLASHINFER_SAMPLER=0, VLLM_WORKER_MULTIPROC_METHOD=spawn. Server boot ~195s (well inside
the 15-min first-action budget if the LLM-free chain acts first). Latency is generation-dominated
(~35 tok/s eager): cap output tokens per decision; consider dropping --enforce-eager later for
CUDA-graph speedup. Duck capped context at 64k for throughput; we serve 131k with 6.2x
concurrency — eviction pressure is halved.


## Round 1 second half — repl-bench kernel (built, awaiting Kaggle push)

`notebooks/repl_bench_kernel.py` + `src/admorphiq/repl_agent/bench.py` give
`ReplAgent` its first real-LLM run and write full observability diagnostics (the
transcripts are how we debug the expected first-run integration bugs).

- **`bench.run_game(env, agent, *, max_actions=150, wall_s=600, reset_action, clock)`**
  — plays one game under BOTH an action cap and a wall-clock soft deadline,
  detects win / GAME_OVER (with restart revival), isolates a per-game crash into
  an error record (one game never kills the run), and assembles `GameDiagnostics`
  {levels, actions, wall_s, llm_calls, parse_failures, governor_rejections,
  sandbox_errors, terminal_reason, error}. `clock` is injectable for
  deterministic deadline tests. 7 unit tests.
- **`ReplAgent` observability counters** — `llm_calls`, `parse_failures`,
  `governor_rejections`, `sandbox_errors` (game-lifetime; read by the diagnostics).
- **Kernel** (`notebooks/repl_bench_kernel.py`, imports cleanly off-Kaggle):
  env-probe → offline install (arc wheels + vLLM from the vllm-deps mount via
  `--find-links`) → boot the vLLM api_server subprocess with the measured PREFLIGHT
  config (bf16 KV, `VLLM_ATTENTION_BACKEND=TRITON_ATTN`,
  `VLLM_USE_FLASHINFER_SAMPLER=0`, spawn, `--max-model-len 131072 --enforce-eager
  --gpu-memory-utilization 0.92`, port 8199) → health-poll (1200s) → run
  `ReplAgent` (OpenAI-compat client → local vLLM, `REPL_SANDBOX_TIMEOUT=30`) on
  su15, ls20 (sanity) + bp35, dc22, g50t (walls), each capped 150 actions / 600s,
  sequentially with per-game try/except → write `diagnostics/{game}.json` +
  `transcripts/{game}.jsonl` + a one-line per-game summary + a grep-able
  `REPL_BENCH_SUMMARY {...}` line.

Kernel metadata (model `michaelpoluektov/qwen3-6-27b-fp8`, kernel_source
`philipvonderlind/vllm-deps`, dataset `jaehyukhyun/admorphiq-src`, competition
source) + the push/poll ceremony are the team-lead's side. 54 repl_agent tests
pass, ruff clean.

### v1 first-run debug → v3 fixes (2026-07-14, transcript-localized)

The kernel v1 real-LLM run (RTX PRO 6000) surfaced integration bugs that the
transcripts localized exactly (the observability design paying off on run #1):
all 5 games TimeoutError — su15/ls20/bp35 hit the 120s client timeout with 0
completed calls; dc22/g50t each got ONE ~102s response that PARSE-FAILED.

Root causes (from `transcripts/*.jsonl`): (1) Qwen 3.6 thinking mode ON → 8.8-10.9k
chars of chain-of-thought at ~35 tok/s eager = 70-100s+/call, timing the client
out; (2) the "parse failure" was near-success — after `</think>` the model emitted
a clean bare-text `MOUSE(46, 35)`, correct perception+reasoning, only the output
CONTRACT mismatched (not JSON/code).

v3 fixes (one axis: the output/latency contract — perception untouched):
1. **Disable thinking** — `OpenAICompatClient` sends
   `chat_template_kwargs={"enable_thinking": false}` + `max_tokens=1000`; prompt
   appends a `/no_think` belt-and-braces + an explicit "action as the LAST line"
   output contract (`_OUTPUT_INSTRUCTION`).
2. **Client timeout 120s → 300s**.
3. **Parser robustness** — `strip_thinking` removes `<think>…</think>` before
   parsing; a bare-text fallback accepts `MOUSE(r, c)` / `UP|DOWN|LEFT|RIGHT|SPACE`
   as the last action line (verified against the actual 8827-char dc22 output →
   `{"action":"MOUSE","row":46,"col":35}`). JSON still preferred when present.
4. **Resilience + latency wiring** — a raised LLM call (timeout) is caught,
   recorded (latency + error in the transcript), counted (`llm_errors`), and the
   game continues via the safe fallback instead of ending. `llm_errors` added to
   `GameDiagnostics` + the kernel summary; the empty `game_id` field is filled.

60 repl_agent tests pass (+6: strip_thinking, bare-text from the real dc22 tail,
bare movement, JSON-preferred, client body disables thinking + caps tokens + 300s,
LLM-error survival), ruff clean.

### v3 first full run analysis → v4 fixes (2026-07-14)

v3 (thinking-off) ran clean end-to-end: all 5 games played to the 600s wall, 0
timeouts, 0 llm_errors, **0 clears**, all wall-bound (~15-21s/call). Transcript
analysis (`scratchpad/replbench_out3`, 173 turns) — answers from the traces:

1. **g50t/ls20 governor "storms" = ILLEGAL MOUSE, not repeat-rejection.** g50t
   legal={UP,DOWN,LEFT,RIGHT,SPACE} (no MOUSE) yet the model proposed MOUSE **33
   times**; ls20 (no MOUSE) **22 times**. The governor rejected each (→ fallback,
   `exec=None`). Repeat-(state,action) count ≈ 0. Root cause: nothing bound the
   model to `GAME.legal_actions`.
2. **su15 8 parse failures = LENGTH TRUNCATION.** Every failed turn was 2.4-3.2k
   chars of reasoning ending mid-sentence (no action line) — the model reasoned
   past `max_tokens=1000` and got cut.
3. **REPL usage = ZERO.** 0 code blocks, 0 inspection calls (`objects/crop/
   compare`), 0 sandbox output across ALL 173 turns. The model only emits bare
   actions (`llm_calls ≈ actions`). The code-REPL premise was never engaged —
   the prompt (turn packet + a thin "output one action" instruction) never told
   the model the sandbox/inspection API exists.
4. **Memory = STATIC.** 1 unique MEMORY state across every turn; goal_hypotheses
   / dead_interventions never populated. The falsifiable-memory infra is present
   but nothing feeds it (downstream of REPL engagement).
5. **Latency = OUTPUT-dominated.** ~35 tok/s eager; su15 mean 21.7s (2-3.2k-char
   outputs), g50t mean 14.8s (shorter). Input prefill is cheap; per-turn cost is
   generation length. Fewer turns (28-41) because each call is slow → brevity is
   also a throughput lever.

**v4 fixes (one axis each, generic, perception untouched):**
1. **Prompt contract / system prompt** (`_SYSTEM_PROMPT` + `_legal_reminder`) —
   describes the REPL + the exact inspection API (objects/crop/ascii/mask/compare/
   relations/action), invites a ```python block OR one action line, HARD-binds
   "use ONLY GAME.legal_actions; if MOUSE not listed, do not click" with the
   concrete legal set injected per turn, and demands brevity (≤4 lines). Targets
   findings 1 (illegal clicks) + 3 (REPL dark) + helps 2/5 (shorter outputs).
2. **Generation budget** — `max_tokens 1000 → 1536` headroom for the turns that
   still reason to completion (finding 2). Modest to bound the latency cost.

61 repl_agent tests pass (+1: prompt describes REPL + binds legal actions), ruff
clean. Deferred (next batch, confirmed order): observability truthfulness (wire
token usage + finish_reason to confirm the truncation fix; fix the after-state
hash via the event stream) before the namespace deltas. Note: the LLM-free card
clears su15 3/9 + ls20 1/7 — the REPL arm needs L1 clears next to stay credible.
