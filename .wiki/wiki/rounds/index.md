---
title: Online-RL Sprint — Rounds Index / Map
type: index
keywords: [rounds, index, map, online-rl, sprint, retrieval]
updated: 2026-07-02
---

# Online-RL Sprint — Rounds Index (retrieval map)

**How to use**: to find past work on a topic, look up the KEYWORD GROUP below → jump straight
to those round pages (do NOT scan the whole log). Each round page has its own keywords, verdict,
commit, and `[[backlinks]]`. Narrative overview + reliable-metric + resume steps live in
[[online_rl_sprint_round_log]].

## Keyword groups (topic → rounds)
- **reward-shaping / potential-based** (the one WORKING axis): [[r19_reward-shaping]] (first win, `2c93fc1`), [[r20_shape-coef-sweep]], [[r21_progress-phi-off]], [[r22_progress-phi-on]]
- **action-selection tweaks — ⛔ ALL FAILED**: [[r05_planning-override]], [[r06_depth-boost]], [[r09_additive-planning]], [[r10_object-state-hash]], [[r14_noop-suppress]], [[r15_dead-action-prune]], [[r16_object-click-prior]], [[r18_object-prior-full25]]
- **efficiency**: [[r13_efficiency-insight]] (key), [[r14_noop-suppress]], [[r15_dead-action-prune]], [[r19_reward-shaping]]
- **depth / level-transition**: [[r06_depth-boost]], [[r08_budget-depth]], [[r13_efficiency-insight]], [[r19_reward-shaping]]
- **object-centric / objectness**: [[r10_object-state-hash]], [[r16_object-click-prior]], [[r18_object-prior-full25]]
- **transfer-honesty / warm-start / proxy-inflation**: [[r29_warmstart-off]] (⚠️ card score is ~90% public-gold BC inflation; judge future rounds warm-start OFF)
- **neural-world-model / forward-model / planning**: [[r32_neural-forward-model]] (neural change-mask predictor — planning FIRES on unseen frames, beats state-uniqueness; needs confidence gate)
- **goal-inference / goal-directed-planning**: [[r33_goal-directed-planning]] (built + correct, but blocked by forward-model accuracy under per-game online budget)
- **budget**: [[r08_budget-depth]]
- **model-capacity / convergence-speed**: [[r24_bigger-cnn]] (bigger CNN FAILED — speed>capacity), [[r23_train-convergence]]
- **measurement / baseline / metric**: [[r11_breadth-measure]], [[r12_clear-rate-stable]], [[r13_efficiency-insight]], [[r17_full25-baseline]] (0.005 baseline)
- **deployment / submission / transfer**: [[r07_deploy-online-rl]] (`9c5d207`), [[r17_full25-baseline]]
- **DC22/TU93 walls / state-explosion**: [[r09_additive-planning]], [[r10_object-state-hash]]

