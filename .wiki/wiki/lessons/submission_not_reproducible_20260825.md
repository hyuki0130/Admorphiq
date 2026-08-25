---
type: lesson
keywords: [submission, kaggle, reproducibility, leaderboard, card, provenance, absence-of-evidence, wrong-artefact]
date: 2026-08-25
verdict: CORRECTED — the 0.20 card IS reproducible from the repo. What is missing is the BUILD PROCEDURE (kernel-metadata, push command, dataset-version → commit mapping), not the source. The first version of this page claimed the opposite because it searched for the wrong artefact.
---

# I searched for the wrong artefact and concluded absence (2026-08-25)

## The claim I made, and why it was wrong

I asserted that the current leaderboard card — v3, `54664749`, **0.20**, 2026-07-14 — could not be
rebuilt from this repository. The reasoning was:

> the submission path is `kaggle_submission.py` → `KaggleChainedAgent` →
> `ChainedAgent`/`UnifiedAgent`/`WorldModelAgent`, and **nothing in that chain imports
> `adapters25`**, so the solvers the submission describes cannot be reached.

The grep was correct. The **inference was not.** The submission's solvers were never in
`adapters25`; they live on the submission path itself:

```
src/admorphiq/world_model_agent.py:96   from .ring_paint import ARROW_COORDS, detect_paint_layout, nav_path
src/admorphiq/world_model_agent.py:112  from .sort_match import detect_portal_sort, plan_match_placement
src/admorphiq/world_model_agent.py:209  _PHASE_PAINT = "ring_paint"
src/admorphiq/world_model_agent.py:208  _PHASE_PORTAL_SORT = "portal_sort"
```

and `WorldModelAgent` is exactly what `KaggleChainedAgent` probes with first. The submission
description — *"cd82 ring-paint solver + sb26 portal-DFS + su15 reset-retry"* — names those three
by their module names. I searched for the quarantined adapter library, found nothing, and read that
as the solvers being absent, when they were sitting in the file I had already identified as on the
path.

**What actually found it:** the round log. `git log --all --grep="5\.83"` returns `3d0fa81`,
*"v10 kaggle-validated proxy 5.8307"*, and `.wiki/wiki/rounds/r53_unified-harness.md:3806` records
the build outright — **"Kernel v10 (dataset v6: ring_paint cd82 solver + sb26 portal-DFS + su15
reset-retry)"**. The project's own discipline — *if it is not in your context, LOOK IT UP in the
round pages* — had the answer, and I ran five negative searches before consulting it.

## What IS missing, stated precisely

The **source** is present and the card is rebuildable. The **build procedure** is not recorded:

* no `kernel-metadata.json` was ever committed, on any branch;
* no script performs `kernels push` / `competitions submit`;
* the mapping from Kaggle **dataset version** (`admorphiq-src` v6) to the **commit** it was built
  from is written nowhere, so "v10 = dataset v6" cannot be resolved to a tree;
* the proxy `5.8307` has no run directory under `scripts/rounds/` on either machine — it is recorded
  only as prose in the r53 page.

So rebuilding is a reconstruction from prose, not a re-run. That is a real cost, and much smaller
than the one I claimed.

## The rules

1. ⛔ **Absence of a grep is not absence of the thing.** Before concluding something is missing,
   name what artefact you searched for and ask whether the thing could exist under another name.
   Here the same capability had two homes and I only knew one.
2. **Consult the round log BEFORE the filesystem.** One `grep` of `.wiki/wiki/rounds/` answered in
   one step what five filesystem searches got wrong.
3. **Commit the build with the score.** Kernel source, `kernel-metadata.json`, the push command,
   and the dataset-version → commit mapping belong in the commit that claims a leaderboard number.

Related: [[false_claim_verification_20260715]], [[instrument_validity_20260825]].
