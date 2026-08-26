---
name: project-bc-transfer-ceiling
description: "BC policy trained on 25-game PUBLIC gold has a transfer ceiling; eval is 110 PRIVATE games — measure transfer, don't trust the proxy score"
metadata: 
  node_type: memory
  type: project
  originSessionId: c7e91ecf-c8c0-4c3c-bd62-4722ff123df5
---

The deployed agent `models/bc_policy.pt` = **v6** is a behavior-cloned CNN
(`PerceptionModel`, frame→4101 logits) trained on gold traces for 24 of the 25
PUBLIC games, with Test-Time Training + cycle-breaker at inference
(`src/admorphiq/bc_agent.py`). Proxy score = **3.41%** on the 25-game set (40
envs, real squared-efficiency metric), **15/25** games clearing ≥1 level
(v2 was 2.20% / 10).

**The blind spot:** the leaderboard runs on **110 PRIVATE unseen games**. BC
learned from gold on the PUBLIC games, so the 3.41% is partly in-sample. It only
transfers to the private set insofar as the CNN learned a *game-agnostic* prior
rather than the specific public games.

**Why:** ARC-AGI-3 measures skill acquisition on novel games; a policy that fit
the dev games can score near the exploration floor (0.18–0.25) on unseen ones.

**MEASURED 2026-06-29: transfer ≈ 0%.** The held-out test trained BC on 18 games
and scored the 7 it never saw → **0.00% transfer ratio, 0 of 7 unseen games
cleared** (vs 0.054 mean in-sample for v6). Confound ruled out: the same holdout
model clears its OWN training games (M0R0 2/6, LP85 1/8), so this is genuine
non-transfer, not undertraining. So the 3.41% proxy is essentially in-sample
overfit; on the private 110 BC alone lands near the exploration floor.

**How to apply:** treat 3.41% as a dev proxy, NOT a leaderboard predictor. BC v6
still ships for M1 as the safety net, but the spine for the private leaderboard
must learn at test time — pivot weight to [[project-general-direction-worldmodel]].
See [[project-kaggle-eval-and-metric]], [[feedback-rl-not-abandoned]].
