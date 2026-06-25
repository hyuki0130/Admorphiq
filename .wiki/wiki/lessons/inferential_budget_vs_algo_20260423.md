---
type: lesson
date: 2026-04-23
rounds: R20-R22
games: [SB26, TN36, KA59, WA30, SU15]
status: closed — failure modes characterised
---

# InferentialAgent failure modes — budget vs algorithm vs state-space (R20-R22)

> `scripts/probe_inferential_direct.py` ran the I-Agent against 10
> envs with a 50 000-action ceiling. Of the 6 envs that returned
> 0 levels, the action-spend distribution split into three distinct
> failure modes: budget exhaustion, early bail, and search-ceiling
> hit. Each mode demands a different fix. Conflating them — as
> earlier rounds did when reporting "0 levels on these envs" —
> hides which fix would help.

## Raw measurements

From `scripts/inferential_direct_results.json` (R20 direct test,
2026-04-23):

| Env  | Brittle baseline | I-Agent levels | Actions used | Elapsed (s) | Failure mode |
|------|------------------|----------------|--------------|-------------|--------------|
| AR25 | 2 | 1 | 9 260 | 262.0 | nav-regression (R20) |
| M0R0 | 2 | 1 | 7 267 | 248.8 | nav-regression (R20) |
| DC22 | 1 | 1 | 50 000 | 129.1 | budget-exhausted post-clear |
| FT09 | 6 | 1 | 50 000 | 32.4 | budget-exhausted, L2+ wrong cell selection |
| CD82 | 6 | 1 | 13 662 | 3.6 | L1 cleared; L2 plan-mismatch (early bail) |
| TN36 | 7 | 0 | **6 999** | 2.6 | early bail, no plan fits |
| SB26 | 8 | 0 | **33 405** | 78.5 | search-ceiling (BFS can't reach sort-state) |
| SU15 | 9 | 0 | **31 213** | 9.3 | merge plan zero-pair bail (see [[su15_l1_singleton_colors_20260423]]) |
| KA59 | 4 | 0 | **6 533** | 1.8 | early bail (dir probes silent — see [[ka59_v2_action6_semantic_20260423]]) |
| WA30 | 2 | 0 | **4 369** | 70.7 | early bail (multi-entity probe ambiguity) |

## The three modes

### 1. Budget-exhausted (DC22, FT09)

Plan fns ran to the 50 000 cap without converging. Symptoms:
`actions ≈ budget`, plan returns `(best_so_far, budget)`. The
algorithm is *running* on the env — every cap-extension would
buy more search. The fix is either a tighter cap (so the agent
re-routes faster) or a smarter heuristic (so the cap is enough).
DC22 cleared L1 in <500 actions then spent the remaining 49 500
on a wrong L2 cell-selection — a per-level cap with prefix-aware
re-observation would unstick this.

### 2. Early bail (TN36, KA59, WA30, SU15)

Plan fn returned `(0, k)` with `k ≪ budget`. The plan looked at
the entity map, decided the prerequisites weren't there, and bailed
without consuming actions. KA59's dir probes were silent (entire
movement plan exits in <100 ms). SU15's `_plan_merge` saw zero
same-color pairs and exited at 0.0s. WA30's `_plan_push_bfs`
couldn't isolate a single player. TN36 fits no current goal kind.

This is the *good* failure mode for the runtime LLM: a low action
spend means budget is preserved for a fallback. The current
WikiAgent loop, however, ignores the unspent budget and re-runs
observation_phase on the next plan attempt — which itself costs
~500 actions. R7f (per-env multi-turn) is the architectural fix:
read the trace, propose a different plan, retry within the same
budget pool.

### 3. Search-ceiling (SB26)

Plan fn ran to a state cap (BFS `max_states ≈ 15 000`) without
finding a path to a level-clear state. Symptoms: `actions ≪ budget`
but `elapsed ≫ early-bail elapsed`. SB26's 33 405 actions / 78.5 s
is search effort, not env interaction (the BFS solver consumes
actions while expanding states). The fix is algorithmic: a bigger
state cap won't help (state space is combinatorial), but a
domain-aware encoding (sort-order pairs, not raw frame hash)
would.

## Decision matrix per mode

| Mode | Diagnostic signal | LLM should | Code change |
|---|---|---|---|
| Budget-exhausted | actions ≈ cap | extend per-level cap OR pick a different plan | per-level cap parameter |
| Early bail | actions ≪ cap, elapsed < 1 s | request fallback plan with same budget | R7f multi-turn |
| Search-ceiling | actions intermediate, elapsed > 30 s | swap to domain-aware encoder | new plan fn |

The runtime LLM can read these signals from the trace
(`actions`, `elapsed`, `levels`) without instrumenting the plan
internals.

## Falsification

The matrix above is wrong if a plan exits with high `actions` AND
high `elapsed` AND `actions ≈ cap`: that is search-ceiling-like
behaviour but masquerading as budget-exhausted. None of the 10
R20 probe envs hit that combination, but the runtime LLM should
treat `(actions ≈ cap, elapsed > 30 s)` as ambiguous and ask
for a probe re-run before deciding.

## Related

- [[../strategies/frame_only/inferential_agent]]
- [[../lessons/prefix_aware_navigation_20260423]] — R20 nav regression context
- [[../lessons/su15_l1_singleton_colors_20260423]] — SU15 early-bail detail
- [[../lessons/ka59_v2_action6_semantic_20260423]] — KA59 early-bail detail
- [[../lessons/sokoban_search_explosion_20260423]] — search-ceiling reasoning

## Sources

- `scripts/probe_inferential_direct.py` — direct-test harness
- `scripts/inferential_direct_results.json` — raw measurements
- R20 commit `afe6ab8`, R22 commit (nav fix)
