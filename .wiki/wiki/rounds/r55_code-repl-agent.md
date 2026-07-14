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

### Observability truthfulness batch (2026-07-14, obs-1..4)

Per the Codex observability review (causal account before more counters), built
on the frozen-dataset window while v4 ran:

- **obs-1** (`62471bb`) — wire vLLM token usage {input,output,reasoning,cached} +
  finish_reason into TurnRecord; add ordered image_hashes; FIX the after-state
  bug (the decision-time frame is the BEFORE hash; the event stream is
  authoritative for the after-hash). `truncations` (finish_reason==length)
  becomes a tracked metric — the su15 finding is now countable.
- **obs-2** (`66082ec`) — `events.py`: append-only per-event JSONL (flush,
  monotonic seq) + `derive_summary` (marks `run_incomplete` when no terminal —
  a killed kernel keeps a truthful record). `run_game` emits game_start /
  action_executed(+pre_hash) / transition(+post_hash) linked by `action_id` /
  level_up / reset / exception / terminal; the kernel opens it FIRST and folds
  the derived summary into the diagnostics.
- **obs-3** (`4874d23`) — `manifest.py`: `run_manifest.json` at bench start
  (run_id, git commit+dirty, model, prompt_version, config env, package
  versions, game list, accelerator, budget, start time); defensive.
- **obs-4** (`1952c9a`) — a `PREDICT: changed|no_change` line scored against the
  observed transition (predictions_made/correct) and fed to
  `EnvironmentMemory.record_prediction` — a deduped falsifiable hypothesis that
  evolves (support/contradict, bounded). **Fixes the v3 static-memory gap:
  MEMORY now evolves across turns**, and every turn carries the causal
  predicted-vs-actual link the directive requires.

71 repl_agent tests, ruff clean, kernel imports clean off-Kaggle. Next in the
confirmed order: the R1 namespace deltas (shortest_path, action_outcomes/is_dead,
exclusions). v4 transcript analysis takes precedence when it lands.

### v5 build — Codex v3-analysis review fixes (2026-07-14)

Codex re-mined the v3 transcripts (docs/r55_codex_v3_analysis_review_20260714.md):
2 of my diagnoses corrected (memory is static because NOTHING mutated it — not
downstream of the REPL; truncation was inferred not proven) + 10 missed defects,
4 structural. Implemented the big four + parser/coords/trim/tokens, one axis per
commit:

- **v5-1** (`d7ddabf`) — wire the rendered image into complete() (was
  complete(prompt, None) — a text-only policy, not multimodal). render_images
  flag for the JSON-only arm.
- **v5-2** (`e8b1f53`) — restore causal feedback: LAST_ACTION carries action +
  coords + source + outcome (board_changed/level/game_over); RECENT_TRANSITIONS
  serialized (HistoryTiers.recent was never sent); RECENT_EVENTS tagged with
  turn+action; game_id threaded (was always empty).
- **v5-3** (`3d508f3`) — governed + disclosed fallback: 74/173 v3 turns ran a
  hidden ungoverned fallback that could loop; now every fallback candidate is
  governor-vetted (first legal non-repeat) and disclosed via source=fallback.
- **v5-5** (`772892d`) — parser recovers a bare action ONLY from the last line
  (no stale mid-reasoning recovery); coordinate fields renamed `_rc`
  (safe_click_rc/bbox_rc/centroid_rc) in packet AND Inspector; trimming keeps
  changed objects first + visible objects_shown marker; max_tokens 1536→512.
- **v5-4** (`d12388c`) — bounded tool loop: inspection-only code returns its
  stdout to the model (NO env action) for up to max_tool_rounds, then it acts;
  inspection never triggers a hidden fallback; each round is its own TurnRecord.
  `inspections` counter added.

