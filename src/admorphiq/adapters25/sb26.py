"""script25 quarantined adapter: SB26 (portal-graph sort/assignment family).

*** QUARANTINE — MODEL-NEVER-VISIBLE. See admorphiq.adapters25's package
docstring. ***

``.wiki/wiki/games/SB26.md`` and ``docs/r57_win_condition_typology_20260715.md``
(read for reference, not imported) describe SB26 as a portal-graph traversal
puzzle disguised as a simple reference/pool colour-match sort (R57's "T3 —
Assignment/Matching" type: two designated region sets must become equal as
multisets of (colour, shape)). The board holds one or more bordered FRAMES,
each exposing N slots; a slot holds either a plain colour item or a PORTAL
that redirects traversal to a different frame (matched by that frame's
border colour). The level clears when a DFS traversal starting at the
first frame, following portals slot-by-slot, visits item slots whose
colours match a target sequence (read off a separate display band) in
TRAVERSAL order, not screen order.

``src/admorphiq/sort_match.py`` (read for MECHANIC understanding only, never
imported -- quarantine: stdlib + admorphiq.kernels + admorphiq.adapters25.base
only) already implements this correctly, but with two properties this
adapter deliberately does NOT carry over: (a) a fixed six-pixel slot grammar
(``x0+2+i*6``) for computing slot positions arithmetically from a frame's
bbox -- exactly the kind of game-specific constant the quarantine forbids;
(b) hardcoded frame/pipe structural detection duplicating what
``admorphiq.kernels.geometry`` now provides generically. This adapter
MEASURES slot positions instead (see role assignment below) and composes
``closed_frames``/``connectors`` for frame and portal detection.

**Offline verification (before any live action, per the R56 discipline of
falsifying before committing budget)**: loaded ``data/traces/sb26.npz``
(gold demonstration traces, label-generation only, never imported into this
adapter). Level 0's (wiki "L1") 8 gold click coordinates matched, to the
pixel after rounding, either a POOL-swatch region's centroid (uniform
~16px clusters in the bottom band) or a SLOT-marker region's centroid
(uniform ~4px clusters inside a ``closed_frames``-detected hollow box) --
confirming slot positions are directly measurable from small uniform-size
clusters, not arithmetic. Running :func:`_plan_sb26` itself (this module's
own function, not the reference solver) against every one of the 8 levels'
gold frames found a structurally valid plan (paired pool/slot clicks plus a
verify) for **7 of 8 levels** -- only level 1 (wiki "L2", the two-frame
portal case) failed, diagnosed below as a genuine kernel-coverage gap at
the time (since resolved -- see "Fused-frame recovery" below), not a bug
in this adapter's own logic.

Two problems were found and fixed during offline verification, both
load-bearing:

1. **Decorative single-item "frames" pollute closed_frames.** Each
   target-sequence marker in the display band is ITSELF a small hollow
   square (a colour border around one interior dot) -- ``closed_frames``
   correctly reports these as frames too, alongside the one genuine
   multi-slot placement frame. :func:`_filter_interactive_frames` and the
   ">=2 measured slots" guard in :func:`_plan_sb26` both filter these out;
   a frame with only one content region is structurally indistinguishable
   from a decorative marker and is dropped.
2. **A repeated connective chrome colour pollutes the target band.** The
   marker squares' own border colour also forms a larger connecting
   backdrop shape spanning the whole display band, which
   :func:`group_by_axis` correctly groups into the SAME row-band as the
   genuine target dots. Since that chrome colour is never suppliable from
   the pool (only genuine target colours are), filtering target-band
   regions to "colour is in the pool" cleanly removes it without assuming
   any specific chrome colour.

**Fused-frame recovery (level 1, portal case) -- formerly a kernel gap,
now resolved**: the two REAL multi-slot frames on this level are not pure
rectangle borders -- at least one has a portal pipe fused onto its own
edge as ONE connected component, so ``closed_frames``'s exact "cells ==
rectangle border" match rejects it outright (it never reaches
``connectors``, which only separates ALREADY-distinct thin paths from
already-detected regions, not a fused shape). ``sort_match.py``'s own
``_split_box_pipe`` did this de-fusion with a game-specific implementation;
:func:`admorphiq.kernels.geometry.split_fused_frame` is the generic
namespace-safe replacement (landed after this adapter's first pass, R56
kernel round). :func:`_recover_fused_frames` calls it on every candidate
region whose cell count EXCEEDS its own bounding-box perimeter (a clean
ring's cells equal its perimeter exactly -- that is ``closed_frames``' own
test -- so only a region with extra fused cells, or a solid block, is
tried; ``split_fused_frame`` itself rejects a solid block by returning
``None``, so the size check is a cheap pre-filter, not a correctness
guard). The recovered frame is reshaped into the same
``{"border_color", "outer_bbox", "inner_bbox", "hole_cells"}`` shape
``closed_frames`` produces and unioned into the frame list BEFORE
:func:`_filter_interactive_frames` runs, so every downstream consumer
(slot detection, portal detection, DFS traversal) needs no changes at
all -- the fused frame is indistinguishable from a clean one once
recovered.

Role assignment (declared HERE, not in the kernel layer, which knows
nothing about frames, slots, portals, or targets):

  - Every :func:`admorphiq.kernels.closed_frames` hit with at least 2
    measured content slots (see below) is a portal-graph FRAME (a
    placement target), sorted by the kernel's own deterministic order
    (outer bbox top-left) -- frame 0 is the DFS traversal root, matching
    the wiki's own "frame[0]" language. A frame with only one content
    region is a decorative target-sequence marker, not a real frame (see
    "Offline verification" above).
  - A frame's CONTENT is every candidate region whose cells fall inside its
    ``hole_cells``. :func:`admorphiq.kernels.size_clusters` splits that
    content by size; the SMALLEST size class is the frame's SLOT markers
    (measured: SB26's own empty-slot markers are small, uniform, and
    smaller than any colour item on the board) -- their centroids, sorted
    left-to-right, are the slot click targets. (When a frame's content is a
    single size class, that class IS the slot set.)
  - Every OTHER candidate region (outside every frame's ``hole_cells``) is
    grouped into row-bands via :func:`admorphiq.kernels.group_by_axis`; the
    TOPMOST band is the TARGET/reference sequence (filtered to colours the
    pool can actually supply -- see "Offline verification" above -- since
    that band also contains connective marker chrome); its regions'
    colours, left-to-right, are the traversal-consumed target order for
    THIS adapter's single-frame case (multi-frame DFS order is handled
    separately below). The BOTTOMMOST band is the POOL (individual colour
    swatches, one instance per slot demand -- measured on the portal level,
    NOT a small fixed reusable set).
  - PORTALS: :func:`admorphiq.kernels.geometry.connectors` finds thin paths
    linking exactly two frames (using each frame's own border cells as a
    pseudo-region, rebuilt fresh from ``outer_bbox`` -- a RECOVERED fused
    frame's outer_bbox already excludes the appendage/pipe cells, so its
    pseudo-region is identical in shape to a clean frame's and needs no
    special-casing here). For each connector, whichever frame's slot
    markers sit closer to the connector's path is the portal's SOURCE
    (that frame's nearest slot redirects traversal to the OTHER frame).
  - Candidate regions exclude the same two RELATIVE-geometry chrome classes
    ``admorphiq.adapters25.su15`` uses (a HUD band spanning almost the full
    frame width/height while only a few cells thick -- measured: SB26 has a
    full-width 1-tall status row exactly like SU15's; and an oversized
    region above a frame-size-fraction ceiling), never absolute pixel
    coordinates.

Composition from ``admorphiq.kernels``:
  - :func:`admorphiq.kernels.find_regions` segments the frame.
  - :func:`admorphiq.kernels.closed_frames` detects clean portal-graph
    frames; :func:`admorphiq.kernels.geometry.split_fused_frame` recovers
    the ones closed_frames rejects because a same-colour appendage (a
    fused portal pipe) is part of the same connected component (see
    "Fused-frame recovery" above; together these replace sort_match's own
    hollow-rectangle-vs-pipe splitting).
  - :func:`admorphiq.kernels.connectors` detects the portal pipes linking
    frames (replacing sort_match's own endpoint-to-frame-membership scan).
  - :func:`admorphiq.kernels.group_by_axis` separates the target-sequence
    band from the pool band by row position (replacing sort_match's fixed
    ``_TOP_BAND``/``_BOT_BAND`` row-cutoff constants).
  - :func:`admorphiq.kernels.size_clusters` separates a frame's slot markers
    from any pre-filled items by size (replacing an assumed marker colour).
  - :func:`admorphiq.kernels.frame_diff` measures whether a drained click
    had any visible effect, so a plan that stops working partway through
    (a wrong guess) is abandoned rather than drained blindly to the end.

The DFS traversal itself (:func:`_dfs_traversal`) is adapter-owned policy
over a small, MEASURED graph (a handful of frames/slots) -- not a
reimplementation of a generic kernel algorithm, the same way
``admorphiq.adapters25.su15``'s pair-ranking and
``admorphiq.adapters25.m0r0``'s frontier bookkeeping are adapter policy, not
banned "own search".

Deliberately out of scope (proof of concept, not a full solver): bottom-
portal PLACEMENT (a portal itself needing to be placed from the pool rather
than being a fixed board feature) and permutation search over multiple
candidate DFS roots/orderings -- the wiki flags both as needed for L3+ and
explicitly "banked" even by the more mature reference module.
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
    simple_action,
    state_name,
)
from admorphiq.kernels import (
    closed_frames,
    connectors,
    find_regions,
    frame_diff,
    group_by_axis,
    size_clusters,
    split_fused_frame,
)

GAME_ID = "sb26"

Grid = tuple[tuple[int, ...], ...]
Cell = tuple[int, int]
Region = dict[str, Any]
PlanStep = tuple[Any, ...]

_GIVEUP_DEFAULT = 4000

# Measured: SB26 exposes ACTION5 as the placement-verify/confirm action (the
# same role admorphiq.world_model_agent's own sort-routing gate uses).
_VERIFY_ACTION = 5

# A region spanning at least this fraction of the frame's own cell count is
# a board-spanning panel, never a discrete band/slot/pool item.
_MAX_CANDIDATE_FRACTION = 0.15
# HUD band detection -- identical shape to admorphiq.adapters25.su15's,
# independently declared here since each adapter's role assignments are its
# own (frame-relative fractions, never absolute pixel coordinates). Measured
# necessary: SB26 has a full-width 1-tall status row exactly like SU15's.
_HUD_SPAN_FRACTION = 0.85
_HUD_THICKNESS_FRACTION = 0.06

# group_by_axis row-clustering tolerance for separating the target-sequence
# band from the pool band (regions further apart than this within a band
# would otherwise be treated as two separate bands).
_BAND_TOLERANCE = 3.0

# Bounded settle-wait at level entry: a multi-layer transient frame stack
# mis-reads structure (measured: detect_portal_sort returns None on the
# raw level-entry frame but valid placements from the very next frame --
# see the module docstring's offline verification). Mirrors
# admorphiq.world_model_agent's own _PORTAL_SETTLE_MAX.
_SETTLE_MAX_WAIT = 6

# Consecutive drained clicks producing zero visible change before the
# remaining plan is abandoned (a wrong layout guess should not be drained
# blindly to the end). Mirrors world_model_agent's own
# _MERGE_DRAG_STALL_LIMIT concept, independently measured via frame_diff.
_STALL_LIMIT = 3


def _is_hud_band(region: Region, height: int, width: int) -> bool:
    r0, c0, r1, c1 = region["bbox"]
    h, w = r1 - r0 + 1, c1 - c0 + 1
    full_width_thin = w >= width * _HUD_SPAN_FRACTION and h <= max(1, int(height * _HUD_THICKNESS_FRACTION))
    full_height_thin = h >= height * _HUD_SPAN_FRACTION and w <= max(1, int(width * _HUD_THICKNESS_FRACTION))
    return full_width_thin or full_height_thin


def _candidates(grid: Grid) -> list[Region]:
    """Non-chrome regions: excludes background, HUD bands, and oversized panels."""
    if not grid:
        return []
    height, width = len(grid), len(grid[0])
    total = height * width
    bg = most_common_color(grid)
    regions = find_regions(grid, background=bg)
    return [
        r
        for r in regions
        if not _is_hud_band(r, height, width) and r["size"] <= total * _MAX_CANDIDATE_FRACTION
    ]


def _frame_pseudo_region(frame: dict[str, Any]) -> Region:
    """A closed_frames entry's own border cells, in find_regions' shape.

    admorphiq.kernels.connectors expects a list of region dicts (it reads
    only ``cells``); closed_frames reports ``outer_bbox``/``border_color``
    but not the border cells themselves, so this derives them (the same
    rectangle-border formula the kernel itself uses internally).
    """
    r0, c0, r1, c1 = frame["outer_bbox"]
    cells = frozenset((r0, c) for c in range(c0, c1 + 1)) | frozenset((r1, c) for c in range(c0, c1 + 1))
    cells |= frozenset((r, c0) for r in range(r0, r1 + 1)) | frozenset((r, c1) for r in range(r0, r1 + 1))
    return {
        "color": frame["border_color"],
        "cells": cells,
        "bbox": frame["outer_bbox"],
        "centroid": ((r0 + r1) / 2, (c0 + c1) / 2),
        "size": len(cells),
    }


def _frame_content(frame: dict[str, Any], candidates: list[Region]) -> list[Region]:
    hole = frame["hole_cells"]
    return [r for r in candidates if r["cells"] & hole]


def _frame_slots(frame: dict[str, Any], candidates: list[Region]) -> list[Region]:
    """This frame's slot-marker regions, left-to-right (then top-to-bottom).

    size_clusters splits the frame's content by size; the smallest class is
    the slot markers (measured smaller than any colour item -- see the
    module docstring's offline verification). A single size class (no split
    possible) is treated as the slot set itself.
    """
    content = _frame_content(frame, candidates)
    if not content:
        return []
    clusters = size_clusters(content, ratio=1.5)
    smallest = min(clusters, key=lambda idxs: content[idxs[0]]["size"])
    slots = [content[i] for i in smallest]
    slots.sort(key=lambda r: (r["centroid"][1], r["centroid"][0]))
    return slots


def _dist2(a: tuple[float, float], b: tuple[float, float]) -> float:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


def _detect_portals(
    grid: Grid, frames: list[dict[str, Any]], frame_slots: list[list[Region]], background: int
) -> dict[tuple[int, int], int]:
    """(source_frame_idx, source_slot_idx) -> destination_frame_idx.

    Composes admorphiq.kernels.connectors over the frames' own border
    pseudo-regions. For each connector, whichever frame's slots sit closer
    to the connector's path cells is the portal SOURCE; the nearest slot
    within that frame to the path is where the portal attaches.
    """
    if len(frames) < 2:
        return {}
    frame_regions = [_frame_pseudo_region(f) for f in frames]
    links = connectors(grid, frame_regions, background=background)
    portal_of: dict[tuple[int, int], int] = {}
    for link in links:
        a, b = link["a"], link["b"]
        path = link["path_cells"]
        cand: list[tuple[int, int]] = []
        for idx in (a, b):
            slots = frame_slots[idx]
            if not slots:
                continue
            best = min(_dist2(s["centroid"], p) for s in slots for p in path)
            cand.append((idx, best))
        if not cand:
            continue
        source = min(cand, key=lambda t: t[1])[0]
        dest = b if source == a else a
        slots = frame_slots[source]
        best_idx = min(range(len(slots)), key=lambda i: min(_dist2(slots[i]["centroid"], p) for p in path))
        portal_of[(source, best_idx)] = dest
    return portal_of


def _dfs_traversal(
    frame_slots: list[list[Region]], portal_of: dict[tuple[int, int], int], n_targets: int
) -> list[tuple[tuple[int, int], str]]:
    """DFS from frame 0: ``[((frame_idx, slot_idx), "item" | "portal" | "revisit"), ...]``.

    A small, MEASURED-graph traversal (adapter policy, not a kernel
    algorithm) mirroring the wiki-documented mechanic: portal slots recurse
    into the linked frame; a revisited item slot still consumes a target
    index (its colour was fixed on first visit) without a fresh placement.
    """
    order: list[tuple[tuple[int, int], str]] = []
    seen: set[tuple[int, int]] = set()
    consumed = [0]

    def visit(frame_idx: int, depth: int = 0) -> None:
        if depth > 20 or consumed[0] >= n_targets or frame_idx >= len(frame_slots):
            return
        for slot_idx in range(len(frame_slots[frame_idx])):
            if consumed[0] >= n_targets:
                return
            key = (frame_idx, slot_idx)
            if key in portal_of:
                order.append((key, "portal"))
                visit(portal_of[key], depth + 1)
            else:
                order.append((key, "revisit" if key in seen else "item"))
                seen.add(key)
                consumed[0] += 1

    if frame_slots:
        visit(0)
    return order


def _filter_interactive_frames(frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop decorative small-marker frames, keeping only genuine placement targets.

    closed_frames() also detects small, single-cell-interior hollow squares
    that are purely decorative styling on the target-sequence markers, not
    interactive slot-holding frames -- measured on SB26 L0: 4 marker frames
    with a 16-cell hole each, alongside ONE real frame with a 208-cell
    hole. size_clusters (the SAME kernel this game's whole slot/pool
    typology was built around) splits frames by hole size; only the
    LARGEST size class is kept, since a placement-holding frame needs room
    for actual slot content while a decorative marker does not. A single
    size class (nothing to split against) keeps everything.
    """
    if len(frames) < 2:
        return frames
    sized = [{"size": len(f["hole_cells"])} for f in frames]
    clusters = size_clusters(sized, ratio=1.5)
    largest = max(clusters, key=lambda idxs: sized[idxs[0]]["size"])
    return [frames[i] for i in largest]


