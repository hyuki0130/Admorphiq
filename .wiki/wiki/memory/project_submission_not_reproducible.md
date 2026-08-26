---
name: project-submission-not-reproducible
description: "CORRECTED — the 0.20 card IS rebuildable (solvers live in world_model_agent.py, not adapters25); what is missing is the BUILD PROCEDURE: no kernel-metadata, no push script, no dataset-version to commit mapping"
metadata:
  type: project
---

**Measured 2026-08-25, then CORRECTED the same day.** The leaderboard holds v1 (proxy 1.072) ->
**0.14** and v3/"v10" (proxy 5.8307) -> **0.20**, the current card.

⛔ My first claim — "v3 cannot be rebuilt from the repo" — was WRONG. I grepped the submission path
for `adapters25`, found nothing, and inferred the solvers were absent. They were never in
`adapters25`: `ring_paint` (cd82) and `portal_sort`/`sort_match` (sb26) are imported by
`src/admorphiq/world_model_agent.py`, which is exactly what `KaggleChainedAgent` probes with first.

`.wiki/wiki/rounds/r53_unified-harness.md:3806` records the build outright: **"Kernel v10 (dataset
v6: ring_paint cd82 solver + sb26 portal-DFS + su15 reset-retry)"**. One grep of the round pages
answered what five filesystem searches got wrong — consult the round log BEFORE the filesystem.

**What IS missing:** no `kernel-metadata.json` on any branch, no push script, no mapping from the
Kaggle dataset version to the commit it was built from, and no run directory for the 5.8307 proxy
(prose only). Rebuilding is a reconstruction from prose, not a re-run.

**How to apply:** commit the BUILD with any score claim (kernel source + metadata + push command +
dataset-version→commit). And treat a negative grep as evidence only after naming what other form
the thing could take. Full write-up:
`.wiki/wiki/lessons/submission_not_reproducible_20260825.md`.
