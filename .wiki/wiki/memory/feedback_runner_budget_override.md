---
name: Runner Budget Override Discipline
description: Never lower total_budget in scripts/run_ensemble.py below class default without explicit justification — silent regressions follow
type: feedback
originSessionId: 96a72d05-e421-4801-9b30-810c293777f0
---
`scripts/run_ensemble.py` previously set `EnsembleAgent(total_budget=20000)` while the `EnsembleAgent` class default is 50000. This silently starved LF52 (needs `adaptive_c2` strategy with ~20K+ actions budget) and SK48 (needs `sk48_snake` with similar budget). Both games showed 0 in regression for weeks despite their strategies still existing.

**Rule:** Do not override `total_budget` in the runner below the class default unless there's a written justification in the same commit. If the regression needs to run faster for iteration, create a separate `scripts/run_ensemble_fast.py` with a documented lower budget for dev-time use only. Submission-quality runs always use class default or higher.

**Why:** Budget starvation is the same symptom as strategy removal or silent regression, but the diagnosis and fix are completely different. Mixing them up wastes days of investigation.

**How to apply:**
- When editing the runner, default to `total_budget=50000` (class default).
- If you must lower it, add an inline comment linking to `.wiki/wiki/debug/budget_starvation.md` and the issue you're working around.
- When triaging a regression, always try the higher budget before assuming the strategy broke — see `.wiki/wiki/debug/budget_starvation.md` playbook.
