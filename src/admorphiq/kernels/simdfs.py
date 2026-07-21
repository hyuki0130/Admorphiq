"""Portal-graph faithful-simulator + DFS FAMILY CORE (R94 distillation).

The load-bearing solving ENGINE distilled out of the ``sb26`` script25 adapter's
full 8/8 conquest, so the SAME code drives two callers with no drifting copy:

  (a) the live adapter (``admorphiq.adapters25.sb26``) — its ``choose_action``
      planning call delegates ``_plan_sb26`` -> :func:`simdfs_plan` (structural
      delegation, extraction-not-rewrite: every planning body is the adapter's
      own, moved here verbatim, so live behaviour is byte-equivalent by
      construction), and
  (b) the offline model's patchable card — :func:`simdfs_core` wraps the same
      planner into ONE sandbox-runnable engine (frame + xy-carrying transition
      dicts + ``act``), assembled by ``tools.solver_core.source_card``.

The distilled slice is the SINGLE-FRAME portal-sort family: from ONE settled
frame, parse the board (bordered FRAMES exposing item SLOTS, PORTAL redirections,
a target-sequence display band, a colour POOL), build a FAITHFUL OFFLINE
SIMULATOR of the game's own portal DFS traversal, solve for the placement whose
DFS-ordered visits read the target sequence, and emit the pick-then-place click
plan. Because the portal-sort board is DETERMINISTIC and STATIC between actions
(the game only changes when the player clicks), the whole plan is derivable from
a single before/after-boundary observation — no intra-action time series — which
is exactly what makes this conquest expressible through the sandbox's per-action
before/after contract (unlike an animating/time-series game).

The adapter's own per-action harness wiring (settle-wait for a multi-layer
transient level-entry stack, bounded plan-retry, frame_diff stall-abandon, and
draining the plan one click per env step) stays adapter-local engine policy —
but the load-bearing SIMULATOR + DFS + placement solver lives here, so the
delegated portion is the solver, not a token slice. The core carries the
"plan-or-settle" orchestration (queue the full plan, else idle so a transient
board settles and the next refill re-plans) so the CARD — not just the adapter —
reproduces the retry loop from the growing observation stream.

Why this lives under ``admorphiq.kernels`` rather than ``tools/solver_core``: a
script25 adapter (quarantine zone) may only import stdlib, ``admorphiq.kernels.*``
and ``admorphiq.adapters25.base`` (enforced by ``scripts/adapters25_lint.py``), so
the delegation target the adapter imports MUST be a kernels submodule. The card is
still registered in ONE place (``tools.solver_core``); this module only supplies
the real source it bundles. ``most_common_color`` (an ``adapters25.base`` helper,
un-importable from a kernel) is replaced by the byte-identical local
:func:`_most_common_color` so parity is preserved.

Sandbox contract (see ``tools.code_agent.run_code``): the card runs with ONLY
``np``, Python builtins, ``from collections import Counter`` /
``from collections.abc import Mapping`` / ``from itertools import permutations``,
and the helper sources the card bundles. ``current_frame`` is a grid (list[list[int]]
in the sandbox, tuple/ndarray at adapter runtime — all normalize); ``transitions``
is a list of ``{"action", "xy": [x, y] | None, "before", "after"}`` dicts (unused
by this static-board planner, accepted for contract uniformity); ``act(name, x, y)``
QUEUES an action (``"CLICK"`` with x=col, y=row for ACTION6).
"""

from __future__ import annotations

from itertools import permutations
from typing import Any, Callable

from admorphiq.kernels._common import normalize_frame as _normalize_frame
from admorphiq.kernels.geometry import (
    closed_frames,
    connectors,
    recover_occluded_frame,
    split_fused_frame,
)
from admorphiq.kernels.regions import find_regions, group_by_axis, size_clusters

__all__ = [
    "simdfs_core",
    "simdfs_plan",
]

Grid = tuple[tuple[int, ...], ...]
Cell = tuple[int, int]
Region = dict[str, Any]
PlanStep = tuple[Any, ...]

