# Curated Commit History

Narrative history of significant commits. Immutable source for `lessons/`, `debug/`, and `reasoning/` pages. Regenerate when major commits land.

Only commits with lasting architectural or score impact appear here — minor tweaks live in git log.

## Timeline

### 2026-03-31 — Project bootstrap (Phase 1-2)
- Initial CNN perception backbone (`agent.py` AdmorphiqAgent, 34M params, dual head)
- Experience buffer with MD5 dedup
- Baseline 0/25 cleared.

### 2026-04-01 — Phase 3 World Model, Phase 3.5 fail
- Added WorldModel (StateEncoder + TransitionPredictor + ChangePredictor, 1.6M params)
- Phase 3.5: level rewards + SystematicExplorer + GameMemory → 500 actions × 3 games → still 0 cleared
- **Lesson extracted**: change prediction alone is insufficient — game-goal understanding is missing. See `[[lessons/change_prediction_is_not_enough]]` (planned).

### 2026-04-01 — Phase 4 Multi-strategy pivot
- Commit `849f8a1`: ensemble 14 games, ~12.8% — LS20 grid solver, surpasses StochasticGoose baseline (12.58%)
- Introduces `DiffAgent`, `GraphAgent`, ensemble dispatch. Clears first games via frame-only BFS.
- **Provenance**: first real wins were frame-only (BFS + diff); foreshadows why hardcoded solvers will later regress on v2.

### 2026-04-01 — 2a4c394 — CD82 first full clear
- CD82 6/6 via `paint_game` solver that reads sprite positions. First analytical solver.
- **Warning signal**: started the brittle-solver path that later created Phase 8 hardcoding debt.

### 2026-04-02 — 063a136 — SK48 cleared
- SK48 cleared via `sk48_snake` strategy. This clear later silently regressed in Apr 10+ runs.
- **Provenance for `[[lessons/silent_regression]]`**: SK48 is one of two documented silent regressions (LF52 is the other).

### 2026-04-02 — 2029c01 — FT09 full clear
- FT09 6/6 via `strat_lights_out` using sprite tags `Hkx`, `NTi`, `bsT`, `ZkU` — analytical GF(p) solve of lights-out puzzle.
- **Extreme brittle dependency**: reads specific tag strings. Later confirmed brittle when v2 version exposed obfuscated tag drift.

### 2026-04-03 — 102002c — SB26 perfect, RE86 6/8
- Two more analytical solvers stacked on sprite-tag reads (`vzuwsebntu`, `vfaeucgcyr`, `ozhohpbjxz` for RE86).
- Score jumped to 29%. Team flagged generalization risk; deferred to Phase 8.

### 2026-04-03 — 486e2ff — Hardcoding debt documented
- First explicit acknowledgment in CLAUDE.md that analytical solvers will not generalize.
- **Key decision**: keep building v1-maximizing hardcoded solvers as upper-bound baselines, commit to Phase 8 refactor later.

### 2026-04-10 — b84839e — SU15 full clear, 24/25 claimed
- SU15 9/9 via `strat_su15_vacuum` reading `game.hmeulfxgy/peiiyyzum/rqdsgrklq`. KA59 4/7 via hardcoded push sequences.
- Commit message claimed 24/25. Not verified with full regression at commit time.
- **Precedent for `[[lessons/trust_regression_not_commits]]`**.

### 2026-04-10 — 5e8562a — TN36 full clear, 25/25 claimed
- TN36 7/7 via `strat_tn36_puzzle` calling `frame.zpzcmabenn(val)` — a direct internal method call.
- Commit message claimed 25/25 / 69 levels / 37.9%. Again unverified at commit time.
- Next regression (same day at 14:17, before this commit) actually showed 22/25 / 56 levels.

### 2026-04-20 — Round 1 regression (this session)
- Ran 25-game ensemble regression; API now served 40 envs (12 games × 2 version hashes + 13 games × 1).
- **v1 primary**: 23/25, 67/182 (36.81%). Close to commit claims once TN36/SU15/KA59 boost counted.
- **v1 + v2 (40 envs)**: 31/40, 79/289 (27.34%). **9.47pp gap is the hardcoding tax**.
- v2 failures: SU15, TN36, RE86, KA59, S5I5, CN04 all 0 — brittle solvers broken by obfuscation drift.
- SK48 both versions fail (historic regression, never re-landed).
- LF52 single version fails (historic regression).
- **Recorded in**: `[[raw/regressions/v2_failures_20260420]]`, `[[lessons/v2_hash_obfuscation]]`, `[[lessons/silent_regression]]`.

### 2026-04-20 — Phase 8 wiki adoption
- Adopt Karpathy LLM-Wiki pattern; abandon vector-DB RAG (Kaggle-incompatible).
- Wiki seeded with 25 game pages + 15 game_type pages + 1 frame-only strategy + 1 brittle anti-pattern page.
- Decision: LLM model selection deferred to Task #11 benchmark (Qwen 3 8B vs Gemma 4 26B MoE vs Gemma 4 E4B).
- This commit history file created.

## Resolved silent regressions

- **LF52** (resolved 2026-04-21): root cause was `scripts/run_ensemble.py` running at `total_budget=20000` instead of the 50000 established at `b1cbc91`. `adaptive_c2` strategy still exists and clears LF52 L1 at 50K budget. Fix: bump runner budget to 50000 (matches class default). See `[[../wiki/debug/budget_starvation]]`.
- **SK48** (resolved 2026-04-21): same budget starvation root cause. `strat_sk48_snake` was removed in Phase 6 refactor (`380c3dc`) and re-added later, but silence at runtime was purely due to insufficient budget. At 50K, `sk48_snake` clears L1. Fix: same as LF52.

## Lessons extracted

- `[[../wiki/debug/budget_starvation]]` created to document this debug playbook.
- Runner-level budget overrides can silently starve strategies that the class defaults correctly size for. Always prefer the class default unless there's a stated reason to lower it.

## How to extend this file

- New major commit: add one entry with date, commit hash, score delta, architectural impact, and links to any lesson/debug page it motivates.
- Do not replay every commit — only the ones that future reasoning needs to know.
- Each entry should name a forward link (`[[lessons/...]]` or `[[debug/...]]`) that uses this commit as provenance.
