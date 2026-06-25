---
type: debug
trigger_symptom: "A game that used to clear now fails; diff shows no strategy was removed; direct single-game test with higher budget clears"
affects: [LF52]
---

# Budget Starvation

> A per-strategy budget (or ensemble total budget) change starves a strategy that needs many actions to progress. The strategy still exists and is dispatched, but finishes before reaching a winning sequence.

## Observable Symptom

- Ensemble regression scores 0 for a game that was cleared at an older commit.
- `strategies_tried` in the trace shows the historical winning strategy was attempted and consumed actions but returned 0 levels.
- Running the same strategy in isolation with a larger budget clears the level.

## Root Cause

`scripts/run_ensemble.py` (or equivalent runner) sets `EnsembleAgent(total_budget=N)` where `N` is smaller than the minimum budget the winning strategy needs. The EnsembleAgent internally divides this across many strategies; the tail strategies get pennies.

For LF52, commit `b1cbc91` established a 50000-action total budget ("Ensemble budget 5K → 50K: AR25 regression fixed, 3 new games cleared"). A later refactor dropped the runner default to 20000, silently starving LF52's `adaptive_c2` strategy.

## Triage Steps

1. Identify the historical clearing strategy by reading `raw/commits.md` or the PR that added it.
2. Run it in isolation at a higher budget:
   ```python
   agent = EnsembleAgent(total_budget=50000)
   agent.solve_game(env, game_id=gid)
   ```
3. If it clears at high budget, the issue is budget starvation.
4. If not, the strategy itself broke — see `[[regression_bisect_playbook]]`.

## Fix Recipes

### Raise runner budget
The simplest fix: set `total_budget` in the runner to the highest per-game need (typically 50K):
```python
agent = EnsembleAgent(total_budget=50000)
```
Cost: longer runs (~25% more time per game on failed cases).

### Per-strategy budget allocation
If raising total budget is unacceptable, allocate per-strategy budgets explicitly so critical strategies get what they need. Edit the dispatch site to use `remaining = min(MIN_BUDGET_FOR_STRATEGY, self.total_budget - total_actions)`.

### Regression CI
Add a commit hook or CI step that runs the 25-game regression and fails the build if any game previously cleared now scores 0.

## LF52 Recovery (2026-04-21)

Root cause confirmed: `scripts/run_ensemble.py` used `total_budget=20000`. Raising to 50000 (matches class default, matches historical value) restored 1/10 via `adaptive_c2` in 17.6 seconds. See commit that set this budget + the current fix commit.

## When to Escalate

- Budget at 50K+ still doesn't clear: strategy itself was modified — use `[[regression_bisect_playbook]]`.
- Raising budget causes other games to regress: dispatch ordering is wrong. File a dispatch audit task.

## Falsification

Obsolete if the runner is refactored to allocate per-strategy budgets explicitly, making total-budget a coarse ceiling rather than the primary constraint.

## Related

- `[[../lessons/silent_regression]]` — symptom class this debug entry resolves
- `[[regression_bisect_playbook]]` — use if budget raise does not recover
- `[[../games/LF52]]`
- `[[../raw/commits.md]]` — entry for commit `b1cbc91` that established 50K budget