def _perimeter(bbox: tuple[int, int, int, int]) -> int:
    r0, c0, r1, c1 = bbox
    h, w = r1 - r0 + 1, c1 - c0 + 1
    if h <= 0 or w <= 0:
        return 0
    if h == 1 or w == 1:
        return h * w
    return 2 * (h + w) - 4


def _recover_fused_frames(grid: Grid, candidates: list[Region], bg: int) -> list[dict[str, Any]]:
    """Frames closed_frames rejects because a same-colour appendage (e.g. a
    fused portal pipe, see the module docstring's former "kernel gap") is
    part of the same connected component, breaking closed_frames' exact
    cells-equal-border match.

    A clean ring's own region has cells == its bbox perimeter EXACTLY
    (that is closed_frames' own equality test), so it is never even tried
    here -- only a region with MORE cells than its own bounding-box
    perimeter (an appendage fused on, or a solid block) is a candidate.
    :func:`admorphiq.kernels.geometry.split_fused_frame` itself rejects a
    solid block (its geometric hole would be entirely filled, never a
    genuine ring) by returning ``None``, so this size check is a cheap
    pre-filter, not a load-bearing correctness guard.
    """
    recovered: list[dict[str, Any]] = []
    for region in candidates:
        if region["size"] <= _perimeter(region["bbox"]):
            continue
        split = split_fused_frame(region, frame=grid, background=bg)
        if split is None:
            continue
        f = split["frame"]
        recovered.append(
            {
                "border_color": region["color"],
                "outer_bbox": f["outer_bbox"],
                "inner_bbox": f["inner_bbox"],
                "hole_cells": f["hole_cells"],
            }
        )
    return recovered


