"""Frame-only CLICK-DRAG-TO-GOAL placement capability (R49).

A third member of the select-and-place ARRANGEMENT family (after
:mod:`admorphiq.arrangement`'s descend-and-sweep for movement+toggle games and
:mod:`admorphiq.sort_match`'s click-only match-to-order placement). This one
handles the **click-drag MERGE / gather** sub-class: the game exposes ONLY an
ACTION6 click (no movement actions, no selection toggle), and a click *pulls*
every nearby movable tile toward the click point. The level is cleared by
walking the movable tile(s) into a distinct GOAL region. SU15 level 1 is the
measured exemplar — a single coloured tile in one corner and a hollow goal
"container" cluster elsewhere; clicking a short step ahead of the tile toward
the goal drags it that far, and repeating walks the tile into the container,
clearing the level (a 2048-style merge game whose L1 needs only a gather).

The capability is fully observation-driven — no game-id / game-title /
game-internal reads:

1. :func:`detect_drag_layout` — segment the canonical layer into small movable
   TILE clusters and a distinct GOAL region (the rarest-coloured cluster that is
   not itself a tile). Returns ``None`` when there is no plausible tile + goal
   pair, so the plan only engages on a genuine gather layout.
2. :func:`drag_probe_target` — the first click the agent issues to TEST the
   drag hypothesis: a short step from the goal-nearest movable tile toward the
   goal. The agent confirms the tile translated toward the click before
   committing to the walk (so a non-drag click game abandons after one probe).
3. :func:`next_drag_click` — given the live frame, emit the next walk click: a
   step of length :data:`_DRAG_STEP` from the tile currently FARTHEST from the
   goal, in the goal's direction. Recomputed every call from the live frame, so
   it is robust to the env's multi-frame drag animation and to a tile that
   merged / changed colour mid-walk.

The "let the env confirm the WIN" philosophy mirrors the rest of the family:
the exact win predicate (which tile, what count, inside which region) is hidden,
but "gather every movable tile into the goal region" is the robust general
behaviour, and the harness checks the live level-up after each click so the walk
stops the instant the gather is complete.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .general_agent import connected_components

# ── Tunables ─────────────────────────────────────────────────────────────────

# A movable value TILE can be as small as a single pixel — SU15's lowest-value
# (value-0) tiles render as one pixel, and the merge chain builds them up into
# bigger squares. So the merge layout admits tiles down to 1 px; the dense-grid
# + container-ratio falsifiers below (not a size floor) are what keep the plan
# off unrelated speckled frames.
_MIN_TILE = 1
# A component larger than this is a board panel / playfield backdrop, not a
# discrete movable tile. SU15's movable value tiles top out near a 10x10
# (~100 px); the goal container ring is ~60 px, so this admits both the tiles
# and the goal region as separate candidate clusters.
_MAX_TILE = 130
# Rows at/above ``_TOP_BAND_CUTOFF`` are the top decorative panel; rows at/below
# ``_HUD_ROW_CUTOFF`` are the bottom HUD / step-counter band. A tile centroid in
# either band is chrome, not a movable piece. Measured on SU15: the top fill
# panel occupies y<=8, the step bar sits on the last row.
_TOP_BAND_CUTOFF = 8
_HUD_ROW_CUTOFF = 61
# Pixels a tile centroid must shift toward the click to count the drag
# hypothesis confirmed (mirrors arrangement._MIN_SHIFT_PX; sub-pixel drift is
# HUD creep, not a real pull).
_MIN_DRAG_PX = 2.0
# Length (px) of one walk step: how far ahead of a tile, toward the goal, the
# next click lands. The env pulls a tile up to ~16 px per click but only tiles
# within a small radius of the click are grabbed, so the step must stay within
# that radius — a short 7 px step keeps the tile inside the grab radius every
# click while still advancing it the full pull distance (measured on SU15 L1:
# a 7 px lead walked the tile corner-to-goal in 7 clicks vs a 22-action human).
_DRAG_STEP = 7.0
# A tile within this many pixels of the goal-region centroid is treated as
# already gathered (its bounding box overlaps the container), so the walk moves
# on to the next-farthest tile instead of re-clicking a placed one.
_GOAL_REACH_PX = 6.0
# Two same-colour tiles within this centroid distance are touching enough that a
# single click at their midpoint pulls both into overlap and MERGES them (the
# 2048 rule: same value tiles combine into the next value). Above this they must
# first be walked together. Measured on SU15: a 3-px gap merges on the midpoint
# click; wider gaps need a drag-together step first.
_MERGE_DIST_PX = 3.0
# Step (px) used to drag one tile of a same-colour pair toward its partner. A
# short lead keeps the dragged tile inside the click grab radius while advancing
# it, and — being shorter than the goal walk step — reduces the chance of
# sweeping a DIFFERENT-colour tile into the path (a different-value collision is
# a lose-state in the measured merge game).
_MERGE_STEP = 5.0
# A gather layout has only a HANDFUL of movable tiles to drag into the goal — a
# board densely tiled with many equal cells is a lights-out / bit-panel TOGGLE
# grid (FT09: ~42 clusters, TN36: ~37), NOT a gather. Capping the tile count is
# the falsifier that keeps the drag plan off those dense click games (SU15 L1
# has 3 movable tiles, L2's merge chain a handful more); above this the layout
# is rejected so the toggle classes keep their own handoff path.
_MAX_TILES = 12
# A colour with at least this many clusters that are scattered sparsely over a
# large bbox is a HUD line / border-dot pattern, not a set of movable tiles
# (SU15's diagonal step-line is ~21 one-pixel dots of one colour spanning the
# board). The threshold sits ABOVE the merge-tile count (SU15 L2 starts with 8
# same-colour value-0 tiles, also scattered) so the genuine merge cloud is kept
# while the longer chrome line is dropped. Paired with ``_MAX_TILES`` (= 12),
# which caps how many tiles a gather/merge layout may have, this brackets the
# merge-tile count to 8..12 and rejects both denser toggle grids and longer HUD
# lines. Measured: SU15 line 21 dots > 13; SU15 merge cloud 8 dots < 13.
_SCATTER_MIN_CLUSTERS = 13
# Below this fraction (clusters per bbox area) a multi-cluster colour is treated
# as a scattered chrome line rather than a compact set of tiles. SU15's diagonal
# line has density ~0.01; a real cluster of merge tiles packs far denser.
_SCATTER_MAX_DENSITY = 0.05


# ── layout detection ──────────────────────────────────────────────────────────


@dataclass
class DragLayout:
    """A detected click-drag-to-goal layout for the gather plan.

    ``tiles`` is the list of ``(cx, cy, color, size)`` movable tile centroids;
    ``goal`` is the ``(cx, cy)`` centroid of the distinct goal / container
    region the tiles must be gathered into.
    """

    tiles: list[tuple[float, float, int, int]]
    goal: tuple[float, float]


def _scatter_colors(comps: list[dict]) -> set[int]:
    """Colours whose clusters form a scattered HUD line / border-dot pattern.

    A colour with many clusters spread sparsely over a large bbox (low cluster
    density) is chrome — SU15 renders its diagonal step-line as ~21 one-pixel
    dots of one colour spanning the board. Such colours are dropped wholesale
    so a single 1-px movable tile is still admitted while a scattered chrome
    line is not. Pure / env-free.
    """
    by_color: dict[int, list[dict]] = {}
    for c in comps:
        by_color.setdefault(c["color"], []).append(c)
    out: set[int] = set()
    for color, cs in by_color.items():
        if len(cs) < _SCATTER_MIN_CLUSTERS:
            continue
        xs = [c["cx"] for c in cs]
        ys = [c["cy"] for c in cs]
        bbox = (max(xs) - min(xs) + 1) * (max(ys) - min(ys) + 1)
        if bbox > 0 and len(cs) / bbox < _SCATTER_MAX_DENSITY:
            out.add(color)
    return out


def _candidate_clusters(layer: np.ndarray, background: int) -> list[dict]:
    """Non-chrome coloured clusters in the playfield (tile / goal candidates).

    Drops the background, board-spanning panels, any cluster whose centroid sits
    in the top decorative panel or the bottom HUD band, and any colour forming a
    scattered HUD line / border-dot pattern (see :func:`_scatter_colors`). Pure /
    env-free.
    """
    raw = [
        c
        for c in connected_components(layer, background)
        if _MIN_TILE <= c["size"] <= _MAX_TILE
        and c["color"] != background
        and _TOP_BAND_CUTOFF < c["cy"] < _HUD_ROW_CUTOFF
    ]
    scatter = _scatter_colors(raw)
    return [c for c in raw if c["color"] not in scatter]


def detect_drag_layout(layer: np.ndarray, background: int) -> DragLayout | None:
    """Detect a movable-tile + goal-region gather layout, or None.

    A gather layout has, on the same frame: at least one small movable TILE and
    a distinct GOAL region of a DIFFERENT colour to gather it into. The goal is
    the rarest-coloured non-tile cluster (rarest colour is the likeliest target,
    matching the navigation planner's rarest-colour goal heuristic); the tiles
    are every other candidate cluster. Returns None when there is no tile + goal
    pair of distinct colours (so the plan never engages on an unrelated click
    game). Pure / env-free.
    """
    if layer.size == 0:
        return None
    comps = _candidate_clusters(layer, background)
    if len(comps) < 2:
        return None

    # The GOAL container is the single LARGEST playfield cluster — a destination
    # "zone" is rendered bigger than the small movable value tiles it receives
    # (measured on SU15: the goal ring is ~60 px vs. ~9 px tiles). The movable
    # TILES are every smaller cluster of a DIFFERENT colour (a same-colour cluster
    # is part of the container, not a piece to drag into it).
    goal_c = max(comps, key=lambda c: c["size"])
    goal_color = goal_c["color"]
    goal = (goal_c["cx"], goal_c["cy"])

    tiles = [
        (c["cx"], c["cy"], int(c["color"]), int(c["size"]))
        for c in comps
        if c["color"] != goal_color
    ]
    # A genuine gather has a HANDFUL of movable tiles; a board densely tiled
    # with many equal cells is a toggle / bit-panel grid (FT09 / TN36), not a
    # gather — reject so those classes keep their own handoff (the falsifier
    # that prevents the drag plan engaging on dense click games).
    if not tiles or len(tiles) > _MAX_TILES:
        return None
    return DragLayout(tiles=tiles, goal=goal)


# ── drag probe + walk planning ────────────────────────────────────────────────


def _step_toward(
    src: tuple[float, float], dst: tuple[float, float], step: float
) -> tuple[int, int]:
    """Integer click point ``step`` px from ``src`` toward ``dst`` (clamped 0..63).

    When ``src`` is already at ``dst`` the click lands on ``dst``. Used both for
    the drag probe (a short test step) and each walk click.
    """
    dx = dst[0] - src[0]
    dy = dst[1] - src[1]
    dist = (dx * dx + dy * dy) ** 0.5
    if dist <= 1e-6:
        x, y = dst
    else:
        x = src[0] + dx / dist * step
        y = src[1] + dy / dist * step
    return (int(round(max(0, min(63, x)))), int(round(max(0, min(63, y)))))


def drag_probe_target(layout: DragLayout) -> tuple[int, int]:
    """First TEST click: a short step from the goal-nearest tile toward the goal.

    Picks the tile CLOSEST to the goal (the cheapest confirmation: a short walk
    proves the drag hypothesis with the least wasted budget if it is wrong) and
    returns a click one :data:`_DRAG_STEP` ahead of it toward the goal. The
    agent issues this, then checks whether that tile translated toward the click
    to decide whether to commit to the full gather walk.
    """
    nearest = min(
        layout.tiles,
        key=lambda t: (t[0] - layout.goal[0]) ** 2 + (t[1] - layout.goal[1]) ** 2,
    )
    return _step_toward((nearest[0], nearest[1]), layout.goal, _DRAG_STEP)


def next_drag_click(layer: np.ndarray, background: int) -> tuple[int, int] | None:
    """Next walk click for the live frame, or None when nothing left to gather.

    Recomputes the layout from the live frame (robust to the drag animation and
    to tiles that merged / recoloured mid-walk), then drives the tile FARTHEST
    from the goal one :data:`_DRAG_STEP` toward the goal — gathering the
    straggler each call so every tile converges on the container. Returns None
    when no movable tile remains outside the goal-reach radius (the gather is
    complete or the layout is no longer a gather), so the agent stops clicking.
    """
    bg = int(background)
    layout = detect_drag_layout(layer, bg)
    if layout is None:
        return None
    outstanding = [
        t
        for t in layout.tiles
        if ((t[0] - layout.goal[0]) ** 2 + (t[1] - layout.goal[1]) ** 2) ** 0.5
        > _GOAL_REACH_PX
    ]
    if not outstanding:
        return None
    # Drive the farthest straggler first so a single tile is never abandoned
    # half-walked; ties broken by larger tile (the more visible mover).
    target = max(
        outstanding,
        key=lambda t: (
            (t[0] - layout.goal[0]) ** 2 + (t[1] - layout.goal[1]) ** 2,
            t[3],
        ),
    )
    return _step_toward((target[0], target[1]), layout.goal, _DRAG_STEP)


def _nearest_same_color_pair(
    tiles: list[tuple[float, float, int, int]],
) -> tuple[tuple, tuple] | None:
    """The closest pair of same-colour tiles, or None when none share a colour.

    Same-colour tiles are the mergeable pairs (the 2048 rule operates on equal
    values, which render as one colour each). Returns the geometrically closest
    such pair so the merge plan combines the cheapest pair first. Pure.
    """
    best: tuple[float, tuple, tuple] | None = None
    n = len(tiles)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = tiles[i], tiles[j]
            if a[2] != b[2]:
                continue
            d = (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2
            if best is None or d < best[0]:
                best = (d, a, b)
    if best is None:
        return None
    return best[1], best[2]


def next_merge_click(layer: np.ndarray, background: int) -> tuple[int, int] | None:
    """Next click for a 2048-style MERGE-then-gather game, or None when done.

    Generalises :func:`next_drag_click` to the merge sub-class (SU15 deep
    levels): a click pulls nearby tiles toward it, two SAME-colour tiles that
    overlap MERGE into one higher tile, and the goal is one merged tile inside
    the container. Strategy, recomputed from the LIVE frame each call (robust to
    the drag/merge animation):

    1. **Merge** — while two same-colour tiles exist, combine them. If the
       closest such pair is within :data:`_MERGE_DIST_PX` click their midpoint
       (pulls both into overlap → merge); otherwise drag one toward its partner
       by a short :data:`_MERGE_STEP` (so distant equals are walked together
       WITHOUT sweeping a different-colour tile into the path, which would be a
       lose-state).
    2. **Gather** — when every remaining tile is a distinct colour (the merge
       chain is exhausted), drive the goal-farthest tile toward the goal so the
       final merged tile lands in the container.

    Returns None when no movable tile remains outside the goal-reach radius (the
    level is solved or the layout is no longer a merge), so the agent stops.
    """
    bg = int(background)
    layout = detect_drag_layout(layer, bg)
    if layout is None:
        return None

    pair = _nearest_same_color_pair(layout.tiles)
    if pair is not None:
        a, b = pair
        dist = ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
        if dist <= _MERGE_DIST_PX:
            # Touching: click the midpoint to pull both into overlap → merge.
            mx = int(round(max(0, min(63, (a[0] + b[0]) / 2))))
            my = int(round(max(0, min(63, (a[1] + b[1]) / 2))))
            return (mx, my)
        # Distant equals: drag the first toward the second a short step.
        return _step_toward((a[0], a[1]), (b[0], b[1]), _MERGE_STEP)

    # No mergeable pair left → gather the final tile(s) into the goal container.
    return next_drag_click(layer, bg)
