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
now resolved for BOTH of the level's two real frames**: neither of level
1's two REAL multi-slot frames is a pure rectangle border, but for two
DIFFERENT reasons, so ``closed_frames``'s exact "cells == rectangle
border" match rejects both outright (it never even reaches
``connectors``, which only separates ALREADY-distinct thin paths from
already-detected regions, not a fused/occluded shape):

- **Frame 1 (colour 14)** has a portal pipe fused onto its own edge as ONE
  connected component -- EXTRA same-colour cells.
  :func:`admorphiq.kernels.geometry.split_fused_frame` (the generic
  namespace-safe replacement for ``sort_match.py``'s game-specific
  ``_split_box_pipe``) recovers it.
- **Frame 2 (colour 8)** is missing 2 of its 72 perimeter cells --
  measured (``data/traces/sb26.npz`` level_index 1, frame 10): those 2
  cells are occupied by frame 1's own colour-14 pipe crossing frame 2's
  bottom border on its way to frame 1's ring. This is the OPPOSITE shape
  defect (too FEW cells, from a foreign-coloured occluder, not too many
  from a same-coloured appendage) --
  :func:`admorphiq.kernels.geometry.recover_occluded_frame` (R56,
  2026-07-15) recovers it, given every OTHER candidate region on the
  frame as its occluder set (never a specific colour -- the quarantine's
  "no hardcoded coordinates/palettes" rule applies to occluder selection
  too).

:func:`_recover_fused_frames` dispatches each candidate by comparing its
own cell count to its bbox's perimeter (a clean ring's cells equal that
perimeter EXACTLY -- ``closed_frames``' own test -- so an exact match is
never even tried here): MORE cells tries ``split_fused_frame``, FEWER
tries ``recover_occluded_frame``. Both kernels reject a shape that isn't
genuinely their case (``split_fused_frame`` rejects a solid block;
``recover_occluded_frame`` rejects a gap no occluder explains), so the
size-comparison dispatch is a cheap pre-filter, not a correctness guard.
Either recovered frame is reshaped into the same ``{"border_color",
"outer_bbox", "inner_bbox", "hole_cells"}`` shape ``closed_frames``
produces and unioned into the frame list BEFORE
:func:`_filter_interactive_frames` runs, so every downstream consumer
(slot detection, portal detection, DFS traversal) needs no changes at
all -- a recovered frame is indistinguishable from a clean one.

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
    frames; :func:`admorphiq.kernels.geometry.split_fused_frame` and
    :func:`admorphiq.kernels.geometry.recover_occluded_frame` recover the
    ones closed_frames rejects because a same-colour appendage is fused
    onto the border (too many cells) or a foreign-coloured region occludes
    part of it (too few cells), respectively (see "Fused-frame recovery"
    above; together these replace sort_match's own hollow-rectangle-vs-pipe
    splitting).
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
    recover_occluded_frame,
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

# Bounded number of planning attempts per level. A level-entry frame can be a
# transient where the board (e.g. the pool piece colours on the pool-portal
# level) has not fully rendered; each failed attempt idles one frame to let it
# settle. Generous enough to cover the settle, small enough to bail on a
# genuinely unsupported layout rather than spin.
_PLAN_MAX_TRIES = 8

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


def _insert_idx(slots: list[Region], centroid_col: float) -> int:
    """How many of ``slots`` sit strictly left of ``centroid_col`` -- the
    sorted insertion position a marker at that column implies, matching
    :func:`_frame_slots`'s own left-to-right sort key."""
    return sum(1 for s in slots if s["centroid"][1] < centroid_col)


