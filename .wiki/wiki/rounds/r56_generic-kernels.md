---
type: reasoning
round: R56
axis: generic-kernel-library
verdict: IN-PROGRESS
keywords: [generic-kernels, namespace-safe, script25, agent25, dual-scoreboard, declared-intent, primitive-firewall, kernel-library, quarantined-adapter]
commit: [4303662, 3edcf4d, 1d797d7, 62fac21, f13b433, d377121, a2a62f0, b67cb39, de013aa, 69101ea]
date: 2026-07-15
---

# R56 — Generic namespace-safe kernel library (Primitive Firewall and Scripted Composition)

> Extract game-agnostic pure-computation kernels from the 25-game solver card so a
> quarantined script — and eventually an LLM composing declared intents — can reach
> comparable coverage without building a second public-trained brain.

## Codex verdict (binding)

Full text: `docs/r56_codex_toolbase_verdict_20260715.md` (committed `4303662`).
Consultation trigger: a user proposal that the hand-built tool layer ALONE should
clear all 25 public games as the LLM's foundation.

**Rejected**: "finish the current LLM-free solver card to 25/25" as the R56
objective. That optimizes PUBLIC semantic coverage, and the measured hidden-LB
transfer (0.14–0.20 despite a major public gain — see
[[../lessons/lb_top_team_research_20260714]]) is evidence this axis is saturating.

**Adopted**: build a namespace-safe generic kernel library such that thin,
quarantined scripts can compose it to clear the public games, while the LLM can
compose the SAME kernels online on unseen games. Two separate scoreboards:
`script25` (kernel EXPRESSIVENESS — quarantined scripts, public adapters never
model-visible) and `agent25` (LLM COMPETENCE — the LLM receives only the kernels
and must supply roles/goals/hypotheses itself). A public `script25` improvement
does NOT promote anything on its own; only `agent25` non-inferiority + hidden/proxy
transfer non-regression do. The original decomposition proposed six intent-level
groups (`regions_and_relations`, `track_motion_and_effects`,
`shortest_path`/`configuration_path`, `shape_transforms_and_assignment`,
`learned_operators_and_search`, `rewrite_derivations`); this round's actual build
grew that to **eight** (`state_canonicalization` and `shape_geometry` were added —
see `docs/r56_kernel_catalog.md`'s per-module intent-group notes for the
provenance of each). The target LLM
interface is **declared-intent offloading** (the model declares a typed problem +
supplies the semantics; the harness auto-invokes the matching kernel) — explicitly
NOT a flat namespace of 30+ function names dumped into the prompt, which the
verdict predicted would make adoption WORSE, not better.

## What was built tonight

- `4303662` — the Codex verdict doc itself, the round's binding design source.
- `3edcf4d` — `rewrite.py` (`derive_rewrites`/`find_derivation`) — first kernel,
  the TR87-class token-rewrite-grammar search.
- `1d797d7` — `shapes.py` (`dihedral_transforms`/`crop_to_content`/`iou`/
  `best_transform_match`/`assign_pairs` — exact bitmask-DP bipartite assignment,
  not greedy).
- `62fac21` — `paths.py` (grid/transition shortest path, multi-source distance
  field, reachable frontier, generic configuration-space BFS).
- `f13b433` — `motion.py` + `regions.py` (frame diff / changed-region
  attribution / object tracking / motion vectors / learned point-operators +
  planning; connected-component segmentation / spatial relations / axis
  grouping / shape-multiset comparison / bbox tiling).
- `d377121` — `canonical.py` (four state-canonicalization modes +
  stability/confidence measurement) — the **7th** intent group, added beyond
  the original six because the `graph_search.py` decomposition row explicitly
  called for it.
- `a2a62f0` — `geometry.py` (closed-frame/ring detection, elongated-axis
  extraction + point-to-axis projection, `point_toward`, `axis_snap`,
  `covering_offsets`, thin-connector detection) — the **8th** intent group;
  closes the catalog's first-flagged "closed shape detection" and "geometry
  primitives" gaps.
- `b67cb39` — cross-module hardening pass: unified frame normalization into a
  new private `src/admorphiq/kernels/_common.py` (fixed a real bug — before
  this, `regions.find_regions`' own `_normalize_frame` skipped the `int(v)`
  cast the other modules applied, so `region["color"]`'s TYPE was
  scan-order-dependent); and refactored `motion.track_objects`' Stage 2 to
  compose `shapes.assign_pairs` for an EXACT minimum-distance assignment
  instead of a greedy nearest-centroid pass, proven with a genuine
  greedy-vs-optimal counterexample (not just a refactor with identical output).
- `de013aa` — `docs/r56_kernel_catalog.md`: an execution-verified reference for
  every kernel function (every code example run via `uv run python -c ...`
  against the real code, none written from memory), three composition recipes
  that explicitly mark CALLER-decision vs kernel-computation boundaries, a gaps
  analysis against the Codex decomposition table, and an API-inconsistency
  audit that fed directly back into the `b67cb39` fixes.