79 repl_agent tests, ruff clean, kernel imports clean. v5 targets Codex's
integrity gates (0% illegal proposals, 0 stale-parse, 100% proposal→governor→
executed correlation, disclosed fallback, inspection→0 env actions). Next: v4
transcript legality-confirmation check when it lands, then the remaining
namespace deltas (action_outcomes/is_dead) + the matched JSON-only arm
(render_images=False + max_tool_rounds=0).

### v4 legality-confirmation check (2026-07-14, scratchpad/replbench_out4)

v4 (legality-prompt) landed. The legality binding WORKED and the prompt
description alone moved REPL engagement — but revealed the dominant failure mode
that v5 was built to fix.

- **Q1 legality binding: FULLY EFFECTIVE.** g50t/ls20 (no MOUSE) had **0 illegal
  MOUSE proposals** (v3: 33 / 22). Governor rejections dropped to 4 / 7 (legit
  repeats, not illegal actions).
- **Q3 (the decisive finding): the prompt description ALONE engaged the REPL** —
  code blocks went from 0 (v3) to the majority of turns (bp35 93/107, g50t
  99/149, su15 58/74). BUT ~95% are **inspection-only** (no `action()` call):
  g50t 94/99, bp35 86/93, su15 49/58. Since v4 **discards sandbox stdout**, those
  inspection turns produce no action → **fallback**. Fallback rate is dominated
  by this exact chain: bp35 86% fallback (86 inspection-only), g50t 69% (94),
  su15 81% (49). **This is precisely what v5's bounded tool loop fixes** — the
  model is already trying to inspect; v5 returns the stdout so those turns become
  productive. Strong forward validation of v5's #1 fix.
- **Q2 su15 parse failures (2):** both were a final-line bare `UNDO` (su15 is
  legal `[MOUSE, UNDO]`) that the bare-text parser did not recognize → dropped →
  fallback. Fixed: `UNDO` added to the movement regex (test added). Lands next
  push.
- No `_rc` / `shortest_path` usage yet (both post-date v4 — expected).

**v5 expectation update:** because v4 proves the model inspects heavily but
blindly, v5's stdout-return should sharply cut the fallback rate and convert
inspection into real, informed actions. Watch: action-source split
(code-with-action vs fallback), REPL engagement = code-that-informs-an-action,
and whether informed inspection unlocks the first L1 clear. Throughput note: v4's
g50t/ls20 hit the 150-action cap, but ~70%/29% of those were fallback churn, not
productive play — v5 changes the character, not just the count.

### v5 full gate evaluation + v6 diagnosis (2026-07-14, replbench_out5)

v5 landed. The machinery gates PASS but the capability gate FAILED (0 clears),
and the analysis found a P0 infrastructure bug that INVALIDATES the REPL-arm read.

**Integrity gates (mostly PASS):**
- Illegal MOUSE proposals: **0** on every game (legality binding holds).
- Executed action SOURCE (from LAST_ACTION disclosure): **70-99% model-chosen**
  (ls20 99%, dc22 91%, su15 87%, bp35 75%, g50t 70%) — v5 cut the v4 fallback
  domination (69-86% fallback) sharply. Fallback is disclosed (source=fallback).
- Governor rejections (bp35 29, g50t 20) are legit **repeat** rejections (illegal
  MOUSE = 0), i.e. the governor correctly blocking same-state-action retries.
- Event streams complete: action_executed == transition (100% correlation), all
  terminal (no run_incomplete). Latency p50 1.7-2.5s / p95 2.7-13s (< target).
  Throughput 84-246 actions/600s (> 60 target). Parse fail: su15 6/162 = 3.7%
  (the bare-UNDO gap, fixed 0c9470f, not in this build) else <1%.

