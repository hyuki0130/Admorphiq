---
type: log
description: Append-only chronological record of every dev-time round and significant infra change. Grep `^## \[` for latest entries.
purpose: append-only chronological record of wiki ingest events, dev-time rounds, and significant infra changes
schema: each entry begins with `## [YYYY-MM-DD round RN]` so `grep "^## \[" log.md | tail -N` returns the latest N entries
---

# Admorphiq Wiki Log

Per Karpathy LLM-Wiki §7.2 (`docs/llm_wiki_karpathy_analysis_ko.md`):
chronological append-only log so any LLM (Claude Code at dev-time,
Qwen at Kaggle-time after retrieval) can answer "when was X last
visited / what changed in round N" via grep instead of git
spelunking.

Entries below are backfilled to seed the timeline (2026-04-21 →
2026-04-29). Future rounds MUST append a fresh entry as part of the
commit; the `remind_wiki_sync.sh` hook flags impl commits without a
wiki touch but does not yet check log.md specifically — that lands
when R23c upgrades the schema.

---

## [2026-04-20 setup] Phase 8 wiki seeded under .wiki/

Initial Karpathy LLM-Wiki seed: schema.md, raw/, wiki/concepts/,
lessons/, debug/, reasoning/, games/, game_types/, strategies/.
~65 pages, ~70 MD files, 416 KB.
Provenance: commit `ec8e81d`.

## [2026-04-20 setup] Phase 7 closed, hash-rotation reality check

API rotated all env hashes overnight; brittle attr-readers (su15_vacuum,
re86_analytical, ka59_sokoban, s5i5_slider, zig3_A2A4) silently dropped
to 0. v1 score 36.81% became un-chaseable. Phase 7 cancelled.
Pages touched: lessons/api_hash_rotation_20260421, lessons/v2_hash_obfuscation.
Provenance: `7a310cb`.

## [2026-04-21 R1] Three-layer architecture doc

`.wiki/wiki/architecture.md` lock: Cognition / Memory / Action layers
+ dev-time vs Kaggle-time split + R1-R6 round skeleton.
Pages touched: architecture (new), schema.
Provenance: `8909077`.

## [2026-04-21 R2] Feature-rich DiscoveryReport

Added dir_map, player_color, movable_region_count, click_responsive_cells,
change_topology, color_histogram, symmetry_score. 23 unit tests.
Hypothesis schema gains confidence + features_missing.
Provenance: `7101241`.

## [2026-04-21 R3] Universal strategy dispatcher

Introspector auto-registers 67/74 strategies via inspect.signature.
Runtime-only-arg strategies (sustained / zigzag / extended_winner /
continue_multilevel / move_click / navigate / graph_explore) skipped.
Files: src/admorphiq/hypothesis/dispatcher.py (new).
Provenance: `e638a99`.

## [2026-04-21 R4] Reflection split — deterministic + LLM stub

scripts/analyze_trace.py (deterministic, no LLM) + reflect_wiki_agent.py
(LLM stub; Qwen 8B/14B too weak for structured reflection on 40-env
trace — kept for future stronger model). Architecture doc updated:
dev-time Cognition = Claude Code; Qwen = Kaggle-time only.
Provenance: `ddb33b2`.

## [2026-04-21 R5] Regression gate

scripts/regression_gate.py + scripts/regression_baseline.json. Strict
by_game_id (fail on drop) + informational by_title (best across hashes).
10 unit tests.
Provenance: `ad4b4c0`.

## [2026-04-21 R6] Live-env bench: 8B vs 14B with R2+R3

8B: 10/25 unique / 15/40 raw / 29 levels — gate PASS.
14B: 13/25 unique / 21/40 raw / 23 levels — gate FAIL (FT09, CD82).
Decision: 8B stays primary; 14B can't be promoted until Python
enforcement layer for selector rules lands.
Pages touched: lessons/selector_is_advisory_not_enforced_20260421.
Provenance: `3a6cde0`.

## [2026-04-21 R7a/c/e] Structured feedback schema + English prompt + whitelist filter

Hypothesis.features_missing → list[FeatureGap]. wiki_gaps, wiki_needs,
doubt added. Qwen system prompt rewritten in English with carryover
slot for round_learnings. _validate_whitelist drops hallucinated names.
11 R7 schema tests. Smoke verified against HallucinatingLLM mock.
Provenance: `4290441`.

