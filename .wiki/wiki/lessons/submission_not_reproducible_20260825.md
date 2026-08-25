---
type: lesson
keywords: [submission, kaggle, reproducibility, leaderboard, card, adapters25, chained-agent, provenance]
date: 2026-08-25
verdict: The 0.20 leaderboard card CANNOT be rebuilt from this repository. Nothing on the submission path can reach the adapter work.
---

# The best card we have is not in the repository (2026-08-25)

## The finding

Two submissions exist on the competition leaderboard:

```
54664749  2026-07-14  "Admorphiq v3: cd82 6/6 + sb26 portal-DFS + su15 reset-retry; proxy 5.83"  →  0.20
54637991  2026-07-13  "Admorphiq v1: LLM-free chained agent; proxy 1.072"                        →  0.14
```

`notebooks/kaggle_submission.py` builds **v1**. Its last commit is `03aacfc`, it registers
`KaggleChainedAgent`, and its own header still says *"measured 1.072% on the 25-game dev proxy"*.

**There is no v3 anywhere in the repository.** Searched and found nothing:

* no commit to `notebooks/kaggle_submission.py` after `03aacfc`;
* no `kernel-metadata.json` ever added, on any branch (`git log --all --diff-filter=A`);
* no script that pushes a kernel or a submission (`kernels push` / `competitions submit` appear
  nowhere under `scripts/`);
* no branch carrying one — `main`, `r27-transfer-pivot`, `r50-depth-class`,
  `backup-before-author-rewrite` all lack it;
* the Kaggle account lists 14 kernels and none is a submission kernel.

## Why it cannot be reconstructed by inference either

The submission path is `kaggle_submission.py` → `KaggleChainedAgent` →
`ChainedAgent` / `UnifiedAgent` / `WorldModelAgent`. **Nothing in that chain can reach
`adapters25`.** The only importers anywhere are `hypothesis_select/{templates,parse}.py` — the R95+
DSL, which is not on the submission path — and dev-only `scripts/_*.py` probes.

So the v3 kernel that scored 0.20 either was edited directly in Kaggle's web UI or was built from
a tree that was never committed. Its "proxy 5.83" is likewise unreproducible: no run directory in
`scripts/rounds/` carries that number.

## What this costs

* **The baseline to beat exists only as a Kaggle artefact.** Any new candidate is being compared
  against a number we cannot rebuild, inspect, or diff.
* **The 3.4% transfer ratio** (proxy 5.83 → hidden 0.20) — the project's only measurement of how
  public-proxy depth converts to leaderboard score — is anchored to that unreproducible artefact.
* Two months of adapter work (R56–R84, script25 32.96%) sits behind a deliberate quarantine, and
  the one submission that *did* ship solvers is the one we cannot examine.

## The rule

⛔ **A submission is not made until its build is committed.** The kernel source, its
`kernel-metadata.json`, and the exact command that pushed it belong in the repository in the same
commit that claims the score. A leaderboard number whose build is not in git is a number the
project cannot act on — it can only be admired.

Related: [[false_claim_verification_20260715]] (a number is a triple: value, budget, env — extend
it to *and a build you can re-run*), [[instrument_validity_20260825]].
