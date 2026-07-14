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
inherit. Live probing on the real env (see the module's own dev-time probe
script, not shipped) measured instead:

  - Clicking DIRECTLY on a tile's own centroid produces ZERO shift (nothing
    to pull across).
  - Clicking a SMALL offset (~15-30% of the tile-to-goal distance) toward
    the destination also produced zero shift on this env.
  - Clicking at a LARGER offset (~50% of the distance) produced a measured,
    if small, shift -- confirming a click must land meaningfully AHEAD of a
    tile (not on it, not barely off it) to register any pull at all.

So instead of assuming any fixed pixel radius, this adapter MEASURES it:
every click is placed at ``_fraction`` of the remaining distance between a
source tile and its destination (a same-color partner for merging, or the
goal container for gathering); ``_fraction`` starts small and escalates
(via :func:`admorphiq.kernels.frame_diff` on the observed before/after)
whenever a click produces no visible change at all, converging on a
distance that actually moves something. It never shrinks back down once a
click succeeds -- a known simplification, see the module's own "Deliberately
out of scope" note below.

Role assignment (declared HERE, not in the kernel layer, which knows
nothing about tiles, goals, or merging):

  - The GOAL container is the largest surviving candidate region (matches
    the wiki's own "goal zones are designated regions"; a destination
    container reliably renders bigger than the small value tiles it
    receives -- independently re-derived here, not copied from
    merge_drag.py's identical heuristic).
  - Every other candidate region is a movable value TILE.
  - Two same-color tiles are a MERGE candidate; a lone tile (or once no
    same-color pair remains) is driven toward the goal (GATHER).
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
    (before/after) + :func:`admorphiq.kernels.track_objects` +
    :func:`admorphiq.kernels.motion_vectors` measure whether the last click
    moved anything at all (used only to drive the fraction escalation --
    the exact matched shift direction is not otherwise consumed, since the
    click already aims where it wants the tile to go).

Deliberately out of scope (this is a proof-of-concept, not a full solver):
enemy/downgrade interaction (the wiki records L4+ needs a downgrade
primitive before some tiles become mergeable at all -- no enemy-vs-tile
role distinction is attempted here), merge-order lookahead, and the
GAME_OVER-inducing stall the wiki records for repeated dead clicks on an
unresponsive tile (``restart_on_game_over`` is set, matching
``admorphiq.adapters25.m0r0``'s convention, but no per-tile dead-click
memory is built the way m0r0's dead-cell tracking was).
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
from admorphiq.kernels import find_regions, frame_diff, motion_vectors, track_objects

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

# Starting fraction-of-remaining-distance for a point-toward click; escalated
# (never shrunk) whenever a click measurably moves nothing at all.
_INITIAL_FRACTION = 0.3
_FRACTION_GROWTH = 1.5
_MAX_FRACTION = 0.9
# A measured dominant shift smaller than this (in px) is treated the same as
# "nothing moved" for escalation purposes -- a click that barely nudged
# something is not yet at a useful working distance either. Small relative
# to the frame (64px on the measured env) but not a coordinate: it bounds a
# MAGNITUDE, not a position.
_MIN_USEFUL_SHIFT = 1.5


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


def _nearest_same_color_pair(tiles: list[Region]) -> tuple[Region, Region] | None:
    best: tuple[float, Region, Region] | None = None
    for i in range(len(tiles)):
        for j in range(i + 1, len(tiles)):
            a, b = tiles[i], tiles[j]
            if a["color"] != b["color"]:
                continue
            ar, ac = a["centroid"]
            br, bc = b["centroid"]
            d = (ar - br) ** 2 + (ac - bc) ** 2
            if best is None or d < best[0]:
                best = (d, a, b)
    return (best[1], best[2]) if best is not None else None


def _point_toward(src: Cell, dst: tuple[float, float], fraction: float, height: int, width: int) -> Cell:
    sr, sc = src
    dr, dc = dst
    row = sr + (dr - sr) * fraction
    col = sc + (dc - sc) * fraction
    row = max(0, min(height - 1, int(round(row))))
    col = max(0, min(width - 1, int(round(col))))
    return (row, col)


class Adapter(GameAdapter):
    """Adaptive point-toward vacuum-merge play composed entirely from admorphiq.kernels."""

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
        # Fraction-of-remaining-distance used for the next point-toward click.
        # A property of the game's own vacuum strength, so it persists across
        # levels (matching admorphiq.adapters25.m0r0's dir_map convention) --
        # only escalated, never reset, by _observe_result.
        self._fraction = _INITIAL_FRACTION
        self._pending_click: Cell | None = None
        self._prev_grid: tuple[tuple[int, ...], ...] | None = None

    # ── harness contract ────────────────────────────────────────────────

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        return state_name(latest_frame) == "WIN" or self._step >= self._giveup

    def choose_action(self, frames: list[Any], latest_frame: Any) -> GameAction:
        state = state_name(latest_frame)
        if state in ("NOT_PLAYED", "GAME_OVER") or not has_frame(latest_frame):
            self._pending_click = None
            self._prev_grid = None
            self._levels_seen = -1
            return reset_action()

        grid = canonical_layer(latest_frame)
        levels = int(getattr(latest_frame, "levels_completed", 0) or 0)
        if levels != self._levels_seen:
            self._levels_seen = levels
            self._pending_click = None
            self._prev_grid = None

        self._step += 1
        self._observe_result(grid)

        _simple_ids, action6_ok = available_action_ids(latest_frame)
        if not action6_ok:
            # No ACTION6 exposed at all -- nothing for a click-vacuum plan to
            # compose from on this frame.
            self._prev_grid = grid
            self._pending_click = None
            return reset_action()

        target = self._next_target(grid)
        self._prev_grid = grid
        self._pending_click = target
        row, col = target
        return click_action(x=col, y=row)

    # ── measurement: did the pending click move anything? ───────────────

    def _observe_result(self, grid: tuple[tuple[int, ...], ...]) -> None:
        """Escalate the click-offset fraction until a click MEASURABLY moves something.

        Composes frame_diff -> find_regions (before/after) -> track_objects
        -> motion_vectors the same way admorphiq.adapters25.m0r0 measures
        movement, but here the MAGNITUDE of the dominant shift (not its
        direction -- the click already aims at where the tile should go)
        decides whether the current fraction is a useful working distance.
        A diff with no matched region shift (e.g. a merge collapsing two
        regions into one, or a color change) still counts as real progress
        and does not escalate.
        """
        point = self._pending_click
        before = self._prev_grid
        self._pending_click = None
        if point is None or before is None:
            return
        diff = frame_diff(before, grid)
        if diff["count"] == 0:
            self._fraction = min(_MAX_FRACTION, self._fraction * _FRACTION_GROWTH)
            return
        regions_before = find_regions(before, background=most_common_color(before))
        regions_after = find_regions(grid, background=most_common_color(grid))
        tracked = track_objects(regions_before, regions_after)
        dominant = motion_vectors(tracked["matches"])["dominant"]
        if dominant is None:
            return
        magnitude = (dominant[0] ** 2 + dominant[1] ** 2) ** 0.5
        if magnitude < _MIN_USEFUL_SHIFT:
            self._fraction = min(_MAX_FRACTION, self._fraction * _FRACTION_GROWTH)

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

        pair = _nearest_same_color_pair(tiles)
        if pair is not None:
            a, b = pair
            src = (int(round(a["centroid"][0])), int(round(a["centroid"][1])))
            return _point_toward(src, b["centroid"], self._fraction, height, width)

        # No mergeable pair -- gather the tile FARTHEST from the goal first
        # (mirrors the "drive the straggler" reasoning: never abandon a
        # tile half-walked while a closer one is idle).
        farthest = max(
            tiles,
            key=lambda r: (r["centroid"][0] - goal["centroid"][0]) ** 2
            + (r["centroid"][1] - goal["centroid"][1]) ** 2,
        )
        src = (int(round(farthest["centroid"][0])), int(round(farthest["centroid"][1])))
        return _point_toward(src, goal["centroid"], self._fraction, height, width)
