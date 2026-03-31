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
├── agent.py            # AdmorphiqAgent (is_done + choose_action)
├── types.py            # GameState, ActionType, GameAction, FrameData
├── perception/
│   ├── cnn.py          # CNN backbone (4-layer, 34M params)
│   └── model.py        # PerceptionModel (dual head: action + coord)
├── world_model/
│   ├── encoder.py      # StateEncoder (CNN-based state embedding)
│   ├── transition.py   # TransitionPredictor + ChangePredictor
│   └── model.py        # WorldModel (1.6M params, residual delta)
├── hypothesis/         # Rule inference engine (Phase 4)
├── planner/            # Action planning & exploration (Phase 4)
└── utils/
    └── buffer.py       # ExperienceBuffer (hash dedup, 200K cap, next_frame)
tests/                  # 69 tests (types, perception, buffer, agent, world model)
configs/                # Configuration files
notebooks/              # Experiment notebooks
scripts/
└── run_local.py        # Local game runner (arcengine integration)
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

### Phase 4: Hypothesis Engine
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

### Lessons Learned
- **Frame structure mismatch**: Actual frames are multi-layer with variable layer count and int8 color indices, not fixed 16ch one-hot as initially assumed
- **Training bottleneck**: 440ms per action spent on training, only 8ms on inference -- training dominates runtime
- **Kaggle time budget is sufficient**: 6 hours allows 43K+ actions at current speed
- **Early diversity improved**: Action variety went from 1-2 types to 3-5 types, ACTION6 coordinate exploration realized
- **Change prediction has fundamental limits**: CNN converges to ACTION6-only preference, 500 actions still 0 levels cleared
- **Architectural redesign needed**: "Predict which action causes change" is insufficient for goal-directed behavior -- need higher-level reasoning about game rules and objectives

## What Doesn't Work

- Direct LLM prompting alone (<5% on ARC-AGI)
- Pure memorization / pattern matching (tasks are novel by design)
- Ensembling existing solutions (doesn't generalize to private test set)
- Brute force search without heuristics (search space too large)
- **Change prediction as sole strategy** (tested Phase 2.5-3.5): CNN learns to predict which actions cause state changes, but converges to ACTION6-only preference without understanding game goals. 500 actions across 3 games, 0 levels cleared.