# ── GAME-SPECIFIC PRIORS — RE-DERIVE from your observations ──────────────────
# These encode sb26's measured portal-sort semantics (see the sb26 adapter's
# module docstring). A patcher on a DIFFERENT portal/assignment game MUST
# re-derive them from the observed board: which simple action confirms a
# placement, what fraction of the board a chrome panel spans, how a HUD status
# band is shaped, how far apart two display rows sit, and the enumeration cap.

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

# Minimum row-centroid gap (pixels) between two target-swatch ROWS. The target
# sequence is a band of hollow-ring swatches above the frames; a long sequence
# wraps onto multiple rows (measured: L8's 12 targets span two rows), which must
# be read top row first then left-to-right, NOT globally by column (that
# interleaves the rows). Swatches within one row share a row centroid; rows are
# separated by more than a swatch's own height.
_TARGET_ROW_GAP = 4

# Upper bound on how many pool portals the multi-portal search will enumerate.
# Enumeration is permutations(empty_slots, n_portals); the measured deep levels
# use up to 3 portals, and 4 keeps the search well-bounded. Beyond this the
# solver bows out (returns None) rather than risk a slow plan inside one step.
_MAX_POOL_PORTALS = 4

# Simple-action id -> the sandbox ``act`` name (UP/DOWN/LEFT/RIGHT/SPACE/ACTION7):
# the plan emits ("simple", action_id); the core translates it for the sandbox.
_SIMPLE_ACTION_NAMES = {1: "UP", 2: "DOWN", 3: "LEFT", 4: "RIGHT", 5: "SPACE", 7: "ACTION7"}
# ── END GAME-SPECIFIC PRIORS ─────────────────────────────────────────────────


def _most_common_color(grid: Grid) -> int:
    """The single most frequent colour in ``grid`` — a generic background guess.

    Byte-identical to ``admorphiq.adapters25.base.most_common_color`` (which a
    kernel cannot import): ties broken toward the smallest colour value for
    determinism, 0 for an empty grid. Kept local so parity with the live adapter
    holds by construction.
    """
    counts: dict[int, int] = {}
    for row in grid:
        for v in row:
            counts[v] = counts.get(v, 0) + 1
    if not counts:
        return 0
    return max(counts.items(), key=lambda kv: (kv[1], -kv[0]))[0]


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
    bg = _most_common_color(grid)
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


def _detect_pool_portals(
    grid: Grid, frames: list[dict[str, Any]], bg: int, frame_bottom: int
) -> list[dict[str, Any]]:
    """Every PORTAL piece sitting in the bottom pool band (not yet placed).

    Unlike L1-L3's portals (fixed board features already inside a frame's hole),
    a deeper level can put portals in the POOL as hollow-ring pieces the player
    must PLACE into slots. :func:`admorphiq.kernels.closed_frames` detects each as
    a small hollow ring; they are told apart from the top-band target swatches
    (also hollow rings) by lying BELOW every interactive frame, and from a
    decorative ring by a border colour that names a real frame (that frame is the
    portal's destination). Each entry is ``{"row", "col", "dest_color"}``, sorted
    left-to-right."""
    portals: list[dict[str, Any]] = []
    frame_colors = {f["border_color"] for f in frames}
    for cf in closed_frames(grid, background=bg):
        r0, c0, r1, c1 = cf["outer_bbox"]
        crow = (r0 + r1) / 2
        if crow <= frame_bottom:
            continue  # a top-band target swatch or an interactive frame, not a pool piece
        if cf["border_color"] not in frame_colors:
            continue  # a ring whose colour names no frame is not a portal
        portals.append({"row": crow, "col": (c0 + c1) / 2, "dest_color": int(cf["border_color"])})
    portals.sort(key=lambda p: p["col"])
    return portals


def _detect_pool_portal(
    grid: Grid, frames: list[dict[str, Any]], bg: int, frame_bottom: int
) -> dict[str, Any] | None:
    """The single pool portal, or None unless exactly one is present (the L4
    case — the two-portal L5 case has its own solver)."""
    portals = _detect_pool_portals(grid, frames, bg, frame_bottom)
    return portals[0] if len(portals) == 1 else None


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
    bg = _most_common_color(grid)
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


