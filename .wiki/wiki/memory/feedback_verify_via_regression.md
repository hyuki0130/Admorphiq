---
name: Verify Score via Regression
description: Trust scripts/ensemble_results.json and full 25-game runs over commit messages
type: feedback
originSessionId: 96a72d05-e421-4801-9b30-810c293777f0
---
When reporting Admorphiq game/level scores, always verify via the latest 25-game regression artifacts (`scripts/ensemble_results.json`, `logs/*_ensemble_*.jsonl`), not via commit messages.

**Why:** Commit messages claimed "25/25 games, 69/182 levels (37.9%)" (5e8562a) and "24/25, 62 levels" (b84839e), but the actual `ensemble_results.json` (run after both commits at 14:13–14:17) shows **22/25 games, 56/182 levels (30.77%)** with LF52, SK48, TN36 all failed. Author commits often reflect single-game tests or aspirational totals, not regression runs. Reporting commit-message numbers as fact misled the user and triggered a correction.

**How to apply:**
- Before quoting any "current score" or "games cleared" number, open `scripts/ensemble_results.json` and aggregate
- Distinguish "verified" (regression) vs "claimed" (commit-message, single-game test) explicitly
- If a commit claims a fix without a fresh regression, treat it as unverified until `run_25games.py` (or equivalent) re-runs
- Watch for silent regressions: LF52/SK48 had cleared in older commits but failed in latest run — only full-suite tests catch this
- When in doubt, suggest re-running the regression before making Phase transitions or doc updates
