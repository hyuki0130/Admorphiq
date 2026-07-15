---
type: reasoning
round: R56
axis: generic-kernel-library
verdict: IN-PROGRESS
keywords: [generic-kernels, namespace-safe, script25, agent25, dual-scoreboard, declared-intent, primitive-firewall, kernel-library, quarantined-adapter, gold-replay-divergence, round-robin-sweep, joint-state-planning]
commit: [4303662, 3edcf4d, 1d797d7, 62fac21, f13b433, d377121, a2a62f0, b67cb39, de013aa, 69101ea, 68b802a, 3151030, cbda9aa, 0a7be09, 6e238de, f406d55, a3a6644, ae8fd95, 204aab2, 3e7391a, f0b0bcb, b28290e, 010df51, fbd625d, 57b325d, a8299de, efaf004, 362c672, 95c27c4, 569a620, de0510e, 4d9472f, 2209a5f, 9e7f474, b36fd8a, fc36602, 6f81df7, b9b35cd, a314bee, ac8c177, f4e8b11, 8b48b0b]
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

## Adapter scoreboard (current, end-of-night sweep)

Per-game script25 status as of this sweep. "Banked" = a genuine negative
or capped result recorded with its own falsification writeup, not an
unmeasured gap. Live smoke numbers are `script25`'s own faithful RHAE
metric (2x500-action runs unless noted), not the legacy 25-game card.

| Game | Status | Live result | Commit | Notes |
|---|---|---|---|---|
| ft09 | **COMPLETE** | 6/6, 100% RHAE, 88 actions, every level @1.0 cap | `95c27c4` | glyph-decode grammar + GF(2) control-glyph solver; no open items |
| tr87 | 3/6 live | L0-L2 all @1.0 efficiency cap (17/54, 35/58, 26/40a) | `362c672` | 7-step Codex-gated grammar arc; L3-L5 (`alter_rules`/`tree_translation`/`double_translation`) deliberately banked unmeasured |
| sb26 | 3/8 live | 0.1446 | `57b325d` | L4 falsified-and-banked: structurally-identical board, different (undiscriminated) mechanic — genuinely open question, not a wiring gap |
| lp85 | 1/8 live | 2.48% (0.0248); L1 18a vs 17 human, score 0.89 | `f4e8b11` | divergence-first: candidate GRANULARITY was the root cause (a rare region can hold several functionally distinct pixels, not one clickable point) — fixed with per-pixel enumeration (`a314bee`), then a round-robin probe-queue redesign + local-focus promotion cut L1 from 69→18 actions (`f4e8b11`) |
| m0r0 | 1/6 live | joint-state planner, desync-capable | `b9b35cd` | mirror-pair mechanic (every action moves BOTH a SELF and PARTNER region simultaneously, independently blockable) modeled via `configuration_path` joint-state hill-climbing; 4 measured bugs fixed en route (GAME_OVER memory wipe, goal-merge fallback, off-lattice routing target, fuzzy self/partner mismatch) plus a peer-relative outlier-rejection fix (`6f81df7`) |
| vc33 | 1/7 live | new mechanic identified | `569a620` | escalating click-counter with a decoy penalty — a genuinely NEW win-condition shape for this round's typology |
| tu93 | 2/9 @3000a (0/9 @500a) | banked | `9e7f474`/`ac8c177` | slide-until-wall maze, transition-graph baseline; corridor-prediction efficiency lever explicitly banked, not pursued further this round |
| dc22 | **BANKED at 0/6** | every individual primitive verified correct | `b36fd8a` | walk/stuck/probe/learn architecture is fundamentally REACTIVE; gold's own solution is PROACTIVE/state-gating (set button parity BEFORE walking, not in response to being stuck) — two independently-sound fix attempts (toggler-cycling re-click, parity-combo enumeration) both measured 0/6; the wall is architectural, not a missing heuristic |
| ka59 | banked at 0/7 | push mechanic WORKS (wall-crossing measured) | `a8299de` | reactive, not planned into the joint solve; re-identify/re-assign overhead eats the action fuse before convergence — a real working primitive with a named remaining gap |
| su15 | **BANKED at 0/9** | candidate-detection layer verified correct end-to-end | `26ebeb6` | iteration 7: 4 real perception bugs closed via gold-replay divergence (fragment fusion via `find_regions(gap=2)`, scatter-detection stray contamination, first-click pair-preference, pool-exhaustion re-enabling dead tiles) — click 1 now matches gold exactly; still 0/9 live, wall moved to a source-IDENTITY question (a live diagnostic found the correctly-identified click-1 target is STATIC while a separate, larger blob is what actually moves — the "vacuum pulls a distant object" hypothesis is the named reopen pointer, not yet built) |
| sp80 | **IN-FLIGHT, characterization only** | 2 hypotheses falsified live, no adapter yet | `8b48b0b` | 149-transform stable byte-identical 4-transform cycle (colour8 count 3,3,2,2 then GAME_OVER, spawns at identical positions each cycle) — position-delivery AND transform-count hypotheses both falsified; non-monotonic colour8 count means something is CONSUMED each loop, not accumulated; next-step pointer is characterizing that consumption |

## Diagnostic method of the night: gold-replay divergence

The single method that cracked the most rounds tonight, used consistently
across unrelated games: replay a level's GOLD trace
(`data/traces/<game>.npz`, label-generation only, never imported at
runtime) frame-by-frame against the adapter's OWN candidate/decision
logic, and find the exact STEP where they diverge — not "does the
strategy sound right" but "where, precisely, does the live decision
differ from what gold's own recorded actions did, and why". This is
offline-only (dev-time consultation of gold, never live-loop access) and
distinct from live-smoke measurement, which comes after: divergence
analysis picks the hypothesis, live smoke confirms or falsifies it.

Three concrete cracks this method produced tonight, each a genuinely
different CLASS of bug:

- **dc22's architecture question** — replaying gold's own click sequence
  against the adapter's reactive walk-stuck-probe loop showed gold
  clicking buttons BEFORE ever getting stuck (state-gating), not in
  response to a blocked path — the reactive architecture was asking the
  wrong question entirely, not missing a heuristic. This reframing is
  what let the dc22 thread end in a clean BANKED verdict (an honest
  architectural mismatch) instead of another "still 0/6, try one more
  heuristic" cycle.
- **lp85's granularity bug** — replaying gold's level-0 clicks against the
  adapter's own region ranking found the winning pixel belonged to a
  40-pixel rare-coloured region whose CENTROID was a completely different
  pixel; frame-diffing gold's own clicks in that region additionally
  showed several DISTINCT functional pixels within one connected blob
  (a HUD-visible fill bar advanced by 4 of them, a 5th, different pixel
  triggered WIN) — a class of bug no amount of "which region to click
  first" ranking could ever have found, only per-pixel replay could.
