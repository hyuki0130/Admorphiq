---
round: r93
axis: agent25 (LLM orchestration) — tool-fork-and-patch falsification
keywords: [agent25, solver-core, source-card, patch-loop, tool-fork, hypothesis-dsl, no-repeat-rule, gpt-oss-offline, codex-review, stall-matrix]
verdict: IN PROGRESS — foundation landed (ea3bf21); falsification measurement pending on Kaggle gemma4
commit: ea3bf21
---

# R93 — tool-fork-and-patch: can the LLM debug OUR code?

> R92 closed "the LLM authors solvers from scratch" (guess-code, 0 clears despite a
> 100%-valid tool-calling interface). R93 tests the user's counter-design: the runtime
> agent works like a coding agent — run OUR tool first, and on stall READ its real
> source, patch it, and re-test with matched replay. A materially different capability
> (repairing an executable scaffold with feedback) than the one falsified in R92.

## Provenance / design authority

- **User directive (2026-07-21, verbatim intent)**: "단순 툴 사용이 전부가 아니고 우선 툴
  사용 후 이상 있으면 코드 이해 후 해결" — select our tool, test it, on error copy the
  tool, fix, re-test, version-manage. Never author game logic from a blank page.
- **Codex review 1 (design)**: worth ONE minimum falsification build, NOT the full
  5-tool version-ledger system. Binding requirements: (a) the card the model patches
  must BE the code the tool executes (no drifting copies; parity tests); (b) blank-page
  coding removed; (c) code channel = free-form fenced python (the JSON-string tool-arg
  channel measurably collapsed kernel usage 23→0); (d) progress = lexicographic
  (level > new states > reproducible new transitions), matched parent-vs-patch replay
  from the same checkpoint — "state changes per action" alone is gameable; (e) success
  = patch changes the correct decision logic + reproducible progress on ≥1 of 2 distinct
  failure cases; both fail → agent25 FINAL shelve.
- **Codex review 2 (extra levers, user-requested)**: "the core problem is not
  insufficient intelligence; it is excessive generative freedom." Ranked additions:
  (1) typed hypothesis DSL + harness-side transition-consistency verification +
  bounded synthesis; (2) harness-controlled active identification (hard no-repeat-no-op
  rule, disagreement probes, machine-enforced evidence ledger); (3) small diverse
  ensemble of SCHEMA hypotheses (not code samples), selected by replay. Waste list:
  more unconstrained code samples, prose-only dynamics calls, sparse learned model as
  ground truth, broad gpt-oss deployment without the 2-case matched A/B, LoRA now,
  further prompt/kernel-exposure expansion.

## Step-1 stall matrix (ceph-build, 2026-07-21 22:29–22:36 KST, SUMMARY-verified)

Direct tool runs, NO LLM (`scripts/probe_tool_direct.py`), 4 tools × 4 games.
Full matrix @300: **15/16 combos 0 levels; toggle×vc33 = 2 levels.** Budget-confound
check @2000 (6 pairs): graph×{vc33,m0r0,ls20} 0, paint×cd82 0, world_model×ls20 0,
toggle×vc33 still 2. Artifacts: `scripts/rounds/R93/step1/` on ceph-build.

- **Reading**: the stalls are STRUCTURAL, not budget — every one of these games is a
  script25 conquest or near (m0r0 1.0, ls20 1.0, cd82 0.98), so the kernels can express
  the solutions; the bare tools cannot. Also contextualizes R92's smoke: at 300 actions
  even our own tools clear ~nothing, so the LLM's 0 had a budget component — but the
  @2000 confirmation shows removing it does not change the structural picture.
- **Chosen failure cases** (tool predictably stalls + game solvable):
  **toggle×vc33** (progress to L2 then wall — concrete patch target) and
  **paint×cd82** (structural 0 — the mechanic mismatch case).

## Foundation landed (commit ea3bf21, suite 1439 green)

- `src/admorphiq/tools/solver_core.py` — `toggle_core`/`paint_plan` as plain
  sandbox-runnable functions; `ToggleTool`/`PaintFloodTool` DELEGATE to them (one
  implementation, parity-tested). `source_card(tool)` assembles the REAL source via
  `inspect.getsource` + a sandbox-contract header (6.6KB for toggle). Instrumented
  trace lines (stencil counts, GF2 consistency, plan sizes) give the patcher
  localization evidence — Codex's "30 actions, zero changes contains little
  localization information" risk.