def _detect_portals(
    grid: Grid,
    frames: list[dict[str, Any]],
    frame_slots: list[list[Region]],
    background: int,
    markers: list[dict[str, Any]],
    candidates: list[Region],
) -> dict[tuple[int, int], int]:
    """(source_frame_idx, insertion_index) -> destination_frame_idx.

    ``insertion_index`` means "before visiting THIS slot index in
    ``source_frame_idx``, first fully traverse ``destination_frame_idx``" --
    the source slot itself is STILL visited as a normal item afterward (a
    portal is a zero-action insertion point in the traversal order, not a
    slot that consumes a placement). ``insertion_index == len(slots)`` means
    "after every real slot".

    TWO independent, composable detection paths, since two DIFFERENT SB26
    boards were measured to need each:

    1. **Connector-pipe-based** (a physical same-colour pipe fuses two
       frames together, R56 first pass). Composes admorphiq.kernels.
       connectors over the frames' own border pseudo-regions. The
       INSERTION POINT is then determined primarily from ``markers`` (the
       :func:`_recover_fused_frames` appendage groups): if a marker of the
       connector's OWN colour sits inside one frame's hole (a decorative
       glyph physically drawn INSIDE that frame, not one of its measured
       item slots), that frame is the portal SOURCE and the insertion index
       is the marker's own sorted column position among that frame's slots
       (:func:`_insert_idx`). NECESSARY, not cosmetic: "whichever frame's
       slots sit nearest the connector's path" is genuinely ambiguous on
       the game this was diagnosed on (a real slot of the OTHER,
       non-source frame sits column-aligned with the connector and is
       narrowly closer by raw pixel distance) -- the marker identifies the
       frame structurally (something drawn INSIDE it), not spatially.
       Falls back to the nearest-slot proximity heuristic only when no
       marker explains either end of a found connector.

    2. **Colour-matched icon, no physical connector at all** (a hub frame
       with MULTIPLE small hollow-ring icons inside its own hole, each
       icon's colour matching a DIFFERENT leaf frame's own border colour,
       diagnosed on a 3-frame hub-and-leaf portal level with zero
       ``connectors()`` hits -- the icons are spatially disconnected from
       every leaf frame, not fused or piped to anything). For every
       non-slot content region (:func:`_frame_content` minus
       :func:`_frame_slots`) inside a frame's hole whose colour matches
       ANOTHER frame's ``border_color``, that frame is the source and the
       destination is whichever frame the colour matches; insertion index
       again from :func:`_insert_idx`. Naturally does not double-fire on a
       path-1 game: a fused icon there is never a standalone ``candidates``
       region (it only exists inside the flood-filled blob
       :func:`split_fused_frame` decomposes), so it never appears in
       ``_frame_content`` at all.
    """
    if len(frames) < 2:
        return {}
    portal_of: dict[tuple[int, int], int] = {}

    dest_by_color = {f["border_color"]: idx for idx, f in enumerate(frames)}
    for src_idx, src_frame in enumerate(frames):
        slot_ids = {id(s) for s in frame_slots[src_idx]}
        icons = [r for r in _frame_content(src_frame, candidates) if id(r) not in slot_ids]
        for icon in icons:
            dst_idx = dest_by_color.get(icon["color"])
            if dst_idx is None or dst_idx == src_idx:
                continue
            idx = _insert_idx(frame_slots[src_idx], icon["centroid"][1])
            portal_of.setdefault((src_idx, idx), dst_idx)

    frame_regions = [_frame_pseudo_region(f) for f in frames]
    links = connectors(grid, frame_regions, background=background)
    for link in links:
        a, b = link["a"], link["b"]
        path = link["path_cells"]
        color = link["color"]

        source = None
        insert_idx = None
        for idx in (a, b):
            hole = frames[idx]["hole_cells"]
            marker = next((m for m in markers if m["color"] == color and m["cells"] & hole), None)
            if marker is None:
                continue
            mcol = sum(c for _r, c in marker["cells"]) / len(marker["cells"])
            source = idx
            insert_idx = _insert_idx(frame_slots[idx], mcol)
            break

        if source is None:
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
            slots = frame_slots[source]
            insert_idx = min(range(len(slots)), key=lambda i: min(_dist2(slots[i]["centroid"], p) for p in path))

        dest = b if source == a else a
        portal_of.setdefault((source, insert_idx), dest)
    return portal_of


