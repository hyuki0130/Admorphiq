---
name: project-leaderboard-first-score
description: "First hidden-set LB score 0.14 (v6, 2026-07-14); measured public-proxy→hidden transfer ~13%; LB top band 1.38–1.61 (supersedes old \"top 12.58%\" anchor)"
metadata: 
  node_type: memory
  type: project
  originSessionId: 3f835f42-61d8-4a15-811f-a74e74370d28
---

**First leaderboard score (2026-07-14)**: submission #54637991 (kernel v6, LLM-free ChainedAgent,
local public-25 proxy 1.0721) scored **publicScore 0.14** on the hidden-set public split.

- **Measured transfer ratio ≈ 13%** (public-25 proxy → hidden LB). The hidden ~110 games are
  unseen; only the genuinely generic fraction of the card transfers.
- **Leaderboard scale corrected**: live LB top on 2026-07-14 = **1.61** (Tecnod8.AI), then 1.56×3,
  1.54…; top-20 packed in 1.38–1.61. This SUPERSEDES the old memory/wiki anchor "top =
  12.58% (StochasticGoose)" — wrong scale for the current LB.
- **Why:** rank is driven by HIDDEN-GAME TRANSFER, not public-proxy depth alone. Local proxies
  (v7 1.6054, v8 1.7091) are numerically top-band but transfer at ~13%.
- **How to apply:** justify every mechanism as frame-observable + game-agnostic; treat the proxy
  as necessary-not-sufficient; expect hidden scores ≈ 0.13× proxy until transfer improves.
  Related: [[project_kaggle_eval_and_metric]], [[project_unified_harness_r53]].

**Second datapoint (2026-07-14 18:12 KST):** submission #54664749 (kernel v10, proxy 5.8307 —
cd82 6/6 + sb26 2/8 + su15 3/9 mechanic-solver wins) scored **hidden publicScore 0.20**.
Descriptive pairs: (1.072→0.14), (5.83→0.20). The +4.7 proxy jump from public-game solver depth
bought +0.06 hidden — public-specific capability barely transfers, per-Codex "treat pairs
descriptively, don't fit a ratio." The hidden-LB lever is generic behavior (R55). Same day, the
R55 repl agent scored its FIRST level clear (su15 L1) — **initially credited to the v7
GoalAuditor, but the matched12 OFF/ON experiment (2026-07-14 22:40, out9) FALSIFIED that**:
the base agent clears su15 3/3 at the identical 19 L1 actions with audit OFF too, so the
audit was non-load-bearing. The matched12 gate FAILED (audit net-negative: lost r11l via
wall-throughput cost, RHAE ON 0.0048 < OFF 0.0055; 10/12 games both-arms-0). Lesson: a
single-game clear is not evidence a lever caused it — matched OFF/ON is required. The real
R55 lever is base capability on the 10/12 walls, NOT goal-revision. See
`.wiki/wiki/rounds/r55_code-repl-agent.md` matched12 RESULT section (commit e19a116).

