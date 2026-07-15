"""script25 quarantined adapter: SU15 (vacuum-merge family).

*** QUARANTINE — MODEL-NEVER-VISIBLE. See admorphiq.adapters25's package
docstring. ***

``.wiki/wiki/games/SU15.md`` and ``.wiki/wiki/game_types/merge_puzzle.md``
(read for reference, not imported) describe SU15 as a 2048-style merge
puzzle: ``ACTION6(x, y)`` creates a vacuum that pulls nearby movable value
tiles toward the click point; two same-color tiles that overlap merge into
one tile of color+1; the level clears once the right count/color of tiles
sits inside a distinct GOAL container region. The wiki also records a
measured ``~8px`` vacuum radius and a fixed absolute step size, but those
numbers come from the LEGACY, game-internal-access solver
(``src/admorphiq/agent_ensemble.py``'s ``strat_su15_vacuum``) and the
frame-only ``src/admorphiq/merge_drag.py`` this module deliberately does
NOT import (quarantine: stdlib + admorphiq.kernels + admorphiq.adapters25.base
only) — its absolute-pixel tunables (``_MERGE_DIST_PX``, ``_DRAG_STEP``,
etc.) are exactly the kind of game-specific constant this adapter must not
inherit.

**R56 iteration 5 -- two mechanic hypotheses tested live, one falsified,
one fixed:**

1. **"select-then-place" (a click SELECTS a tile, a second click PLACES
   it), FALSIFIED.** ``avail`` for this game is measured ``[6, 7]`` only
   (no ACTION5) -- reading ``src/admorphiq/world_model_agent.py``'s own
   routing gate confirms this structurally: its select-toggle arrangement
   phase requires ACTION5, and its ``_merge_drag_step`` (a SINGLE-click
   model, the one that actually clears SU15 L1-2 in ~58 actions) is
   entered specifically when 1-5 are ALL absent and 6+7 are present -- SU15
   is its cited example. Live probe (click ON a tile, then click the
   goal): the tile's distance to goal was IDENTICAL before and after both
   clicks (19.7px both times) -- the second click pulled something else
   entirely, never the "selected" tile. Two-click select-then-place is not
   this game's mechanic.
2. **Fraction-of-remaining-distance (this module's own iteration 1-4
   design), the REAL bug, found while testing hypothesis 1.** A probe
   walked a single tile through absolute click-ahead offsets of 5px, 7px,
   10px from ITS OWN position: 5px and 7px (note -- close to
   merge_drag.py's OWN measured ``_DRAG_STEP``/``_MERGE_STEP`` constants,
   arrived at independently here) produced ZERO shift; 10px worked. Since
   this module's ``_fraction`` was a FRACTION of the total remaining
   distance, the ABSOLUTE click-ahead offset it produced SHRANK every time
   a tile got closer to its target -- exactly backwards, since getting
   closer is the whole point of gathering. Once a click's absolute offset
   fell below the true effective threshold, escalation only made the
   FRACTION bigger, not the useful thing (a modest absolute nudge) --
   fraction rockets toward its ceiling and clicks become huge, distant,
   overshooting jumps instead of the small local nudges the mechanic
   actually needs.

The fix: :func:`admorphiq.kernels.point_toward` is now called with an
ABSOLUTE pixel distance (``_step_px``), not a fraction of the remaining
distance. ``_step_px`` starts small and escalates (via
:func:`admorphiq.kernels.frame_diff` on the observed before/after)
whenever a click produces no visible change, exactly like the old fraction
did -- but now escalation makes the click reach FARTHER in absolute terms
regardless of how close the target already is, matching the measured
mechanic (a modest, roughly-constant nudge, recomputed fresh every call).

**R56 iteration 6 -- the absolute-step model REGRESSED (GAME_OVER 14->15,
true useful-click rate 29%->6.8%), root-caused, and fixed with three
policy changes, all still composed from ``admorphiq.kernels``:**

1. **Measured floor.** :data:`_MIN_EFFECTIVE_PX` (10.0, the measured
   working value from the iteration-5 probe -- 5px/7px dead, 10px worked)
   is a hard floor: ``_step_px`` never starts, escalates, or resets below
   it.
2. **Overshoot instead of clamp.** The regression's actual driver:
   :func:`admorphiq.kernels.point_toward` clamps to the destination
   exactly when the step would overshoot it -- so once ``_step_px`` grew
   past a shrinking remaining distance (which happens constantly as a
   gather nears completion), EVERY click landed exactly ON a tile/goal
   centroid, a measured no-pull zone (this module's very first probe:
   clicking directly on a tile produces zero shift). :func:`_click_toward`
   now detects that regime itself (step >= remaining distance) and
   computes the click with its own unit-vector arithmetic, deliberately
   landing PAST the destination -- the vacuum pulls toward the click
   point, so a click beyond the goal still pulls goal-ward.
   ``point_toward`` remains in use for the normal (step < remaining)
   regime; only the clamping regime is bypassed.
3. **Success-reset de-escalation.** ``_step_px`` still escalates x1.5 on a
   not-useful click (as iteration 5), but a USEFUL click now resets it
   back to :data:`_MIN_EFFECTIVE_PX` instead of staying escalated forever.
   This is what actually bounds the runaway: iteration 5's step only ever
   grew, so a handful of early misses on a long-distance target permanently
   inflated it for every LATER, shorter-distance click too. Escalation now
   tracks "is THIS click succeeding", not "how many failures has this run
   accumulated overall".

**R56 iteration 7 -- perception layer fixed via gold-replay divergence
(2026-07-15), four real bugs closed, STILL 0/9 -- BANKED here with a named
next-hypothesis, not resolved.** Replayed ``data/traces/su15.npz``'s L1
gold block against this adapter's own ``_next_target``/``_candidates``:

1. **Fragment fusion.** A single game tile renders as ~15-17
   DISCONNECTED same-colour regions (a symmetric bowtie sprite, not one
   connected blob) -- ``_candidates`` had no fusion step, so every
   fragment was its own spurious candidate. Fixed via
   :func:`admorphiq.kernels.find_regions`'s own ``gap`` parameter
   (gap-tolerant cell clustering -- no new kernel needed): a 9-level
   offline acceptance table over every opening frame in ``su15.npz``
   showed ``gap=2`` fuses every measured bowtie into one region with a
   true aggregate centroid while NEVER merging two genuinely distinct
   same-coloured tiles (L9's 4 separate colour-9 tiles, 61px apart, stay
   4 distinct regions through ``gap=4``). See :data:`_CANDIDATE_GAP`.
2. **Scatter-detection stray contamination.** The old ``_scatter_colors``
   measured density over a colour's FULL region list unscoped -- one
   UNRELATED same-coloured region far from a real, dense tile inflated
   the whole group's bbox enough to push density under threshold,
   silently deleting the real tile's every fragment from candidates (not
   mis-ranked -- gone). Fixed via :func:`_spatial_subgroups` (see
   :data:`_SUBGROUP_RADIUS`): density is now measured per LOCAL subgroup,
   computed on the FINE-grained (``gap=0``) region list specifically
   (gap-fusion would hide a genuine scattered pattern's own sparse
   signature the same way it correctly fuses a real tile's fragments).
3. **First-click pair-preference.** On the very first, zero-evidence
   decision, ``_ranked_targets`` defaulted to a same-colour PAIR guess --
   unable to distinguish two coincidentally-same-coloured STATIC
   decorations from a genuine mergeable pair with no prior observation.
   Measured directly: the adapter's first click targeted two never-moving
   decorative regions where gold instead targeted the one colour-unique,
   genuinely movable tile. Fixed via ``prefer_lone=True`` on click 0 only
   (:attr:`Adapter._clicks_this_level` gates it, resets every level).
4. **Pool-exhaustion re-enabling dead tiles** (found via LIVE-smoke
   diagnostic on the above fixes, not the original divergence replay).
   ``_next_target``'s "unless that empties the pool entirely" fallback
   reverted to the FULL unfiltered tile list once every candidate
   accumulated dead/fatal status -- re-enabling tiles already PROVEN
   useless, an infinite retry loop (measured live: a static decoration
   dead-bucketed at step 8 got re-picked at step 19 via exactly this
   path). Fixed: degrade to the harmless centre re-probe instead of ever
   resurrecting a proven-dead bucket.

Acceptance: re-ran the divergence replay after the fixes -- click 1's
source now matches gold's exactly (centroid ``(53, 10)``, the
colour-unique tile), not the static ``(5, 31)``/``(59, 4)`` decoration
pair. The 9-level offline candidate table confirms correct fusion with
zero over-merging anywhere. **Live smoke (2x500 + 1x3000a): still 0/9,
game_score 0.0, reproducible.** The candidate-detection layer is now
verified correct end-to-end; the wall has moved from perception to
mechanic understanding.

**NEXT HYPOTHESIS (not yet built -- the explicit reopen pointer for a
future session, per the team's "bank, don't re-derive" convention).** A
live diagnostic traced the correctly-identified click-1 target
(``(53, 10)``, colour 0, size 5) across ~15 further steps post-fix: it is
STATIC -- unchanged across steps 6, 8, 10, 11 despite being repeatedly
clicked -- while a SEPARATE, larger (~48-54 size) colour-0 blob is the
one whose position actually changes every single step. This suggests the
"vacuum" mechanic (the game's own name) may PULL a distant object toward
the click point rather than DRAG the region nearest the click: the
moving ~50-cell blob is likely the controlled/pulled entity, and the
small static tiles (like ``(53, 10)``) may be targets/receptacles/anchor
markers, not the thing being dragged. If so, this adapter's entire
source-tile IDENTITY model -- "the region nearest the click point is the
thing being moved", used throughout dead-click/fatal-click/useful-shift
tracking -- needs re-deriving from gold with THIS frame specifically
before any further policy work; the click-POSITION divergence fix above
is directionally correct (matches gold) but may be built on the wrong
object-identity assumption. See ``.wiki/wiki/games/SU15.md`` for the same
finding cross-linked into the wiki.

**R56 iteration 8 -- gold-replay divergence RESOLVES the source-identity
reopen: SU15 is CLICK-TO-STEER NAVIGATION, not vacuum-pull. The whole
vacuum-merge-nearest model above is WRONG.** (2026-07-15; ``data/traces/
su15.npz`` replayed frame-by-frame + confirmed live.)

1. **A single PLAYER follows clicks EXACTLY.** Across all 9 gold levels the
   moving entity is ONE blob (colour 0, ~48-52 cells) whose centroid lands
   AT the click point every step (click-distance -> 0). A live follow-test
   (five clicks 7px apart along a diagonal) reproduced it: one colour-0
   size-48 region sat on each click, dist 0, every time. The small static
   tiles near a click (e.g. ``(53, 10)`` colour 0 size 5, the iteration-7
   "target") are DECOYS/anchors -- they never move. So the reopen's guess
   was RIGHT that the ~50-cell blob is the controlled entity, but the
   mechanic is not "vacuum pulls a distant object toward the click" -- it is
   "the PLAYER moves to wherever you click". There is NO vacuum, NO
   click-near-a-tile-to-drag-it; the region nearest the click is irrelevant.
2. **The gold trace TRANSFERS to the live env.** Replaying gold's exact 101
   clicks on the live ``su15-1944f8ab`` env (gold was recorded on
   ``su15-4c352900``) clears ALL 9 levels (WIN) -- su15's per-level layouts
   are identical across hashes; the hash is cosmetic. So gold's clicks are a
   valid oracle for every level here.
3. **The WIN is a stateful MERGE/CONVERSION, not "reach a goal tile"
   (falsified two ways).** (a) Steering the player ONTO the largest colour-9
   tile (they merge into one region at its centroid) does NOT clear L0. (b)
   Steering the player to gold's exact winning cell ``(19, 44)`` and holding
   does NOT clear L0 either. Gold cleared L0 on the specific click that moved
   the player ``(24,39)->(19,44)`` while the colour histogram changed
   ``{9: -8, 5: +11, 3: -1}`` -- i.e. the player's diagonal SWEEP converts
   tiles as it passes, and the level clears when the swept configuration
   reaches the goal spec, not when the player reaches a position.
4. **Enemies exist and cause GAME_OVER on contact.** Steering the player
   toward a colour-3 tile GAME_OVERed within ~5 steps -- colour-3 (and
   similar small tiles) behave like the wiki's "enemies chase / downgrade".

**NAMED MISSING CAPABILITY (the redirected reopen):** REPLACE this module's
vacuum-merge model with player-steering navigation -- (i) identify the
player as the colour-0 blob that lands on the last click (or the largest
movable non-container blob); (ii) decode the MERGE/CONVERSION rules (what the
player's contact/sweep does to each tile colour, and what target
configuration -- from the goal spec -- triggers the level clear); (iii) plan
a collecting SWEEP path that reaches that configuration while AVOIDING enemy
tiles; (iv) steer with :func:`admorphiq.kernels.point_toward` (already
correct). The player-steering primitive is trivial (the player follows
clicks); the depth is entirely in the merge-rule decode + collecting-path
plan. Gold (9/9 live) is the oracle for validating any such planner.

Role assignment (declared HERE, not in the kernel layer, which knows
nothing about tiles, goals, enemies, or merging):

  - The GOAL container is the largest surviving candidate region (matches
    the wiki's own "goal zones are designated regions"; a destination
    container reliably renders bigger than the small value tiles it
    receives -- independently re-derived here, not copied from
    merge_drag.py's identical heuristic).
  - Every other candidate region is a movable value TILE, unless its
    coarse position-bucket is DEAD (see below).
  - **HAZARD role, tried and REMOVED (R56 iteration 2 -> 3 falsification)**:
    iteration 2 tagged any region that shifted far from the click just
    issued as an autonomous "enemy" mover and excluded it from targeting.
    Correctly implemented (a real bug -- SU15's flickering status row
    initially polluted the signal -- was found and fixed first), it fired
    ZERO times across a reproduced 500-action run while GAME_OVERs stayed
    essentially unchanged (14 -> 15). Measured-inert and su15-local, so
    per the repo's "no speculative safety nets" discipline it is REMOVED
    here rather than kept dormant; the implementation is preserved in
    commit ``cb8a205`` if a future measurement ever motivates reviving it.
  - **Dead-click memory** (R56 iteration 3, replacing the hazard role):
    the wiki's own lesson log (not the removed hazard theory) records the
    real mechanism -- repeated clicks on an unresponsive tile accumulate
    toward GAME_OVER. Mirrors ``admorphiq.adapters25.m0r0``'s dead-cell
    design: a tile's coarse position-bucket (:func:`_tile_key`) that has
    been the click SOURCE :data:`_DEAD_CLICK_THRESHOLD` times with no
    useful shift (see :data:`_MIN_USEFUL_SHIFT`) is marked dead and
    excluded from future target selection for the rest of the level.
    Iteration 3's "useful" check measured a DOMINANT shift ANYWHERE on the
    frame, which turned out to always find something to credit (100%
    useful-shift rate, dead-click memory never firing) even while a
    forensic 6-action-window trace showed the SAME merge target being
    re-clicked 5+ times with the intended pair never actually converging.
    Iteration 4 tightens "useful" to require the CLICK'S OWN SOURCE tile
    (identified in ``regions_before`` by nearest centroid to the exact
    point recorded at commit time) to be the one that moved -- a merge
    collapsing the source into its partner (the source vanishing) also
    counts as useful, since that IS the mechanic succeeding.
  - **Fatal-click memory** (R56 iteration 4): a forensic trace of the
    first 3 GAME_OVERs (reproduced identically, deterministic env) found
    the SAME click target killing the run 3/3 times, always immediately
    after several identical stalled clicks elsewhere. One death is
    sufficient evidence -- unlike dead-click memory's repeat-count
    threshold, a source bucket whose click was IMMEDIATELY followed by a
    GAME_OVER (detected the same way ``admorphiq.adapters25.m0r0`` detects
    a restart snap-back: the frame reverts to the exact level-start frame
    while the PRE-click frame had already diverged from it) is excluded
    permanently for the rest of the level on the FIRST occurrence.
  - Two same-color tiles are a MERGE candidate; a lone tile (or once no
    same-color pair remains) is driven toward the goal (GATHER). Every
    same-color pair is ranked nearest-first, then every lone tile ranked
    farthest-from-goal-first, and the first (now: only) entry is chosen
    (see :func:`_ranked_targets`).
  - **Coverage rotation** (R56 iteration 2): if the SAME tile keeps being
    picked as a click source too many times in a row (the same coarse
    position-bucketed identity dead-click memory uses), the ranking is
    overridden ONCE and the LEAST-recently-targeted tile is driven toward
    the goal instead. First pass measured a tile that was never once
    selected across a full 500-action run because a different same-color
    pair kept out-ranking it every single call.
  - Candidate regions exclude two classes of chrome, both detected by
    RELATIVE frame geometry, never absolute pixel coordinates: (a) a HUD
    band -- a region spanning almost the full width or height of the frame
    while being only a few cells thick (measured live: SU15's own bottom
    status row is exactly this shape and was, uncorrected, misidentified
    as the goal because it is the single largest region on the frame); (b)
    a SCATTERED decorative line -- a color rendered as many small clusters
    sparsely spread over a large bounding box (measured live: SU15's
    diagonal step-line pollutes naive candidate lists the same way
    :mod:`admorphiq.merge_drag`'s own docstring describes for a different
    game).

Composition from ``admorphiq.kernels``:
  - :func:`admorphiq.kernels.find_regions` segments the frame.
  - :func:`admorphiq.kernels.frame_diff` + :func:`admorphiq.kernels.find_regions`
    (before/after) + :func:`admorphiq.kernels.track_objects` measure
    whether the click's OWN source tile moved (or merged away) -- this
    single measurement drives step-size escalation, dead-click counting,
    AND (via a separate frame-identity comparison against the level's
    start frame) fatal-click memory.
  - :func:`admorphiq.kernels.point_toward` replaces this adapter's own
    hand-rolled vector arithmetic from the first pass -- composition over
    local math.

Deliberately still out of scope (this is a proof-of-concept, not a full
solver): merge-order lookahead, and any enemy/downgrade interaction
(``restart_on_game_over`` is set so a GAME_OVER costs one action, not the
run; dead-click memory addresses the wiki-documented "repeated dead click"
GAME_OVER path specifically, not a hostile-entity interaction).
"""

