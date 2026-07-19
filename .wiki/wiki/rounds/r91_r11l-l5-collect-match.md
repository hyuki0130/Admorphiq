---
round: R91
axis: r11l L5 collect-match build (task #116) — decode + perception + solver + navigation
keywords: r11l, l5, level5, whkxtx, collect-match, colour-set, puukul, collector, absorb, teleport-absorption, subset-cover, drag-assembly
verdict: (in progress) Pass 1 perception CONFIRMED live — mechanic fully decoded, teleport-absorption simplification found; build continues
commit: (this round)
---

# R91 — r11l L5 collect-and-colour-set-match build

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

Related: [[r89_r11l-l5-probe]] · [[r85_r11l-strike-aware-assembly]] · [[../games/R11L]].
