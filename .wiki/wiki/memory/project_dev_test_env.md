---
name: project_dev_test_env
description: "The Kaggle-matched GCP dev/test environment + how to run tests (score_efficiency, orchestrator_probe), model candidates, and the local-Mac limits — for cross-session continuity"
metadata: 
  node_type: memory
  type: project
  originSessionId: 3f835f42-61d8-4a15-811f-a74e74370d28
---

The DEV/TEST environment as of 2026-07-08 (self-improving tool-orchestrating agent, north-star
`.wiki/wiki/architecture_self_improving_agent.md`). Keep this current across sessions.

**GCP VM = Kaggle-identical dev box** (the whole harness is developed + measured here so it runs
on Kaggle verbatim; the 24GB Mac CANNOT run 30B models or parallel — crashes — Mac is for
edit/lint/tests only):
- Instance `ewm-bench`, zone `asia-east1-a`, machine `g4-standard-48` (RTX PRO 6000 Blackwell
  **96GB**), SPOT. Start: `gcloud compute instances start ewm-bench --zone=asia-east1-a`;
  STOP when idle (cost): `gcloud compute instances stop ...`. SSH: `gcloud compute ssh ewm-bench
  --zone=asia-east1-a --command='...'`. Budget so far ~$36 of GCP free credits (2-3 VMs OK).
- On VM: repo at `~/admorphiq` (uv-synced `.venv`; run tools with `~/.local/bin/uv run python`).
  25 games in `environment_files/`, transitions in `data/transitions/train/` (18 games; ft09/etc
  NOT collected yet). ollama 0.31.1 with **gemma4:31b-it-q8_0** (measured best, R50b 0.133) +
  **gpt-oss:120b** already pulled (disk persists across stop).
- Transfer code to VM: `tar czf` the essentials (src, scripts/*.py, environment_files, pyproject,
  uv.lock, .wiki, tests; EXCLUDE .git/scripts/rounds/models/data/transitions bloat) → `gcloud
  compute scp` → untar. Transitions data ships separately (not in git).

**Test methods (run on the VM):**
- Full-game score: `uv run python scripts/score_efficiency.py --agent graph_frontier --titles
  <game> --max-actions N --out out.json` (offline, verified working on VM). Metric = fraction;
  ×100 = leaderboard %. Anchors: us ~0.20%, M1 winner (Tufa Duck) 1.21%, live top ~1.56%.
- Orchestrator/tool-selection probe (runtime-brain validation): `uv run python
  scripts/orchestrator_probe.py --model gemma4:31b-it-q8_0 --games ...` → for each game it derives
  a generic signature (avg_changed_cells, click_action_fraction, NONDETERMINISM, palette) + the
  tool menu and asks the model to pick the FIRST tool. 2026-07-08 result: gemma4-31b correctly
  picked de-aliasing on high-nondeterminism games (dc22 0.53, ka59 0.46) — KNOWLEDGE→BRAIN link
  works; wrong picks (ar25/sb26→paint) trace to missing tool_selector discriminators (fix the
  wiki, not the model).
- EWM synthesis bench: `scripts/llm_worldmodel_bench.py` (+ `rescore.py`). ⛔ never run ≥18GB
  Ollama models on the 24GB Mac (WindowServer crash); ollama nohup logs need `flush`/`-u`.

**Model = measured choice, not fixed**: candidates gemma4-31b-q8 (leads) / gpt-oss-120b /
Qwen3.6-27B (Tufa's, code-agent-proven) — re-bench on the harness. See [[project_online_rl_baseline]],
[[project_kaggle_eval_and_metric]].
