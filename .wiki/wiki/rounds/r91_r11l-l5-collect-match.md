---
round: R91
axis: r11l L5 collect-match build (task #116) — decode + perception + solver + navigation
keywords: r11l, l5, level5, whkxtx, collect-match, colour-set, puukul, collector, absorb, teleport-absorption, subset-cover, drag-assembly
verdict: Pass 1-3 built. Mechanic decoded + teleport-absorption; perception-wall RETRACTED (colour-10 = 1-frame entry artifact); collect-match CONTROLLER (detection+solver+closed-loop, MEASURED-correct detection/assign) SHIPPED gated + floor-safe (4/6 @ 0.2594 byte-identical, verified ×2). L5 NOT yet cleared: greedy single-leg controller can't seat the body next to the wall within 60 actions — needs a 2-leg coordinated _plan_creature-style A* + wall pad (precise continuation banked).
commit: d901501, 6e7da27, cfe8fdd, 061c82d
---

# R91 — r11l L5 collect-and-colour-set-match build

> Multi-session L5 build, passes 1–3: mechanic decoded (teleport-absorption),
> perception-wall retracted, collect-match controller shipped gated and
> floor-safe (4/6 byte-identical); L5 not yet cleared — continuation = 2-leg
> coordinated A* + wall pad.

Multi-session build granted in [[r89_r11l-l5-probe]] / the R90 L5 BUILD HANDOFF.
Floor SACRED: r11l 4/6 @ 0.2594 on env `r11l-495a7899`.

## Pass 1 — perception probe (DONE, source reading CONFIRMED on the live board)

Drove the shipped adapter to `levels_completed==4` (Level 5) in 269 actions and
read `env._game` passively (`scripts/_r11l_l5_probe.py`, disposable). The R89
source decode is exact, with three build-critical refinements:

**Structure (5 creatures in `kacotwgjcyq`, keyed by name-suffix):**
- **2 collectors** (body-LESS `whkxtx` creatures): `roefwu-whkxtx` body @frame≈(32,32)
  with **2 legs**, `roefwu-whkxtx-2` body @≈(40,50) with **3 legs**. Both bodies
  START COLOURLESS (`col=set()`, 5×5 of pixel-0). A collector body = the CENTROID
  of its own legs (`rvkbignsyr`), exactly like the L1-L4 drag-assembly body — so the
  same leg-drag control applies.
- **4 collectibles** (`owuypsqbino`, `puukul-*`), each a single colour:
  blxuub={9}@(12,38), grhcew={14}@(18,51), rengnt={8}@(31,17), yeogyf={11}@(54,41).
- **2 real targets** (`flkdtg`, non-dirwzt, no body): `blxuubrengnt`={8,9}@(10,25,17,32),
  `yeogyfgrhcew`={11,14}@(45,6,52,13). Plus a `dirwzt` distractor target (skipped).

**Win** (`ldzvchvkvp` colour-set equality + overlap): each real target must be
overlapped by SOME collector whose ABSORBED colour set EQUALS the target's set.
Collectors are interchangeable (both start empty); subsets are DISJOINT and trivial
(each colour maps to exactly one collectible): target {8,9} ← {rengnt,blxuub};
target {11,14} ← {yeogyf,grhcew}. Over-absorbing a wrong colour breaks equality AND
removes that piece from the shared pool, so each collector must AVOID the other's 2
collectibles.

**Three build-critical mechanics facts (verified from source + live):**
1. **`_max_actions = 60`** hard budget (`lose()` at 60). Every select / place / refused
   place burns one.
2. **`havofgepjpl = 1` ⇒ TELEPORT absorption, NOT swept-path.** The body jumps
   straight to its legs' new centroid in ONE animation frame; `zlkgwqnxrp` checks
   body-vs-collectible collision ONLY at that final position. So absorption happens
   iff a leg-move leaves the body centroid OVERLAPPING a collectible — and every
   intermediate body centroid (after each single leg move) must avoid WRONG
   collectibles. This is the strike-aware-A* shape (avoid wrong-collectible cells as
   a body hazard; must land the body on each right collectible then the target).
3. **NO `defgjl` obstacle on Level 5** (only `wakneh-Level7` arena wall) ⇒ no
   body-collision strike; the only failure is wall-refused leg placement + the
   60-action budget. Collectors are fully INDEPENDENT (a leg re-centres only its own
   body); plan one fully, then the other.

**Frame-observable:** all target and collectible colours render on the frame
(collectors trackable via their legs' centroid, no need to detect the colourless
body region). Perception is sufficient for a frame-only solver.

## Build plan (Passes 2-4)

- **Pass 2 subset+assignment**: per target, required collectibles = subset whose
  colour union == target colour set (general subset-cover; trivial here). Assign the
  2 bodies to the 2 targets by cheaper total path.
- **Pass 3 navigation**: per collector, ordered body waypoints [collectible_a,
  collectible_b, target]; A* over single-leg moves (reuse `_plan_creature` shape)
  driving the body centroid onto each waypoint while every intermediate centroid
  avoids the wrong collectibles; legs stay `_LEG_SEP` apart and off the wall.
- **Pass 4 compose + gate** behind an L5-specific trigger (colourless-collector /
  puukul-collectible signature) so L0-L4 stay byte-identical.

## Pass 2 — subset + assignment (SPECIFIED, trivial here)

Per target, required collectibles = the subset whose colour UNION == target colour
set. On L5 each colour maps to exactly one collectible, so: target {8,9} ←
{rengnt(8), blxuub(9)}; target {11,14} ← {yeogyf(11), grhcew(14)}. Bodies start
empty and are interchangeable → assign the 2 collectors to the 2 targets by cheaper
total path. Write it as a general subset-cover over colours so L6 (more `puukul`
variety) reuses it.

## Pass 3 — navigation: BANKED on a frame-PERCEPTION wall (multi-session)

The L5 render is NOT the clean board L0-L4 detection assumes. An engine interface
(`xeuvojjxyk`, added in `on_set_level` for this level) draws, ON TOP of the board:
- **colour-1 tendon LINES** from each leg to its collector body (Bresenham,
  overwriting only bg/colour-10). 85 cells at entry.
- a **colour-10 collector-reach FIELD** around the collector body (235 cells,
  bbox rows 14-57 × cols 13-58 — nearly the whole interior).

Measured consequences on the clean L5-entry frame (`scripts/_r11l_l5_map.py`,
`_r11l_l5_overlay.py`, disposable):
- The camera transform is scale=1/offset=0, but frame_row = sprite.y + h//2 and
  frame_col = sprite.x + w//2 hold for the 7×7 TARGET rings and the collector body,
  yet the puukul CENTRES land on bg — the small collectibles are DISPLACED /
  occluded by the overlay, not where the naive map predicts.
- The 2 real TARGETS are cleanly frame-visible as TWO-colour ~7×7 hollow rings:
  blxuubrengnt{8,9} and yeogyfgrhcew{11,14} (each a colour-a arc adjacent to a
  colour-b arc). This is a good discriminator vs the single-colour dirwzt rings.
- The 4 COLLECTIBLES are single-colour ~5×5 blobs, but **not all are visible at
  entry**: colour-8 has only 10 cells on the whole frame — all of them the target's
  8-side ring — so the `rengnt`(8) collectible is FULLY OCCLUDED under the colour-10
  field. colour-14 shows spurious extra fragments. So a one-shot entry-frame scan
  cannot see all 4 collectibles.

**The wall = robust frame perception of collectors + collectibles under this
overlay.** It is a dedicated perception round, not a bounded pass. **Actionable
leads for the next lane** (the overlay is also SIGNAL):
1. **Mask the overlay first**: colour-1 and colour-10 are overlay-only (never a game
   piece) → set them to bg before segmenting. (Verify colour-10 is never a real piece
   on other levels before shipping any gate.)
2. **Collectors via the colour-1 tendons OR the leg centroid**: each collector body =
   the centroid of its own legs; legs are the colour-3/0 crosses (as L0-L4). The
   colour-1 tendons converge on each body → free leg↔collector grouping (2 groups:
   2-leg + 3-leg).
3. **Targets** = the 2 TWO-colour ~7×7 rings (colour-set = the ring's two colours).
   dirwzt rings are single-colour → skip.
4. **Occluded collectibles need dynamic re-observation**: the colour-10 field is
   around the ACTIVE collector (the one whose leg is selected). Selecting the other
   collector's leg (a click) moves the field and reveals a hidden collectible — so
   perception must re-scan as the board changes (the R88 stochastic re-detect
   pattern), not trust the entry frame. This couples with Pass-3 navigation.

Because Pass 3 needs this perception layer first, NO adapter code was written — the
floor stays byte-identical 4/6 @ 0.2594. Disposable probes kept for the next lane:
`scripts/_r11l_l5_probe.py` (ground truth), `_r11l_l5_map.py` (grid→frame map),
`_r11l_l5_overlay.py` (overlay masking + collectible scan).

### R91b — PERCEPTION WALL RETRACTED (the colour-10 field is a one-frame entry artifact)

`scripts/_r11l_l5_occlude.py`: after the FIRST action on L5 the colour-10 field drops
from 235 cells to **0** and colour-8 jumps 10→17 — the "occluded" `rengnt`(8)
collectible becomes fully visible. So colour-10 is an ENTRY/interface transient that
clears on the first `complete_action`, NOT a persistent occluder. The existing
`_SETTLE_FRAMES` gate (which clicks refused wall cells while the level animates in)
already waits past exactly this, so detection on the settled frame is clean.

`scripts/_r11l_l5_settled.py` validates the SETTLED-frame detector signatures (all
frame-only, colours read from the frame, no hardcoded coordinates):
- **Collectors (2)** = colour-0 SOLID ~5×5 blobs (size ~21, fill ~0.84) sitting at the
  centroid of their leg groups; equivalently detect legs (colour-3 crosses + the one
  colour-0 SELECTED leg, fill ~0.48 size ~12), proximity-cluster into 2 groups,
  body = group centroid (matches the mechanic).
- **Collectibles (4)** = SOLID single-colour blobs, fill ≥ ~0.6 (size ~10-11), colours
  {8,9,11,14}. (The dirwzt target rings share those colours but are HOLLOW, fill ~0.24
  — fill separates them.)
- **Real targets (2)** = TWO-colour hollow ~7×7 rings {8,9}@ and {11,14}@; dirwzt
  targets are SINGLE-colour rings (remapped 7/9/14) — separated by 2-colour + the R87
  nested-colour-set discriminator (`_target_score`).

The build (perception → subset/assign → closed-loop navigation with teleport
absorption, re-detecting each step) proceeds from here; probe `_r11l_l5_occlude.py`
+ `_r11l_l5_settled.py` kept.

### R91c — collect-match CONTROLLER built (detection+solver+closed-loop), floor-safe; L5 not yet cleared — navigation-efficiency wall

Commit `061c82d`. The Level-5 handler is implemented in `src/admorphiq/adapters25/r11l.py`,
gated behind the collect-match signature so L0-L4 are **byte-identical (verified
4/6 @ 0.2594 twice)**:
- `_detect_collect_match` — MEASURED-correct on the live board: 2 collectors
  ((34,34) 2-leg, (52,42) 3-leg), 4 collectibles (8@,9@,11@,14@), 2 targets
  ({8,9}@(28,13), {11,14}@(9,48)). Key fix over the first cut: cluster legs by
  NEAREST BODY (colour-0 solid blob, fill≥0.78) — a single leg-proximity threshold
  can't separate the two collectors (their legs interleave: inter-collector 13 <
  intra 18). The body-fill discriminator (`_CM_BODY_FILL=0.78`: collector body
  ~0.84 vs collectible ~0.7) is what keeps the gate OFF on L0-L4 coloured bodies.
- `_setup_collect_match` — subset-cover + cheaper collector↔target permutation
  (both L5 permutations are near-equal cost; picked the marginally cheaper).
- `_collect_step`/`_collect_place` — closed-loop greedy single-leg controller,
  re-detects each step, teleport-absorption model, learns engine-refused cells
  (`_cm_bad`, the R88 under-covering-wall pattern) so it reroutes.

**The wall (navigation efficiency).** Traced live (`scripts/_r11l_l5_trace.py`,
`R11L_DEBUG=1`): the controller activates and assigns correctly but absorbs
NOTHING and burns the 60-action budget. Root cause is measured, not guessed: to
put the body centroid on a wall-adjacent collectible (e.g. 14@(53,19)) with ONE
leg fixed, the moved leg would need row ~71 (off-board), so the greedy keeps
proposing row-61 cells that the engine's true wall REFUSES (frame hazard
under-covers it). Learned-refusal reroutes but there are too many wall cells to
mark within 60 actions. **A single-leg greedy cannot seat the body next to the
wall; it needs a 2-LEG COORDINATED plan** — exactly the shape of the existing
`_plan_creature` A* (ordered single-leg moves landing the body in a target box
while every intermediate centroid avoids a hazard).

