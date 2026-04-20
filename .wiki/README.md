# Admorphiq LLM Wiki

LLM-maintained markdown knowledge base for Phase 8 generalization.

- **Pattern**: [Karpathy LLM Wiki (April 2026)](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
- **Schema**: see [schema.md](./schema.md)
- **Index**: see [wiki/index.md](./wiki/index.md)

## Quick Navigation

- [`raw/`](./raw) — Immutable sources (solution traces, regression analyses)
- [`wiki/games/`](./wiki/games) — Per-game mechanics pages
- [`wiki/game_types/`](./wiki/game_types) — Category pages (movement, click, programming_puzzle, ...)
- [`wiki/strategies/frame_only/`](./wiki/strategies/frame_only) — Generalizable strategies
- [`wiki/strategies/brittle/`](./wiki/strategies/brittle) — Strategies tied to game internals (for caution/refactor)
- [`wiki/selector.md`](./wiki/selector.md) — Feature → strategy dispatch rules

## Obsidian (dev-time viewer, optional)

Open the `.wiki/` directory as an Obsidian vault to get graph view + backlinks.
No Obsidian at Kaggle inference — the selected LLM (Qwen 3 8B / Gemma 4 26B MoE / Gemma 4 E4B, decided by Task #11 benchmark) reads `.md` files directly.
