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

| Constraint | Limit |
|-----------|-------|
| CPU notebook | ≤ 6 hours runtime |
| GPU notebook | ≤ 6 hours runtime (T4 16GB VRAM) |
| Internet | **Disabled** (no external API calls) |
| External data | Freely available public data + pre-trained models OK |
| Submission | 1 per day |
| Open source | Required for prize eligibility |

**Key implication**: No Claude/GPT API calls. Must use offline models (quantized open-source LLMs on Kaggle GPU). Claude Code is dev-time only — final notebook ships with pre-downloaded open-weight model (candidate set under evaluation; see [LLM Selection](#llm-selection-phase-8-hypothesis-engine)).

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

### Phase 7: Multi-Level + Score Optimization 🔄 In Progress (Round 1 verified 2026-04-20)
- **v1 primary versions**: 23/25 games, 67/182 levels (36.81%)
- **v1 + v2 (40 envs served by API)**: 31/40 envs, 79/289 levels (27.34%)
- ✅ TN36 7/7, SU15 9/9, KA59 4/7 commit claims verified on v1
- ❌ LF52, SK48 still fail (silent regressions, not fixed)
- 🔴 **v2 hash versions collapse all internals-based solvers** — preview of private-test-set behavior
- Five verified perfect games on v1: CD82 6/6, FT09 6/6, SB26 8/8, SU15 9/9, TN36 7/7
- StochasticGoose baseline (12.58%) surpassed by +24% on v1 / +15% on full 40-env set
- **Remaining Phase 7 work**:
  - Fix LF52/SK48 regressions (git bisect to find breaking commit)
  - DO NOT add v2-version hardcoding — that's anti-generalization, waste of effort
  - Instead move to Phase 8 (frame-only solvers close the v1→v2 gap)

### Phase 8: Generalization + Kaggle Submission 🔄 ACTIVE (Karpathy LLM-Wiki pattern)

**Architecture decision (2026-04-20)**: Adopt [Karpathy's LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) — markdown knowledge base maintained by LLM at dev-time, read by inference LLM at Kaggle-time. No vector DB (incompatible with Kaggle internet constraint).

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

**Phase 8 TODO (Karpathy-Wiki-driven plan)**:

**Step 1 — Wiki seed (dev-time, Claude Code)**
- [x] 1a: Scaffold `.wiki/` directory structure (raw/, wiki/games/, wiki/game_types/, wiki/strategies/, schema.md, index.md)
- [x] 1b: Seed `raw/traces/<game>.jsonl` for all 25 games (distilled from regression) + `raw/regressions/v2_failures_20260420.md` analysis
- [x] 1c: Write first 3 game wiki pages (TN36, SU15, AR25) as rich templates — brittle vs frame-only contrast
- [x] 1d-skeleton: Generate skeleton wiki pages for remaining 22 games via `scripts/generate_wiki_game_pages.py`
- [x] 1d-expand: Fill Observations + Mechanics Hypothesis + Refactor Plan for 22 skeletons via `scripts/enrich_wiki_game_pages.py` (curated `GAME_KNOWLEDGE`)
- [x] 1e: 13 game_type pages written (click, merge_puzzle, sokoban, platformer, transform, delivery, slider_puzzle, rotation, sort_puzzle, spell_cast, sequence, hybrid, unknown) in addition to movement + programming_puzzle
- [x] 1f: `.wiki/wiki/index.md` auto-regeneration via `scripts/generate_wiki_index.py` (43 pages indexed)
- [x] 1g: Knowledge-graph layer written — `concepts/` (7), `lessons/` (6), `debug/` (3), `reasoning/` (4)
- [x] 1h: `raw/commits.md` compiled as narrative history for LLM reasoning
- [x] 1i: 25 game pages retrofit with `Lessons Learned` + `Related Concepts` + `Peer Games` cross-links
- [ ] 1j: Expand `strategies/frame_only/` pages (`click_rare`, `seq_search`, `spell_cast`, `explore_interact`) beyond current `bfs_state_space`

**Step 1 status: ~90% complete (65 pages, 70 MD files, 416KB total — well under the 10MB budget).**

**Step 2 — Frame-only solver refactoring (parallel to Step 1)**
- [~] 2a: TN36 — `strat_tn36_frame_only` probing fallback added; does not yet score on v2 because the mechanic requires bit-panel detection + BFS planning. Follow-up task filed for full implementation (see `.wiki/wiki/games/TN36.md` findings section).
- [ ] 2b: Refactor SU15 solver — replace `hmeulfxgy/peiiyyzum/rqdsgrklq` with color-cluster fruit/enemy/goal detection
- [ ] 2c: Refactor RE86 solver — replace sprite-tag reads with diff-based movable/target detection
- [ ] 2d: Refactor KA59/S5I5/CN04 with same principle
- [ ] 2e: Regression gate after each refactor — v1 ≥ previous, v2 > 0

**Step 3 — LLM + Wiki inference pipeline (Kaggle side, model selected by empirical bench)**
- [x] **3-pre: Benchmark harness built & portable** — `configs/llm.yaml` + `configs/llm_bench_tasks.yaml` + `src/admorphiq/llm/registry.py` + `src/admorphiq/llm/ollama_backend.py` + `scripts/bench_llm.py`. Framework is intentionally **environment-free** (no `Arcade` / `GameAction` imports at bench time) so it can run on any box with an LLM backend: Kaggle, Colab, local, CI. See [[../.wiki/wiki/reasoning/benchmark_protocol.md]] and `memory/feedback_preserve_framework.md`.
- [x] **3-pre-cold-prompt baseline (Qwen 3 8B, local 2026-04-21)**:
  - thinking mode ON: classification 24% / strategy 32% / latency 12.4s/call (thinking tokens exhausted num_predict → empty `response` on 13/25 prompts).
  - `/no_think` + `think: false`: classification 32% / strategy 40% / latency 1.75s/call (7× faster, parse 100%).
  - The 32%/40% is a **cold-prompt ceiling** — bench deliberately gives no live frame data; the model must classify from the game title and generic wiki alone. Useful for apples-to-apples model comparison, NOT for deployment accuracy prediction.
- [ ] **3-pre-live-env driver (SEPARATE script, not yet written)** — build `scripts/bench_llm_with_live_env.py` that imports the framework and prepends real `FrameData` observations (reset + ACTION1..4 diff probes + dominant colors) to the prompt. This reproduces the actual deployment scenario and gives a realistic accuracy number. Do not modify the portable framework.
- [ ] 3-pre-run-ceiling-reference (optional): on 24GB+ hardware, run Gemma 4 26B MoE (local-only, does not ship to Kaggle) as an upper-bound reference.
- [ ] 3-pre-run-reserve: if 8B cold-prompt + live-env numbers are insufficient, `ollama pull qwen3:14b` and re-run on same bench.
  - **Selection rule**: pick model with best accuracy × 1/latency product; don't pre-commit to any
- [ ] 3a: `scripts/run_wiki_agent.py` — load selected LLM 4bit + `.wiki/` at startup
- [ ] 3b: Game classifier: first 10-20 actions → game_type label
- [ ] 3c: Wiki retrieval: select `wiki/game_types/<type>.md` + top-3 similar `wiki/games/*.md`
- [ ] 3d: Zero-shot strategy selection + rule hypothesis
- [ ] 3e: Compare vs current ensemble — target: match v1 score, recover v2 score

**Step 4 — Independent cleanup (parallel)**
- [ ] 4a: LF52/SK48 regression bisect (separate line, not blocked on Wiki)
- [ ] 4b: Offline LoRA tuning on v1 traces — ONLY if Step 3d zero-shot falls short, **and only if selected model has mature LoRA tooling** (favors Qwen 3 8B for this fallback)

**Validation gates**:
- Gate A (after Step 2): v2-hash envs improve from 9→≥18 cleared
- Gate B (after Step 3): zero-shot wiki agent clears ≥21/25 unique games on both v1 and v2
- Gate C (Kaggle packaging): runtime ≤ 6h, memory ≤ 16GB, fully offline

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
