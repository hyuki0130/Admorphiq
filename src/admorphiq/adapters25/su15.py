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
It never shrinks back down once a click succeeds -- a known simplification.

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

# Starting ABSOLUTE click-ahead distance (px) for a point-toward click;
# escalated (never shrunk) whenever a click measurably moves nothing at
# all. Unlike a fraction of the remaining distance, this does NOT shrink
# as a tile approaches its target -- see the module docstring's iteration-5
# finding (a fraction-based step falls below the effective pull threshold
# exactly when it matters most, right as a gather nears completion).
# Starts below the measured working value (10px, one tile/distance) so
# escalation -- not an assumed constant -- finds the real threshold.
_INITIAL_STEP_PX = 5.0
_STEP_GROWTH = 1.5
# Capped well under half the board so an escalated step stays a local
# nudge, never a huge cross-board jump (the failure mode of the old
# fraction model at its own ceiling).
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


def _scatter_colors(regions: list[Region]) -> set[int]:
    by_color: dict[int, list[Region]] = {}
    for r in regions:
        by_color.setdefault(r["color"], []).append(r)
    out: set[int] = set()
    for color, rs in by_color.items():
        if len(rs) < _SCATTER_MIN_CLUSTERS:
            continue
        rows = [r["centroid"][0] for r in rs]
        cols = [r["centroid"][1] for r in rs]
        bbox_area = (max(rows) - min(rows) + 1) * (max(cols) - min(cols) + 1)
        if bbox_area > 0 and len(rs) / bbox_area < _SCATTER_MAX_DENSITY:
            out.add(color)
    return out


def _candidates(grid: tuple[tuple[int, ...], ...]) -> list[Region]:
    """Non-chrome regions: excludes background, HUD bands, and scattered colors."""
    if not grid:
        return []
    height, width = len(grid), len(grid[0])
    total = height * width
    bg = most_common_color(grid)
    regions = find_regions(grid, background=bg)
    non_hud = [r for r in regions if not _is_hud_band(r, height, width)]
    scatter = _scatter_colors(non_hud)
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
    tiles: list[Region], goal: Region
) -> list[tuple[Region, tuple[float, float]]]:
    """(source_tile, destination_point) pairs in preferred order.

    Every same-color pair first (nearest pair first -- the cheapest merge),
    then every lone tile driven toward the goal (farthest-from-goal first,
    so a straggler is never abandoned half-walked while a closer tile sits
    idle). The caller picks the first entry whose click path clears the
    hazard check.
    """
    out: list[tuple[Region, tuple[float, float]]] = [(a, b["centroid"]) for a, b in _same_color_pairs(tiles)]
    for t in sorted(tiles, key=lambda r: -_dist2(r["centroid"], goal["centroid"])):
        out.append((t, goal["centroid"]))
    return out


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
    """Click point ``step_px`` ahead of ``src`` toward ``dst``, clamped to the frame.

    Thin wrapper over admorphiq.kernels.point_toward (which already takes
    an absolute pixel distance and clamps to ``dst`` itself if ``step_px``
    would overshoot it) adding only the frame-bounds clamp point_toward
    doesn't know about.
    """
    row, col = point_toward(src, dst, distance=step_px)
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
        # dir_map convention) -- only escalated, never reset, by
        # _observe_result.
        self._step_px = _INITIAL_STEP_PX
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
        # from future targeting for the rest of the level -- unless that
        # empties the pool entirely, in which case still act rather than
        # freeze.
        excluded = self._dead_buckets | self._fatal_buckets
        alive_tiles = [t for t in tiles if _tile_key(t) not in excluded]
        pool = alive_tiles or tiles

        if self._same_target_count > _STALL_ROTATE_THRESHOLD:
            # The same tile has been the click source too many times in a
            # row -- override the ranking once and drive whichever tile has
            # gone longest without being targeted at all (see the module
            # docstring's "Coverage rotation" note).
            self._same_target_count = 0
            least_recent = min(pool, key=lambda t: self._target_history.get(_tile_key(t), -1))
            return self._commit_target(least_recent, goal["centroid"], height, width)

        src_region, dst_point = _ranked_targets(pool, goal)[0]
        return self._commit_target(src_region, dst_point, height, width)

    def _commit_target(self, src_region: Region, dst_point: tuple[float, float], height: int, width: int) -> Cell:
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