- **Click-xy transition fix** (bug found during build): `self._transitions` recorded
  only an action NAME — click (x,y) was dropped, making click-game analysis impossible
  for ANY model. Now records full Step; serializes as {'action','xy','before','after'}.
  This retroactively explains part of R92's zero `transitions` usage: the record was
  unusable for the click games in the smoke.
- Sandbox `_ALLOWED_IMPORTS` += `__future__`, `numpy` (re-exec real annotated source).

## gpt-oss-120b offline vocab — SOLVED (bounded A/B lever only)

Verified locally with network blocked: `TIKTOKEN_ENCODINGS_BASE` → plain-named
`o200k_base.tiktoken`/`cl100k_base.tiktoken` (sha256 match the strings embedded in
`openai_harmony.abi3.so`). Kaggle dataset `jaehyukhyun/tiktoken-encodings-offline`;
bench notebook wired + preflight (commit fa66d9f). Per Codex: gpt-oss runs ONLY as the
2-case matched A/B against gemma4 — not a broad deployment.

## v1 Kaggle run (2026-07-21 23:44 KST) — harness defects found, patches were GOOD

Kernel `admorphiq-r93-patchloop-gemma4` v1 (RTX PRO 6000, gemma4-31b-it): both cases
returned **PATCH_INVALID(execute)** — but per-stage telemetry shows these were OUR
defects, not model verdicts, and the model's patch CONTENT is the first positive
agent25 signal ever measured:

- **The patches were evidence-grounded and correct in form.** paint×cd82 (2.5KB):
  diagnosed the REAL stall from the instrumented trace (*"the stall seen in logs where
  the same coordinate is clicked repeatedly"* — parent noop_rate 0.36) and made the
  targeted fix (probe the next-largest region to break the deadlock), composing our
  helpers (`_infer_fill_color`/`_bg_regions`/`paint_plan`) correctly. toggle×vc33:
  conservative structure-preserving patch whose `_next_probe(frame, set(stencils))`
  call is semantically exact. **Contrast with R92**: the same model that guess-coded
  `act('RIGHT')` from a blank page debugs OUR code with evidence. The user's
  tool-fork thesis has first-order support.
- **Harness defect 1 (execute failures)**: models omit the card's leading
  `from __future__ import annotations`, so the REAL signature's `Any`/`Callable`
  annotations NameError at def time. Fixed c048bfa (prepend in run_patched_step;
  reproduced + verified locally); execute error TEXT now preserved in the JSON.
- **Harness defect 2 (parent parity)**: Kaggle parent toggle×vc33 was 0 levels vs 2 on
  ceph-build — the solver_core refactor had replaced ToggleTool's component-CENTROID
  probe order with a full foreground-pixel scan (drift the synthetic parity test
  missed; Codex's exact warning). Fixed 65f8a61 (`_component_centroids`, self-contained
  + card-bundled); engine parity gate back to 2 levels @2000.
- v2 re-pushed (dataset v5) 2026-07-22 00:03 KST — the first run where the verdict is
  actually about the MODEL. Artifacts: `scripts/rounds/R93/` + kernel outputs.

## Next

1. `scripts/probe_patch_loop.py` (in build): parent run → patch ask (source_card +
   trace + free-form python) → validate (1 error-feedback retry) → matched patch replay
   from RESET → lexicographic verdict JSON. Per-stage failure telemetry.
2. Kaggle gemma4 run on the 2 failure cases → THE falsification verdict.
3. If signal: add hypothesis DSL (Codex #1) + no-repeat rule (Codex #2) + ensemble
   (Codex #3); gpt-oss 2-case A/B. If both cases fail: agent25 FINAL shelve; the
   private-110 lever stays dev-time kernel generality.

## Related

- [[r92_agent25-kernel-bridge]] (the falsified from-scratch axis; v6 interface fix)
- [[r56_generic-kernels]] · [[r53_unified-harness]]
- `memory/project_r56_r58_state.md` (R92 verdict block)
