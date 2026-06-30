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