## Full table
| Round | Axis | Verdict | Commit | Page |
|---|---|---|---|---|
| R05 | action-selection | FAIL (regress) | — | [[r05_planning-override]] |
| R06 | action-selection | FAIL (regress) | — | [[r06_depth-boost]] |
| R07 | deployment | KEEP | `9c5d207` | [[r07_deploy-online-rl]] |
| R08 | budget | KEEP | `850ee02` | [[r08_budget-depth]] |
| R09 | action-selection | FAIL (no gain) | — | [[r09_additive-planning]] |
| R10 | state-abstraction | FAIL (no gain) | — | [[r10_object-state-hash]] |
| R11 | measurement | 14/25 | `886b497` | [[r11_breadth-measure]] |
| R12 | measurement | 12/14 stable | — | [[r12_clear-rate-stable]] |
| R13 | insight | KEY: efficiency | `00b3ae4` | [[r13_efficiency-insight]] |
| R14 | action-selection | FAIL (no-op) | — | [[r14_noop-suppress]] |
| R15 | action-selection | FAIL (regress) | — | [[r15_dead-action-prune]] |
| R16 | exploration-prior | FAIL (depth hint) | — | [[r16_object-click-prior]] |
| R17 | measurement | BASELINE 0.005 | `0266634` | [[r17_full25-baseline]] |
| R18 | exploration-prior | FAIL (noise) | — | [[r18_object-prior-full25]] |
| R19 | reward-shaping | KEEP (first win) | `2c93fc1` | [[r19_reward-shaping]] |
| R20 | reward-shaping | TUNE (0.1 best) | — | [[r20_shape-coef-sweep]] |
| R21 | reward-shaping | NULL (off) | — | [[r21_progress-phi-off]] |
| R22 | reward-shaping | NULL (no gain) | — | [[r22_progress-phi-on]] |
| R23 | training-convergence | FAIL (sweep closed) | — | [[r23_train-convergence]] |
| R24 | model-capacity | FAIL (0.0019, slow convergence) | — | [[r24_bigger-cnn]] |
| R25 | exploration-prior | FAIL (sweep: 0.0051/0.0060 < card) | — | [[r25_object-prior-sweep]] |
| R26 | reward-shaping | FAIL (progress-Φ w=0.5/1.0 < card) | — | [[r22_progress-phi-on]] |
| R27 | world-model+planning | NULL (gate never fired) | — | [[r27b_planning-gate]] |
| R27b | world-model-planning | FAIL (planned=0, state-uniqueness wall) | — | [[r27b_planning-gate]] |
| R28 | depth-transition | FAIL (0.0121 < card) | — | [[r28_keep-across-levels]] |
| R29 | transfer-honesty | ⚠️ CRITICAL: OFF 0.0014 vs ON 0.0134 (90% is BC inflation) | — | [[r29_warmstart-off]] |
| R30 | transfer-honesty | shaping doesn't transfer (0.0015=0.0014) | — | [[r29_warmstart-off]] |
| R31 | transfer-honesty | budget doesn't transfer (6000=3000=0.0014) | — | [[r29_warmstart-off]] |
| R32 | neural-world-model | PARTIAL: planning FIRES (beats R10 wall) but 92% takeover crushes novelty | — | [[r32_neural-forward-model]] |
| R32b | neural-world-model | FAIL: conf-gate didn't help (0.0013) — wall is GOAL-absence, not activation | — | [[r32_neural-forward-model]] |
| R33a | goal-inference | heuristic goal 0.0013 ≈ baseline | 20afa66 | [[r33_goal-directed-planning]] |
| R33b | goal-inference | LLM goal 0.0013 = baseline — wall is FORWARD-MODEL ACCURACY | 20afa66 | [[r33_goal-directed-planning]] |
| R34 | metric-calibration | random=0.0000 on our harness → we BEAT random; '0.18/1.21' baselines were bogus | — | [[r34_metric-reexamination]] |
| R35 | neural-world-model transfer | dynamics transfer 52.4% (vs BC 0%); abs accuracy low → secondary | cc866eb | [[r35_forward-transfer]] |
| R36 | explicit-graph-search | WORKS: 0.0055 transfer-honest (4x), 8/25 L1, L2 @30k (CD82/VC33) — DEPLOYED | 5e4665d/2026e67 | [[r36_graph-frontier-bfs]] |
| R37 | explicit-graph-search | budget upside: full-25 8/25; L2 needs GF_GIVEUP raised | 08dfbb5 | [[r36_graph-frontier-bfs]] |
| R38 | graph-efficiency | salience tiering: TN36 6x, mean 0.0064, no loss | cd90a4f | [[r36_graph-frontier-bfs]] |
| R48 | llm-selection | research: Qwen3-Coder-30B-A3B primary (pending measured bench) | — | [[r48_llm-selection-ewm]] |
| R49 | llm-selection | local ceiling: 14b best-exact=0.100 > Q3-30b-coder 0.033 (quant damage) > 8b 0; original-30b go/no-go deferred to Kaggle 96GB | a12e760 | [[r49_ewm-bench-partial]] |
| R49d | llm-bench-full18 | 14b full-18: exact 0.078/0.089 (8/18 games >0); 3 of 7 graph-blocked games show EWM traction (dc22/g50t/sc25); launchd = durable runner | — | [[r49_ewm-bench-partial]] |
| R49e | llm-bench-full18 | gpt-oss-20b full-18: exact 0.239/0.256 = 3x 14b; sb26 1.00, 10/18 >0; gpt-oss-120b promoted co-primary | — | [[r49_ewm-bench-partial]] |
| R49f | llm-bench-full18 | gemma4-26b-a4b full-18: 0.144/0.244; unlocks su15/re86/tr87/ka59/sk48 (gpt-oss zeros); union 15/18, graph-blocked 6/7 traction; late-round regression → keep-best fix needed | — | [[r49_ewm-bench-partial]] |
| R50 | llm-bench-cloud | Kaggle-identical HW (96GB): gemma4-31b-q8 0.433/0.494 LEADER > gpt-oss-120b 0.272 > 26b 0.239 > qwen3-coder ELIMINATED; held-out leakage in refinement found+fixed | aea406d | [[r50_cloud-bench-k3]] |
| R50b | llm-bench-honest | HONEST K=8: gemma4-31b-q8 0.133/0.139 = deploy candidate ≫ gpt-oss-120b 0.039 (7x leak-inflated); ar25 0→0.80 genuine climb; ⛔ pre-R50b absolutes are leak-inflated | — | [[r50b_honest-k8]] |
| R51 | ewm-quality | few=40/prior sweep: no single config > f15 0.133, BUT per-game config-UNION 0.211 (1.6x) → adaptive multi-config synthesis; 10/18 stable zero-set ⛔ no more config sweeps for those | — | [[r51_fewshot-prior-sweep]] |
| R52 | ewm-integration | GF_EWM hook built (default OFF) + measured: score delta +0.0000 NULL — no-change pruning redundant with empirical self-loop learning; runtime fit 0.357 (3/24 > gate); R53 = goal-conditioned WM | pending | [[r52_ewm-integration]] |

- **graph-search / hud-masking / frontier-bfs**: [[r36_graph-frontier-bfs]] (the deep-level axis; offline env.step ~1000+/s discovery)
- **forward-model transfer / pretrain**: [[r35_forward-transfer]] (dynamics 52.4% vs BC 0%; pos_weight collapse fix)
- **metric-calibration / baselines**: [[r34_metric-reexamination]] (random=0.0000 measured; real RHAE top=0.1258; purge the bogus 0.18/0.25/1.21)

- **llm-selection / executable-world-model**: [[r48_llm-selection-ewm]] (candidate research; verdict superseded by R50), [[r49_ewm-bench-partial]] (local 3-way; ⛔ 18GB Ollama models crash the 24GB dev Mac), [[r50_cloud-bench-k3]] (Kaggle-identical HW; leakage fix), [[r50b_honest-k8]] (HONEST baseline: gemma4-31b-q8 0.133/0.139 deploy candidate; ⛔ pre-R50b absolutes leak-inflated), [[r51_fewshot-prior-sweep]] (config-UNION 0.211 → adaptive synthesis; stable zero-set 10/18), [[r52_ewm-integration]] (GF_EWM runtime hook default-OFF; no-change pruning NULL; R53 = goal-conditioned WM)

## The two standing conclusions
- ⛔ **Do NOT re-try action-selection tweaks** — 8 rounds failed; the novelty learner's action
  choice is a tight local optimum.
- ✅ **Iterate the reward-signal / potential axis** — the only lever that opened DEPTH (R19).
