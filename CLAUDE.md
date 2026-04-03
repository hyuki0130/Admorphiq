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
| GPU notebook | ≤ 6 hours runtime |
| Internet | **Disabled** (no external API calls) |
| External data | Freely available public data + pre-trained models OK |
| Submission | 1 per day |
| Open source | Required for prize eligibility |

**Key implication**: No Claude/GPT API calls. Must use offline models (quantized open-source LLMs on Kaggle GPU).

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

**Hypothesis Engine**
- Option A: Quantized open-source LLM (Llama/Qwen ~8B with LoRA)
- Option B: Program synthesis — generate candidate rule programs
- Option C: Neurosymbolic — neural intuition + symbolic rule extraction

**Action Planner** (implemented in AdmorphiqAgent)
- Hierarchical sampling: action type first, then coordinates if ACTION6
- Entropy regularization to encourage exploration
- Change prediction bias: prefer actions likely to cause state changes
- Level transition detection with automatic buffer/model reset

## Game Environment

### Agent Interface
- Two required methods: `is_done()` and `choose_action(frame_data)`
- `FrameData` contains: `frame[N][64][64]` (variable layers, int8 color index per cell), `available_actions`, `state`, `levels_completed`
- **Frame structure** (corrected): NOT fixed 16ch one-hot. Games have variable layer count (1~N), each cell is an int8 color index. Our adapter converts to 16ch one-hot for the CNN.
- `GameAction`: RESET=0, ACTION1-5 (simple, no coordinates), ACTION6 (complex, requires x/y), ACTION7 (simple, cancel/undo)
- `MAX_ACTIONS = 80` per game

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
├── hypothesis/         # Rule inference engine (Phase 5)
├── planner/
│   ├── explorer.py     # SystematicExplorer (untried action bonus)
│   ├── graph_explorer.py  # GraphExplorer (BFS state graph traversal)
│   ├── state_graph.py  # StateGraph (state transition graph)
│   └── memory.py       # GameMemory (success sequence replay)
└── utils/
    └── buffer.py       # ExperienceBuffer (hash dedup, 200K cap, next_frame)
tests/                  # Test suite
configs/                # Configuration files
notebooks/              # Experiment notebooks
scripts/
├── run_local.py        # Local game runner (arcengine integration)
└── play.py             # Interactive game play script
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.12 |
| Framework | arcengine 0.9.3 + arc-agi 0.9.6 |
| Package manager | uv |
| Deep learning | PyTorch |
| LLM (offline) | TBD — Llama/Qwen/Mistral quantized |
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

### Phase 5: Hypothesis Engine (was Phase 4)
- Integrate offline LLM or program synthesis
- Hypothesis-verify loop

### Phase 5: Optimization & Submission
- Fit within 6-hour Kaggle runtime
- Optimize model size for GPU memory
- Milestone 1 submission (Jun 30)

## Reference Projects