- **su15's perception bugs** — the multi-iteration su15 arc (6 rounds,
  `77a4c53` through `f4158f3`) used the same discipline at smaller grain
  each time: falsify one specific hypothesis (enemy-hazard, select-then-
  place, escalate-only policy) against a direct gold/live measurement
  before trying the next, rather than guessing broadly — each iteration's
  commit message names the exact falsified claim and the measured
  evidence, not just the next thing tried. Iteration 7 (`26ebeb6`)
  finally applied the method to the CANDIDATE-DETECTION layer itself
  (previous iterations tuned click mechanics on top of unverified
  candidates): replaying gold's L1 clicks against `_next_target` found
  the adapter's very first decision targeted a coincidentally-same-
  coloured STATIC decoration pair instead of the one colour-unique,
  genuinely movable tile gold used — plus three more bugs the same
  replay + a 9-level offline table + a live-smoke diagnostic surfaced
  (fragment-sprite fusion, a stray-region scatter-contamination bug, a
  dead-bucket pool-exhaustion re-enable). All four fixed and verified;
  still 0/9 live, BANKED with a named next-hypothesis (source-tile
  IDENTITY, not click position, may be the wrong model — see
  [[../games/SU15]] for the full trace evidence).

The common thread: a strategy can be "individually correct" at every
piece (as dc22's re-click fix and lp85's original rarity ranking both
were) and still fail, because the DIVERGENCE is in a layer the piece-level
correctness check never examines — gold-replay is the layer that finds it.

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
- `b28290e` — `geometry.recover_occluded_frame` (missing-border-cells
  recovery via caller-supplied occluders) — `split_fused_frame`'s inverse
  case; see "Measured so far (continued) — sb26" below for the diagnosis
  and real-data validation this landed with.

