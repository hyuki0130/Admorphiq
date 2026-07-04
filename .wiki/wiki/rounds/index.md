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

## The two standing conclusions
- ⛔ **Do NOT re-try action-selection tweaks** — 8 rounds failed; the novelty learner's action
  choice is a tight local optimum.
- ✅ **Iterate the reward-signal / potential axis** — the only lever that opened DEPTH (R19).