### R91d — nav planner + assignment fixed; wall = arena-WALL PLACEABILITY under-coverage (learned-placeability is the fix)

Commits `cdc56ab` (+ `061c82d`). Two improvements shipped (floor byte-identical
4/6 @ 0.2594, 8 tests green): (1) `_collect_pick_move` now solves BOTH legs' final
cells with `points_with_centroid` (seats the centroid exactly on the goal) instead
of a greedy one-leg step; (2) `_setup_collect_match` uses MANHATTAN path cost — the
squared cost mis-assigned the FAR collector to a wall-adjacent collectible; Manhattan
gives the natural assignment (whkxtx→{8,9}, whkxtx-2→{11,14}, verified).

**Root cause of the non-clear, now ISOLATED (manual engine probe, disposable):**
select→place DOES work on L5 and is PREDICTABLE — a manual place moved a whkxtx leg
and the leg CENTER lands at the clicked frame cell (engine `leg = click − half`, a
near-identity transform, NOT a rotation despite the wakneh-90° wall). So the
controller's legs-don't-move is NOT a coordinate/select bug: the solved cells near a
goal are ENGINE-REFUSED because the frame hazard SIGNIFICANTLY UNDER-COVERS the L5
octagon wall (the R59/R88 lesson), and `points_with_centroid` keeps proposing
wall-marginal cells (learned-refusal + a 1-cell pad don't cover enough of the gap
within 60 actions). Cells were refused even top-center, confirming the frame wall
model is too thin.