def _simulate_portal_dfs(
    root: int, kinds: list[list[tuple[str, Any]]], n_targets: int
) -> list[tuple[int, int]] | None:
    """The item-visit sequence of the DFS the game runs from ``root``, stopped
    once ``n_targets`` items are visited.

    Faithful to the game's own traversal (source ``dbfxrigdqx``/``rfdjlhefnd``):
    slots are visited left-to-right; a PORTAL slot descends into its destination
    frame (a zero-target jump), and after that frame is fully traversed the walk
    RETURNS and continues at the next slot. An ITEM slot is a visit that consumes
    the next target. Frames MAY be re-entered — two portals to one frame traverse
    it twice (L5), and a pair of MUTUAL portals cycle A→B→A→B until the target
    count is met (L8) — so this is an iterative walk BOUNDED by ``n_targets`` (the
    game wins the moment the last target is filled), with a step cap that rejects
    a degenerate loop that never fills targets (the game FAILs those). Returns the
    exact-length visit list, or None if the walk ends early or spins. ``kinds[f][s]``
    is ``("portal", dest_idx)`` or ``("item", (f, s))``."""
    stack: list[list[int]] = [[root, 0]]
    order: list[tuple[int, int]] = []
    steps = 0
    max_steps = n_targets * 8 + 128
    while stack and len(order) < n_targets:
        steps += 1
        if steps > max_steps:
            return None  # a non-productive loop — the game's loop-guard FAILs it too
        f, s = stack[-1]
        slots = kinds[f]
        if s >= len(slots):
            stack.pop()  # frame exhausted — return to the parent, past its portal slot
            if stack:
                stack[-1][1] += 1
            continue
        kind = slots[s]
        if kind[0] == "portal":
            stack.append([kind[1], 0])
        else:
            order.append(kind[1])
            stack[-1][1] += 1
    return order if len(order) == n_targets else None


def _read_target_sequence(target_rings: list[dict[str, Any]]) -> list[int]:
    """The target colour sequence in READING order: top row left-to-right, then
    each lower row. Reading globally by column would interleave a wrapped
    multi-row band (see :data:`_TARGET_ROW_GAP`)."""
    if not target_rings:
        return []
    entries = sorted(
        (((cf["outer_bbox"][0] + cf["outer_bbox"][2]) / 2, cf["outer_bbox"][1], int(cf["border_color"]))
         for cf in target_rings),
        key=lambda e: (e[0], e[1]),
    )
    rows: list[list[tuple[float, int, int]]] = [[]]
    last_row: float | None = None
    for r, c, color in entries:
        if last_row is not None and r - last_row > _TARGET_ROW_GAP:
            rows.append([])
        rows[-1].append((r, c, color))
        last_row = r
    sequence: list[int] = []
    for row in rows:
        sequence.extend(color for _r, _c, color in sorted(row, key=lambda e: e[1]))
    return sequence


def _read_targets_and_pool(
    grid: Grid,
    frames: list[dict[str, Any]],
    candidates: list[Region],
    bg: int,
    frame_top: int,
    portals: list[dict[str, Any]],
) -> tuple[list[int], dict[int, list[tuple[int, int]]]] | None:
    """The target colour sequence (top-band ring borders, traversal order) and
    the pool colour swatches (colour -> click points), or None if unreadable.
    Shared by the one- and two-portal solvers. The pool excludes the hollow
    portal rings (matched by position)."""
    target_rings = [
        cf
        for cf in closed_frames(grid, background=bg)
        if (cf["outer_bbox"][0] + cf["outer_bbox"][2]) / 2 < frame_top
    ]
    target_colors = _read_target_sequence(target_rings)
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
    pool: dict[int, list[tuple[int, int]]] = {}
    for r in sorted(bottom_band, key=lambda r: (r["centroid"][1], r["centroid"][0])):
        if r["color"] == bg:
            continue
        if any(
            abs(r["centroid"][1] - p["col"]) <= 2 and abs(r["centroid"][0] - p["row"]) <= 3
            for p in portals
        ):
            continue  # a hollow portal ring, not a colour swatch
        pool.setdefault(int(r["color"]), []).append(
            (int(round(r["centroid"][0])), int(round(r["centroid"][1])))
        )
    return target_colors, pool


