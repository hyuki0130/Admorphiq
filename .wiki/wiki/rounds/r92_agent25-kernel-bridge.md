---
round: r92
axis: agent25 (LLM orchestration) — runtime kernel bridge
keywords: [agent25, code-agent, kernel-api, sandbox, HARNESS_KERNEL_API, gpu-prep, tool-vocabulary, codex-review]
verdict: PREP LANDED (gated OFF) — the runtime code-agent can now CALL the r59 kernels; behaviour byte-identical until measured on GPU
commit: f14f323
---

# R92 — agent25 kernel bridge (GPU-waiting prep)

> The runtime code-agent LLM could not call the r59 kernel library that produced the
> 32.96% script25 card; it reimplemented every composition from scratch. R92 wires the
> curated kernels into the code sandbox as `K.<name>(...)`, gated OFF by default.

## Why

script25 (adapters25 composing kernels at DEV-TIME) proves the kernel toolbox can EXPRESS
public-25 clears (card 32.96%). The deploy path is agent25 = the offline LLM composing the
SAME kernels at RUNTIME on unseen games. The runtime code-agent (`tools/code_agent.py`)
execs model-written python in a sandbox that blocked `import` and exposed only `np +
current_frame + shallow history` — so the model could not reach `admorphiq.kernels`. That
is the gap between 32.96% expressiveness and agent25 competence.

## What landed (commit f14f323)

- **`src/admorphiq/tools/kernel_api.py`** — `KERNEL_API`: curated PURE, current_frame-
  composable, bounded kernels (find_regions, region_relations, multiset_signature,
  color_mode, elongated_axis, point_toward, covering_offsets, grid_shortest_path,
  path_to_moves, dihedral_transforms, crop_to_content, best_transform_match, assign_pairs).
  `KERNEL_CARDS` = compact per-kernel prompt card ((row,col) convention, arg/return shapes,
  hard limits). `DEFERRED` = the kernels left out WITH the reason.