def _plan_sb26(grid: Grid) -> list[PlanStep] | None:
    """The full placement click plan, DFS-ordered, or None if unsupported here."""
    if not grid:
        return None
    bg = most_common_color(grid)
    candidates = _candidates(grid)
    frames = _filter_interactive_frames(
        closed_frames(grid, background=bg) + _recover_fused_frames(grid, candidates, bg)
    )
    if not frames:
        return None

    all_hole: frozenset[Cell] = frozenset()
    for f in frames:
        all_hole |= f["hole_cells"]
    band_candidates = [r for r in candidates if not (r["cells"] & all_hole)]
    if len(band_candidates) < 2:
        return None
    bands = group_by_axis(band_candidates, axis="row", tolerance=_BAND_TOLERANCE)
    if len(bands) < 2:
        return None
    top_band = [band_candidates[i] for i in bands[0]]
    bottom_band = [band_candidates[i] for i in bands[-1]]

    pool_by_color: dict[int, list[Region]] = {}
    for r in bottom_band:
        pool_by_color.setdefault(r["color"], []).append(r)
    for lst in pool_by_color.values():
        lst.sort(key=lambda r: (r["centroid"][1], r["centroid"][0]))
    if not pool_by_color:
        return None

    # A target-band region whose colour is NOT suppliable from the pool at
    # all is connective/decorative chrome (measured: SB26's marker-frame
    # styling colour appears repeatedly in the target band but never in the
    # pool), not a genuine target -- drop it wholesale rather than assume a
    # fixed "chrome colour".
    target_colors = [
        r["color"] for r in sorted(top_band, key=lambda r: r["centroid"][1]) if r["color"] in pool_by_color
    ]
    if not target_colors:
        return None

    # A frame with only ONE content region is structurally indistinguishable
    # from a decorative single-item marker (the same shape as the dropped
    # target-band markers) -- a genuine placement frame needs multiple
    # slots to be worth clicking into. Measured necessary: closed_frames
    # rejects a real multi-slot frame outright when a portal pipe is fused
    # onto one of its edges (breaking the "cells == exact rectangle border"
    # match), which left ONLY single-item marker-shaped frames detected on
    # a portal-graph board -- without this guard those would be
    # mis-planned as one-slot "frames" instead of honestly finding nothing.
    keep = [(f, s) for f, s in zip(frames, (_frame_slots(f, candidates) for f in frames)) if len(s) >= 2]
    if not keep:
        return None
    frames = [f for f, _s in keep]
    frame_slots = [s for _f, s in keep]

    portal_of = _detect_portals(grid, frames, frame_slots, bg)
    order = _dfs_traversal(frame_slots, portal_of, len(target_colors))
    if not order:
        return None

    plan: list[PlanStep] = []
    used_pool: dict[int, int] = {}
    ti = 0
    for (frame_idx, slot_idx), kind in order:
        if kind != "item":
            continue
        if ti >= len(target_colors):
            break
        color = target_colors[ti]
        ti += 1
        pool_list = pool_by_color.get(color)
        if not pool_list:
            return None
        k = min(used_pool.get(color, 0), len(pool_list) - 1)
        used_pool[color] = k + 1
        pool_region = pool_list[k]
        slot_region = frame_slots[frame_idx][slot_idx]
        plan.append(("click", int(round(pool_region["centroid"][0])), int(round(pool_region["centroid"][1]))))
        plan.append(("click", int(round(slot_region["centroid"][0])), int(round(slot_region["centroid"][1]))))
    if not plan:
        return None
    plan.append(("simple", _VERIFY_ACTION))
    return plan