def _plan_sb26_multi_portal(grid: Grid) -> list[PlanStep] | None:
    """Placement plan when TWO OR MORE portals must be placed from the pool
    (L5/L6-class).

    Pool portals routed into the frames make the DFS traverse destination frames
    extra times (their item slots re-read against later target positions), so a
    few physical slots produce a longer target sequence — e.g. two portals to one
    leaf traverse it twice (L5), three portals from an all-portal root visit three
    leaves once each (L6). Exact search: enumerate the portals over empty slots
    (never a portal's own destination frame), SIMULATE the resulting DFS, assign
    the target sequence to the item-visit order, and accept the first placement
    where every slot's colour is consistent across its (possibly repeated) visits,
    pre-filled slots agree, and the pool can supply the empties. Gated on >= 2
    pool portals (the one-portal L4 case has its own solver, so L1-L4 stay
    byte-identical); returns None on any unsupported shape."""
    if not grid:
        return None
    bg = _most_common_color(grid)
    candidates = _candidates(grid)
    fused_frames, _markers = _recover_fused_frames(grid, candidates, bg)
    frames = _filter_interactive_frames(closed_frames(grid, background=bg) + fused_frames, candidates)
    if len(frames) < 2:
        return None
    frame_bottom = max(f["outer_bbox"][2] for f in frames)
    frame_top = min(f["outer_bbox"][0] for f in frames)
    portals = _detect_pool_portals(grid, frames, bg, frame_bottom)
    if not 2 <= len(portals) <= _MAX_POOL_PORTALS:
        return None

    border_to_idx = {f["border_color"]: i for i, f in enumerate(frames)}
    dests = [border_to_idx.get(p["dest_color"]) for p in portals]
    if any(d is None for d in dests):
        return None
    layouts = [_frame_slot_layout(f, candidates) for f in frames]
    if any(not layout for layout in layouts):
        return None
    read = _read_targets_and_pool(grid, frames, candidates, bg, frame_top, portals)
    if read is None:
        return None
    target_colors, pool = read

    empty = [
        (fi, si) for fi, layout in enumerate(layouts) for si, slot in enumerate(layout) if slot["content"] is None
    ]
    for placement in permutations(empty, len(portals)):
        if any(placement[i][0] == dests[i] for i in range(len(portals))):
            continue  # a portal cannot target the frame it sits in
        kinds: list[list[tuple[str, Any]]] = [
            [("item", (fi, si)) for si in range(len(layouts[fi]))] for fi in range(len(frames))
        ]
        for i, (fi, si) in enumerate(placement):
            kinds[fi][si] = ("portal", dests[i])
        order = _simulate_portal_dfs(0, kinds, len(target_colors))
        if order is None:
            continue
        slot_color: dict[tuple[int, int], int] = {}
        if not _assign_colors(order, target_colors, slot_color):
            continue
        if not _placement_consistent(layouts, placement, slot_color, pool):
            continue
        return _build_multi_portal_plan(portals, placement, layouts, slot_color, pool)
    return None


def _assign_colors(
    order: list[tuple[int, int]], target_colors: list[int], slot_color: dict[tuple[int, int], int]
) -> bool:
    """Map each item visit to its target colour; a slot re-read by a second portal
    pass must carry the SAME colour both times. Fills ``slot_color`` in place,
    returns whether the assignment is conflict-free."""
    for key, tcol in zip(order, target_colors):
        if key in slot_color:
            if slot_color[key] != tcol:
                return False
        else:
            slot_color[key] = tcol
    return True


def _placement_consistent(
    layouts: list[list[dict[str, Any]]],
    placement: tuple[tuple[int, int], ...],
    slot_color: dict[tuple[int, int], int],
    pool: dict[int, list[tuple[int, int]]],
) -> bool:
    """Every non-portal slot is visited and gets a colour, pre-filled slots keep
    their fixed colour, and the pool can supply every empty slot's colour."""
    portal_slots = set(placement)
    need: dict[int, int] = {}
    for fi, layout in enumerate(layouts):
        for si, slot in enumerate(layout):
            key = (fi, si)
            if key in portal_slots:
                continue
            if key not in slot_color:
                return False  # an item slot the traversal never reaches
            if slot["content"] is not None:
                if slot["content"] != slot_color[key]:
                    return False
            else:
                need[slot_color[key]] = need.get(slot_color[key], 0) + 1
    return all(len(pool.get(color, [])) >= cnt for color, cnt in need.items())