**🔴 P0 BUG — the sandbox was NON-FUNCTIONAL on Kaggle.** sandbox_errors ≈ the
inspection count on every game (bp35 101, dc22 133, su15 84). The error, on ALL
of them: `Error while finding module specification for
'admorphiq.repl_agent._sandbox_worker'`. The subprocess sandbox spawns `python -m
admorphiq…` but `run_code` passed NO env, and on Kaggle `admorphiq` is
sys.path-INJECTED (not pip-installed) — so the fresh subprocess can't import it
and EVERY run_code errored. **The tool loop ran but returned ERRORS, not
inspection data — the model never actually got to inspect via code.** Fixed:
`run_code` now propagates the parent's sys.path as PYTHONPATH to the subprocess
(+ test). This means v5's REPL-arm result is INVALID — the REPL was dead; a v6
re-run is required to truly evaluate it.

**Capability diagnosis (the real question — WHY no clears):** even packet+image-
only (the model DID have the working segmentation packet), the trace shows the
core wall. On su15 (paint game, human L1 ≈ 12-22 actions; model used 85):
- Perception/dynamics are FINE: PREDICT 100%, every action changed the board
  (nochange=0), every state unique — NOT wandering-in-place.
- But the model formed an early WRONG goal ("connect the dots — click the next
  green dot") at t0 and NEVER revised it: every click spawns new green objects
  (su15's mechanic), which it reads as "continue the chain-reaction/clearing
  sequence" — indefinitely (t11/t21/t31/t82 all the same hypothesis). **It
  conflates 'my action changed the board' (trivially true) with 'I progressed
  toward the goal'.** No win-condition model → can't tell productive change from
  noise → clicks forever. 85 > 22 actions, so it is NOT a budget problem.
- This is the GOAL-INFERENCE frontier (project-wide: r51/r52, graph 7/25
  ceiling) now confirmed at the 27B-multimodal-policy level. Movement games
  (g50t PREDICT 56%, dc22 72%) add a weaker walls dynamics model on top.

**v6 fix set (ranked by tractability):**
1. **P0 sandbox PYTHONPATH (DONE this commit)** — makes the REPL actually work on
   Kaggle. The #1 action: RE-RUN v6 to get a valid REPL-arm evaluation (v5's is
   confounded — the REPL never ran). Also bump the sandbox-error integrity gate
   into the kernel summary so this class of bug fails loudly next time.
2. **Goal-revision signal (tractable, additive)** — the model never revises a
   wrong goal because nothing tells it it's not progressing. Add to the packet an
   `actions_since_last_level` counter + an explicit "if this is high, your goal
   hypothesis is likely WRONG — try a different mechanic" nudge; and make PREDICT/
   memory score a GOAL-relevant prediction (predict level_completed or a target
   state), not the trivial board-change it scores now (which is ~always right and
   never bites). Directly attacks the observed "endless clicking = mistaken
   progress".
3. **Honest caveat** — whether a 27B model can infer these win conditions with a
   WORKING REPL + goal-revision signal is UNKNOWN, because v5's REPL was dead. Do
   NOT conclude "model too small / pivot to JSON-arm or model-swap" from v5. That
   decision needs v6 (working REPL) first. If v6 with working inspection + goal
   revision still clears nothing on su15/ls20, THAT is the model-swap input.

### v7 build — Codex v5-review safeguards + fixes (2026-07-14, flag-gated for v6)

Codex reviewed the v5 gate evaluation (docs/r55_codex_v5_review_20260714.md):
accepted the P0 invalidation but scoped it (only REPL-usefulness/capability
metrics are invalid; illegal-0%, event completeness, latency stay valid),
amended su15 to "wrong JOINT mechanic/goal model under a degraded tool path",
and specified the v7 goal-revision mechanism. Built the safeguards + fixes,
commit-per-item; the audit is flag-gated (default OFF) so v6 (P0-only) vs v7
stays one-variable:

- **v7-1** (`a9a0ed0`) — `sandbox_self_test()` spawns the REAL worker subprocess
  before play and the kernel HARD-ABORTS on failure (the mocked test only proved
  PYTHONPATH is passed); `SandboxResult.infra_error` separates a subprocess
  import/spawn crash (the v5 P0) from the model's code raising — counted
  separately in diagnostics.
- **v7-2** (`609d39a`) — real per-level `turn_in_level` (was aliasing the
  game-lifetime turn, never reset on level-up; transcript field now populated).
- **v7-4** (`19b2eea`) — de-self-confirm memory: the per-turn PREDICT is
  relabeled EFFECT_PREDICT (dynamics, scored as a counter only) and NO LONGER
  written to goal_hypotheses (a board-change 'supported' any story); Hypothesis
  gains milestone+falsifier, and record_progress supports a goal ONLY when its
  declared bounded-horizon milestone is met.
- **v7-3** (`9c30ad7`) — `GoalAuditor`: at 12/24/48 actions-without-level it
  demands GOAL_HYPOTHESIS / EXPECTED_MILESTONE(within N) / FALSIFIER /
  ALTERNATIVE_HYPOTHESIS + one discriminating action; the first audit forces an
  informative TEST, a milestone missed twice forces the alternative. Flag-gated
  (`audit_enabled`, kernel `REPL_AUDIT`).
- **v7-5** (`959697b`) — save the actual rendered PNG every N turns
  (`frame_dump_dir`/`REPL_FRAME_DUMP_EVERY`) for human legibility inspection
  (hashes prove attachment, not legibility).

95 repl tests, ruff clean, kernel imports clean. Per Codex: run v6 P0-only first;
if a clean v6 (working REPL) still repeats the same false mechanic after real
transition inspection, v7's audit is the goal-revision evidence.

### v6 (P0-only) analysis — REPL alive, but false mechanic PERSISTS (replbench_out6)

The P0 fix WORKED. vs v5 (comparison harness): inspection_success_rate 0 → ~1.0
(bp35 1.0, dc22 0.985, g50t 0.89, ls20 0.937, su15 1.0); sandbox_errors ~100 →
0-10. Actions now flow THROUGH code (source split: su15 code 129 / llm 8 /
fallback 5; bp35 code 116; dc22 code 125) — the model uses the REPL to act, and
fallback collapsed. Integrity holds: illegal MOUSE = 0 everywhere.

**But still 0 clears, and the decisive question answers YES on both gaps:**
1. **False mechanic PERSISTED.** su15 t0 is the SAME wrong "connect the dots /
   path-following" hypothesis as v5 (su15 is actually vacuum/merge/delivery), and
   it clicks the same cell (57,6) repeatedly. A working REPL alone did NOT
   trigger revision.
2. **Tool-use judgment gap on su15.** su15 ran 136 code turns but only ONE
   inspection-only — the model used code to FIRE CLICKS, not to investigate the
   mechanic on the game where it most needed to. (Contrast g50t/ls20, which DID
   inspect: informed_inspections 18 / 13.) So on the click games the model does
   not spend the free internal computation on understanding — it acts.

Both are exactly the pre-agreed branch condition. Working inspection is
necessary but not sufficient; the model needs to be FORCED to falsify its goal.

**Two tractable sandbox bugs fixed (ride the next push, `430d000`):** (a) the
allowlist lacked `next` (and other common read-only builtins) — valid model code
NameError'd; added them in the repl worker. (b) `Inspector.objects()` returned
`color`/none while the packet shows `colors`/`change_history` — code written from
the packet field names KeyError'd; the Inspector schema now mirrors the packet.
Residual v6 errors were small (g50t 10, ls20 6) and entirely these two classes.

**Recommendation (pre-agreed branch fires): next run = v7 with `REPL_AUDIT=1`.**
The GoalAuditor forces, at 12/24/48 actions-without-level, a declared
GOAL_HYPOTHESIS + bounded MILESTONE + FALSIFIER + ALTERNATIVE + one discriminating
action, and rejects the goal after two missed milestones — directly attacking
BOTH the goal-revision gap (makes "connect the dots" falsifiable and forces the
vacuum/merge alternative on miss) and the tool-use gap (the discriminating-action
requirement forces an investigative test instead of blind clicking). All other
levers (image legible at 4×, inspection now working, fallback governed) are
already in place.

### 🎉 v7 (REPL_AUDIT=1) — FIRST LLM-agent clear: su15 L1 via the audit (replbench_out7)

**su15 levels=1 — the first level cleared by the code-REPL LLM agent**, on the
exact game whose false "connect the dots" mechanic persisted through v5 and v6.
The continuation gate (≥1 sanity L1) PASSED.

**Causal chain (the audit is the lever):** the GoalAuditor fired at the 12/24
action thresholds. At the first audit (idx 12) the model still declared the wrong
"guide the green trail to the red target" goal — but WITH a falsifier + an
alternative. At the SECOND audit (idx 13) it REVISED the mechanic to "guide the
four moving objects into target zones" (toward su15's real vacuum/merge/delivery
mechanic), and L1 cleared ~7 turns later (first level>=1 record at idx 20).
Forcing a declared, falsifiable goal + alternative broke the loop that a working
REPL alone (v6) did not. ~107 actions total for L1 (human 12-22; ~12 pre-first-
audit); the clear itself came fast once the mechanic flipped.