def _dfs_traversal(
    frame_slots: list[list[Region]], portal_of: dict[tuple[int, int], int], n_targets: int
) -> list[tuple[tuple[int, int], str]]:
    """DFS from frame 0: ``[((frame_idx, slot_idx), "item" | "portal" | "revisit"), ...]``.

    A small, MEASURED-graph traversal (adapter policy, not a kernel
    algorithm) mirroring the wiki-documented mechanic: a portal is a
    ZERO-ACTION insertion point, not a slot that consumes a placement --
    ``portal_of[(frame_idx, insert_idx)]`` fires BEFORE visiting slot
    ``insert_idx`` of ``frame_idx`` (``insert_idx == len(slots)`` fires
    after the last real slot), and that slot is STILL visited as a normal
    item afterward. Diagnosed necessary on this exact game: gold's actual
    click sequence places 2 real items in frame 0, silently continues into
    all 4 of frame 1's items with no separate "portal" action anywhere in
    the trace, then RETURNS to frame 0's 3rd remaining item -- a slot being
    "sacrificed" to trigger the portal (the pre-fix model) undercounts by
    exactly the sacrificed slot and never reaches the return leg. A
    revisited item slot still consumes a target index (its colour was
    fixed on first visit) without a fresh placement.
    """
    order: list[tuple[tuple[int, int], str]] = []
    seen: set[tuple[int, int]] = set()
    consumed = [0]

    def visit(frame_idx: int, depth: int = 0) -> None:
        if depth > 20 or frame_idx >= len(frame_slots):
            return
        slots = frame_slots[frame_idx]
        for slot_idx in range(len(slots) + 1):
            if consumed[0] >= n_targets:
                return
            key = (frame_idx, slot_idx)
            if key in portal_of:
                order.append((key, "portal"))
                visit(portal_of[key], depth + 1)
            if slot_idx < len(slots) and consumed[0] < n_targets:
                order.append((key, "revisit" if key in seen else "item"))
                seen.add(key)
                consumed[0] += 1

    if frame_slots:
        visit(0)
    return order


def _filter_interactive_frames(
    frames: list[dict[str, Any]], candidates: list[Region]
) -> list[dict[str, Any]]:
    """Drop decorative small-marker frames, keeping only genuine placement targets.

    closed_frames() also detects small, single-cell-interior hollow squares
    that are purely decorative styling on the target-sequence markers, not
    interactive slot-holding frames -- measured on SB26 L0: 4 marker frames
    with a SINGLE content region each (one decorative dot), alongside ONE
    real frame with 4 content regions. A frame's own CONTENT COUNT (regions
    whose cells fall inside its hole, via :func:`_frame_content`) is the
    discriminator: a genuine placement frame needs room for multiple
    interactable things (item slots, and possibly portal-marker icons too),
    a decorative marker structurally has exactly one.

    Superseded a HOLE-SIZE clustering approach (R56, this session): that
    heuristic assumed every real frame on a board is roughly the same size,
    which measurably breaks on an asymmetric hub-and-leaf portal-graph
    board (a 3-portal-frame level where the hub frame's hole is 2x+ larger
    than either leaf frame's, purely because the hub also hosts portal-icon
    markers alongside its own item slots) -- it would cluster the leaf
    frames away from the hub and drop them outright, even though each leaf
    frame has 2 genuine content regions, same as this function's own
    ``>= 2`` bar. Content-count generalizes to any number of differently-
    sized real frames on one board; hole-size clustering does not.
    """
    return [f for f in frames if len(_frame_content(f, candidates)) >= 2]


def _perimeter(bbox: tuple[int, int, int, int]) -> int:
    r0, c0, r1, c1 = bbox
    h, w = r1 - r0 + 1, c1 - c0 + 1
    if h <= 0 or w <= 0:
        return 0
    if h == 1 or w == 1:
        return h * w
    return 2 * (h + w) - 4


