---
title: ARC-AGI-3 top open-source solutions survey (2026-07-08)
type: lesson
keywords: [arc-agi-3, leaderboard, top-solutions, stochasticgoose, online-rl, world-model, metric-scale, generic-methods]
date: 2026-07-08
description: Survey of what is actually open-sourced for ARC-AGI-3 (M1 winners = local-LLM agents), resolution of the leaderboard score-scale confusion (top ~1.56 = 1.56%, not 156%; the 12.58% anchor was the 2025 preview), and the top-3 generic levers to adopt next.
---

# ARC-AGI-3 Top Open-Source Solutions Survey (2026-07-08)

## Symptom (what we needed)

Two open questions blocked our planning:

1. Our repo's recorded anchor said "top ~ 0.1258 (12.58%)", but a 2026-07-08
   leaderboard screenshot shows top scores of ~1.56 (Mathurin Ache, anngle,
   NoOneAhead all 1.56; Biubiu/MLRush 1.46; tight 1.3-1.44 cluster to rank ~22).
   These numbers are irreconcilable unless the scale/reference is clarified --
   and our local harness (scripts/score_efficiency.py) yields ~0.002/game, so
   we could not tell if we were 8x or 800x below the top.
2. We needed GENERIC, generalizing mechanisms (not per-game hardcoding) that we
   can fold into a training-free graph-frontier BFS agent (~18/25 sample games)
   plus a new offline-LLM executable-world-model track.

## Root Cause / Findings

### Metric-scale resolution (the 1.56 vs 0.1258 contradiction)