- **Audit fires reliably on all games** (3-5 audits each) with LOW overhead:
  llm_calls barely exceed actions (su15 115/107, g50t 168/144) — audits are part
  of the decision, not extra rounds. Inspections dropped modestly vs v6 (8-27)
  but not crowded out (g50t still 27).
- **Integrity holds**: illegal MOUSE = 0 everywhere; sandbox_errors already 0-2
  (the `430d000` allowlist + field-alignment fixes will take them to ~0 next run).
- **ls20 did NOT clear** (budget cap at 150): audits fired (4×) and the model
  revised to a plausible NAVIGATION goal ("navigate the player to the target"),
  but didn't solve within budget — a CONTROL/efficiency gap (it never used
  `shortest_path` for the declared navigation), not a goal-inference failure.

**Leaderboard double-confirmation (same day):** v10 hidden publicScore = 0.20
(public proxy 5.83, mechanic-solver depth) vs v6 0.14 (proxy 1.072). +4.7 proxy
from public-game solvers bought only +0.06 hidden — public-specific capability
barely transfers, exactly the R55 thesis; and R55's generic agent scored its
first clear the same day via the audit. See memory `project_leaderboard_first_score`.

**v8 recommendation (ranked):**
1. **Scale the audit** — it works (su15 proof); run REPL_AUDIT=1 on more games /
   the full 25 to measure the clear count. This is the headline lever now.
