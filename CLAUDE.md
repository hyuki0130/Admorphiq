# CLAUDE.md — Admorphiq

## Project Overview

**Admorphiq** (Adaptive Morphing Intelligence) is an AI agent for the [ARC Prize 2026 — ARC-AGI-3](https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-3) competition.

ARC-AGI-3 is the first **interactive reasoning benchmark** — agents must explore unfamiliar game environments, discover rules through trial and error, and adapt in real-time. Unlike static puzzles, this requires genuine fluid intelligence: exploration, hypothesis generation, planning, and learning from sparse feedback.

### Core Philosophy (François Chollet)

> "Intelligence = efficiency of skill acquisition in novel situations"

- Not memorization, not pattern matching on training data
- Few-shot rule discovery from interaction
- Human Core Knowledge as prior: object permanence, numeracy, geometry

## Competition Details

### Prize Structure ($850,000 for ARC-AGI-3 track)

| Category | Prize | Timing |
|----------|-------|--------|
| **Milestone 1** (Jun 30) | 1st $25K, 2nd $7.5K, 3rd $5K | Mid-competition (must open-source by date) |
| **Milestone 2** (Sep 30) | 1st $25K, 2nd $7.5K, 3rd $5K | Mid-competition (must open-source by date) |
| **Final Leaderboard** | 1st $40K, 2nd $15K, 3rd $10K, 4th $5K, 5th $5K | After Dec 4 announcement |
| **Bonus (100% accuracy)** | 1st $350K, 2nd $175K, 3rd $70K, 4th $70K, 5th $35K | After Dec 4 announcement |

### Timeline

- **2026-03-25**: Competition started
- **2026-06-30**: Milestone #1
- **2026-09-30**: Milestone #2
- **2026-10-26**: Entry deadline + team merger deadline
- **2026-11-02**: Final submission deadline
- **2026-12-04**: Winners announcement

### Constraints (Kaggle Environment)

> **✅ Hardware CONFIRMED 2026-06-25 from the official Kaggle overview** (not
> a guess). Overview "Upgraded accelerators": *"Kaggle uses machine type
> `g4-standard-48`"* + *"added RTX 6000 machines"* → **1× NVIDIA RTX PRO
> 6000 Blackwell, 96GB VRAM**, 48 vCPU, 180GB RAM. Code Requirements: *"GPU
> Notebook ≤ **9 hours** run-time"*, *"Internet access disabled"*,
> *"pre-trained models allowed"*. This **invalidates the old "T4 16GB / 6h"
> assumption.** The VRAM ceiling is gone (96GB). Pre-trained model weights
> mount as a **read-only Kaggle Model/Dataset** — NOT counted against the
> notebook's working disk — so model SIZE is not meaningfully constrained
> (tens of GB fine). Binding constraints are now: **9h wall-clock across all
> eval games** + the offline/no-internet rule. Model selection reopened (R17).

| Constraint | Limit (CONFIRMED 2026-06-25, official overview) |
|-----------|-------|
| GPU | `g4-standard-48`: 1× RTX PRO 6000 Blackwell, **96GB VRAM** |
| Host | 48 vCPU, 180GB RAM |
| Runtime | **≤ 9 hours** (CPU or GPU notebook) |
| Internet | **Disabled** (no external API calls — RTX sessions enforced) |
| External data | Public data + **pre-trained models** OK (read-only mount) |
| Submission | **Notebook only**; file auto-generated once the agent acts on any game |
| Metric | per-game 0–100% (human action-count relative), **averaged over all games** |
| Open source | Notebook must be public/open-source by the milestone date to win |

