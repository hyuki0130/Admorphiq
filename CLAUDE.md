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

**Perception Layer**
- Input: 16-channel one-hot encoded 64x64 frames
- CNN backbone (4-layer, 32→64→128→256 channels)
- Dual head: action probability + coordinate prediction (for ACTION6)

**World Model**
- Predict next state given (current_state, action)
- Experience buffer (~200K unique state-action pairs)
- Hash-based deduplication for sample efficiency
- Dynamic reset on level completion

**Hypothesis Engine**
- Option A: Quantized open-source LLM (Llama/Qwen ~8B with LoRA)
- Option B: Program synthesis — generate candidate rule programs
- Option C: Neurosymbolic — neural intuition + symbolic rule extraction

**Action Planner**
- Change prediction bias: prefer actions likely to cause state changes
- Hierarchical sampling: action type first, then coordinates if ACTION6
- Entropy regularization to encourage exploration

## Game Environment

### Agent Interface
- Two required methods: `is_done()` and `choose_action(frame_data)`
- `FrameData` contains: `frame[16][64][64]` (one-hot encoded), `available_actions`, `state`, `levels_completed`
- `GameAction`: RESET=0, ACTION1-5 (simple, no coordinates), ACTION6 (complex, requires x/y), ACTION7 (simple, cancel/undo)
- `MAX_ACTIONS = 80` per game

### Scoring
- Per-game: 0~100% (100% = matching human-level performance)
- Final: average across all games
- Capped at 100% even if agent uses fewer moves than humans

## Project Structure

```
src/admorphiq/
├── agent.py            # Agent entry point
├── perception/         # Frame encoding (CNN)
├── world_model/        # State transition prediction
├── hypothesis/         # Rule inference engine
├── planner/            # Action planning & exploration
└── utils/              # Shared utilities
tests/                  # pytest test suite
configs/                # Configuration files
notebooks/              # Experiment notebooks
scripts/                # Helper scripts
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.12 |
| Framework | ARC-AGI-3-Agents (official) |
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

### Phase 2: Baseline Agent
- Random agent → rule-based agent → simple CNN agent
- Implement experience buffer and basic exploration

### Phase 3: World Model
- Train state transition predictor
- Change prediction for smarter exploration

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

## What Doesn't Work

- Direct LLM prompting alone (<5% on ARC-AGI)
- Pure memorization / pattern matching (tasks are novel by design)
- Ensembling existing solutions (doesn't generalize to private test set)
- Brute force search without heuristics (search space too large)
