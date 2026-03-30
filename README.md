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

**Phase 3: World Model** -- Next

## Project Structure

```
admorphiq/
├── src/admorphiq/
│   ├── agent.py            # AdmorphiqAgent (is_done + choose_action)
│   ├── types.py            # GameState, ActionType, GameAction, FrameData
│   ├── perception/
│   │   ├── cnn.py          # CNN backbone (4-layer, 34M params)
│   │   └── model.py        # PerceptionModel (dual head: action + coord)
│   ├── world_model/        # State transition prediction (Phase 3)
│   ├── hypothesis/         # Rule inference engine (Phase 4)
│   ├── planner/            # Action planning & exploration (Phase 4)
│   └── utils/
│       └── buffer.py       # ExperienceBuffer (hash dedup, 200K cap)
├── tests/                  # 41 tests (types, perception, buffer, agent)
├── configs/                # Configuration files
├── notebooks/              # Experiment notebooks
├── scripts/                # Helper scripts
├── pyproject.toml
└── CLAUDE.md               # Architecture & competition context
```

## Installation

```bash
# Requires Python 3.12+ and uv
uv sync
```

## Usage

```python
from admorphiq.agent import AdmorphiqAgent

agent = AdmorphiqAgent()
# Agent implements is_done() and choose_action(frame_data)
# Compatible with the ARC-AGI-3-Agents framework
```

> Full integration with the arcengine runner will be available in Phase 3.

## Architecture

```
Perception Layer  →  World Model  →  Hypothesis Engine  →  Action Planner
(CNN encoder)        (dynamics)      (rule inference)      (explore/exploit)
```

See [CLAUDE.md](CLAUDE.md) for detailed architecture design and competition context.

## License

MIT