def _recover_fused_frames(
    grid: Grid, candidates: list[Region], bg: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Frames closed_frames rejects because their own cells don't EXACTLY
    equal their bbox's rectangle border -- either too MANY cells (a
    same-colour appendage, e.g. a fused portal pipe, fused into the same
    connected component) or too FEW (some of the border is covered by a
    DIFFERENT-coloured, already-detected region, e.g. a connector pipe
    crossing the frame's edge). A clean ring's own region has cells ==
    perimeter EXACTLY (that is closed_frames' own equality test), so it is
    never even tried here.

    Too many cells -> :func:`admorphiq.kernels.geometry.split_fused_frame`
    (rejects a solid block by returning ``None``, since its geometric hole
    would be entirely filled, never a genuine ring -- the size check above
    is a cheap pre-filter, not a load-bearing correctness guard). Its
    ``appendages`` (the leftover same-colour cells NOT part of the
    recovered ring -- e.g. a portal-marker glyph plus its connecting pipe)
    are returned alongside the frame as ``markers``, see below.

    Too few cells -> :func:`admorphiq.kernels.geometry.recover_occluded_frame`,
    diagnosed on this exact game (level 1's second portal frame: a
    colour-14 connector pipe crosses the colour-8 frame's border, replacing
    2 of its 72 perimeter cells) -- the occluder set is every OTHER
    candidate region on the frame (never a specific colour or shape; the
    "an occluder is whatever the caller supplies" contract stays generic
    here too, matching the quarantine rule against hardcoded coordinates/
    colours). Real-data validated across the full sb26 gold trace: 30/30
    recoveries genuine, zero false positives (see
    ``.wiki/wiki/rounds/r56_generic-kernels.md``).

    Returns ``(frames, markers)``: ``markers`` is every
    ``split_fused_frame`` appendage group, reshaped to ``{"cells",
    "color"}`` -- :func:`_detect_portals` uses whichever marker group falls
    inside a DIFFERENT frame's own hole to identify that frame as a
    portal's insertion point (see its own docstring for why: a marker
    physically sitting inside frame X's interior, not frame X's own
    detected item slots, is a portal glyph belonging to frame X, even
    though the ring it's geometrically fused onto is a DIFFERENT frame).
    """
    recovered: list[dict[str, Any]] = []
    markers: list[dict[str, Any]] = []
    for region in candidates:
        perimeter = _perimeter(region["bbox"])
        if region["size"] > perimeter:
            split = split_fused_frame(region, frame=grid, background=bg)
            if split is None:
                continue
            f = split["frame"]
            for appendage in split["appendages"]:
                markers.append({"cells": appendage["cells"], "color": region["color"]})
        elif region["size"] < perimeter:
            occluders = [r for r in candidates if r is not region]
            result = recover_occluded_frame(region, occluders=occluders)
            if result is None:
                continue
            f = result["frame"]
        else:
            continue
        recovered.append(
            {
                "border_color": region["color"],
                "outer_bbox": f["outer_bbox"],
                "inner_bbox": f["inner_bbox"],
                "hole_cells": f["hole_cells"],
            }
        )
    return recovered, markers


def _frame_slot_layout(frame: dict[str, Any], candidates: list[Region]) -> list[dict[str, Any]]:
    """EVERY slot of a frame, left-to-right, with its content — empty or a
    pre-placed item's colour.

    :func:`_frame_slots` returns only the empty-marker class (the placement
    targets); this returns the FULL slot row including any pre-placed colour
    items, which the pool-portal solver needs because a pre-filled slot's fixed
    colour PINS where a placed portal can go. Each entry is ``{"col", "row",
    "content", "region"}`` where ``content`` is ``None`` (empty spot) or the
    item's colour. Empty markers are the smallest size class (measured smaller
    than any colour item — the same discriminator :func:`_frame_slots` uses); a
    single size class means every slot is empty.
    """
    content = _frame_content(frame, candidates)
    if not content:
        return []
    clusters = size_clusters(content, ratio=1.5)
    smallest = min(clusters, key=lambda idxs: content[idxs[0]]["size"])
    empty_ids = {id(content[i]) for i in smallest}
    multi_class = len(clusters) > 1
    layout: list[dict[str, Any]] = []
    for r in sorted(content, key=lambda r: (r["centroid"][1], r["centroid"][0])):
        is_empty = (not multi_class) or id(r) in empty_ids
        layout.append(
            {
                "col": r["centroid"][1],
                "row": r["centroid"][0],
                "content": None if is_empty else int(r["color"]),
                "region": r,
            }
        )
    return layout


def _detect_pool_portal(
    grid: Grid, frames: list[dict[str, Any]], bg: int, frame_bottom: int
) -> dict[str, Any] | None:
    """A PORTAL piece sitting in the bottom pool band (not yet placed), or None.

    Unlike L1-L3's portals (fixed board features already inside a frame's hole),
    a deeper level can put a portal in the POOL as a hollow-ring piece the player
    must PLACE into a slot. :func:`admorphiq.kernels.closed_frames` detects it as
    a small hollow ring; it is told apart from the top-band target swatches (also
    hollow rings) by lying BELOW every interactive frame, and from a decorative
    ring by its border colour matching a real frame's border (that frame is the
    portal's destination). Returns ``{"row", "col", "dest_color"}`` or None."""
    portals: list[dict[str, Any]] = []
    frame_colors = {f["border_color"] for f in frames}
    for cf in closed_frames(grid, background=bg):
        r0, c0, r1, c1 = cf["outer_bbox"]
        crow = (r0 + r1) / 2
        if crow <= frame_bottom:
            continue  # a top-band target swatch or an interactive frame, not a pool piece
        if cf["border_color"] not in frame_colors:
            continue  # a ring whose colour names no frame is not a portal
        portals.append({"row": crow, "col": (c0 + c1) / 2, "dest_color": cf["border_color"]})
    if len(portals) != 1:
        return None  # exactly one pool portal is the supported case
    return portals[0]