## [2026-04-21 R7b] Graph-based wiki retrieval (Karpathy pattern executed)

src/admorphiq/hypothesis/wiki_retrieval.py with GraphRetriever.
Seeds from selector + reasoning/core + game_types + games/<TITLE>;
walks [[backlinks]] in keyword-scored order to 16K char budget.
24 unit tests. Suite 210/210.
Provenance: `386e047`.

## [2026-04-21 R7d] Round protocol formalised

scripts/round.py with start / finalize / learnings subcommands.
Writes .omc/rounds/round_NNN/{meta.json, notes.md}.
9 unit tests. .omc/rounds/round_001 initialised.
Provenance: `a52eae6`.

## [2026-04-21 round 1] First R7 bench — schema enforcement

Goal: match baseline 10/25 envs / 29 levels without regressions; prove
graph retrieval surfaces game-specific pages. Result: 15/40 raw envs /
19 levels — env coverage = baseline, hallucinations crushed to 0, but
levels -17 because 4 games (FT09 / CD82 / SB26 / AR25) lost game-
specific fallback picks. Gate verdict FAIL.
Provenance: `142cdce`.

## [2026-04-21 round 2] Title-match + rule-4 Python reinforcement

Added _augment_with_title_match + _augment_click_only_rule4 in
wiki_agent.py. 20/40 envs / 37 levels. FT09 0→6, SB26 0→8 recovered;
CD82 still 1, AR25 -2 unrecovered. Gate FAIL.
Provenance: `eced2cd`.

## [2026-04-21 round 3] Rule-3 hybrid Python reinforcement

