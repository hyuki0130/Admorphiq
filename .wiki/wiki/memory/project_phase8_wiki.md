---
name: Phase 8 Adopts Karpathy LLM-Wiki Pattern
description: Admorphiq Phase 8 uses markdown knowledge base (no vector DB) readable by Qwen 3 8B offline on Kaggle
type: project
originSessionId: 96a72d05-e421-4801-9b30-810c293777f0
---
## Decision (2026-04-20)
Phase 8 architecture adopts [Karpathy's LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) (April 2026, viral — 16M views, 5K+ stars).

## Why
- RAG vector DBs are incompatible with Kaggle's internet-disabled inference environment
- Wiki pattern uses plain markdown + backlinks — compiles knowledge at dev-time, LLM reads `.md` files at inference
- Perfect fit for offline Qwen 3 8B Hypothesis Engine
- Round 1 regression (2026-04-20) revealed v2 hash regressions: 37% v1 collapses to 27% on v1+v2 because internals-based solvers break

## Directory Layout (`.wiki/` in repo root)
```
.wiki/
├── schema.md, README.md           # conventions + entry point
├── raw/
│   ├── traces/<game>_v1_clear.jsonl   # solution traces (immutable)
│   └── regressions/v2_failures_20260420.md
└── wiki/
    ├── games/<GAMEID>.md          # per-game mechanics
    ├── game_types/<type>.md       # movement, click, programming_puzzle, merge_puzzle, sokoban
    ├── strategies/
    │   ├── frame_only/            # generalizable (bfs_state_space, ...)
    │   └── brittle/               # anti-patterns (internal_method_call)
    ├── selector.md                # feature → strategy dispatch rules
    └── index.md                   # flat backlink index
```

## Current Seeding Status (as of 2026-04-20)
- ✅ Directory scaffold, schema.md, README.md
- ✅ 3 game pages (TN36, SU15 brittle examples; AR25 frame-only template)
- ✅ 2 game_type pages (movement, programming_puzzle)
- ✅ 1 frame_only strategy (bfs_state_space), 1 brittle strategy (internal_method_call)
- ✅ selector.md draft + index.md + v2_failures_20260420.md regression analysis
- 🔄 22 more game pages, 4 more game_types, ~10 more strategies to seed
- 🔄 raw/traces/ extraction from ensemble_results.json + logs/*.jsonl to be scripted

## Inference Pipeline (Phase 8 Step 3, not yet built)
1. `scripts/run_wiki_agent.py` loads Qwen 3 8B 4bit + `.wiki/`
2. First 10-20 actions: discovery → classify game_type
3. Retrieve `wiki/game_types/<type>.md` + top-3 similar `wiki/games/*.md`
4. Zero-shot JSON output: primary_strategy + fallback_stack + rationale
5. No LoRA/TTT in v1 — only fall back if zero-shot underperforms

## What NOT to do
- Don't add v2-specific hardcoding — that's anti-generalization
- Don't add vector DB — incompatible with Kaggle
- Don't do online TTT — 6h budget better spent on actions
- Don't offline-fine-tune before proving zero-shot Wiki is insufficient

**How to apply:** When continuing Phase 8 work, refer to this layout; write new pages following `.wiki/schema.md`. Next incremental work: seed remaining 22 game pages + refactor 1 brittle solver (TN36 first). Stay inside the three-layer discipline — raw stays immutable, wiki/ compiles from raw, schema.md governs format.