**Result (verified via `admorphiq.kernels.__all__` + a fresh test collection,
not carried forward from the catalog doc's own snapshot): 9 kernel modules
(`canonical`, `geometry`, `gf2`, `motion`, `parse`, `paths`, `regions`,
`rewrite`, `shapes`), 46 public exports, 142 kernel-specific tests
(`tests/test_kernels_*.py`), ruff clean.** Full function-by-function
reference for the modules present at `de013aa`: `docs/r56_kernel_catalog.md`
(does not yet cover `parse`/`gf2`/`split_fused_frame`/`recover_occluded_frame`/strict
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

6. **`efaf004` — tr87 step 3: LATTICE bar tokenization, gate PASSES exactly
   on ALL THREE levels.** `extract_bar1_tokens` (occupied_runs-segmented,
   step 2) replaced with `extract_bar_tokens` (generalized for bar1 OR
   bar2), composing `split_runs_by_pitch` instead: the bar's full measured
   extent becomes ONE parent run (real ink cells computed directly, not
   via a second `occupied_runs` pass), split into `pitch`-wide slots
   POSITIONALLY. This closes step 5's own bar1-fragmentation KILL (L2's C4
   glyph, 8/8 tokens now exact, matching oracle) and, applied to bar2 too,
   fully dissolves the design doc's SEPARATELY-flagged L1 bar2
   fragmentation (11 messy runs -> exactly 7 clean, all-recognized
   tokens). Two genuine findings surfaced doing this: bar1/bar2 have
   INDEPENDENT column counts (not paired 1:1 — L1: 4 vs 7, L2: 8 vs 7,
   falsifying an initial assumption), and not every one of bar2's 7
   measured dial states is necessarily NAMED by a given level's 6 rules
   (L0: 1 of 5 current-state reads has no rule-table name — a clean,
   well-formed shape, hypothesized as a legitimate off-table state, not a
   lattice defect; never treated as a kill, since the adapter only needs
   to detect a target MATCH, never to name the current state). Also fixed
   a latent, unrelated bug this step's success first exposed: the test
   harness's own oracle-target verification assumed every rule LHS was
   single-token, crashing on L2's genuine multi-token LHS rules — L0/L1
   never exercised that code path because their bar1 KILL fired earlier,
   before this fix.
7. **`362c672` — tr87 step 4: THE ADAPTER, `src/admorphiq/adapters25/
   tr87.py`. TR87 goes from the card's 0/6 wall to 3/6, EVERY clear at the
   1.0 efficiency cap.** Packages the proven step-1/3 pipeline
   (background/band discovery -> rule extraction -> bar1 lattice read ->
   `greedy_parse` -> target) plus a NEW dial executor: bracket-column
   detection (the bracket is a short, structurally-adjacent-to-bar2 band,
   not a fixed row; its own ink projected onto bar2's lattice gives the
   selected column) and a per-column bracket-move + dial-step loop.
   Neither action direction is assumed from the verification-only source
   read — bracket-move direction (`ACTION3` vs `ACTION4`) is calibrated
   LIVE, once per level (one probe action, observe which way the detected
   column index moved, cache the mapping); dial-step direction needed NO
   calibration at all, since the measured CLOSED 7-state cycle guarantees
   that repeatedly pressing ONE dial action reaches any rule-table-derived
   target within 7 hops regardless of direction. Live smoke (2x500,
   deterministic): L1 17a/54human, L2 35a/58human, L3 26a/40human — ALL
   THREE score the maximum 1.0. A 5000-action budget check confirmed the
   flagged-level (L3-L5, 0-indexed) fallback fails SAFELY: `classify_bands`'
   own structural gate causes an unsupported board to fall back to
   harmless `ACTION3` bracket-nudges, exhausting the level's own internal
   128-action budget (verification-only source read) without crashing,
   hanging, or attempting exploratory recovery against unmeasured
   `alter_rules`/`tree_translation`/`double_translation` semantics.

**Net honest status, UPDATED (was "still 0/6" at step 5): TR87 is 3/6
live-cleared, every cleared level at PERFECT efficiency.** The segmentation
model was falsified-and-replaced with a verified recovery heuristic (step
3), gated through Codex twice, integrated to prove all-level token-exact
(step 3) and packaged into a working adapter (step 4) — the full
"fully-scoped, partially-built solver" from step 5's own honest status now
IS a shipped, measured 3/6 solver. See
[[../lessons/tr87_dial_match_hypothesis_falsified_20260713]] for the prior
(pre-this-arc) falsified hypothesis this segmentation work supersedes, and
`docs/tr87_frame_only_grammar_design_20260715.md`/`docs/r56_codex_tr87_reruling_20260715.md`
for the full design documents. Remaining: [[../games/TR87]]'s own "L3-L5"
scope note — the three flagged levels are UNMEASURED, banked deliberately
(Codex's own "bank the simple slice instead of contaminating kernels"),
not a wiring gap.

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

**Updated live result (`57b325d`): 3/8, 0.1446.** L3 decoded via a
DIFFERENT signal than the L1/L2 connector-geometry path — pure colour
matching (a hollow icon inside the hub's hole whose colour equals a leaf
frame's border), kept alongside the connector path since games may use
either signal. A second real bug fixed in the same commit: the
largest-hole-cluster frame filter was silently dropping BOTH leaf frames
(the hub is legitimately the largest), replaced with a content-count >= 2
threshold (decorative markers measured to have exactly 1). Slot sequence
matches gold exactly; L1/L2 did not regress; 2x500 deterministic. L4 is
the next wall (~4000-action plateau).

**L4 attempted and BANKED, not built** — same session, gold-trace-first
method applied a third time. L4's board (2-frame hub-and-leaf) is
STRUCTURALLY IDENTICAL in shape to L3's colour-matched-icon mechanic (no
physical connector, `connectors()` returns zero links) but its single
icon requires an EXPLICIT standalone click (auto-consuming its own
colour's pool swatch, no paired pool pick) BEFORE any hub item is placed
— confirmed both offline (region-diffed gold trace) and live (L3's
zero-cost colour-matching detection does not clear L4 even at a
5000-action budget). Two hypotheses tested and FALSIFIED, not just left
untried:
1. *Always click every colour-matched icon* — degrades L2's efficiency
   (21a→22a; L2's icon is independently visible as a `candidates` region
   despite using the connector path) AND still doesn't fix L4 (the
   REQUIRED insertion position is "before any hub item"; the same
   column-position rule that correctly orders L3's two icons would place
   L4's icon mid-sequence instead — both the trigger condition and the
   insertion semantics were wrong simultaneously).
2. *An icon whose colour has a matching pool swatch needs a click; one
   without doesn't* (a natural follow-up hypothesis) — falsified by
   direct measurement: colour14 (L4's icon) and colour9 (one of L3's
   icons) both have a pool swatch present, same single-instance count,
   in ALL of L2/L3/L4's pools. Pool/target-band composition is
   byte-identical in shape across all three levels — no per-level
   difference to key off.
Both attempted fixes were REVERTED (not banked as partial wins) once
disproven — `sb26.py` sits at the clean `57b325d` state, 3/8, no
regression. No structural signal (frame geometry, pool composition,
target-band composition) was found that discriminates "icon needs a
click" from "icon is free" between two boards with visually identical
icons. See [[../games/SB26]]'s own "L4 open question" section for the
full writeup and next-step ideas.

**Not yet re-measured after this session's fused-frame integration**: a
LATER same-session commit (`f0b0bcb`, not part of the original `3e7391a`
clear) wires `split_fused_frame` into `_recover_fused_frames` so the
adapter can now attempt level 1's previously-unreachable portal frame —
but this has not yet been run live, so whether it actually clears L1 (or
further levels) is not yet a measured result, only a built capability.

**Second portal frame diagnosed and closed (`b28290e`, same session)** —
level 1 actually needs TWO frames for portal detection, and the second
(colour 8, `outer_bbox (18,18,27,45)`, 70 cells vs its own 72-cell
perimeter) was still unrecoverable by anything landed so far. Root cause,
confirmed against the real gold trace (not guessed): the 2 missing border
cells are occupied by a SEPARATE colour-14 connected component (98
cells) that is itself a compound shape — a small icon ring connected by a
2-cell pipe to a SECOND large ring at `outer_bbox (32,18,41,45)` (sb26's
actual second portal target). The pipe physically crosses the colour-8
frame's border at exactly its 2 missing cells. This is a genuinely
DIFFERENT fusion shape than `split_fused_frame`'s case (a foreign-colour
object crossing a border, not a same-colour appendage fused onto it) —
recursing `split_fused_frame` into just the colour-14 sub-blob does NOT
work (confirmed: returns `None`), but calling it on the FULL 98-cell
blob directly correctly recovers the second ring.

New kernel `recover_occluded_frame(region_or_cells, occluders)`
(`geometry.py`) closes the colour-8 side: the candidate bbox comes
directly from its own cells (no mode-span search needed, unlike
`split_fused_frame` — nothing pushes a MISSING-cells bbox outward the way
an appendage does), and it only recovers when every missing border cell
is covered by the union of caller-supplied `occluders`' own cells, plus
the same hole-must-be-empty guard `split_fused_frame` uses to reject
solid blocks. Fully caller-parameterized — no portal/pipe/connector
semantics inside the kernel.

**Real-data validation, full 292-frame sb26 gold trace** (every
non-background region on every frame checked against every OTHER region
on that frame as a candidate occluder set): **exactly 30 recoveries, ALL
of them the same colour-8 frame with the same occluded cells — zero false
positives anywhere else in the trace.** `split_fused_frame` recovers the
second ring on **28/28** relevant frames. Composing the two kernels now
recovers BOTH of sb26's portal frames from one frame — what `connectors()`
needs (it links exactly two already-detected frames) to reach L2+. 8 new
tests in `tests/test_kernels_geometry.py` (the real-data one skips
cleanly when `data/traces/sb26.npz` isn't present locally — `data/` is
gitignored). **Adapter wiring (composing this into `_recover_fused_frames`
/ `_plan_sb26` and driving `connectors()`) is not done here** — kernel +
diagnosis only, per the R56/adapter division of labour this round.

## Measured so far (continued) — ft09

**ft09 glyph-decode adapter** (`src/admorphiq/adapters25/ft09.py`, committed
`68b802a`, extended `3151030`/`010df51`) — gold-trace reverse-engineering
falsifies the R16-R18 "coupled GF(2) neighbourhood stencil" reading of
FT09 entirely: a click only ever changes the clicked cell (plus, on one
level, a second cell at a fixed MEASURED offset — see the lesson page's
"cell coupling" section). The real win condition is a constraint set
collected from EVERY glyph covering a cell (not just the nearest one — a
coverage-scoping near-miss taught this the hard way, see below), decoded
fresh from the frame on every call (no caching), which also makes
two-phase decoy->reveal boards fall out for free. Ring/pitch/glyph
geometry is entirely discovered (modal button size, mode of measured
button-gap distances, `tile_bbox` 3x3 split, a measured 4-member floor for
truncated rings) — no fixed pixel offsets.

**LIVE result (script25, 2x500-action smoke, fully reproducible): 6/6
levels, 100% RHAE (1.0), 88 total actions, every level at the 1.0
per-level cap** (agent action count at or below the human baseline on all
6; commit `95c27c4`). This is the first fully-conquered game on the
script25 scoreboard. Level 5 (0-indexed 4) — the one Codex SOLVED
(`docs/r58_codex_ft09_l4_solution_20260715.md`, committed `df12717`) — is
now live-integrated: the apparent "third glyph type" was actually two
things: 3 ordinary stateful cross-toggle BUTTONS (click toggles self
14<->15 + every existing ink-6 neighbour, a distinct mechanism alongside
the constraint rule, not a new ink value the rule interprets) constrained
by 2 real target glyphs discovery had silently DROPPED (3 members each).
Integration required a NEW GF(2) toggle-system solve (`_build_toggle_system`/
`_glyph_target_controlled`) used only on boards with control glyphs, plus a
live-only discovery-ordering fix: the member-count floor was being
checked BEFORE the control-center registry extension, so the same two
3-member glyphs kept getting dropped for a subtly different reason even
after the floor was lowered to 3 — fixed by deferring the floor check to
after extension. Level 5 now clears in exactly 21 actions, matching
Codex's predicted gold click count. Level 6 (0-indexed 5), fully decoded
offline but never reached live because level 5 blocked it sequentially,
ran live for the first time in this same smoke and cleared at 22 actions
— confirming the offline coupling model transfers unchanged. See the
lesson page's resolution section for the complete writeup, including the
finding that level 5's apparent decoy->reveal was NOT real (an engine
level-installation lifecycle artifact, not a hidden second board).

