---
type: game_type
examples: [R11L]
refactor_status: frame_only_works
---

# Sequence Game

> Progress requires a short action sequence (typically 3-5 actions) which the agent discovers by search.

## Identifying features

- Small `available_actions` set
- No obvious movement/click target; the game reacts only when a specific sequence is produced
- Frame diff reveals periodic structure on success

## Discovery protocol

1. Try all 2-tuples, then 3-tuples, of available actions (`seq_search`)
2. For each tuple, run it `k` times; detect level-up signal
3. Cache winning tuple per level

## Canonical strategy

[[../strategies/frame_only/seq_search]] then [[../strategies/frame_only/seq_repeat]] once a winner is found.

## Games and current results

| Game | v1 | v2 | Strategy |
|------|-----|-----|----------|
| [[../games/R11L]] | 1/6 | 1/6 | seq_repeat (frame_only) |
