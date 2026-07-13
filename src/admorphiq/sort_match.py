"""Frame-only MATCH-TO-ORDER placement capability (R48).

A second member of the select-and-place ARRANGEMENT family (the first being
:mod:`admorphiq.arrangement`'s descend-and-sweep for movement+toggle games).
This one handles the **click-only sort** sub-class: the game exposes a SELECT
toggle + an ACTION6 click but NO movement actions, and the level is cleared by
placing a pool of coloured items into a row of slots so the placed order matches
a fixed REFERENCE order. SB26 level 1 is the measured exemplar — a top row of
colour-bordered frames (the reference order) plus a bottom row of matching
colour swatches (the pickable pool); the level clears when each mid-row spot
holds the swatch whose colour equals the reference frame at that position, then
a verify action (ACTION5) confirms the arrangement.

The capability is fully observation-driven — no game-id / game-title /
game-internal reads:

1. :func:`detect_match_layout` — segment the canonical layer into a top
   REFERENCE row (colour-distinct clusters high on the board), a bottom POOL
   row (matching-colour clusters low on the board), and a mid PLACEMENT band.
   Returns ``None`` when the top/bottom rows do not share a colour multiset
   (so the plan only engages on a genuine match-to-order layout).
2. :func:`plan_match_placement` — emit the ordered click plan: for each
   reference position left-to-right, click the pool swatch of the matching
   colour then the mid-row placement cell beneath that reference position, and
   finish with the verify action. The placement cells are derived from the
   reference cluster columns (the spot footprint absorbs the small column
   offset between a frame and its slot, measured on SB26 L1).

The verify-after-placement / hidden-spot design mirrors the descend-and-sweep
"let the env confirm the WIN" philosophy: the exact spot pixels are not visible
(the slots render as background until filled), but their COLUMNS are fixed by
the reference row, so the plan clicks the reference columns at the detected mid
band and lets the env validate.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import numpy as np

from .general_agent import connected_components

# ── Tunables ─────────────────────────────────────────────────────────────────

# A coloured component must be at least this large to count as a frame / swatch
# (filters single-pixel hint dots and anti-aliasing). SB26 frames/swatches are
# 4x4..6x6 squares → 12..36 px; the floor at 8 keeps small swatches while
# dropping 1-2 px specks.
_MIN_CLUSTER = 8
# A component this large is a board-spanning panel / playfield backdrop, not a
# discrete frame or swatch — excluded so the reference/pool rows stay clean.
_MAX_CLUSTER = 200
# Rows above this are the top REFERENCE band (the frame row); rows below
# _BOT_BAND are the bottom POOL band (the swatch row). Measured on SB26: frames
# at y~1-6, swatches at y~56-62.
_TOP_BAND = 10
_BOT_BAND = 53
# A non-background colour spanning at least this multiple of the median
# non-background colour count is a board fill / playfield band (chrome), not a
# discrete frame / swatch. Measured on SB26 L1: the slot-fill colour spans ~4x
# the median frame colour, while every frame/swatch colour sits near the median.
_CHROME_FILL_MULT = 3.0


# ── layout detection ────────────────────────────────────────────────────────


@dataclass
class MatchLayout:
    """A detected match-to-order layout for the click-sort placement plan.

    ``reference`` is the ordered list of ``(cx, color)`` top-row frames (the
    target colour order, left-to-right). ``pool`` maps each colour to the
    ``(cx, cy)`` centroid of its bottom-row swatch. ``placement_y`` is the mid
    band row to click when dropping a swatch into the slot beneath a reference
    frame.
    """

    reference: list[tuple[int, int]]
    pool: dict[int, tuple[int, int]]
    placement_y: int


def _chrome_colors(layer: np.ndarray, background: int) -> set[int]:
    """Background-class chrome to exclude: bg + any board-spanning fill colour.

    A frame / swatch is a small coloured square; a chrome colour is the
    background or a playfield-fill that spans far more pixels than a square. So
    a colour is chrome when its total pixel count is at least ``_CHROME_FILL_MULT``
    times the *median* non-background colour count (the typical frame/swatch
    footprint). This keeps the frame/swatch colours (all near the median) while
    dropping the background and a large fill band — without a fixed colour list,
    and robust to a frame colour tying as the second-most-frequent pixel (which a
    naive top-2 exclusion would wrongly drop).
    """
    chrome = {int(background)}
    if not layer.size:
        return chrome
    vals, counts = np.unique(layer, return_counts=True)
    chrome.add(int(vals[int(counts.argmax())]))
    nonbg = [(int(v), int(c)) for v, c in zip(vals.tolist(), counts.tolist()) if int(v) not in chrome]
    if nonbg:
        med = float(np.median([c for _v, c in nonbg]))
        for v, c in nonbg:
            if c >= _CHROME_FILL_MULT * med:
                chrome.add(v)
    return chrome


def detect_match_layout(layer: np.ndarray, background: int) -> MatchLayout | None:
    """Detect a top-reference / bottom-pool match-to-order layout, or None.

    A match-to-order layout has, on the same frame: a TOP row of distinct
    colour-bordered frames (the reference order) and a BOTTOM row of swatches
    whose colours cover the reference's multiset. The colour-coverage test is
    the falsifier — a layout whose bottom row cannot supply the top row's
    colours is not a sort puzzle and returns None, so the plan never engages on
    an unrelated click game. Pure / env-free.
    """
    if layer.size == 0:
        return None
    chrome = _chrome_colors(layer, background)
    comps = [
        c
        for c in connected_components(layer, background)
        if _MIN_CLUSTER <= c["size"] <= _MAX_CLUSTER and c["color"] not in chrome
    ]
    top = sorted((c for c in comps if c["cy"] < _TOP_BAND), key=lambda c: c["cx"])
    bottom = sorted((c for c in comps if c["cy"] > _BOT_BAND), key=lambda c: c["cx"])
    if len(top) < 2 or len(bottom) < 2:
        return None

    ref_colors = [c["color"] for c in top]
    pool_colors = [c["color"] for c in bottom]
    # The pool must supply every reference colour with at least the needed
    # multiplicity (a strict multiset equality would reject layouts with a spare
    # swatch, which the measured game allows).
    need = Counter(ref_colors)
    have = Counter(pool_colors)
    if any(have[col] < cnt for col, cnt in need.items()):
        return None

    reference = [(int(round(c["cx"])), int(c["color"])) for c in top]
    pool: dict[int, tuple[int, int]] = {}
    for c in bottom:
        pool.setdefault(int(c["color"]), (int(round(c["cx"])), int(round(c["cy"]))))
    # Placement band: midway between the top frame row and the bottom swatch row.
    top_y = float(np.mean([c["cy"] for c in top]))
    bot_y = float(np.mean([c["cy"] for c in bottom]))
    placement_y = int(round((top_y + bot_y) / 2))
    return MatchLayout(reference=reference, pool=pool, placement_y=placement_y)


# ── plan synthesis ──────────────────────────────────────────────────────────


@dataclass
class PortalSortLayout:
    """A detected portal-graph SORT layout (SB26 L2+ class).

    ``placements`` is the ordered list of ``(pool_xy, slot_xy)`` pairs to click —
    for the i-th slot the DFS traversal visits, click the pool swatch of the
    colour the target sequence assigns to that visit, then the slot. Order is the
    portal-graph DFS traversal order (NOT screen order), which is what the game's
    stack-based matcher consumes. ``verify_action`` is the scan/confirm action.
    """

    placements: list[tuple[tuple[int, int], tuple[int, int]]]
    verify_action: int


def _split_box_pipe(
    cells: set[tuple[int, int]],
) -> tuple[tuple[int, int, int, int] | None, set[tuple[int, int]]]:
    """Split a connected component into its hollow-rectangle BOX and thin PIPE.

    A SB26 frame renders as a hollow rectangle (border); a PORTAL renders as a
    1-2px-thin bar that extends OUT of the frame it points to and merges into the
    same colour component as that frame's border (measured L2: colour 14 = the
    frame-14 box + a vertical pipe up into frame-8's slot). BOX rows span most of
    the component width (a hollow rectangle's top/bottom edges AND its two side
    borders all reach both x-extremes); PIPE rows are the thin runs outside the
    box's row band. Returns ``(box_bbox, pipe_cells)`` — ``box_bbox`` is
    ``(x0, y0, x1, y1)`` or None when no wide rows exist (a pure pipe). ``cells``
    are ``(col, row)``. Pure / env-free. Minimal (vertical-pipe) form.
    """
    if not cells:
        return None, set()
    cols = [c for c, _r in cells]
    x0, x1 = min(cols), max(cols)
    width = x1 - x0 + 1
    row_cols: dict[int, list[int]] = {}
    for c, r in cells:
        row_cols.setdefault(r, []).append(c)
    box_rows = [r for r, cs in row_cols.items() if (max(cs) - min(cs) + 1) >= 0.6 * width]
    if not box_rows:
        return None, set(cells)
    box_top, box_bot = min(box_rows), max(box_rows)
    box = {(c, r) for c, r in cells if box_top <= r <= box_bot}
    pipe = {(c, r) for c, r in cells if r < box_top or r > box_bot}
    bx0 = min(c for c, _r in box)
    bx1 = max(c for c, _r in box)
    return (bx0, box_top, bx1, box_bot), pipe


def detect_portal_sort(layer: np.ndarray, background: int) -> PortalSortLayout | None:
    """Detect a portal-graph SORT layout and return the DFS-ordered placement plan.

    Fully observation-driven on the canonical layer (no game-id / internal reads):
    the top-display row is the target colour sequence; the mid-band hollow
    rectangles are the frames (their border colour = identity); a thin pipe
    merged into a frame's colour component is a portal linking the frame at the
    pipe's far endpoint to the frame whose border the pipe colour is; the bottom
    row is the pool. A depth-first traversal from the top frame (slots
    left-to-right, portals recurse, a re-visited slot does not consume a fresh
    target) yields the item-slot visitation order, which the target sequence maps
    to colours. Returns None when no two-frame portal structure is present, so the
    plan only engages on this sub-class (the simpler single-frame case stays with
    :func:`detect_match_layout`). Pure / env-free. Minimal L2 scope: in-frame
    (fixed) portals only — bottom-portal placement / permutation search is a
    future extension.
    """
    if layer.size == 0:
        return None
    # Background = the most-frequent colour of the CURRENT frame (robust to the
    # passed model background lagging the live render); frame/target/pool
    # detection is otherwise colour-agnostic (shape + role), because a SB26
    # frame-border colour (e.g. 14) is ALSO an item/target colour, so a
    # frequency-based chrome filter wrongly drops it.
    vals, counts = np.unique(layer, return_counts=True)
    bg = int(vals[int(counts.argmax())])
    comps = connected_components(layer, bg)

    # pool: bottom-row swatches, colour -> centroid (markers/separators may slip
    # in harmlessly — only colours the target sequence needs are ever looked up).
    pool: dict[int, tuple[int, int]] = {}
    for c in comps:
        if c["cy"] > _BOT_BAND and c["color"] != bg and c["size"] >= _MIN_CLUSTER:
            pool.setdefault(int(c["color"]), (int(round(c["cx"])), int(round(c["cy"]))))
    pool_colors = set(pool)
    if len(pool_colors) < 2:
        return None

    # target order: top-display cells whose colour is a real pool swatch colour
    # (this drops the thin separator chrome between cells without a colour list).
    top = sorted(
        (c for c in comps if c["cy"] < _TOP_BAND and int(c["color"]) in pool_colors and c["size"] >= _MIN_CLUSTER),
        key=lambda c: c["cx"],
    )
    target_order = [int(c["color"]) for c in top]
    if len(target_order) < 2:
        return None

    # frames (box parts) + pipes (portals): pure SHAPE detection (a hollow
    # rectangle), colour-agnostic — the shape filter excludes solid fills.
    frames: list[dict] = []
    pipes: list[tuple[int, set[tuple[int, int]]]] = []
    for c in comps:
        if c["color"] == bg or not (_TOP_BAND <= c["cy"] < _BOT_BAND):
            continue
        cells = {(col, r) for r, col in c["cells"]}
        box, pipe = _split_box_pipe(cells)
        if box is None:
            continue
        x0, y0, x1, y1 = box
        if (x1 - x0 + 1) >= 18 and (y1 - y0 + 1) >= 6:
            frames.append({"border": int(c["color"]), "bbox": box})
            if pipe:
                pipes.append((int(c["color"]), pipe))
    if len(frames) < 2:
        return None
    frames.sort(key=lambda f: f["bbox"][1])  # top-to-bottom; frame[0] = traversal root

    # slot grid per frame
    for f in frames:
        x0, y0, x1, y1 = f["bbox"]
        sy = y0 + 2
        slots = []
        i = 0
        while x0 + 2 + i * 6 + 4 <= x1 + 1:
            slots.append((x0 + 2 + i * 6, sy))
            i += 1
        f["slots"] = slots

    # portals: each pipe links a slot (in the frame containing its far endpoint)
    # to the frame whose border colour equals the pipe colour.
    portal_of: dict[tuple[int, int], int] = {}
    for color, pipe in pipes:
        endpoint = min(pipe, key=lambda cr: cr[1])  # topmost = far end (vertical pipe up)
        ex, ey = endpoint
        for f in frames:
            bx0, by0, bx1, by1 = f["bbox"]
            if bx0 <= ex <= bx1 and by0 - 2 <= ey <= by1 + 2 and f["slots"]:
                slot = min(f["slots"], key=lambda s: abs(s[0] - ex))
                portal_of[slot] = color
                break

    # DFS traversal -> item slots in visitation order, mapped to target colours
    frame_by_color = {f["border"]: f for f in frames}
    order: list[tuple[tuple[int, int], str]] = []
    seen: set[tuple[int, int]] = set()
    consumed = [0]

    def _traverse(frame: dict, depth: int = 0) -> None:
        if depth > 20 or consumed[0] >= len(target_order):
            return
        for s in frame["slots"]:
            if consumed[0] >= len(target_order):
                return
            if s in portal_of:
                order.append((s, "portal"))
                nxt = frame_by_color.get(portal_of[s])
                if nxt is not None:
                    _traverse(nxt, depth + 1)
            else:
                order.append((s, "revisit" if s in seen else "item"))
                seen.add(s)
                consumed[0] += 1

    _traverse(frames[0])
    slot_color: dict[tuple[int, int], int] = {}
    ti = 0
    for s, kind in order:
        if kind == "item":
            slot_color[s] = target_order[ti]
            ti += 1
        elif kind == "revisit":
            ti += 1

    placements: list[tuple[tuple[int, int], tuple[int, int]]] = []
    for s, kind in order:
        if kind != "item":
            continue
        color = slot_color.get(s)
        if color is None or color not in pool:
            return None  # a needed colour is not in the pool -> not this layout
        placements.append((pool[color], (s[0] + 2, s[1] + 2)))  # slot corner -> centre
    if not placements:
        return None
    return PortalSortLayout(placements=placements, verify_action=5)


def plan_match_placement(layout: MatchLayout, verify_action: int) -> list[tuple]:
    """Ordered action plan: place each pool swatch under its reference frame.

    Returns a list of action descriptors:
      ``("click", x, y)`` — an ACTION6 click at pixel (x, y).
      ``("simple", aid)`` — a simple action id (the verify ``verify_action``).
    For each reference position left-to-right: click the pool swatch of the
    matching colour, then click the mid-band placement cell at the reference
    frame's column. After all placements, issue the verify action so the env
    confirms the arrangement. Only one swatch position is recorded per colour by
    :func:`detect_match_layout`, so a repeated reference colour re-clicks that
    swatch — the measured sort game treats a swatch as a colour source, so
    re-selecting the same colour is accepted.
    """
    plan: list[tuple] = []
    for ref_x, color in layout.reference:
        pos = layout.pool.get(color)
        if pos is None:
            continue
        plan.append(("click", pos[0], pos[1]))
        plan.append(("click", ref_x, layout.placement_y))
    plan.append(("simple", verify_action))
    return plan