**A genuine falsification-replay near-miss, root-caused and fixed**: a
Codex-derived 3-colour-cycle formula (`docs/r58_codex_ft09_l3_formula_20260715.md`)
claimed one gold click was redundant; a live deterministic replay omitting
it FAILED to clear the level, directly contradicting the claim. Root
cause: the "redundant" cell was covered by a THIRD glyph the original
2-glyph tabulation missed — full enumeration of every glyph's reach
against every cell (not "the nearest one or two") resolved it to 18/18
exact, with the cell turning out to be uniquely determined, not
ambiguous. This is now the load-bearing coverage-collection rule.

**A separate, real bug found live and fixed**: the adapter's trigger-click
fallback judged success by "did anything visibly change", which loops
forever on a board where an ordinary click is always visibly effective
(measured: 60+ identical clicks, zero contradictions, before the fix).
Fixed via `_is_wholesale_change` (bbox-set Jaccard overlap, not any-diff)
plus bounded distinct-cell trigger and per-level action budgets. Score
unchanged (4/6, 47.62% both before and after), but total actions on the
same 500-budget smoke dropped from 500 (exhausted) to 195 (a clean bounded
bail on the unsolved level) — the intended wall-clock fix.

Falls back to the pre-existing measured-GF(2)-stencil machinery, unchanged,
via a per-cell click cap + seen-colour loop detector + contradiction budget
if the decode doesn't apply to a board it hasn't seen. See
[[../lessons/ft09_glyph_decode_20260715]] for the full falsification-
journey writeup (16 tests in `tests/test_adapters25_ft09.py`, including
regression pins for the trigger-loop bug, glyph classification, the
3-member floor, and the GF(2) control-glyph solver) — FT09's decode arc is
now COMPLETE, 6/6 live, no open items remain on this game.

## Measured so far (continued) — lp85

**lp85 adapter** (`src/admorphiq/adapters25/lp85.py`) — a rare-colour
click game, previously measured 0/8 on the VM's full-budget run
(~4000 actions) despite the wiki recording a known win pixel
(`click_c8_(30,4)`). Diagnosed via gold-replay divergence (see the
"Diagnostic method" section above): replaying `data/traces/lp85.npz`'s
gold level-0 block against the adapter's own candidate ranking found the
winning pixel `(30,4)` belongs to a 40-pixel rare-coloured region whose
own CENTROID — the ONLY point the old adapter ever tried per region — is
a completely DIFFERENT pixel, `(32,5)`. Frame-diffing gold's own clicks
in that region showed why collapsing a region to its centroid is
categorically wrong here: four adjacent pixels within the SAME blob each
independently advance a HUD-visible fill bar (a real, frame-observable
reaction) without winning, and only a fifth, different pixel triggers
WIN. A single connected region can hold several functionally distinct
targets. Two competing hypotheses (a repeated-click/vc33-style counter
mechanic; a GAME_OVER fuse killing each life before reaching the region)
were checked against the SAME gold replay in one pass and directly
FALSIFIED (all 69 gold clicks are on distinct pixels; gold shows zero
GAME_OVER events).

**Fix 1 (`a314bee`): per-pixel candidate enumeration — 0/8 → 1/8.**
`_region_candidates` now enumerates EVERY pixel of each qualifying
region (rarest colour total first, then position within a colour)
instead of one centroid per region — exactly mirroring the RETIRED
`agent_ensemble.strat_click_rare`'s own `np.argwhere(frame == color)`
enumeration, which is how this game was originally won pre-quarantine.
Live: 1/8, level 1 clears in 69 actions (vs human baseline 17, score
0.06) — matching gold's own action count for that level exactly, since
the per-pixel rarity sweep effectively reproduces gold's own
label-generation strategy action-for-action.

**Fix 2 (`f4e8b11`): round-robin queue + local-focus promotion —
0.17% → 2.48% (14.6x), L1 18a vs 17 human (score 0.89, near the 1.0
cap).** The first fix's flat per-pixel ordering still grouped one
region's pixels fully consecutive before the next, so the productive
region (ranked 3rd-rarest) still had to wait for two entirely inert
colours' full pixel counts (32 + 32 = 64 pixels) to exhaust first —
reproducing gold's own breadth-first inefficiency almost exactly. A
first attempt at "promote a responsive region's remaining pixels ahead
of the outer sweep" was measured to be a NO-OP against that baseline
(a region's own pixels were ALREADY consecutive by construction, so
there was nothing to promote past). The actual fix rebuilt the BASE
queue itself as ROUND-ROBIN across regions (one untried pixel per
region per round, rarity order within a round) — reaching every
region's own first pixel after a single pass over every rarer-or-tied
region, not after exhausting their full pixel counts — with local-focus
promotion then providing the genuine escape hatch once a region reacts.

Falls back to `learn_point_operators`-prioritized re-cycling once every
candidate has been tried once, unchanged from before. 8 tests in
`tests/test_adapters25_lp85.py` (per-pixel enumeration, rarity/position
ordering, chrome exclusion, round-robin base ordering, promotion
mechanics including the unknown/exhausted-region no-op case, and an
end-to-end `choose_action`-loop pin).

## Measured so far (continued) — dc22

**dc22 adapter** (`src/admorphiq/adapters25/dc22.py`, committed `0e59f88`)
— a button-barrier navigation adapter reusing ka59's optimistic-passability
navigation design (genuinely-unexplored cells assumed passable, so a button
click that opens new territory is discovered by simply trying to walk
there, rather than requiring button->barrier semantics to be understood).
Avatar and goal are both identified structurally, not by any hardcoded
colour: the avatar by FIRST-movement-probe region tracking (`track_objects`,
mirroring ka59's identity-by-movement technique), the goal by being the
smallest SINGLETON-coloured region excluding the avatar's own colour
(measured on the offline gold trace: goal + avatar are both far smaller
than any other singleton-coloured region on the board). A measured SEESAW
gate (one button's click opens one path while simultaneously closing a
DIFFERENT one, confirmed by direct before/after diffing, not assumed) is
handled without needing to interpret WHAT a button does: every cell that
changes after a probe click is simply dropped from `_known_blocked`
("unknown again, optimistically passable"), and the existing
blocked-cell-record path re-adds any that turn out still blocked the next
time routing tries to walk through them — sidestepping button->barrier
semantics entirely, including the re-closing case.

**Live probe (2x500-action smoke): 0/6, but every measured primitive is
individually CORRECT** — avatar identification, goal identification,
`dir_map`, and effective-vs-inert probe click classification all verified
against the live trace, not just the offline gold trace. The wall is a
probe-SEMANTICS gap, not a plumbing gap: `_live_regions`'s "effective
click" classifier counts a probe click as effective whenever ANY cell
changes, but this over-counts COSMETIC indicator flips (small paired
marker regions that flip colour on every click, whether or not a barrier
actually moved) as genuine barrier-opening events — the same false-signal
shape `frame_diff`'s HUD-masking convention exists to filter, but not yet
applied at the probe-classification layer here. A second, independent gap:
the adapter's "never re-probe a region once probed this level" rule
(borrowed from vc33's own measured lesson that re-probing wastes a
budgeted action on an already-known result) conflicts with dc22's own gold
trace, which clicks the SAME button region twice at different points in
the level — a genuine SEESAW re-visit, not wasted repetition, that the
current never-re-probe rule incorrectly forbids.

**Re-click fix landed, still 0/6 — the second gap only, same session.**
The "never re-probe" rule was replaced with per-button click memory
distinguishing INERT (first click zero diff, never re-clicked) from
TOGGLER (any diff observed, stays eligible for re-click) buttons, each
toggler's own COSMETIC signature (cells that repeat on every click of
that specific button) subtracted before judging a click's real effect.
The re-click DECISION itself went through a falsification: an initial
spatial-overlap gate (re-click a toggler whose accumulated effect
footprint overlaps a cell currently in `_known_blocked`) measured ZERO
reclicks in a live probe — click 1's 97-cell reveal has no reason to
land spatially near wherever the avatar happens to be stuck, so
correlating "where an effect lands" with "where the avatar is stuck"
conflates two unrelated things. Replaced with stuck-state toggler
cycling (try each known toggler once per distinct (avatar cell,
per-toggler click-parity) state, using the planner's own next-step
success as the effectiveness signal instead of a spatial proxy) plus
route-proximity candidate ranking (a live probe measured the OLD
avatar-proximity ranking spending 32 of ~128 per-life actions on
nearby-but-irrelevant regions before ever reaching plausibly-relevant
buttons).

