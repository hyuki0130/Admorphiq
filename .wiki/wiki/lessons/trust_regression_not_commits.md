---
type: lesson
symptom: "Commit message claims a score but no regression artifact verifies it"
severity: warn
first_seen: 2026-04-10 (commit 5e8562a claimed 25/25, regression showed 22/25)
---

# Trust Regression, Not Commit Messages

> Commit messages often reflect a single-game test or an aspirational total. Only a full 25-game regression run produces a trustworthy score. Always cite the regression artifact, never the commit message.

## Symptom

A commit says "25/25 games, 69/182 levels (~37.9%)" or "24/25, 62 levels". Documentation downstream quotes the commit number as fact. Later regression shows something lower.

## Why it happens

- **Single-game test after a fix** produces a clean win; author extrapolates to "all 25".
- **Per-game tests done manually** but not aggregated into the full regression pipeline.
- **LF52/SK48 style silent regressions** are not re-checked; the author assumes they still pass because nothing in their PR touched them.

## Prevention

1. **Single source of truth**: `scripts/ensemble_results.json` (or its archived copies). Every claim about total score links to a specific regression run and timestamp.
2. **Commit message format** for score-claiming commits should include:
   ```
   Regression: scripts/ensemble_results.20260420.json
   v1: 23/25, 67/182 (36.81%)
   v1+v2: 31/40, 79/289 (27.34%)
   ```
3. **Documentation cross-check**: before copying a number into `CLAUDE.md` or `memory/`, grep for "regression" in the source commit message. If absent, require a fresh run.

## Recovery when caught

When a doc quotes a phantom number:

1. Run the regression to get the real number.
2. Update the doc with `Verified: <date>` and the regression file reference.
3. Add a `Claimed vs verified` table if the gap is material.
4. If the gap is caused by silent regression, file a bisect task. See `[[debug/regression_bisect_playbook]]`.

## Falsification

Obsolete if CI enforces regression-on-every-commit and merges blocked on score-claim mismatch.

## Related

- `[[lessons/silent_regression]]`
- `[[debug/regression_bisect_playbook]]`
- `[[raw/commits.md]]` — 2026-04-10 entries for commits that claimed more than they verified

## Sources

- Commit `5e8562a` commit message vs actual run at 14:17 on same date
- Memory feedback: `memory/feedback_verify_via_regression.md`
