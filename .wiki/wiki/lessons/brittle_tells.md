---
type: lesson
symptom: "During code review, a strategy looks like it works but is actually tied to game internals"
severity: warn
first_seen: 2026-04-03 (486e2ff — hardcoding debt documented)
---

# Brittle Tells

> Code smells that indicate a strategy will fail on a new version hash. Use this checklist when reviewing any new `strat_*` function in `src/admorphiq/agent_ensemble.py`.

## The checklist

Each red flag is a reason to reject the PR or mark the strategy as brittle.

### 🚩 Direct attribute access on game/frame/level
```python
game.hmeulfxgy                      # RED — game attribute name
frame.zpzcmabenn(val)               # RED — frame method
level.some_obfuscated_attr          # RED
```
Attribute names are version-hash-specific. **Obfuscated-looking identifiers (random letter sequences) are the strongest tell.**

### 🚩 Sprite tag strings
```python
level.get_sprites_by_tag("Hkx")     # RED — tag string
level.get_sprites_by_tag("vzuwsebntu")  # RED — obfuscated tag
```
Tag strings are part of the obfuscation mapping. See `[[lessons/v2_hash_obfuscation]]`.

### 🚩 Hardcoded level dictionaries
```python
hardcoded = {
    1: [ACTION1, ACTION2, ACTION4, ...],  # RED — level layout dependency
    2: [ACTION3, ACTION6, ...],
}
```
Level layouts change between versions. Any `if level == N: do_sequence` branch is a bet on layout equivalence.

### 🚩 Hardcoded coordinate constants tied to level
```python
COLOR_SWATCH_POSITIONS = {1: (12, 5), 2: (24, 5), ...}   # RED if values were read from source
```
Fine if derived from frame observation at runtime; brittle if copied from game source code.

### 🚩 Calling private/_-prefixed members or module-level functions on the game
```python
from environment_files.cd82.cd82 import _internal_helper  # RED
```
Direct imports from `environment_files/<game>/` are per-version brittle.

## Green (frame-only) patterns

| Pattern | Why safe |
|---------|----------|
| `find_color_positions(frame, color_idx)` | operates on pixel grid only |
| Frame diff between consecutive actions | no internal access |
| Cluster connected components | topology-based, not name-based |
| Probe-click to learn effect | learns dynamically, not hardcoded |
| `available_actions` subset checks | part of public `FrameData` |

## Review gate (copy for PR description)

```
Brittle-solver review for `strat_<name>`:
- [ ] no direct `game.<attr>` / `frame.<method>` access
- [ ] no `get_sprites_by_tag(...)` calls
- [ ] no hardcoded `{level: sequence}` or `{level: coords}` dicts
- [ ] no imports from `environment_files/<game>/*`
- [ ] passes both v1 and v2 hash versions in latest regression

If any box unchecked, file under `strategies/brittle/` and add to Phase 8 refactor queue.
```

## Falsification

This lesson becomes obsolete if the ARC Prize API stabilizes a public contract where internal attribute names are guaranteed stable across hashes — currently not the case.

## Related

- `[[lessons/v2_hash_obfuscation]]`
- `[[lessons/hardcoded_is_anti]]`
- `[[strategies/brittle/internal_method_call]]`
- `[[lessons/frame_diff_as_probe]]` — the dominant frame-only alternative

## Sources

- `src/admorphiq/agent_ensemble.py` — all 7 brittle solvers listed in `[[strategies/brittle/internal_method_call]]`
- Commit `486e2ff` — first written documentation of this concern
- 2026-04-20 regression — 12 brittle games × v2 failure confirms every listed tell