from __future__ import annotations

from typing import Any

from admorphiq.adapters25.base import (
    GameAction,
    GameAdapter,
    available_action_ids,
    canonical_layer,
    click_action,
    has_frame,
    most_common_color,
    reset_action,
    state_name,
)
from admorphiq.kernels import find_regions, frame_diff, point_toward, track_objects

GAME_ID = "su15"

Cell = tuple[int, int]  # (row, col)
Region = dict[str, Any]

# Per-level safety cap, mirroring the sibling adapters' giveup convention.
_GIVEUP_DEFAULT = 4000

# A region spanning at least this fraction of the frame's own cell count is
# a board-spanning panel, never a discrete tile/goal.
_MAX_CANDIDATE_FRACTION = 0.15
# A region whose bbox spans at least this fraction of the frame's width (or
# height) while being at most this fraction of the frame's height (or
# width) thick is a HUD band (status row/column), not a game object -- both
# fractions are relative to the LIVE frame's own dimensions, never a fixed
# pixel count. Measured necessary: SU15's bottom status row is exactly a
# 1-tall, full-width strip and was, uncorrected, the single largest
# candidate region (mistaken for the goal container).
_HUD_SPAN_FRACTION = 0.85
_HUD_THICKNESS_FRACTION = 0.06
# A color rendered as at least this many separate clusters, spread sparsely
# (fewer clusters per unit bbox area than this) over its own bounding box,
# is a scattered decorative line, not a set of movable tiles. Measured
# necessary: SU15's diagonal step-line.
_SCATTER_MIN_CLUSTERS = 10
_SCATTER_MAX_DENSITY = 0.05
# Proximity radius (px, centroid-to-centroid) for grouping one colour's own
# regions into spatial SUBGROUPS before the scatter test runs -- a real bug
# measured directly (R56, gold-replay divergence against su15.npz L1/L2): a
# single UNRELATED same-coloured region far from a genuinely dense, real
# tile inflated that colour's overall bbox enough to push the WHOLE group's
# density under _SCATTER_MAX_DENSITY, silently excluding the real tile's
# every fragment from candidates entirely (not mis-ranked -- gone). Grouping
# by single-linkage chaining at this radius scopes the density test to each
# LOCAL cluster: a real tile's own fragments (measured ~2-8px apart) chain
# into one subgroup with its own tight bbox regardless of a distant stray;
# a genuinely scattered decorative pattern (SU15's diagonal step-line,
# consecutive dots ~2.8px apart) still chains into one elongated subgroup
# and is still correctly measured as sparse over its own (large) bbox.
_SUBGROUP_RADIUS = 10.0
# Gap-tolerant clustering radius (kernels.find_regions' own `gap` param --
# same-colour CELLS within Chebyshev distance gap+1 join one region) used
# for the CANDIDATE-EMISSION pass only (never for scatter classification,
# which needs gap=0's fine-grained fragments to preserve the true sparse-
# pattern signal -- see _candidates). Measured (R56, 9-level offline
# acceptance table over every opening frame in su15.npz): a single game
# tile renders as ~15-17 DISCONNECTED same-colour fragments (a symmetric
# bowtie sprite shape, not one connected blob); gap=2 fuses every such
# bowtie into one region with a true aggregate centroid on all 9 levels
# while never merging two GENUINELY distinct same-coloured tiles (e.g. L9's
# 4 separate colour-9 tiles, sizes [49,64,69,69] spread 61px apart, stay 4
# distinct regions through gap=4) -- the smallest gap value that fully
# resolves every measured bowtie case.
_CANDIDATE_GAP = 2

