---
type: debug
trigger_symptom: "Same game title, two different hash envs, one passes and one fails"
affects: [SU15, TN36, RE86, KA59, S5I5, CN04]
---

# v1 vs v2 Diagnosis

> Structured procedure for isolating what changed between two version hashes of the same game, so the refactor is targeted.

## Observable Symptom

`scripts/ensemble_results.json` shows two envs with the same title, e.g. `su15-4c352900` (9/9 ✅) and `su15-1944f8ab` (0/9 ❌).

## Triage Steps

### 1. Confirm it's a v2 issue, not a stochastic failure
Run the failing env twice. If it's truly 0 both times, it's structural.

### 2. Locate both env source files
```
environment_files/<game>/<hash>/<game>.py
```
Example:
- `environment_files/su15/4c352900/su15.py` (v1)
- `environment_files/su15/1944f8ab/su15.py` (v2) — if pre-downloaded; otherwise server-only

### 3. Read the failing strategy
Open `src/admorphiq/agent_ensemble.py`, find `strat_<game>_<name>`. List every external reference:
- `game.<attr>`
- `frame.<method>`
- `level.get_sprites_by_tag("...")`
- Hardcoded level dicts

### 4. Cross-check each reference against v2
For each reference from step 3, grep the v2 source file:
```bash
grep -n "hmeulfxgy" environment_files/su15/1944f8ab/su15.py
```
Missing matches identify the obfuscation drift.

### 5. Classify what drifted

| Drift type | Action |
|------------|--------|
| Attribute name rename (`hmeulfxgy` → something else) | refactor to frame-only detection |
| Tag string rename | same |
| Added or removed levels | refactor hardcoded dict to runtime solver |
| Different number of sprites per level | refactor to dynamic count |
| Same attribute but different value semantics | rare; investigate carefully |

### 6. Plan the refactor

Write the refactor as a PR targeting:
- Replaces the drifted references with frame-only alternatives
- Passes v1 regression at same level count
- Improves v2 from 0 to > 0

See `[[strategies/brittle/internal_method_call]]` for the refactor catalogue and `[[games/<game>]]` for per-game refactor plans.

## Common Patterns Observed

From 2026-04-20 regression:

| Game | v1 references | v2 drift |
|------|---------------|----------|
| SU15 | `game.hmeulfxgy`, `game.peiiyyzum`, `game.rqdsgrklq` | all 3 attribute names differ on v2 |
| TN36 | `frame.zpzcmabenn(val)` | method name differs (or absent) on v2 |
| RE86 | 3 sprite tags | all 3 tag strings differ |
| KA59 | hardcoded L1-L4 push sequences | layout differs; sequences walk into walls |
| S5I5 | 2 sprite tags | differ |
| CN04 | `zig3_A2A4` tuning | timing/repeat count does not transfer |

## Falsification

Obsolete if v2 ever shares the v1 obfuscation mapping (would indicate a leak or competition policy change).

## Related

- `[[lessons/v2_hash_obfuscation]]`
- `[[lessons/brittle_tells]]`
- `[[debug/attribute_error_playbook]]`
- `[[strategies/brittle/internal_method_call]]`
- `[[raw/regressions/v2_failures_20260420]]`
