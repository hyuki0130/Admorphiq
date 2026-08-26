---
type: index
description: Catalog of the machine-local memory directory, mirrored here so it survives a change of machine.
---

# Memory (mirror)

> The machine-local memory directory copied into the wiki, because that directory does not travel and the wiki does.

Each entry is a single durable fact. `MEMORY.md` is the index the machine-local loader reads;
this page exists so every mirrored memory has a home inside the wiki graph.

- [[MEMORY]]
- [[feedback_codex_review_gate]] — "ALL planning, design, test plans, AND analyses must be reviewed with Codex (codex exec) before acting on them — user standing order 2026-07-14"
- [[feedback_dev_loop]] — Failure → document → redesign → delegate → test → repeat loop for all development work
- [[feedback_english_only_artifacts]] — All docs, code, comments, wiki pages, commit messages must be English; Korean only in chat with user
- [[feedback_generic_not_game_specific]] — When strengthening math/algorithm layers, every decision branch must run on frame observations or feature signatures, never game-title strings
- [[feedback_infinite_loop]] — Run test→log→analyze→fix→retest loop indefinitely until all 25 games solved, no rush for quick results
- [[feedback_llm_drives_loop]] — Qwen is the game-completion agent — comprehend / pick / execute / fix. Claude Code is the implementation helper for code fixes Qwen proposes, not the unilateral designer
- [[feedback_measure_full_25]] — Measure the full 25 games before keeping any tool change; score a tool by net card effect, never by its own game
- [[feedback_measurement_discipline]] — "Timestamp every output; run measurements as background shells (rate-limit-proof); one live SUMMARY.txt per round; never discard partial results — analyze and advance"
- [[feedback_never_idle_between_ticks]] — "Never wait for the next cron tick — the cron is a watchdog, not a work queue; keep measuring continuously"
- [[feedback_never_stop]] — Never say "let's continue next session" or "we did a lot today" — keep working in infinite loop
- [[feedback_no_copying_winners]] — "NEVER copy Duck/winner harness code — reference-only for understanding; we must design a BETTER original solution (user standing order, 2026-07-14)"
- [[feedback_no_python_augmentation]] — Do NOT add Python-level post-processing to patch LLM mistakes. Enrich the wiki so the LLM reasons correctly from frame observations alone.
- [[feedback_online_rl_is_the_spine]] — "The performance lever for ARC-AGI-3 is TEST-TIME ONLINE CNN+RL (learn fresh per game), NOT sample-specific algorithm primitives or offline-on-public RL — both fail to transfer to the 110 private games"
- [[feedback_parallel_build]] — Tool development runs as one background agent per game, integrated centrally and kept only on a full-25 measurement
- [[feedback_phase_commit]] — Commit per phase with docs update, code review, and push convention
- [[feedback_preserve_framework]] — When a test/framework is portable by design, do not fold local-environment coupling into it; build a separate driver instead
- [[feedback_proactive_doc_sync]] — Update CLAUDE.md and project memories without being asked when phase/state changes
- [[feedback_rl_not_abandoned]] — "One bad RL run is not a verdict on the method; validate multiple versions / checkpoints with keep-best before concluding, and don't blind-benchmark the top team"
- [[feedback_runner_budget_override]] — Never lower total_budget in scripts/run_ensemble.py below class default without explicit justification — silent regressions follow
- [[feedback_submission_user_decides]] — NO automatic Kaggle submissions — the user decides when to submit (standing order 2026-07-14); also minimize GPU quota usage (CPU-only pushes for LLM-free kernels, batched experiments only)
- [[feedback_verify_via_regression]] — Trust scripts/ensemble_results.json and full 25-game runs over commit messages
- [[feedback_wiki_doctrine]] — The .wiki/ directory must support LLM reasoning, not just document current state; write history + concepts + lessons + reasoning chains, heavily cross-linked
- [[policy_two_stage_tools_then_llm]] — TOP POLICY — build generic tools to 25/25 sample clears myself, THEN the LLM patches them on hidden games; order, machines, and what is NOT the plan
- [[project_bc_transfer_ceiling]] — "BC policy trained on 25-game PUBLIC gold has a transfer ceiling; eval is 110 PRIVATE games — measure transfer, don't trust the proxy score"
- [[project_cpu_dev_vm_ceph_build]] — "GCP credits EXHAUSTED (real money now) — for CPU-only work use the ceph-build VM instead: ssh -i ~/VM/keys/nfw-dev.pem ubuntu@ceph-build (64 cores/251GB RAM/Python 3.12). GCP only when GPU is truly required, with user awareness."
- [[project_current_state]] — Admorphiq ARC-AGI-3 — verified 22/25 games, 56/182 levels (~30.77%); commits claim 25/25/69 but unverified
- [[project_dev_test_env]] — "The Kaggle-matched GCP dev/test environment + how to run tests (score_efficiency, orchestrator_probe), model candidates, and the local-Mac limits — for cross-session continuity"
- [[project_ensemble_strategies]] — Current ensemble strategy count, categories, and target games for each new strategy
- [[project_game_analysis]] — Detailed analysis of each game's mechanics, what works, what doesn't, and hypotheses for solving
- [[project_general_direction_worldmodel]] — "The general path to private-game score = object-centric perception + online (test-time) world model + search planning + RL; BC is a warm-start, not the destination"
- [[project_kaggle_eval_and_metric]] — "ARC-AGI-3 eval = 110 PRIVATE unseen games; metric = efficiency SQUARED (min(human/agent,1)^2); leaderboard reality + submission mechanics"
- [[project_kaggle_hardware]] — "ARC-AGI-3 2026 Kaggle eval hardware is g4-standard-48 (96GB VRAM), NOT T4 16GB — corrects a foundational CLAUDE.md assumption"
- [[project_leaderboard_2026_08_and_method]] — "LB re-checked 2026-08-25: top = 5.99 (cstl), 2nd 4.58 (Tufa), 12th 2.66 — the old '1.38-1.61 top band' is STALE by 4x. Ours 0.20. Goal: clear all games + chase within August. Measurement method = ceph-build 64c, ALL 25 games in parallel."
- [[project_leaderboard_first_score]] — "First hidden-set LB score 0.14 (v6, 2026-07-14); measured public-proxy→hidden transfer ~13%; LB top band 1.38–1.61 (supersedes old \"top 12.58%\" anchor)"
- [[project_llm_selection]] — Qwen 3 8B is primary Kaggle candidate; 14B as reserve; Gemma 4 26B MoE excluded due to T4 VRAM; edge variants dropped
- [[project_online_rl_baseline]] — "Deployed online-RL card's honest RHAE baseline = full-25 mean game_score 0.0051 (14/25 clear, mostly L1); depth is the ceiling; learner saturated to exploration tweaks"
- [[project_phase8_restart]] — Linear Phase 8 plan replaced by agentic loop with Cognition/Memory/Action separation and dev/Kaggle time boundaries
- [[project_phase8_wiki]] — Admorphiq Phase 8 uses markdown knowledge base (no vector DB) readable by Qwen 3 8B offline on Kaggle
- [[project_r56_r58_state]] — "R56-R58 state (2026-07-15 dawn): generic kernel library + script25 adapters (ft09 3/6 super-human, sb26 first live clear), win-condition typology + GoalLedger, explanation-layer protocol; Codex verdicts list; VM/engagement runs in flight"
- [[project_stage1_tool_build]] — Stage 1 = build frame-only rule-recovery tools until the 25 sample games clear; how to build one, and the scoreboard
- [[project_submission_not_reproducible]] — "CORRECTED — the 0.20 card IS rebuildable (solvers live in world_model_agent.py, not adapters25); what is missing is the BUILD PROCEDURE: no kernel-metadata, no push script, no dataset-version to commit mapping"
- [[project_unified_harness_r53]] — R53 unified self-improving harness — 6 from-scratch generic tools + retry loop; graph clears 3/9 legacy games; continuation = per-tool strengthening
- [[project_wiki_agent_first_run]] — 40-env Qwen 3 8B WikiAgent bench — 15/40 envs, 36/290 levels (12.41%), classification accuracy 45%
- [[reference_karpathy_llm_wiki]] — Full Karpathy "LLM Wiki" (2026-04-02) analysis in Korean is saved at docs/llm_wiki_karpathy_analysis_ko.md; gap table maps missing pieces to R23+ sub-rounds

## Related

- [[../top_policy]] — the two stages these memories serve.
- [[../rounds/r101_tool-development]] — the round that added the stage-one memories.
