---
type: lesson
symptom: "A game that was cleared in a past commit scores 0 in the current regression, with no commit message explaining why"
severity: blocker
first_seen: 2026-04-20 (noticed LF52 0/10 and SK48 0/8)
---

# Silent Regression

> A silent regression is a game that used to clear but now fails, without any commit explicitly breaking it. These are dangerous because commit messages claim continued progress, and the regression only surfaces on the next full 25-game run.

## Symptom

- `scripts/ensemble_results.json` shows a previously cleared game with `levels_completed: 0`
- No recent commit message mentions the game
- Cleared levels of other games may have increased during the same period

Concrete 2026-04-20 examples:
- **LF52** cleared at commit `b1cbc91` via ensemble-budget 50K; now 0/10
- **SK48** cleared at commit `063a136` via `sk48_snake`; now 0/8 on both v1 and v2

## Root Cause (hypotheses)

1. **Dispatch ordering change**: a later strategy added earlier in the dispatch list consumes budget before the historical winning strategy can run. Example: if `sk48_snake` used to run first but now runs after 10 other strategies, the per-strategy budget may starve it.
2. **Shared resource mutation**: a solver added for game Y modifies a shared state (ensemble `total_budget`, memoization cache) that game X previously relied on.
3. **Budget split regression**: reducing a single-strategy budget for policy reasons (e.g. PROVEN strategy priority at `4b683e0`) may starve long-running winners.
4. **Refactor side effect**: the Phase 6 generalization refactor (`380c3dc`) removed game-ID-specific dispatch. If the old clearing strategy depended on a game-ID gate that was stripped, the strategy is no longer tried.

## Prevention

- **Full 25-game regression on every commit that touches dispatch or ensemble budget.** Cheap (~15 min on local machine) and catches this.
- **Commit message hygiene**: if a commit claims a new score, include a `scripts/ensemble_results.json` hash or a summary line. See `[[lessons/trust_regression_not_commits]]`.
- **Do not trust commit-claim scores.** Only regression-produced numbers count.

## Recovery

See `[[debug/regression_bisect_playbook]]` for the stepwise procedure. Short version:

1. Identify last known good commit from `raw/commits.md` (e.g. LF52 cleared at `b1cbc91`).
2. `git bisect start <current> <known-good>`.
3. At each step, run a scoped regression on just the affected games (faster than full 25).
4. Once the breaking commit is found, diff it and revert or patch the specific dispatch change.

## Falsification

This lesson is obsolete if we adopt CI that runs full regression on every commit — silent regressions become loud regressions.

## Related

- `[[lessons/trust_regression_not_commits]]`
- `[[debug/regression_bisect_playbook]]`
- `[[games/LF52]]`, `[[games/SK48]]`
- `[[raw/commits.md]]` — timeline entries for LF52/SK48 clears and the suspected breaking refactor commits

## Sources

- 2026-04-20 Round 1 regression (`scripts/ensemble_results.json`)
- Historical commits `b1cbc91`, `063a136`, `380c3dc`, `4b683e0`
