---
type: lesson
date: 2026-07-14
keywords: [leaderboard, top-teams, vision-llm, duck, reki, forge, gemma-31b, transfer]
---

# LB top-team strategy research (2026-07-14)

> M1 top-3 all use offline LLM brains (Gemma-4-31B ×2, Qwen 3.6 27B); the untried lever for us is vision-LLM-as-policy; our model pick and brittle-purge direction are independently validated.

## Symptom
Our hidden-set publicScore 0.14 vs LB top band 1.38–1.61; question raised whether "LLM-free" was
a measurement artifact of OUR harness design rather than a property of LLMs.

## Root Cause (of the gap, per evidence)
Top teams use the LLM in roles we never measured:
- **Duck (Tufa, M1 #1, 1.21)**: Qwen 3.6 27B FP8, agent-writes-code REPL over game state
  variables, sliding-window context eviction, multimodal perception (rendered image + ASCII +
  segmentation). "Hand-crafted tools actually hurt; letting it improvise worked better."
  https://tufalabs.ai/research/duck-harness/
- **Reki (M1 #2)**: Gemma-4-31B local, vision-LLM-as-policy — labeled frame image → one JSON
  action/turn + reflection memory (~10 steps) + dead-signature avoidance + legal-action
  constraints + 1-4 action plan queue. numpy click heuristic fallback.
- **forge (M1 #3)**: Gemma-4-31B, same pick-JSON + multi-candidate arbiter; best run had extra
  machinery OFF (simple > complex).
- LLM-free deterministic graph search exists (arXiv 2512.24156, claims private #3-ish tier,
  19 levels @4000 actions) — our graph tool's family.
- Executable WM (arXiv 2605.05138): mean RHAE 58% on 15 games but GPT-5.5-class API only,
  10× Duck's cost — not Kaggle-deployable as-is. (Our EWM track's ceiling explanation.)
Sources: https://arcprize.org/blog/arc-prize-2026-milestone-1 ,
https://arcprize.org/media/ARC_AGI_3_Technical_Report.pdf

## Prevention / How to apply
1. **Model pick validated**: gemma4-31b-q8 (R48–R51 measured) = the M1 #2/#3 winning model.
   Do not chase bigger models; refine the harness.
2. **NEXT LEVER (R54): vision-LLM-as-policy** — gemma4-31b is multimodal; render the frame to a
   labeled image, prompt for a single JSON action under legal-action constraints, reflection
   memory, dead-signature, short plan queue. Build alongside (not replacing) the chained card;
   measure head-to-head.
3. **Tool-ablation rounds are evidence-backed** (#1/#3: machinery off = best score): measure the
   card with each of the 6 tools disabled.
4. **Public-proxy distrust is official**: public 25 deliberately under-represents private 110
   mechanics; harness can hit 97.1% on one env and 0% on another. Never treat local 25 as an LB
   proxy (matches our measured 13% transfer).
5. **agent-writes-code stays closed at 31B scale** (our R51 0/6 + sk48 break) unless following
   Duck's exact recipe (minimal helpers + image perception) with Qwen-27B-class.

## Falsification
If a vision-LLM policy at gemma-31b scale measures BELOW the LLM-free chained card on the
public 25 after a fair bring-up (prompt iterations + the Reki efficiency kit), the lever is
falsified for our stack and this page must be updated.

## Related
[[r53_unified-harness]], [[size_floor_and_settle_reads]], [[r54_vision-llm-policy]] (the R54 build of the vision-LLM-as-policy lever defined here), [[duck_harness_teardown_20260714]] (measured fact-extraction of the #1 Duck harness + our design deltas)

## Deep-read addendum (2026-07-14 09:25 KST) — Duck internals + official technical report

**Duck harness specifics** (github.com/Tufalabs/duck-harness, ARC3-Inference/README.md):
- Perception: raw numeric grid deliberately HIDDEN from the model. Primary = SEGMENTATION summary
  (connected components, object hashes, boundaries, containment, adjacency); ASCII grid for local
  checks; images only auxiliary. Variables exposed: current_frame.ascii/.segmentation, history,
  previous_frame, transitions, last_transition, valid_actions, last_action_result
  {board_changed, level_completed, game_over, run_complete, reward}.
- Actions: UP/DOWN/LEFT/RIGHT, SPACE, MOUSE(row=..., col=...) — legacy x/y REJECTED.
- REPL: stateless per call, stdlib allowlist, 30s timeout. (Context-eviction details + the list
  of harmful hand-crafted tools are only in Kaggle discussion/717133 — JS/login-gated, needs a
  human browser.)

**Official technical report** (ARC_AGI_3_Technical_Report.pdf, read in full):
- Hidden = 55 semi-private + 55 fully-private; BOTH intentionally out-of-distribution vs public
  ("limited overlap with public mechanics"); semi vs fully differ only in ACCESS. Public 25 is a
  demonstration interface, not a training resource.
- No official mechanic-tag taxonomy (scorecard tags derive from available_actions). Env mechanics
  deliberately undisclosed (4-char ids, anti-leak).
- Human baseline: 10 humans/env in-person, env kept only if ≥2 independent full-solves; baseline =
  upper-median best FIRST-RUN action count; action budget = 5× human median.
- RHAE confirmed: S=min(1.15,(h/a)²), level-index weights, env cap = completed-weight fraction;
  our scripts/score_efficiency.py is FAITHFUL (1.0 vs 1.15 cap only).
- **Two leaderboards**: official (no harness, fixed system prompt; frontier ~0.1-0.5%) vs
  community/Kaggle-code (harness allowed) — we compete in the latter; top 1.61 is that band.
- Generalization warning (official): a public-tuned harness hit 97.1% on a seen variant and 0.0%
  on an unseen env — public-specific harnesses collapse on hidden. Brittle-purge re-validated.
- Envs: Core Knowledge priors only, no language/symbols, ≥6 levels, L1 = tutorial (random
  sometimes passes), difficulty = COMPOSITION of earlier concepts in later levels — implies
  cross-level concept reuse is a real lever for depth.

**R54 design deltas applied**: segmentation-first prompt (image auxiliary), row/col MOUSE schema,
per-turn last_action_result feedback, Reki reflection JSON {what changed, short plan, next 1-4
actions}.

## Duck writeup FULL TEXT captured (2026-07-14 10:36, discussion/717133 via logged-in browser)

Raw text: `.wiki/raw/duck_writeup_discussion_717133_20260714.txt`. NEW facts beyond the README:
- **"World Model" = a NOTE carried across turns**: the model writes a `World model:` tagged block
  in its response; the harness copies it into every subsequent user message until the model
  overwrites it. That's their whole persistent memory — prompt echo, no code.
- **Context policy**: 64k hard cap, evict to maintain ~32k input; evict oldest user message +
  subsequent assistant turns; reasoning blocks removed; system prompt always kept. They note they
  do NOT yet exploit vLLM prefix caching.
- **Per-action user message repeats**: game state, valid actions, tool-usage reminder, world-model
  instructions + current world model, and "collect evidence on what happened before acting."
- Segmentation tool exists because "printing the whole grid pollutes context" (their words) —
  4-connected components, adjacency, parent-child.
- Their own future-work list: context compaction/curated memory, abstract-description perception
  ("coding models are not trained to reason over ASCII crops").

## Official serving recipe (gregkamradt/arc-agi-3-gpt-oss-120b notebook, pulled 2026-07-14)

An ARC-Prize-team example runs **gpt-oss-120B via vLLM inside the competition kernel** — so
27B FP8 serving is a solved problem. Exact recipe:
- `python -m vllm.entrypoints.openai.api_server --model /kaggle/input/models/danielhanchen/
  gpt-oss-120b/... --max-model-len 64000 --kv-cache-dtype fp8 --tensor-parallel-size 1
  --enforce-eager` as a subprocess; health-poll until ready (1800s timeout).
- Agent = openai SDK OpenAI client → local server (matches our repl_agent OpenAICompatClient).
- vllm + tiktoken encodings from a "vllm-deps" input notebook (offline wheels).
- ⚠️ **15-minute FIRST-ACTION deadline**: the notebook records start time to avoid missing it —
  act BEFORE the LLM finishes loading. Our ChainedAgent (LLM-free WMA probe) can take first
  actions immediately while vLLM boots in the background: natural fit.

