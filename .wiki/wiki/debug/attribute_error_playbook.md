---
type: debug
trigger_symptom: "AttributeError when running a strategy on a v2 game hash"
affects: [su15_vacuum, tn36_puzzle, re86_analytical, wa30_analytical, s5i5_slider, ka59_sokoban, lights_out, sb26_sort, paint_game]
---

# AttributeError Playbook

> A strategy throws `AttributeError` on a new game hash version. This is the defining signature of `[[lessons/v2_hash_obfuscation]]`.

## Observable Symptom

```
AttributeError: 'Game' object has no attribute 'hmeulfxgy'
```

or similar with any random identifier. Also variants:

```
AttributeError: 'FrameData' object has no attribute 'zpzcmabenn'
```

```
  sprites = level.get_sprites_by_tag("vzuwsebntu")
AttributeError: 'NoneType' object has no attribute 'get_sprites_by_tag'
```

(The last form can happen when the tag itself returns None.)

## Triage Steps

1. **Identify the failing line**. Check the traceback for the exact attribute name.
2. **Grep the codebase** for the attribute: `grep -rn "hmeulfxgy" src/`. You'll find the strategy function (e.g. `strat_su15_vacuum`).
3. **Check when the attribute was added**: `git log -p --all -S "hmeulfxgy"` to find the introducing commit.
4. **Check which game versions have the attribute**: open each `environment_files/<game>/<hash>/<game>.py` and grep for the attribute. On v2, it won't appear.
5. **Classify**: this is a brittle-solver failure. File under `[[strategies/brittle/internal_method_call]]` if not already there.

## Likely Root Causes

| Cause | Diagnosis |
|-------|-----------|
| v2 obfuscation renamed the attribute | grep `environment_files/<game>/<v2_hash>/*.py` — attribute missing |
| v2 removed the attribute entirely | same grep shows no replacement |
| Code path only entered on a specific level that doesn't exist in v2 | walk through the logic with a v2 frame to confirm |

## Fix Recipes

### Option A (preferred) — Frame-only refactor

See `[[lessons/frame_diff_as_probe]]` and `[[strategies/frame_only/bfs_state_space]]`. Replace the attribute-reading block with:

- Color clustering to identify sprites
- Frame diff to classify entity types (player/block/interactive)
- Persistent-region detection for goals
- Probe-click for interactive objects

This is the path CLAUDE.md Phase 8 Step 2 prescribes.

### Option B (temporary) — Swap in v2 attribute name

Only acceptable as a **research prototype** to measure ceiling. Never merge.

### Option C — Fallback to frame-only strategy

If the brittle solver is the only one in the stack, wrap it with a fallback:

```python
try:
    return strat_brittle(env, ...)
except AttributeError:
    return strat_bfs_state_space(env, ...)  # frame-only fallback
```

This at least avoids zero-score on v2 until the refactor lands.

## When to Escalate

Escalate (i.e. stop and ask) when:
- More than one attribute error appears for the same game (widespread obfuscation — may indicate entire game reimplementation, not just renaming)
- The attribute is used via `getattr(game, name)` with a variable `name` — implies the code was already trying to be version-agnostic and something else broke

## Falsification

Obsolete if ARC Prize publishes a stable public API contract for game objects. Not currently the case.

## Related

- `[[lessons/v2_hash_obfuscation]]`
- `[[lessons/brittle_tells]]`
- `[[strategies/brittle/internal_method_call]]`
- `[[debug/v1_vs_v2_diagnosis]]`
