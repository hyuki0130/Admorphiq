---
type: debug
trigger_symptom: "A game cleared in a past commit now scores 0 and no single commit obviously broke it"
affects: [LF52, SK48]
---

# Regression Bisect Playbook

> Use `git bisect` against a focused regression command to find the commit that silently broke a game.

## Observable Symptom

See `[[lessons/silent_regression]]`. A game you know was cleared before scores 0 on the current regression, with no commit message mentioning it.

## Prerequisite

Identify the last known-good commit from `[[raw/commits.md]]`. Example:
- **LF52** last seen cleared at `b1cbc91` (commit message: "13/25 games — ensemble budget 50K clears G50T, LF52, CD82").
- **SK48** last seen cleared at `063a136` (commit message mentions SK48 added).

## Procedure

### 1. Write a bisect script

Create `scripts/bisect_<game>.sh`:

```bash
#!/usr/bin/env bash
set -e
# Run only the target game, short budget
uv run python - <<'PY'
import json, sys
from arc_agi import Arcade, OperationMode
from admorphiq.agent_ensemble import EnsembleAgent

arcade = Arcade(operation_mode=OperationMode.NORMAL)
envs = [e for e in arcade.get_environments() if e.game_id.startswith("lf52-")]
if not envs:
    sys.exit(125)  # skip — env missing on this commit
agent = EnsembleAgent(total_budget=5000)
env = arcade.make(envs[0].game_id)
result = agent.solve_game(env, game_id=envs[0].game_id)
sys.exit(0 if result.get("cleared") else 1)
PY
```

Make it executable, and **verify it works on both the known-good commit (should exit 0) and the broken current commit (should exit 1)**.

### 2. Run the bisect

```bash
git bisect start
git bisect bad HEAD                 # current commit is broken
git bisect good b1cbc91             # known-good commit

git bisect run scripts/bisect_lf52.sh
```

`git bisect run` will run the script at each midpoint commit. When it converges, git prints the first bad commit.

### 3. Diff the first bad commit

```bash
git show <first_bad_commit> -- src/admorphiq/agent_ensemble.py
```

Look for:
- Changes to strategy dispatch order
- Shared budget reductions
- Removal of a `if title == "LF52"` branch (Phase 6 refactor `380c3dc` did this)
- Strategy registration changes

### 4. Write the fix

- If dispatch order starved the winning strategy: reinsert it earlier, or use a per-game priority hint.
- If budget starved it: raise per-strategy budget or split budget fairer.
- If Phase 6 refactor stripped a gate: re-add the behavior via a feature-based trigger (not game-ID).

### 5. Verify with full regression

Run the full 25-game regression (`uv run python scripts/run_ensemble.py`) to confirm the fix does not regress other games.

## Pitfalls

- **Environment API changes**: if the Arcade API changed between HEAD and the old commit, the script may fail for unrelated reasons. Use `sys.exit(125)` to skip those commits.
- **Nondeterminism**: some strategies are stochastic. Run each commit 3×; majority vote.
- **Budget inflation bias**: if you raise the budget too high in the bisect script, every commit may pass — losing sensitivity. Use the same budget the real regression uses (~20K).

## When to Escalate

- If bisect converges on a commit that looks unrelated: the regression may be caused by an environment/dependency upgrade, not a code change. Check `uv.lock` history.
- If bisect cannot reproduce on the known-good commit either: the regression may have been an artifact of an older environment that is no longer reachable.

## Related

- `[[lessons/silent_regression]]`
- `[[lessons/trust_regression_not_commits]]`
- `[[games/LF52]]`, `[[games/SK48]]`
- `[[raw/commits.md]]`