- `69101ea` — `scripts/script25.py` + `src/admorphiq/adapters25/` (the
  quarantined per-game adapter zone) + an AST-based quarantine lint (adapters
  may compose kernels and declare mechanic hypotheses/role assignments, but may
  not hardcode coordinates/palettes/target sequences or their own search —
  enforced by tooling, not convention) + a runner that reuses
  `scripts/score_efficiency.py`'s own faithful RHAE loop rather than
  reimplementing it.

**Result: 7 kernel modules, 37 public exports, 93 tests, ruff clean**
(`uv run pytest tests/ -q -k kernel`). Full function-by-function reference:
`docs/r56_kernel_catalog.md`.

## Measured so far

**m0r0 PoC adapter** (`src/admorphiq/adapters25/m0r0.py`) — a maze-navigation
script25 adapter composing `find_regions`/`frame_diff`/`track_objects`/
`motion_vectors` (measures whether/how much something moved after each press,
with NO assumption about which region is the player or which direction is "up")
and `grid_distance_field`/`grid_shortest_path`/`path_to_moves` (frontier
navigation to the nearest cell with an untried action), with zero
game-specific coordinates anywhere in the adapter.

First smoke run (per the adapter's own docstring, its measured provenance):
**GAME_OVER at 151 actions, 0 levels cleared, no hazard-avoidance policy at
that point.** The kernel-composition PLUMBING is verified working
end-to-end — regions are detected, movement is measured, frontier BFS drives
navigation — but the adapter had no way yet to avoid repeating the same fatal
`(cell, action)` pair, so it kept dying at the same hazard every restart. This
is a capability gap in the ADAPTER's own mechanic hypothesis and hazard
handling, not a kernel defect — the kernel layer performed exactly as
designed; script25's job (per the verdict) is to prove kernel expressiveness,
and each adapter's own game-specific policy is squarely the adapter's problem
to solve, not the kernels'.

(Note, recorded for provenance honesty: at the time of writing this page, an
UNCOMMITTED hazard-memory fix already exists in the adapter's working tree —
`restart_on_game_over` plus tracking which `(cell, action)` pairs cause a
silent env repositioning and excluding them from future frontier search — but
it has not yet been re-measured, so no result is claimed for it here. See
Open items.)

## Open items

- **Adapter iteration.** m0r0's hazard-memory fix (uncommitted as of writing)
  needs a re-measured smoke run before its effect can be reported. A second
  adapter, `lp85.py` (rare-colour click family — clicks the region whose
  colour is the rarest on the board), has also landed (uncommitted,
  unmeasured).
- **TR87 feasibility.** `docs/tr87_frame_only_grammar_design_20260715.md`
  (uncommitted, dated 2026-07-15): scopes whether `derive_rewrites` +
  `shapes` + `regions` can crack the TR87 wall (0/6 on the LLM-free card) via
  a frame-only rewrite-grammar adapter. Verdict recorded there: **feasible,
  and the hardest sub-problem (glyph tokenization) is now MEASURED, not
  hypothesized** — but a real solver is scoped as "a multi-day build, not a
  same-session patch." Design + prototype only; not built.
- **Declared-intent offloading interface** (task #42) — per current team
  coordination, this is pending the engagement/basenav experiment results
  before design work starts. The design should account for **8** intent
  groups now (the original 6 plus `state_canonicalization` and
  `shape_geometry`), not 6.
- **Two API inconsistencies deliberately left undone this round** (fully
  documented in `docs/r56_kernel_catalog.md`, no code churn against them):
  the `shapes.py` vs `canonical.py` "shape" representation bridge (a cropped
  mask+offset dict vs a bare frozenset of offsets — same concept, two
  incompatible data shapes), and `motion.py`'s validation-strictness
  asymmetry versus the other five modules (a deliberate, documented "trust
  internal callers" choice, not an oversight).
- `geometry.py`'s own former private `_normalize_frame` duplicate was the
  last of the four modules with the pattern to be unified onto `_common.py`
  (done this session; confirm it lands in the next commit alongside this
  page).

## Related

- [[r53_unified-harness]] — the harness whose 6 generic TOOLS this round's
  kernel library sits one layer below: R53 built tool-level primitives
  (`graph`/`world_model`/`dealias`/`deadsig`/`paint`/`llm_goal`) as a
  self-improving retry loop with policy baked into each tool; R56's kernels
  are pure computation with NO policy at all, the kind of primitive an R53
  tool — or a future declared-intent interface — composes underneath its own
  decisions.
- [[r55_code-repl-agent]] — the code-REPL agent whose sandboxed Python
  execution is the natural RUNTIME for kernel composition (the model writes
  code that imports `admorphiq.kernels` directly, exactly as script25's
  adapters do by hand). R55's matched12 experiment measured that
  GOAL-INFERENCE — not tool/kernel availability — is the dominant wall on
  the games neither track has cracked; that finding is the strongest argument
  for keeping R56 kernels policy-free and pushing goal/role decisions
  entirely onto the caller, since adding kernel-side policy would not have
  helped R55's wall and risks the same public-overfit trap that sank the
  brittle solver card (0.14–0.20 hidden transfer).
- [[index]]