# Measured minimum click-ahead distance (px) that ever registered a shift
# (iteration-5 probe: 5px/7px dead, 10px worked) -- both the STARTING
# ``_step_px`` and the floor it is never allowed below, including on
# success-reset (see the module docstring's iteration-6 section).
_MIN_EFFECTIVE_PX = 10.0
# Growth factor applied to _step_px on a not-useful click; reset back to
# _MIN_EFFECTIVE_PX on a useful one (iteration 6 -- iteration 5's step only
# ever grew, so a handful of early misses permanently inflated every LATER
# click too, well past the point it was still needed).
_STEP_GROWTH = 1.5
# Capped well under half the board so an escalated step stays a local
# nudge, never a huge cross-board jump.
_MAX_STEP_PX = 30.0
# A measured dominant shift smaller than this (in px) is treated the same as
# "nothing moved" for escalation purposes -- a click that barely nudged
# something is not yet at a useful working distance either. Small relative
# to the frame (64px on the measured env) but not a coordinate: it bounds a
# MAGNITUDE, not a position.
_MIN_USEFUL_SHIFT = 1.5

# A tile's coarse position-bucket (see _tile_key) that has been the click
# SOURCE this many times with no useful shift is marked dead -- mirrors
# admorphiq.adapters25.m0r0's dead-cell threshold, and directly targets the
# wiki-documented "repeated dead clicks accumulate toward GAME_OVER" cause
# (unlike the removed hazard mechanism, which measured inert).
_DEAD_CLICK_THRESHOLD = 3