_augment_hybrid_rule3 added: when avail ⊇ {1..4} AND 6 ∈ avail,
inject {bfs_state_space, paint_game, click_toggle_detect} into
fallback_stack. 26/40 envs / 47 levels (R1→R3: 19→37→47, +28).
CD82 stuck 1/6 (run() loop breaks on first success, paint_game
never runs). G50T regressed 1→0 (Ollama uniqueItems didn't honor).
Gate FAIL.
Pages touched: many — but rolled back next round.
Provenance: `3a6cde0`.

## [2026-04-21 round 4] Wiki-first routing — rollback Python helpers

User directive: stop patching LLM mistakes with Python helpers; wiki
enrichment is the only lever. Deleted _augment_with_title_match,
_augment_click_only_rule4, _augment_hybrid_rule3. Selector rule 3 split
into 3a/3b/3c. New concept page probe_signature.md. Three-layer
enforcement: tests/test_classify_contract.py + .claude/hooks/
guard_wiki_agent.sh + .claude/hooks/run_contract_tests.sh. CLAUDE.md
"Prohibited Patterns" section. 40/40 envs / 31 raw levels / 22 unique.
Gate FAIL but **first measured wiki-only routing success: CD82 0→6**.
Pages touched: selector, concepts/probe_signature (new), prohibited
patterns in CLAUDE.md.
Provenance: `19974e8`.

## [2026-04-22 round 5] Generic G1-G4 inference + brittle purge

Purged 12 brittle strategies (paint_game, lights_out, sb26_sort, etc.)
from default_strategy_registry. Added G1-G4: interactive_grid_toggle,
sprite_cluster_interaction, push_bfs_grid, bfs_framehash. selector.md
references G1-G4. 11/25 unique / 27 raw levels / 15 unique. Diagnostic:
**G1-G4 picked 0 times** — Qwen anchored on bfs_state_space (26) and
click_rare (14). Gate FAIL.
Provenance: `51475e2`.

## [2026-04-22 round 6] InferentialAgent 5-phase pipeline

scripts/probe_generics_direct.py revealed G1-G4 were brute-force-with-
fixed-thresholds, scored 0-1/47 across 10 envs. User directive:
redesign as real inference agent (Chollet framing). Implemented
strat_inferential_agent (528 lines, 5 phases). Decision_tree.md added
as compact LLM context. Direct test: 6/47 cleared.
Pages touched: strategies/frame_only/inferential_agent (new),
llm_context/decision_tree (new), lessons/g1_g4_direct_test_20260422 (new).
Provenance: `413a089`.

## [2026-04-22 round 7] I-Agent refinements + compact LLM anchor measured

Plan budget caps (nav 10k, toggle 15k, merge 12k, paint 12k). Toggle
plan rewrite (cluster centroids + corner samples + depth 4). Merge
plan vacuum-radius calibration. Bench: 17/40 raw / 23 levels (vs R5
27). decision_tree.md improved Qwen decisiveness (raw 15→23) but
I-Agent picks remained 0 — Qwen still anchored on bfs_state_space (25)
and click_rare (15). Gate FAIL.
Provenance: `66d6cf2`.

## [2026-04-22 round 8] Anchor-ban (FAIL, anchor-whack-a-mole)

ANCHOR_BANNED_STRATEGIES = {bfs_state_space, click_rare}. Registry
60→58. Qwen primary distribution shifted to bfs_explore (22) +
click_rotation_puzzle (14). 4/40 envs / 4 levels (vs R7 17/40 / 23).
Gate FAIL — partial purging produces whack-a-mole.
Provenance: `76bd22d`.

## [2026-04-22 round 9] Ultra-minimal allowlist (FAIL, name-preference)

LLM_WHITELIST_ALLOWLIST = {inferential_agent, click_toggle_detect,
click_all_colors, click_color_order}. Registry 4. Qwen picked
click_toggle_detect 11/11 — actively avoided "inferential_agent"
string. Aborted at 11/40.
Provenance: `6d9ec73`.

## [2026-04-22 rounds 10-11] Rename + single-item allowlist

R10: aliased strat_inferential_agent → strat_adaptive_bfs_solver.
4-item allowlist with new name. click_toggle_detect still 11/11.
R11: collapsed to {adaptive_bfs_solver}. Schema relaxed (uniqueItems
only when whitelist ≥ 4). Qwen picked adaptive_bfs_solver 40/40 envs.
14/40 envs / 20 levels — true wiki-only baseline.
**Architectural takeaway: Wiki-First Routing now end-to-end enforced.**
Pages touched: dispatcher (allowlist), wiki_agent (schema relaxation),
decision_tree (compact rewrite).
Provenance: `b500119`.

## [2026-04-23 round 12] Observation HUD masking

Pixels changing under ≥80% of probes identified as HUD/timer; subtracted
from per-probe diff_magnitude / bbox / centroid / region_kind.
Bench: 20 raw / 14 cleared — identical to R11. HUD masking cleaned up
entity-detection false positives (CD82 71→2 responsive clicks; palette
67→0) but didn't change plan outcomes. Bottleneck = plan execution
layer, not observation quality.
Pages touched: strategies/frame_only/inferential_agent (HUD note added).
Provenance: `84e53d1`.

## [2026-04-23 round 13] click_then_move plan

_plan_click_then_move added for hybrid games (CD82 pattern: button
press + 2-step movement). No bench lift in WikiAgent run.
Provenance: `a70bf92`.

## [2026-04-23 round 14] lights_out plan + stride-4 obs retry

Default observation stride 8 → 4 on retry pass after first plan fails.
FT09 stride-2 found 72 responsive cells when stride-8 found 0.
FT09 +1 / LP85 +1 in direct probe.
Provenance: `173b399`.

## [2026-04-23 round 15] Cumulative prefix chaining (architectural)

_ACTIVE_PREFIX + _LAST_WIN_SEQUENCE globals. _reset_then_replay()
helper. Outer loop appends winning sequence after each level clear so
subsequent levels start from correct state, not game start.
**Multi-level progression infrastructure**.
Provenance: `e88fb7b`.

## [2026-04-23 round 16] Lights-out toggle stencil measurement

`_measure_toggle_stencil` and `_extract_cell_class`. n+1 resets +
n single clicks → A[i][j] uint8 stencil + base/toggled cell classes.
6 unit tests. Suite 249/249.
Pages touched: NONE (process violation — backfilled in R22).
Provenance: `377ca48`.

## [2026-04-23 round 17] GF(2) solver + predictive ranking

`_gf2_solve` (Gaussian elimination over GF(2)),
`_homogeneity_score`, `_rank_subsets_by_prediction`. Top-K ranked
subsets tried in env before naive 2^n enumeration. 5 unit tests.
Suite 254/254.
Pages touched: NONE (process violation — backfilled in R22).
Provenance: `009a6be`.

## [2026-04-23 round 18] Delta-chain trials + cumulative sweep

Replaced per-trial reset_then_replay with xor-delta chaining (lights-
out clicks are commutative + self-inverse). 64 trials × 375-step prefix
→ 1 reset + ~320 clicks. Cumulative 40-cell single-click sweep before
stencil measurement catches click-the-right-button games. FT09 L1
clears via generic path. L2 stencil density 91-100% under top-diff
selection — buttons elsewhere; deferred to runtime self-heal.
Pages touched: NONE (process violation — backfilled in R22).
Provenance: `8c41623`.

## [2026-04-23 round 19] KA59 sokoban budget bump + diagnosis

navigation cap raised 10k→30k when goal=navigation AND merge_items≥3
(Sokoban-like signature). probe_ka59 + probe_ka59_raw scripts. Direct
finding: 2-player Sokoban state space (~24^10) exceeds BFS ceiling at
any budget. KA59 stays at 0; needs specialised _plan_push_bfs.
Pages touched: NONE (process violation — backfilled in R22).
Provenance: `fcc39ea`.

## [2026-04-23 round 20] Prefix-aware _plan_navigation (caused regression)

Rewrote `_plan_navigation` to call BFSSolver.solve directly with
prefix=_ACTIVE_PREFIX. Discovered ensemble's strat_bfs_state_space
ignored _ACTIVE_PREFIX, re-solving L1 every iteration. Direct probe
confirmed AR25 1/2 + M0R0 1/2 regression vs R6 baseline 2/2 each
(single-solve instead of solve_all_levels).
Pages touched: NONE (process violation — backfilled in R22).
Provenance: `afe6ab8`.

## [2026-04-23 round 21] SU15 merge_items detection loosening

entity_phase merge_items: loosened from "same-color pair only" to
"size 8..150 OR same-color pair". SU15 surfaces 4 merge_items and
goal_phase classifies as merge — but `_plan_merge` still bails on L1
because it requires same-color pairs.
Pages touched: NONE (process violation — backfilled in R22).
Provenance: `ce95929`.

## [2026-04-23 round 22] Nav multi-level fix + framing correction + wiki backfill

Two-part round.
**(a) Code fix**: restored solve_all_levels-style internal chaining
inside `_plan_navigation` (while True: solve, extend prefix, repeat).
3-env probe: AR25 2/2 ✅ M0R0 2/2 ✅ DC22 1/1 ✅. R20 regression resolved.
**(b) Framing correction**: user directives clarified Qwen's role —
not just routing, but game-completion driver (comprehend / pick /
execute / self-heal / propose code fixes). Claude Code is the
implementation helper. R11 single-item allowlist tagged for rollback
in R23.
**(c) Wiki backfill**: 4 lesson + 1 concept + 4 game-page updates
covering R16-R21 gaps. .claude/hooks/remind_wiki_sync.sh hook added.
2 new memory entries (feedback_llm_drives_loop,
feedback_generic_not_game_specific).
Pages touched: concepts/gf2_toggle_stencil (new),
lessons/gf2_lights_out_stencil_20260423 (new),
lessons/prefix_aware_navigation_20260423 (new),
lessons/sokoban_search_explosion_20260423 (new),
games/FT09 / CD82 / KA59 / SU15 (provenance updates).
CLAUDE.md (Phase 8 — LLM-as-game-completion-driver section + R23+
roadmap).
Provenance: `a43dea4`.

## [2026-04-23 docs] Karpathy LLM Wiki analysis archived

User-provided Korean analysis of Karpathy's "LLM Wiki" gist saved at
docs/llm_wiki_karpathy_analysis_ko.md. CLAUDE.md links to it.
Memory entry reference_karpathy_llm_wiki.md points to the doc.
5 new TODO items (#40-#44, R23a/b/c, R24b, R25b) absorb the gap table:
log.md missing, lint pass missing, ingest ritual not enforced,
query→page refiling not systematic.
Pages touched: docs/llm_wiki_karpathy_analysis_ko.md (new), CLAUDE.md.
Provenance: `49e05c7`.

## [2026-04-29 R23a] log.md created (this file)

Backfilled R1-R22 + setup commits + docs. Future rounds MUST append
a fresh entry per commit; the schema check lands in R23c.
Pages touched: log.md (new).
Provenance: `d6b9138`.

## [2026-04-29 R23b] index.md generator categorised + frontmatter fallback

Rewrote `scripts/generate_wiki_index.py` to surface 10 categories
separately (concepts / lessons / debug / reasoning / llm_context +
existing games / game_types / strategies). One-liner fallback chain:
blockquote `> ...` → frontmatter `description` → `purpose` → `type`.
status_v1_brittle / status_v1_generic both rendered so generic-vs-
brittle gap is visible. log.md frontmatter gains `description` field.
80 pages indexed across 10 categories.
Pages touched: scripts/generate_wiki_index.py, .wiki/wiki/index.md,
.wiki/wiki/log.md (frontmatter).
Provenance: `45fc709`.

## [2026-04-29 R23c] schema.md — ingest ritual + runtime-consumable fields

`.wiki/schema.md` gains two load-bearing sections:

  - **Ingest Ritual** (Karpathy §6.1) — mandatory per-round
    checklist: log.md append, games/<G>.md provenance update,
    new lessons/<topic>_<date>.md when round produced a
    falsifiable claim, new concepts/<concept>.md when reusable
    abstraction emerged, strategies/frame_only/<plan>.md update
    with runtime-consumable fields, debug/<symptom>_playbook.md
    when reproducible failure mode measured, index.md regeneration.
  - **Runtime-Consumable Signature Fields** — four required prose
    sections per plan-fn / mechanic page: Observable Signature /
    Falsification Signature / Tunable Parameters / Next-Best.
    Without them, the runtime LLM can call the plan but cannot
    decide when to stop. R16-R22 pages grandfathered but back-filled
    when next edited.

Reference link to docs/llm_wiki_karpathy_analysis_ko.md added.
Pages touched: .wiki/schema.md, log.md (this entry).
Provenance: `96330a7`.

## [2026-04-29 R24b] wiki_lint.py — periodic health check (Karpathy §6.3)

`scripts/wiki_lint.py` walks `.wiki/wiki/**/*.md` and reports
4 finding kinds: orphan pages (no inbound `[[backlinks]]`),
missing cross-refs (unresolved `[[link]]`), stale claims
(frontmatter status_v1 contradicts regression_baseline.json),
R23c gaps (plan-fn pages missing the 4 runtime-consumable
sections). Output: markdown report on stdout + JSON at
`scripts/wiki_lint_report.json`. Exit 0/1/2.

False-positive guards: skip metalinguistic terms (`backlinks`,
`link`, `page`), skip template placeholders (`<` `>` in target),
skip directory-shaped links, resolve `raw/...` against `.wiki/`.
Initial run on the current wiki: 18 orphans + 9 missing-xref + 13
stale-claims + 2 R23c gaps surfaced — these are real maintenance
items, not lint bugs. Future rounds will burn down the list.

Pages touched: scripts/wiki_lint.py (new), log.md (this entry).
Provenance: `45d3621`.

## [2026-04-29 R25b] schema.md — Query→Page refiling ritual

Adds a "Query → Page Refiling" section to `.wiki/schema.md` per
Karpathy §6.2. Lists 4 refiling triggers (falsifiable claim,
regression bisect, manual analysis, failed plan-fn iteration) and
maps each to its target page kind. Anti-pattern called out:
finding stays in `scripts/probe_*.json` or `/tmp/` only — cache
not memory. R16-R22's R22 backfill is named as the cautionary
example. Future-round work to add a round-without-lesson lint
check is noted but deferred (needs heuristic for legitimate
no-lesson rounds).
Pages touched: .wiki/schema.md, log.md (this entry).
Provenance: this commit.

## [2026-05-08 R23 — v5 final] Anchor pathology resolved by 7 code/wiki bug fixes

User pushback after v3 anchor diagnosis ("자꾸 모델 한계라고 하지말고 제대로
읽게 하려면 어케 하는지 좋을지 제대로 분석해서 다시 진행해봐!") triggered a
proper systematic audit of the LLM call path. The "model anchor" framing of
v1-v3 was wrong — anchor was the OBSERVABLE OUTCOME, not the CAUSE. Audit
found 7 distinct code/wiki bugs:

| # | Bug | Fix | Verified in |
|---|---|---|---|
| 1 | retrieval seed pages saturate 16K budget; R27/R26a/R24 pages 0/40 retrieve | budget 16K → 24K → 32K, plan_failure_signatures forced into seed list | v3, v5 |
| 2 | _PROMPT_TEMPLATE "low confidence → bfs_state_space" hardcoded anchor | rewritten: "low confidence → adaptive_bfs_solver" | v4 |
| 3 | _PROMPT_TEMPLATE example referenced brittle su15_frame_only (not in allowlist) | example removed; peer-pick rule explicit | v4 |
| 4 | selector.md recommended 6 strategies NOT in 13-allowlist (interactive_grid_toggle, sprite_cluster_interaction, push_bfs_grid, bfs_framehash, graph_explore, raster) | rewrote selector.md table to use only allowlist names | v4 |
| 5 | Ollama JSON schema uniqueItems not enforced by Qwen 8B/14B → fallback duplicates | Python post-process dedupe in classify() | v4 |
| 6 | classify max_tokens=512 too small for verbose 14B output → JSON truncated → empty hypothesis (BP35 trace) | bumped to 1536 | v5 |
| 7 | selector.md rule 4 "avail == [6]" ambiguous → 14B applied click_rare to envs with movement actions (SC25 misclassified) | added "EXACTLY" wording + new prelude warning | v5 |

Bench progression:

| Variant | Cleared | Levels | Distinct primaries | Click_rare anchor share |
|---|---|---|---|---|
| 8B v1 (R23 baseline) | 17 | 23 | 2 | 32% |
| 14B v1 | 19 | 27 | 2 | 30% |
| 14B v3 (retrieval fix) | 19 | 27 | 2 | 45% |
| 14B v4 (prompt + selector + dedupe) | 17 | 23 | 2 + 1 empty | **62%** ← worse before better |
| **14B v5 (max_tokens + budget + rule 4)** | **18** | **26** | **3** ✅ | **0%** ✅ |

v5 final state:

  primary distribution:
    bfs_state_space    24/40 (60%) — movement/hybrid envs (correct)
    click_select_move  12/40 (30%) — NEW (3rd primary)
    click_toggle_detect  4/40 (10%) — NEW (4th unique pick path)
  fallback distribution:
    click_toggle_detect 33  click_select_move  13
    spell_cast           9  adaptive_bfs_solver 3  ← first emergence
    bfs_state_space      2  click_color_order   1
  retrieval — backlink walk activated:
    seed pages (5): 40/40
    game_types/hybrid.md   19/40 (48%)  ← backlink, util 14.6%
    game_types/click.md    13/40 (32%)  ← backlink, util  9.2%
    game_types/movement.md  8/40 (20%)  ← backlink, util  6.8%
  rule_compliance vs decision_tree.md: 50% (was 35-60% across v3-v4)
  click_rare anchor: 0/40 primary picks (rule 4 disambiguation)

Cleared envs delta v3 → v5: SC25 +2 (recovered via spell_cast fallback),
CD82 -1 (different plan tried, BP35-style L1 missed). Net +1 env / -1 level
in unique-title-best terms; raw +1 env.

Brittle gap (FT09 -6, SB26 -8, CD82 -6 in by_game_id strict gate) unchanged
since all three need plan-fn algorithm work (R28 sprints), not LLM routing
diversity.

Pages touched: src/admorphiq/hypothesis/wiki_agent.py (prompt template +
classify max_tokens + context_chars + dedupe), src/admorphiq/hypothesis/
wiki_retrieval.py (per-page sizes, seed list expanded with
plan_failure_signatures), .wiki/wiki/selector.md (full rewrite to
13-allowlist + rule 4 disambiguation), tests/test_wiki_retrieval.py
(plan_failure_signatures seed assertion), log.md (this entry).

Conclusion stated for posterity: **Karpathy LLM-Wiki pattern works end-to-end
on Qwen 3 14B Q4 once the prompt + retrieval + decoder constraints are
consistent with the actual allowlist.** "Model anchor pathology" v1-v3
diagnosis was a measurement artifact of accumulated code/wiki bugs.

Provenance: scripts/wiki_agent_results_r23_14b_v{3,4,5}.json,
scripts/analyze_wiki_agent_v{1_8b,3,4,5}.json, this commit.

## [2026-05-06 R23 — 8B] Allowlist reopen → Qwen 8B anchor pathology re-confirmed

R27 backfilled the four runtime-consumable sections onto every plan-fn
page. The bet was that explicit Falsification Signature → Next-Best
mappings would dislodge Qwen 3 8B's anchor on `bfs_state_space` /
`click_rare`. R23 expanded `LLM_WHITELIST_ALLOWLIST` from
`{adaptive_bfs_solver}` → 13 frame-only strategies, emptied
`ANCHOR_BANNED_STRATEGIES`, and rewrote `decision_tree.md` to reference
the 4 sections.

**Bench** (40 envs, qwen_3_8b_q4, 2268s):
- 17/40 envs cleared, 23 raw levels, 10 unique titles cleared.
- vs R11 (single allowlist baseline 14/40, 20 levels): +3 envs / +3
  levels / -47% runtime.
- vs 2026-04-21 baseline (regression_gate.py): FAIL — FT09 -6, SB26
  -8, CD82 -5 = -19. All three are R5-purged brittle clears, not R23
  regressions; the baseline was seeded pre-purge.

**Primary distribution** (the load-bearing measurement):

  bfs_state_space   27/40  (68%)
  click_rare        13/40  (32%)
  adaptive_bfs_solver  0/40  (0%)
  other 11 entries     0/40  (0%)

**Verdict — anchor pathology confirmed**: 4 rounds of wiki strengthening
(R3 universal dispatcher, R4 reflection, R7b graph retrieval, R27 4
sections per plan-fn) have not changed Qwen 3 8B's behavior. 8B picks
two familiar BFS-shaped names regardless of probe signature, regardless
of selector rules, regardless of plan-fn falsification signatures.

**Decision**: escalate to Qwen 3 14B (R23 — 14B follow-up). 14B was
measured in R6 to produce env diversity (13/25 unique vs 8B 10/25)
and is now usable because R7e's `_validate_whitelist` handles
hallucinated names.

**Implication for the plan**:
- If 14B breaks the anchor → promote to primary, implement R25 R7f
  multi-turn on top.
- If 14B also anchors → wiki-driven LLM routing has a measured
  ceiling at ≤14B class. Pivot to R28 sprints (plan-fn algorithm
  improvements) which produce levels independent of LLM pick
  diversity.

Pages touched: src/admorphiq/hypothesis/dispatcher.py (allowlist
expansion), .wiki/wiki/llm_context/decision_tree.md (rewrite),
log.md (this entry).
Provenance: this commit + R23 trace `wiki_agent_results_r23.json`.

## [2026-05-06 R27] Plan-fn runtime-consumable fields backfill

R27c (`schema.md` Runtime-Consumable Signature Fields) defined four
required prose sections per plan-fn / mechanic page:

  ## Observable Signature
  ## Falsification Signature
  ## Tunable Parameters
  ## Next-Best

Without those four, the runtime LLM can call the plan but cannot
decide when to stop calling it. R27 backfills the gap that
`scripts/wiki_lint.py` flagged on `bfs_state_space.md` and
`inferential_agent.md`, and adds the six missing plan-fn pages
(`PLAN_FNS = {navigation, merge, paint_fill, toggle, lights_out,
click_then_move}`) so every entry the inferential agent's outer loop
can call has its own runtime-consumable wiki page.

  - `strategies/frame_only/bfs_state_space.md` — appended 4 sections
    (cross-link to navigation as the prefix-aware wrapper).
  - `strategies/frame_only/inferential_agent.md` — appended 4 sections
    (cross-link to all 6 inner plan fns + `selector` rule 9).
  - `strategies/frame_only/navigation.md` — new page; documents
    R20-R22 prefix-aware multi-level chaining, BFSSolver delegation,
    failure modes from
    [[lessons/inferential_budget_vs_algo_20260423]].
  - `strategies/frame_only/merge.md` — new; documents R7 vacuum-radius
    calibration, 5-position pair candidates, R21 entity loosening,
    SU15 L1 falsification signature.
  - `strategies/frame_only/paint_fill.md` — new; palette → cells →
    executor sequence with the CD82 multi-level limitation cross-
    linked to [[lessons/cd82_paint_palette_signature_20260423]].
  - `strategies/frame_only/toggle.md` — new; R7 candidate-pool
    widening (cluster centroids + corner samples + responsive probes)
    with depth-3 / depth-4 retry tunable.
  - `strategies/frame_only/lights_out.md` — new; full R16-R18 GF(2)
    algorithm (cumulative sweep → stencil → GF(2) solve → predictive
    rank → delta-chain trials → naive fallback).
  - `strategies/frame_only/click_then_move.md` — new; R13 hybrid plan,
    HUD-mask precondition, pass-1 / pass-2 search structure.

Why this matters: per [[../schema]] R23c, the four sections are the
LLM's runtime reasoning surface. With them in place, future R23
(allowlist reopen — Qwen sees all ~14 frame-only strategies) can
expect the LLM to actually swap plans on falsification rather than
re-anchoring on whatever was the last winning name.

Pages touched: 2 strategy pages (edit), 6 strategy pages (new),
log.md (this entry).
Provenance: this commit.

## [2026-05-06 R26a] Probe-output refile sweep — 5 new lessons + 1 boost

Executes the Karpathy §6.2 query→page refiling ritual on probe
outputs from R12-R22 that were never refiled into wiki pages.
Five new lesson pages plus a numerical/narrative boost on the
existing G1-G4 lesson:

  - `lessons/su15_l1_singleton_colors_20260423.md` — R21 finding
    that SU15 L1 has zero same-color fruit pairs, so the merge
    plan early-bails at 0.0 s. Falsification signature for
    "merge plan correct in kind, wrong in phase."
  - `lessons/ka59_v2_action6_semantic_20260423.md` — R19 finding
    that v2 KA59's direction probes return `dir_pixels=0` because
    ACTION6 was added with a selection-then-move mechanic. The
    `probe_signature` uniformity rule misclassifies the env.
  - `lessons/cd82_paint_palette_signature_20260423.md` — R12+R20
    finding that HUD masking collapses 71 false-positive responsive
    cells to 2 real cells with shared centroid; that two-cell
    signature is the L1 paint signature `_plan_navigation` keys on.
  - `lessons/inferential_budget_vs_algo_20260423.md` — R20-R22
    failure-mode taxonomy: budget-exhausted vs early-bail vs
    search-ceiling, with action/elapsed signatures. Lets the
    runtime LLM read the trace and pick the right fix.
  - `lessons/ft09_stride_button_drop_20260423.md` — R14 finding
    that stride-8 lands on FT09 cell borders (8 px grid alignment);
    stride-4 retry surfaces 72 responsive cells. Generalises to
    any "default-stride dead, fine-stride alive" trace.
  - `lessons/g1_g4_direct_test_20260422.md` — boosted with the raw
    per-strategy actions/elapsed table from
    `scripts/g1_g4_direct_results.json` (KA59 push_bfs 48 012/4.1 s,
    SB26 bfs_framehash 37 688/34.8 s, etc.) and cross-links to the
    new R26a lessons.

Game pages cross-linked: `games/SU15.md`, `games/KA59.md`,
`games/CD82.md`, `games/FT09.md` — each gains 1-2 lesson links
in the "Lessons Learned" section.

Why this matters: per Karpathy LLM-Wiki §6.2, findings that stay
in `scripts/probe_*.json` are cache, not memory. The Kaggle-time
LLM has no access to those caches; only `.wiki/wiki/**` ships
with the submission. R22's backfill covered R16-R22 partially;
R26a is the audit-and-completion pass.

Pages touched: 5 lessons (new), 1 lesson (edit), 4 game pages
(cross-link), log.md (this entry).
Provenance: this commit.

---

## [2026-06-25 R16] Wiki retrieval efficiency: authoring skill + graph hygiene; seed reorder benched and reverted

Triggered by the karpathywiki / obsidian-skills question. Clarified the
authoring model (Claude Code writes dev-time; Qwen only reads at
Kaggle-time, no skill runtime). Shipped a dev-time `wiki-authoring`
skill (`.claude/skills/`). Fixed a `wiki_lint` accuracy bug —
`check_orphans`/`check_missing_xrefs` blanket-skipped relative `../`
links — cutting false orphans 14→1 and surfacing the true broken-link
count (8→33). Graph hygiene fixed all 33 dead-links + authored 5
missing live-strategy pages (click_rare / spell_cast / seq_repeat /
seq_search / explore_interact, R23c-compliant) + connected the TU93
orphan; index 92→97.

Benched the seed reorder (B2: env-specific seeds before generic prose)
on 14B: REGRESSED 14→8 levels (routing shifted click_select_move 12→0,
click_toggle_detect 4→19). Reverted. Confirmation bench (B2 reverted,
hygiene+pages kept) returned 14 levels with the identical pick
distribution to the R23 reference — proving the graph-hygiene changes
are routing-neutral and B2 was the sole regression.

Pages touched: lessons/seed_reorder_regression_20260625 (new),
reasoning/wiki_retrieval_recipe (cross-link), 5 strategies/frame_only/*
(new), ~9 link-fix pages, index.md, log.md (this entry).
Provenance: this commit. Bench traces: scripts/wiki_agent_results_r16_14b*.json.