**Measured: 6 live 500-action smokes (`scripts/rounds/
script25_dc22_smoke`..`smoke6`), ALL still 0/6.** Every individual piece
of the fix is independently correct per its own docstring measurement
(button classification, cosmetic-signature subtraction, route-proximity
ranking), but the combination does not clear a level within the
measured budget. This is a genuine negative result on the SECOND gap
only — the first gap (cosmetic indicator flips over-counted as barrier
changes in the pre-toggle "effective click" classifier) was not
addressed by this fix and remains open, with the same fix direction as
before (compose dc22's probe-effect measurement through the existing
HUD/cosmetic-diff filtering convention). See [[../games/DC22]] for the
game's own current status.

**Follow-up, same round — parity-combo enumeration, still 0/6
(`2209a5f`).** The toggler-cycling fix's own negative result motivated a
different theory: gold's own solution proves dc22's button clicks are
PROACTIVE/state-gating (set both togglers to a specific parity combo
BEFORE walking) rather than reactive to physical blockage the way the
stuck-triggered probe assumed. Locks in the two known non-inert togglers
with the largest measured single-click diff and enumerates all 4 parity
combos in Gray-code order (3 transition clicks total, not 8) instead of
clicking only when stuck. **Measured: still 0/6 at 500a
(`scripts/rounds/script25_dc22_smoke7`)** — a different, also-individually-
sound mechanism, also not sufficient on its own.

**BANKED at 0/6 (`b36fd8a`), final verdict for this round.** With BOTH a
reactive re-click fix (toggler-cycling) AND a proactive parity-combo
enumeration independently measuring 0/6, the pattern across both negative
results is the real finding: this adapter's whole walk/stuck/probe/learn
architecture only ever ACTS in response to being stuck (reactively) or,
at best, pre-sets state once via a fixed enumeration schedule — but gold's
own solution is genuinely STATE-GATED throughout (specific button parity
combinations are prerequisites for specific walk segments, decided BEFORE
attempting them, not triggered by failure). This is an architectural
mismatch between "reactive walk-stuck-probe-learn" and "proactive
state-gated win check", not a missing heuristic, a wrong ranking, or an
unaddressed classifier gap — no further heuristic tuning within the
current architecture is expected to close it. Banked here with the full
falsification writeup (both fix attempts' own measurements) rather than
continuing to iterate reactive-loop heuristics against a proactive
requirement.

## Open items

- **FT09 — DONE, complete arc.** The glyph decode has been run against the
  live API (script25, 2x500-action smoke): 6/6 levels, 100% RHAE, 88 total
  actions, reproducible (commit `95c27c4`). Both previously-open items
  (level 5's control-glyph integration, level 6's live re-smoke) are
  resolved — see "Measured so far (continued) — ft09" above and
  [[../lessons/ft09_glyph_decode_20260715]]'s resolution section. No
  further FT09 work is currently open.
- **Adapter iteration — corrected from an earlier stale note on this
  page (the "budget ceiling" read below is now FALSIFIED, see the next
  bullet).** m0r0's hazard-memory fix (dead-cell memory keyed
  per-`(cell, action)`, `known_passable` persisted across restarts instead
  of being wiped each life) landed and was smoke-measured in `4129284`:
  `known_passable` count 70 -> 132 at the same 500-action budget, still
  0 levels — hypothesized at the time as a BUDGET ceiling (legacy solved
  the same maze at ~2130 actions), not the hazard-repeat bug this fix
  targeted. `lp85.py` (rare-colour click family — clicks the region whose
  colour is the rarest on the board) also landed in the same commit: 0/8
  at 500a, consistent with the legacy ceiling (LP85's own budget
  hypothesis is NOT re-tested by the m0r0 backport below and remains
  open).