def _plan_sb26_pool_portal(grid: Grid) -> list[PlanStep] | None:
    """Placement plan when the portal is a POOL piece to be PLACED (deeper level).

    The portal occupies one root-frame slot; the DFS then reads
    ``root[0..k-1] + dest[all] + root[k+1..]`` in traversal order, which must
    equal the target sequence. A pre-placed slot's fixed colour pins the only
    consistent portal position ``k``. Solves for ``k``, then places the portal
    into root slot ``k`` and each remaining colour into its DFS-ordered slot.
    Returns None (caller falls through to the fixed-portal planner) whenever the
    board is not this shape, so L1-L3 are untouched."""
    if not grid:
        return None
    bg = most_common_color(grid)
    candidates = _candidates(grid)
    fused_frames, _markers = _recover_fused_frames(grid, candidates, bg)
    frames = _filter_interactive_frames(closed_frames(grid, background=bg) + fused_frames, candidates)
    if len(frames) != 2:
        return None  # the measured pool-portal case is a 2-frame root+dest board
    frame_bottom = max(f["outer_bbox"][2] for f in frames)
    frame_top = min(f["outer_bbox"][0] for f in frames)
    portal = _detect_pool_portal(grid, frames, bg, frame_bottom)
    if portal is None:
        return None

    root = frames[0]  # kernel order (outer bbox top-left) — the DFS root
    dest_idx = next((i for i, f in enumerate(frames) if f["border_color"] == portal["dest_color"]), None)
    if dest_idx is None or dest_idx == 0:
        return None  # a portal cannot target the root
    root_slots = _frame_slot_layout(root, candidates)
    dest_slots = _frame_slot_layout(frames[dest_idx], candidates)
    if len(root_slots) < 2 or not dest_slots:
        return None

    # The target sequence is the row of hollow-ring swatches ABOVE the frames;
    # closed_frames reads each ring's BORDER colour cleanly (a plain colour-region
    # read would also pick up each ring's interior hole colour). Column order =
    # traversal order.
    target_rings = [
        cf
        for cf in closed_frames(grid, background=bg)
        if (cf["outer_bbox"][0] + cf["outer_bbox"][2]) / 2 < frame_top
    ]
    target_colors = [
        int(cf["border_color"]) for cf in sorted(target_rings, key=lambda cf: cf["outer_bbox"][1])
    ]
    if not target_colors:
        return None

    all_hole: frozenset[Cell] = frozenset()
    for f in frames:
        all_hole |= f["hole_cells"]
    band_candidates = [r for r in candidates if not (r["cells"] & all_hole)]
    bands = group_by_axis(band_candidates, axis="row", tolerance=_BAND_TOLERANCE)
    if len(bands) < 2:
        return None
    bottom_band = [band_candidates[i] for i in bands[-1]]

    # Pool solid swatches (colour -> queue of click points, left-to-right),
    # EXCLUDING the portal ring itself (the bottom-band region nearest it).
    pool: dict[int, list[tuple[int, int]]] = {}
    for r in sorted(bottom_band, key=lambda r: (r["centroid"][1], r["centroid"][0])):
        if r["color"] == bg:
            continue
        if abs(r["centroid"][1] - portal["col"]) <= 2 and abs(r["centroid"][0] - portal["row"]) <= 3:
            continue  # this is the portal piece, not a colour swatch
        pool.setdefault(int(r["color"]), []).append(
            (int(round(r["centroid"][0])), int(round(r["centroid"][1])))
        )

    # Solve for the portal slot k: the DFS order it induces must read the target
    # sequence, and every pre-filled slot's fixed colour must agree.
    for k in range(len(root_slots)):
        if root_slots[k]["content"] is not None:
            continue  # the portal must land on an EMPTY root slot
        order = root_slots[:k] + dest_slots + root_slots[k + 1 :]
        if len(order) != len(target_colors):
            continue
        assign = list(zip(order, target_colors))
        if any(s["content"] is not None and s["content"] != t for s, t in assign):
            continue
        need: dict[int, int] = {}
        for s, t in assign:
            if s["content"] is None:
                need[t] = need.get(t, 0) + 1
        if any(len(pool.get(color, [])) < cnt for color, cnt in need.items()):
            continue
        return _build_pool_portal_plan(portal, root_slots[k], assign, pool)
    return None


