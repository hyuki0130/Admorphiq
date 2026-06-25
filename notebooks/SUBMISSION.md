# ARC-AGI-3 — How to submit (Milestone 1)

Our agent runs offline in a Kaggle notebook. Submission = run the notebook;
the harness auto-generates the submission file. Deadline: **June 30 2026
23:59 UTC** (= Jul 1 08:59 KST); the notebook must be **public / open-source**
by then to qualify for the milestone prize.

## One-time setup (Kaggle)

1. **Create the competition notebook**: on the ARC-AGI-3 competition page →
   Code → New Notebook. Enable GPU (`g4-standard-48`, RTX PRO 6000 96GB).
2. **Attach inputs** (Data tab of the competition already provides these as
   `/kaggle/input/`):
   - `ARC-AGI-3-Agents/` (framework), `arc_agi_3_wheels/` (offline wheels),
     `environment_files/`.
3. **Ship our code as a Kaggle Dataset** (no internet at runtime, so our
   package must be uploaded, not pip-installed):
   - Create a Kaggle Dataset containing this repo's `src/admorphiq/` tree
     (and `configs/`, `.wiki/` if the agent reads them). Name it e.g.
     `admorphiq-src`. Attach it to the notebook → it mounts at
     `/kaggle/input/admorphiq-src/`.
   - If using the offline LLM: create a second Dataset/Model with the **GGUF
     weights** (e.g. `qwen3-14b-q4.gguf`) + a **CUDA `llama-cpp-python`
     wheel**; attach both. Set notebook env `ADMORPHIQ_GGUF_PATH=/kaggle/input/.../model.gguf`
     and `ADMORPHIQ_LLM_BACKEND=llamacpp`.

## The notebook

Paste the cells from `notebooks/kaggle_submission.py` (each `# %%` = one cell).
It already: installs the wheels offline, puts `ARC-AGI-3-Agents` + our `src`
on `sys.path`, registers the agent, boots an OFFLINE `Arcade` over the private
games, runs the Swarm, and writes `/kaggle/working/submission.json`.

To use the strong agent instead of the v0 cheap-explore, change the registered
class in the agent cell:
```python
from admorphiq.general_agent import GeneralAgent  # efficiency-first general agent
AVAILABLE_AGENTS["admorphiq"] = GeneralAgent       # (wrap as Agent subclass if needed)
```
(`kaggle_agent.CheapExploreAgent` is the guaranteed-valid v0 floor.)

## Submit

`Save Version` → `Save & Run All (Commit)`. When the run finishes (≤9h) the
`Submit` button activates if a submission file was produced. Select it as a
Final Submission (up to 2). Then **make the notebook public** before the
milestone deadline for prize eligibility.

## Sanity before submitting
- Local smoke: `uv run python scripts/smoke_kaggle_agent.py` (agent acts, no crash).
- Local score: `uv run python scripts/score_efficiency.py --agent general --games 6`
  — the real efficiency metric on sample games (human baselines from
  `EnvironmentInfo.baseline_actions`).

## Reality check (2026-06-25 leaderboard)
Random = 0.18, stochastic-sample = 0.25, top (Dries Smit/Tufa) = 1.21. Metric
squares efficiency, so any submission that *completes* a few level-1s near
human action counts already beats the random floor. Get a real number on the
board first, then climb.
