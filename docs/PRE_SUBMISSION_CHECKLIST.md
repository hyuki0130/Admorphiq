# Pre-Submission Checklist — ARC-AGI-3 Milestone 1

> **Deadline**: June 30 2026 23:59 UTC (= Jul 1 08:59 KST). The Kaggle
> **notebook must be public/open-source by then** to qualify for the M1 prize.
> Last updated: 2026-06-29 (R24/R26).

Two surfaces go "public": the **GitHub repo** (our source of truth) and the
**Kaggle notebook** (the competition open-source requirement). This doc covers
both, in order: **Part A** = what to do in the repo before committing + opening
it, **Part B** = the Kaggle submission path + prerequisites.

---

## Current deployed state (what would submit today)

| Item | Value |
|---|---|
| Deployed model | `models/bc_policy.pt` = **v6** (BC retrain on 24-game gold) |
| Proxy score (25 public games / 40 envs, real metric) | **3.41%** (`min(human/agent,1)²`, level-weighted) |
| Games clearing ≥1 level | **15 / 25** unique |
| Prior baseline | v2 = 2.20% / 10 games → v6 is **+55% score, +50% coverage** |
| RL fine-tune (v6_rl) | 1.54% / 9 — first-config run underperformed, NOT deployed (one config, **not a method verdict**; redesign per `feedback_rl_not_abandoned`) |
| Agent class | `KaggleBCAgent` (official `agents.agent.Agent` subclass) + `BCPolicyAgent` core (cycle-break + Test-Time Training) |
| Tests | **374 passing**, ruff clean |
| Offline submission path | **verified locally** (no internet) via `scripts/verify_offline_submission.py` |
| Leaderboard context | random 0.18 · stochastic-sample 0.25 · FORGE 0.43 · top (Tufa/Dries Smit) 1.21 |

---

## Part A — Repo: do before `git commit` + going public

### A1. Secrets & sensitive data — DONE ✅
- [x] Secret scan clean (no hardcoded API keys/tokens — all matches are NLP "token" counts).
- [x] No `.env` / credential / `.pem` / `.key` files tracked.
- [x] `models/*.pt`, `data/`, `*.log`, `*.jsonl`, `.omc/` are git-ignored (not published).
- [x] **`environment_files/` is git-ignored** — these are competition game assets, NOT ours. Keep them out of the public repo.

### A2. License — DONE ✅
- [x] `LICENSE` (MIT) added at repo root. Required for the open-source prize condition.

### A3. Documentation currency
- [x] `README.md` rewritten to current state (was stale at Phase 2.5 / Mar 31). Now reflects the BC+TTT agent, v6 deployment, offline submission.
- [x] `notebooks/SUBMISSION.md` — verified offline mechanism + upload table.
- [x] `docs/sprint_m1_architecture_20260625.md` — architecture source-of-truth (metric, contract, pivot).
- [x] This checklist (`docs/PRE_SUBMISSION_CHECKLIST.md`).
- [ ] (optional) Trim/curate `.wiki/` if any pages contain stale claims you don't want public — the wiki is LLM-reasoning fuel and ships in-repo, but is NOT loaded by the BC submission. Safe to leave as-is.

### A4. Code to commit (currently untracked / modified)
The pipeline left these uncommitted. They belong in the public source:
- `scripts/train_rl.py` — REINFORCE/actor-critic RL fine-tune from BC init (new).
- `scripts/_v6_rl_pipeline.sh` — v6 BC→RL→score→auto-promote pipeline (new).
- `scripts/train_policy.py` — balanced sampling + DAgger-lite + efficiency-weighting (modified).
- Plus this commit: `LICENSE`, `README.md`, `docs/PRE_SUBMISSION_CHECKLIST.md`.

> **NOTE**: `models/bc_policy.pt` (v6) is **git-ignored by design** — it ships as a
> Kaggle Dataset (Part B), not in git. Do not force-add it.

### A5. Final repo gates (run before commit)
```bash
uv run pytest -q                       # expect 374 passing
uv run ruff check .                    # expect clean
git status -s                          # confirm only intended files staged
```