2. **Navigation efficiency (ls20-class)** — the model forms a roughly-right
   navigation goal but never uses `shortest_path`, so it wanders under budget.
   Nudge the audit's discriminating-action toward `shortest_path` for declared
   navigation goals, and/or the packet toward a plan-then-execute step.
3. **First-audit earliness** — ~12 pre-revision actions wasted before the first
   audit. A slightly earlier first threshold (measured, one-variable) could cut
   waste — but keep Codex's "first audit forces a TEST, not a premature switch".
4. Ship the `430d000` sandbox fixes (allowlist + field alignment) — already
   committed, ride the next push.

### v8 — Codex v7-review: matched OFF/ON experiment + standing gates (2026-07-14)

Codex reviewed the v7 milestone (docs/r55_codex_v7_review_20260714.md): accepted
su15 as MECHANISM evidence (not an effect estimate) and specified a matched
experiment. Pre-run fixes + the experiment kernel built (commit-per-item);
key corrections:

- **Efficiency corrected — su15 L1 was 19 actions, not 107** (`45cbc1d`). The
  bench continues after L1; 86 of the 105 total were POST-clear (L2 attempts).
  19 actions vs human 12-22 = **near-human, RHAE ≈ 0.4-1.0** (not 0.013). The
  new `action_phases()` reports actions-to-first-level-up / before-first-audit /
  between-audits / revision-to-level-up / after-level-up.