# If the SAME (coarsely-bucketed) tile has been the click SOURCE this many
# times in a row, the ranking is overridden once in favour of whichever
# tile has gone longest without being targeted at all.
_STALL_ROTATE_THRESHOLD = 6


def _is_hud_band(region: Region, height: int, width: int) -> bool:
    r0, c0, r1, c1 = region["bbox"]
    h, w = r1 - r0 + 1, c1 - c0 + 1
    full_width_thin = w >= width * _HUD_SPAN_FRACTION and h <= max(1, int(height * _HUD_THICKNESS_FRACTION))
    full_height_thin = h >= height * _HUD_SPAN_FRACTION and w <= max(1, int(width * _HUD_THICKNESS_FRACTION))
    return full_width_thin or full_height_thin


def _spatial_subgroups(regions: list[Region], radius: float) -> list[list[Region]]:
    """Single-linkage chain ``regions`` (already ONE colour, by construction
    of every caller here) into subgroups: two regions join the same
    subgroup when their centroid distance is at most ``radius``, and
    membership is TRANSITIVE (a chain of close regions groups together
    even when its two ends are farther apart than ``radius``) -- exactly
    the property that keeps a real tile's own fragments (and a genuinely
    elongated decorative line, whose consecutive dots are each close to
    their neighbour) in ONE subgroup, while a single distant, unrelated
    region of the same colour never joins either."""
    n = len(regions)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[ri] = rj

    for i in range(n):
        for j in range(i + 1, n):
            if _dist2(regions[i]["centroid"], regions[j]["centroid"]) <= radius * radius:
                union(i, j)

    groups: dict[int, list[Region]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(regions[i])
    return list(groups.values())


def _scatter_colors(regions: list[Region]) -> set[int]:
    """Colours whose regions are scattered decoration, not movable tiles.

    Groups each colour's OWN regions into spatial subgroups first (see
    :func:`_spatial_subgroups`) and applies the min-clusters/density test
    per subgroup -- a colour is scattered if ANY of its subgroups
    independently qualifies. Necessary (not just a robustness nicety):
    testing density over a colour's FULL region list, unscoped, measured a
    real bug (R56, gold-replay divergence against su15.npz) -- one
    UNRELATED same-coloured region far from a genuinely dense real tile
    inflated the whole colour's bbox enough to push density under
    threshold, silently excluding the real tile's every fragment from
    candidates."""
    by_color: dict[int, list[Region]] = {}
    for r in regions:
        by_color.setdefault(r["color"], []).append(r)
    out: set[int] = set()
    for color, rs in by_color.items():
        for group in _spatial_subgroups(rs, _SUBGROUP_RADIUS):
            if len(group) < _SCATTER_MIN_CLUSTERS:
                continue
            rows = [r["centroid"][0] for r in group]
            cols = [r["centroid"][1] for r in group]
            bbox_area = (max(rows) - min(rows) + 1) * (max(cols) - min(cols) + 1)
            if bbox_area > 0 and len(group) / bbox_area < _SCATTER_MAX_DENSITY:
                out.add(color)
                break
    return out


def _candidates(grid: tuple[tuple[int, ...], ...]) -> list[Region]:
    """Non-chrome candidate objects: excludes background, HUD bands, and
    scattered colors, with fragmented tile sprites fused into one region
    per physical object.

    TWO passes, deliberately at different granularities (see
    :data:`_CANDIDATE_GAP`'s docstring for the measured justification):
    scatter classification runs on the FINE-grained (``gap=0``) region
    list, since a genuinely scattered decorative pattern's own sparse
    signature is only visible at native resolution -- gap-tolerant fusion
    would merge it into one elongated blob and hide that signature just as
    it correctly fuses a real fragmented tile's own pieces. The actual
    candidate list returned is built from the GAP-FUSED (``gap=
    _CANDIDATE_GAP``) regions, filtering out whichever colours the
    fine-grained pass flagged as scattered, so a real tile gets ONE
    candidate entry with a true aggregate centroid instead of ~15-17
    fragment entries."""
    if not grid:
        return []
    height, width = len(grid), len(grid[0])
    total = height * width
    bg = most_common_color(grid)

    fine = find_regions(grid, background=bg, gap=0)
    scatter = _scatter_colors([r for r in fine if not _is_hud_band(r, height, width)])

    fused = find_regions(grid, background=bg, gap=_CANDIDATE_GAP)
    non_hud = [r for r in fused if not _is_hud_band(r, height, width)]
    return [r for r in non_hud if r["color"] not in scatter and r["size"] <= total * _MAX_CANDIDATE_FRACTION]


def _dist2(a: tuple[float, float], b: tuple[float, float]) -> float:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


def _same_color_pairs(tiles: list[Region]) -> list[tuple[Region, Region]]:
    """Every same-color tile pair, nearest-centroid-first."""
    scored: list[tuple[float, Region, Region]] = []
    for i in range(len(tiles)):
        for j in range(i + 1, len(tiles)):
            a, b = tiles[i], tiles[j]
            if a["color"] == b["color"]:
                scored.append((_dist2(a["centroid"], b["centroid"]), a, b))
    scored.sort(key=lambda t: t[0])
    return [(a, b) for _d, a, b in scored]


def _ranked_targets(
    tiles: list[Region], goal: Region, *, prefer_lone: bool = False
) -> list[tuple[Region, tuple[float, float]]]:
    """(source_tile, destination_point) pairs in preferred order.

    Every same-color pair first (nearest pair first -- the cheapest merge),
    then every lone tile driven toward the goal (farthest-from-goal first,
    so a straggler is never abandoned half-walked while a closer tile sits
    idle). The caller picks the first entry whose click path clears the
    hazard check.

    ``prefer_lone=True`` moves COLOUR-UNIQUE tiles (no same-coloured
    partner exists anywhere in ``tiles``) ahead of every pair, instead of
    behind. Used ONLY for the very first decision this level (no click has
    been issued yet, so there is zero movement evidence): a same-colour
    PAIR is an unverified guess at this point (two regions sharing a
    colour by coincidence, e.g. static decoration, look identical to a
    genuine mergeable pair with no prior observation to tell them apart --
    measured directly, R56 gold-replay divergence against su15.npz L1: the
    default ordering picked two never-moving decorative regions as its
    first click, where gold instead probed the one colour-UNIQUE, genuinely
    movable tile). A colour-unique tile carries no such ambiguity -- it is
    the only candidate of its colour, so there is nothing to misidentify it
    as. Tiles that DO have a partner are never reordered by this flag (they
    stay in their normal after-pairs position) -- only genuinely unique
    tiles jump the queue.
    """
    pairs: list[tuple[Region, tuple[float, float]]] = [(a, b["centroid"]) for a, b in _same_color_pairs(tiles)]
    lone: list[tuple[Region, tuple[float, float]]] = [
        (t, goal["centroid"]) for t in sorted(tiles, key=lambda r: -_dist2(r["centroid"], goal["centroid"]))
    ]
    if not prefer_lone:
        return pairs + lone

    color_counts: dict[int, int] = {}
    for t in tiles:
        color_counts[t["color"]] = color_counts.get(t["color"], 0) + 1
    lone_unique = [entry for entry in lone if color_counts[entry[0]["color"]] == 1]
    lone_rest = [entry for entry in lone if color_counts[entry[0]["color"]] != 1]
    return lone_unique + pairs + lone_rest


def _tile_key(region: Region) -> tuple[int, int, int]:
    """A coarse, position-bucketed identity for cross-call bookkeeping.

    Regions carry no persistent id across frames; a tile's position drifts
    gradually between consecutive clicks rather than teleporting, so
    bucketing the live centroid to a coarse grid (plus color) is a
    stable-enough proxy for "probably the same tile" -- used only for
    streak/rotation bookkeeping, never as a click coordinate itself.
    """
    r, c = region["centroid"]
    return (region["color"], int(r) // 4, int(c) // 4)


def _click_toward(src: Cell, dst: tuple[float, float], step_px: float, height: int, width: int) -> Cell:
    """Click point ``max(step_px, _MIN_EFFECTIVE_PX)`` ahead of ``src`` toward ``dst``.

    Uses :func:`admorphiq.kernels.point_toward` for the NORMAL regime
    (step shorter than the remaining src->dst distance). When the step
    would REACH OR PASS ``dst``, point_toward's own contract clamps the
    result to ``dst`` exactly -- measured a no-pull zone (this module's
    very first probe: clicking directly on a tile produces zero shift).
    That regime is detected here and handled with plain unit-vector
    arithmetic instead, deliberately overshooting past ``dst`` -- the
    vacuum pulls toward wherever the click lands, so landing beyond the
    goal still pulls goal-ward. Clamped to the frame in both regimes,
    which point_toward itself does not know about.
    """
    step = max(step_px, _MIN_EFFECTIVE_PX)
    remaining = _dist2(src, dst) ** 0.5
    if remaining > 1e-9 and step >= remaining:
        ux = (dst[0] - src[0]) / remaining
        uy = (dst[1] - src[1]) / remaining
        row = int(round(src[0] + ux * step))
        col = int(round(src[1] + uy * step))
    else:
        row, col = point_toward(src, dst, distance=step)
    row = max(0, min(height - 1, row))
    col = max(0, min(width - 1, col))
    return (row, col)


class Adapter(GameAdapter):
    """Adaptive absolute-step point-toward vacuum-merge play composed entirely from admorphiq.kernels."""

    GAME_ID = GAME_ID

    def __init__(self, giveup: int = _GIVEUP_DEFAULT) -> None:
        # The wiki's own lesson log records repeated dead clicks accumulating
        # toward GAME_OVER on this game -- same convention as
        # admorphiq.adapters25.m0r0/lp85: RESET and keep playing rather than
        # end the run.
        self.restart_on_game_over = True

        self._giveup = giveup
        self._step = 0
        self._levels_seen = -1
        # ABSOLUTE click-ahead distance (px) used for the next point-toward
        # click. A property of the game's own vacuum strength, so it
        # persists across levels (matching admorphiq.adapters25.m0r0's
        # dir_map convention) -- escalated on a not-useful click, reset back
        # to the floor on a useful one, by _observe_result.
        self._step_px = _MIN_EFFECTIVE_PX
        self._pending_click: Cell | None = None
        # The click SOURCE tile's bucket key + exact centroid, so
        # _observe_result can (a) credit a no-useful-shift outcome to the
        # right bucket for dead-click counting and (b) re-identify that
        # SAME region in the next frame's candidate list to check whether
        # IT specifically moved. Both None when the pending click had no
        # identifiable source region (the frame-centre fallback probe).
        self._pending_source_key: tuple[int, int, int] | None = None
        self._pending_source_centroid: tuple[float, float] | None = None
        self._prev_grid: tuple[tuple[int, ...], ...] | None = None
        # The very first frame seen this level -- a GAME_OVER-triggered
        # restart snaps back to exactly this frame (see _observe_result's
        # fatal-click detector), mirroring admorphiq.adapters25.m0r0's own
        # restart-snapback technique.
        self._level_start_grid: tuple[tuple[int, ...], ...] | None = None
        # Dead-click memory -- a property of THIS level's layout, reset on
        # level-up alongside the rest.
        self._dead_click_counts: dict[tuple[int, int, int], int] = {}
        self._dead_buckets: set[tuple[int, int, int]] = set()
        # Fatal-click memory -- one-shot, also reset on level-up.
        self._fatal_buckets: set[tuple[int, int, int]] = set()
        # Coverage-rotation bookkeeping -- also a property of the level.
        self._target_history: dict[tuple[int, int, int], int] = {}
        self._same_target_key: tuple[int, int, int] | None = None
        self._same_target_count = 0
        # Clicks committed so far THIS level -- gates _ranked_targets'
        # prefer_lone flag (see that function's docstring): on click 0
        # (zero movement evidence yet), a colour-unique tile is preferred
        # over trusting a same-colour pair guess. Reset on level-up.
        self._clicks_this_level = 0

    # ── harness contract ────────────────────────────────────────────────

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        return state_name(latest_frame) == "WIN" or self._step >= self._giveup

    def choose_action(self, frames: list[Any], latest_frame: Any) -> GameAction:
        state = state_name(latest_frame)
        if state in ("NOT_PLAYED", "GAME_OVER") or not has_frame(latest_frame):
            self._pending_click = None
            self._pending_source_key = None
            self._pending_source_centroid = None
            self._prev_grid = None
            self._levels_seen = -1
            return reset_action()

        grid = canonical_layer(latest_frame)
        levels = int(getattr(latest_frame, "levels_completed", 0) or 0)
        if levels != self._levels_seen:
            self._levels_seen = levels
            self._pending_click = None
            self._pending_source_key = None
            self._pending_source_centroid = None
            self._prev_grid = None
            self._level_start_grid = grid
            self._dead_click_counts = {}
            self._dead_buckets = set()
            self._fatal_buckets = set()
            self._target_history = {}
            self._same_target_key = None
            self._same_target_count = 0
            self._clicks_this_level = 0

        self._step += 1
        self._observe_result(grid)

        _simple_ids, action6_ok = available_action_ids(latest_frame)
        if not action6_ok:
            # No ACTION6 exposed at all -- nothing for a click-vacuum plan to
            # compose from on this frame.
            self._prev_grid = grid
            self._pending_click = None
            self._pending_source_key = None
            self._pending_source_centroid = None
            return reset_action()

        target = self._next_target(grid)
        self._prev_grid = grid
        self._pending_click = target
        row, col = target
        return click_action(x=col, y=row)

    # ── measurement: did the pending click move anything? ───────────────

    def _observe_result(self, grid: tuple[tuple[int, ...], ...]) -> None:
        """Detect a fatal click, else measure whether the click's OWN source tile moved.

        Two DISTINCT questions, checked in order:

        1. Fatal-click detection: the frame reverting to EXACTLY the
           level's start frame, when the frame just BEFORE this click had
           already diverged from it, means a GAME_OVER-triggered restart
           just happened (mirrors admorphiq.adapters25.m0r0's own restart
           snap-back detector) -- the click that was just issued killed the
           run. Its source bucket is excluded permanently for the rest of
           the level; nothing else in this method runs for that call.
        2. Otherwise, "useful": composes frame_diff -> _candidates
           (before/after) -> track_objects, matching the SAME
           chrome-filtered candidate set gameplay decisions use (not raw
           find_regions output -- SU15's status row would otherwise
           pollute matching). The click's SOURCE tile -- re-identified in
           ``regions_before`` by nearest centroid to the exact point
           recorded at commit time, since regions carry no persistent id
           across frames -- must EITHER have vanished (merged into its
           partner: the mechanic succeeding) OR shifted by at least
           :data:`_MIN_USEFUL_SHIFT` to count as useful. A NOT-useful click
           escalates the absolute step size and counts toward its source
           bucket's dead-click total; crossing :data:`_DEAD_CLICK_THRESHOLD` marks
           the bucket dead for the rest of the level. Neither dead nor
           fatal marks are ever healed by a later useful click, mirroring
           m0r0's dead-cell permanence.
        """
        point = self._pending_click
        source_key = self._pending_source_key
        source_centroid = self._pending_source_centroid
        before = self._prev_grid
        self._pending_click = None
        self._pending_source_key = None
        self._pending_source_centroid = None
        if point is None or before is None:
            return

        if before != self._level_start_grid and grid == self._level_start_grid:
            if source_key is not None:
                self._fatal_buckets.add(source_key)
            return

        diff = frame_diff(before, grid)
        if diff["count"] == 0:
            useful = False
        elif source_centroid is None:
            # No identifiable source tile (the frame-centre fallback probe)
            # -- can't be pickier than "something changed".
            useful = True
        else:
            regions_before = _candidates(before)
            regions_after = _candidates(grid)
            if not regions_before:
                useful = False
            else:
                tracked = track_objects(regions_before, regions_after)
                source_idx = min(
                    range(len(regions_before)),
                    key=lambda i: _dist2(regions_before[i]["centroid"], source_centroid),
                )
                if source_idx in tracked["vanished"]:
                    useful = True  # merged into its partner -- the mechanic succeeding
                else:
                    match = next((m for m in tracked["matches"] if m["before"] == source_idx), None)
                    if match is None:
                        useful = False
                    else:
                        dr, dc = match["shift"]
                        useful = (dr * dr + dc * dc) ** 0.5 >= _MIN_USEFUL_SHIFT

        if useful:
            # Success-reset (iteration 6): a click that worked at the
            # CURRENT step size is evidence that size is (at least) enough
            # right now -- de-escalate back to the floor rather than
            # carrying an inflated step from earlier, unrelated failures
            # into every later, likely-shorter-distance click.
            self._step_px = _MIN_EFFECTIVE_PX
            return

        self._step_px = min(_MAX_STEP_PX, self._step_px * _STEP_GROWTH)
        if source_key is not None:
            count = self._dead_click_counts.get(source_key, 0) + 1
            self._dead_click_counts[source_key] = count
            if count >= _DEAD_CLICK_THRESHOLD:
                self._dead_buckets.add(source_key)

    # ── planning: where to click next ────────────────────────────────────

    def _next_target(self, grid: tuple[tuple[int, ...], ...]) -> Cell:
        height = len(grid) or 1
        width = len(grid[0]) if grid else 1
        candidates = _candidates(grid)
        if len(candidates) < 2:
            # Nothing to gather/merge on this frame -- a harmless re-probe
            # at the frame's own observed centre rather than a crash.
            return (height // 2, width // 2)

        goal = max(candidates, key=lambda r: r["size"])
        tiles = [r for r in candidates if r is not goal]
        if not tiles:
            return (height // 2, width // 2)

        # Exclude dead-bucketed (repeated no-useful-shift clicks) AND
        # fatal-bucketed (one click that immediately GAME_OVER'd) tiles
        # from future targeting for the rest of the level. A real,
        # measured bug this fixed (R56, live-smoke diagnostic against the
        # candidate-fix above): the PREVIOUS version fell back to the
        # FULL unfiltered tile list whenever every tile happened to be
        # excluded, which -- once enough tiles accumulate dead status --
        # RE-ENABLES tiles already PROVEN dead/fatal, producing an
        # infinite retry loop on a confirmed-useless source (measured
        # live: a static decoration dead-bucketed at step 8 got re-picked
        # at step 19 via exactly this path). If every candidate is
        # confirmed dead/fatal, there is nothing left worth clicking on
        # purpose -- degrade to the same harmless centre re-probe used
        # when there are no candidates at all, never resurrect a proven-
        # useless bucket.
        excluded = self._dead_buckets | self._fatal_buckets
        alive_tiles = [t for t in tiles if _tile_key(t) not in excluded]
        if not alive_tiles:
            return (height // 2, width // 2)
        pool = alive_tiles

        if self._same_target_count > _STALL_ROTATE_THRESHOLD:
            # The same tile has been the click source too many times in a
            # row -- override the ranking once and drive whichever tile has
            # gone longest without being targeted at all (see the module
            # docstring's "Coverage rotation" note).
            self._same_target_count = 0
            least_recent = min(pool, key=lambda t: self._target_history.get(_tile_key(t), -1))
            return self._commit_target(least_recent, goal["centroid"], height, width)

        # Zero clicks committed yet this level: no movement evidence exists
        # to confirm a same-colour pair is real (see _ranked_targets'
        # prefer_lone docstring) -- probe a colour-unique tile first if one
        # exists.
        prefer_lone = self._clicks_this_level == 0
        src_region, dst_point = _ranked_targets(pool, goal, prefer_lone=prefer_lone)[0]
        return self._commit_target(src_region, dst_point, height, width)

    def _commit_target(self, src_region: Region, dst_point: tuple[float, float], height: int, width: int) -> Cell:
        self._clicks_this_level += 1
        key = _tile_key(src_region)
        if key == self._same_target_key:
            self._same_target_count += 1
        else:
            self._same_target_key = key
            self._same_target_count = 1
        self._target_history[key] = self._step
        self._pending_source_key = key
        self._pending_source_centroid = src_region["centroid"]

        src = (int(round(src_region["centroid"][0])), int(round(src_region["centroid"][1])))
        return _click_toward(src, dst_point, self._step_px, height, width)
