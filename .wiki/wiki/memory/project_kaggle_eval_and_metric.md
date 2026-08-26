---
name: project_kaggle_eval_and_metric
description: "ARC-AGI-3 eval = 110 PRIVATE unseen games; metric = efficiency SQUARED (min(human/agent,1)^2); leaderboard reality + submission mechanics"
metadata: 
  node_type: memory
  type: project
  originSessionId: c7e91ecf-c8c0-4c3c-bd62-4722ff123df5
---

Verified 2026-06-25 from the live Kaggle competition pages (Data/Overview/Code/Leaderboard/Rules).

**Eval set**: NOT the 25 preview games. Evaluation uses a **separate private set of 110 games** the agent has never seen — half → Public LB, half → Private LB. The 25 in `environment_files/` are dev-only; local 25-game scores do NOT predict the leaderboard.

**Metric = RHAE** (Relative Human Action Efficiency; exact, from https://docs.arcprize.org/methodology, verified 2026-06-29):
- **Per-level**: `level_score = (human_baseline_actions / ai_actions)²` — SQUARED. Capped at **1.15** (beating the human count scores >1.0, up to 1.15), NOT 1.0. Baseline = **upper-median** first-time human per level. An "action" = an env-state-changing command (internal reasoning/retries excluded).
- **Per-game**: **weighted average** of per-level scores, weight = 1-indexed level number; denominator = sum of ALL levels' weights. So max game score is completion-capped: 4 of 5 levels → max `(1+2+3+4)/(1+2+3+4+5)=66.7%`; **100% requires clearing the final level**.
- **Total**: mean of per-game scores; 0–100%, can exceed 100% via the 1.15 cap. ⚠️ **BASELINE FIGURES DISPUTED (R34, 2026-07-05)**: the "random≈0.18 / stochastic≈0.25 / Tufa 1.21" figures below are UNVERIFIED (no source URL ever recorded) and are contradicted by the web-verified RHAE top score **StochasticGoose = 12.58% (0.1258)**, 2nd = 6.71%. On the faithful RHAE harness a MEASURED random agent scores **0.0000** on our 9 games (R34) — 0.18 is impossible for random on RHAE (needs all levels of all games cleared at ~2.36× human). Treat 0.18/0.25/1.21 as WRONG until re-sourced; real anchors: random≈0.001, top≈0.126.
- Consequence: **brute-force completion ≈ 0** (BFS in 374 actions vs human ~15 → `(15/374)²≈0.0016`). Deep + EFFICIENT clears dominate (level-index weight × square).

**Our harness `scripts/score_efficiency.py` is FAITHFUL to this** — same squaring, same level-index weighted average, same all-levels denominator (only diff: caps per-level at 1.0 vs official 1.15, negligible since we never beat human). So its `total_score` fraction is directly comparable to the leaderboard scale; all round measurements are trustworthy dev proxies.

**Leaderboard reality** — ⚠️ SEE R34 DISPUTE ABOVE. Originally recorded (2026-06-25, UNVERIFIED): "Random = 0.18, stochastic = 0.25, top = 1.21, gold ≈ 0.60". R34 (2026-07-05) found these unsourced and RHAE-impossible; web-verified reality: **top (StochasticGoose/Dries Smit) = 12.58%, 2nd = 6.71%**; measured RHAE random on our harness = 0.0000. Use these. Public LB = ~50% of the hidden test set (live); Private LB = the other ~50% (final standings). "Entries" = a team's submission count.

**Submission mechanics**: code competition, notebook-only; ≤9h; internet disabled; offline open-weight models OK (read-only mount). **1 submission/day** (resets 00:00 UTC); up to **2 Final Submissions** selected at the end (best auto-picked). `kaggle kernels push` runs a notebook server-side WITHOUT consuming a slot (free validation); `kaggle competitions submit -k <kernel>` consumes the daily slot. **Swarm/`listen_and_serve` is BROKEN offline** (builds its own NORMAL-mode Arcade fetching an API key over HTTP) — use a **direct OFFLINE loop**: `Arcade(OperationMode.OFFLINE, environments_dir=...)` → `open_scorecard` → per-game `make`+`agent.main()` → `close_scorecard` → write submission.json (verified `scripts/verify_offline_submission.py`; see `notebooks/SUBMISSION.md`). M1 = June 30 23:59 UTC; notebook must be public by then.

**How to apply**: optimize for EFFICIENT deep clears + coverage on unseen games, not raw completion. Design = cheap discovery → online world model → efficient planning; offline LLM hypothesizes the goal at discovery. Full plan: `docs/sprint_m1_architecture_20260625.md`. Relates to [[project_kaggle_hardware]], [[project_general_direction_worldmodel]], [[project_bc_transfer_ceiling]].
