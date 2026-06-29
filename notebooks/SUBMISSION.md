# ARC-AGI-3 — How to submit (Milestone 1)

Our agent runs **fully offline** in a Kaggle notebook and writes
`/kaggle/working/submission.json` itself. Submission = run the notebook to
completion. Deadline: **June 30 2026 23:59 UTC** (= Jul 1 08:59 KST); the
notebook must be **public / open-source** by then to qualify for the
milestone prize.

## Mechanism (verified locally 2026-06-29)

The notebook uses a **direct OFFLINE loop**, NOT `agents.swarm.Swarm` +
`Arcade.listen_and_serve`:

```
arc = Arcade(operation_mode=OFFLINE, environments_dir=.../environment_files)
card_id = arc.open_scorecard(tags=["admorphiq","bc"])
for game_id in [e.game_id for e in arc.get_environments()]:
    env   = arc.make(game_id, scorecard_id=card_id)
    agent = KaggleBCAgent(card_id, game_id, "admorphiq", "", record=False, arc_env=env)
    agent.main()                       # official run-loop, steps env, updates scorecard
scorecard = arc.close_scorecard(card_id)
write scorecard.model_dump_json() -> /kaggle/working/submission.json
```

**Why not Swarm / listen_and_serve.** `Swarm.__init__` builds its OWN
`Arcade()` in NORMAL mode, which fetches an anonymous API key over HTTP and
runs every game through that internal Arcade — never through a locally-served
OFFLINE one. With internet disabled that errors out, and the
`on_scorecard_close` callback that was supposed to write the submission never
fires. The direct loop above has no Flask server, no second Arcade, no
network — it is the offline-correct mechanism.

- **OperationMode**: `OFFLINE`. The notebook also sets
  `os.environ["OPERATION_MODE"]="offline"` because the `Arcade` constructor
  lets an `OPERATION_MODE=competition` env var override the constructor arg,
  and competition mode needs the network (impossible with internet disabled).
- **submission.json** is the closed `EnvironmentScorecard` JSON — per-game
  `runs[]` with `level_scores` (the squared human/agent efficiency metric),
  `level_actions`, `level_baseline_actions`, plus `score` / `total_*` rollups.

Local proof:
```
uv run python scripts/verify_offline_submission.py --games ar25 dc22 --max-actions 12
```
produces `scripts/offline_submission_sample.json` (a valid scorecard) with no
internet. The notebook's `run_offline_submission()` uses the same loop.

## One-time setup (Kaggle)

1. **Create the competition notebook**: ARC-AGI-3 competition page → Code →
   New Notebook. Enable GPU (`g4-standard-48`, RTX PRO 6000 96GB).
2. **Settings → Internet: OFF** (required by the competition; the path above
   is built for this).
3. **Attach competition inputs** (provided on the Data tab), mounting at:
   - `/kaggle/input/ARC-AGI-3-Agents`   — official `agents` framework
   - `/kaggle/input/arc_agi_3_wheels`   — offline wheels (`arc_agi`, `arcengine`, deps)
   - `/kaggle/input/environment_files`  — the games to play
4. **Ship our code + weights as Kaggle Datasets** (no pip at runtime):

   | Upload | Source path (repo) | Size | Mount on Kaggle | Notebook expects |
   |--------|--------------------|------|-----------------|------------------|
   | `admorphiq-src` | `src/admorphiq/` | 1.9M | `/kaggle/input/admorphiq/src/admorphiq` | dir containing `admorphiq/` added to `sys.path` |
   | `admorphiq-bc-weights` | `models/bc_policy.pt` | 131M | `/kaggle/input/.../bc_policy.pt` | path via `BC_WEIGHTS` env, else `models/bc_policy.pt` |

   The notebook's `_ensure_admorphiq_importable()` already probes
   `/kaggle/input/admorphiq/src` and `os.getcwd()/src`. If you mount the src
   dataset elsewhere, either add that path or set it so `admorphiq` imports.
   Set `BC_WEIGHTS=/kaggle/input/<your-weights-dataset>/bc_policy.pt` in the
   notebook env (Add-ons → Secrets/Variables, or an `os.environ[...]` line in
   the first cell) so the agent finds the weights at the mounted path.

## The notebook

Paste the cells from `notebooks/kaggle_submission.py` (each `# %%` = one cell).
It: installs the wheels offline, puts `ARC-AGI-3-Agents` + our `src` on
`sys.path`, registers `KaggleBCAgent` as `AVAILABLE_AGENTS["admorphiq"]`, then
runs the OFFLINE direct loop and writes `/kaggle/working/submission.json`.

### Dependencies (offline) — confirmed sufficient

The agent's import chain needs only: **torch, numpy** (our code) +
**arcengine, arc_agi** (wheels) + the **`agents` framework** (mounted). Our
`admorphiq._agents_shim` loads just `agents.agent.Agent` via a namespace
package, bypassing the heavy `agents/__init__.py` template imports
(langgraph / smolagents / vision) — so those are NOT required offline.

## Submit

`Save Version` → `Save & Run All (Commit)`. When the run finishes (≤9h) the
`Submit` button activates once `/kaggle/working/submission.json` exists.
Select it as a Final Submission (up to 2). Then **make the notebook public**
before the milestone deadline for prize eligibility.

## Sanity before submitting
- **Offline submission path** (the critical one):
  `uv run python scripts/verify_offline_submission.py --games ar25 dc22 --max-actions 12`
  — confirms a valid scorecard JSON is produced with no internet.
- Local smoke (agent acts, no crash): `uv run python scripts/smoke_kaggle_agent.py`.

## Reality check (2026-06-25 leaderboard)
Random = 0.18, stochastic-sample = 0.25, top (Dries Smit/Tufa) = 1.21. The
metric squares efficiency, so any submission that *completes* a few level-1s
near human action counts already beats the random floor. Get a real number on
the board first, then climb.