**Precise continuation (the real fix = LEARNED PLACEABILITY, R59's original r11l
reopen):** don't trust the frame `is_free`/hazard for wall cells — LEARN the
placeable region online from observed click→move outcomes (a placement that fires =
that cell is free; a refused one = blocked), and feed that learned mask to
`points_with_centroid`'s `is_free`. Seed it by probing a few placements at level
start. This is the same "learn which cells accept a leg" lever R59 named for L1 and
is now the gating piece for L5's collect-match navigation. THEN handle the
post-absorption re-detection (below).

**Superseded earlier guess (kept for the record):** replace the greedy `_collect_pick_move`
with a `_plan_creature`-style A* over the collector's FULL leg config, goal =
body centroid within `_CM_ABSORB_TOL` of the next collectible (then the target
box), hazard = wall PLUS the wrong collectibles (avoid over-absorbing), and PAD
the wall hazard a cell (the collectibles sit near the wall, so a few refusals are
unavoidable — pad to cut them). Then handle the post-absorption re-detection: once
a collector absorbs, its body GAINS colour (no longer colourless) — `_detect_collect_match`
must track a collector that has turned coloured (match by body POSITION continuity,
not just the colourless test). Probe `_r11l_l5_trace.py` kept.

Related: [[r89_r11l-l5-probe]] · [[r85_r11l-strike-aware-assembly]] · [[../games/R11L]].
