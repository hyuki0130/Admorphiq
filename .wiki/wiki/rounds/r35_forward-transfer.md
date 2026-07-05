---
title: R35 — forward-model pretrain + held-out transfer
type: round-log
round: R35
axis: neural-world-model transfer
keywords: [forward-model, pretrain, transfer, held-out, pos-weight, class-imbalance, dynamics]
verdict: TRANSFER CONFIRMED directionally (ratio 52.4% vs BC 0%) but absolute accuracy below planning gate — secondary asset
commit: cc866eb
date: 2026-07-05
---

# R35 — forward-model pretrain + held-out transfer test

**Question**: does a DYNAMICS model transfer across games where the BC POLICY (0%) did not?

**Method**: 50k transitions from random+change-biased rollouts (2000/game, 25 games), 18/7 split;
pretrain the 15K-param change-mask ForwardModel; measure held-out change-mask IoU vs in-sample.

**Finding 1 — class-imbalance collapse (also explains R32/R33!)**: plain BCE on the change mask
collapses to the trivial "no change anywhere" predictor (in-sample IoU 0.0000 at acc 0.99 — changed
cells are ~1-2% of the grid). Fixed with pos_weight (neg/pos, clamped ≤200). ⚠️ The ONLINE agent's
_train_forward uses the same plain BCE → its forward model likely ALSO collapsed during R32/R33,
which is why "accuracy" gates stayed open (fake acc) while planning was useless. A pos_weight fix
there could partially resurrect the neural planning track — noted as a future option.

**Finding 2 — dynamics DO transfer (directionally)**: with pos_weight, in-sample IoU 0.0487 (still
climbing at 8 epochs = undertrained), HELD-OUT IoU 0.0256 → **transfer ratio 52.4%** vs BC policy
0%. The core hypothesis is confirmed: action→change dynamics generalize across games.

**Verdict**: absolute IoU (~0.03-0.05) is far below a planning-usefulness gate (~0.5), so the neural
forward model stays a SECONDARY asset (could improve with more data/epochs/pos_weight-tuned online
training). PRIMARY deep-level path = R36 explicit graph (exact transitions, no accuracy question).

**Related**: [[r36_graph-frontier-bfs]], [[r32_neural-forward-model]], [[r29_warmstart-off]]
See map: [[rounds_index]].
