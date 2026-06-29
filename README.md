# Admorphiq

**Adaptive Morphing Intelligence** — an AI agent for the [ARC Prize 2026 (ARC-AGI-3)](https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-3) competition.

ARC-AGI-3 is the first interactive reasoning benchmark. Agents must explore unfamiliar game environments, discover rules through trial and error, and adapt in real-time. This requires genuine fluid intelligence: exploration, hypothesis generation, planning, and learning from sparse feedback.

> **Evaluation reality** (verified from the official pages, 2026-06-25): the
> leaderboard runs on **110 PRIVATE unseen games**, not the 25 public preview
> games. The metric is **efficiency squared** — per level `min(human_actions /
> agent_actions, 1)²`, level-index-weighted per game, averaged over games. So
> brute-force completion scores ≈ 0; *efficient* completion is what counts.
> Hardware: `g4-standard-48` (RTX PRO 6000, 96GB VRAM), ≤ 9h, internet disabled.

## Current approach (Milestone 1 sprint)

The deployed agent is a **behavior-cloned CNN policy with Test-Time Training
(TTT)** — the recipe the top ARC-AGI-3 teams use, learned from frame pixels so
it transfers to unseen games (no game-id / sprite-tag hardcoding).

1. **Gold trajectories** — efficient solution traces for 24 of the 25 public
   games (`scripts/generate_traces.py` → `data/traces/*.npz`).
2. **Behavior cloning** — train a `PerceptionModel` (16ch one-hot frame → 4101
   logits: 5 action + 4096 coord) on those traces with per-game balanced
   sampling, DAgger-lite, and efficiency-weighting (`scripts/train_policy.py`).
3. **Test-Time Training** — at inference the policy adapts online per game,
   with a cycle-breaker to escape loops (`src/admorphiq/bc_agent.py`).
4. **Offline submission** — `KaggleBCAgent` (an official `agents.agent.Agent`
   subclass) runs the policy in a fully offline Kaggle notebook.

| Metric (25 public games / 40 envs, real competition metric) | Value |
|---|---|
| Deployed model `models/bc_policy.pt` (= **v6**, BC retrain on 24-game gold) | **3.41%** |
| Games clearing ≥1 level | **15 / 25** |
| Prior baseline (v2) | 2.20% / 10 games |
| Tests | 374 passing, ruff clean |
| Offline submission path | verified locally (no internet) |

> An RL fine-tune (REINFORCE from the BC init, `scripts/train_rl.py`) scored
> 1.54% (< BC 3.41%) on its first config, so it is not deployed — but that is
> one hyperparameter run, **not a verdict on the method**. RL-from-BC is
> sensitive; redesign (lower LR, stronger KL anchor, drop frame-change shaping,
> keep-best-by-eval) is the next step, not abandonment.

**BC is the M1 ship asset and a warm-start — not the destination.** Eval is 110
PRIVATE unseen games, but BC learned from gold on the 25 PUBLIC ones, so 3.41%
is partly in-sample (the held-out transfer test, `scripts/_transfer_test.sh`,
measures the real transfer). The general path to the private leaderboard is an
agent that learns **at test time, per game**: object-centric perception → online
world model → search-based planning → RL on top, with BC as the exploration
prior. See [docs/sprint_m1_architecture_20260625.md](docs/sprint_m1_architecture_20260625.md) §8.

An offline-LLM "wiki" reasoning track (Qwen/Gemma reading a markdown knowledge
base, `.wiki/`) is built and gated **off** — it was net-neutral-to-negative at
the 8B–14B scale tested. It is retained as a future lever (goal hypothesis at
discovery), not abandoned.

## Project structure

```
admorphiq/
├── src/admorphiq/
│   ├── bc_agent.py          # BCPolicyAgent — CNN policy + cycle-break + TTT (core)
│   ├── kaggle_bc_agent.py   # KaggleBCAgent — official Agent subclass for submission
│   ├── general_agent.py     # GeneralAgent — discovery + efficient planning
│   ├── adapter.py           # AdmorphiqAdapter (official ↔ internal bridge)
│   ├── perception/          # CNN backbone + PerceptionModel (dual head, 34M)
│   ├── world_model/         # State transition prediction (1.6M params)
│   ├── planner/             # BFS / graph / sequence solvers
│   ├── hypothesis/          # WikiAgent + dispatcher (offline-LLM track, gated off)
│   ├── llm/                 # Offline LLM backends (Ollama dev / CUDA wheel Kaggle)
│   └── utils/               # ExperienceBuffer, logging
├── scripts/
│   ├── generate_traces.py        # gold trajectory dataset
│   ├── train_policy.py           # behavior-cloning training
│   ├── train_rl.py               # REINFORCE/actor-critic RL fine-tune
│   ├── score_efficiency.py       # REAL competition-metric harness
│   └── verify_offline_submission.py  # offline submission.json proof
├── notebooks/
│   ├── kaggle_submission.py      # the submission notebook (cells)
│   └── SUBMISSION.md             # how to submit (verified mechanism + uploads)
├── docs/
│   ├── sprint_m1_architecture_20260625.md   # architecture source-of-truth
│   └── PRE_SUBMISSION_CHECKLIST.md           # repo + Kaggle pre-submit checklist
├── data/traces/             # gold *.npz (git-ignored)
├── models/                  # *.pt checkpoints (git-ignored; ship as Kaggle Dataset)
├── .wiki/                   # offline-LLM knowledge base (markdown)
├── pyproject.toml
└── CLAUDE.md                # full architecture & competition context
```

## Installation

```bash
# Requires Python 3.12+ and uv
uv sync
```

## Usage

```bash
# Score the deployed agent with the real competition metric (25 public games)
uv run python scripts/score_efficiency.py --agent bc --games all

# Train behavior cloning from the gold traces
uv run python scripts/train_policy.py --epochs 40 --out models/bc_policy.pt

# Prove the offline submission path produces a valid submission.json (no internet)
uv run python scripts/verify_offline_submission.py --games ar25 dc22 --max-actions 12
```

## Submission

The agent runs **fully offline** in a Kaggle notebook and writes
`/kaggle/working/submission.json` itself. The notebook (`notebooks/kaggle_submission.py`)
uses a direct OFFLINE `Arcade` loop — see **[notebooks/SUBMISSION.md](notebooks/SUBMISSION.md)**
for the verified mechanism + the dataset upload table, and
**[docs/PRE_SUBMISSION_CHECKLIST.md](docs/PRE_SUBMISSION_CHECKLIST.md)** for the
full repo + Kaggle checklist.

## License

[MIT](LICENSE)
