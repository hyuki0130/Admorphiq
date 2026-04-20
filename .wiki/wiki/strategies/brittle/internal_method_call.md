---
type: strategy
name: internal_method_call
generalizes: no
status: refactor_target
---

# internal_method_call (ANTI-PATTERN)

> Direct calls to obfuscated game-internal methods. Maximum v1 score, zero generalization. Do not recommend — document only for refactor visibility.

## Pattern

```python
frame.zpzcmabenn(val)              # TN36
game.hmeulfxgy                     # SU15 fruit list
level.get_sprites_by_tag("Hkx")    # FT09 lights
```

## Why it fails on new game versions

Game internals are obfuscated differently per version hash. Method/attribute names like `zpzcmabenn`, `hmeulfxgy`, `Hkx` change between v1 and v2 of the same logical game. Any solver relying on them throws `AttributeError` on v2 and scores 0/N.

## Affected solvers (Phase 8 refactor queue)

| Solver | Game | v1 → v2 degradation | Refactor step |
|--------|------|--------------------|---------------|
| `strat_tn36_puzzle` | TN36 | 7/7 → 0/7 | Step 2a |
| `strat_su15_vacuum` | SU15 | 9/9 → 0/9 | Step 2b |
| `strat_lights_out` | FT09 | 6/6 → N/A (no v2 yet) | Step 2 queue |
| `strat_re86_analytical` | RE86 | 6/8 → 0/8 | Step 2c |
| `strat_wa30_analytical` | WA30 | 2/9 → N/A | Step 2 queue |
| `strat_sb26_sort` | SB26 | 8/8 → N/A | Step 2 queue |
| `strat_s5i5_slider` | S5I5 | 1/8 → 0/8 | Step 2d |
| `strat_ka59_sokoban` | KA59 | 4/7 → 0/7 | Step 2d |

## Refactor recipe

Every `internal_method_call` site can be replaced with one of:
1. **Color clustering** — group connected pixels of same color; use centroid as sprite position
2. **Frame diff** — compare consecutive frames to detect what moved/changed, infer entity type
3. **Persistent-region detection** — static background regions = walls/goal zones
4. **Behavior probing** — during discovery phase, click candidate entities and observe which cause state changes (= interactive, not static)

## Related

- [[../raw/regressions/v2_failures_20260420]]
- [[frame_only/bfs_state_space]] (template for refactor)
- Phase 8 Step 2 in [[../../../CLAUDE.md]]