- The Kaggle leaderboard "Score" column is the RHAE total on a 0-100% scale,
  displayed as the bare percentage number. `1.56` means 1.56%, NOT 156%.
  - Confirmation: Tufa Labs' own post says "We hit 1.21% with our lightweight
    harness" (https://x.com/tufalabs/status/2072336849465417747); press coverage
    says Tufa raised the top "from 0.68% to 1.17%" (https://digg.com/ai/k8o9t7me);
    frontier models score <1% (Gemini 3.1 Pro 0.37%, GPT-5.4 0.26%, Claude Opus
    4.6 0.25% -- https://arxiv.org/html/2603.24621v1). The live 1.3-1.56 cluster
    is therefore 1.3%-1.56%.
- The "12.58%" anchor was the 2025 Agent PREVIEW competition (StochasticGoose),
  a smaller/easier, partly random-solvable game set -- NOT the 2026 main
  competition's 110 private games. Apples-to-oranges. The 2026 main-competition
  top is ~1.2-1.6%. (https://arcprize.org/blog/arc-agi-3-preview-30-day-learnings)
- No conflict with the 1.15 per-level cap. The cap is per-LEVEL. The total is
  the mean of per-game scores over ~110 games; most games score ~0, so the mean
  lands at a small percentage (1-1.6%) far below any cap. Methodology confirms:
  per-level (human_actions/ai_actions)^2, capped 1.15x; per-game =
  level-index-weighted average; total = mean of per-game scores, 0-100%
  (https://docs.arcprize.org/methodology).
- Comparison rule for our harness: score_efficiency.py reports a FRACTION
  (0-1). Multiply by 100 to compare to the leaderboard number. Our ~0.002/game
  mean -> total fraction ~0.002 -> ~0.20 on the leaderboard scale, vs top 1.56
  and Tufa M1 1.21. So we are roughly 8x below the current top, ~6x below the
  M1 winner -- a closeable gap, not a hopeless one. Our harness IS faithfully
  comparable once x100 is applied.

### Which solutions are ACTUALLY open-source

Open-sourcing is only REQUIRED at milestone deadlines (M1 = June 30 passed,
M2 = Sep 30). The current LIVE-leaderboard leaders are NOT yet required to
publish (https://arcprize.org/competitions/2026/arc-agi-3).

- Current top-3 (Mathurin Ache, anngle, NoOneAhead @1.56; Biubiu/MLRush @1.46):
  NOT open-sourced. No writeups, notebooks, repos, or discussion posts were
  found for any of them (targeted searches returned nothing). Mathurin Ache is a
  known Kaggle Grandmaster (https://www.kaggle.com/mathurinache) but has no public
  ARC-AGI-3 writeup. Treat their methods as UNKNOWN. (Kaggle leaderboard/discussion
  pages are JS-rendered and not machine-fetchable here; a human should re-check
  the discussion tab directly.)
- The only PUBLIC 2026 solutions are the M1 (June 30) winners -- all three run
  LOCAL open-weight LLM/VLM, all training-free at inference
  (https://arcprize.org/blog/arc-prize-2026-milestone-1):

  1. Tufa Labs "The Duck" -- M1 1st, ~1.21%. LLM code-agent: converts game
     state to Python variables, acts through a live REPL (reason -> write helper
     fns -> execute -> observe). Perceives via rendered image + raw ASCII grid +
     segmentation tools. "Infinite play via eviction" context management (drop
     oldest messages, keep system prompt + recent). Model: Qwen 3.6 27B FP8,
     local. Lesson: hand-crafted tools HURT the model; letting it improvise won.
     Notebook:
     https://www.kaggle.com/code/jeroencottaar/tufa-labs-duck-harness-june-30-milestone-winner
     ; writeup: https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-3/discussion/717133
  2. Reki -- M1 2nd. Vision-LLM-as-policy: renders recent frames as labeled
     images -> single JSON (what changed + short plan + next 1-4 actions).
     Reflection memory (~10-step refresh), numpy click heuristic (small,
     rare-colored, button-like shapes), "Dead-signature" to stop clicking
     ineffective object types, JSON self-repair, legal-action constraints.
     Model: Gemma-4-31B, local. Notebook:
     https://www.kaggle.com/code/ruichardliu/milestone1-2nd-solution
  3. Md Boktiar Mahbub Murad "forge" -- M1 3rd (LB 0.86). Same local-VLM
     policy family (image -> JSON, reflection memory, repair/legal guards) wrapped
     in a "forge" profile framework (flow / candidate-generators / arbiter
     scoring); the WINNING config disabled the extra machinery (minimal wins).
     Model: Gemma-4-31B, local. Notebook:
     https://www.kaggle.com/code/mbmmurad/arc-agi-3-lb-0-86-3rd-place-candidate-milestone

### Reference solutions (2025 preview + papers)

- StochasticGoose (preview 1st, 12.58%) -- CNN + test-time RL; (state,action)->
  frame_changed BCE, 200K hash-dedup buffer, hierarchical action sampling, buffer/
  model reset per level. Repo: https://github.com/DriesSmit/ARC3-solution (no
  license stated). Non-determinism: not handled.
- Blind Squirrel (preview 2nd, 6.71%) -- state graph from frames + retrained
  ResNet18 VALUE model to rank promising state-action pairs; prunes dead actions.
- arc-agi-3-just-explore / dolphin-in-a-coma (preview 3rd) -- training-free
  graph explorer; connected-component segmentation, status-bar masking, clickable
  segments in 5 button-likelihood tiers, frontier BFS by tier. MIT, CPU-feasible.
  Repo: https://github.com/dolphin-in-a-coma/arc-agi-3-just-explore ; paper
  https://arxiv.org/abs/2512.24156. Self-states non-determinism/partial-observation
  "causes issues" -- the SAME ceiling we hit.
- Executable World Models for ARC-AGI-3 (paper) -- coding agent fills 3 Python
  files (engine/state_io/planner), verifies the model reproduces past transitions,
  refactors toward MDL simplicity, plans through the model, executes with online
  predicted-vs-observed checking. GPT-5.5: 15/25 games, 58.12% RHAE (highest
  published). Repo (MIT, code released): https://github.com/astroseger/arc-3-agents-baseline1
  ; paper https://arxiv.org/abs/2605.05138. NOT offline as-shipped (needs GPT-5.5/
  OpenAI API) -- but the LOOP is our LLM-WM blueprint; swap the LLM for local Qwen.
- Explore Before You Solve (paper) -- epistemic agent, info-gain action choice,
  tunable speed-depth tradeoff, training-free. Repo:
  https://github.com/farmountain/aera-arc3-paper ; paper https://arxiv.org/abs/2605.25931.

### Determinism / hidden-state (question c)

The official technical report states the released games are deterministic
(same TRUE state + action -> same result) -- which is what enables graph search.
The "same screen + action -> different result" phenomenon is partial
observability / hidden state (timers, off-screen entities, accumulated
counters), NOT stochastic dynamics. Frame-hash graph BFS assumes visible frame =
state; when two distinct true states alias to the same frame, the graph is
corrupted. This is likely the #1 cause of our BFS plateau. No public M1 winner
documents explicit hidden-state handling (they assume determinism). This is our
differentiation opportunity. (https://arxiv.org/html/2603.24621v1)

## Prevention / Adoption -- top-3 generic levers to try next

Lever 1 -- Local-Qwen executable-world-model loop (highest ceiling; effort HIGH).
Combine the astroseger loop structure (MIT, 58% RHAE blueprint: synthesize ->
verify-against-replay -> refactor-for-simplicity -> plan -> execute-with-online-check)
with Tufa's proof that a LOCAL Qwen 3.6 27B FP8 code-agent works on Kaggle
hardware (96GB VRAM is ample). Hidden state becomes explicit Python variables --
fundamentally beats frame-hashing. This is our stated track; risk is low because
both the loop and the offline-feasibility are already demonstrated.

Lever 2 -- Graph-BFS state de-aliasing for hidden state (immediate; effort MED).
Augment the frame hash with recent action-history k-gram / visit-count / status-bar
counters so aliased nodes separate; detect when identical (frame,action) yields
different next-frames and fork parallel branches (per arxiv 2512.24156); optionally
rank the frontier with a Blind-Squirrel-style learned/heuristic value. Directly
targets the games where our BFS currently corrupts.

Lever 3 -- Cheap generic action priors (fastest; effort LOW).
Port the M1 2nd/3rd-place heuristics into our BFS frontier priority: numpy click
heuristic (small/rare-colored/button-like components -- we already have
connected-components in FrameAnalyzer), "Dead-signature" blacklist to stop probing
ineffective object types (saves actions -> directly helps the squared-efficiency
metric), and for the LLM track adopt reflection-memory (~10-step) + eviction
context management. Principle to internalize: minimize hand-crafted tools, let the
model improvise (Tufa + forge both converged on this).

## Falsification

- If a fetch of the live Kaggle leaderboard shows the top team's score rendered
  as "156%" or as a raw sum >100, the "1.56 = 1.56%" reading is wrong -- re-derive.
  (Current evidence -- Tufa's 1.21% tweet matching the ~1.2 cluster -- makes this
  very unlikely.)
- If any of Mathurin Ache / anngle / NoOneAhead publishes a writeup or repo before
  M2, the "current top-3 not open-source" claim expires -- re-survey.
- If a measured local-Qwen executable-WM run scores <= our BFS baseline (~0.20
  leaderboard-scale) after a fair implementation, Lever 1's "highest ceiling"
  ranking is falsified for our stack.

## Related

- [[online_rl_sprint_round_log]] -- online-RL round history + this survey's entry
- [[rounds/r52_ewm-integration]] -- our executable-WM integration (the Lever-1 track)
- [[rounds/r34_metric-reexamination]] -- prior (preview-era) metric anchor this corrects
- StochasticGoose repo, astroseger executable-WM repo, dolphin-in-a-coma graph repo (URLs above)

## 2026-07-08 follow-up — latest models + post-M1 public methods

### Q1 — latest open-weight models for an OFFLINE code-agent / executable-WM on 96GB

Hard fact that reframes everything: nearly ALL new (Apr–Jul 2026) strong open
models EXCEED 96GB VRAM and are excluded — GLM-5.2 (744B/40B, INT4 ~372GB, MIT,
https://recipes.vllm.ai/zai-org/GLM-5.2), DeepSeek V4-Flash (284B/13B, 4bit
~142GB, MIT, https://www.morphllm.com/deepseek-v4), MiniMax M3 (428B/23B, Q4
~265GB), Kimi K2.7 Code (1T/32B, 2bit ~325GB), DeepSeek V4-Pro (1.6T). Qwen
3.7-Max is API-ONLY (no weights, https://qwen.ai/blog?id=qwen3.7). So the offline
lever is METHOD, not a bigger model. Ranked shortlist that FITS 96GB:

1. **Qwen 3.6-27B (dense)** — 27B dense, 4bit ~15GB, FITS (huge headroom),
   Apache 2.0. SWE-bench Verified 77.2 / SWE-Pro 53.5 / LiveCodeBench v6 83.9 —
   best coder in-bracket; the EXACT model Tufa's M1 winner ran. 2026-04-22.
   https://qwen.ai/blog?id=qwen3.6-27b  <- SINGLE BEST PICK for us.
2. **gpt-oss-120b** — 117B MoE / ~5B active, MXFP4 native ~63GB, FITS (tight),
   Apache 2.0. Strongest math/scientific reasoning in-bracket, small active =
   fast; good for the goal-hypothesis reasoning role. 2025-08.
   https://openai.com/index/introducing-gpt-oss/
3. **Qwen 3.6-35B-A3B (MoE)** — 35B / 3B active, 4bit ~20GB, FITS, Apache 2.0.
   Slightly below the 27B dense on coding but 3B active = top throughput (matters
   for the 9h/110-game budget). 2026-04-16. https://ollama.com/library/qwen3.6
4. **Gemma 4 31B (dense)** — 31B, 4bit ~18GB, FITS, Gemma license (not Apache,
   check Kaggle use terms). Proven on THIS task (M1 2nd/3rd + JEPA writeup),
   multimodal. https://ai.google.dev/gemma/docs/core

Recommendation: Qwen 3.6-27B dense as the primary executable-WM code-agent
(re-evaluate the R48 Qwen3-Coder-30B-A3B pick against it); gpt-oss-120b as the
reasoning backup.

### Q2 — any NEW public method beating ~1.2% published AFTER the June-30 M1 winners?

No. No public notebook/writeup/paper dated after June 30 2026 demonstrably beats
the M1 top (~1.21%). The live top-3 (~1.56%) remain NOT open-sourced (no writeups
found). The strongest published methods are still the M1 winners (Tufa "The Duck",
Qwen 3.6-27B FP8 local, live-REPL code agent — "hand-crafted tools hurt, let the
model improvise") and the pre-M1 arXiv 2605.05138 executable-WM paper (cloud
GPT-5.5, 58.12% RHAE on public-25, NOT offline as-shipped). Both reinforce our
R48/R49 executable-WM direction; no newer public SOTA to chase.