### A6. Commit + go public (user-gated)
```bash
git checkout -b r26-submission-prep    # not on main for a feature commit
git add LICENSE README.md docs/PRE_SUBMISSION_CHECKLIST.md \
        scripts/train_rl.py scripts/_v6_rl_pipeline.sh scripts/train_policy.py
git commit            # message ends with the Co-Authored-By trailer
```
- [ ] Push, open PR (or merge to main per your flow).
- [ ] On GitHub: **Settings → Danger Zone → Change visibility → Public**.
- [ ] (After public) confirm `environment_files/` and `models/*.pt` are absent from the public tree.

---

## Part B — Kaggle: the submission path

> Mechanism verified locally 2026-06-29. Full detail + dependency notes:
> `notebooks/SUBMISSION.md`. Notebook cells: `notebooks/kaggle_submission.py`.

### B1. One-time: upload our assets as Kaggle Datasets (no pip/internet at runtime)
| Dataset | Source (repo) | Size | Mounts at | Notebook expects |
|---|---|---|---|---|
| `admorphiq-src` | `src/admorphiq/` | ~1.9M | `/kaggle/input/admorphiq/src/admorphiq` | dir on `sys.path` |
| `admorphiq-bc-weights` | `models/bc_policy.pt` (**= v6**) | 131M | `/kaggle/input/<weights>/bc_policy.pt` | `BC_WEIGHTS` env, else `models/bc_policy.pt` |

- [ ] **Re-upload the weights dataset** — `bc_policy.pt` changed to v6 today (md5 `578ea6da…`). If a stale v2 dataset exists, push a new version.

### B2. Create the competition notebook
- [ ] ARC-AGI-3 competition page → **Code → New Notebook**.
- [ ] **GPU on** (`g4-standard-48`, RTX PRO 6000 96GB).
- [ ] **Settings → Internet: OFF** (competition rule; the offline path is built for this).
- [ ] **Attach competition inputs** (Data tab): `ARC-AGI-3-Agents`, `arc_agi_3_wheels`, `environment_files`.
- [ ] **Attach our 2 datasets** (`admorphiq-src`, `admorphiq-bc-weights`).
- [ ] First cell: set `BC_WEIGHTS=/kaggle/input/<weights-dataset>/bc_policy.pt`.

### B3. Run → submit
- [ ] Paste cells from `notebooks/kaggle_submission.py` (`# %%` = one cell).
- [ ] **Save Version → Save & Run All (Commit)**. Must finish ≤ 9h.
- [ ] Confirm `/kaggle/working/submission.json` was written.
- [ ] **Submit** that version (Final Submission; up to 2 allowed).
- [ ] **Make the notebook public** before June 30 23:59 UTC (prize eligibility).

### B4. Pre-submit sanity (local, optional but recommended)
```bash
# offline submission.json path (the critical one) — no internet:
uv run python scripts/verify_offline_submission.py --games ar25 dc22 --max-actions 12
# agent acts, no crash:
uv run python scripts/smoke_kaggle_agent.py
```

---

## Risk notes / gotchas
- **Swarm is broken offline** (fetches an API key over HTTP). The notebook uses a
  direct OFFLINE loop instead — already fixed (commit `7d9a95f`). Do not revert to
  `Swarm` / `listen_and_serve`.
- **`OPERATION_MODE` env override**: the notebook forces `os.environ["OPERATION_MODE"]="offline"`
  because a `competition` value would override the constructor and need the network.
- **Proxy ≠ leaderboard**: 3.41% is on the 25 public games. Eval = 110 PRIVATE games;
  the BC policy was trained from-pixels (transferable), but expect the private number to differ.
  Getting a valid offline run on the board (beating the 0.25 sample floor) is the P0 win.
- **TTT is on by default** in `BCPolicyAgent` (`BC_TTT=1`); scoring above was with `BC_TTT=0`
  for speed-ranking, so the live submission may score equal-or-higher.
