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

## R33b result (2026-07-05) — LLM goal = heuristic goal = baseline (forward-model accuracy is the wall)
R33b (LLM goal via qwen3:8b at discovery, warm-start OFF) = 0.0013 — IDENTICAL to R33a heuristic
(0.0013) and baseline (0.0014), clears 3/9, per-game numbers the same. Better goals do NOT help.

FINAL DIAGNOSIS: the wall is NOT goal quality — it's FORWARD-MODEL ACCURACY. The 15K-param change-mask
model, trained from scratch (warm-start OFF) within the per-game budget, predicts rollouts too
inaccurately for goal-proximity scoring to mean anything. Giving planning a correct GOAL doesn't help
if the model can't accurately predict which action MOVES TOWARD it. Consistent with R32b (accuracy gate
was ineffective). goal-directed planning is blocked by forward-model accuracy under the from-scratch,
per-game online budget.

CONCLUSION: The full R27 pipeline (neural forward model + goal inference + goal-directed planning) is
BUILT and CORRECT (468 tests, planning fires, LLM goal parses) but does not beat the 0.0014
transfer-honest baseline, because an online-from-scratch forward model isn't accurate enough for
lookahead in the per-game budget. The pipeline is a reusable asset; the binding constraint is now
forward-model sample-efficiency/accuracy.