- **Audit overcount fixed** (`7b2c937`) — a transcript AUDIT scan overcounts
  (prompt persists across tool-loop rounds; ls20's "4" > the max 3). Explicit
  `TurnRecord.audit {threshold, action_count, fields}` + `audits_triggered`
  counter is the real count.
- **Temperature pinned** (`21adb3c`) — v7 actually sent **0.0** (greedy), not the
  assumed 0.2; now explicit + manifest-recorded.
- **Matched experiment** (`7aad83b`) — `MATCHED_12_GAMES` + `matched_run_plan`
  (interleaved OFF/ON per game, su15 x3 = 28 runs) + kernel
  `REPL_EXPERIMENT=matched12`; sandbox fixes in BOTH arms; NO nav fix / NO
  threshold changes; temp pinned; per-run outputs `{game}_{arm}_r{rep}`.

**Standing criteria (Codex, binding):**
- **Continuation gate**: ON clears su15 ≥ 2/3 replicates AND materially beats OFF;
  the revision + discriminating action precede every ON clear; across the 12, ON
  gains ≥ 2 clears over OFF WITHOUT worse aggregate RHAE. If it passes, run the
  unchanged audit arm on the full 25, then test navigation on ls20/dc22/g50t/tu93.
- **Efficiency ranking** (RHAE + actions-to-clear now CO-PRIMARY with clear
  count; the metric squares efficiency & level-weights): (1) post-revision plan
  quality + short verified execution (short receding-horizon macros with
  invariants, not long batches); (2) navigation `shortest_path`/plan-then-execute;
  (3) earlier first audit (saves ≤ ~12 actions — least leverage).
- **Submission-chain gate** (the REPL arm has NOT earned deployment yet; earns it
  only when ALL hold): ≥3 reproducible clears across ≥2 mechanic families; ≥2
  incremental over the LLM-free floor; median clear efficiency within ~3× human;
  ≥1 L2+ result showing knowledge amortizes; `floor+REPL` beats floor by ≥5% on
  paired real RHAE with no lost floor clears; uplift survives metamorphic/OOD +
  a non-oracle router; simulated 110-game runtime < 8h. Integrate as a
  zero-action plan proposer / pre-action routed controller — NOT a post-stall
  fallback (stalled actions permanently damage RHAE).

### v9 — next levers (flag-gated, built while matched12 runs) + su15 L2 finding

Built the next levers, all default-OFF so they don't touch the matched12
comparison and each becomes its own one-variable test after the verdict:

- **REPL_PLAN** (`383e4f4`, Codex #1 efficiency lever) — while a goal is active,
  between audits the prompt requests a short 2-5 step MACRO (precondition +
  predicted invariant per step) through the existing governor macro machinery
  (arm → stop-on-surprise → re-plan). Converts post-revision wandering into
  verified short bursts. Not on the goal-declaration turn.
- **REPL_NAV** (`8b0d9f5`) — for the ls20/dc22/g50t/tu93 nav class, audits nudge
  the model to CALL `shortest_path` with its OWN start/goal/passable_mask (tool
  decides nothing).
- **REPL_EXPERIMENT=full25** (`ae1cf72`) — 25 games × single audit-ON arm
  (~450s/run ~3.2h), ready to push after the matched12 gate passes.

**su15 L2 finding (v7 post-L1 segment):** L1 cleared at idx 20, then 95 records
on L2, **never reaching L2 clear**. On L2 the model did NOT carry the L1 revised
mechanic ("moving objects to zones") across the boundary — it re-hypothesized
fresh ("black ring / red object center"). So the composition property (learned
mechanic amortizing across levels) did NOT visibly help here; L2 is a distinct
sub-configuration the model re-reasons from scratch. A future lever: carry the
CONFIRMED mechanic (not just the goal) across the level boundary — relevant to
the submission-chain's "L2+ knowledge amortizes" condition.
