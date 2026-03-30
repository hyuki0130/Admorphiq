# Admorphiq

**Adaptive Morphing Intelligence** — an AI agent for the [ARC Prize 2026 (ARC-AGI-3)](https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-3) competition.

ARC-AGI-3 is the first interactive reasoning benchmark. Agents must explore unfamiliar game environments, discover rules through trial and error, and adapt in real-time. This requires genuine fluid intelligence: exploration, hypothesis generation, planning, and learning from sparse feedback.

## Status

**Phase 1: Environment Understanding** -- Complete

- Project scaffolding with uv, PyTorch, ruff, pytest
- Official framework ([ARC-AGI-3-Agents](https://github.com/arcprize/ARC-AGI-3-Agents)) analysis complete
- Reference solution ([DriesSmit/ARC3-solution](https://github.com/DriesSmit/ARC3-solution)) analysis complete

**Phase 2: Baseline Agent** -- Next

## Project Structure

```
admorphiq/
├── src/admorphiq/
│   ├── agent.py            # Agent entry point
│   ├── perception/         # Frame encoding (CNN)
│   ├── world_model/        # State transition prediction
│   ├── hypothesis/         # Rule inference engine
│   ├── planner/            # Action planning & exploration
│   └── utils/              # Shared utilities
├── tests/                  # pytest test suite
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

> Coming soon -- a runnable agent will be available after Phase 2.

## Architecture

```
Perception Layer  →  World Model  →  Hypothesis Engine  →  Action Planner
(CNN encoder)        (dynamics)      (rule inference)      (explore/exploit)
```

See [CLAUDE.md](CLAUDE.md) for detailed architecture design and competition context.

## License

MIT
