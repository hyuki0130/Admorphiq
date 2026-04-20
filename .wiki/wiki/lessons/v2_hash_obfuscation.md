---
type: lesson
symptom: "Strategy that cleared game X on v1 hash scores 0 on v2 hash of the same game"
severity: blocker
first_seen: 2026-04-20 (Round 1 regression)
---

# v2 Hash Obfuscation

> When the ARC Prize API serves a second version hash of a game, game internals (attribute names, sprite tags, method names, level layouts) are re-obfuscated — so any solver that reads those internals fails silently.

## Symptom

Run the 25-game ensemble regression. Observe that specific games have two envs (e.g. `su15-4c352900` and `su15-1944f8ab`), both with the same title. The first hash passes; the second returns 0 levels cleared, often via silent `AttributeError` or empty sprite lists.

## Root Cause

Each published version hash of a game appears to carry an **independent obfuscation mapping**. Things that change between v1 and v2 include:

- Python attribute names on the game class (e.g. `game.hmeulfxgy` → some other random string on v2)
- Method names on frame/game objects (e.g. `frame.zpzcmabenn(val)` → `AttributeError` on v2)
- Sprite tags returned by `level.get_sprites_by_tag("Hkx")` (different tag strings → empty list)
- Hardcoded level layouts (blocks in different positions, different number of pieces)

What stays the same: the **game rules** (visible behavior), the `available_actions`, frame dimensions, color palette, and ACTION6 coordinate semantics.

## Prevention

Write solvers that read **only** the public interface:

| Use | Avoid |
|-----|-------|
| `frame_data.frame` (pixel grids) | `game.<attr>` / `frame.<method>` |
| `frame_data.available_actions` | `level.get_sprites_by_tag("...")` |
| `frame_data.state`, `frame_data.levels_completed` | direct access to obfuscated sprite lists |
| per-pixel color clustering | hardcoded sprite coordinate constants |
| frame-diff after action | hardcoded action sequences per level |

This is the `[[strategies/frame_only/...]]` side of the split. See `[[strategies/brittle/internal_method_call]]` for the anti-pattern catalogue.

## Recovery

When a solver breaks across versions:

1. Identify the exact failing call site (likely `AttributeError` or empty sprite list) — see `[[debug/attribute_error_playbook]]`.
2. Replace with a frame-only detection (color cluster, diff, persistent region, probe-click).
3. Validate that v1 still passes (regression non-degradation).
4. Re-run 25-game regression and confirm v2 improves from 0.

## Falsification

This lesson is obsolete if any of these becomes true:

- ARC Prize API stops serving v2/v3 hashes and commits to a fixed internal API contract.
- A reliable deobfuscation tool is published that maps v2 names back to v1 names (ethically questionable, likely against competition rules).
- We switch to a solver architecture where game internals are never read (Phase 8 completion).

## Related

- `[[concepts/version_hash]]` — what a version hash is and why the API serves multiples
- `[[lessons/brittle_tells]]` — how to spot brittle solver code during review
- `[[lessons/hardcoded_is_anti]]` — broader anti-pattern argument
- `[[debug/attribute_error_playbook]]` — stepwise recovery from `AttributeError`
- `[[debug/v1_vs_v2_diagnosis]]` — how to isolate which internal changed
- `[[raw/regressions/v2_failures_20260420]]` — original observation (7 brittle solvers broken at once)
- `[[raw/commits.md]]` — see 2026-04-20 entry

## Sources

- Round 1 regression: `scripts/ensemble_results.json` (2026-04-20)
- Commit history entries for `2a4c394`, `2029c01`, `102002c`, `b84839e`, `5e8562a`
- `[[strategies/brittle/internal_method_call]]` refactor queue (7 solvers)
