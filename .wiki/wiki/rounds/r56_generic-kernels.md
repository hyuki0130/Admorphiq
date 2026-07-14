---
type: reasoning
round: R56
axis: generic-kernel-library
verdict: IN-PROGRESS
keywords: [generic-kernels, namespace-safe, script25, agent25, dual-scoreboard, declared-intent, primitive-firewall, kernel-library, quarantined-adapter]
commit: [4303662, 3edcf4d, 1d797d7, 62fac21, f13b433, d377121, a2a62f0, b67cb39, de013aa, 69101ea, 68b802a, 3151030, cbda9aa, 0a7be09, 6e238de, f406d55, a3a6644, ae8fd95, 204aab2, 3e7391a, f0b0bcb]
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

**Kernel growth continued past the initial catalog** (`docs/r56_kernel_catalog.md`
was written at `de013aa`, before the four additions below — its own module/
export/test counts are a snapshot, not current; this page's are):

- `1aab383` — `parse.py` (gap windows, window-majority colour, width
  clustering, greedy first-rule parse over a token sequence) — feeds the
  TR87-class grammar work below.
- `d185404` — `gf2.py` (`gf2_solve`/`gf2_nullspace`, Gaussian elimination
  over GF(2)) plus the first `ft09` adapter pass, and a parse-kernel
  revision per an intervening Codex ruling.
- `6e238de` — `geometry.split_fused_frame` (ring+appendage de-fusion):
  generalizes `sort_match.py`'s own `_split_box_pipe` into a namespace-safe
  kernel. Per-dimension SPAN-MODE technique (not a fixed orientation
  assumption) finds the true ring under an appendage fused on in any
  direction; subset+empty-hole validation rejects solid blobs (a filled
  block is never mistaken for a ring-plus-pipe). Real-data check against
  the FULL sb26 gold trace: recovers the one genuine fused ring
  `closed_frames` misses (its own L2 level, a ring + 26-cell icon
  appendage), **0/4310 false positives** across the whole trace. 8 new
  tests.
- `3e7391a` — `parse.split_runs_by_pitch` promoted to its STRICT form
  (explicit pitch argument, exact division, provenance recorded) per the
  Codex tr87 re-ruling (`204aab2`) — see "TR87 gate arc" below.

**Result (verified via `admorphiq.kernels.__all__` + a fresh test collection,
not carried forward from the catalog doc's own snapshot): 9 kernel modules
(`canonical`, `geometry`, `gf2`, `motion`, `parse`, `paths`, `regions`,
`rewrite`, `shapes`), 45 public exports, 134 kernel-specific tests
(`tests/test_kernels_*.py`), ruff clean.** Full function-by-function
reference for the modules present at `de013aa`: `docs/r56_kernel_catalog.md`
(does not yet cover `parse`/`gf2`/`split_fused_frame`/strict
`split_runs_by_pitch` — a catalog refresh is an open item below).

## TR87 gate arc — a multi-step Codex-gated promotion, not a single decision

TR87 (0/6 on the LLM-free card) is a token-rewrite-grammar game
(`derive_rewrites`/`greedy_parse`-class), and Codex required each capture
to clear a gate BEFORE the next kernel/adapter step could proceed — this
did not happen in one commit. Full sequence, in order:

1. **`f406d55` — Codex tr87 review.** GATE ruling: no kernel work proceeds
   past L1 without a genuine capture. Primitive rulings made ahead of any
   code: C4 (not D4) transform group for this game's symmetry, no
   minority-ink kernel needed, greedy-parse belongs in the `rewrite`
   group rather than as its own module.
2. **`a3a6644` — tr87 L1 gate test: SEGMENTATION FALSIFIED, oracle-exact.**
   A disposable oracle-assisted capture of the L1 reset frame found
   `occupied_runs` merges every multi-token rule side into ONE window —
   the naive segmentation hypothesis is wrong, oracle-exact-verified
   (12/12 widths = token_count x 7px). A validated-not-yet-built recovery
   heuristic was identified: split runs at multiples of the observed
   single-glyph pitch (recovered 6/6 on L1). Side findings from the same
   capture: the wiki's own TR87.md had ACTION1/2 dial direction INVERTED
   (fixed); TR87 reproduces the SB26 transient-multilayer lesson at level
   transitions (must read `frame[-1]`); an `L6 double_translation` branch
   was found to be dead code (if/elif precedence bug).
3. **`ae8fd95` — tr87 L2 gate: SPLITTER SURVIVES L1+L2.** The
   pitch-multiple splitting heuristic from step 2 recovers every
   rule-side token count on BOTH captured levels — L2 is the Codex worst
   case (multi-token both sides of the rule) and every recovered width is
   still an exact 7px multiple. A capture-chain bug was caught by a
   byte-equality sanity check against a known-different prior frame
   (lesson: verify new captures against byte-IDENTITY, not plausibility).
   Per the gate protocol, this did NOT auto-promote the splitter — it
   reopened the gate for SCOPING ONLY, sent back to Codex before any
   kernel/adapter build.
4. **`204aab2` — Codex re-ruling: promote strict `split_runs_by_pitch`.**
   Codex approved promotion given steps 2-3's evidence, with an explicit
   5-step build sequence and named kill criteria, and flagged that FT09
   should be prioritized ahead of finishing TR87 (+3.81pp measured
   ceiling vs TR87's +1.14pp).
5. **`3e7391a` — tr87 integration: PASS L0-L1, KILL L2 (honestly).** The
   strict `split_runs_by_pitch` kernel (promoted per step 4) drives a
   frame-only integration that passes L0 and L1 TOKEN-FOR-TOKEN, then
   kills on L2 — but the KILL itself is new evidence: it fails at BAR1
   fragmentation, not just bar2 as earlier rounds assumed, meaning the
   wall moved closer to the actual mechanic rather than staying in the
   same place.

**Net honest status**: TR87 is still 0/6 live-cleared. What changed is
epistemic, not a score: the segmentation model is now falsified-and-
replaced with a verified recovery heuristic, gated through Codex twice,
integrated far enough to prove L0-L1 token-exact and isolate the L2
failure to bar1 — a fully-scoped, partially-built solver, not a guess.
See [[../lessons/tr87_dial_match_hypothesis_falsified_20260713]] for the
prior (pre-this-arc) falsified hypothesis this segmentation work
supersedes, and
`docs/tr87_frame_only_grammar_design_20260715.md`/`docs/r56_codex_tr87_reruling_20260715.md`
for the full design documents.

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

## Measured so far (continued) — sb26: script25's FIRST live clear

**sb26 adapter** (`src/admorphiq/adapters25/sb26.py`, committed `3e7391a`) —
the portal-sort mechanic was verified OFFLINE against gold traces before
any live action was spent: slot positions are measurable uniform
clusters, which falsifies `sort_match.py`'s own arithmetic-placement
assumption. Decorative-frame and chrome-colour filters compose entirely
from existing kernels (the same relative-geometry HUD-band exclusion
`su15` uses). Running the adapter's own `_plan_sb26` against all 8 gold
levels offline found a structurally valid plan for 7/8 — only level 1
(wiki "L2", the portal case) failed, at the time diagnosed as a genuine
kernel-coverage gap (a fused box+pipe connected component `closed_frames`
rejects outright) — the exact gap `split_fused_frame` (`6e238de`, above)
was built to close.

**Live result: script25's FIRST clear, at SUPER-HUMAN efficiency** — L1
in 13 actions vs. a human baseline of 18, `level_score = 1.0` (the
squared-efficiency RHAE metric's cap). This is the first script25 adapter
to actually clear a level against the live API, not just plan correctly
offline against gold traces — the plumbing-to-live-result gap the m0r0
PoC adapter above explicitly left open.

**Not yet re-measured after this session's fused-frame integration**: a
LATER same-session commit (`f0b0bcb`, not part of the original `3e7391a`
clear) wires `split_fused_frame` into `_recover_fused_frames` so the
adapter can now attempt level 1's previously-unreachable portal frame —
but this has not yet been run live, so whether it actually clears L1 (or
further levels) is not yet a measured result, only a built capability.

## Measured so far (continued) — ft09

**ft09 glyph-decode adapter** (`src/admorphiq/adapters25/ft09.py`, committed
`68b802a`) — gold-trace reverse-engineering (replay against captured L0/L1
frames) falsifies the R16-R18 "coupled GF(2) neighbourhood stencil" reading
of FT09 entirely: a click only ever changes the clicked cell. The real win
condition is a 3x3 compass glyph drawn in each ring's own center gap; a
ring cell needs a click iff its current colour differs from its
glyph-predicted target, decoded fresh from the frame on every call (no
caching), which also makes two-phase decoy->reveal boards fall out for
free. Ring/pitch/glyph geometry is entirely discovered (modal button size,
mode of measured button-gap distances, `tile_bbox` 3x3 split) — no fixed
pixel offsets. Falls back to the pre-existing measured-GF(2)-stencil
machinery, unchanged, via a per-cell click cap + contradiction budget if
the decode doesn't apply to an unseen board. **Verified byte-for-byte
offline against gold-trace data; live-env smoke run not yet run** — see
[[../lessons/ft09_glyph_decode_20260715]] for the full falsification
writeup and open item.

## Open items

- **FT09 live-env smoke run.** The glyph decode above is gold-trace
  verified but has not been run against the live API the way the m0r0 PoC
  adapter below was — that is the next falsification step for this game.
- **Adapter iteration — resolved, corrected from an earlier stale note on
  this page.** m0r0's hazard-memory fix (dead-cell memory keyed
  per-`(cell, action)`, `known_passable` persisted across restarts instead
  of being wiped each life) landed and was smoke-measured in `4129284`:
  `known_passable` count 70 -> 132 at the same 500-action budget, still
  0 levels — the wall is now a BUDGET ceiling (legacy solved the same
  maze at ~2130 actions), not the hazard-repeat bug this fix targeted.
  `lp85.py` (rare-colour click family — clicks the region whose colour is
  the rarest on the board) also landed in the same commit: 0/8 at 500a,
  consistent with the legacy ceiling. Full-budget re-runs live on the
  GCP VM, not yet reported here.
- **KA59 had a real init bug, fixed same session.** The committed adapter
  (`cbda9aa`) used `self._select_point`/`self._last_select_cell`/
  `self._select_attempts` without ever initializing them in `__init__` —
  a latent `AttributeError` on the first select-click cycle. Fixed in
  `0a7be09`, which also corrects blocked-move attribution to use the
  actual cell a move was issued for instead of a possibly-stale
  `_active_cell` right after a select. No dedicated
  `test_adapters25_ka59.py` exists yet to pin either fix (unlike `ft09`,
  which has `test_adapters25_ft09.py`) — the gap this bug slipping
  through exposes.
- **TR87 L2 wall.** Corrected from an earlier stale note on this page
  (the design doc is now committed, and a real integration WAS built —
  see "TR87 gate arc" above, not "design + prototype only"). Remaining
  gap: the L2 KILL is now isolated to bar1 fragmentation specifically,
  not a vague "segmentation is hard" — the next step is a bar1-specific
  fix attempt, not another scoping round.
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
- **`docs/r56_kernel_catalog.md` needs a refresh.** It was written at
  `de013aa` and its own module/export/test counts are a snapshot from
  before `parse.py`, `gf2.py`, `split_fused_frame`, and strict
  `split_runs_by_pitch` landed — this page's "What was built tonight"
  section carries the current verified totals (9 modules / 45 exports /
  134 tests) but the catalog doc itself still needs the four missing
  functions' execution-verified examples added.
- **sb26's fused-frame recovery (`f0b0bcb`) needs a live re-run** to see
  whether it actually clears level 1 (or deeper) now that
  `split_fused_frame` is wired in — see "Measured so far (continued) —
  sb26" above.

## Related

- [[r57_win-condition-typology]] — mines the same trace/kernel toolkit (R56's
  `find_regions`/`frame_diff`/`multiset_signature`) at the META level, across
  all 25 games, to name a transferable vocabulary of win-condition TYPES;
  ft09's glyph decode above is one game-specific instance of the pattern
  R57 catalogues generically.
- [[r58_explanation-layer]] — the Codex verdict on TEACHING the weak offline
  model to use these kernels (typed intents + enforced state machine +
  goal-typology detectors), one layer above pure computation; its P2
  artifact (`GoalLedger`) composes R56 kernels (`find_regions`, `frame_diff`,
  `multiset_signature`) exactly as script25 adapters do by hand.
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
