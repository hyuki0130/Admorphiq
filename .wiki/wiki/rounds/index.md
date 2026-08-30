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
| R53 | harness-architecture | 6 generic tools RE-IMPLEMENTED (graph/world_model/dealias/deadsig/paint/llm_goal) on a shared Tool contract + UnifiedAgent self-improving loop (signature → minimal wiki slice → pick tool OR write code → feed-back → re-decide on stall); code-agent alone re86=0/8 → frontier needs the combined loop; 655 tests | b533ca4 | [[r53_unified-harness]] |
| R54 | vision-llm-as-policy | Built the Reki/forge lever: labeled frame image → multimodal LLM picks ONE JSON action/turn (legal-masked) + reflection memory + dead-signature avoidance + 1-4 plan queue + JSON self-repair; additive `--agent vlm`, 13 tests. Local measure SUSPENDED — gemma4-26b proxy ~26s/changing-turn (su15 30-action probe >700s); policy-quality validation → Kaggle 31B phase B | pending | [[r54_vision-llm-policy]] |
| R55 | code-repl-agent | Duck-style code-REPL offline core (Codex design) + Kaggle deployment: transcript/replay + segmenter/tracker + turn-packet builder + stateless subprocess Python sandbox/inspection API + action governor + GoalAuditor. Kaggle-run: su15 first LLM clear via the audit, then matched12 GATE FAIL falsified the audit as non-load-bearing (base agent already clears su15; audit costs throughput, lost r11l). Engagement 2×2 (ACTION_FIRST adopted, REPEAT_FEEDBACK dropped) confounded cross-session by vLLM temperature=0.0 non-determinism (diagnosed via turn-by-turn replay, not a config bug); found+fixed a sandbox/turn-packet topology-schema KeyError bug (7 verbatim repros). basenav PUSH-READY, HELD on GPU-quota decision | d6c339a | [[r55_code-repl-agent]] |
| R56 | generic-kernel-library | 9 namespace-safe kernel modules (rewrite/shapes/paths/motion/regions/canonical/geometry/parse/gf2 + split_fused_frame de-fusion), 45 exports, 134 tests; script25 quarantined-adapter scoreboard + AST quarantine lint; **ft09 COMPLETE 6/6 live, 100% RHAE, 88 total actions, every level at the 1.0 cap** (glyph-decode grammar, GF(2) control-glyph solver); **tr87 3/6 live (L0-L2), every clear at the 1.0 cap** (7-step Codex-gated grammar arc); sb26 3/8 live (L4 falsified-and-banked, open question); **lp85 1/8 live, 2.48% (L1 18a vs 17 human, near the 1.0 cap)** — gold-replay divergence found the root cause was candidate GRANULARITY (a rare region can hold several functionally distinct pixels, not one clickable centroid), then a round-robin probe-queue redesign cut L1 from 69→18 actions; m0r0 1/6 live via a genuine JOINT-STATE planner (every action moves a self AND partner region simultaneously; `configuration_path` hill-climbs the joint state, replacing an earlier single-agent "chase a moving goal" framing that stayed 0/6); vc33 1/7 live (new escalating click-counter mechanic); tu93 2/9@3000a baseline banked; **dc22 BANKED at 0/6** — gold's own solution is PROACTIVE/state-gating, this adapter's whole walk-stuck-probe-learn architecture is REACTIVE, an architectural mismatch not a missing heuristic (two independently-sound fix attempts both measured 0/6); ka59 push mechanic measured working (wall-crossing verified) but banked 0/7 (planning-integration gap); su15 IN-FLIGHT (6 falsification iterations, best GAME_OVER=11, near-merge 1.9px); sp80 IN-FLIGHT characterization-only (2 hypotheses falsified: position-delivery, transform-count; stable 4-transform GAME_OVER cycle, non-monotonic colour8 count means something is consumed each loop; no adapter built yet). Diagnostic method of the round: GOLD-REPLAY DIVERGENCE (replay a level's gold trace against the adapter's own decision logic to find the exact step they diverge) cracked dc22's architecture question, lp85's granularity bug, and su15's perception bugs alike | b67cb39/68b802a/6e238de/3e7391a/204aab2/f406d55/a3a6644/ae8fd95/efaf004/362c672/0e59f88/95c27c4/de0510e/4d9472f/569a620/9e7f474/b36fd8a/fc36602/6f81df7/b9b35cd/a314bee/ac8c177/f4e8b11 | [[r56_generic-kernels]] |
| R59 | depth-wave-2 | Parallel 6-lane team day (2026-07-16) on the R56 base: **official card 18.02% → 21.56%** (r59s1 full-25 parallel @5000 ceph-build, HEAD 9b8e2e8, all 25 games matched lane predictions exactly). m0r0 1/6→**5/6 @0.7143, all levels 1.000** (L5 momentary pressure-plate gates decoded, L5 48a vs human 500); bp35 0/9→**1/9 first-ever generic clear** (faithful sim + visited-aware frontier exploration); sk48 3/8→4/8 + **L4 CLOSED single-control-unsolvable** (lockstep-faithful sim + exhaustive 94,921-state reachability, the sk48-L4 analogue of an honest bank); post-HEAD landings su15 3/9→**4/9 @0.1923** (enemy-in-sim, euclidean fruit-match fix inverted the lure_base=20 belief) and re86 2/8→**3/8 @0.1162** (separation-by-motion + max_coverage_offset kernels) → current arithmetic ≈22.25%; ls20 L5 moving-changer decoded+validated (43-action plan designed); lp85 twist-topology kernel + detection solved (residual: σ/σ² multi-step ordering); re86 L4 changer/recolour + m0r0 L6 block-pin×gate×desync parked as ready-specs | 9b8e2e8 + bc04e63/6b6ad2e/b2128c9/36d23cd/3b6c11c/0197b8b/fa8e3bc | [[r59_depth-wave]] |
| R57 | win-condition-typology | MEASUREMENT-ONLY: 8-type typology (T1-T8) named as observable predicates over R56 kernels, mined from 67 gold-trace level-up events across 25/25 games (24 frame-verified, tr87 source-labeled only); coverage caveats: only 5/25 games have a complete captured win sequence, tr87 has zero frame evidence (circularity risk), R11L unresolved T7-vs-T8 | 0b9e5f9 | [[r57_win-condition-typology]] |
| R58 | explanation-layer | ON HOLD (2026-07-15 dawn): Codex protocol-compiler verdict (typed intents + enforced SELECT→FILL→COMPUTE→CONSUME→VERIFY state machine, not a bigger wiki); Navigation Vertical Slice v0 (P0/P1) + GoalLedger (P2, 6/8 R57 types as kernel-only detectors) built; real-trace validation found ranking was fixed-pipeline-order not evidence (TOP1 38.1%/TOPK 57.1%, 21 games) → strength-scoring fix (TOPK→76.2%) but TOP1 regressed to 28.6% (cross-detector calibration) → floor-anchoring fix CONFIRMED calibration correct but TOP1 stayed flat → residual gap reframed as detector SELECTIVITY, not calibration → **Codex verdict #2**: replace scalar ranking with evidence TIERS (affordance/behavioral/predicate) + footprint ADJUDICATION (shared/subsumed/independent) + union-find CAP + rebuilt `pattern_match` (lattice/congruent-pair) → tuning round #3 rebuild: TOP1 28.6%→42.9% (now diagnostic-only), recall held 71.4% → transition-window validation found evidence PROMOTION too permissive (19/24 games, coincidental board-spanning overlap, `tn36` false-confident to predicate) and no DEMOTION path existed → tuning round #4: confinement-based promotion (≥50% diff inside footprint, non-board-spanning) + contradiction demotion (≥2 steps→affordance, ≥4→margin floor); promotions 19/24→4/24, `tn36` demoted tier1→tier3, `ft09`'s stencil-confined case survives, recall unchanged 71.4%. GoalLedger now HOLDS pending agent25 A/B (gated on Kaggle engagement results) or new Codex input; P3 + other mechanic playbooks still open | 5ceb5ec/0f105e0/70686d1/0a31279/8166efd/29a9ca8/2fe6c21/c679056/698e050/a1f418b/9c41887 | [[r58_explanation-layer]] |

