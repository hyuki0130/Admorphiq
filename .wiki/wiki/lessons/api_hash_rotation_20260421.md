---
name: ARC API Hash Rotation (2026-04-21) — The "v1" Goalposts Moved
description: Between 2026-04-20 and 2026-04-21 the API replaced every served env hash; all brittle-internals solvers silently died
type: lesson
date: 2026-04-21
severity: high
related: [v2_hash_obfuscation, hardcoded_is_anti, silent_regression, trust_regression_not_commits]
---

## What happened

**2026-04-20 Round 1 regression** showed SU15 7/9 via `strat_su15_vacuum` on env
`su15-4c352900`. The solver read `game.hmeulfxgy / peiiyyzum / rqdsgrklq`.

**2026-04-21 re-run** (same runner, same code, same budget) produced SU15 0/9 on
env `su15-1944f8ab`. Those attributes no longer exist on the live env. A direct
probe:

```
hmeulfxgy   : ✗
peiiyyzum   : ✗
rqdsgrklq   : ✗
```

Today's Su15 game object exposes a completely different set of obfuscated
attribute names (`bicnaxoxq`, `cmaswhinr`, `dgpsayght`, ... — 55 public fields,
none matching what the solver expects).

Game-by-game diff vs 2026-04-20 regression:

| Game | 2026-04-20 | 2026-04-21 | Strategy that broke |
|------|-----------|-----------|---------------------|
| SU15 | 7/9 | **0/9** | `strat_su15_vacuum` (3 attr reads) |
| RE86 | 6/8 | **0/8** | `strat_re86_analytical` (3 attr reads) |
| KA59 | 2/7 | **0/7** | `strat_ka59_sokoban` (hardcoded level pushes + attr reads) |
| CN04 | 1/5 | **0/5** | `zig3_A2A4` tuning |
| S5I5 | 1/8 | **0/8** | `strat_s5i5_slider` (2 attr reads) |

**Overall score**: 27.34% (79/289 levels) → **18.62%** (54/290 levels). Same
agent, same code, one calendar day apart.

Games that survived the rotation: all dispatched through frame-only strategies
(TU93, AR25, M0R0, SC25, WA30, BP35, LP85, DC22, SP80, G50T, R11L, VC33, LS20,
SK48, LF52 via `adaptive_c2`, FT09 via `paint_game`/`lights_out` which are
more pattern-based).

## Why it happened

The ARC Prize API treats each "game" as a family of hash-versioned environments.
`su15-4c352900` and `su15-1944f8ab` are both instances of the Su15 game, but
the obfuscator ran differently — every attribute name is a fresh hash. Any
solver that baked a specific attribute string into code is hostage to that
single run's hash.

What we previously called "v1 vs v2 hash obfuscation" was the *visible* part of
the same phenomenon: two hashes served simultaneously. The 2026-04-21 event is
the same mechanism rotating through time — yesterday's working hash is simply
no longer served.

## What this changes

1. **The 2026-04-20 "v1 36.81%" baseline was a one-day fluke.** It looked stable
   because the hash was stable *that day*. It isn't a reproducible reference
   number going forward.
2. **Every brittle solver is on borrowed time.** Even if a solver clears a game
   on today's regression, the next API refresh can zero it out overnight without
   any code change on our side.
3. **Frame-only becomes strictly necessary, not just "for private test set".**
   The preview set itself rotates.
4. **Our `trust_regression_not_commits` lesson was right for the wrong reason.**
   We were worried about commit-message drift; the real drift is env drift.

## How to apply

- **Stop counting "v1 score" as a long-term metric.** Always compare
  frame-only scores; brittle scores are noise that can evaporate.
- **Add a frame-only scaffold *alongside* every brittle solver.** The Phase 8
  Step 2 plan already calls this out — treat it as the floor, not the stretch
  goal.
- **When regressing, record the env hashes.** If SU15 cleared on hash X but
  not on hash Y, that tells us the solver is hash-coupled even if both were
  marketed as "v1" at some point.
- **The LLM Hypothesis Engine path (Task #9) is the only sustainable answer.**
  Frame-only + wiki retrieval + LLM strategy pick does not depend on the hash.
  Prioritize WikiAgent validation accordingly.

## Evidence

- `scripts/ensemble_results.20260410.json` — SU15 `su15-4c352900` 7/9
- `scripts/ensemble_results.json` — SU15 `su15-1944f8ab` 0/9 (2026-04-21 run)
- Inline probe output: 11 attribute reads × 3 games, all AttributeError on today's envs.

## Related

- [[v2_hash_obfuscation]] — describes the two-hash-per-game pattern
- [[hardcoded_is_anti]] — general rule against attribute-coupled code
- [[silent_regression]] — same failure mode shape
- [[../debug/attribute_error_playbook]] — the recovery checklist
