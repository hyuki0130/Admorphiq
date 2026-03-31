# Admorphiq

**Adaptive Morphing Intelligence** — an AI agent for the [ARC Prize 2026 (ARC-AGI-3)](https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-3) competition.

ARC-AGI-3 is the first interactive reasoning benchmark. Agents must explore unfamiliar game environments, discover rules through trial and error, and adapt in real-time. This requires genuine fluid intelligence: exploration, hypothesis generation, planning, and learning from sparse feedback.

## Status

**Phase 1: Environment Understanding** -- Complete

- Project scaffolding with uv, PyTorch, ruff, pytest
- Official framework ([ARC-AGI-3-Agents](https://github.com/arcprize/ARC-AGI-3-Agents)) analysis complete
- Reference solution ([DriesSmit/ARC3-solution](https://github.com/DriesSmit/ARC3-solution)) analysis complete

**Phase 2: Baseline Agent** -- Complete

- CNN perception backbone (16→32→64→128→256 channels, dual head, 34M params)
- Experience buffer with hash-based deduplication (200K capacity)
- AdmorphiqAgent with hierarchical action sampling and entropy regularization
- Type abstractions for arcengine compatibility (GameState, ActionType, FrameData)
- 41 tests passing (types 8, perception 11, buffer 10, agent 12)

**Phase 2.5: SDK Integration + Live Testing** -- Complete

- arcengine 0.9.3 + arc-agi 0.9.6 integration
- AdmorphiqAdapter: official Agent <-> internal Agent bridge
- Frame conversion: multi-layer variable color index -> 16ch one-hot
- Local game runner (`scripts/run_local.py`)
- Live tested on 3 games (DC22, LF52, BP35) -- 0 levels cleared, bottleneck identified

**Phase 3: World Model** -- Complete

- World Model (1.6M params): StateEncoder + ActionEmbedding + TransitionPredictor (residual delta) + ChangePredictor
- Agent integration: combined score = alpha * perception + (1-alpha) * world_model (alpha=0.5)
- Experience buffer extended with next_frame storage and sample_with_next()
- 69 tests passing (41 existing + 28 new world model tests)

**Phase 3.5: Exploration Strategy Improvement** -- Failed

- Reward shaping, SystematicExplorer, GameMemory, MAX_ACTIONS=500
- Still 0 levels cleared -- change prediction approach has fundamental limits
- **Next: architectural redesign needed**

## Project Structure

```
admorphiq/
├── src/admorphiq/
│   ├── agent.py            # AdmorphiqAgent (is_done + choose_action)
│   ├── types.py            # GameState, ActionType, GameAction, FrameData
│   ├── perception/
│   │   ├── cnn.py          # CNN backbone (4-layer, 34M params)
│   │   └── model.py        # PerceptionModel (dual head: action + coord)
│   ├── world_model/
│   │   ├── encoder.py      # StateEncoder (CNN-based state embedding)
│   │   ├── transition.py   # TransitionPredictor + ChangePredictor
│   │   └── model.py        # WorldModel (1.6M params, residual delta)
│   ├── hypothesis/         # Rule inference engine (Phase 4)
│   ├── planner/            # Action planning & exploration (Phase 4)
│   └── utils/
│       └── buffer.py       # ExperienceBuffer (hash dedup, 200K cap)
├── tests/                  # 69 tests (types, perception, buffer, agent, world model)
├── configs/                # Configuration files
├── notebooks/              # Experiment notebooks
├── scripts/
│   └── run_local.py        # Local game runner (arcengine integration)
├── pyproject.toml
└── CLAUDE.md               # Architecture & competition context
```

## Installation

```bash
# Requires Python 3.12+ and uv
uv sync
```

## Usage

```bash
# Run agent on a local game
python scripts/run_local.py
```

```python
from admorphiq.agent import AdmorphiqAgent

agent = AdmorphiqAgent()
# Agent implements is_done() and choose_action(frame_data)
# Compatible with the ARC-AGI-3-Agents framework via AdmorphiqAdapter
```

## Architecture

```
Perception Layer  →  World Model  →  Hypothesis Engine  →  Action Planner
(CNN encoder)        (dynamics)      (rule inference)      (explore/exploit)
```

See [CLAUDE.md](CLAUDE.md) for detailed architecture design and competition context.

## License

MIT