- **vision-llm-as-policy / multimodal / pick-json-action**: [[r54_vision-llm-policy]] (Reki/forge lever built: labeled-image renderer + ollama multimodal + reflection/dead-signature/plan-queue policy loop; model-agnostic VLM_MODEL; local proxy latency → Kaggle 31B validation)
- **code-repl-agent / duck / qwen3.6 / transcript-replay / sandbox / turn-packet / action-governor / matched12 / engagement / action-first / repeat-feedback / vllm-nondeterminism / topology-schema-bug / basenav / goal-auditor**: [[r55_code-repl-agent]] (Codex-designed code-REPL offline core: transcript/replay foundation, segmenter+tracker with stable ids, turn-packet YAML + falsifiable memory, subprocess sandbox + inspection API, action governor with macro stop-on-surprise, GoalAuditor; Kaggle results: su15 first LLM clear via the audit then FALSIFIED by matched12 (base agent clears su15 unaided, audit is throughput-negative and cost r11l); engagement 2×2 ADOPTED action-first (parse failures 8→1) and DROPPED repeat-feedback (worsens rejections); base/control arms scored 0/32 for a cross-session reason, not a config bug — see [[../lessons/vllm_cross_session_nondeterminism_20260715]]; found+fixed a topology.holes sandbox/turn-packet schema mismatch that KeyError'd 7 times; Round-2 2×2 ablation pairs this vs [[r54_vision-llm-policy]])
- **generic-kernels / namespace-safe / script25 / agent25 / dual-scoreboard / declared-intent / primitive-firewall / tr87 / ft09 / dc22 / lp85 / m0r0 / gold-replay-divergence / learned-operator / configuration-path / probe-validity / 25-adapter-coverage**: [[r56_generic-kernels]] (Codex verdict: reject solver-card 25/25, adopt a pure-computation kernel library + script25(expressiveness)/agent25(competence) dual scoreboards + declared-intent offloading; 9 modules/45 exports/134 tests; quarantined script25 adapter zone with AST-enforced no-hardcoding lint; ft09 glyph decode falsifies the R16-R18 coupled-stencil reading, live COMPLETE 6/6; tr87 rewrite-grammar crack, live 3/6; lp85 gold-replay candidate-granularity bug, live 1/8 near-human-efficient; m0r0 joint-state `configuration_path` planner, live 1/6; dc22 BANKED at 0/6 — proactive/state-gated win vs reactive walk-stuck-probe, architectural mismatch; master diagnostic = GOLD-REPLAY DIVERGENCE. **Expansion sprint (2026-07-15 afternoon): 25/25 adapter coverage** (was 10; 12 new adapters in one parallel-teammate afternoon) — new clears ar25 2/8, ls20/sp80/cn04/r11l/sc25 1/6-1/7, re86 1/8 (first generic, brittle ceiling 6/8), s5i5 1/8 (first frame-only); honest 0-banks with decoded mechanics sk48/wa30/g50t/bp35/tn36/lf52. **Learned-operator + `configuration_path` = 2/2 super-human levels** (reflection kernel ar25 L0 23a vs 32 human score 1.0; flow kernel sp80 L0 10a vs 39 human score 1.0). Uniform-depth thesis: blind explorers clear single-goal reachability, never chained multi-subgoal plans → every 0-bank's reopen points at a learned-operator kernel. Two falsified reopen pointers banked docs-only: tn36 (bits gate multi-frame interpreter trajectories) and bp35 (momentum/hidden-velocity aliases the frame-key graph, exit recedes). Methodology lesson [[../lessons/probe_validity_20260715]] — a probe only measures what its action actually EXERCISES; base fix `f586fd3` surfaces ACTION7; CPU bench env now `ceph-build` (byte-exact repro of GCP, GCP credits exhausted). **Evening depth phase (2026-07-15): faithful state-models push DEPTH** — sk48 0/8→3/8 @0.1667 (move-sim+A*, edge-snake parse), lp85 1/8→3/8 @0.1637 (ring-permutation planner, L2/L3 capped 1.0), su15 0/9→3/9 @0.1035 (vacuum-pull merge decode), sb26 8/8 @0.846 (portal-DFS sim), cd82 6/6 @0.98, dc22 0/6→**1/6** @0.0272 (gated product-graph — SUPERSEDES the earlier 0/6 bank), ka59 1/7 @0.0205, tu93 0.0002→0.0028 (goal-directed frontier, 11.6×); cn04 verified **1/6** @0.0309 (NOT the interim "2/5"). Pattern named [[../lessons/faithful_offline_simulator_20260715]]; measurement-integrity lesson [[../lessons/false_claim_verification_20260715]] (r11l nonexistent-commit incident); all numbers SUMMARY-verified)
- **depth-wave / r59s1 / 21.56% / m0r0 / pressure-plate / bp35-first-clear / frontier-exploration / su15 / enemy-in-sim / re86 / separation-by-motion / sk48-l4-closed / reachability / lp85 / twist-topology / ls20 / moving-changer / parallel-lanes**: [[r59_depth-wave]] (6-lane bounded-pass team day; official card 18.02%→21.56% + post-HEAD ≈22.25%; faithful-sim/learned-operator wave 2; honest closes: sk48 L4 topologically unsolvable, su15 L4 single-lure class airtight-negative; ready-spec parks: re86 L4 changer/recolour, m0r0 L6 joint desync)
- **win-condition-typology / goal-evidence / gold-trace-mining / t1-t8**: [[r57_win-condition-typology]] (8 observable-predicate types mined from real gold traces across all 25 games; feeds R58's GoalLedger)
- **explanation-layer / protocol-compiler / typed-intents / goal-ledger / falsification / evidence-tiers / confinement-promotion / contradiction-demotion**: [[r58_explanation-layer]] (harness-enforced state machine so a weak offline model can't ignore a kernel result or forget invocation syntax; GoalLedger turns R57's typology into 6 executable kernel-only detectors — tuned for calibration, then Codex-redesigned into evidence tiers + footprint adjudication, then hardened with confinement-based promotion and contradiction demotion after real-trace validation found the naive promotion test fired on 19/24 games via coincidental overlap; ON HOLD pending agent25 A/B)

- **graph-search / hud-masking / frontier-bfs**: [[r36_graph-frontier-bfs]] (the deep-level axis; offline env.step ~1000+/s discovery)
- **forward-model transfer / pretrain**: [[r35_forward-transfer]] (dynamics 52.4% vs BC 0%; pos_weight collapse fix)
- **metric-calibration / baselines**: [[r34_metric-reexamination]] (random=0.0000 measured; real RHAE top=0.1258; purge the bogus 0.18/0.25/1.21)

- **harness / unified-agent / generic-tools / self-improving-loop**: [[r53_unified-harness]] (6 tools re-implemented on a Tool contract + UnifiedAgent retry loop; minimal signature-targeted wiki context, HARNESS_CTX sweep lever; code-agent alone re86=0/8 → frontier needs the combined loop)

- **llm-selection / executable-world-model**: [[r48_llm-selection-ewm]] (candidate research; verdict superseded by R50), [[r49_ewm-bench-partial]] (local 3-way; ⛔ 18GB Ollama models crash the 24GB dev Mac), [[r50_cloud-bench-k3]] (Kaggle-identical HW; leakage fix), [[r50b_honest-k8]] (HONEST baseline: gemma4-31b-q8 0.133/0.139 deploy candidate; ⛔ pre-R50b absolutes leak-inflated), [[r51_fewshot-prior-sweep]] (config-UNION 0.211 → adaptive synthesis; stable zero-set 10/18), [[r52_ewm-integration]] (GF_EWM runtime hook default-OFF; no-change pruning NULL; R53 = goal-conditioned WM)

## The two standing conclusions
- ⛔ **Do NOT re-try action-selection tweaks** — 8 rounds failed; the novelty learner's action
  choice is a tight local optimum.
- ✅ **Iterate the reward-signal / potential axis** — the only lever that opened DEPTH (R19).

- **bounded-frontier / queue-scan / open-bounded / r11l-placeability / frontier-exhausted**: [[r84_bounded-frontier-scan]] (task #108 audit of 10 non-conquered games; verdict: bounded frontier essentially exhausted — 3 SETTLED-⛔ tr87/sk48/sc25, 6 MULTI-SESSION dc22/wa30/ar25/vc33/bp35/sp80, 1 marginal OPEN-BOUNDED = r11l L1 learned-placeability. **sp80 row CORRECTED by [[r92_sp80-l2-premise-correction]]: MULTI-SESSION for multi-piece tracking, NOT angled deflectors.**)
- **sp80-l2 / flow-coverage / multi-source / multi-piece / angled-deflector-misdiagnosis / connected-components-merge / piece-tracking / premise-check**: [[r92_sp80-l2-premise-correction]] (task #117 Pass 1 decode; PREMISE FALSIFIED — sp80 L2 has NO angled deflectors (the cited tags `odioorqnkn`/`trurgcakbj` exist nowhere in source; real angled `tuvkdkhdokr-*` are L5/L6 only). L2 = straight-block multi-SOURCE (3 streams) multi-PIECE (4 blocks) coverage, SAME physics as L0/L1. Real wall = self-inflicted perception merge: pipeline detects pieces AFTER probe/restore leaves the auto-selected block adjacent to a neighbour → 4-connectivity fuses 2 blocks → 3 "pieces" not 4 → executor can't move the phantom merged blob → 0 spills committed → graph burns budget. Planner + flow model measured OK (covering plan found even at 500k states). Build spec: snapshot 4 pieces from the PRISTINE entry board, track via unique colour-9 selection, joint-plan, verify multi-source `simulate_flow` faithfulness, L2-signature gate. Floor 2/6 @0.1429 untouched)
- **agent25 / kernel-bridge / kernel-api / tool-calling / route-valid / guess-code / gpt-oss-offline / TIKTOKEN_ENCODINGS_BASE / shelved**: [[r92_agent25-kernel-bridge]] (the "LLM composes kernels at runtime" axis tested to its cheap end and SHELVED for the gemma4/qwen tier: kernel bridge (K.* in the code sandbox) + few-shot + qwen-vs-gemma4 comparison (uptake 1 vs 23 K.-replies, clears 0 both) + Phase-2 transition kernels (usage DROPPED 23→2; more kernels hurt) + native tool-calling v6 (route_valid==route_calls 100% on all 4 smoke games — interface FIXED — yet 0 clears; verbatim code = blind guess-probes, 0 K.*/0 transitions across 120+10 ON-arm blocks). Context/output/exposure/model-swap all measured-eliminated; dual-scoreboard clincher: m0r0 is a script25 conquest (1.0) so the kernels CAN solve it. gpt-oss-120b offline vocab blocker SOLVED+verified (TIKTOKEN_ENCODINGS_BASE + plain-named o200k/cl100k tiktoken files, dataset jaehyukhyun/tiktoken-encodings-offline) — reserved for the R93 bounded 2-case A/B only)
- **agent25 / adapter-template / game-cards / simdfs / sb26-sk48 / paired-holdout / upper-bound-gate / template-size-law / distill-small / d5-skel**: [[r94_adapter-template]] (the user's escalation of the surviving R93 thesis: conquered adapters as patch templates. GATES ALL PASSED — the user's upper-bound requirement PROVEN: the sb26 simdfs card reproduces the FULL conquest through the LLM patch sandbox (8/8 @131a, vs adapter 170; 4-rung trace-diagnosed fix ladder; adapter parity 8/8 @0.846 exact throughout). lp85 = pair-INELIGIBLE (frozen rule: action-boundary expressibility — its conquest is time-series). D5 v3 (first clean run): the 75KB family card ADAPTS (626s) but yields a near-inert solver on sk48 (3st/7tr) while the 6.6KB mismatch card adapts into 71st/309tr and WINS → **design law: template SIZE/SPECIFICITY dominates family match — distill family cards SMALL** (vindicates the compact 특징→해결법 game-card framing over full-adapter provision). **D5-SKEL FINAL (size-controlled): the family skeleton ALSO loses** — the 8.2KB simdfs_skel adapts cleanly (208.7s, 0 exec errors) yet stays near-inert on sk48 (3st/55tr, noop 0.999) while the generic card replicates 71st/309tr a FOURTH deterministic time → combined law: on an out-of-family holdout neither engine size nor compact family mechanics transfers; generic probe-first wins at every size (caveat: sk48 flagged schema-inexpressible by the R95 Codex review; in-family reproduction DID pass via the sb26 gate). ROUND CLOSED; road = generic card + R95 hypothesis-DSL discriminative selection, `docs/design_hypothesis_dsl_r95.md` v2.6)
- **agent25 / hypothesis-dsl / discriminative-selection / enum-vocabulary / equivalence-class / ft09-sc25 / fallback-ladder / self-extension / two-model / prereg**: [[r95_hypothesis-dsl]] (the post-R94 road: model hypothesizes via closed-choice DSL, harness codes. Design v2.6 twice Codex-consulted (NO-GO v1 corrected: family sub-banks, sound PASS/CONTRADICTED/UNKNOWN verifier, oracle gate, R95a cheap pre-test first; vocabulary consult: reach_mode question, typed guard clauses, ID-only binding, Q5 composition = gap DETECTION not expressibility, 15-game inexpressible backlog). 5-tier fallback ladder incl. DSL SELF-EXTENSION (user directive; EWM-measured basis) with fork-and-patch demoted to final LLM tier; two-model rule (gemma4 + gpt-oss, paired, x3 reps). R95a COMPLETE, thesis CONFIRMED PAIRED: BOTH gemma4 and gpt-oss pass ft09 3/3 picking the EXACT oracle with true-discriminator evidence; both identically failed sc25 on a chrome artifact -> #125 generic HUD-edge masking (diagnosis CORRECTED: right-edge click-budget bar, not a cursor) -> masked rerun sc25 0/3 -> 3/3 exact-oracle = FIRST CLOSED DEFECT CHAIN through the hypothesis channel. No model difference. R95b COMPLETE THROUGH STEP vii — **FIRST FULLY AUTONOMOUS agent25 CLEARS, CONFIRMED PAIRED** (e1289c7): full stack built in one day per the Codex plan (contract 34553c5 / schema 3c1b142 / grounding 925d26f / verifier 05b5b0c matrix-8/8 / compiler 25a129a 4-click-fixture / live driver d8f3421); both oracle gates PASS 3/3 (ft09 idx0+idx1 at 4+8a = human baseline; sc25 cast+handover under the frozen contract criterion); MODEL stage: gemma4 6/6 PERFECT exact-oracle from live evidence, gpt-oss ft09 2/3 (wrong stencil pick CAUGHT LIVE by the verifier, zero actions wasted) + sc25 3/3 (execution-equivalent absolute mutant on the uniform base — the thin-evidence signature; second soft divergence, no nomination). Zero adapter code / zero game ids in the runtime path. **ROUND CLOSED — CONTRACT COMPLETE (2026-07-23): fill mode ALSO passes (ft09 3/3 x4 rounds + sc25 3/3 after the v3-v8 defect ladder; final root cause = histogram-notation misparse captured verbatim from the model's reply via the echoing_llm observability wrapper → prose fix; lesson prompt_notation_misparse_20260723)**. Next round = family expansion per the 15-game backlog)
- **detection-dispatch / adapters25 / port / false-positive-gate / probe-detection / control-scheme / card / submission / ceiling / first-frame-limit**: [[r99_detection-dispatch]] (the submission card's depth was locked behind `script25.py`'s `game_id` selection; this round moves nine adapters onto the card by recognising each mechanic FROM THE FRAME. **0.0566 -> 0.2771, 4.9x, zero regressions**, every port landing EXACTLY on its ceiling and the shipped configuration matching the benched one game for game. The adapters do NOT cheat — their entry points take no game identity — so the port is a dispatch change, not a rewrite; what is hard is SPECIFICITY, and ft09's first detector false-positived on 9 of 24. A detector ships only at a MEASURED 0/24: the gate refused sb26 at 2/24, predicted an s5i5 regression, and the run produced exactly it (0.0278 -> 0.0000) — it protects TRANSFER, not the proxy score, since on the public 25 the unsafe detector is strongly net-positive. Write a detector as the mechanic's CONTROL SCHEME plus the entities it cannot do without, requiring BOTH members of a pair; ⛔ never ask the SOLVER whether it copes, which inherits its permissiveness. Probe detection adds ONE shared action for mechanics a still frame cannot show (m0r0: static 18/25 candidates -> 2 with a probe -> 1 with its mirror pair; ⚠️ probe the axis being MIRRORED, and the probe costs nothing — 6/6 in 199 actions fresh, 198 after). ⛔ PARKED: lp85's ring mechanic appears at LEVEL 2 while dispatch decides at L0 — **first-frame dispatch cannot see a mechanic that only appears deeper**, and m0r0's probe worked only because a direction key needs no aim where a click must choose where to press. Build provenance ships WITH the card this time. **SUBMITTED 2026-08-25 16:19 UTC** (`55774529`, kernel v3 @ 20aa652); reading criteria FIXED before the score. **Three axes then CLOSED by measurement, two of them against my own reading**: (a) further PORTS ⛔ stop at nine — every remaining port summed is +0.0524 while losing cd82 to one wrong detector is −0.0379, and cd82's 0.9463 comes from the FALLBACK path so a misfire takes the game from the solver that already conquers it; (b) DEPTH ⛔ bounded frontier exhausted per R84 — sk48 L4 has a 94,921-state proof, re86 L8 is unwinnable as modelled, su15 idx6 hits a sub-pixel-perception wall (⚠️ I first quoted an OLDER su15 entry as reopenable; the log carries several entries per game and `scripts/round_lookup.py` now orders them by date); (c) EFFICIENCY ⚠️ REOPENED — I closed it on vc33 (every click changes the frame: 1,406/1,406 first, 2,179/2,179 re-clicks, so no waste and the gap is mechanic understanding) and sk48 is the OPPOSITE regime (**31/488 first clicks change anything, 6%; 155/715 re-clicks, 22% — 94% of clicks are inert**), where removable waste genuinely exists and skipping a cell already shown to do nothing needs no mechanic knowledge. WIDENED to eight games and CLOSED on the distribution: **five of eight land 100% of clicks** (tn36, lf52, r11l, sp80, vc33), m0r0 is 42%, sk48 5%, tu93 clicks not at all — so the 100% regime is typical, the gap is mechanic understanding, and sk48/m0r0 are outliers already covered by their ports. ⛔ The path there is the lesson: closed on ONE game, reopened by its counter-example, closed again by the distribution — the first closure reached the right answer for a reason not yet good enough, which is not the same as being right. **RUNTIME solved**: per-game budget 100,000 -> 4,000 is measured IDENTICAL at 0.2772 while cutting 110-game projection from ~213 min to ~26 (⛔ but a cap at 500 would destroy 1.0 of real score — re86 L7 clears at 588 cumulative actions, so the cliff had to be LOCATED). ⚠️ Five deployment-path defects were invisible to every local score [[../lessons/deployment_path_is_not_the_measured_path_20260826]].)
- **agent25 / family-expansion / flow-deflection / place-then-propagate / sp80 / response-table / reference-propagator / gated-enum / inert-slot / equivalence-class / near-ood / two-phase-commit**: [[r98_flow-deflection]] (family #3, PIVOTED to sp80 after the design review showed the backlog has no clean sokoban oracle. Central claim MEASURED: the transition model IS the simulator — the reference propagator built from the response table reproduces the engine's outcome on all 12 reachable placements and the CELL-EXACT trajectory on both probe placements. Oracle certified LIVE (idx0 clears in 4 actions vs 39 human; one commit exposes 20 animation layers). Codex schema consult CONDITIONAL GO, six corrections bound; two open questions CLOSED BY MEASUREMENT — **hazard-fatal CERTIFIED** (+2 fills every sink and fails, +3 fills the same and advances, differing only in hazard contact) and **all-vs-any UNKNOWN with a PROOF OF ABSENCE** (no placement fills a strict subset). Gated-enum test demoted `own_flow` and `boundary` as INERT, made `piece_propagation` verifier-only, and recorded `both_flanks` as data-indistinguishable. **OOD controls SWAPPED by measurement**: the family's tell is a multi-layer scripted consequence from one action — re86 bursts 1 and is unrelated, tu93 bursts 8 and becomes near-OOD. Contract FROZEN: idx0 only, 20-action cap over a 9-action certified path. schema_flow.py landed, all 9 mutants certified. **LIVE ORACLE GATE 3/3 PASS end to end** — discovery→grounding→verify→compile→execute clears idx0 in 10 actions / 2 commits vs a 20/3 cap, same plan every run. Grounding (the pre-declared 40% risk) earns 10/10 slots from observation alone and its recovered trajectory EQUALS the propagator's prediction cell-for-cell; four measured traps fixed on the way, incl. the R92 4-connectivity merge in a new guise (an oscillating edge band merging with the targets) and a scale-inference rule that first accepted a scale twice too large. `control_mode` recorded as an UNESTABLISHED PREMISE — unobservable at idx0 because the single piece starts pre-selected. Verifier reproduces the frozen mutant table on live evidence with no disagreement. Model-stage driver self-tests 6/6: wrong picks blocked at ZERO executed actions, equivalence-class answers scored correct, leak guard clean; the inert-slot mutants had to be excluded from the select list because they serialize identically to the truth. **MODEL STAGE MEASURED 2026-08-23: SELECT CONFIRMED ON BOTH CONTRACT MODELS** — gemma4 3/3, gpt-oss 3/3, and the newly released qwen3.8-27b 3/3, each picking the EXACT truth every run then clearing the level in 10 actions / 2 commits (oracle-gate performance reached by the model). FILL passed outright by gpt-oss-120b 3/3 with a perfect 7-of-7 hypothesis; gemma4 misses exactly ONE slot and does so self-contradictorily (correct hazard POLICY, incompatible hazard RESPONSE), which is our encoding splitting fatality across two slots — recorded as a schema finding to be measured separately, NOT patched to move a verdict. The first prompt version produced the round's sharpest lesson: three independent models unanimous on the same three wrong values across nine runs while getting the other three right = a PROMPT defect, not a model verdict [[../lessons/unanimous_wrong_answers_are_a_prompt_defect_20260823]]; fixing it took gpt-oss from 0/3 to 3/3 on BOTH stages. **MODEL STAGE RE-MEASURED AT NINE RUNS 2026-08-25** after gpt-oss returned 3/3 then 0/3 on the SAME prompt — three draws cannot separate a rate from an accident, so `R98_RUNS` was raised 3 -> 9. Result: select gemma4 9/9, qwen 9/9, gptoss 8/9; fill/fused/explicit gemma4 0/9, qwen 0/9, **gptoss 9/9 / 9/9 / 8/9**. Every model is DETERMINISTIC on the decisive slot and they disagree — gptoss `terminate_fatal` 27/27, gemma4 and qwen `terminate_local` 27/27 — with ONE distinct board throughout, so the grounding is identical and the split is entirely the models'. gptoss's two 8/9s are verifier UNKNOWNs on a data-indistinguishable objective axis, not wrong answers. ⛔ **The "encoding splits fatality across two slots" reading is REFUTED**: qwen answers BOTH slots coherently (`neutral` policy beside `terminate_local`) and is still wrong, so incoherence is gemma4's symptom and not the cause; the fused encoding, which asks once, is 0/9 for both; and naming the barrier contact explicitly is 0/9 too. FILL is a ONE-SLOT exam and the slot is hazard fatality. **PROPAGATOR NOW EXACT ON THREE LEVELS** (idx0/idx1/idx2 cell-for-cell; corpus 93 -> 12) after two instrument fixes and one grounding fix: the capture paired a board with a spill that ran on a different layout (engine flow passed through 1/1, 2/3, 3/4 of the recorded pieces where a valid board has ZERO), captures only ever fired when a level FAILED (which is why every board came from idx3), and `_obstruction_regions()` seeded on BACKGROUND-coloured blockers so `_regions` returned the 187-cell background as one region and the mouth split carved a 17-cell "target" out of empty space — 100% of idx2's error. The whole remaining residual is ONE genuine step-off refusal at `(4,11)`; 17 distinct events say the engine always steps off, so there is NO step-off rule to find from this corpus. ⛔ `WALK_REACH` is supported only as "at least 2" (reach 1 -> 132, reach 2/3/99 -> 12, indistinguishable) — stop citing 2 as a measured optimum. The four instrument failures behind all of this are written up as their own page: [[../lessons/instrument_validity_20260825]] — NINE failures: validate the corpus before fitting to it, count EVENTS not instances over sibling boards, read the CONSUMER not the guard, a probe that ACTS is a change, a scored prompt can FORBID the thing being diagnosed (JSON-only leaves nothing to read), a diagnostic prompt that WITHHOLDS the evidence gets a confabulation, and — three times in one afternoon — the CHECKERS built to catch the others were themselves wrong on their first run, so run a checker on input whose verdict you already know, in BOTH directions. **FAMILY SCOPE MEASURED (2026-08-25), which is what a fourth expansion reads first**: widening the near-OOD screen from 8 hand-picked candidates to all 25 games finds the family's structural tell — a scripted multi-tick consequence from ONE action — on TEN of them, two bursting harder than sp80 (sb26 42 and lf52 27 against sp80's 22, both on ACTION5, the same commit-shaped action; then sc25 22, cd82 15, g50t 9, tu93 8, bp35/ft09/su15 5, r11l 3, and fifteen at 1). ⚠️ But burst does NOT predict readability: given the gate's own discovery, **0 of 5 candidates assemble a board** — sb26, lf52, cd82 and g50t fail all six slots while sc25, which merely ties sp80's burst, reads THREE of six (pieces, emitters, trajectory) and fails on `sink_candidates`, `barriers`, `initial_direction`. So the harness reads its own game and no other, and the ten-game pool is a list of games to TRY rather than near-members. The entry cost of a second member, diagnosed on that nearest miss: sc25 is a **64-cell board at scale 1** where sp80 is 16 cells at scale 4, so the top-row source reading degenerates to 128 "emitters" against 1, and its spill registers 5 non-empty frontiers of 21 layers with NO region changing appearance (sp80: 20 of 27, two changed). The bill is scale-independence in the readings plus a spill extractor that survives four times the width — not a new schema. Probes: `scripts/rounds/R98/near_ood_screen.py` (all 25) and `family_reach_probe.py`. ⚠️ The round's own near-OOD control was picked from the 8-game list — tu93 at burst 8 was called "nearest" when sb26 and lf52 outrank it — and was deliberately NOT swapped, because re-picking a control after the fact unmakes it). **ROUND COMPLETE 2026-08-25** — the closing measurement enabled the explanation follow-up on all three models and settles the strong reading of FILL: **every model cites the SAME discriminator** (both targets satisfied, level did not advance) and `explanation_check.py` clears every explanation against the capture, so the stage is neither a prior nor perception — it separates ONE inference from two distinct wrong ones (gemma4 demands a terminal marking the engine never emits; qwen's explicit variant concludes fatal IN PROSE and emits the opposite token). Closing corrections were all against OUR OWN RECORD, never a model: the fill evidence called thin is not thin; the 'unstated completeness' hypothesis is false because the prompt states it; the 'gemma4 misses TWO slots' correction was ITSELF wrong (both losing models miss exactly ONE discriminating slot — qwen's extra difference is a declared EQUIVALENCE CLASS); and ⛔ idx3's blocker is NOT 'a fourth target the schema cannot express' — those four cells ARE `absorber_cells` in all four captures, so the board models the region, and the real gap is that `sink_response_predicate` is GLOBAL where one board needs it PER-TARGET (`contact` wins 14033 layouts but is CONTRADICTED on idx0). Open work is family expansion under a frozen contract. ⚠️ R98 never touched the leaderboard: measured the same day, `notebooks/kaggle_submission.py` still ships `KaggleChainedAgent` (proxy 1.072%), NO Kaggle-facing file references `adapters25`, and the 32.96% script25 card selects adapters by `game_id` substring — quarantined BY DESIGN. Live card = **0.20**, unmoved since 2026-07-13)
- **agent25 / self-extension / tier-2 / authored-cell-update / exact-transition-verifier / ast-sandbox / certify-hole / ft09-k3-idx4 / seed-pass / prereg**: [[r97_self-extension]] (tier-2 of the R95 fallback ladder: ablate `ordered_cycle`, measure whether the model authors the missing rule as a verified function. Codex CONDITIONAL GO exposed two validity traps (no causal-use compiler node; footprint verifier cannot discriminate flip-vs-cycle) — both built as prerequisites (2b517ce) with a dedicated AST sandbox; contract FROZEN (4eb845e): SEED-PASS cap, 4-case structure, exclusive select/extend/abstain union, detection-vs-authoring split scoring. Pre-model oracle-certification gate PASS (42bc851) with the load-bearing finding: **ft09 is a per-level 2-state toggle; the genuine k=3 cycle first appears at idx4 (8,12,9)** — hole evidence comes from the k≥3 level, idx0 doubles as the honest no-hole control; hand-authored oracle clears LIVE at [4,8] through the causal-use node; all 6 definition mutants fail. **ROUND COMPLETE: CONFIRMED SEED-PASS BOTH MODELS** — gptoss hole 2/3 + no-hole 3/3; gemma4 (R97b v2, after the syntax-contract fix) hole 3/3 + no-hole 3/3 with the EXACT cyclic-successor rule authored via if/elif/else (identical source hash every run); all controls abstain. v1 gemma4 0/3 was an un-communicated AST-constraint harness defect (semantically exact-oracle '.get' rule rejected), not capability — the R95b notation-misparse lesson replicated in the authoring channel: every enforced constraint must be STATED in the model-facing contract)
- **agent25 / family-expansion / controlled-grid-dynamics / coupled-actors / m0r0 / actor-relation / mirror-deltas / settle-absorption / online-occupancy-learning / invisible-obstacle / time-expanded-bfs / behavioural-orbit / oracle-partial**: [[r96_controlled-grid-dynamics]] (the R95 pipeline applied to its second family; contract m0r0 idx0+idx1 (727b34b). **ROUND COMPLETE: ORACLE PARTIAL / GROUNDING PIVOT + MODEL STAGE CONFIRMED — idx0 FULL PASS 3/3 @15a = gold through 15 gates; all four model substages PASS 3/3 (gemma4 select exact-oracle + fill idx0@15a; gptoss select equivalence-class + fill idx0@15a; two shared-root harness defects found+fixed mid-campaign, verifier blocked 3 wrong picks with zero executed actions); idx1 PARKED at the pre-declared grounding-class wall (POSITION-DRIVEN invisible guard — 61/61 block events follow the actor-config schedule; StateDependentOccupancy banked as the future model class)**: an INVISIBLE floor-coloured (colour-5-on-colour-5, no frame diff exists) dynamic obstacle with NO stable period ≤12 (behavioural fit engages but climbs 2→10 without stabilizing; long-period / multi-obstacle / position-dependent). NOT a schema failure — the schema/verifier/compiler plan idx1 perfectly given correct walls. The 15-defect instrumented ladder is banked as GENERALISATION ASSETS: per-level fresh re-grounding, confirmed-edge-subset planning, actor persistence gate, settle absorption, clean/double/no-op wall learning + retry, observation-trumps-inference invalidation (learned AND grounded walls — the patroller was baked into the static parse), online hazard learning (joint-teleport detection), meet-in-the-middle merge semantics (engine-evidenced; walk-onto/swap blocked, adjacent gap parity-impossible), block-evidence transient sensor + TTL decay, flip-flop commit-and-wait, frame-diff transient perception, time-expanded joint BFS (pos_a, pos_b, t mod P) with frame-diff + behavioural orbit sources. Model substages proceed on idx0; position-dependence discriminator pre-registered)
- **agent25 / tool-fork-patch / solver-core / source-card / executable-card / patch-loop / click-xy-fix / stall-matrix / hypothesis-dsl / no-repeat-rule / falsification**: [[r93_tool-fork-patch]] (the user's counter-design after R92: runtime agent works like a coding agent — run OUR tool, on stall read its REAL source (source_card = inspect-assembled, parity-tested, the card IS the production code), patch it, matched parent-vs-patch replay from RESET, lexicographic progress verdict. Codex: worth ONE minimum falsification build (2 failure cases; both fail → agent25 FINAL shelve); ranked extra levers = typed hypothesis DSL + transition-consistency verifier, hard no-repeat-no-op rule, schema-hypothesis ensemble. Step-1 stall matrix (no LLM, ceph-build): 15/16 tool×game combos 0 @300 AND structural @2000; chosen failure cases toggle×vc33 (L2 wall) + paint×cd82 (structural 0). Foundation ea3bf21: solver_core.py + the CLICK-XY TRANSITION FIX — the sandbox record was dropping click coordinates, which partially explains R92's zero transitions usage. **VERDICT (v3, 2026-07-22): THESIS SURVIVES — paint×cd82 PATCH_WINS** (first positive agent25 outcome ever: gemma4 diagnosed the repeated-click deadlock from the instrumented trace, its next-largest-region patch DOUBLED transition diversity 128 vs 64 on a fair driver — verbatim-core control reached vc33 L2 through the sandbox path; 6/6 model patch outputs across v1-v3 diagnosed correctly, ALL failures were harness defects, 6-defect chain regression-pinned in 17 tests. Honest bound: third-tier win, no level clears yet. Conversion levers → R94 adapter-template paired-holdout (lp85→s5i5, Codex-approved minimum), hypothesis DSL, no-repeat rule)
- **r11l / strike-aware / defgjl / body-obstacle / centroid-assembly / leg-separation / camera-identity / misdiagnosis-correction / depth**: [[r85_r11l-strike-aware-assembly]] (task #109; r11l 1/6 → **3/6 @ 0.2551** deterministic ×2; FALSIFIED the R60c "wall-edge / DISPLAY→GRID camera transform" bank via engine-truth probes — camera is IDENTITY, both L1 creatures 121/121 feasible; the real wall was the un-modelled in-play `defgjl` body obstacle (70×36 over rows ~22-58, NOT off-screen); fix = per-creature A* over single-leg moves keeping every intermediate body centroid off the generic hazard set + `_LEG_SEP` leg separation + exact-from-cell select; generalises to L2's 4-leg grhcew; L0 byte-identical). L3 (R85b probe): same class + feasible but detection returns None — bodies are MULTI-COLOUR with SHARED colours.
- **r11l-l3 / colour-blind / connectivity / target-assignment / multi-colour / detection / banked**: [[r86_r11l-l3-connectivity-detection]] (task #111; colour-blind L3 detection ATTEMPTED — proximity-cluster high-fill bodies SOLVES leg-grouping (3 bodies, perfect 2+2+3, engine-verified), but TARGET-ring assignment is ambiguous under colour-sharing (4 equally-optimal one-to-one solutions for orrqlj's target, no clean tie-break) → multi-session wall, NOT bounded; NO code change, floor 3/6 untouched; reopen = ring-GEOMETRY target detection)
- **r11l-l5 / level5 / whkxtx / collect-match / colour-set / puukul / dirwzt / mechanic-class / multi-session / probe**: [[r89_r11l-l5-probe]] (task #115; verified indexing — 6 levels, 4/6 = Levels 1-4 cleared, next = Level 5 idx4; verdict: Level 5 is a NEW HYBRID mechanic — drag-assembly creatures PLUS `whkxtx` COLLECT-AND-COLOUR-SET-MATCH creatures (a collector absorbs `owuypsqbino` pieces, wins when its accumulated colour set EQUALS the target's — a subset/exact-cover + collision navigation, not centroid drag) PLUS `dirwzt` distractors; MULTI-SESSION decode+build, NOT bounded; no build, floor 4/6 unchanged; L6 same/harder)
- **r11l-l3 / colour-blind / nested-colourset / target-discriminator / speculative-trial / dirwzt / depth**: [[r87_r11l-l3-colour-blind-trial]] (task #112; r11l 3/6 → **4/6 @ 0.2594** deterministic ×2, L3 CLEARED, floor byte-identical. Three frame-only pieces, fallback-gated: (1) colour-blind connectivity detection (fill-band split + proximity-fuse multi-colour bodies) recovers 3 creatures + 2+2+3 legs; (2) the **NESTED-colour-set discriminator** (`target ⊆ body` OR `body ⊆ target`) UNIQUELY identifies all 3 targets — retires the R86 ambiguity wall; (3) speculative-target-trial net (drive body to each candidate until the engine WIN fires). L3 clear is REAL but INEFFICIENT (172a, s0.023) — strike-learn churn on the central defgjl-Level7 obstacle; reopen = single-life L3 via body-hazard pad + replan-churn fix (→ ~0.37 game); L5 uncracked. Ring-geometry falsified first: 0 low-fill pieces enclose a hole at any sep)
- **r11l-l5 / whkxtx / collect-match / teleport-absorption / colour-set / puukul / interface-overlay / occlusion / perception-wall**: [[r91_r11l-l5-collect-match]] (task #116; Pass 1 mechanic DECODE done + confirmed live — 2 colourless collectors (body = legs' centroid, same drag as L1-L4), 4 single-colour `puukul` collectibles, 2 disjoint-colour-set targets {8,9}/{11,14}; **`havofgepjpl=1` ⇒ TELEPORT absorption** (checked at the body's final centroid per leg-move, NOT swept path — corrects the R89 handoff), 60-action budget, NO defgjl/strike on L5, independent collectors. Pass 2 subset-cover SPECIFIED (trivial). Pass 3 BANKED on a frame-PERCEPTION wall: L5's `xeuvojjxyk` interface overlays colour-1 leg→body tendons + a colour-10 collector-reach FIELD that occludes/fragments the small collectibles (colour-8 `rengnt` FULLY hidden at entry) → a dedicated perception round (mask 1/10; collectors via leg-centroid+tendons; targets = 2-colour ~7×7 rings; occluded collectibles need DYNAMIC re-observation, R88 stochastic re-detect). **R91c: collect-match CONTROLLER SHIPPED (`061c82d`) — `_detect_collect_match`/`_setup_collect_match`/`_collect_step` gated behind the collect-match signature, floor byte-identical 4/6 @ 0.2594 verified ×2; detection+assignment MEASURED-correct live (cluster legs by nearest colour-0 solid body, not leg proximity). L5 NOT yet cleared — greedy single-leg controller can't seat the body next to wall-adjacent collectibles in 60 actions (engine-refused wall cells the frame hazard under-covers); continuation = 2-leg `_plan_creature`-style A* + wall pad + track collector after it turns coloured**)
- **tool-selection / tool_selector / graph-collapse / alt-sweep / generic-path / depth-wall / vc33-toggle / harness / near-human-level-1**: [[r100_tool-selection-wall]] (OPENED 2026-08-26 because R98 is exhausted on the public set — sp80 is the ONLY place-then-propagate game in the 25, so its family cannot expand publicly. Axis: is the generic path's level-1/2 wall a PLANNING limit or a SELECTION one? Measured that day: the generic path is near-human on level 1 (median 1.3x, seven games at a perfect 1.0) yet 19 of 25 wall at level 1-2 and burn the whole budget there; the harness picks `graph` on all nine games tested; and vc33/toggle clears 2 levels in 113+143 actions where vc33/graph clears 1 in 2,335. The collapse is the DECISION TABLE, not the model — tool_selector.md gives graph 'ANY game' and excludes toggle with 'NONE of the 25 dev games is one', which vc33 refutes. First step: finish scripts/rounds/ALTFULL (95/100, toggle only 11/20, stopped on a 60-core breach exactly where toggle was thinnest) at safe parallelism.)
- **tool-set-spec / stage-one / reach-deliver-configure-induce / four-classes / test-method**: [[tool_set_spec]] (ACTIVE SPEC, not a round — the four generic tools derived from the 25 games' mechanics, their build order, and how each is tested. Read before writing tool code: A navigate (7 games) / B transport+assignment (6) / C configure+simulate (5) / D induce-rule-then-apply (7); `graph` expands over ACTIONS which is class A's shape alone, so 18 of 25 games have no tool shaped for them. Build order T-D, T-B, T-C, T-A. Testing: unit on fixed captures -> single game via tool_alternatives -> the whole class in parallel on ceph at LOAD-capped 60 -> card must stay 0.3162.)
- **model-guidance / context-budget / gemma4-31b / qwen3.8-27b / gpt-oss-120b / closed-choice / per-model / two-model-rule**: [[model_guidance_spec]] (ACTIVE SPEC — the harness layer that turns a game's measured signature into a tool choice a SPECIFIC model can make within its context. Design constraint from R98's nine-run stage: gemma4 and qwen3.8 are 9/9 at closed-choice SELECT and 0/9 at open FILL, gpt-oss-120b is the only one that fills — so tool choice must be presented as a CLOSED multiple choice with glossed options, never as open description. Contents per game: measured observables, the class as a 4-way closed choice, the tool's config slots as glossed enums, and a falsification signature. Budget: build_context caps at 6000 chars while tool_selector is 12.9 KB, so it is already truncating — sweep HARNESS_CTX per model before shipping. Waits on stage 1.)
- **r101-llm / kaggle-gpu / vllm / gemma4 / routing / claim-threshold**: [[r101_llm-path-measured]]
  (CLOSED — the shipped LLM path measured at width on a Kaggle GPU. First run: agrees with the
  LLM-free signature fallback on 24 of 25 games and loses cn04 alone, 0.6333 vs 0.6733, 18x the
  wall-clock. Cause was in the PROMPT, not the model — a 0.60 CLAIMS threshold the fallback does
  not have, so the two paths could only diverge in 0 < fit < 0.60 and that is where they did.
  After the fix: **25 of 25 IDENTICAL, ZERO routing losses, 0.7288 both, and the LLM arm fell
  from 2817s to 228s.** ⛔ Parity is the CEILING of this measurement, not a win — on these 25 the
  signature default is already right everywhere. Whether the model helps on a board we have never
  tuned against is untouched by it.)
- **r101 / tool-development / generic-tools / fan-out / selectivity / transfer / stage-one /
  25-of-25 / depth-vs-efficiency / instrumentation**: [[r101_tool-development]] (ACTIVE — the
  generic tools ALONE, zero adapters, over the 25 sample games: **0.0200 -> 0.8540**, FIFTEEN at
  1.0000, SEVENTEEN clearing every level, cumulative regressions ZERO across ~20 gates. Method:
  one background agent per GAME owning two new files, parent integrates ONE at a time, full 25 on
  ceph decides ([[../parallel_build_protocol]], gate scripted as `scripts/rounds/gate_tool.sh`).
  ⛔ **The card is NOT the property that matters**: the shipped `--agent kaggle_detect` scores
  0.5422 against the generic path's 0.8540, so the thirteen adapters now COST 0.31 and only ls20
  still earns its board ([[../lessons/adapters_now_cost_the_card_20260827]] — submission-affecting,
  the user's call). **TRANSFER essentially clean: ratio 0.9981, 13 of 14 re-rendered games
  IDENTICAL** ([[../lessons/generic_transfer_20260827]]) — and the ratio dipped and recovered
  while the card only rose, so a card number cannot tell you which run you are in. Load-bearing:
  a tool with no plan must bid 0.0 ([[../lessons/tool_selectivity_20260827]]); DEPTH without
  efficiency is worth nothing — two extra levels bought +0.0011 where the same levels made
  cheaper bought +0.0304; COUNT how often each branch runs before tuning any of them, and a
  guard whose condition can never be false is the commonest defect here, five instances in one
  day ([[../concepts/guard_about_the_model]]); a game stops 1200 actions after its last level-up
  and at 1000s wall-clock ([[../concepts/no_progress_bail]], -63% actions); frame layers are an
  ANIMATION TIMELINE and reading the last one globally REGRESSED three games
  ([[../concepts/frame_layer_timeline]]); ties break by registration order because specialists
  claim one board and searchers claim all 25 ([[../concepts/tool_claim_breadth]]).)

- **R101SILENT — why the last eight games stop, and thirteen repairs that did not move them**
  ([[r101_silent-specialists]], [[r101_probe-fallback]], 2026-08-29; score unchanged 0.8935/17 at
  the cap.) Keywords: silent tool, empty propose, tool retirement, patience knobs, alignment
  threshold, search cap, vocabulary probe, fuel budget, discovery cost, instrument validity.
  **Every stuck game retires its specialist through the EMPTY path** — the tool proposes nothing —
  and the general searcher inherits ~500 actions; the tools' MODELS are correct, checked against
  each game's own win predicate. **Where the 0.1065 sits: depth 0.0919, efficiency 0.0147**, and
  ls20/lp85/re86 have ZERO depth loss (they clear everything and are merely slow). Mechanics
  recovered from game source: **lf52** = peg solitaire, select a pad then land two cells away, win
  at 2 pads, and its level 6 has no adjacent pair so NO legal capture exists; **bp35** level 6
  introduces one `yuuqpmlxorv` CRUMBLING PLATFORM whose four shrinking sprites read as four glyph
  kinds; **ls20** is a FUEL game — 42 units at 2 per action, refills by touching a colour-11 ring,
  three lives, restart-to-start, and level 7 is the only fogged level and carries six pickups.
  ⛔ Thirteen repairs measured and reverted (patience x2, alignment threshold, shift range, pitch
  re-fit, tool revival, map-drop-on-flip which cost 0.12, admissibility bypass, shape matching,
  probe-order memory, lethal-glyph probing, vocabulary carry, switch-reset, gauge speed-up). The
  obvious defects were already fixed by whoever wrote these tools' docstrings; what remains is the
  COMPOSITION. ⚠️ Twelve instrument failures, all one family — an instrument returning a plausible
  number for a quantity it is not measuring; the survivors are in the round page and in
  `OPERATING_RULES.md` rules 7c and 7d.


- **allowance / action budget / GAME_OVER / death clock / overrun / tool retirement** →
  [[r101_allowance-ledger]] — a level's action allowance is learnable from ONE death via `obs.state`
  alone (no pixels, no source access): the death length IS declared+1. A 24-game sweep recovered
  NINE, three of which the games declare nowhere (tn36 61, tr87 129, r11l 60). ⛔ The trust gate is
  most of the instrument — hazard deaths SCATTER (tu93 9..51, su15 48..150, sb26 69..217, sp80
  14..121) while clock deaths agree within 1, and nothing measured lands in between; cd82's nineteen
  length-1 "deaths" are the harness idling in GAME_OVER, hence the floor of 2. Consumer = retire the
  tool after two agreeing deaths, scoped to THAT level (the scorer charges a cleared level with every
  death that preceded it; bp35 repeated one 64-action death 19 times). ⚠️ Headroom on the public 25
  is wall-clock only — seventeen games never die and the five that do die only on levels they never
  clear; the score case is the private 110. ⚠️ EIGHTEEN games score 1.0 in that baseline, not the
  seventeen CLAUDE.md's header still names (that is the older 0.8935 card) — and `total_actions ==
  sum(per_level)` does NOT detect a death, since the GAME_OVER reset increments both counters.


- **level restart / retry / attempts spent as one / wa30 / shepherd / haulage / mover reachability /
  route-not-straight-line / conquest** → [[r101_wa30-level-restart]] — **wa30 0.8000 -> 1.0000, 9/9,
  levels 1-8 unchanged TO THE ACTION.** ⭐ The class of failure: a level whose allowance runs out
  **RESTARTS**, and `levels_completed` does not move, so a tool that watches only that number cannot
  see the boundary — wa30's last level got EIGHT attempts and six of them were byte-identical
  replays of the first attempt's endgame, carrying a plan for a board that no longer existed, a
  held-piece flag and a walker sweep straight across the reset. The board was never short of moves;
  it was short of ATTEMPTS. Fix = `_reborn` (a restart is a carrier TELEPORT **and** two or more
  pieces reappearing outside the bays — neither half alone is safe) **plus** `_start_haul` ranking
  by the WALKING ROUTE to a helper rather than the straight line (the rule `_police` already stated
  for a thief): wa30's level 9 has a second helper sealed above a hazard band that moves ZERO cells
  in seventy actions, and a straight line called it four cells from pieces it can never reach.
  ⛔ **MEASURED that neither rule works alone** — shipped, restart-aware alone, and route-distance
  alone all give 8,7,7,7,7,7,7; together they clear on attempt 2. ⚠️ Two negatives worth as much:
  VARYING the retries per attempt makes it WORSE (8,8,6,4,4,4,4 — they were not failing because
  they were identical but because each was the first attempt's endgame replayed), and learning the
  allowance from the first death to decline an over-long haul is INERT even though it FIRES (ten
  refusals, allowance learnt as 69) — an independent confirmation of [[r101_allowance-ledger]].
  Blast radius MEASURED not argued (`scripts/_wa30_who.py`: `shepherd` appears in no other game's
  action histogram). Related: [[r101_silent-specialists]], [[r101_allowance-ledger]].


- **bp35 / crag / attempts / window does not belong / alignment / re-seed / empty path / measured
  negative** → [[r101_bp35-attempts]] — the wa30 mechanism taken to bp35 and **REFUTED there**: its
  eight wall attempts are eight DISTINCT sequences, nothing is replayed. The real wall is that
  `crag` clears boards 1-5 and then quits eight times on board 6 with one reason, `window does not
  belong to this board`, body frozen at (6,8) — NOT `_refuted`, `_mute` 0; the harness just retires
  a tool that keeps returning nothing, and `graph` inherits ~450 actions and dies on the 64-clock
  six times. ⛔ The three faults behind that one word were SEPARATED rather than guessed
  (`scripts/_bp35_lost.py`): physics refuses nothing once `allow` goes None, and the best alignment
  is **0.60 against a 0.82 threshold** — so neither the admissibility window nor the threshold, both
  of which R101SILENT already tried blind and reverted. Lowering `_ALIGN_FIT` to 0.55 measured
  INERT. ⭐ Re-seeding the map after N losses DOES fix the silence — crag keeps the board for four
  whole attempts instead of thirteen actions — **and moves the score by NOTHING**, while CREATING
  the wa30 disease (it then emits the identical 64-action loser three times). Not shipped: worse in
  kind at equal score. It is also a live confirmation of the offline proof that crag's candidate
  rule excludes every board-6 solution — handed a fresh map and four attempts, it still does not
  clear. ⭐ bp35's real headroom is on the boards it ALREADY clears: L2 = 8+34 spike deaths before a
  **43-action clear against a human 48**, L5 = 14+14 before a **30 against 33** — the winning
  attempt already beats the human both times, so the whole loss is exploratory deaths, worth
  **0.2220 -> 0.3304, +0.0043 on the mean**, and it needs lethality read from the FRAME before
  contact, not restart bookkeeping.

- **R101CONQUEST** ([[r101_conquest-wave]]) — 0.8935 -> 0.9069, re86 and wa30 CONQUERED, nineteen at the cap. The durable half: a level that RESTARTS is invisible to `levels_completed`; the gate itself was the contamination (snapshot it); nine instruments lied and all in the same direction.

- **ls20 / fogscout / level 7 / fuel / mover / patrol / oracle / cannot wait / measured negative** →
  [[r101_ls20-fog-cost]] — level 7's 231 against a human 186, decomposed with the ENGINE's own state
  (`scripts/_ls20_census.py`, control reproduces [17,101,63,66,67,100,231] four runs out of four).
  ⭐ **You cannot wait for a mover on these boards**: `Ls20.step` moves every mover first and UNDOES
  that step when the player's move is refused, so a blocked action is a strict no-op — 18 of 18
  measured — which is WHY the earlier "ambush at its remembered beat" arm was exactly inert, and
  removing `_hold` outright measures 231 unchanged. ⭐ An oracle BFS over the level's own geometry
  puts a full-knowledge solve at **61 with fuel, 55 without**, against the tool's own
  knowledge-complete 75 — so the 45-action gap is **three ~15-action gaps** (10 keymaze handover,
  14 execution, ~21 discovery), not one defect. ⛔ Twelve arms across four axes all lose or are
  exactly inert: cycle-closure inference (324 / level LOST), motion conjugation (36 fires, EXACTLY
  INERT — so the token model's completeness is not what gates this level), fuel-first mark seeking
  (level LOST x2, 343), refuel ranked by round-trip detour (307 x2, level LOST). ⭐ **The handover is
  now CLOSED as NOT A GAP**: only 2 of its 10 actions are `keymaze`'s (its `_idle` blind step) — the
  other EIGHT are the harness `_probe` fallback firing while the tool proposes nothing — and a
  sixteen-arm sweep of both empty-proposal constants shows **231 is invariant for handovers from 9 to
  17 actions**, with six arms LOSING the level, because the tank those actions burn belongs to a
  first life that runs dry on action 21 regardless. Open: cross-level mechanic carry (a first-time human reaches level 7 having played six levels with
  the same three changers; `fogscout` cannot, because `detect` is 0.00 on every unfogged board).

- **tenure / retirement / EMPTY_TOLERANCE / empty proposal / handover / what ends a tenure** →
  [[r101_tenure-end]] — the census (rules 7bq + **7bp**) and the arm 7bq said was unnecessary.
  ⭐ The whole 25-game corpus contains **NINE tenure-ending events** (EMPTY 7 · STALL 2 · CLOCK 0 ·
  CODE 0) and **twenty of twenty-five games are played start to finish by ONE tool**. The empty
  channel is 70 proposes of 7,049 round-trips (1.0%), and it is BIMODAL: fifteen recovered runs,
  **every one of length ONE**, and nothing between a blip and death. ⭐ **SIX of the seven EMPTY
  retirements land on a level the game NEVER clears**, so they are scored zero however they are
  spent; the seventh is ls20's, already swept to invariance by 7ax. ⭐ A **175-arm full-25 sweep**
  makes the shipped `_EMPTY_TOLERANCE = 8` the **measured ARGMAX** (0.9082 vs tol1 0.7756, tol2/16/32
  0.9017, tol4 0.9049) with **zero dynamic range on 24 of 25 games** — outside tol1, only ls20 ever
  moves, and its surface reproduces 7ax exactly from an independent instrument. ⛔ tol1 collapses
  ar25/ft09/re86 from 1.0000 to ~0.03, which is what the fifteen singles are worth. ⚠️ Two things
  reported and NOT shipped: `_empty_runs` is AGENT-scoped where the concept is tenure-scoped (one
  retirement is measurably one proposal early), and the tenure-scoped fix is EXACTLY INERT on all 25;
  and there is **no tool→harness exhaustion channel at all** (rule **7bt**): `base.Tool` is four
  methods, none of which says "I am out of plan", and the harness's five duck-typed channels
  (`state_key`, `set_target_frame`, `target_stalled`, `target_progress`, `augmenter`) contain no
  exhaustion signal — `target_stalled` is the nearest, is implemented by ONE tool, and gates a target
  redraw. ⚠️ This first reached the record naming `cover_targets._handover`, which is unread but is
  PIECE-CONTROL semantics; the attribute that actually knows is `_stuck` (`cover_targets.py:499`),
  read only by its own tool. Caught by grepping the assignment sites before writing the claim.

- **shipped card / kaggle_unified / submission path / transfer / re-render / archived hash /
  brittleness / does it read pixels** → [[r101_shipped-and-transfer]] — the two numbers the campaign
  quoted without measuring. ⭐ The SHIPPED wrapper scores **0.9082, zero games differing** from the
  bench member (`AGENT=kaggle_unified bash scripts/snapgate.sh`), and the notebook has shipped
  `KaggleUnifiedAgent` since `f1067554` — ⚠️ CLAUDE.md claimed `KaggleDetectAgent`/`KaggleChainedAgent`
  in two places for days. ⭐ **24 of 25 games are action-for-action IDENTICAL on an archived
  re-render** (ratio 0.9989); the only difference in the whole set is s5i5 L4, 39 -> 61 actions,
  still clearing. ⚠️ A re-render is the SAME GAME — a floor on brittleness, ⛔ not a leaderboard
  transfer coefficient. Both had been blocked by INSTRUMENTS, not by the work: `snapgate.sh` could
  not take an agent argument, so the file's own "measure the card AS SHIPPED" order named a flag the
  runner refused; and the transfer procedure had been re-derived by hand three times because no
  round dir ever carried its `run.sh` (now `scripts/xfergate.sh`). Rules **7bv** + **7by**, plus
  **7bu** — the r59s15 duplicate-`game_id` hazard RECURRED on ceph-build and is measured INERT
  (both sk48 sources, same score, same action count on all eight levels).

- **inert action / dead action / wasted action / efficiency of a cleared level / board_changed vs raw
  diff / edge counter / livelock / RHAE cap / canary margin** → [[r101_inert-actions]] — the
  follow-up to rule 7bw's lf52 finding, asked of every game and restricted to levels that CLEAR.
  ⭐ **A dead action is 9.2x more likely on a level that never clears** (9.82% of 1996 uncleared
  actions vs 1.07% of 6381 cleared ones); removing every repeat-dead action from every cleared level
  is worth **+0.000056 of the mean, all of it ls20**, and 24 of 25 games gain exactly zero. ⛔ The
  bound is structural and computable before any census: only FIVE cleared levels in the whole 25
  score below 1.0, so **+0.00796 is the ceiling on efficiency work over cleared levels**. ⚠️ The
  three-way split (dead / edge-only / live) is load-bearing — `board_changed` discards the frame's
  outer band on purpose, so r11l's "47.6% inert" is 0 dead and 39 edge-only, and the raw `!=` test
  reports ZERO inert on bp35 where the interior test finds 205. Neither test alone is sound.
  ⭐ Rule 7bw's memo-plus-give-up livelock appears ONLY on never-cleared levels (runs of 116 and 49;
  the longest on any cleared level is 7). ⚠️ And of the five zero-margin canary levels, sc25 L2 is
  the one that is not tight — 6 actions against a human 6 with one of them DEAD. Rule **7cb**.

- **z-order / paint order / occlusion / rider not drawn / why s5i5 L4 costs 22 more on a re-render /
  does the tool read mechanics or pixels** → [[r101_zorder-rider]] — the follow-up
  [[r101_shipped-and-transfer]] asked for, and the answer is ⭐ **a frame-only tool that identifies an
  object by whether it is DRAWN is reading PAINT ORDER**. The two s5i5 serializations are identical
  by construction (same art, same positions, same `Children`; only the sprite LIST ORDER differs, and
  the engine paints same-layer sprites in list order), and on the level in question **exactly ONE
  cell of the opening frame differs** — the rider, painted over by its own bar. `telescope._begin`
  then falls back from a pinned rider to EVERY bar as a candidate: nine of them for one destination,
  nine plans, four pairings knocked down by the board, +22 actions. ⭐ **The contrast is the
  finding** — the fallback fires on ALL FIVE levels and is FREE on four, so the dependence is
  QUANTITATIVE, and 7by's 0.9989 is a floor measured on small candidate sets, ⛔ not a forecast.
  PROVED BY INTERVENTION, three runs in one process: restoring the rider evidence inside `_begin`
  alone returns the level to 39 actions and the game to 0.5833. ⛔ Nondeterminism REFUTED first
  (3/3 identical on both boards). No repair shipped and the reason is measured: the guess is not
  avoidable, only its price, and that is a redesign against four levels already optimal. Rule **7cd**.

- **render mutation / colour permutation / palette relabel / translation / camera pan / full-bleed
  board / sprite rename / version hash rotation / instrument validity / refusal path / rendergate**
  → [[r101_render-mutation-transfer]] — the transfer test that MANUFACTURES the re-render, because
  the archive only covers 14 of the 25 games (⭐ **fourteen, not fifteen**: `environment_files_archive/sk48`
  is the SAME version hash as the live tree, byte-identical, so substituting it substitutes a game
  for itself). It mutates the AGENT'S OBSERVATION, never the game, so validity is by construction
  rather than by reading a 41,463-line source. ⭐ **Three independent colour relabellings, full 25
  each, against an identity control at the same commit: mean 0.9082 in every arm, and ONE ACTION of
  one level moves in the whole set** (cd82 L3, 33 -> 34, score unchanged; it is a colour-ORDER
  tie-break at one of the 8 sites that sort a colour set by index — there is not one numeric colour
  literal compared against a frame anywhere in the tools). ⛔ **Translation is NOT constructible: 24
  of 25 boards are FULL-BLEED**, zero uniform margin on all four sides, so there is nowhere to pan
  to. The one game with a margin, tn36, scored **1.0000 -> 0.1071** under a 1-cell shift and it
  means NOTHING — four clicks landed in the synthetic band — which is exactly why the instrument
  prints NO VERDICT instead of a 90% loss. ⭐ The API's own identifier rotation is INERT where it can
  be built: 14 games render BYTE-IDENTICALLY under a full sprite rename, 10 are not constructible
  with a stated reason, 1 (bp35) has a failing negative control and is unmeasurable, 1 (sb26) ends
  the run early and is a broken mutation. ⚠️ Two earlier versions of that rename were broken and both
  failed by renaming PART of a whole, each producing a column of DIFFERENTs that read as a
  spectacular transfer failure — the tell is that the divergence was UNIVERSAL and at index 0.
  ⛔ A recoloured board is the SAME BOARD; 1.0000 is not a transfer coefficient. Rule **7ce**.

- **outer band / edge band / board_changed / HUD / marching counter / deadsig / globally_dead /
  drop_dead / augmenter / does the harness see this action** → [[r101_discarded-band]] — what the
  deliberately-discarded frame band actually costs, answered by reading the CONSUMER. ⭐ **Exactly one
  tool sets `augmenter = True` (`deadsig`), so the whole cost flows through
  `deadsig -> globally_dead -> GraphSearchTool._drop_dead`** — tenure, retirement and the stall
  detector consume none of it, and the active tool is fed the RAW flag. `_drop_dead` was called 2049
  times over the 25 and withheld something on **918, all on bp35 level 6, never once on a level that
  clears**. ⛔ And it is zero for a reason, not by luck: **the one place the discard is consumed is the
  one place it is right** — bp35's band moves at rate 1.00 for all fifteen of its action classes (a
  pure counter), while the games whose band carries real content (cd82 0.649, dc22 0.218) are exactly
  the ones where `_drop_dead` is never called. ⚠️ **This CORRECTS [[r101_inert-actions]]**: `edge-only`
  is NOT a safe harbour, r11l's band is a counter at 1.000, so its 39 "edge-only" actions are
  genuinely inert (cleared-level dead 1.07% -> 1.94%). ⚠️ The per-pixel ">=80% of probes" HUD test
  cannot see a marching counter and returned zero HUD pixels on all 25 — ask it per REGION and per
  ACTION CLASS. Rule **7cf**.

- **llm / offline model / gpu / vllm / target draw / routing / does the model help / axis closed** →
  [[r101_llm-on-a-gpu]] — ⭐ **arm_llm 0.908187, arm_fallback 0.908187, ZERO games differing** on a
  Kaggle GPU with vLLM serving gemma4. The controls are the result: **38** served chat completions,
  target-draw failures **fallback 3 · llm ZERO** (the draw succeeded for the first time in the
  campaign), **34** re-decides in each arm, and **104 seconds** of extra wall clock — so the model
  really ran, answered, drew targets, and changed not one action. ⛔ Amends rule 7ca, whose headline
  was that the draw had never succeeded anywhere. ⚠️ It does NOT say an LLM is useless: it says
  **these 25 cannot measure it**, because nineteen sit at the cap and signature routing already picks
  a tool that clears — the private 110 are the case where no tool fits. ⛔ And the first reading of
  the log was WRONG (three `Connection refused` lines read as "the draw failed here too"); splitting
  them by arm banner reversed it — a count spanning two arms describes neither (7aj). Rules **7ch**,
  and **7cc** for the load-110 incident that preceded it on the CPU box.

- **ablation / owner / ownership / no tool fits / latch / unseen game / private-110 floor / generic
  path / fallback position / graph / world_model / primary_owns / ablategate** →
  [[r101_owner-ablation]] — the closest available proxy to an UNSEEN game, because every other
  transfer instrument perturbs the RENDERING of a game we already implement and none perturbs the
  MECHANIC. Remove each game's owner: **0.9082 -> 0.1932**, 25 of 25 moved, negative control (drop a
  tool with zero actions anywhere) 0 of 25 differing in score, levels or actions. ⛔ **The floor is
  NOT flat and no single number may be quoted** — median 0.0069, stdev 0.256, 13 games under 0.01
  against 9 at or above 0.30, split by whether any surviving tool CLAIMS the board (claimed n=11
  mean 0.3725 · unclaimed n=14 mean 0.0523, and 13 of those 14 average **0.0014**). ⛔ 0.1932 is
  OPTIMISTIC: every claimant is one of OUR specialists near-missing a PUBLIC board, which an unseen
  game has no reason to have. ⭐ **The latch is real and `_PRIMARY_CONF` is REFUTED as its cause** —
  14 games have exactly ONE `pick=` line for the whole run, all with `primary_owns` FALSE: a
  frontier explorer never goes silent and never stalls, so it looks productive by every signal the
  harness watches while clearing nothing. ⛔ And it is not about `graph`: dropping owner **and**
  `graph` gives **0.1925**, `world_model` doing the identical thing — the latch is a property of the
  fallback POSITION, so "demote graph" is closed. ⚠️ Ownership by ACTION SHARE inverts on 3 of 5
  multi-tool games (bp35's 486-action `graph` is worth EXACTLY ZERO; `crag` clears the levels).
  Rule **7cj**.

- **lost signal / does a run know it is lost / give-up / bail / no-progress / novelty saturation /
  coverage / inert rate / revisit / level-segment / FPR0 / budget threshold** →
  [[r101_lost-signal]] — 7cj's closing hypothesis, tested before anything was built. Both ablation
  arms re-run with per-action telemetry (verified INERT, 0 of 25 differing either arm), giving **255
  level segments, 205 cleared / 50 doomed**. ⛔ **The classes are labelled by OUTCOME, not shape —
  `m0r0` latches for 731 actions and CLEARS FIVE LEVELS**, so latch-shape is the wrong label. ⛔ Only
  k=25 and k=50 have enough winners to define an FPR-0 threshold (2/31 by k=150), so the strong-looking
  late columns are NO VERDICT. ⭐ **Elapsed time carries ZERO information at a fixed decision point
  (AUC 0.500 BY CONSTRUCTION)** — a clock does not discriminate, it only decides when to stop, so the
  baseline is a POLICY. **Alone no signal beats it**: clock@311 saves 34.9% of doomed actions at zero
  levels lost, best signal `coverage@50` only 28.7%. **As a supplement it pays**: coverage OR clock =
  **51.5%**, plus inert_rate 53.2%, still zero levels lost. Controls hold — all 20 re86/wa30/ls20
  segments below threshold with **re86 L5 PINNING it**, 10 of 35 doomed flagged. ⛔ **All ten flagged
  segments come from the ABLATED arm, so on the shipped card it fires zero times and is worth
  0.0000**; the actions saved are on levels scoring zero anyway (7ax/7bq), so it frees wall-clock not
  points, and 7ba says there is no better tool to hand the board to. ⚠️ Threshold fitted IN-SAMPLE by
  one segment. ⭐ The consequence points AWAY from a smarter give-up rule and toward having a second
  claimant at all. Rule **7cm**.

- **visibility / identity / drawn / paint-order / z-order / occlusion / census / candidate set /
  fallback-to-unfiltered / telescope / swivel / blastclock / slotlaunch / tether / lattice_maze /
  cover_targets / viscensus** →
  [[r101_visibility-identity-census]] — the POPULATION of the class rule 7cd named from one exemplar.
  Static: **63 sites**, 14 with the fallback-to-unfiltered structure, and **five of those filter on
  what is currently painted** in four files but only three distinct mechanics (telescope/swivel are
  the same two lines; blastclock/slotlaunch are the same two lines against the same
  `Piece.clickable`, which reads a piece's CENTRE PIXEL). On a run, full 25 @4000, both arms
  reproducing every banked score: **three fire** — telescope 9 -> 1 on s5i5 (the positive control,
  landing on 7cd's own table), swivel 6 -> 1, blastclock 2 -> 1 on ka59 with the fallback firing 9
  times. ⛔ **"Never evaluated" is TWO findings**: `slotlaunch` never proposes on any of the 25;
  `tether` proposes 6x on r11l and does not reach the line. ⭐ **The worst instance has NO fallback
  and 7cd's shape cannot see it** — `lattice_maze.py:484` pins one of nine candidates on 163 of 187
  evaluations on tu93, and its own docstring records **9 levels/188 actions -> 4/1288** from a
  z-order change on the archived re-render, a 6.9x blow-up against telescope's 1.56x; already
  repaired 2026-08-27, never connected to 7cd. Widening to filters without a fallback: 49 static, 39
  live — an EXPOSURE map, not a defect list. ⛔ No repair, no gate (7o): deleting a filter IS the
  61-action behaviour. ⚠️ Two instruments lied toward "nothing here" — an exact-text matcher scoring
  its own exemplar at ZERO, and a missing helper injection that put eleven games at ~0.0 while
  reporting success, caught only by the banked comparison now built in. Rule **7cl**.

- **z-order / paint order / draw order / occlusion / sprite list order / which sprite is on top /
  zordergate / zrev / zrevall / buried sprite / camera _raw_render / no-sort camera** →
  [[r101_zorder-mutation]] — the arm rule 7cd said did not exist. A colour bijection and a
  translation both PRESERVE which sprite is drawn on top, so [[r101_render-mutation-transfer]] is
  blind to the corpus's only measured transfer defect by construction; this one permutes the order
  the engine PAINTS in, installed on `Camera.render` (ONE caller in arcengine, the observation
  frame) and never on `_raw_render` (which games call as logic). ⭐ **Identity control 0.9082 on all
  25 reproducing R101SHIPPED, and the positive control lands to the action: s5i5 L4 39 -> 61,
  0.5833 -> 0.5593, every other level identical.** Population: **14 of 25 applied, 10 INERT (they
  cannot exhibit it), 1 PARTIAL** (sb26 consumes `Camera.render` as game logic — NO VERDICT).
  ⛔ **"Same-layer siblings only" is meaningless for s5i5/tu93/wa30**, whose camera never sorts —
  their rider and bar are on DIFFERENT declared layers, the conservative arm changed 0 cells on
  seven of s5i5's eight levels, and the two scopes differ on exactly those games. ⛔ **Burial does
  not predict cost**: r11l loses 7 sprites of 27 and plays identically, g50t loses ONE of 18 and
  goes to 0.0000, and **re86 loses NOTHING and pays 200 extra actions on L2** — the round's one
  unambiguous tool defect. tu93 (2 of 3 sprites) is a broken mutation; g50t and sc25 are NOT
  classifiable and that is the honest output. ⚠️ Two instrument failures paid for: the diff rendered
  twice through `Camera.render` so the camera's INTERFACES ran twice (272,208 phantom cells on a
  ONE-sprite board, and lf52 two actions faster), and a camera detector matched the imported
  `Camera` itself. Rule **7ck**.

- **dead reckoning / tracked identity / repair transfer / deferral / commit-once / opening frame /
  lattice_maze repair / telescope / swivel / blastclock / success criterion / deadreckon** →
  [[r101_dead-reckoning-transfer]] — does the repair that ALREADY WORKS on the class's worst site
  transfer to the three live ones? ⛔ **No, measured both ways.** `lattice_maze._locate` demotes
  paint from IDENTITY to CANDIDATE GENERATION and lets a tracked prediction
  (`prev_cell + effect[prev_action]`, accepted only if it lands on a drawn candidate) choose — and it
  works because **178 of its 187 reads happen mid-level**. `telescope` reads **5 of 5** and `swivel`
  **2 of 2** on the level's OPENING frame, where no action has been spent and there is nothing to
  reckon from. ⛔ **Deferral is closed by the board, not the tool**: on the archived s5i5 the rider
  markers are absent across **all 62 reads of the 61-action level** and every level 0-5, so there is
  no later moment with better evidence (positive control: the live arm shows 2 1 2 1 2; internal
  control: the archived board's level 6 DOES report movers=1). ⚠️ **And two of the three had no
  success criterion at all** — `swivel`'s levels cost 32/31 on BOTH boards, `blastclock` fires only
  on ka59 which is action-for-action identical on its own re-render at 1.0000 and widens 2 to 1. Of
  the three, only `telescope` costs anything anywhere, and that is the one where the state is
  provably unavailable. **Nothing built, no gate run** (7o). ⭐ Transferable: *dead reckoning is
  available exactly where identity is re-read CONTINUOUSLY*; a commit-once-per-level site admits
  only deferral or cheaper refutation. Rule **7cn**.

- **which object / buried sprite / g50t / tu93 / existence read / detect declines / maze sprite /
  exit / steered piece / zshuf / expected case / engine-created sprite / broken mutation / zobject**
  → [[r101_which-object]] — 7ck asked which object, and had two verdicts backwards. ⭐ **Both
  mutations are RENDER-ONLY** — each game replays its own action tape (g50t 296, tu93 187, s5i5
  692, r11l 83) to the same levels in the same per-level counts, so *"tu93 is a broken mutation"* is
  REFUTED. ⭐ **tu93 is the real, GENERIC dependence**: a no-sort game whose single full-board maze
  sprite covers the EXIT (`0014…`, one flat colour), the STEERED PIECE (`0016…`, body+facing mark)
  and the crowd on all nine levels — 46 burials — and **6 of 7 sampled re-serialisations destroy
  it**. ⛔ **g50t is the ARM'S ARTEFACT**: zero burial among its AUTHORED sprites on all 7 levels,
  and all 8 `zshuf` seeds change ZERO pixels at 1.0000 while reordering every one of 3,333 renders —
  only arms that move an ENGINE-CREATED sprite against the authored list hurt it, which no
  re-serialisation can do. ⛔ **The read is an EXISTENCE read, not an identity read**: tu93's
  `parse_board` returns a board with `pieces_max=0`, `detect` returns 0, the tool proposes ZERO of
  187, and **`_locate` — the censused, repaired site — is called zero times**, so the repair is not
  at fault. ⚠️ Two burial metrics (ownership vs pixels) nearly read as a contradiction; both are
  right. ⚠️ Consequence: **7ck's "14 of 25 depend on paint order" is a WORST-CASE count** and
  includes a game no re-render can touch. Nothing built, no gate (7o). Rule **7cp**.

- **routing vs capability / forced-alone / solo sweep / exclusive ownership / destination / handoff /
  idle tools / prune the registry** → [[r101_routing-or-capability]] — the question 7cm left open,
  since *"there is nowhere better to send the board"* was an INFERENCE from 7ba (full registry, five
  games, never an ablated board). **47 tools x 25 games forced alone = 1175 runs**, through
  `ablate_run.py --only` — ⛔ NOT `ceph_sweep.sh`, whose `_solo_tool.py` hand-rolls its own loop and
  reports no game_score (7aj clause 1). ⭐ Forcing `T` alone builds `UnifiedAgent([T])`, so dropping
  the owner is a NO-OP for any non-owner — one sweep answers the ablated question AND reproduces
  7ba's control. **VERDICT: CAPABILITY, 23 of 25.** An oracle always picking the best surviving tool
  recovers **0.0034 of the 0.7150** the owner was worth — **0.5%**; in **21 of 25 games the best
  surviving tool scores EXACTLY what the ablated harness scores**, and on **10 of 25 NOTHING in the
  registry clears level 1 without the owner** — ownership is not merely singular (7bb) but
  **EXCLUSIVE**. Controls: owner-alone clears 25 of 25; no solo tool beats the full harness on any of
  the 25 (**7ba reproduced beyond its original five**). ⛔ The 7cj class split does NOT predict
  recoverability (CLAIMED 1/11, UNCLAIMED 1/14) — expectation refuted. ⭐ **7bb's warning is now a
  measurement: 12 of the 16 tools that clear anything on an orphaned board are from its
  never-holds-a-board roster**, so pruning by tenure would delete exactly the tools that hold an
  unowned board. ⚠️ Solo max is a LOWER bound (the harness composes — cd82 and tn36 beat every single
  tool), but it settles the single-tool handoff, which is the only kind 7cm's signal could trigger.
  Rule **7cq**.
