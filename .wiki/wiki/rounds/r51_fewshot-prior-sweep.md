---
title: R51 — few-shot scale & mechanics-prior sweep (honest protocol)
type: round-log
round: R51
axis: ewm-quality
keywords: [executable-world-model, few-shot-scale, mechanics-prior, adaptive-config, train-fit-selection, union-ensemble, gemma4-31b, gpt-oss-120b]
verdict: no single config beats gemma/f15 0.133, BUT per-game config-UNION = 0.211 (1.6x) — adaptive multi-config synthesis selected by train-fit is the real lever; 10/18 games are zero under ALL 6 honest configs (stable out-of-scope set)
commit: pending
date: 2026-07-08
description: Two-axis sweep (few 15→40, mechanics prior) x 2 models — averages flat but effects are strongly game- and model-dependent; per-game union 0.211 motivates runtime adaptive-config synthesis
---

# R51 — few-shot scale & mechanics-prior sweep

Design: vs the [[r50b_honest-k8]] baseline (gemma4-31b-q8 / gpt-oss-120b, few=15, no prior,
K=8, honest protocol), two isolated axes: **A** few 15→40 (data), **B** few=15 + game-agnostic
mechanics vocabulary in the system prompt (prior; `--mechanics-prior`, commit `fb40e58`).

## Means (sel-exact, 18 games)

| config | gemma4-31b-q8 | gpt-oss-120b |
|---|---|---|
| f15 baseline | **0.133** | 0.039 |
| A: few=40 | 0.100 | 0.078 (2.0x) |
| B: prior | 0.122 | 0.117 (3.0x, best 0.144) |

Both axes FLAT-to-negative for gemma, strongly POSITIVE for gpt-oss — data appetite and
prior benefit are model-dependent. No single config beats gemma/f15.

## The real finding: per-game config-UNION = 0.211 (1.6x best single)

Each config uniquely tops some game: gemma/f15 → ar25 0.80, ka59, tr87; gemma/f40 → **sb26
1.00** (0.10 at f15!); gemma/prior → dc22 0.40; oss/f15 → g50t, sc25; oss/f40 → sp80;
oss/prior → ar25 0.80, lf52 1.00. Per-game max across the 6 = **0.211**. gemma-only 3-config
union = 0.189 — one model captures ~90% of it.

**Runtime-realizable**: run synthesis under 2-3 config variants at discovery, pick per game by
train-fit (labels the agent owns). Cost = 2-3x synthesis calls (~2-6 min/game on the 96GB
budget) — affordable within 9h/110 games.

Notable pair: few-shot count is game-dependent (lf52 1.00@15 → 0.00@40; sb26 0.10@15 →
1.00@40) — fixed budgets are wrong; adaptive selection resolves it without any game ID.

## The stable zero-set (10/18)

lp85 re86 s5i5 sk48 su15 tn36 tu93 vc33 wa30 (+near-zero g50t) score 0 under ALL 6 honest
configs. Diff-only few-shot induction saturates here regardless of model/data/prior — these
need a different observation surface (interactive probing, object-level serialization) or stay
graph/RL territory ([[r36_graph-frontier-bfs]]). Do NOT re-run more config sweeps hoping these
flip. ⛔

**Related**: [[r50b_honest-k8]] (baseline + honest protocol), [[r50_cloud-bench-k3]],
[[r49_ewm-bench-partial]].
