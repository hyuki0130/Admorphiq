---
type: lesson
symptom: "A solver has a per-level lookup table or a precomputed action sequence"
severity: blocker
first_seen: 2026-04-10 (TN36 `zpzcmabenn` direct call, KA59 hardcoded L1–L4)
---

# Hardcoded Is Anti

> Any hardcoded mapping of `level → solution` is a bet that level layouts stay identical. They do not. Every hardcoded solver eventually breaks; the only question is how much score it takes with it when it does.

## Symptom

- Solver function contains a dict like `{1: [...], 2: [...]}` keyed on level index
- Or contains magic coordinates copied from game source (`(12, 5)`, `(24, 5)`, ...)
- Or contains a precomputed program number (e.g. TN36 bit-encoded value per level)

## Why it fails

Two failure modes, both observed:

1. **Layout drift** between version hashes — the same level index has different tile positions, so the hardcoded move sequence hits a wall. Observed at `tn36-ef4dde99` v2 (0/7) and `ka59-38d34dbb` v2 (0/7).

2. **New preview game release** — the private test set contains entirely unseen games and the dict has no entry, so the solver returns without progress.

The failure mode is total: the solver does not degrade gracefully. It goes from perfect to zero.

## Prevention

Replace hardcoded tables with **runtime search**:

| Instead of | Do |
|------------|-----|
| `solutions = {1: "RRDD", 2: "LURR"}` | BFS/A* on frame state each level |
| `paint_positions = [(12,5), (24,5)]` | Detect swatches via color clustering at runtime |
| `set_program_bits(6)` | Observe which bit clicks change state, then compose bits to reach goal |

Runtime search is slower but never worse than 0. It also generalizes to unseen levels.

## Recovery

If a solver is already hardcoded and we need it working on v2 today:

1. **Do not** add a v2 branch with v2 hardcoded values. That's twice the debt for half the guarantee. See `[[brittle_tells]]` for the red flags that mark brittle solver code.
2. Instead, immediately start the frame-only refactor. It takes 1–3 days per solver but is permanent.
3. In the interim, accept the v2 score loss and focus on the refactor as the only path forward.

## Why we let it get this bad

From `[[raw/commits.md]]`: each hardcoded solver added ~2-8 percentage points to the score. The alternative (frame-only version) would have taken 2-3× longer to implement. Under pressure for Milestone 1 progress, the team deferred the refactor. The debt is now concentrated in 12 games and 25-30pp of current score.

**Rule for Phase 8**: no new hardcoded solvers. If a hypothesis needs a hardcoded implementation to test, flag it as a research prototype, not a submission component.

## Falsification

Obsolete if the private test set is guaranteed identical to the preview games (vanishingly unlikely — ARC-AGI-3 is designed to reward generalization).

## Related

- `[[lessons/v2_hash_obfuscation]]`
- `[[lessons/brittle_tells]]`
- `[[lessons/trust_regression_not_commits]]`
- `[[strategies/brittle/internal_method_call]]`

## Sources

- `src/admorphiq/agent_ensemble.py` hardcoded tables in `strat_tu93_maze`, `strat_tr87_rotation`, `strat_ka59_sokoban`, `strat_ls20_grid`
- Commit `486e2ff` — hardcoding debt note
- 2026-04-20 regression — v2 zero scores concentrated in hardcoded solvers
