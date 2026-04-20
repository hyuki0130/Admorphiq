---
type: concept
instantiating_games: [ALL]
detection_frame_only: n/a
---

# Version Hash

> A game's identifier in the ARC Prize API has the form `<title>-<hash>` (e.g. `tn36-ab4f63cc`). The hash is a version fingerprint: games with the same title but different hashes share gameplay rules but differ in internal implementation details that solvers may or may not observe.

## Definition

When the Arcade API returns an environment list, each entry has a `game_id` like `su15-4c352900`. Structure:
- `su15` — the **title** (shared across versions)
- `4c352900` — the **version hash** (unique per implementation)

Visible gameplay (rules, goal, action semantics) is identical across hashes of the same title. What differs:

| Differs between versions | Example |
|--------------------------|---------|
| Obfuscated Python attribute names | `game.hmeulfxgy` in v1, something else in v2 |
| Sprite tag strings | `"Hkx"` in v1, different string in v2 |
| Frame method names | `frame.zpzcmabenn(val)` in v1, possibly absent in v2 |
| Level layouts (per-level tile positions, counts) | level 1 of KA59 has different push sequence in v2 |

Stays the same:
- Action semantics (ACTION1 means the same rule)
- Color palette and frame dimensions
- Win condition and level progression signal

## Why the API serves multiple hashes

Not officially documented; working hypothesis:
- Each hash is a separate anti-memorization instance
- Running on both catches solvers that memorize internals of a single hash
- The private test set uses further unseen hashes

Observed: as of 2026-04-20, the API serves 40 envs = 25 titles × (1 or 2 hashes each). 12 titles have a v2 hash, 13 titles have only v1.

## Implication for solver design

- A solver that depends on any `game.<attr>` or tag string read from the obfuscation mapping will pass v1 and fail v2. See `[[lessons/v2_hash_obfuscation]]`.
- A solver that reads only public `FrameData` fields passes both. See `[[lessons/frame_diff_as_probe]]`.
- Private test set likely introduces v3+/new titles; robustness to v1 → v2 is a proxy for private-set robustness.

## Detection heuristics

None needed at inference — the hash is in `env.game_id`. The implication for the LLM is: **never write logic conditioned on the hash value**. Treat the hash as opaque.

## Related

- `[[lessons/v2_hash_obfuscation]]`
- `[[raw/regressions/v2_failures_20260420]]`
- `[[lessons/hardcoded_is_anti]]`

## Sources

- `scripts/ensemble_results.json` (2026-04-20) — first run showing two hashes per title
- `logs/regression_round1_20260420.log` — API log showing hash list