def _build_pool_portal_plan(
    portal: dict[str, Any],
    portal_slot: dict[str, Any],
    assign: list[tuple[dict[str, Any], int]],
    pool: dict[int, list[tuple[int, int]]],
) -> list[PlanStep]:
    """The click plan: place the portal into its slot, then each empty slot's
    colour in DFS order, then verify. Each placement is a pool-pick then a
    slot-click (the game's own pick-then-place gesture)."""
    plan: list[PlanStep] = [
        ("click", int(round(portal["row"])), int(round(portal["col"]))),
        ("click", int(round(portal_slot["row"])), int(round(portal_slot["col"]))),
    ]
    used: dict[int, int] = {}
    for slot, color in assign:
        if slot["content"] is not None:
            continue  # already on the board — the DFS reads it in place
        k = used.get(color, 0)
        used[color] = k + 1
        prow, pcol = pool[color][k]
        plan.append(("click", prow, pcol))
        plan.append(("click", int(round(slot["row"])), int(round(slot["col"]))))
    plan.append(("simple", _VERIFY_ACTION))
    return plan


def _plan_sb26(grid: Grid) -> list[PlanStep] | None:
    """The full placement click plan, DFS-ordered, or None if unsupported here."""
    if not grid:
        return None
    # A portal sitting in the pool (a piece to place) is a distinct, deeper case
    # from L1-L3's fixed in-frame portals; try it first and fall through when the
    # board is not that shape, so the L1-L3 path is byte-identical.
    pool_portal_plan = _plan_sb26_pool_portal(grid)
    if pool_portal_plan is not None:
        return pool_portal_plan
    bg = most_common_color(grid)
    candidates = _candidates(grid)
    fused_frames, markers = _recover_fused_frames(grid, candidates, bg)
    frames = _filter_interactive_frames(closed_frames(grid, background=bg) + fused_frames, candidates)
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

    portal_of = _detect_portals(grid, frames, frame_slots, bg, markers, candidates)
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
        self._plan_tries = 0
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

        # Retry planning (bounded) until a plan is found: a level-entry frame can
        # be a transient (the pool renders its piece colours a frame or two after
        # the level loads — measured on the pool-portal level), so a single
        # attempt on the first frame reads an incomplete board. Idle (a harmless
        # corner click) between tries lets the board settle. L1-L3 find their plan
        # on the first good frame, so their behaviour is unchanged.
        if not self._plan and self._plan_tries < _PLAN_MAX_TRIES:
            self._plan_tries += 1
            plan = _plan_sb26(grid)
            if plan:
                self._plan = plan

        self._prev_grid = grid
        return self._next_action(grid, simple_ids, action6_ok)

    # ── level bookkeeping ───────────────────────────────────────────────

    def _reset_level_state(self) -> None:
        self._plan = []
        self._plan_tries = 0
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
        # No plan yet (settling, unsupported layout, or exhausted) -- a harmless
        # idle click at the padding corner (never a sys_click sprite) so a
        # transient board can settle without perturbing any slot or pool piece.
        return click_action(x=0, y=0)