class Adapter(GameAdapter):
    """Portal-graph DFS placement composed entirely from admorphiq.kernels."""

    GAME_ID = GAME_ID

    def __init__(self, giveup: int = _GIVEUP_DEFAULT) -> None:
        self.restart_on_game_over = True

        self._giveup = giveup
        self._step = 0
        self._levels_seen = -1
        self._plan: list[PlanStep] = []
        self._plan_attempted = False
        self._settle_wait = 0
        self._prev_grid: Grid | None = None
        self._stall_count = 0

    # ── harness contract ────────────────────────────────────────────────

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        return state_name(latest_frame) == "WIN" or self._step >= self._giveup

    def choose_action(self, frames: list[Any], latest_frame: Any) -> GameAction:
        state = state_name(latest_frame)
        if state in ("NOT_PLAYED", "GAME_OVER") or not has_frame(latest_frame):
            self._reset_level_state()
            return reset_action()

        levels = int(getattr(latest_frame, "levels_completed", 0) or 0)
        if levels != self._levels_seen:
            self._levels_seen = levels
            self._reset_level_state()

        self._step += 1

        # Settle-wait: a multi-layer transient frame stack at level entry
        # mis-reads structure (see the module docstring's offline
        # verification). Bounded, one-shot per level.
        raw_layers = getattr(latest_frame, "frame", None) or []
        if len(raw_layers) > 1 and self._settle_wait < _SETTLE_MAX_WAIT:
            self._settle_wait += 1
            return click_action(x=0, y=0)

        grid = canonical_layer(latest_frame)
        self._observe(grid)

        simple_ids, action6_ok = available_action_ids(latest_frame)

        if not self._plan and not self._plan_attempted:
            self._plan_attempted = True
            plan = _plan_sb26(grid)
            if plan:
                self._plan = plan

        self._prev_grid = grid
        return self._next_action(grid, simple_ids, action6_ok)

    # ── level bookkeeping ───────────────────────────────────────────────

    def _reset_level_state(self) -> None:
        self._plan = []
        self._plan_attempted = False
        self._settle_wait = 0
        self._prev_grid = None
        self._stall_count = 0

    # ── measurement: did the last drained click do anything? ────────────

    def _observe(self, grid: Grid) -> None:
        if self._prev_grid is None or not self._plan:
            self._stall_count = 0
            return
        diff = frame_diff(self._prev_grid, grid)
        if diff["count"] == 0:
            self._stall_count += 1
        else:
            self._stall_count = 0
        if self._stall_count >= _STALL_LIMIT:
            # This layout guess stopped working partway through -- abandon
            # rather than drain a plan that is no longer tracking reality.
            self._plan = []
            self._stall_count = 0

    # ── planning: drain the precomputed plan one action per call ────────

    def _next_action(self, grid: Grid, simple_ids: list[int], action6_ok: bool) -> GameAction:
        while self._plan:
            kind, *rest = self._plan.pop(0)
            if kind == "click":
                if not action6_ok:
                    continue
                row, col = rest
                return click_action(x=col, y=row)
            aid = rest[0]
            if aid not in simple_ids:
                continue
            return simple_action(aid)
        # No plan (unsupported layout, or exhausted) -- a harmless idle
        # click at the frame's own observed centre rather than crash.
        height = len(grid) or 1
        width = len(grid[0]) if grid else 1
        return click_action(x=width // 2, y=height // 2)
