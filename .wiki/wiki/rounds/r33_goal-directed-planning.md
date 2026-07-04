---
title: R33 — goal inference + goal-directed planning
type: round-log
round: R33
axis: goal-inference
keywords: [goal-inference, goal-directed-planning, forward-model, llm-goal, heuristic-goal, transfer-honest]
verdict: R33a heuristic goal = 0.0013 ≈ baseline 0.0014 (no gain); R33b LLM-goal testing
commit: 20afa66 (infra, env-gated OFF)
date: 2026-07-05
---

# R33 — goal inference + goal-directed planning (R27 pipeline missing piece)

**Axis**: goal-inference · attacks the GOAL-ABSENCE wall (R32b)
Neural forward model rollouts scored by GOAL-PROXIMITY (not novelty). Goal from a heuristic (R33a) or
the offline LLM at discovery (R33b). Judged warm-start OFF (baseline 0.0014). Infra committed 20afa66
(env-gated OFF = card; forward_model.py reconstructed to the test-pinned 2-plane contract after the
worktree copy was lost).

- **R33a — heuristic goal** (RL_GOAL_PLAN=1, RL_GOAL_LLM=0, warm-start OFF): 0.0013 ≈ baseline 0.0014,
  clears 3/9. The goal-directed planning MACHINERY runs, but a crude heuristic goal (most-changed
  colour region) doesn't steer well — no gain. This isolates that the mechanism works but goal QUALITY
  matters. Does NOT yet condemn goal-directed planning — the user-chosen path is the LLM goal (R33b).
- **R33b — LLM goal** (RL_GOAL_LLM=1, qwen3:8b at discovery): testing whether a better (LLM-inferred)
  goal makes goal-directed planning beat baseline.

**Related rounds**: [[r32_neural-forward-model]], [[r29_warmstart-off]], [[r13_efficiency-insight]]
See map: [[rounds_index]]. Overview: [[online_rl_sprint_round_log]].