def _build_multi_portal_plan(
    portals: list[dict[str, Any]],
    placement: tuple[tuple[int, int], ...],
    layouts: list[list[dict[str, Any]]],
    slot_color: dict[tuple[int, int], int],
    pool: dict[int, list[tuple[int, int]]],
) -> list[PlanStep]:
    """Place each portal into its slot, then each empty slot's colour (in DFS
    visit order), then verify."""
    plan: list[PlanStep] = []
    for portal, (fi, si) in zip(portals, placement):
        slot = layouts[fi][si]
        plan.append(("click", int(round(portal["row"])), int(round(portal["col"]))))
        plan.append(("click", int(round(slot["row"])), int(round(slot["col"]))))
    used: dict[int, int] = {}
    portal_slots = set(placement)
    for (fi, si), color in slot_color.items():
        if (fi, si) in portal_slots:
            continue
        slot = layouts[fi][si]
        if slot["content"] is not None:
            continue
        k = used.get(color, 0)
        used[color] = k + 1
        prow, pcol = pool[color][k]
        plan.append(("click", prow, pcol))
        plan.append(("click", int(round(slot["row"])), int(round(slot["col"]))))
    plan.append(("simple", _VERIFY_ACTION))
    return plan


def simdfs_plan(grid: Grid) -> list[PlanStep] | None:
    """The full placement click plan, DFS-ordered, or None if unsupported here.

    The load-bearing solving ENGINE (renamed from the sb26 adapter's own
    ``_plan_sb26``, extracted verbatim so the live adapter is byte-equivalent):
    parse the board -> build the faithful offline portal-DFS simulator -> solve
    the placement whose DFS-ordered visits read the target sequence -> emit the
    pick-then-place click plan. ``grid`` is a settled board (tuple/list rows of
    int colour indices)."""
    if not grid:
        return None
    # A portal sitting in the pool (a piece to place) is a distinct, deeper case
    # from L1-L3's fixed in-frame portals; try it first and fall through when the
    # board is not that shape, so the L1-L3 path is byte-identical. The one- and
    # two-portal pool cases are separate gated solvers so each shallower level
    # stays byte-identical.
    pool_portal_plan = _plan_sb26_pool_portal(grid)
    if pool_portal_plan is not None:
        return pool_portal_plan
    two_portal_plan = _plan_sb26_multi_portal(grid)
    if two_portal_plan is not None:
        return two_portal_plan
    bg = _most_common_color(grid)
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


def simdfs_core(
    current_frame: Any,
    transitions: list[dict[str, Any]],
    act: Callable[..., None],
    trace: list[str] | None = None,
) -> None:
    """Sandbox-runnable portal-sort engine: parse the settled ``current_frame``,
    build the faithful offline portal-DFS simulator, solve the placement, and
    QUEUE the pick-then-place click plan.

    Carries the sb26 conquest's load-bearing SIMULATOR + DFS + placement solver
    (:func:`simdfs_plan`) PLUS its plan-or-settle orchestration: because a
    portal-sort board is deterministic and static between actions, the whole plan
    is derivable from ONE settled frame (``transitions`` are accepted for the
    sandbox contract but not needed by this static-board planner). When the board
    is a level-entry transient the plan comes back ``None``; the core then QUEUES
    a single harmless idle corner click so the board settles and the next refill
    (on the settled frame) re-plans — the same bounded retry the live adapter runs
    across env steps. Instrumented ``trace`` lines (plan length or the settle
    decision) give a patcher localization evidence.
    """
    grid = _normalize_frame(current_frame)
    plan = simdfs_plan(grid)
    if not plan:
        if trace is not None:
            trace.append("no plan (transient/unsupported board) -> idle-settle, retry next refill")
        act("CLICK", 0, 0)
        return
    if trace is not None:
        clicks = sum(1 for step in plan if step[0] == "click")
        trace.append(f"plan={len(plan)} steps ({clicks} clicks) -> queue")
    for step in plan:
        if step[0] == "click":
            _kind, row, col = step
            act("CLICK", int(col), int(row))
        else:
            name = _SIMPLE_ACTION_NAMES.get(step[1])
            if name is not None:
                act(name)
