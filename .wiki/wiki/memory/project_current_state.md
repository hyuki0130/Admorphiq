---
name: Current Project State (2026-04-20, verified)
description: Admorphiq ARC-AGI-3 — verified 22/25 games, 56/182 levels (~30.77%); commits claim 25/25/69 but unverified
type: project
originSessionId: 96a72d05-e421-4801-9b30-810c293777f0
---
## Verified vs Claimed (CRITICAL distinction)
- **Verified** (latest 25-game regression `scripts/ensemble_results.json`, 2026-04-10): **22/25 games, 56/182 levels (30.77%)**
- **Claimed** (post-regression commit messages, single-game tests only): 25/25 / 69 levels / 37.9%
- **Gap**: TN36 (5e8562a), SU15 9/9 (b84839e), KA59 4/7 (b84839e) need fresh regression to confirm

## Failed in latest regression
- **LF52** 0/10 — regression from earlier clear (was cleared in older runs)
- **SK48** 0/8 — regression from earlier clear (063a136 added it)
- **TN36** 0/7 — never cleared in regression (5e8562a fix not yet re-tested)

## Verified Per-Game Status
- **Perfect (3)**: CD82 6/6, FT09 6/6, SB26 8/8
- **High depth**: SU15 7/9 (claimed 9/9), RE86 6/8
- **Multi-level**: TU93 2/9, AR25 2/8, M0R0 2/6, SC25 2/6, KA59 2/7 (claimed 4/7), WA30 2/9
- **Single-level (11)**: CN04, TR87, LP85, DC22, SP80, G50T, BP35, S5I5, R11L, VC33, LS20

## Phase Status
- Phase 1-6: ✅ Complete
- **Phase 7: 🔄 In Progress** — verified 30.77%, needs regression re-run + LF52/SK48 root cause
- Phase 8 (Generalization + Kaggle): NEXT, blocked on Phase 7 verification

## Immediate Next Actions (priority order)
1. **Re-run 25-game regression** to verify TN36/SU15/KA59 commit claims
2. **Investigate LF52/SK48 regression** — find what broke them since earlier clears
3. **Then** start Phase 8 cleanup (hardcoding debt) + LLM integration

## Phase 8 Plan (after Phase 7 verified)
- Remove game-internal access from analytical solvers
- Integrate Qwen 3 8B + LoRA hypothesis engine (primary) / Gemma 4 26B MoE 4-bit (alt)
- Validation gate: ≥21/25 games still cleared after refactor
- Kaggle T4 16GB packaging

## Lessons (do not repeat)
- **Never trust commit messages alone for score claims** — always verify via `scripts/ensemble_results.json` or fresh regression
- LF52/SK48-style regressions are silent without full 25-game runs; need CI gate

**How to apply:** When asked about current score, cite `ensemble_results.json` numbers as "verified" and commit-message numbers separately as "claimed, unverified". Re-run the regression before any Phase 7→8 transition.