*(Superseded: "≤6h, T4 16GB VRAM". Sections below — esp. [LLM Selection](#llm-selection-phase-8-hypothesis-engine) — still cite the old T4/VRAM math; stale, tracked for R17.)*

**Milestones (optional):** M1 = **June 30 2026 23:59 UTC** (=7/1 08:59 KST), M2 = Sep 30. Prizes per milestone: 1st $25K / 2nd $7.5K / 3rd $5K. Must open-source the notebook by the deadline. As of 2026-06-25: **1,424 teams / 11,222 submissions** already on the board — we have **0 submissions**.

**Key implication**: No Claude/GPT API calls — offline open-weight LLM only, loaded from a mounted Kaggle Model (no `ollama serve`, no internet). With 96GB VRAM + read-only weight mount, model choice is bounded by 9h-across-all-games throughput, not VRAM/disk. The submission is a **notebook running an agent against the offline ARC game interface** (NOT the networked `arc_agi` API we use locally). Claude Code is dev-time only.

## Architecture Design

```
┌─────────────────────────────────────────┐
│         1. Perception Layer             │
│  64x64 frame → CNN encoder → state repr │
└──────────────┬──────────────────────────┘
               ▼
┌─────────────────────────────────────────┐
│         2. World Model                  │
│  "If I take action X, state becomes Y"  │
│  Learn transition dynamics from buffer  │
└──────────────┬──────────────────────────┘
               ▼
┌─────────────────────────────────────────┐
│         3. Hypothesis Engine            │
│  Lightweight LLM or rule inference      │
│  "The goal of this game is probably X"  │
└──────────────┬──────────────────────────┘
               ▼
┌─────────────────────────────────────────┐
│         4. Action Planner               │
│  Hypothesis-driven planning → execute   │
│  Explore vs exploit balance (UCB etc.)  │
│  Feedback loop: observe → revise        │
└─────────────────────────────────────────┘
```

### Layer Details

**Perception Layer** (implemented)
- Input: 16-channel one-hot encoded 64x64 frames
- CNN backbone (5-layer, 16→32→64→128→256 channels, 34M params)
- Dual head: action logits (5 actions) + coordinate logits (4096 = 64x64)
- Total output: 4101 logits, trained with BCEWithLogitsLoss

**World Model** (implemented, 1.6M params)
- StateEncoder: CNN-based state embedding from 16-channel frames
- ActionEmbedding: 8 action types + coordinate encoding
- TransitionPredictor: predicts residual delta (next_state = current + delta)
- ChangePredictor: binary classifier for state-change likelihood
- Experience buffer (~200K unique state-action pairs, MD5 dedup)
- Agent scoring: combined = alpha * perception + (1-alpha) * world_model (alpha=0.5)

**Hypothesis Engine** (planned — Phase 8 integration, **model undecided, pending benchmark**)

Role is **NOT "one-shot router"**. The LLM is a runtime reasoning
agent that participates in the whole game-completion loop:

1. **Classify & route** — pick the best primary strategy + fallback
   stack from the observable signatures.
2. **Observe runtime failures** — when a strategy returns levels=0
   or regresses, read the failure context (what was probed, what
   cluster counts emerged, what post-click homogeneity looked like).
3. **Self-heal** — propose an alternate plan from the wiki's
   failure-mode playbooks (`.wiki/wiki/debug/*`) without waiting for
   the next dev-time round. The plan may be a different strategy
   name, a parameter adjustment, or a new observation stride.
4. **Decide game-complete** — track per-level progress and reason
   "are we stuck because the plan is wrong, or because the game
   genuinely requires more budget?" Budget-bail vs plan-swap is an
   LLM call, not a hardcoded threshold.

Wiki pages must therefore be written as **runtime reasoning fuel**:
observable signatures + falsification criteria + "if you see X, try
Y" next-step rules — not just historical narrative. See Wiki Doctrine.

Candidates to evaluate (all Apache 2.0 or equivalent, Kaggle-compatible):
- **Qwen 3 8B** (dense, ~5GB 4bit) — strong 8B-class reasoning, best LoRA ecosystem (favored if TTT needed)
- **Gemma 4 26B MoE** (3.8B active / 26B total, ~13GB 4bit) — 31B-tier reasoning (AIME 89.2% / GPQA 84.3%), fast MoE inference (favored for Wiki zero-shot)
- **Gemma 4 E4B** (4.5B effective, ~3GB 4bit) — low-VRAM fallback, long 128K context
- **Llama 3.1 8B** — weaker reasoning vs Qwen 3 / Gemma 4; reference-only, not a candidate

Selection rule: choose empirically after Phase 8 Step 3 benchmark. Each candidate tested on identical Wiki-pattern zero-shot task (game classification + strategy selection) against the 25-game regression. See [LLM Selection](#llm-selection-phase-8-hypothesis-engine) for full matrix.

Option B: Program synthesis — generate candidate rule programs (DSL primitives)
Option C: Neurosymbolic — neural intuition + symbolic rule extraction

**Action Planner** (implemented in AdmorphiqAgent + EnsembleAgent)
- Hierarchical sampling: action type first, then coordinates if ACTION6
- Entropy regularization to encourage exploration
- Change prediction bias: prefer actions likely to cause state changes
- Level transition detection with automatic buffer/model reset
- Ensemble dispatch: 60+ generic strategies + game-specific analytical solvers

## Game Environment

### Agent Interface
- Two required methods: `is_done()` and `choose_action(frame_data)`
- `FrameData` contains: `frame[N][64][64]` (variable layers, int8 color index per cell), `available_actions`, `state`, `levels_completed`
- **Frame structure** (corrected): NOT fixed 16ch one-hot. Games have variable layer count (1~N), each cell is an int8 color index. Our adapter converts to 16ch one-hot for the CNN.
- `GameAction`: RESET=0, ACTION1-5 (simple, no coordinates), ACTION6 (complex, requires x/y), ACTION7 (simple, cancel/undo)
- `MAX_ACTIONS = 80` per game (ensemble strategies use larger budgets internally)

### Scoring
- Per-game: 0~100% (100% = matching human-level performance)
- Final: average across all games
- Capped at 100% even if agent uses fewer moves than humans

## Project Structure

```
src/admorphiq/
├── agent.py            # AdmorphiqAgent (CNN-based, is_done + choose_action)
├── agent_graph.py      # GraphAgent (state graph + BFS exploration)
├── agent_diff.py       # DiffAgent (frame diff + state graph engine)
├── agent_ensemble.py   # EnsembleAgent (60+ strategies + analytical solvers)
├── adapter.py          # AdmorphiqAdapter (official Agent ↔ internal bridge)
├── types.py            # GameState, ActionType, GameAction, FrameData
├── _types_internal.py  # Internal type definitions
├── perception/
│   ├── cnn.py          # CNN backbone (5-layer, 34M params)
│   ├── model.py        # PerceptionModel (dual head: action + coord)
│   └── frame_analyzer.py  # FrameAnalyzer (frame diff detection)
├── world_model/
│   ├── encoder.py      # StateEncoder (CNN-based state embedding)
│   ├── transition.py   # TransitionPredictor + ChangePredictor
│   └── model.py        # WorldModel (1.6M params, residual delta)
├── hypothesis/         # Rule inference engine (Phase 8 LLM integration)
├── planner/
│   ├── explorer.py     # SystematicExplorer (untried action bonus)
│   ├── graph_explorer.py  # GraphExplorer (BFS state graph traversal)
│   ├── state_graph.py  # StateGraph (state transition graph)
│   ├── memory.py       # GameMemory (success sequence replay)
│   ├── bfs_solver.py   # Generic BFS over state space
│   ├── toggle_solver.py    # Click-toggle solver
│   └── sequence_solver.py  # Action sequence search
└── utils/
    ├── buffer.py       # ExperienceBuffer (hash dedup, 200K cap, next_frame)
    └── logger.py       # Structured run logger
tests/                  # Test suite
configs/                # Configuration files
notebooks/              # Experiment notebooks
scripts/
├── run_local.py        # Local game runner (arcengine integration)
├── run_25games.py      # 25-game regression battery
├── run_ensemble.py     # Ensemble agent driver
├── classify_games.py   # Game-type classifier
└── play.py             # Interactive game play script
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.12 |
| Framework | arcengine 0.9.3 + arc-agi 0.9.6 |
| Package manager | uv |
| Deep learning | PyTorch |
| LLM (offline, planned) | Candidates under benchmark: Qwen 3 8B, Gemma 4 26B MoE 4bit, Gemma 4 E4B 4bit (decided after Phase 8 Step 3 eval, not pre-committed) |
| Monitoring | TensorBoard, AgentOps |
| Testing | pytest |
| Linting | ruff |

## Development Roadmap

### Phase 1: Environment Understanding ✅ Complete
- ~~Install arc-agi SDK, set up local development~~
- ~~Play games manually to understand structure~~
- ~~Study official framework (arcprize/ARC-AGI-3-Agents)~~
- ~~Analyze reference solution (DriesSmit/ARC3-solution)~~

### Phase 2: Baseline Agent ✅ Complete
- ~~CNN perception backbone (16→32→64→128→256, dual head, 34M params)~~
- ~~Experience buffer with MD5 hash deduplication (200K capacity)~~
- ~~AdmorphiqAgent with hierarchical sampling + entropy regularization~~
- ~~Type abstractions: GameState, ActionType, GameAction, FrameData~~
- ~~41 tests passing (types 8, perception 11, buffer 10, agent 12)~~

### Phase 2.5: SDK Integration + Live Testing ✅ Complete
- ~~arcengine 0.9.3 + arc-agi 0.9.6 installation and integration~~
- ~~AdmorphiqAdapter: official Agent ↔ internal Agent bridge~~
- ~~Frame conversion: multi-layer (1~N layers, int8 color index) → 16ch one-hot~~
- ~~scripts/run_local.py: local game runner~~
- ~~Live tested on 3 games (DC22/1L, LF52/2L, BP35/2L) — 0 levels cleared~~

### Phase 3: World Model ✅ Complete
- ~~StateEncoder (CNN) + ActionEmbedding (8 types + coordinates) + TransitionPredictor (residual delta)~~
- ~~ChangePredictor for smarter exploration (1.6M params total)~~
- ~~Agent integration: combined = alpha * perception + (1-alpha) * world_model~~
- ~~ExperienceBuffer extended with next_frame + sample_with_next()~~
- ~~69 tests passing (41 existing + 28 new)~~

### Phase 3.5: Exploration Strategy Improvement — Failed
- Level completion rewards (frame_changed=0.3, level_up=1.0, game_over=-0.5)
- SystematicExplorer (untried action bonus, forced traversal)
- GameMemory (success sequence replay)
- Hotfixes: explorer diversity, train_frequency=20, MAX_ACTIONS=500
- **Result**: 0 levels cleared on all 3 games despite 500 actions each
- **Conclusion**: Change prediction approach has fundamental architectural limitations

### Phase 4: Multi-Strategy Exploration ✅ Complete
- ~~4A: Graph-based exploration — state graph + BFS (agent_graph.py, graph_explorer.py)~~
- ~~4B: StochasticGoose improvements — binary reward, coord /4096 scaling, train_freq=5, perception only~~
- ~~4C: Frame diff engine — FrameAnalyzer + StateGraph + DiffAgent (agent_diff.py)~~
- ~~Game classification: 25 games auto-classified (movement 7, click 6, hybrid 6, transform 2, unknown 4)~~
- ~~Interactive play script (play.py)~~
- **Best result**: Frame diff solver cleared 4 games/4 levels (25 games in 25s)
- **Key insight**: Graph/Diff/CNN each clear different games — ensemble potential

### Phase 5: Maximize Game Clears ✅ Complete
- Cleared 16/25 games using all 4 approaches in parallel
- Game-specific analytical solvers introduced (lights-out, paint, maze BFS, etc.)
- Game internals access used for upper-bound performance measurement

### Phase 6: Generalization Refactoring ✅ Complete
- Removed ALL game-ID hardcoding from dispatch — 60+ generic strategies
- All triggers feature-based (available_actions + frame analysis)
- No game IDs in strategy names or conditions
- Analytical solvers retained internal access (Phase 8 will clean up)

### Phase 7: Multi-Level + Score Optimization ✅ Closed (post-rotation reality check, 2026-04-21)
- **Round 1 (2026-04-20, since-superseded baseline)**: 31/40 envs, 79/289 levels (27.34%).
- **2026-04-21 re-run, SAME code, SAME runner, 50K budget**: **28/40 envs, 54/290 levels (18.62%)**.
  The ARC Prize API rotated every env hash overnight; `su15-4c352900 → su15-1944f8ab` etc.
  Every brittle attr-reader (`strat_su15_vacuum`, `strat_re86_analytical`, `strat_ka59_sokoban`,
  `strat_s5i5_slider`, `zig3_A2A4`) silently dropped to 0. See
  `.wiki/wiki/lessons/api_hash_rotation_20260421.md`.
- **Lesson written in blood**: "v1 score" is not a stable metric. The previous 36.81% figure
  was a single-day snapshot tied to the 2026-04-20 hash set. It cannot be chased.
- **LF52/SK48 budget fix verified**: LF52 1/10 via `adaptive_c2`, SK48 1/8 via `sk48_snake`
  (both recovered from 0). Root cause was `total_budget=20000` in the runner starving late
  strategies; fix raised it to 50000 to match the class default.
- **All further Phase 7 work cancelled** — no more brittle solvers, no more hash-coupled
  hardcoding. Phase 8 (frame-only + LLM) is the only sustainable path.

### Phase 8: Generalization + Kaggle Submission 🔄 ACTIVE (Karpathy LLM-Wiki pattern)

> **🚨 M1 SPRINT CORRECTION (2026-06-25) — read `docs/sprint_m1_architecture_20260625.md` FIRST.**
> Verified from the live Kaggle pages; corrects load-bearing errors that
> shaped rounds R1–R17:
> - **Eval = 110 PRIVATE unseen games** (NOT the 25 preview). The 25 in
>   `environment_files/` are dev-only; the leaderboard is NOT the 25-game score.
> - **Metric = efficiency SQUARED**: per-level `min(human/agent_actions, 1)²`,
>   level-index-weighted per game, mean over games. Brute-force completion
>   (BFS clearing in hundreds of actions) scores ≈ 0. Real leaderboard:
>   random = 0.18, stochastic-sample = 0.25, top (Dries Smit/Tufa) = 1.21.
> - **Hardware**: g4-standard-48 / RTX PRO 6000 **96GB** / **9h** (see Constraints).
> - **Design pivot**: drop "LLM routes among brute-force strategies"; adopt a
>   single **efficiency-first general agent** — cheap discovery → online
>   world model → *efficient* planning; the offline LLM hypothesizes the
>   goal at discovery time (a few calls/game), NOT per-action routing. The
>   R1–R16 wiki-routing machinery is de-prioritized, not the spine.
> - We have **0 submissions**. A valid offline notebook on the board (beating
>   the 0.25 sample) + open-sourcing by June 30 23:59 UTC is **P0**.

> **📐 EXACT SCORING — RHAE (from https://docs.arcprize.org/methodology, verified 2026-06-29).**
> "Relative Human Action Efficiency". Three levels of aggregation:
> 1. **Per-level**: `level_score = (human_baseline_actions / ai_actions)²` — SQUARED.
>    Capped at **1.15** (an agent that beats the human action count can exceed 1.0,
>    up to 1.15). human=10/ai=10 → 1.0; ai=20 → 0.25; ai=100 → 0.01.
>    Human baseline = **upper-median** first-time human per level (not average).
>    An "action" = an env-state-changing command; internal reasoning/retries don't count.
> 2. **Per-game**: **weighted average** of per-level scores, weight = 1-indexed level
>    number (deep levels dominate). Denominator = sum of ALL levels' weights, so the
>    max game score is capped by completion: clearing 4 of 5 levels caps the game at
>    `(1+2+3+4)/(1+2+3+4+5)=66.7%`. **100% requires clearing the final level.**
> 3. **Total**: arithmetic **mean of per-game scores**. Range 0–100%, can exceed 100%
>    via the 1.15 per-level cap (that is how Tufa shows **1.21**). random≈0.18,
>    stochastic-sample≈0.25 on this same scale.
> - **Public vs Private leaderboard**: BOTH are the hidden test set, split ~50/50.
>   Public LB = ~50% of test data (live); Private = the other ~50% (final standings).
>   "Entries" on the LB = a team's submission count. Daily limit = **1 submission/day**
>   (resets 00:00 UTC); up to **2 Final Submissions** selected at the end (best auto-picked).
> - **Submission**: code competition. The notebook runs server-side; a submission file
>   for all games is auto-created once the agent acts on any game. `kaggle kernels push`
>   runs a notebook WITHOUT consuming a submission (free server-side validation);
>   `kaggle competitions submit -k <kernel>` consumes the daily slot.
> - **Our local harness `scripts/score_efficiency.py` is FAITHFUL to this** — same
>   squaring, same level-index weighted average, same all-levels denominator. (It caps
>   per-level at 1.0 vs the official 1.15, negligible because our agents never beat the
>   human action count.) So its `total_score` fraction is directly comparable to the
>   leaderboard scale, and all round measurements are trustworthy dev proxies.
> - **What the formula rewards (the levers)**: (a) clear MORE games (coverage), and
>   especially (b) clear DEEPER levels EFFICIENTLY — the level-index weight × the square
>   means deep, near-human-efficient clears dominate the score. Shallow/inefficient
>   clears barely move it. This is why depth + efficiency + coverage are the spine,
>   not raw completion. Memory: [[project_kaggle_eval_and_metric]].

> **🧭 DIRECTION CORRECTION (2026-06-29) — BC is the M1 ship asset and a
> warm-start, NOT the destination. The general path is world-model + online
> (test-time) learning + RL.** Read this before extending the BC track.
>
> **What the BC sprint (R14–R26) produced** — a behavior-cloned CNN policy
> (`PerceptionModel`, frame→4101 logits) trained on gold traces for 24 of the
> 25 public games, plus Test-Time Training + a cycle-breaker at inference
> (`src/admorphiq/bc_agent.py`, `kaggle_bc_agent.py`). Deployed model
> `models/bc_policy.pt` = **v6** (BC retrain on 24-game gold) = **3.41%** on the
> 25-game proxy (40 envs, real squared-efficiency metric), **15/25** games
> clearing ≥1 level (v2 was 2.20% / 10). This is the **M1 submission asset** —
> ship it (P0), keep it.
>
> **The structural blind spot — MEASURED 2026-06-29: transfer ≈ 0%.** Eval is
> **110 PRIVATE unseen games**, but BC learned from gold on the **25 PUBLIC**
> ones. The **held-out transfer test** (`scripts/_transfer_test.sh`: train BC on
> 18 games, score the 7 it never saw) returned a **0.00% transfer ratio** — the
> holdout model cleared **0 of 7** unseen games (vs 0.054 mean in-sample for v6).
> Confound ruled out: the same holdout model DOES clear its own training games
> (M0R0 2/6, LP85 1/8), so this is genuine non-transfer, not undertraining.
> **Conclusion: BC-on-public-gold memorizes the training games and is a proxy
> overfit — it cannot be the spine for the private leaderboard.** (Log:
> `scripts/transfer_test.log`; memory `project_bc_transfer_ceiling`.)
>
> **The top-team recipe, read correctly** — StochasticGoose (Dries Smit / Tufa,
> top ≈ 1.21) is CNN+RL, but the load-bearing half is **online RL that adapts
> per game at TEST time** (retrains between levels), not BC on a public training
> set. We copied the transferable-weak half. The learning that matters happens
> *inside each unseen game*, within the 9h / 110-game budget.
>
> **RL status is NOT "rejected"** — one fine-tune run (`scripts/train_rl.py`,
> REINFORCE from the BC init, lr 1e-4, KL 0.1, +0.02/frame-change shaping,
> 50k steps) scored 1.54% (< BC 3.41%), so auto-promote correctly kept v6 for
> *deployment*. That is one config, not a verdict on the method. Likely fixes:
> lower LR, stronger KL/BC anchor, drop the frame-change shaping (it rewards
> wiggling over solving), longer training, and **keep-best-by-eval instead of
> keep-last** (intermediate checkpoints scored via `scripts/_rl_curve.sh` show
> the trajectory). RL-from-BC is hyperparameter-sensitive; redesign, don't bury.
>
> **The general path (R27+ thrust, toward M2 / final / the $350K bonus)** — an
> object-centric agent that does its learning AT TEST TIME on each unseen game:
> 1. **Perception → objects** — segment the frame into entities/color regions
>    (game-agnostic; `FrameAnalyzer` exists). No game-id / sprite-tag reads.
> 2. **Online world model** — from the agent's own probes, learn "action X
>    changes object Y" *per game* in the first tens of actions (`world_model/`
>    exists). This is what transfers, because it is rebuilt fresh per game.
> 3. **Goal inference** — detect the level-complete condition via the model +
>    a small reasoning step (heuristic, or the offline LLM at discovery, a few
>    calls/game).
> 4. **Search-based planning** — BFS/MCTS in the learned model toward the goal
>    → short action sequences (the squared-efficiency metric rewards this).
> 5. **RL on top** — online policy improvement per game; **BC = warm-start
>    prior** that biases exploration toward "actions that do something", not the
>    final policy.
>
> **Two-layer plan**: (M1, now) ship BC v6 — valid offline notebook beating the
> 0.25 floor, open-sourced by the deadline. (R27+) build the world-model +
> online-learning + RL general agent as the real lever for the private 110.
> Both tracks coexist: BC v6 is the safety net; the general agent is the climb.
> Doc: `docs/sprint_m1_architecture_20260625.md` (post-M1 direction section).

**Architecture decision (2026-04-20)**: Adopt [Karpathy's LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) — markdown knowledge base maintained by LLM at dev-time, read by inference LLM at Kaggle-time. No vector DB (incompatible with Kaggle internet constraint).

**Reference analysis**: see [`docs/llm_wiki_karpathy_analysis_ko.md`](docs/llm_wiki_karpathy_analysis_ko.md) for the full Karpathy pattern breakdown and the Admorphiq gap table (log.md missing, lint pass missing, ingest-workflow not ritualised, query→page refiling not systematic). R23+ roadmap below absorbs the gaps as dedicated sub-rounds.

### LLM as Game-Completion Driver — Claude Code as Helper (not as auto-coder)

**Framing correction (2026-04-23, two passes)**: The offline LLM
(Qwen 3 family) is the **primary agent** — it does game
comprehension, picks the plan fn, runs it, observes failure, and
**decides how to fix the code or swap strategies**. Dev-time
Claude Code is the LLM's **implementation helper**: receive the
LLM's diagnosis + fix proposal, write the code change, commit,
re-bench. This is qualitatively different from how rounds R16-R22
were run (Claude Code read the probe trace and unilaterally
rewrote plan fns without routing the failure through the LLM).

**The actual per-env runtime loop (Kaggle-time)** is:

1. **Discovery** — `DiscoveryReport` from observation_phase.
2. **Routing** — LLM picks primary + fallback strategies from the
   whitelist based on observable signatures + wiki retrieval.
3. **Plan execution** — the chosen plan fn runs for its budget cap.
4. **Failure observation** — if levels=0 or regression, the LLM
   reads the post-plan envelope: stencil density, cluster counts,
   probe diffs, which cells were tried, what happened on each.
5. **Self-decision**: one of
   (a) **Swap strategy** — pick a different whitelist name.
   (b) **Retune parameters** — "same plan with stride=2 instead
       of stride=8", "widen vacuum radius R", "pick cells from the
       18 we didn't try".
   (c) **Propose code fix** — "the measurement is wrong because
       it trusts the first observation pass; the wiki says to
       re-observe after the sweep invalidates top-10 choices.
       Edit `_plan_lights_out` to re-rank after sweep."
6. **Loop** — execute the chosen action, observe again.

When the LLM reaches (c), the Kaggle-time run simply can't act on
it (the code is frozen post-submission). But during **dev-time**
iteration, (c) proposals MUST route through Claude Code:

- Qwen writes a structured `CodeFixProposal {target, reason,
  suggested_patch}` into the run trace.
- Claude Code at the next dev round reads the proposals, discusses
  with the user if needed, and implements the agreed ones.
- Re-bench. Qwen sees whether its proposed fix helped.

**This inverts the control**: Claude Code is no longer the
designer of plan fns — Claude Code is the scribe who turns Qwen's
runtime diagnoses into committable code. R16-R22 skipped this
because R11's `LLM_WHITELIST_ALLOWLIST = {"adaptive_bfs_solver"}`
zeroed out Qwen's routing voice, so Claude Code substituted its
own judgement. That substitution is a procedural bug, not a
performance win.

**Implication for R11's single-item allowlist**: it was a dev-time
emergency patch to stop Qwen anchor-looping on `bfs_state_space /
click_rare`. It is NOT the target state. The target is: Qwen sees
all ~14 frame-only strategies + reads the wiki's failure-mode
playbooks + reasons runtime + proposes code fixes when no
existing plan fits.

**Implication for the wiki**: each page must expose the plan fn's
INTERNAL algorithm (not just API) so Qwen can reason "the stencil
measurement uses stride-8 which drops button cells; try stride-4
or a different cell-selection heuristic". Runtime-consumable
signature fields per wiki page:

- Observable signature to detect "this plan is the right fit"
- Falsification signature to detect "this plan has failed, swap now"
- Internal-algorithm hooks the LLM can suggest tuning
- Short "next-best" pointer to the alternative plan if failure

### Wiki Doctrine (non-negotiable)

The wiki is **not a state dump**. It exists to let an offline LLM reason about a new game by retrieving:

1. **`concepts/`** — cross-game domain entities (merge mechanic, pushable block, version hash, frame hashing, ...)
2. **`lessons/`** — accumulated engineering wisdom from past incidents (v2 obfuscation, silent regression, brittle tells, ...)
3. **`debug/`** — failure-mode playbooks keyed on observable symptoms (attribute error, regression bisect, ...)
4. **`reasoning/`** — explicit observation → hypothesis → action chains (discovery phase, frame-to-strategy, hypothesis check)
5. **`games/` + `game_types/` + `strategies/`** — entity pages that link into the above

Every page answers: **What is this? How did we arrive at this claim (provenance)? What related pages should a reader consult? What would falsify this claim?**

Describe the **journey, not just the state**: "initially we thought X, observed Y, changed to Z". A page that records only the current snapshot is half-done.

**Cross-link aggressively.** Each new claim should cite ≥1 concept page, ≥1 lesson page, and ≥1 peer entity page when applicable.

See `.wiki/schema.md` for the write conventions and `memory/feedback_wiki_doctrine.md` for the full doctrine.

**Directory layout**:
```
.wiki/
├── raw/                       # immutable sources (traces, logs, commits)
│   ├── traces/                # {game}.jsonl from regression runs
│   ├── regressions/           # v2_failures_20260420.md etc.
│   └── commits.md             # curated git-log narrative
├── wiki/                      # LLM-compiled markdown, hand-maintained
│   ├── concepts/              # cross-game domain entities (merge_mechanic, pushable_block, ...)
│   ├── lessons/               # engineering wisdom (v2_hash_obfuscation, silent_regression, ...)
│   ├── debug/                 # failure-mode playbooks (attribute_error, regression_bisect, ...)
│   ├── reasoning/             # inference chains (discovery_phase, frame_to_strategy_chain, ...)
│   ├── games/                 # per-game mechanics + solution pattern + lessons learned
│   ├── game_types/            # movement, click, programming_puzzle, merge_puzzle, sokoban, ...
│   ├── strategies/
│   │   ├── frame_only/        # generalizable (bfs_state_space, click_rare, ...)
│   │   └── brittle/           # hardcoded-internals (anti-patterns, refactor queue)
│   ├── index.md               # auto-generated backlink index
│   └── selector.md            # features → strategy dispatch rules
└── schema.md                  # write conventions
```

**Phase 8 RESTART (2026-04-21) — three-layer agent, dev/Kaggle split, R1-R6 loop**:

Binding architecture doc: **`.wiki/wiki/architecture.md`** (load-bearing — any change contradicting it updates the doc first). The pre-restart linear plan (Step 1-4 below, kept for traceability) capped at 15/40 envs / 36 levels / 45% classification on 2026-04-21 live-env run. Four structural gaps drove the restart: thin LLM input (5 features), thin LLM output (17/74 strategies exposed), no failure feedback loop, no regression gate.

**Three layers** (see `architecture.md` for full contract):
- **Cognition (LLM, Qwen 3 family)** — reasons, hypothesizes, reflects. Proposes code/wiki edits via JSON. Never writes code directly.
- **Memory (Wiki + Session)** — `.wiki/` long-term, append-only dev-time, frozen Kaggle-time. In-memory session dict at Kaggle-time tracks intra-run failures.
- **Action (Strategies)** — `agent_ensemble.py` functions. Dev-time: added/rewritten by Claude Code from LLM proposals. Kaggle-time: frozen.

**Boundary rule** (non-negotiable): Kaggle-time the only mutable layer is session state. Everything else ships as a frozen asset. Dev-time loop hardens the snapshot between submissions.

**Restart steps R1–R6**:

- [x] **R1 — Architecture doc** (`.wiki/wiki/architecture.md`, this commit). Defines 3 layers, dev/Kaggle split, dev loop, Kaggle loop, layer contracts, falsification criteria.
- [x] **R2 — Feature-rich DiscoveryReport** (2026-04-21). Added `dir_map`, `player_color`, `movable_region_count`, `click_responsive_cells`, `change_topology`, `color_histogram`, `symmetry_score`. Seven pure derive helpers (`_derive_*` + `_connected_components`) unit-tested via `tests/test_discovery_features.py` (23 tests). `Hypothesis` extended with `confidence` + `features_missing` so the LLM can flag what it needed but didn't get. Prompt template rewritten to expose all features. Full suite 126/126.
- [x] **R3 — Universal strategy dispatcher** (2026-04-21). `src/admorphiq/hypothesis/dispatcher.py` introspects `agent_ensemble` at registry-build time via `inspect.signature()` and auto-registers every `strat_*` whose non-default non-env non-budget params are keys of `CTX_KEYS`. **67/74 strategies now dispatchable** (was 17); the remaining 7 (`sustained`, `zigzag`, `extended_winner`, `continue_multilevel`, `move_click`, `navigate`, `graph_explore`) require runtime-only args (winning action ids, target colors) and stay in the internal ensemble dispatcher. WikiAgent builds ctx once per env via `build_ctx(report)` and passes it to each strategy call. 14 new unit tests in `tests/test_dispatcher.py`; full suite 140/140.
- [x] **R4 — Reflection module** (2026-04-21). Split into two tools after measured reality:
  - `scripts/analyze_trace.py` — **deterministic** pattern extraction (no LLM). Emits `scripts/trace_analysis.json` with headline stats, per-primary success rates, and flagged failure patterns (`dir_map_but_click_primary`, `wasted_budget_zero_levels`, `unknown_strategy_picks`, `llm_flagged_missing_features`, `movement_type_non_movement_primary`). 8 unit tests in `tests/test_analyze_trace.py`.
  - `scripts/reflect_wiki_agent.py` — LLM-assisted reflector (16 unit tests in `tests/test_reflection.py`). Works end-to-end mechanically but Qwen 3 8B/14B proved too weak for structured reflection on a 40-env trace (they drift into "describe the input" mode — documented as a measured falsification of the LLM-driven variant, not a regression to fix). Kept for future use with stronger models.
  - Architecture doc updated: **dev-time Cognition = Claude Code**, Qwen is Kaggle-time only. Claude Code reads `trace_analysis.json` and authors wiki/code proposals inline during a session — no intermediate LLM call required.
  - Full suite 164/164.
- [x] **R5 — Regression gate** (2026-04-21). `scripts/regression_gate.py` + `scripts/regression_baseline.json`. Compares new trace against baseline with two views: strict `by_game_id` (same title+hash, fails on drop), and informational `by_title` (best across hashes, logs but does not fail — API hash rotation is outside our control, see lessons/api_hash_rotation_20260421). Seeded from the 2026-04-21 WikiAgent trace: 10 unique cleared envs / 29 levels (aggregate per unique game_id, max over duplicate runs). CLI: `--seed`, `--promote`, `--dry-run`; exit 0/1/2 for PASS/FAIL/INPUT_ERROR. 10 unit tests in `tests/test_regression_gate.py`. Full suite 174/174.
- [x] **R6 — Live-env bench (formal)** (2026-04-21). Full 40-env comparison: Qwen 3 8B and 14B, both with R2 feature-rich DiscoveryReport + R3 universal dispatcher (67 strategies).

  | Run | Envs cleared | Total levels | Runtime | Gate verdict |
  |---|---|---|---|---|
  | Baseline (pre-R2/R3, 8B) | 10/25 unique / 15/40 raw | 29 / 36 | 990s | — |
  | R6 8B + R2+R3 | 10/25 unique / 15/40 raw | 29 / **36** | 1066s | **PASS** |
  | R6 14B + R2+R3 | 13/25 unique / 21/40 raw | 23 / 34 | 1389s | FAIL (FT09, CD82 -6 each) |
  | R6 14B + selector v2 | 11/25 unique / 18/40 raw | 21 / 31 | 1080s | FAIL (+LS20 regression) |

  **Decision**: 8B stays primary. 14B regresses on FT09/CD82 because it ignores selector.md's fallback guidance — even after selector edits, 14B produced `[click_rare, seq_search]` for FT09 (seq_search hallucinated, not in the 67-whitelist) and missed lights_out/paint_game.
  
  **Lesson captured**: `.wiki/wiki/lessons/selector_is_advisory_not_enforced_20260421.md`. Wiki edits alone don't change LLM behavior reliably at 8B-14B scale; selector rules need a Python enforcement layer (next dev-cycle task). 14B is strategically better (env diversity, whitelist discipline, calibrated confidence 0.77 vs 0.93) but can't be promoted until Python enforcement lands.

**What is frozen by R1 that wasn't before**:
- No more ad-hoc "add an 18th strategy to the whitelist" edits — R3 covers all 74 uniformly.
- No more cold-prompt bench as decision input — R6 (live-env) is the only bench that decides.
- No more one-shot classify-and-dispatch — every run feeds R4 reflection.

**Legacy linear plan (kept for traceability, superseded by R1-R6)**:

<details>
<summary>Step 1-4 as written pre-restart (2026-04-20) — do not follow linearly</summary>

- Step 1 (Wiki seed): ~90% complete (65 pages, 70 MD files, 416KB). Carried forward into R4 reflection which appends new pages.
- Step 2 (Frame-only solvers): subsumed by R4 — reflection proposes refactors as they're needed, not in a hardcoded order.
- Step 3 (LLM + Wiki inference): subsumed by R2+R3+R6. The cold-prompt bench (2026-04-21: 8B 32%/40%, 14B 16%/40%) is a model-comparison artifact, not a deployment predictor.
- Step 4 (Independent cleanup): LF52/SK48 regression bisect still open; LoRA tuning deferred until R6 numbers say it's needed.

</details>

**Validation gates (R1-R6 framing)**:
- Gate A — R2+R3 regression: live-env ≥15 envs / 36 levels (2026-04-21 baseline), classification ≥45%.
- Gate B — R4 reflection effectiveness: ≥1 proposed change per run survives R5 gate; cumulative best_levels non-decreasing over 3 consecutive dev cycles.
- Gate C — R6 decision: live-env numbers with full features + full whitelist justify primary LLM choice. Target: ≥21/40 envs on v1+v2 combined (vs ensemble 28/40, WikiAgent 15/40).
- Gate D — Kaggle packaging: runtime ≤ 6h, VRAM ≤ 16GB, fully offline, frozen wiki + frozen strategies + frozen weights.

### R7 — Round Loop formalization (in progress)

Round 1 of the dev-time loop. Per user direction (2026-04-21), the R1-R6 skeleton is kept but the Qwen prompt and feedback schema are upgraded so each round produces actionable, structured input for the next round.

- [x] **R7a — Structured Hypothesis schema**. `features_missing` is now `list[FeatureGap(name, why_needed, derive_hint)]`; added `wiki_gaps: list[WikiGap]`, `wiki_needs: list[str]`, `doubt: str`. Parser (`_parse_feature_gaps`, `_parse_wiki_gaps`) accepts dict form; a single-commit tolerance for bare-string `features_missing` is FEEDBACK-GATED and deletable once all traces emit dicts. `scripts/analyze_trace.py` updated to group by `name` and surface a representative `why_needed` / `derive_hint` per feature.
- [x] **R7c — Qwen system prompt rewrite (English only)**. New sections: Output schema / Hard rules / Wiki search guidance / Feedback discipline / Expressing uncertainty / Carryover from prior rounds. `WikiAgent` now takes `round_num` + `round_learnings` and injects them into the prompt so every call knows which round it is and what the last round taught.
- [x] **R7e — Whitelist validation (`_validate_whitelist`)**. Filters hallucinated strategy names from primary/fallback before dispatch. Pins the 2026-04-21 R6 Qwen 14B FT09 `seq_search` regression as a FEEDBACK-GATED test.
- [x] **R7b — Graph-based wiki retrieval** (2026-04-21). `src/admorphiq/hypothesis/wiki_retrieval.py` with `GraphRetriever` that seeds from discovery signals (selector.md + reasoning core always; `game_types/hybrid.md` when both click and movement; `game_types/click.md`/`movement.md`/`concepts/merge_mechanic.md` by probe signature; `games/<TITLE>.md` by title match) then walks `[[backlinks]]` in keyword-scored order until the char budget is hit. Context budget raised 8K→16K (Qwen 128K context has room; seed pages saturated 8K before any link traversal). Smoke verified: SU15 now retrieves `concepts/merge_mechanic`, FT09 retrieves `games/FT09`, M0R0 retrieves `game_types/hybrid` + `games/M0R0` + `reasoning/hypothesis_check` — every env gets a different slice. 24 unit tests in `tests/test_wiki_retrieval.py`. Full suite 210/210.
- [x] **R7d — Round protocol** (2026-04-21). `scripts/round.py` with `start` / `finalize` / `learnings` subcommands writes `.omc/rounds/round_NNN/meta.json` + `notes.md`. `meta.json` captures goal, before/after summary (matching the regression gate's per-game_id aggregate), verdict (PASS/FAIL + per-env regressions/improvements lists), changes_made log, and prior_learnings_used. `round.py learnings N` replays prior rounds' takeaways — output is suitable for injection into WikiAgent's `round_learnings` prompt slot (R7c), closing the feedback carryover loop. 9 unit tests in `tests/test_round_protocol.py`. `.omc/rounds/round_001/` initialized for the first R7 bench.
- [ ] **R7f — Per-env multi-turn (UPGRADED to central, 2026-04-23)**. When primary fails, re-ask the LLM with the failure context before running fallback_stack. Originally optional — the 2026-04-23 framing correction makes this a **central architectural requirement**: without it, Qwen's self-healing role is degraded to single-shot routing, and the whole "LLM as game-completion driver" framing collapses. See below.

186/186 tests passing (was 174, +11 R7 schema tests + 1 replaced features test). Smoke-tested end-to-end against a mock `HallucinatingLLM` that emits `seq_search` + structured `features_missing` / `wiki_gaps` / `wiki_needs` — filter strips hallucination, structured feedback round-trips to trace intact.

### R16-R22 rounds (2026-04-23) — math-primitive additions, Claude-Code only

One-line summaries (commit messages have full detail; wiki pages
carry per-round provenance):

- **R16** (`377ca48`) — lights-out toggle stencil measurement (`_measure_toggle_stencil`, `_extract_cell_class`).
- **R17** (`009a6be`) — GF(2) solver + predictive ranking (`_gf2_solve`, `_homogeneity_score`, `_rank_subsets_by_prediction`).
- **R18** (`8c41623`) — delta-chain trials + cumulative cell sweep; FT09 L1 clears via generic path.
- **R19** (`fcc39ea`) — Sokoban-like navigation budget bump (30k); KA59 still blocked by BFS state-space explosion.
- **R20** (`afe6ab8`) — prefix-aware `_plan_navigation` using BFSSolver directly; broke AR25/M0R0 multi-level.
- **R21** (`ce95929`) — loosened `merge_items` heuristic (size 8..150); SU15 L1 still blocked on same-color-pair requirement.
- **R22** (pending commit) — restored `solve_all_levels` chaining inside `_plan_navigation`; AR25 2/2 verified.

**What R16-R22 got right**: the math primitives are generic
(verified grep for game_title / game_id in logic: clean). They
are usable building blocks for future Qwen-driven plan additions.

**What R16-R22 got wrong**: the rounds were run with Qwen out of
the loop. R11's `LLM_WHITELIST_ALLOWLIST={"adaptive_bfs_solver"}`
zeroed Qwen's voice, so Claude Code read direct-test results and
unilaterally wrote code. Per the 2026-04-23 framing correction,
this is a procedural bug — the LLM should have diagnosed the
failures and proposed the fixes; Claude Code should have
implemented them. All R16-R22 improvements remain valid CODE,
but the process needs to change for R23+.

### R23+ plan — restore Qwen to the dev loop

Target architecture: Qwen drives comprehension + plan selection +
failure diagnosis; Claude Code implements the fixes Qwen proposes.

- [ ] **R23 — Reopen the allowlist** (2026-04-24). Expand
  `LLM_WHITELIST_ALLOWLIST` from `{adaptive_bfs_solver}` to the
  ~14 frame-only strategies that actually have plan fns. Update
  `.wiki/wiki/llm_context/decision_tree.md` to reflect
  "inferential_agent first, swap on failure". Bench to verify
  Qwen doesn't re-anchor.
- [ ] **R24 — Debug playbook pages**. Populate
  `.wiki/wiki/debug/plan_failure_signatures.md` and per-plan
  pages with observable failure signatures + next-best pointers
  (stencil density > 0.8 → try plan X, merge_items=0 but
  responsive>10 → try plan Y, etc.). Sourced from R16-R22
  direct-probe traces.
- [ ] **R25 — Implement R7f per-env multi-turn**. `WikiAgent.run`
  captures per-env failure envelope on plan return; re-invokes
  the LLM with `{previous_attempt, failure_envelope, remaining_budget}`
  asking for next action (swap / retune / code-fix proposal).
  Session state tracks attempted plans so Qwen doesn't repeat.
- [ ] **R26 — Structured `CodeFixProposal` schema**. Extend the
  Hypothesis JSON with an optional `code_fix_proposals` field.
  Qwen writes "target: `_plan_lights_out`, reason: ..., suggested
  edit: use stride=4 on retry" into the trace. Dev-time Claude
  Code reads proposals at round start.
- [ ] **R27 — Runtime wiki signature exposure**. Each plan fn's
  wiki page (`strategies/frame_only/*.md`) must expose:
  observable-signature / falsification-signature / tunable
  parameters / next-best. This is the LLM's runtime reasoning
  surface.
- [ ] **R28+ — Iterative game-completion sprints**. For each
  failing game class (FT09 L2+, SU15, CD82 L2+, SB26, KA59),
  run the loop: Qwen diagnosis → Claude Code implements → bench
  → repeat until cleared or ceiling hit. Target: ≥ 1 new
  level per sprint.

**Gate for promoting past R23**: Qwen picks a non-primary
strategy on a bench where the primary returns 0 levels. If Qwen
always picks `adaptive_bfs_solver` regardless of failure, the
allowlist expansion is ineffective and we either re-prompt the
wiki or downgrade the decoder schema.

## Reference Projects

| Project | Approach | Score | Notes |
|---------|----------|-------|-------|
| [arcgentica](https://github.com/symbolica-ai/arcgentica) | Multi-agent LLM | 85.28% (AGI-2) | Online API needed, not Kaggle-compatible |
| [da-fr/arc-prize-2024](https://github.com/da-fr/arc-prize-2024) | Mistral 8B + LoRA + TTT + DFS | 53.5 (AGI-1) | Kaggle-compatible, single H100, **template for Phase 8 LLM track** |
| [DriesSmit/ARC3-solution](https://github.com/DriesSmit/ARC3-solution) | CNN action predictor | — | **ARC-AGI-3 specific**, closest reference |
| [transversal-arc-solver](https://github.com/khalildh/transversal-arc-solver) | Plücker geometry, zero learning | 316 tasks | No ML, pure math |
| [arcprize/ARC-AGI-3-Agents](https://github.com/arcprize/ARC-AGI-3-Agents) | Official framework | — | Required base framework |

## Key Research

- François Chollet, ["On the Measure of Intelligence"](https://arxiv.org/abs/1911.01547) (2019)
- ARC Prize research page: https://arcprize.org/research
- ARC-AGI-3 docs: https://docs.arcprize.org
- Kaggle discussion: https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-3/discussion
- Gemma 4 (2026-04-02 release, Apache 2.0): https://deepmind.google/models/gemma/gemma-4/

## Proven Approaches (from ARC-AGI-1/2 research)

1. **Discrete Program Search (DSL)** — define grid-transform primitives, search for compositions
2. **Test Time Training (TTT)** — fine-tune model on test examples at inference
3. **LLM as Hypothesis Generator** — generate candidate programs, verify against examples
4. **Active Inference** — real-time adaptation via few-shot fine-tuning (Jack Cole, 34%)
5. **Neurosymbolic** — neural perception + symbolic reasoning (Chollet's recommended direction)

## LLM Selection (Phase 8 Hypothesis Engine)

**Status**: 🔄 **Model undecided — pending Step 3-pre benchmark (Task #11)**. Do not pre-commit in scripts/docs; refer to the chosen model via config, not hardcoded imports.

**Why an LLM is needed**: Current high-scoring solvers depend on game-internal access (sprite tags, internal variables) that won't generalize to private test games. An LLM converts frame observations into rule hypotheses without source-code peek.

**Why the Karpathy LLM-Wiki pattern changed the calculus**: Earlier we favored Qwen 3 8B because LoRA fine-tuning was central. With Wiki-pattern zero-shot as the primary path, raw reasoning ceiling (where Gemma 4 26B MoE leads) matters more than LoRA ecosystem maturity. Decision now depends on measured Wiki-reading accuracy, not a-priori preference.

**Candidate comparison** (April 2026 specs):

| Model | Params | MMLU/Reason | Math (AIME) | VRAM (4bit, T4) | LoRA Ecosystem | Context | License |
|-------|--------|-------------|-------------|-----------------|----------------|---------|---------|
| **Qwen 3 8B** | 8B dense | 8B-class top | Strong | ~5GB | 🥇 most mature | 128K | Apache 2.0 |
| **Gemma 4 26B MoE** | 3.8B active / 26B | 31B-tier (top) | 89.2% (top) | ~13GB | 🥉 growing | 128K | Apache 2.0 |
| **Gemma 4 E4B** | 4.5B effective | Solid w/ thinking mode | Mid | ~3GB | 🥈 | 128K | Apache 2.0 |
| Llama 3.1 8B | 8B dense | Behind | Behind | ~5GB | 🥇 mature | 128K | Llama license — ⚠️ check Kaggle compat |

**Benchmark rubric (Task #11)**:
1. **Game classification accuracy**: given first 20 discovery frames + action effects → predict correct `game_type` (movement/click/programming_puzzle/merge_puzzle/sokoban). 25-game labeled test.
2. **Strategy selection hit rate**: given classified type + top-3 similar `wiki/games/*.md`, pick strategy. Score = % matches to known-good dispatch.
3. **Latency**: tokens/sec on simulated T4 (local proxy: MPS or 4090 with T4 memory cap).
4. **VRAM headroom**: measured usage alongside loaded CNN (34M) + World Model (1.6M).
5. **LoRA viability** (secondary): only relevant if zero-shot underperforms.

**Decision output**: one primary model + one fallback. Config in `configs/llm.yaml` so swap is a one-line change.

**Do NOT do before benchmark**:
- Write `scripts/run_wiki_agent.py` with a specific model hardcoded
- Pre-download any single model's weights to Kaggle dataset
- Commit LoRA training scripts targeting one specific model

## Live Test Results

### Phase 2.5 (Baseline, 80 actions)

| Game | Layers | Actions | ms/action | Levels | Result |
|------|--------|---------|-----------|--------|--------|
| DC22 | 1 | 80 | 552 | 0/6 | Failed |
| LF52 | 2 | 80 | 463 | 0/10 | Failed |
| BP35 | 2 | 80 | 454 | 0/9 | Failed |

### Phase 3.5 (Exploration Improvements, 500 actions)

| Game | Actions | Levels | ms/action | ACTION6 ratio |
|------|---------|--------|-----------|---------------|
| DC22 | 500 | 0/6 | 1308 | 484/500 |
| LF52 | 500 | 0/10 | 1316 | 482/500 |
| BP35 | 500 | 0/9 | 1279 | 481/500 |

### Phase 4 (Multi-Strategy Comparison, 25 games)

| Approach | Games Cleared | Levels Cleared | Speed |
|----------|---------------|----------------|-------|
| CNN Phase 2.5 | 0 | 0 | 500ms/action |
| CNN Phase 3.5 | 0 | 0 | 1300ms/action |
| Frame Diff Solver | **4** | **4** | 25s / 25 games |
| Graph-based | 1 | 1 | <1ms/action |
| Frame Diff Engine | 1 | 1 | 0.6s/game |
| CNN StochasticGoose | 0 | 0 (100 actions) | 154ms/action |

### Phase 7 (Ensemble + Analytical Solvers, Round 1 — 2026-04-20)

**Source of truth**: `scripts/ensemble_results.json` (2026-04-20 22:24–22:38, 826s runtime)

**Verified results**:
- v1 primary versions only (legacy 25-game metric): **23/25 games, 67/182 levels (36.81%)**
- All API-served envs (40 total, 12 games with 2 version hashes): **31/40 envs, 79/289 levels (27.34%)**

Perfect clears on v1 (5 games verified): **CD82 6/6, FT09 6/6, SB26 8/8, SU15 9/9, TN36 7/7**

Previous baseline (2026-04-10, backed up to `scripts/ensemble_results.20260410.json`): 22/25 games, 56/182 levels (30.77%)
Round 1 improvement: **+1 game (TN36), +11 levels** (TN36 +7, SU15 +2, KA59 +2)

Verified per-game depth (sorted):
| Game | Levels | Status |
|------|--------|--------|
| SB26 | 8/8 | ✅ perfect |
| SU15 | 7/9 | ✅ |
| RE86 | 6/8 | ✅ |
| FT09 | 6/6 | ✅ perfect |
| CD82 | 6/6 | ✅ perfect |
| TU93 | 2/9 | ✅ |
| AR25 | 2/8 | ✅ |
| M0R0 | 2/6 | ✅ |
| SC25 | 2/6 | ✅ |
| KA59 | 2/7 | ✅ |
| WA30 | 2/9 | ✅ |
| CN04, TR87, LP85, DC22, SP80, G50T, BP35, S5I5, R11L, VC33, LS20 | 1 each | ✅ |
| **LF52** | **0/10** | ❌ regression (was cleared earlier) |
| **SK48** | **0/8** | ❌ regression (was cleared earlier) |
| **TN36** | **0/7** | ❌ never cleared in regression |

**Unverified post-regression commits** (commit messages, single-game tests only):
- 5e8562a: TN36 7/7 via `strat_tn36_puzzle` (uses `frame.zpzcmabenn`)
- b84839e: SU15 7→9 (L8/L9 hardcoded), KA59 2→4 (L3/L4 push mechanics)
- These boost CLAIMED score to 25/25 / 69 levels / 37.9%, but require fresh 25-game regression to confirm and to check whether LF52/SK48 still regress

### Lessons Learned
- **Frame structure mismatch**: Actual frames are multi-layer with variable layer count and int8 color indices, not fixed 16ch one-hot as initially assumed
- **Training bottleneck**: 440ms per action spent on training, only 8ms on inference -- training dominates runtime
- **Kaggle time budget is sufficient**: 6 hours allows 43K+ actions at current speed
- **Early diversity improved**: Action variety went from 1-2 types to 3-5 types, ACTION6 coordinate exploration realized
- **Change prediction has fundamental limits**: CNN converges to ACTION6-only preference, 500 actions still 0 levels cleared
- **StochasticGoose gap explained**: Same architecture but 0% -- root cause was coordinate scaling (/4096 missing), reward=0.3 (not binary), low train frequency
- **Game classification is key**: 25 games classified into movement(7), click(6), hybrid(6), transform(2), unknown(4) -- strategy should branch by type
- **Ensemble potential realized**: Graph/Diff/CNN/Analytical each clear different games — ensemble dispatch via feature-based triggers reaches 25/25
- **Analytical solvers are double-edged**: Game-internal access boosted score from 12% → 38% but creates Phase 8 generalization debt

## What Doesn't Work

- Direct LLM prompting alone (<5% on ARC-AGI)
- Pure memorization / pattern matching (tasks are novel by design)
- Ensembling existing solutions (doesn't generalize to private test set)
- Brute force search without heuristics (search space too large)
- **Change prediction as sole strategy** (tested Phase 2.5-3.5): CNN learns to predict which actions cause state changes, but converges to ACTION6-only preference without understanding game goals. 500 actions across 3 games, 0 levels cleared.

## Agent Behavior Rules

- **NEVER suggest stopping, pausing, or continuing in a "next session"**. Keep the infinite improvement loop running until the user explicitly says to stop.
- **NEVER say** "오늘 많이 했다", "다음 세션에 이어서 하자", "여기서 마무리하자", or similar phrases.
- The test→log→analyze→fix→retest loop runs indefinitely. Commit periodically but never use commits as a reason to stop.
- All 4 strategies (CNN, Ensemble, Graph, Diff) run in parallel. Never abandon one unless the user approves with clear justification.
- **Proactively keep CLAUDE.md in sync** with each phase commit — never wait for the user to point out stale stats.

## Dev-Time Round Loop (Phase 8)

Every improvement cycle is a **round** tracked under `.omc/rounds/round_NNN/`.
The protocol exists so ad-hoc bench runs don't lose provenance.

**Per-round files**:
- `meta.json` — structured metadata. `round.py start` seeds it with the
  current baseline snapshot; `round.py finalize` captures after-summary
  + verdict.
- `notes.md` — freeform work log. Claude Code appends to this during the
  round as changes are proposed, reviewed, and applied.

**Lifecycle** (runnable from the repo root):
1. `uv run python scripts/round.py start N --goal "..."`
2. (Qwen proposes → Claude Code applies → bench)
3. `uv run python scripts/round.py finalize N --trace scripts/wiki_agent_results_rN.json --takeaway "one-line lesson"`
4. If PASS, promote the baseline: `uv run python scripts/regression_gate.py --trace ... --promote`
5. Next round pulls the takeaway via `round.py learnings N+1` and
   injects it into WikiAgent's `round_learnings` prompt slot (R7c).

**Round principles**:
- The LLM (Qwen) is the **proposer**, Claude Code is the **implementer**.
  Never let Qwen write code or wiki directly — 8B-class models are
  reliable at spotting gaps but unreliable at integrating changes into
  an 8000-line codebase (measured in R4).
- Structured feedback only. `features_missing` and `wiki_gaps` entries
  without the R7a-required fields are parser-dropped, not coerced.
- Every round must produce a one-line `takeaway`. If the round taught
  nothing worth remembering, the goal was wrong or the bench is noise.
- Regression gate is non-optional. A round that fails R5 rolls back the
  proposing commit; the baseline only moves forward.

### Round 1 outcome (2026-04-21, FAIL, not promoted)

First real loop cycle. Infrastructure validated end-to-end: 4 bench
iterations in one session, each driven by measuring the prior failure
and adding one defensive layer. Final numbers: 15/40 raw envs cleared,
19 levels, 0 hallucinations. Baseline (pre-R7): 15/40 / 36 levels / 12
hallucinations. So env coverage = baseline, hallucinations crushed to
zero, but levels -17 because 4 games lost their game-specific fallback
picks (FT09 / CD82 / SB26 / AR25). Gate verdict FAIL; baseline NOT
promoted.

Four rules were extracted from the round and hoisted into main docs
(see `.wiki/wiki/architecture.md` "LLM Output Shape Enforcement" and
"Routing Rules Require Python Reinforcement" sections, and
`.wiki/schema.md` "Frontmatter Policy"):

1. Strip YAML frontmatter from any retrieved wiki page before feeding
   it to the LLM.
2. Enforce output JSON shape at the decoder (Ollama `format` param),
   not via prompt instruction alone.
3. Enum-bind fields with closed value sets (strategy names, game_type).
4. `uniqueItems: true` on choice arrays to prevent duplicate padding.

Round 2 candidate action (picked up from the lesson page): add a
Python-level post-processing step that guarantees `<title>_frame_only`
or title-matching whitelist strategies land in `fallback_stack` — a
reinforcement of selector.md's title-match rule that Qwen ignored
under 16KB context.

### Round 2 outcome (2026-04-21, FAIL, not promoted)

Landed title-match + rule-4 (click-only) Python reinforcements
(`_augment_with_title_match`, `_augment_click_only_rule4` in
`src/admorphiq/hypothesis/wiki_agent.py`). Result: 20/40 envs cleared,
37 levels raw (vs R1 15/40, 19 levels). FT09 recovered 0→6 via rule-4
`lights_out` injection; SB26 recovered 0→8 via title-match `sb26_sort`.
Gate FAIL because AR25 (-2) and CD82 (-6) remained unrecovered — both
match selector.md rule 3 (hybrid) but Qwen picked `explore_and_interact`
/ `click_select_move` instead of `bfs_state_space` + `paint_game`.

Round 3 candidate: Python reinforcement of selector.md rule 3 — inject
`bfs_state_space`, `paint_game`, `click_toggle_detect` into fallback_stack
for any env where `avail ⊇ {1,2,3,4}` AND `6 ∈ avail`.

### Round 3 outcome (2026-04-21, FAIL, not promoted)

Added `_augment_hybrid_rule3` Python reinforcement for rule 3. Result:
26/40 envs cleared, 47 levels raw (vs R2 20/40, 37 levels). Rule-3 worked
for **movement-dominant hybrids**: AR25 0→2, M0R0 0→2, SC25 0→2, WA30
0→2, BP35/R11L/SK48/TR87 +1 each. Cumulative R1→R3: **19→37→47 levels
(+28)**.

Gate FAIL, two defects surfaced that round 3 is explicitly not fixing:

1. **CD82 stuck at 1/6 (vs baseline 6/6).** Paint-dominant hybrid
   (probe6 responsive=5/5, probe 3/4 huge diff). Rule-3 put `paint_game`
   into fallback[1], but `WikiAgent.run()` breaks on first success —
   `explore_and_interact` cleared 1 level, loop broke, `paint_game` never
   ran. Run-loop policy issue, not a rule-3 issue.
2. **G50T regressed 1→0.** Qwen emitted `[bfs_state_space × 3]` as
   fallback_stack despite `uniqueItems: true`. Ollama 0.20.3's `format`
   enforcement doesn't honor uniqueItems for Qwen 3 8B. Stochastic LLM
   variance.

Round 4 candidates (a), (b), (c) listed here historically were all
Python-layer patches. **Rejected by user directive** mid-round 4: no
more Python-level routing. See "Round 4 outcome" below.

### Round 4 outcome (2026-04-21, FAIL, not promoted)

User directive (paraphrased): *"Don't keep patching LLM mistakes with
Python helpers. Don't stack fallbacks as a workaround. Fix the wiki
so Qwen reasons correctly from frame observations alone."* This turned
rounds 2-3 into rollback debt — those helpers were hardcoded to 25
preview games and made the bench score rise without transferring to
Kaggle private test.

Round 4 enforces **Wiki-First Routing** (architecture.md §). The three
`_augment_*` helpers and the title-match utility in
`src/admorphiq/hypothesis/wiki_agent.py` are deleted. `classify()` now
only runs `_validate_whitelist`. Selector.md rule 3 was split into 3a
(movement-hybrid, uniform movement probes, dead click) / 3b
(paint-hybrid, asymmetric probes, responsive click) / 3c
(transform-hybrid, asymmetric probes, dead click). A new
`concepts/probe_signature.md` page defines the observable
discriminators (probe-ratio, click-responsiveness). Enforcement layered:

- `tests/test_classify_contract.py` — semantic contract test,
  title-blind + probe-signature-blind invariants.
- `.claude/hooks/guard_wiki_agent.sh` — PreToolUse warning on edits to
  wiki_agent.py.
- `.claude/hooks/run_contract_tests.sh` — Stop hook, blocks response
  completion when the contract test is red.
- CLAUDE.md "Prohibited Patterns" section lists banned helper name
  patterns.

**Bench result**: 40/40 envs, 31 raw levels (vs R3 47, -16). Unique
22 levels (vs R3 34, -12). Gate FAIL against baseline: SB26 -8, LS20
-1, M0R0 +2, net -7.

The honest read: rounds 2-3's 47-level peak was inflated by Python
hardcoding. Round 4's 22 unique levels is the true wiki-only baseline
of Qwen 8B + current strategies.

**Wiki-first success — CD82 0/6 → 6/6**. Qwen read the new rule 3b
(paint-hybrid signature) and picked `paint_game` primary on its own,
without any Python helper. This is the first measured evidence that
the Karpathy LLM-Wiki pattern works end-to-end for a routing decision
that the previous round needed a Python override to get right.

**Wiki gaps revealed**:

- **SB26 (−8)** — Qwen classified `click` and picked `click_rare`
  instead of applying selector rule 7 (sort-puzzle: `avail ⊇ {5,6}`,
  no 1-4). The rule is present in selector.md but the title-match
  preference block is too soft. Fine-grained rules (5, 6, 7) need
  stronger probe-signature discriminators.
- **SC25 (−2)** — Qwen classified `unknown`, picked `bfs_state_space`.
  No `spell_cast` discriminator in selector.md's signature rows.
- **SU15 (0/9, same as R3)** — Qwen picked `su15_vacuum` (brittle,
  name contains `vacuum`). The "prefer frame-only" note is too soft
  and `su15_frame_only` vs `su15_vacuum` disambiguation isn't explicit.

**Strategy-implementation gap — bigger problem**: 12 whitelisted
strategies read game-internal sprite tags or attribute names:

| Strategy | Hardcoded to |
|---|---|
| `paint_game` | CD82 sprite tags `pqkenviek`, `ctwspzkygu` |
| `lights_out` | FT09 tags `Hkx/NTi/bsT/ZkU`, `game.` |
| `sb26_sort` | SB26 `frame.`, `game.` internals |
| `su15_frame_only` (name sayiing frame-only!) | `hmeulfxgy`, `peiiyyzum`, `rqdsgrklq` (SU15) |
| `su15_vacuum` | same SU15 internals |
| `tn36_frame_only`, `tn36_puzzle` | `zpzcmabenn` (TN36) |
| `ka59_sokoban` | `game.` (KA59) |
| `re86_analytical` | `vzuwsebntu`, `vfaeucgcyr`, `ozhohpbjxz` (RE86) |
| `wa30_analytical` | `wbmdvjhthc`, `wyzquhjerd`, `pkbufziase` (WA30) |
| `s5i5_slider` | `myzmclysbl`, `zylvdxoiuq` (S5I5) |
| `bp35_platformer` | `game.` (BP35) |

Even round 4's CD82 +5 only works because `paint_game` reads CD82
internals. On Kaggle private test, where sprite tags differ, it
produces 0. The honest ceiling for a Kaggle submission is the set of
frame-only generic strategies: `bfs_state_space`, `click_rare`,
`click_toggle_detect`, `click_color_order`, `click_select_move`,
`explore_and_interact`, `spell_cast`, `tu93_maze`, `tr87_rotation`,
`ls20_grid`, `sk48_snake`, `zigzag`, `raster`, `click_all_colors`.

Round 5 candidates (pick one):
- (a) **Wiki discriminator strengthening** — write the missing
  signature rules into selector.md so Qwen applies rules 5/6/7 and the
  frame-only-vs-brittle preference. Projected: recover SB26 / possibly
  SU15 via `su15_frame_only` (still hardcoded, but at least routed).
- (b) **Brittle purge from the whitelist** — remove the 12
  hardcoded strategies from `default_strategy_registry` so Qwen cannot
  select them. Bench score drops further but reflects actual Kaggle
  reality. Forces the strategy re-implementation work to be visible.
- (c) **Strategy re-implementation (generic)** — rewrite `paint_game`
  and `lights_out` to detect paint/toggle structure from frame pixels
  (connected components, color clustering) without reading internals.
  Highest leverage, biggest lift — easily a full round each.

### Round 5 outcome (2026-04-22, FAIL, not promoted)

Picked option **(b) + (c) combined**: purged the 12 brittle strategies
from `default_strategy_registry()` AND added four generic inference
classes (G1-G4) to `agent_ensemble.py` that combine probing + frame
analysis + state-space search. None of the G1-G4 functions read
game-internal sprite tags or attribute names.

**Code changes**:
- `src/admorphiq/agent_ensemble.py` — added `strat_interactive_grid_toggle`
  (G1, replaces paint_game/lights_out/tn36_frame_only), `strat_sprite_cluster_interaction`
  (G2, replaces su15_*), `strat_push_bfs_grid` (G3, replaces
  ka59_sokoban/wa30_analytical), `strat_bfs_framehash` (G4, universal
  fallback). Stripped L1 hardcoded sequences from `strat_tu93_maze`,
  `strat_tr87_rotation`, `strat_ls20_grid` — they now BFS every level.
- `src/admorphiq/hypothesis/dispatcher.py` — added `BRITTLE_STRATEGIES`
  frozenset (12 names) and deny-filter in `introspect_strategies`.
  Registry size 67 → 59.
- `.wiki/wiki/selector.md` — rules 4/5/6/7/8 now reference G1-G4 names.
  Added "four generic inference classes" table mapping G1-G4 to what
  each replaces and how each works.

**Tests**: 243/243 passing (was 228; +13 generic-strategy tests + 2
dispatcher tests pinning the deny-list and G1-G4 registry presence).

**Bench**: 40/40 envs, 27 raw levels, 1943s.

| Metric | R3 | R4 | R5 | Δ vs R4 |
|---|---|---|---|---|
| Raw levels | 47 | 31 | **27** | -4 |
| Unique envs cleared | 17/25 | 9/25 | **11/25** | +2 |
| Unique levels | 34 | 22 | **15** | -7 |
| Gate | FAIL | FAIL | **FAIL** | — |

**Gate verdict**: FAIL — CD82 6→1 (-5), FT09 6→0 (-6), SB26 8→0 (-8)
all attributable to the brittle purge. M0R0 0→2, SC25 0→2, SK48 0→1
improvements offset partially. LS20 0→1 recovered via pure BFS after
its L1 hardcoded sequence was removed.

**Critical diagnostic finding — G1-G4 were never executed**. Qwen 3
8B's primary-strategy picks across all 40 envs:

```
bfs_state_space   26
click_rare        14
```

`interactive_grid_toggle`, `sprite_cluster_interaction`,
`push_bfs_grid`, `bfs_framehash` — 0 picks primary, 0 picks fallback.
The 27 raw levels in R5 came entirely from the two pre-existing
generic strategies. G1-G4 implementations are in the whitelist and
selector.md references them, but 8B collapses to familiar names under
long wiki context — the same pattern measured in rounds 1 / 3 / 4.

**Honest read**: R5's 15 unique levels is the true Kaggle-realistic
frame-only baseline of Qwen 8B + the current generic strategy set.
R2/R3's 37/47 were inflated by brittle internal reads; R4's 22 was
closer but still included CD82 +5 from `paint_game`'s CD82-specific
sprite tags. All those gains were fake for deployment.

**Round 6 candidates** (diagnostic → fix, in order):
1. **Direct G1-G4 validation** — run `strat_interactive_grid_toggle`,
   `strat_sprite_cluster_interaction`, `strat_push_bfs_grid`, and
   `strat_bfs_framehash` against CD82 / FT09 / SB26 / SU15 live envs
   outside the WikiAgent loop. Necessary before any routing fix —
   confirms whether the implementations actually work, or are also
   broken (in which case routing them wouldn't help).
2. **Remove bfs_state_space + click_rare from the whitelist** — forces
   Qwen to pick from G1-G4 + peers. Radical but measures G1-G4
   effectiveness. Reversible.
3. **Decoder bias / anchor the prompt at G1-G4** — move G1-G4 to the
   front of the strategy list, tag them in selector.md as "preferred
   for any click-driven game", add explicit "if you see signature X,
   pick G-Y" sentences. Round 4 showed this doesn't fully work at 8B
   but it's cheap to try.
4. **LLM upgrade** — Qwen 3 14B hallucinated in round 6 pre-R7; Gemma
   4 E4B untested. Pick based on `configs/llm.yaml` candidate matrix
   and what Kaggle VRAM allows.

### Round 6 outcome (2026-04-22, partial progress, not promoted)

Diagnostic via `scripts/probe_generics_direct.py` revealed round-5's
G1-G4 were "generic" only in the "no hardcoding" sense — their
internals were brute-force search/enumeration with fixed thresholds.
Direct-run score: **0-1/47 cleared** across FT09/CD82/SB26/SU15/KA59/
WA30/AR25/M0R0/DC22/TN36. See
`.wiki/wiki/lessons/g1_g4_direct_test_20260422.md` for the full
measurement arc.

User directed: redesign as a real inference agent (Chollet framing —
"intelligence = efficiency of skill acquisition in novel situations").

Implemented `strat_inferential_agent` in
`src/admorphiq/strategies/inferential.py` — 528-line five-phase
pipeline:

  Phase 1 Observation — probe every action + stride-8 grid + cluster
    centroids, record (diff_magnitude, bbox, centroid, region_kind,
    did_transition) per probe.
  Phase 2 Entity Detection — flood-fill clusters, match before/after
    across movement probes, tag player = cluster with highest
    "mobility" (number of directions it shifts ≥ 2 px under), plus
    executor / palette / goal-region / merge-item / obstacle tags.
  Phase 3 Goal Inference — prefer navigation when player detected,
    else merge / paint-fill / toggle from observed transitions or
    entity-map heuristics.
  Phase 4 Plan Synthesis — delegates navigation plan to the proven
    `strat_bfs_state_space` engine (iteration 4-7 showed in-plan BFS
    re-implementations were buggy). Merge / paint / toggle plans are
    still domain-specific and need per-game refinement.
  Phase 5 Learning Loop — on plan failure, widen probe stride,
    re-tag entities, and retry sibling plans.

Added `.wiki/wiki/llm_context/decision_tree.md` (≤ 1200 chars) and
made it the first seed in `wiki_retrieval.derive_seed_pages` so 8B
Qwen gets the compact dispatch decision before attention degrades on
longer prose pages.

Registry: 60 strategies (was 59; +1 `inferential_agent`). Brittle
deny-list unchanged.

**Direct-test result** (`scripts/probe_inferential_direct.py` v9,
1479 s for 10 envs):

| Env | I-Agent v9 | Brittle | Notes |
|---|---|---|---|
| AR25 | 2/2 | 2 | navigation plan via bfs_state_space |
| M0R0 | 2/2 | 2 | navigation |
| DC22 | 1/1 | 1 | navigation |
| CD82 | 1/6 | 6 | navigation partial |
| FT09 | 0/6 | 6 | toggle plan not reaching lit cells |
| SB26 | 0/8 | 8 | merge plan doesn't handle sort-order |
| SU15 | 0/9 | 9 | merge plan outside vacuum radius |
| TN36 | 0/7 | 7 | bit-panel combinatorial search infeasible |
| KA59 | 0/4 | 4 | push plan not implemented |
| WA30 | 0/2 | 2 | pick-carry-drop plan not implemented |

Cleared 6/47 levels (13% of brittle baseline), up from 1/47 in the
G1-G4 round-5 state. Navigation plan is effectively at brittle parity
(2+2+1 = 5 levels on M0R0/AR25/DC22 match the brittle 2+2+1 = 5).

Tests: 243/243 passing. Updated `test_wiki_retrieval.py` seed-order
invariant to require `llm_context/decision_tree.md` first.

Runtime: 1479 s for 10 envs = **147 s / env** is too slow for a full
40-env WikiAgent bench (would run ≈ 1.6 hours). Round 7 must cap
per-plan budget and/or parallelize plan fanout.

**Round 7 candidates**:

1. Cap `_plan_navigation` budget at 10000 instead of 50000 so
   unsolvable levels bail fast (AR25 took 866 s because BFS tried L3
   with full 50k budget after L1+L2 were already cleared).
2. Implement **toggle plan** properly for FT09-class (sparse
   responsive cells): enumerate combinations of cluster-responsive
   cells up to depth 4, test each as click sequence.
3. Implement **merge plan** with vacuum-radius calibration (probe
   near a pair to measure reach, then only propose midpoints within
   radius).
4. Run full WikiAgent bench with the decision_tree.md seed and
   I-Agent registered — measure whether Qwen now picks
   inferential_agent (previous rounds defaulted to bfs_state_space /
   click_rare).

### Round 7 outcome (2026-04-22, FAIL vs baseline, raw +8 vs R5)

Applied three I-Agent refinements in
`src/admorphiq/strategies/inferential.py`:

- **Nav budget cap**. Per-plan budget caps: navigation 10 000,
  toggle 15 000, merge 12 000, paint_fill 12 000. Previously a single
  plan call could burn the full 50 000. AR25 direct-test time did not
  shrink much (875 s → 875 s; arcengine `env.step` is ~60 actions/sec,
  so wall-clock is dominated by step latency, not plan cost).
- **Toggle plan rewrite**. Candidates now include every cluster
  centroid PLUS corner samples of non-trivial clusters, not just cells
  that showed immediate click-responsiveness. Depth extended to 4.
  Rationale: FT09 has 0/20 responsive probes on cluster centroids,
  yet brittle `lights_out` clears 6/6 — clicks are being registered
  but the effect is delayed / cumulative. Still didn't clear FT09 in
  the v10 direct test; likely needs even deeper combinations or a
  different cell-selection heuristic.
- **Merge plan vacuum-radius calibration**. Infer radius R from
  observation-phase click probes (max click-to-diff-bbox L∞
  distance). Only propose midpoints for pairs within 2R. Fallback
  click positions: midpoint → 1/3 → 2/3 → on-cluster. Still didn't
  clear SU15.

**Bench result** (full 40-env WikiAgent, 1911 s):

| Metric | R5 | R6 | **R7** | Δ vs R5 |
|---|---|---|---|---|
| Raw levels | 27 | — | **23** | — |
| Raw envs cleared | 11/40 | — | **17/40** | **+6** |
| Raw total (trace) | 15 | — | **23** | **+8** |
| Gate | FAIL | — | **FAIL** | CD82/FT09/SB26 |
| I-Agent picks (primary) | 0 | — | **0** | no change |

The compact `llm_context/decision_tree.md` seeded first in the
retriever DID improve Qwen's decisiveness: raw-levels 15 → 23 (+8)
even though I-Agent is never selected. `bfs_state_space` got 25
picks, `click_rare` got 15, I-Agent 0. The gate still fails because
CD82 / FT09 / SB26 all need brittle strategies (purged) OR I-Agent
(not selected).

**Critical finding — Qwen 8B anchor bias is very strong**. Four
rounds of wiki work (R3 split, R4 architecture pivot, R5 G1-G4, R6
decision_tree) have not dislodged Qwen's anchoring on the two most
familiar strategy names. Adding new names to the whitelist does not
change routing behavior.

**Round 8 direction**: force the single-entry-point by removing
`bfs_state_space` and `click_rare` from the LLM-pickable whitelist.
They remain internally callable from `strat_inferential_agent`'s
navigation plan (which delegates to `strat_bfs_state_space`). Qwen
will be forced to pick a name it has never been "used to" — ideally
`inferential_agent`. Projected: I-Agent primary picks jump to ~30/40,
measured levels become a direct test of I-Agent's in-bench
performance.

### Round 8 outcome (2026-04-22, FAIL — anchor-whack-a-mole confirmed)

Added `ANCHOR_BANNED_STRATEGIES = {"bfs_state_space", "click_rare"}`
to `src/admorphiq/hypothesis/dispatcher.py` and extended
`introspect_strategies` to skip them with the round-8 reason.
Registry 60 → 58. Tests 243 → 245 (+2 round-8 invariants).

Updated `.wiki/wiki/llm_context/decision_tree.md` to state
`inferential_agent` as the ONLY first-class choice.

**Bench result** (40 envs, 688 s):

| Metric | R5 | R6 | R7 | **R8** | Δ vs R7 |
|---|---|---|---|---|---|
| Raw levels | 27 | — | 23 | **4** | **-19** |
| Envs cleared | 11/40 | — | 17/40 | **4/40** | **-13** |
| Qwen primary dist | bfs 26, click_rare 14 | — | bfs 25, click_rare 15 | **bfs_explore 22, click_rotation_puzzle 14, bfs_framehash 4** | anchor moved |
| I-Agent picks | 0 | — | 0 | **0** | unchanged |
| Gate | FAIL | — | FAIL | **FAIL** | CD82/FT09/SB26/+5 new regressions |

**Decisive finding — anchor-whack-a-mole**: removing the two
high-frequency names did NOT push Qwen toward `inferential_agent`.
Instead the model found the next-most-familiar BFS-shaped name
(`bfs_explore`) and click-shaped name (`click_rotation_puzzle`) and
continued anchoring on those. The compact `decision_tree.md` saying
"always pick inferential_agent" had no measurable effect.

Score collapsed because the fallback anchors (`bfs_explore`,
`click_rotation_puzzle`) are substantially weaker than the removed
ones. 8 envs regressed vs the pre-R7 baseline, including games that
R5/R6/R7 had cleared (TU93, AR25, DC22, SP80, FT09, SB26, LS20,
CD82).

**Round 9 direction (ultra-minimal whitelist)**:

The whack-a-mole proves that *partial* whitelist purging doesn't
work — the model will always find another BFS-like name to anchor
on. Round 9 eliminates that option by shrinking the whitelist to
only the strategies that actually form a coherent routing
architecture:

- `inferential_agent` — the sole routing entry point
- `click_toggle_detect` — minimal fallback for click-only puzzles
  that the inference phase timed out on
- `click_all_colors` — minimal fallback for color-scan games
- `click_color_order` — minimal fallback for pattern-click games

Every other `strat_*` gets added to `ANCHOR_BANNED_STRATEGIES`
(expanding the set from 2 to ~50). Qwen will have no BFS-like
name to anchor on; the whitelist is designed so the inferential
agent is the only sensible primary pick. Internal delegation
continues to call the banned strategies as needed.

This is the logical endpoint of wiki-first routing: if the
architecture says "the agent decides per-env via its phases", then
the LLM's routing choice should literally be "run the agent".

### Round 9 outcome (2026-04-22, FAIL — name-preference pathology)

Implemented `LLM_WHITELIST_ALLOWLIST = {"inferential_agent",
"click_toggle_detect", "click_all_colors", "click_color_order"}`
and extended `introspect_strategies` to skip every strategy not in
the allowlist. Registry 58 → 4. Tests 245 → 243 (retired two
obsolete invariants about the bigger registry, added the round-9
exact-set invariant).

Bench (aborted at 11/40 envs): Qwen picked `click_toggle_detect`
11/11 times. `inferential_agent` 0. The same model that had been
picking `bfs_state_space` across 40 envs now picks
`click_toggle_detect` across all its attempts — any name BUT
`inferential_agent`.

**Finding — name-preference pathology**: Qwen 3 8B actively avoids
the string `inferential_agent` regardless of how few alternatives
are offered. The 4-item allowlist was not enough to force the pick.
Likely cause: "inferential_agent" is an abstract noun phrase that
Qwen's pretraining associates weakly with executable code; the
other three names are concrete action-compound phrases
(verb_subject_noun).

Round 10 candidate: rename the underlying function to a name Qwen
is more likely to pick — e.g. `adaptive_bfs_solver` (retains `bfs`
token Qwen already anchors on, distinguishing adjective).

### Round 10 outcome (2026-04-22, FAIL — rename didn't help)

Aliased `strat_inferential_agent` → `strat_adaptive_bfs_solver`
and updated the allowlist to use the new name. 4-item allowlist:
{adaptive_bfs_solver, click_toggle_detect, click_all_colors,
click_color_order}. Decision_tree.md updated.

Bench aborted at 11/40 envs: `click_toggle_detect` picked 11/11,
`adaptive_bfs_solver` 0. The `bfs`-token anchor hypothesis was
wrong — Qwen picks the click-verb-compound over any adj-noun-noun
form.

### Round 11 outcome (2026-04-22, architectural PASS — I-Agent runs 100%)

Collapsed the allowlist to a single item: `{adaptive_bfs_solver}`.
Schema in `wiki_agent.py` relaxed so `uniqueItems` only applies
when whitelist ≥ 4; maxItems of fallback_stack scales to the
whitelist size. The decoder now has exactly one valid name to
return for `primary_strategy`.

**Bench result** (40 envs, 4295 s):

| Metric | R7 | R8 | R11 |
|---|---|---|---|
| Raw levels | 23 | 4 | **20** |
| Raw envs cleared | 17 | 4 | **14** |
| Adaptive-BFS-solver primary picks | 0 | 0 | **40** |
| Gate | FAIL | FAIL | FAIL |

For the first time in rounds 6-11, Qwen picked the inferential
agent on every single env. I-Agent's five-phase pipeline actually
executed 40 times.

**Per-env clears** (14 unique cleared):

  TU93 2, AR25 2, M0R0 2, DC22 1, SP80 1, SK48 1, LS20 1, CD82 1

**Per-env failures** (18 unique 0):

  RE86, SU15, CN04, FT09, TR87, SC25, LP85, KA59, G50T, SB26, LF52,
  BP35, S5I5, R11L, WA30, VC33, TN36, plus duplicates.

Gate FAIL: cleared 10 → 8 (−2), levels 29 → 11 (−18). Regressions
are against the pre-R7 baseline which was brittle-inflated:
FT09 (−6), CD82 (−5), SB26 (−8), LP85 (−1), VC33 (−1). Brittle
strategies cleared those games via sprite-tag reads that this
architecture intentionally excludes.

R11 is the honest Kaggle-realistic baseline of the current
InferentialAgent implementation + Qwen 3 8B. Every level in the
20-level total came from the real single-entry-point path: Qwen →
adaptive_bfs_solver → five-phase pipeline → internal plan
delegation → ensemble primitives. No hardcoding, no
title-matching, no brittle sprite-tag reads.

**Architectural takeaway**: Wiki-First Routing is now
**end-to-end enforced**. Rounds 4-10 each proved a different way
the architecture could be undermined; round 11 closes the last
loophole by forcing the LLM's routing pick mechanically.

**Round 12 direction**: the routing layer is done. Remaining lift
comes from plan-quality improvements inside strat_inferential_agent
so the 18 unsolved game classes clear something:

1. Toggle plan needs sparse-click strategies for FT09 / TN36 —
   maybe interaction with `click_toggle_detect` logic from
   `agent_ensemble`.
2. Merge plan needs vacuum-radius calibration that actually
   triggers SU15-class merges.
3. Paint plan needs palette/executor detection that works on CD82.
4. Push plan needs grid-aware item-state BFS for KA59 / WA30.

Each is a per-plan iteration, not a routing layer change.

### Round 12 outcome (2026-04-23, observation HUD masking, bench unchanged)

Added HUD masking to `observation_phase` — pixels that change under
≥ 80 % of all probes (step counters / timers / animated overlays)
are identified post-hoc and subtracted from every probe's effective
`diff_magnitude` / `bbox` / `centroid` / `region_kind`. The raw
diff mask is also exposed as `profile["hud_mask"]`.

Motivation: CD82 trace showed 71/71 click probes labeled
"responsive" because a step-counter at (63,63) incremented on every
action, producing a 1-pixel change. That mass-tagged cells as
"palettes" (67 of them) and drowned out the 2 truly-meaningful
clicks ((36,4) and (37,4) with diff=94 at centroid (32,25) — the
actual game button).

After HUD masking: CD82 responsive clicks correctly drop to 2/71,
palette count 67 → 0, the real interaction points surface.

**Bench result** (40 envs, 4236 s): 20 raw levels, 14/40 cleared,
100 % `adaptive_bfs_solver`. **Identical to R11** per-env.

HUD masking cleaned up entity-detection false positives but didn't
change plan outcomes. This confirms the round-11 diagnosis: the
bottleneck is the plan execution layer, not observation quality.
Plans clear movement/navigation games at brittle parity but fail
on click-heavy classes (toggle / merge / paint / push) because
the plan algorithms themselves aren't game-semantic-aware enough.

**Round 13+ direction**: deep per-game-class plan work. Broad
architectural improvements have now saturated; remaining lift
requires understanding what specifically each failing class
(FT09 lights-out, SU15 merge, CD82 paint, SB26 sort, KA59/WA30
sokoban) needs and implementing that inside the corresponding
plan fn. Each is a narrow research-and-implement cycle, not a
sweeping change.

## Prohibited Patterns (Wiki-First Routing enforcement)

The routing decision — which strategy runs as primary and what lands in
`fallback_stack` — is owned by the LLM reasoning over `.wiki/` + frame
observations. Python is NOT a second router. Rounds 2-3 added
`_augment_with_title_match` / `_augment_click_only_rule4` /
`_augment_hybrid_rule3` that mutated `Hypothesis` after the whitelist
filter. Those were **rolled back in round 4** because:

1. They were hardcoding to the 25 preview games (title-based) and to
   fixed probe signatures — neither transfers to the Kaggle private test.
2. They made the bench score rise without the LLM actually learning —
   metric gaming.
3. They grew by one rule per round, implying an unbounded trajectory.

**Banned now, by name and by shape**:

- No function reading `DiscoveryReport.game_title` and writing
  `Hypothesis.primary_strategy` or `Hypothesis.fallback_stack`. Titles
  are Kaggle-invisible.
- No function reading `DiscoveryReport.probe_diffs` /
  `available_actions` / `click_responsive_cells` / `dir_map` /
  `change_topology` and using them to decide strategy names. That
  decision belongs in the LLM.
- Banned name patterns in `src/admorphiq/hypothesis/wiki_agent.py`:
  `_augment_*`, `_inject_*`, `_reinforce_*`, `_override_*`,
  `_post_process_strategy_*`, `_seed_strategy_*`. Renaming does not
  make the rule OK — the shape is what is banned, not the string.

**Permitted**:

- JSON Schema `enum` + `uniqueItems` on `primary_strategy` and
  `fallback_stack.items` (decoder-level, shapes the output space only).
- `_validate_whitelist` — drops invented names; never inserts,
  reorders, or substitutes.
- Everything else in `wiki_agent.py` that does NOT read frame signals
  to pick strategies (prompt building, retrieval, schema construction,
  trace serialization).

**When the LLM picks wrong**:

1. Edit `.wiki/wiki/selector.md` — add a table row or refine an existing
   one so the observable signal → strategy mapping is explicit.
2. Edit `.wiki/wiki/reasoning/frame_to_strategy_chain.md` — write the
   prose "if you observe X then the right pick is Y because Z" chain.
   8B models need the *why*.
3. Edit the relevant `concepts/*.md` — if the discriminator relies on a
   concept not yet named (e.g., "probe-asymmetry"), define it first.
4. Re-bench. Do NOT patch Python.

**Enforcement (three layers)**:

- `tests/test_classify_contract.py` — semantic contract test. Passing
  means classify() is title-blind and probe-blind at the Python layer.
- `.claude/hooks/guard_wiki_agent.sh` — PreToolUse hook that prints a
  reminder when `wiki_agent.py` is being edited.
- `.claude/hooks/run_contract_tests.sh` — Stop hook that blocks
  response completion when the contract test is red.

If a future task needs behavior that looks like it must go in Python,
first prove the wiki route is insufficient by: (a) writing the wiki
page, (b) re-benching, (c) showing in a trace that Qwen still cannot
learn the rule from the wiki alone. Only then discuss a Python
exception — and it will require updating architecture.md first.

## Measurement Discipline (dev-time rounds — enforced 2026-07-01)

**Timestamp every output.** Every status report, round SUMMARY, progress.txt
entry, and record carries an absolute timestamp (`date '+%Y-%m-%d %H:%M:%S %Z'`).
Before claiming a result "just ran", CHECK the clock and compare to the file's
mtime. When waiting, report current time + elapsed since the run started. Stale-vs-fresh
confusion is a timestamp failure.

**Measurements run as background shells, never inside agents.** Agents write CODE
only; measurement runs as a `run_in_background` shell. Online-RL measurement inside
an agent burns its session tokens and it dies mid-run; manual `setsid nohup` is torn
down by the Bash sandbox. The harness-managed `run_in_background` survives session
rate-limits (rate-limit blocks only LLM turns, not the running process) — so the
measurement keeps going even when I can't respond.

**One LIVE SUMMARY per round.** Fixed convention: `scripts/rounds/RN/run.sh` →
`scripts/rounds/RN/SUMMARY.txt` (+ `games/*.json`, `run.log`). SUMMARY.txt is
regenerated LIVE after every run via `scripts/rounds/aggregate.py` — always readable
mid-run, valid partial on crash. On completion OR crash the answer is ALWAYS
SUMMARY.txt; never grep agent transcripts. Parallelize games (PAR=3 locally; the
per-step online CNN training is the bottleneck, uniform ~530s/game @3000, so Kaggle's
GPU would speed training).

**Never discard partial results; analyze and advance.** If a run dies at 27/42, do
NOT re-run the completed ones and do NOT restart the whole round. Aggregate what
exists, ANALYZE it (not merely archive), conclude if signal is sufficient, and launch
the NEXT round applying that finding — in parallel. Keep rounds running continuously
until the user intervenes. Don't be hasty: reckless kill/restart wasted hours.

## Implementation Discipline (applies to every change)

**No speculative safety nets.** Do not add hardcoded constants, fallback
branches, or placeholder returns unless the task explicitly requires them.
If you find yourself typing `if x is None: return default` as a "just in
case," stop and verify whether `x` can actually be `None` at runtime — if
not, the branch is dead weight and obscures the real contract. Do not
invent scenarios the task did not ask for (negative budgets, missing
fields, partial configs). Trust internal callers. Validate only at genuine
system boundaries (user input, external APIs, file reads).

**No backward-compatibility shims by reflex.** Do not keep old argument
shapes, aliased names, or deprecation wrappers unless an external caller
actually depends on the old form. In a single-commit refactor, rename
together and move on.

**No placeholders.** `TODO`, `FIXME`, `# implement later`, and returning
`None`/`{}`/`""` from a half-written function are anti-patterns in this
repo. If a task isn't complete, the code isn't written yet — write it or
don't commit it. There is no "stub now, finish later" mode.

**Test code is proof of intent.** Every new test MUST carry a top-of-
function docstring stating:
  1. **Purpose** — what decision, invariant, or contract this test proves.
  2. **Expected feedback** — what its pass or fail outcome signals to the
     reader. A maintainer should understand the significance without
     reading the test body.

**Feedback-gated tests are deletable.** Tests that exist solely to validate
a one-off design decision (e.g., "does Qwen 8B still hallucinate
`seq_search`?") MUST be marked with a single-line `# FEEDBACK-GATED:`
comment directly above the test function. Once the feedback has been
collected and the decision is locked in, these tests ARE deleted — keeping
them around "just in case" is cruft that hides signal. Durable contract
tests (invariants, API guarantees, regression pins, schema validation)
are never marked and never deleted.

**When in doubt, prefer deletion over retention.** A clean test suite that
protects only durable contracts is worth more than a bloated suite that
protects every past experiment.

## Current Status (2026-04-20, Round 1 Regression Verified)

**Verified Score** (2026-04-20 re-run, `scripts/ensemble_results.json`):
- **v1 primary versions only (legacy 25-game metric)**: **23/25 games, 67/182 levels (~36.81%)**
- **All envs served by API (v1 + v2 hashes, 40 total)**: **31/40 envs, 79/289 levels (~27.34%)**

**Commit-claim verification**:
- ✅ **TN36 7/7** (5e8562a) — verified on v1
- ✅ **SU15 9/9** (b84839e) — verified on v1
- ✅ **KA59 4/7** (b84839e) — verified on v1
- ❌ **"25/25 games"** claim — actually 23/25 (LF52, SK48 still failed, no fix in any commit)

**Still failing in v1**:
- LF52 0/10 — silent regression from earlier clears (historical commit b1cbc91 had LF52 working)
- SK48 0/8 — silent regression from earlier clears (063a136 added SK48)

### 🔴 NEW: v2 Game-Hash Versions Expose Hardcoding Brittleness
The ARC Prize API now serves **12 games with 2 version hashes each** (25 base + 15 duplicates = 40 envs). v2 hashes likely preview the private-test-set style obfuscation — **hardcoded solvers tuned to v1 internals fail on v2**:

| Game | v1 result | v2 result | Failure cause (hypothesis) |
|------|-----------|-----------|---------------------------|
| SU15 | 9/9 ✅ | **0/9 ❌** | `game.hmeulfxgy/peiiyyzum/rqdsgrklq` var names differ |
| TN36 | 7/7 ✅ | **0/7 ❌** | `frame.zpzcmabenn` method name differs |
| RE86 | 6/8 ✅ | **0/8 ❌** | `vzuwsebntu/vfaeucgcyr/ozhohpbjxz` sprite tags differ |
| KA59 | 4/7 ✅ | **0/7 ❌** | hardcoded L1-L4 push sequences invalid |
| S5I5 | 1/8 ✅ | **0/8 ❌** | `myzmclysbl/zylvdxoiuq` sprite tags differ |
| CN04 | 1/5 ✅ | **0/6 ❌** | `zig3_A2A4` tuning doesn't transfer |
| SK48 | 0/8 ❌ | 0/8 ❌ | never cleared |

v2 passes (solvers robust enough):
- AR25, DC22, M0R0, R11L, SC25, SP80, TU93, VC33 — mostly generic strategies (bfs_state_space, seq_repeat, click_rare, spell_cast) = **frame-observation-based strategies generalize; game-internal-access strategies don't**

**Implication**: v2 is an effective proxy for private-test-set behavior. Phase 8 (frame-only solvers + LLM hypothesis engine) is no longer theoretical — the 9.47% score gap between v1 (36.81%) and v1+v2 (27.34%) quantifies the hardcoding debt today.

### Per-Strategy Results (verified regression)

| Strategy | Cleared Games | Notes |
|----------|--------------|-------|
| Ensemble (60+ strategies) | 22/25 in regression | Primary engine; LF52/SK48/TN36 failed in latest run |
| Diff | AR25, CN04, FT09, KA59, LP85, LS20, S5I5, SP80, R11L, VC33 (10, historical) | Strong on click/state-toggle games |
| Graph | M0R0, CN04, LP85, LS20 (4, historical) | BFS state-graph traversal |
| CNN | LP85, AR25, R11L, SP80 (4, historical) | Hierarchical sampling baseline |

### Verified Per-Game Depth (from 2026-04-10 regression)

| Game | Verified | Claimed (post-test commits) | Strategy | Internal Access |
|------|----------|----------------------------|----------|----------------|
| SB26 | 8/8 | — | strat_sb26_sort | ✅ portal/slot internals |
| SU15 | 7/9 | **9/9** (b84839e) | strat_su15_vacuum | ✅ `hmeulfxgy/peiiyyzum/rqdsgrklq` |
| RE86 | 6/8 | — | strat_re86_analytical | ✅ sprite tags |
| FT09 | 6/6 | — | strat_lights_out | ✅ `Hkx/NTi/bsT/ZkU` |
| CD82 | 6/6 | — | strat_paint_game | ✅ hardcoded positions |
| TU93 | 2/9 | — | tu93_maze | ✅ hardcoded L1/L2 |
| AR25 | 2/8 | — | bfs_state_space | — |
| M0R0 | 2/6 | — | bfs_state_space | — |
| SC25 | 2/6 | — | spell_cast | — |
| KA59 | 2/7 | **4/7** (b84839e) | strat_ka59_sokoban | ✅ hardcoded L1-L4 |
| WA30 | 2/9 | — | strat_wa30_analytical | ✅ sprite tags |
| CN04 | 1/5 | — | zig3_A2A4 | — |
| TR87 | 1/6 | — | tr87_rotation | ✅ hardcoded L1 |
| LP85 | 1/8 | — | click_rare | — |
| DC22 | 1/6 | — | bfs_state_space | — |
| SP80 | 1/6 | — | bfs_state_space | — |
| G50T | 1/7 | — | explore_interact | — |
| BP35 | 1/9 | — | bp35_platformer | — |
| S5I5 | 1/8 | — | strat_s5i5_slider | ✅ sprite tags |
| R11L | 1/6 | — | seq_search | — |
| VC33 | 1/7 | — | click_rare | — |
| LS20 | 1/7 | — | ls20_grid | ✅ hardcoded L1 |
| **LF52** | **0/10** | — | — | ❌ regression from earlier clear |
| **SK48** | **0/8** | — | — | ❌ regression from earlier clear |
| **TN36** | **0/7** | **7/7** (5e8562a) | strat_tn36_puzzle | ✅ `frame.zpzcmabenn` |

### Active TODO per Team

**Phase 8 Cleanup Team (highest priority)**:
- Remove all game-internal access from analytical solvers (see Hardcoding Debt below)
- Replace with frame-only object detection (color clustering, diff analysis)
- Replace hardcoded level solutions with online BFS/search

**LLM Integration Team (Phase 8)**:
- **First: Task #11 benchmark** — evaluate Qwen 3 8B / Gemma 4 26B MoE 4bit / Gemma 4 E4B 4bit on Wiki zero-shot classification + strategy selection. No implementation work until benchmark decides.
- Build hypothesis prompt template (frame description → rule guess → action plan) — model-agnostic, lives in `.wiki/wiki/selector.md`
- Pre-download winner + fallback weights to Kaggle dataset (no internet at inference time)
- LoRA training pipeline — ONLY if zero-shot benchmark reveals need AND winning model has mature LoRA tooling

**CNN Team (lower priority)**:
- LP85 only consistent clear — analyze what makes it solvable vs other games
- May be deprecated if LLM hypothesis engine subsumes its role

**Ensemble Team**:
- Push level depth on partially-cleared games (RE86, KA59, AR25, etc.) via better generic strategies
- Avoid adding new game-internal-access solvers (Phase 8 debt)

**Graph Team**:
- State expansion working (1000+ states after fix)
- Better ACTION6 coordinate exploration (16x16 → 32x32 grid)
- State hash downsampling (64x64 → 16x16)

**Diff Team**:
- Strongest single strategy (10 games)
- Improve movement game strategies (BFS + wall mapping)
- Click games need pattern recognition (click order)

### Game-Strategy Mapping (for final submission)
Each game should use its best-performing strategy. Build a meta-agent that:
1. Classifies game type in first 20 actions (discovery phase)
2. Selects optimal strategy based on classification
3. Falls back to other strategies if primary fails
4. **Phase 8**: invoke LLM Hypothesis Engine when frame-only solvers stall

## ⚠️ CRITICAL: Game-Specific Hardcoding Debt (Phase 8 must fix)

Many high-scoring strategies currently depend on **game-internal access** that won't work on new games.

**Problem**: Analytical solvers read game source code internals (obfuscated variable names, sprite tags, internal state, hardcoded level solutions). These are specific to the 25 preview games and will NOT generalize to private test games.

### Affected strategies and their hardcoded dependencies

| Strategy | Game (cleared) | Dependency type | Specific hooks |
|----------|---------------|-----------------|----------------|
| `strat_lights_out` | FT09 6/6 | Sprite tags | `Hkx`, `NTi`, `bsT`, `ZkU` |
| `strat_paint_game` | CD82 6/6 | Hardcoded positions | `pqkenviek`, `ctwspzkygu` sprite x/y per level |
| `strat_sb26_sort` | SB26 8/8 | Game internals | portal/slot internal state |
| `strat_su15_vacuum` | SU15 9/9 | Game internals | `game.hmeulfxgy` (fruits), `game.peiiyyzum` (enemies), `game.rqdsgrklq` (goals) |
| `strat_tn36_puzzle` | TN36 7/7 | Direct internal call | `frame.zpzcmabenn(val)` to set bit-encoded program |
| `strat_re86_analytical` | RE86 6/8 | Sprite tags | `vzuwsebntu`, `vfaeucgcyr`, `ozhohpbjxz` |
| `strat_wa30_analytical` | WA30 2/9 | Sprite tags | `wbmdvjhthc`, `wyzquhjerd`, `pkbufziase` |
| `strat_s5i5_slider` | S5I5 1/8 | Sprite tags | `myzmclysbl` rotate buttons, `zylvdxoiuq` goals |
| `strat_ka59_sokoban` | KA59 4/7 | Hardcoded level solutions | per-level push sequences |
| `strat_tu93_maze` | TU93 2/9 | Hardcoded L1/L2 | move sequences |
| `strat_tr87_rotation` | TR87 1/6 | Hardcoded L1 | rotation values |
| `strat_ls20_grid` | LS20 ≥1 | Hardcoded L1 | move sequence |

**Estimated impact**: ~25-30% of current 37.9% score depends on these hooks. Conservative Phase 8 floor target: 21/25 games still cleared after refactoring (~22-25% score), then LLM hypothesis engine recovers/exceeds.

### Phase 8 Refactoring Plan
1. Each analytical solver must be converted to work through **official API only** (frame observation + actions)
2. Replace sprite tag reads with **frame-based object detection** (color clustering, connected components, diff analysis)
3. Replace hardcoded solutions with **online BFS/search** from frame state
4. Maintain a **discovery phase** where the agent learns game mechanics from first ~20 actions
5. Integrate **LLM Hypothesis Engine** (winner of Task #11 benchmark — Qwen 3 8B / Gemma 4 26B MoE / Gemma 4 E4B) to propose rule hypotheses from frame observations when search stalls
6. **Validation**: after refactoring, verify ≥21/25 games still cleared via 25-game regression test
7. Stretch goal: LLM-driven solvers exceed pre-refactor analytical scores

**Current approach is valid for**:
- Understanding game mechanics (research value — feeds LLM training data)
- Setting upper-bound performance targets (37.9% with internals = ceiling for frame-only attempts)
- Generating supervised solution traces for LoRA fine-tuning
