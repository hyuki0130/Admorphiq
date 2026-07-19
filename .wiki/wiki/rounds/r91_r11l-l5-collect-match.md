---
round: R91
axis: r11l L5 collect-match build (task #116) — decode + perception + solver + navigation
keywords: r11l, l5, level5, whkxtx, collect-match, colour-set, puukul, collector, absorb, teleport-absorption, subset-cover, drag-assembly
verdict: Pass 1 DONE (mechanic fully decoded live + teleport-absorption simplification); Pass 3 BANKED on a frame-PERCEPTION wall — an interface overlay (colour-10 collector-reach field + colour-1 leg->body tendons) occludes/fragments the small collectibles (one, rengnt-8, fully hidden at entry). Multi-session perception round. Floor 4/6 byte-identical (no adapter change).
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

Related: [[r89_r11l-l5-probe]] · [[r85_r11l-strike-aware-assembly]] · [[../games/R11L]].