- **`run_code`** injects the kernels as a `K` SimpleNamespace (inert — the model won't call
  what the prompt doesn't advertise).
- **Prompt gate** `HARNESS_KERNEL_API` (default OFF): `_system_content()` appends the cards
  only when set, so the DEPLOYED prompt/behaviour is byte-identical until measured.
- Combinatorial guards enforced IN CODE (not prompt): `assign_pairs` smaller-dim ≤ 12,
  `region_relations` ≤ 96 regions, `find_regions` gap ≤ 3. A breach raises → run_code
  catches → empty queue, never a hang.

## Codex design review (APPROVE-WITH-CHANGES, gpt-5.6-sol)

- **Security**: injecting live functions does NOT attenuate them
  (`K.fn.__globals__["__builtins__"]` reaches real builtins) — but the sandbox's existing
  `np`/`act` already leak identically, the code author is our own cooperative offline model,
  and Kaggle has internet disabled. So the bridge adds no practical capability the sandbox
  didn't already grant; `import` stays a guard-rail, not a boundary. Accepted.
- **Curated OUT** (this round): callback kernels (configuration_path, plan_delivery,
  points_with_centroid), grammar kernels (derive_rewrites, find_derivation), gf2_solve,
  plan_token_assignment, and connected_components (tools.base variant — background-rule
  clash with find_regions).
- **DEFERRED** to a Phase-2 sandbox enrichment: the transition-dependent kernels
  (frame_diff, separate_by_motion, track_objects, learn_cyclic_successor, complete_cycle,
  is_single_cycle, reachable_frontier) — they need `previous_frame` + observed transition
  triples the sandbox does not yet hand the model. **This is the load-bearing finding**: the
  HIGH-value kernels (learned-operator / faithful-sim / config-space that made lp85 / r11l /
  m0r0 clear) can't be reached until the sandbox exposes richer state. Phase-2 = pass
  previous frames + a bounded (state,action)->state record + a capped successors harness.

## Tests / gates

7 new tests in `tests/test_code_agent_kernels.py` (kernels callable in-sandbox, import still
blocked, guards degrade safely, prompt gate default-off byte-identical / on-appends-cards,
exposed∩deferred = ∅). 258 green in the code_agent/harness/ewm/kernel subset; ruff clean.

## Kaggle agent25 smoke — FIRST END-TO-END RUN (2026-07-21, kernel v3 COMPLETE)

Pipeline PROVEN on the real eval hardware. Kernel `admorphiq-agent25-kernel-bench` v3
(RTX PRO 6000, offline; qwen3-6-27b-fp8 via vLLM api_server; result
`r92_agent25_bench_v3.json`). 4 games × matched OFF/ON arms, 300 actions, both
HARNESS_CODE_ESC=1.

- **Infra all green**: vLLM served qwen (`/v1/models 200`), LLM calls landed (latency
  20–34s), code escalation fired, the kernel-bridge preflight (`K.find_regions`) passed,
  RHAE scoring + telemetry worked. The "BRIDGE INERT" guard did NOT trip — the ON arm
  sent the KERNEL TOOLBOX card on vc33 (5 code prompts) and ls20 (10).
- **Result: 0 clears in BOTH arms** (m0r0/vc33/cd82/ls20, all 0.0). Load-bearing finding:
  **the model was handed the kernel vocabulary but produced ZERO `K.`-using replies**
  (`kernel_replies=0` on every arm). Exposing the toolbox in the prompt did not, by itself,
  get qwen3.6-27b to call the kernels.
- Two boot gotchas fixed en route (both now standard): kernel-metadata needs
  `"machine_shape": "NvidiaRtxPro6000"` (interactive push otherwise gets a P100, compute
  6.0, which can't run fp8 — `Minimum capability: 75`); and the dataset mount path for
  `scripts/score_efficiency.py` varies, so resolve it by walk, not a hardcoded path.

Read correctly: this is a smoke on qwen (NOT the measured-best gemma4), a small budget, the
known-weak code-agent path, AND only the perception/geometry kernels are exposed (the
high-value transition kernels that cleared lp85/r11l/m0r0 are DEFERRED). So 0 clears is
uninformative about the ceiling; the ACTIONABLE signal is `K.`-usage = 0.

## Qwen vs gemma4 comparison (2026-07-21) — MODEL is the kernel-uptake variable

Same notebook (model-agnostic, auto-detected served name), same 4 games, same matched
OFF/ON arms, same model-agnostic few-shot. Only the model differs. Results:

| model | ON code_prompts | ON kernel_replies (`K.` used) | clears |
|---|---|---|---|
| Qwen3.6-27B-fp8 + few-shot (v4) | 15 | **1** | 0 |
| gemma4-31b-it (bf16) | 40 | **23** | 0 |

- **gemma4 engages the bridge ~23× more than qwen.** Given the SAME cards + example, gemma4
  called `K.` on most turns (m0r0 10/10, cd82 10/10, ls20 3/10; vc33 0/10) and wrote a python
  block every turn (pyR=10 in BOTH arms); qwen mostly returned no python at all. The user's
  caution was right — tuning the bridge to qwen's (non-)uptake would have been misleading.
- **vLLM 0.19.1 serves gemma4-31b-it fine** (`served-name=gemma4`, 13 calls/game, 15-30s
  latency) — the arch-support risk is resolved; gemma4 is a viable Kaggle runtime model.
- **Still 0 clears for BOTH.** So the agent25 gap is no longer "does the model use the
  kernels" (a capable model does) — it is "the composed solutions don't yet SOLVE." The
  most likely cause is the exposed set: only PERCEPTION/GEOMETRY kernels are live; the
  high-value transition/permute/config-path kernels that actually cleared lp85/r11l/m0r0 are
  DEFERRED (Phase-2), and the code sandbox still only sees current_frame + shallow history.

Files: `r92_agent25_bench_v4_fewshot.json` (qwen), `r92_agent25_bench_gemma4.json`.

## Phase-2 result (2026-07-21) — transition kernels did NOT unlock clears

gemma4-31b-it re-run with Phase-2 (sandbox exposes `transitions`/`previous_frame` +
8 transition kernels). Result JSON `r92_agent25_bench_gemma4_phase2.json`. The three
measured configs:

| config | exposed kernels | ON kernel_replies | clears |
|---|---|---|---|
| qwen + few-shot | perception/geometry | 1 | 0 |
| gemma4 v1 | perception/geometry | 23 | 0 |
| gemma4 v2 (Phase-2) | + transition kernels | 2 | 0 |

- **Still 0 clears**, and adding the transition kernels + `transitions` data REDUCED
  gemma4's kernel engagement (23 → 2 K.-replies) — prompt bloat (the big TRANSITIONS
  card + few-shot) diluted focus rather than helping. Errors = 0; the model just wrote
  fewer K.-using blocks. OFF arms byte-identical to v1 (deterministic, temp 0).
- **Viability read (the question this round was set up to answer):** the agent25
  code-agent path — LLM writes python composing kernels, stall-triggered escalation,
  300-action budget, ≤10 code blocks — does NOT produce clears at smoke scale across
  qwen + two gemma4 kernel-sets. This is consistent with the R53 finding that
  "orchestrating pre-built tools plateaus"; piling on kernels is NOT the lever, and
  more kernels can hurt (engagement drop). The 32.96% script25 card is kernels composed
  BY US at dev-time; the LLM composing them at runtime remains the unsolved gap and this
  experiment shows exposing more kernels does not close it.
- **Cheapest next diagnostic (NOT another kernel pile-on):** does the unified harness
  clear the games its OWN graph tool clears in script25 (m0r0/vc33/ls20)? If the harness
  gets 0 where the bare tool clears, the bottleneck is harness orchestration/budget
  (tools starved by the LLM routing), not the kernel bridge — a different, cheaper fix.
  If even bare tools get 0 in the offline Arcade @300a, the smoke's budget/game choice is
  the confound. Either way, resolve THAT before more agent25 LLM/kernel investment.

## Next (needs GPU)

0. DONE — few-shot added (kernel_replies qwen 0→1) and the qwen-vs-gemma4 comparison run:
   gemma4 uptakes the kernels heavily (23 K.-replies), so model choice, not prompt tweaking,
   is the uptake lever. gemma4-31b-it is the runtime model to carry forward.
1. **Phase-2 sandbox enrichment is now the critical path** (was already the deferred item;
   the comparison confirms it): expose the transition-dependent kernels (frame_diff,
   track_objects, learn_cyclic_successor, reachable_frontier, configuration_path) by passing
   the code sandbox `previous_frame` + a bounded (state,action)->state transition record +
   a capped successors harness. That gives gemma4 the kernels that actually clear, not just
   perception. Re-run the gemma4 matched smoke and look for the first clears.

1. Turn `HARNESS_KERNEL_API=1` and measure agent25 with the bridge on a GPU host (NHN 2×V100
   or Kaggle) — does the kernel vocabulary lift the code-agent above the ~18/25 plateau?
2. Phase-2 sandbox enrichment to unlock the deferred transition-dependent kernels.

## Related

- [[r56_generic-kernels]] (the kernel library) · [[r53_unified-harness]] (the code-agent core)
- `docs/r56_codex_toolbase_verdict_20260715.md` (script25/agent25 dual scoreboard)