- **m0r0 — RESOLVED to 1/6 live, corrected from an earlier stale note on
  this page.** Full arc: the undirected frontier-BFS baseline (0/6 at
  both 500a and the VM's ~4000a full-budget run) was replaced with dc22/
  ka59's optimistic-passability + shortest-path-to-a-declared-goal
  pattern (`fc36602`) once gold-trace investigation (`data/traces/
  m0r0.npz`) found the goal is a MOVING mirror-partner region (the
  avatar's own colour is shared by two simultaneously-moving regions,
  each independently blockable; the measured win action is the step that
  brings them into pixel-adjacency) — still 0/6 at first (`4d9472f`,
  `2209a5f`: a goal-jump bug where a merged partner fabricated a goal
  from an unrelated HUD region was found and fixed, not sufficient
  alone). This single-agent framing was itself then replaced with a
  genuine JOINT-STATE planner (`6f81df7`/`b9b35cd`): every action moves
  BOTH the self and partner region simultaneously (not "self chases a
  moving target"), so `kernels.configuration_path` now hill-climbs the
  JOINT `(self_cell, partner_cell)` state toward a smaller combined gap,
  using per-side measured dynamics and per-side optimistic passability.
  A peer-relative outlier-rejection fix (`6f81df7`) also closed a
  spurious-magnitude bug in the per-level dir_map bootstrap. **Live:
  1/6** (`b9b35cd`) — the joint-state architecture is now the canonical
  m0r0 model. See [[../games/M0R0]] for the game's own current status.
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
- **KA59 push mechanic WORKS (`a8299de`), banked at 0/7.** Measured wall
  crossing at `(30,27)->(30,39)` — only L0 of the 4 gold levels actually
  needs a push, and it's now calibrated. Slide execution ticks until 2
  stable frames plus full re-identification; a deliberate collision walk
  is the routing last resort. Three repeat-forever bugs fixed in the same
  commit: identity re-probe without an anchor, a frontier tier that
  excluded the current cell (ping-pong), and fixed-action repeat on
  exhausted cells. Still 0/7 live: the push is REACTIVE, not planned into
  the joint solve, and re-identify/re-assign overhead eats the 100-action
  fuse before convergence — banked as a real, working primitive with a
  named remaining gap (planning integration), not a dead end.
- **TR87 L2 wall — RESOLVED, corrected from an earlier stale note on
  this page.** The bar1-fragmentation KILL this note originally flagged
  (from step 5, `3e7391a`) was closed by step 6's lattice fix
  (`efaf004`, `extract_bar_tokens` composing `split_runs_by_pitch`
  positionally instead of a second `occupied_runs` pass) and packaged
  into the live adapter in step 7 (`362c672`). TR87 is now 3/6 live
  (L0-L2), every cleared level at the 1.0 efficiency cap — see "TR87
  gate arc" above for the full 7-step provenance. Remaining scope is
  L3-L5 (`alter_rules`/`tree_translation`/`double_translation`),
  deliberately banked unmeasured, not a wiring gap.
- **DC22 — BANKED at 0/6, corrected from an earlier stale note on this
  page.** See "Measured so far (continued) — dc22" above. Two
  independently-sound fix attempts were built and live-measured, both
  still 0/6: the re-probe/toggler gap fix (per-button click memory,
  cosmetic-signature subtraction, stuck-state toggler cycling,
  route-proximity ranking; `de0510e`, 6 live smokes) and a parity-combo
  enumeration (`2209a5f`, Gray-code button-state gating instead of
  reactive stuck-triggered probing). The FINAL diagnosis (`b36fd8a`):
  gold's own solution is PROACTIVE/state-gating — it sets button parity
  BEFORE ever walking into a wall — while this adapter's whole
  walk-stuck-probe-learn architecture is fundamentally REACTIVE (a
  button click only ever happens in response to being stuck). No amount
  of tuning the reactive loop's heuristics can produce proactive
  behaviour; the wall is architectural, not a missing heuristic or an
  unaddressed classifier gap (the cosmetic-indicator-flip false-positive
  concern this bullet previously flagged is superseded by this finding
  — a probe-classification fix would not have closed an architectural
  mismatch). Banked with the full falsification writeup at commit
  `b36fd8a`; see [[../games/DC22]] for the game's own current status.
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
- **`docs/r56_kernel_catalog.md` refresh — DONE (`1ee9fff`).** The four
  missing functions/modules now have execution-verified examples: a new
  `parse.py` section (`occupied_runs`, `split_runs_by_pitch`, `color_mode`,
  `cluster_widths`) and `gf2.py` section (`gf2_solve`, `gf2_nullspace`),
  plus `split_fused_frame`/`recover_occluded_frame` added to the existing
  `geometry.py` section. Every example was run via `uv run python -c`
  against the real code, then cross-checked with `doctest.DocTestRunner`.
  The stale "seven modules" count in the Gaps section is also fixed to
  nine.
- **sb26's fused-frame recovery — resolved, corrected from two earlier
  stale notes on this page.** Both `f0b0bcb`'s live re-run AND wiring
  `recover_occluded_frame` alongside `split_fused_frame` landed
  (`bffe4be`); sb26 reached 3/8 live (`57b325d`, L1-L3, see "Measured so
  far (continued) — sb26" above). Remaining wall is L4, banked with a
  full falsification writeup in that same section (and on
  [[../games/SB26]]) — not a wiring gap, a genuinely unexplained per-board
  mechanic difference.

## Expansion sprint — 25/25 adapter coverage (2026-07-15 afternoon)

A single-afternoon parallel-teammate sprint took script25 adapter coverage
from 10 games to **25/25** (12 new adapters). Every number below is measured
(2x500-action live smoke on the adapter's own faithful RHAE loop unless noted);
each 0-bank ships with the game's mechanic DECODED and documented in the
adapter's module docstring (`src/admorphiq/adapters25/<game>.py`), not left as
an unmeasured gap.

**New clears (frame-only, no game-internal reads):**

| Game | Result | Commit | Mechanic + note |
|---|---|---|---|
| ar25 | 2/8 | `83c39f6` | mirror-reflection COVERAGE; learned-operator planner, L0 super-human (23a vs 32 human, level score 1.0) |
| re86 | 1/8 | `bfc5c18`/`2222a2e` | delivery + colour-assignment; **FIRST generic clear** (brittle ceiling was 6/8 via sprite tags); L2 wall = recolour |
| s5i5 | 1/8 | `757e4b2` | slider / goal-to-target; **first frame-only clear**, ties the brittle 1/8 |
| ls20 | 1/7 | `c8a7fd3` | shape/color/rotation-match maze — joint (position × token-appearance) BFS, not plain xy maze |
| sp80 | 1/6 | `6e86293`/`79ec697` | water-routing / spill-coverage; learned flow-operator planner, L0 super-human (10a vs 39 human, level score 1.0) |
| cn04 | 1/6 | `b7c6234` | rigid connector-marker arrangement (rotate+translate) — the old `zig3_A2A4` blind zig-zag scores 0 on the v2 hash |
| r11l | 1/6 | `7d2d17c` | click-driven drag-assembly (body follows leg centroids); resolves R57's unresolved T7/T8 case |
| sc25 | 1/6 | `cfde3a1` | two-phase pattern-toggle (auto-cast on match) then navigate; frame-keyed BFS with per-key click/move split clears L0 |

**Honest 0-banks with decoded mechanics** (measured negative, mechanic
documented, reopen pointer named): sk48 (`b24651e`, snake shape/pattern-match),
wa30 (`b34931b`/`ea15a44`, pick-carry-drop delivery), g50t (`dccc135`,
reactive Lolo-family maze, ACTION5=undo), bp35 (`f5447ac`/`e5e8217`, momentum
platformer), tn36 (`292d275`/`6eb0c02`, bit-panel programming puzzle), lf52
(`9587a5b`, cursor-move + click-to-connect, least-characterised public game).

### Learned-operator + configuration_path = 2/2 super-human levels

The round's strongest positive result: when an adapter LEARNS the game's
transition operator from its own undo-bracketed probes and then plans coverage
over the learned model (instead of blind frontier search), it clears at or
below the human action count.

- **Reflection kernel** (`e9ce9ec`, `learn_reflection_operators` /
  `plan_reflection_coverage`) — ar25 L0 in 23 actions vs a 32-action human
  baseline (level score 1.0), where the earlier blind transition-graph search
  needed ~835 actions for the same depth (scoring ~0 on squared-efficiency
  because it is blind to the reflection coupling that makes each move
  consequential).
- **Flow kernel** (`79ec697`, learned flow-operator + coverage planning) —
  sp80 L0 in 10 actions vs a 39-action human baseline (level score 1.0).
- **Delivery kernel** (`ea15a44`, `plan_delivery`: min-cost pickup->target
  assignment + per-leg `grid_shortest_path` + `path_to_moves`) landed and
  composes cleanly, but wa30 stays 0/9 — blocked on carry-follow physics (a
  box attaches and FOLLOWS the worker rather than teleporting to the goal), a
  divergence the generic route-and-interact model does not yet capture (open
  task #48).

### Three reusable explorer patterns

The blind explorers that clear single-goal games generalise across three
action alphabets, each reusable for the next game of its shape:

- **pure-move** frontier explorer (transition-graph BFS over ACTION1-4).
- **pure-click alphabet** — r11l's click-frontier over salient region
  centroids (ACTION6-only games).
- **hybrid move+click** — bp35's combined alphabet (simple move ids PLUS a
  bounded set of clicks at salient centroids) for games that mix both.

### Uniform-depth thesis

Across every new adapter the same ceiling recurs: a blind explorer clears a
level whose win is SINGLE-GOAL reachability (walk/route to one place, or click
one discoverable target), and never clears a level requiring a CHAINED or
PRECISE MULTI-SUBGOAL plan (deliver N boxes in order, transform a token
through K changer cells, set a multi-frame bit program). Every 0-bank's reopen
pointer therefore targets a LEARNED-OPERATOR kernel (learn the game's operator,
plan over the learned model), which is exactly the axis the ar25/sp80
super-human clears validate — not another blind-search budget bump.

### Two falsified reopen pointers, banked docs-only

Two games had a plausible "learn the dynamics, plan a route" reopen pointer
that a proper probe FALSIFIED before any planner was built — banked honestly
rather than shipping speculative code on a wrong model:

- **tn36** (`6eb0c02`) — the bits do not directly encode a route; they gate
  level-DATA trajectories run by a stateful multi-frame interpreter. The single
  visible bit row is ONE program frame; the winning program is a SEQUENCE of
  frame values advanced by play clicks, and the multi-frame editor's
  frame-SELECTOR is not frame-identifiable. The space of multi-frame bit
  programs is combinatorial — an opcode-learning planner would be speculative.
- **bp35** (`e5e8217`) — a momentum platformer with ACCELERATION and HIDDEN
  velocity, so the masked frame-key transition graph is ALIASED (R53 "dealias"
  territory); the `+` exit RECEDES 2 cells ahead of the player (no fixed goal a
  route can target); and clicking the colour-14 block centroids is inert (the
  "destroy-then-fall" model is unconfirmed). All three assumptions the reopen
  pointer rested on (fixed exit, fixed displacement, droppable blocks) are
  falsified.

Both falsifications came from probe-validity failures generalised into
[[../lessons/probe_validity_20260715]]: a determinism probe must use an action
that is actually AVAILABLE and actually MOVES the agent (bp35's original probe
issued the unavailable `ACTION1`, a no-op that trivially reproduced and falsely
"confirmed" determinism); a diff THRESHOLD can mask a real effect (tn36's 3-px
bit toggles were dropped by a large-diff sweep — cross-check the wiki's
recorded layout before trusting a fresh probe); and a decisive single-variable
probe (set-one-bit / single-click-from-reset) belongs BEFORE any planner build.

### Base fix + measurement environment

- **ACTION7 now surfaced** (`f586fd3`, task #46) —
  `adapters25.base.available_action_ids` was dropping ACTION7 (undo), which
  several mechanics (ar25 probe-undo, sk48/g50t undo) depend on; re-measured
  with no regression on the games that do not use it.
- **CPU bench env: `ceph-build`** — a free 64-core VM reproduced the GCP
  `r56s4` numbers BYTE-EXACTLY in a 10-game parallel run, and is now the
  official CPU bench environment (GCP credits are exhausted; see
  `memory/project_cpu_dev_vm_ceph_build.md`). script25's RHAE loop is
  CPU-only, so no GPU is needed for adapter measurement.

**Provenance commits (this sprint):** `83c39f6` (ar25), `c8a7fd3` (ls20),
`6e86293` (sp80 adapter), `b7c6234` (cn04), `7d2d17c` (r11l), `b24651e` (sk48),
`b34931b` (wa30 adapter), `dccc135` (g50t), `f5447ac`+`e5e8217` (bp35),
`fdc2b53`+`bfc5c18`+`2222a2e` (re86), `292d275`+`6eb0c02` (tn36), `9587a5b`
(lf52), `cfde3a1` (sc25), `757e4b2` (s5i5), `e9ce9ec` (reflection kernel),
`79ec697` (flow kernel), `ea15a44` (delivery kernel), `f586fd3` (ACTION7 fix).

## Depth phase — deeper levels via faithful state-models (2026-07-15 evening)

The afternoon reached 25/25 adapter COVERAGE (mostly L0/L1). The evening pushed
DEPTH on the games whose structure a faithful forward-model could search. Every
number below is verified against its committed `scripts/rounds/script25_<game>_*/
SUMMARY.txt` (see the "Provenance" line) — not a commit-message recollection;
one afternoon lane's unverified claim is the subject of
[[../lessons/false_claim_verification_20260715]].

| game | before | after | game_score | mechanism (verified) |
|---|---|---|---|---|
| sk48 | 0/8 | **3/8** | **0.1667** | faithful move-sim + A*; L2 via colour-5-bordered edge-snake parse; all clears super-human |
| lp85 | 1/8 | **3/8** | **0.1637** | ring-permutation planner (`kernels/permute.py`, tour+direction-vote); L2 & L3 capped 1.0 |
| su15 | 0/9 | **3/9** | **0.1035** | vacuum-pull merge-and-deliver decoded from source (resolved 9 prior vacuum-RING iterations) |
| sb26 | (afternoon) | **8/8** | **0.846** | N-portal DFS placement simulator (`_simulate_portal_dfs`), 170 actions |
| cd82 | (afternoon) | **6/6** | **0.98** | ring-paint replan-one-op, 97 actions |
| ka59 | 0/7 | **1/7** | **0.0205** | L0 launch-then-walk joint placement; L1 3-round arc banked (placement→slide→invisible-walk) |
| dc22 | 0/6 | **1/6** | **0.0272** | `plan_gated_path` product-graph (position × passability); L0 78a vs 59h (per-level 0.572) |
| tu93 | 2/9 | 2/9 | **0.0028** (was 0.0002) | goal-directed frontier expansion (11.6× efficiency, floor held) |
| cn04 | 0/? | **1/6 @1000** / **2/5 @5000** | **0.0309** / **0.2000** | geometric partner-matching; BUDGET-CONDITIONAL — 1/6 @1000 (Mac local, env `-2fe56bfb` shows /6) but **2/5 @5000** (VM ceph-build `r56s7`, 16:11 HEAD, env `2fe56bfb` shows /5). L2's occlusion-robust re-selection (`1e5006b`) needs the larger budget |

**Provenance (SUMMARY dirs):** `script25_sk48_edge`, `script25_lp85_l3` +
`_l4det2`, `script25_su15_sim_final` + `_enemy1`, `script25_sb26_l8b`,
`script25_cd82_smoke3`, `script25_ka59_l1char1`, `script25_dc22_gated`,
`script25_tu93_goalward3000` + `_3000b`, `script25_cn04_smoke2` (@1000 local) +
VM `~/r56s6`/`~/r56s7` (@5000, ceph-build). Commits:
`5189ded`/`dd0f750`/`d5eb5d5` (su15), `df0eb6f` (dc22), `6f61c11`/`b24d7ac`/
`0cf4f16`/`a2b7cb2` (ka59), `6760b09`/`476b209`/`799e718` (sk48), `a2e6d2e`/
`58987eb`/`fe1a06a`/`ed147a0`/`5dcdcbf`/`17619ea` (lp85), `6fd466c` (tu93),
`2c1ed0f` (cd82), `4513a4a`/`e9e0b19` (sb26), `1879864`/`1e5006b`/`650e530` (cn04).

**The load-bearing pattern of the evening: a FAITHFUL OFFLINE STATE-MODEL, then
search it.** Six of the clears above are the same shape — reconstruct the game's
exact state machine offline (portal traversal for sb26, slide/move semantics for
sk48, ring rotations for lp85, joint configuration for m0r0's afternoon 1/6,
position×passability product for dc22, vacuum-merge cascade for su15) and drive a
DFS / A* / BFS over it, instead of learning from sparse live reward. This is now
a named, reusable design rule — see [[../lessons/faithful_offline_simulator_20260715]].
The rule's trigger is exactly the sk48 case: when the live WIN signal is too
SPARSE to learn from (sk48's win fires once, at the end), a faithful offline
simulator is the only way to search the plan space cheaply.

**Two honest banks, verified against SUMMARYs, not upgraded:**
- **ka59 L1** — a genuine 3-round arc (placement fill → slide-hypothesis →
  invisible colour-15-walk correction) that still does not clear; floor held at
  1/7. Documented, not overstated.
- **cn04 — a BUDGET-CONDITIONAL result, both numbers real.** The @1000 Mac
  smokes (`script25_cn04_*`) all show **1/6 @ 0.0309**, so an interim "2/5 @ 0.20"
  looked false at first pass — but re-verifying on the VM (ceph-build, byte-quoted
  from `~/r56s6` and `~/r56s7`) shows it is genuine at a larger budget: `r56s6`
  (14:08 HEAD, @5000) = **1/5 @ 0.0667**, `r56s7` (16:11 HEAD, @5000) = **2/5 @
  0.2000**. cn04 L2 does NOT clear @1000 but DOES @5000 once the occlusion-robust
  re-selection (`1e5006b`) has enough budget. Both are recorded with their
  budget+env, per the sibling rule below. (Env-hash `2fe56bfb` reports **5**
  levels on the VM vs **6** locally — a preview/version discrepancy noted on the
  CN04 page.) The lesson is not "one number was wrong" — it is
  [[../lessons/false_claim_verification_20260715]]'s sibling rule: **a number
  without its budget + env is not a number.**

su15's L3+ wall (enemies reverse the merge cascade) and lp85's L4 wall (dense
20-ring self-test rejects single-press reconstruction) are both banked as
NEW-STRUCTURE ceilings on their game pages, not threshold tweaks.

## Official closing card — r56s7 full-25 (2026-07-15 night)

**Total = 3.7450 / 25 = 14.98%** — the day's official kernel-expressiveness card.
Triple: **budget = 5000, env = ceph-build (VM), HEAD = 16:11 (a2b7cb2-era)**,
per-game SUMMARYs in `~/r56s7/` on the VM. Arithmetic re-verified locally
(summed the 25 game_scores = 3.7450 exactly). Deployed-card proxy 5.83% →
**2.57× the deployable baseline**. This is EXPRESSIVENESS (script25), never
reported as agent capability — see the dual-scoreboard doctrine in this round.

| game | score | game | score | game | score |
|---|---|---|---|---|---|
| ft09 | 1.0000 (88a) | vc33 | 0.0357 | m0r0 | 0.0057 |
| cd82 | 0.9800 (97a) | ar25 | 0.0278 | tu93 | 0.0002 |
| sb26 | 0.8460 (170a) | re86 | 0.0278 | ls20 | 0.0000 (1/7, scores ~0) |
| tr87 | 0.2857 (503a) | dc22 | 0.0272 | bp35 | 0.0000 |
| cn04 | 0.2000 (2/5 @5000) | lp85 | 0.0248¹ | g50t | 0.0000 |
| su15 | 0.1035 (3/9) | ka59 | 0.0205 | lf52 | 0.0000 |
| r11l | 0.0476 | wa30 | 0.0222 | s5i5 | 0.0000 |
| sp80 | 0.0476 | | | sk48 | 0.0000² |
| sc25 | 0.0427 | | | tn36 | 0.0000 |

¹ lp85 0.0248 is the PRE-planner 1/8 — the r56s7 snapshot predates the
ring-permutation planner (now 3/8 @ 0.1637, commit `ed147a0`).
² sk48 0.0000 is the PRE-simulator 0/8 — snapshot predates the faithful
simulator (now 3/8 @ 0.1667, commit `476b209`). tu93 0.0002 likewise predates
goal-directed frontier (now 0.0028, commit `6fd466c`).

**HEAD estimate (NOT measured — do not cite as a card).** Swapping the three
post-snapshot landings into the r56s7 sum (lp85 0.0248→0.1637, sk48 0→0.1667,
tu93 0.0002→0.0028) gives an ARITHMETIC estimate of **4.0532 / 25 = 16.21%**.
This is an addition, not a run — the confirming measurement is **r56s8**
(launched ~20:00, current HEAD, same budget=5000 / env=ceph-build), PENDING.
Per the (value, budget, env) triple rule, 16.21% is not asserted as a card until
r56s8 lands.

**Day arc:** morning **5.85%** → r56s6 (14:08 HEAD) **~15.0%** → r56s7 (16:11
HEAD) **14.98% official** → r56s8 (current HEAD) **pending ~16%**.

## Final closing card — r56s9 full-25 (landed 2026-07-16 03:32 KST)

Two confirming runs landed overnight, each matching its arithmetic prediction
EXACTLY (deterministic adapters — every per-game number byte-matched its smoke):

- **r56s8** (20:00 HEAD, budget=5000, env=ceph-build): **4.0532 / 25 = 16.21%**
  — confirmed the 16.21% estimate above to four decimals. Snapshot predates the
  ls20 offline-reconstruction (`57eb823`/`e2b1794`) and sp80 multi-piece
  (`401a6e1`) landings.
- **r56s9** (e2b1794 HEAD — all 2026-07-15 work included, budget=5000,
  env=ceph-build, per-game SUMMARYs in `~/r56s9/` on the VM):
  **4.5056 / 25 = 18.02% — the R56 round's FINAL official card.**
  Deltas vs r56s8: ls20 0.0000→**0.3571** (4/7, all levels super-human),
  sp80 0.0476→**0.1429** (2/6, both super-human). All other 23 games
  byte-identical across s8/s9.

**R56 round summary:** deployed LLM-free card 5.83% → **18.02%** (3.09×) in one
round, via 25/25 quarantined kernel-composition adapters. Games at ≥0.1: ft09
1.0, cd82 0.98, sb26 0.846, ls20 0.357, tr87 0.286, cn04 0.20, sk48 0.167,
lp85 0.164, sp80 0.143, su15 0.104. Expressiveness only — promotion still
gates through agent25 + hidden transfer per the Codex verdict.

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