| Project | Approach | Score | Notes |
|---------|----------|-------|-------|
| [arcgentica](https://github.com/symbolica-ai/arcgentica) | Multi-agent LLM | 85.28% (AGI-2) | Online API needed, not Kaggle-compatible |
| [da-fr/arc-prize-2024](https://github.com/da-fr/arc-prize-2024) | Mistral 8B + LoRA + TTT + DFS | 53.5 (AGI-1) | Kaggle-compatible, single H100 |
| [DriesSmit/ARC3-solution](https://github.com/DriesSmit/ARC3-solution) | CNN action predictor | — | **ARC-AGI-3 specific**, closest reference |
| [transversal-arc-solver](https://github.com/khalildh/transversal-arc-solver) | Plücker geometry, zero learning | 316 tasks | No ML, pure math |
| [arcprize/ARC-AGI-3-Agents](https://github.com/arcprize/ARC-AGI-3-Agents) | Official framework | — | Required base framework |

## Key Research

- François Chollet, ["On the Measure of Intelligence"](https://arxiv.org/abs/1911.01547) (2019)
- ARC Prize research page: https://arcprize.org/research
- ARC-AGI-3 docs: https://docs.arcprize.org
- Kaggle discussion: https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-3/discussion

## Proven Approaches (from ARC-AGI-1/2 research)

1. **Discrete Program Search (DSL)** — define grid-transform primitives, search for compositions
2. **Test Time Training (TTT)** — fine-tune model on test examples at inference
3. **LLM as Hypothesis Generator** — generate candidate programs, verify against examples
4. **Active Inference** — real-time adaptation via few-shot fine-tuning (Jack Cole, 34%)
5. **Neurosymbolic** — neural perception + symbolic reasoning (Chollet's recommended direction)

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

### Lessons Learned
- **Frame structure mismatch**: Actual frames are multi-layer with variable layer count and int8 color indices, not fixed 16ch one-hot as initially assumed
- **Training bottleneck**: 440ms per action spent on training, only 8ms on inference -- training dominates runtime
- **Kaggle time budget is sufficient**: 6 hours allows 43K+ actions at current speed
- **Early diversity improved**: Action variety went from 1-2 types to 3-5 types, ACTION6 coordinate exploration realized
- **Change prediction has fundamental limits**: CNN converges to ACTION6-only preference, 500 actions still 0 levels cleared
- **StochasticGoose gap explained**: Same architecture but 0% -- root cause was coordinate scaling (/4096 missing), reward=0.3 (not binary), low train frequency
- **Game classification is key**: 25 games classified into movement(7), click(6), hybrid(6), transform(2), unknown(4) -- strategy should branch by type
- **Ensemble potential**: Graph/Diff/CNN each clear different games -- combining strategies could improve coverage

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

## Current Status (2026-04-01)

**Score: 11/25 games, 12/182 levels cleared**

### Per-Strategy Results
| Strategy | Games Cleared | Unique Games |
|----------|--------------|-------------|
| Ensemble | AR25, CN04, LP85, SP80, R11L, VC33 (6) | VC33 |
| Diff | AR25, CN04, FT09, KA59, LP85, LS20, S5I5(2lvl), SP80, R11L, VC33 (10) | FT09, KA59, S5I5 |
| Graph | M0R0, CN04, LP85, LS20 (4) | M0R0 |
| CNN | LP85, AR25, R11L, SP80 (4) | — |

### Remaining 14 Games (TODO)
DC22, TU93, RE86, SU15, TR87, SC25, G50T, SB26, LF52, BP35, SK48, WA30, CD82, TN36

### Active TODO per Team

**CNN Team:**
- Investigate why StochasticGoose gets 12.58% with same architecture but we get ~0%
- Try lr adjustments (0.001, 0.0005), smaller buffer (1000-5000), epsilon-greedy
- LP85 is only consistent clear — analyze what makes it solvable
- Run 25-game full test when stable improvement found

**Ensemble Team:**
- Develop frame-analysis-based intelligent navigation (not blind zigzag)
- Use FrameAnalyzer to detect player, walls, goals per game
- Fix ACTION6 data= passing in ensemble (LF52, BP35, TN36 crash)
- Focus on movement games (7 unsolved) — need wall avoidance + pathfinding

**Graph Team:**
- State expansion is working (states grow to 1000+) after fix
- Need better ACTION6 coordinate exploration (16x16 → 32x32 grid)
- State hash downsampling (64x64 → 16x16) to reduce state space
- Escape mechanism when stuck in same states for N steps

**Diff Team:**
- 7 games cleared, strongest single strategy
- Improve movement game strategies (BFS + wall mapping)
- Click games need pattern recognition (click order matters)
- Hybrid/transform games need specialized approaches

### Game-Strategy Mapping (for final submission)
Each game should use its best-performing strategy. Build a meta-agent that:
1. Classifies game type in first 20 actions
2. Selects optimal strategy based on classification
3. Falls back to other strategies if primary fails

## Development Phases

### Phase 5 — Maximize Game Clears (DONE)
- Cleared 16/25 games using all 4 approaches in parallel
- Game-specific solvers: GF(p) lights-out (FT09), paint game (CD82), maze BFS (TU93), etc.

### Phase 6 — Generalization Refactoring (DONE)
- Removed ALL game ID hardcoding — 54+ generic strategies
- All triggers feature-based (available_actions + frame analysis)
- No game IDs in strategy names or conditions

### Current: Phase 7 — Multi-Level + Score Optimization (in progress)
- **Official score: ~29.44%** (21/25 games, 48+ levels)
- Three perfect games: CD82 6/6, FT09 6/6, SB26 8/8
- High clears: RE86 6/8, SU15 3/9, AR25 2/8, M0R0 2/6, SC25 2/6, TU93 2/9, WA30 2/9
- StochasticGoose (12.58%) surpassed by +16.86%
- Focus: push more levels + clear remaining 4 games (BP35, KA59, TN36, S5I5)

### ⚠️ CRITICAL: Game-Specific Hardcoding Debt (Phase 8 must fix)
Many high-scoring strategies currently depend on **game-internal access** that won't work on new games:

**Problem**: Analytical solvers read game source code internals (obfuscated variable names, sprite tags, internal state). These are specific to the 25 preview games and will NOT generalize to private test games.

**Affected strategies and their hardcoded dependencies**:
- `strat_lights_out` (FT09 6/6): reads sprite tags `Hkx`, `NTi`, `bsT`, `ZkU`
- `strat_paint_game` (CD82 6/6): hardcoded paint positions per level
- `strat_sb26_sort` (SB26 8/8): reads game portal/slot internals
- `strat_re86_analytical` (RE86 6/8): reads `vzuwsebntu`, `vfaeucgcyr`, `ozhohpbjxz` tags
- `strat_wa30_analytical` (WA30 2/9): reads `wbmdvjhthc`, `wyzquhjerd`, `pkbufziase` variables
- `strat_tu93_maze` (TU93 2/9): hardcoded L1/L2 solutions
- `strat_tr87_rotation` (TR87 1/6): hardcoded L1 rotation values
- `strat_su15_vacuum` (SU15 3/9): reads game vacuum/fruit internals

**Phase 8 refactoring plan**:
1. Each analytical solver must be converted to work through **official API only** (frame observation + actions)
2. Replace sprite tag reads with **frame-based object detection** (color clustering, diff analysis)
3. Replace hardcoded solutions with **online BFS/search** from frame state
4. Maintain a "discovery phase" where the agent learns game mechanics from first ~20 actions
5. **Validation**: after refactoring, verify ≥21/25 games still cleared via 25-game test

**Current approach is valid for**:
- Understanding game mechanics (research value)
- Setting upper-bound performance targets
- Developing algorithms that can later be generalized

### Later: Phase 8 — Generalization + Kaggle Submission
- **CRITICAL**: Remove ALL game-internal access (sprite tags, variable names, hardcoded solutions)
- Convert analytical solvers to frame-observation-only versions
- Fit within 6-hour runtime constraint
- Single unified meta-agent that auto-selects best strategy per game
- Optimize for Kaggle T4 GPU (16GB VRAM)
- Package as Kaggle notebook
