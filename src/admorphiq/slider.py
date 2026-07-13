"""Frame-only SLIDER-PUZZLE capability (R28 world-model-agent family, sibling
of :mod:`admorphiq.rotation`).

A fifth member of the select-and-place family. This one handles the
**resizable-slider** sub-class: the game is click-only, the board holds one
or more compact axis-aligned bars — a solid FILL colour occupying most of a
narrow (elongated) rectangle, with one cell near the movable end recoloured
to a distinct TIP colour — plus, elsewhere along the SAME axis, a small
fixed-colour MARKER the bar's tip must be grown to reach. Widget clicks
(frame+interior "button" rings, structurally identical to
:mod:`admorphiq.rotation`'s pieces and detected by reusing
:func:`admorphiq.rotation.detect_rotatable_pieces`) grow or shrink a bar by a
fixed number of cells per click; every other click only burns the on-board
attempt/move counter, exactly as in the rotation sub-class.

Provenance: S5I5 was originally modelled (R28-rotation round) as an in-place
``np.rot90`` rotation puzzle, following ``.wiki/wiki/rounds/r53_unified-
harness.md``'s "s5i5 rotation-solver DESIGN" section. A live clean-reset
per-click trace (one reset before each of the 8 ambiguous widget candidates,
recording exact before/after cell diffs) showed the responsive clicks do NOT
rotate a 5x5 interior in place — they shift a bar's filled extent by a fixed
number of cells along one axis, entirely OUTSIDE any detected rotation
"piece" bbox. Repeated single-button clicks confirmed: a fixed 3-cell step
per click (until a measurement-artifact plateau — see below), one END of the
bar staying fixed (the ANCHOR) while the other END (the TIP, marked by a
single distinctly-coloured cell) moves. This matches ``.wiki/wiki/games/
S5I5.md`` verbatim, written BEFORE the R28 rotation round and never
consulted by it: "Resizeable slider objects plus rotate buttons... Clicking
a slider moves its goal marker by 3 units along slider axis." S5I5 is a
slider puzzle, not a rotation puzzle; :mod:`admorphiq.rotation` is kept as a
general capability for a genuine future rotation-mechanic game.

1. :func:`detect_slider_tracks` — a TRACK is a compact, elongated,
   mostly-filled bar with a single distinctly-coloured TIP cell near one end
   (the other end, the ANCHOR, never moves).
2. :func:`detect_track_markers` — candidate GOAL positions: any distinctly-
   coloured component within the track's own perpendicular band, OUTSIDE its
   current fill extent (so the tip's own marker cell, which sits AT the
   current extent, is excluded without needing a colour-based rule — see
   below on why the tip marker and a real target marker can share a colour).
3. Widget discovery reuses :func:`admorphiq.rotation.detect_rotatable_pieces`
   for the button rings (no separate detector needed — the buttons ARE the
   same frame+interior structure).
4. :func:`identify_moved_track` — attributes one live probe click to a track
   + direction (grow/shrink) + MEASURED step size (never assumed — the
   "3 units" above is the recorded S5I5 instance value, not a constant).
5. :func:`resolve_goal` + :func:`clicks_needed` + :func:`track_reached_goal`
   — plan and live-confirm the grow sequence, the same "let the env confirm"
   philosophy as the rest of the family.

Measured plateau caveat (not solved, does not affect the plan above): a
same-coloured TIP-style marker sitting IN a bar's growth path breaks
``connected_components``' 4-adjacency at that cell, so growth measured via
components can appear to "cap" there even though the bar keeps extending
underneath — :func:`_measure_tip` avoids this entirely by scanning the
band's raw pixel colours directly (never connected-component based), so it
reports the TRUE live extent regardless of any marker interrupting
connectivity.

Grow-only scope (recorded, not solved here): every marker observed on the
live S5I5 board sat AHEAD of the bar's initial tip in its one growable
direction (away from the fixed anchor), so :func:`resolve_goal` only
searches that side. The live probe still records a SHRINK button too, should
one be discovered, but no shrink-toward-goal plan is implemented — there is
no measured case motivating it (see the module's parent round's "no
speculative branches" instruction), so this module handles growth only.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .arrangement import _HUD_ROW_CUTOFF
from .general_agent import connected_components
from .rotation import RotatablePiece, detect_rotatable_pieces

# ── Tunables ─────────────────────────────────────────────────────────────────

# A track's short axis (the "band" thickness) must be at most this many
# cells. Measured S5I5 tracks are 3 cells thick.
_MAX_BAND = 4
# A track's long axis must span at least this many cells to be a plausible
# bar (filters small blobs that are not sliders).
_MIN_TRACK_LEN = 4
# Long axis must be at least this multiple of the short axis to count as
# "elongated" — excludes compact near-square shapes (e.g. a rotation-style
# 5x5 piece never qualifies as a track).
_MIN_ELONGATION = 1.5
# A track candidate's fill must occupy at least this fraction of its own
# bounding box. Measured S5I5 tracks: 14/15 initially (0.93), 71/72 after
# growth (0.986) — well above this floor; it only rules out sparse/hollow
# shapes (e.g. a rotation-style ring frame).
_MIN_FILL_RATIO = 0.6
# The tip-marker cell(s) — the single distinctly-coloured cell near the
# movable end — must total at most this many cells. Measured: 1.
_MAX_TIP_CELLS = 3
# A candidate GOAL marker component must span between these many cells.
# Measured S5I5 markers are single disconnected pixels (a 4-dot "diamond"
# under 4-connectivity), so the floor is 1; the ceiling excludes large
# structural regions (buttons, panels, the attempt-counter row).
_MIN_MARKER_SIZE = 1
_MAX_MARKER_SIZE = 8
# Small perpendicular tolerance (px) when matching a marker's centroid to a
# track's band — accommodates a marker whose centroid sits fractionally
# outside the exact measured band (e.g. a diagonal-looking dot cluster).
_BAND_SLOP = 1


# ── entity structures ───────────────────────────────────────────────────────


@dataclass
class SliderTrack:
    """A detected resizable slider bar.

    ``axis`` is ``"row"`` (the tip moves along columns, band is a row range)
    or ``"col"`` (tip moves along rows, band is a column range). ``band`` is
    the FIXED perpendicular coordinate range. ``anchor`` is the fixed end's
    axis coordinate; ``tip`` is the movable end's axis coordinate AT
    DETECTION TIME (re-measured live via :func:`_measure_tip` thereafter).
    """

    axis: str
    band: tuple[int, int]
    anchor: int
    tip: int
    fill_color: int
    tip_color: int


@dataclass
class TrackMarker:
    """A candidate goal position: a distinctly-coloured cell/component along
    a track's axis, outside its current fill extent."""

    axis_pos: int
    color: int


@dataclass
class SliderPuzzle:
    """A detected slider puzzle ready for live probing + commit.

    ``markers[i]`` is the candidate goal list for ``tracks[i]``.
    ``candidates`` is the ordered, de-duplicated list of ``(x, y)`` button
    click positions worth probing.
    """

    tracks: list[SliderTrack]
    markers: list[list[TrackMarker]]
    candidates: list[tuple[int, int]]


# ── detection ────────────────────────────────────────────────────────────────


def detect_slider_tracks(layer: np.ndarray, background: int) -> list[SliderTrack]:
    """Compact, elongated, mostly-filled bars with a distinct tip cell.

    For each candidate bar component, the bounding box is scanned for a
    single dominant non-fill, non-background colour occupying at most
    :data:`_MAX_TIP_CELLS` cells — that is the TIP marker, and whichever end
    of the bar it sits nearer to is the movable end (``tip``); the other end
    is the fixed ``anchor``. A bar with no such small distinct marker is
    skipped — with no discoverable tip there is no way to tell which end (if
    either) is meant to move. Pure / env-free.
    """
    tracks: list[SliderTrack] = []
    for c in connected_components(layer, background):
        if c["cy"] >= _HUD_ROW_CUTOFF:
            continue
        rows = [r for r, _c in c["cells"]]
        cols = [cc for _r, cc in c["cells"]]
        r0, r1, c0, c1 = min(rows), max(rows), min(cols), max(cols)
        h, w = r1 - r0 + 1, c1 - c0 + 1
        if h <= _MAX_BAND and w >= _MIN_TRACK_LEN and w >= h * _MIN_ELONGATION:
            axis, band, e0, e1 = "col", (r0, r1), c0, c1
        elif w <= _MAX_BAND and h >= _MIN_TRACK_LEN and h >= w * _MIN_ELONGATION:
            axis, band, e0, e1 = "row", (c0, c1), r0, r1
        else:
            continue
        if c["size"] / (h * w) < _MIN_FILL_RATIO:
            continue
        fill_color = c["color"]
        sub = layer[r0 : r1 + 1, c0 : c1 + 1]
        other = sub[(sub != background) & (sub != fill_color)]
        if other.size == 0 or other.size > _MAX_TIP_CELLS:
            continue
        vals, counts = np.unique(other, return_counts=True)
        tip_color = int(vals[int(counts.argmax())])
        tip_cells = [
            (r if axis == "row" else c2)
            for r in range(r0, r1 + 1)
            for c2 in range(c0, c1 + 1)
            if layer[r, c2] == tip_color
        ]
        avg_tip = sum(tip_cells) / len(tip_cells)
        if abs(avg_tip - e0) <= abs(avg_tip - e1):
            tip, anchor = e0, e1
        else:
            tip, anchor = e1, e0
        tracks.append(
            SliderTrack(axis=axis, band=band, anchor=anchor, tip=tip, fill_color=fill_color, tip_color=tip_color)
        )
    return tracks


def _measure_tip(layer: np.ndarray, track: SliderTrack) -> int:
    """Current LIVE axis-coordinate of ``track``'s movable end.

    Scans raw pixel colours (never ``connected_components``) along a single
    row/column through the middle of the track's band, so a same-coloured
    marker elsewhere on the bar's growth path — which would fragment a
    connected-component read into a shorter "capped-looking" piece — cannot
    under-report the true extent (see the module docstring's "measured
    plateau caveat"). Returns ``track.anchor`` when no fill cell is found
    (the bar shrank to nothing). Pure / env-free.
    """
    lo, hi = track.band
    mid = (lo + hi) // 2
    if track.axis == "col":
        positions = [c for c in range(layer.shape[1]) if layer[mid, c] == track.fill_color]
    else:
        positions = [r for r in range(layer.shape[0]) if layer[r, mid] == track.fill_color]
    if not positions:
        return track.anchor
    return max(positions, key=lambda p: abs(p - track.anchor))


def detect_track_markers(
    layer: np.ndarray, background: int, track: SliderTrack
) -> list[TrackMarker]:
    """Candidate goal positions along ``track``'s axis, outside its current extent.

    A candidate is any non-background, non-fill-colour component whose
    centroid falls within the track's perpendicular band (+/- a small
    tolerance) AND whose axis position is OUTSIDE the track's current
    ``[anchor, tip]`` extent. The extent exclusion — not a colour exclusion —
    is what keeps the tip's OWN marker cell from registering as its own
    "goal": on the real S5I5 board the tip marker and a genuine distant
    target marker are the SAME colour (both a generic "boundary" colour), so
    a colour-based filter would incorrectly drop real markers too; position
    is the only signal that reliably distinguishes "this track's own current
    edge" from "a fixed marker further along the lane". Pure / env-free.
    """
    lo, hi = track.band
    e_lo, e_hi = min(track.anchor, track.tip), max(track.anchor, track.tip)
    out: list[TrackMarker] = []
    for c in connected_components(layer, background):
        if c["color"] == track.fill_color or c["cy"] >= _HUD_ROW_CUTOFF:
            continue
        if not (_MIN_MARKER_SIZE <= c["size"] <= _MAX_MARKER_SIZE):
            continue
        perp = c["cy"] if track.axis == "col" else c["cx"]
        if not (lo - _BAND_SLOP <= perp <= hi + _BAND_SLOP):
            continue
        axis_pos = c["cx"] if track.axis == "col" else c["cy"]
        if e_lo <= axis_pos <= e_hi:
            continue
        out.append(TrackMarker(axis_pos=int(round(axis_pos)), color=c["color"]))
    return out


def detect_slider_puzzle(layer: np.ndarray, background: int) -> SliderPuzzle | None:
    """Detect a slider puzzle on ``layer``, or ``None`` when the structure is absent.

    Composes :func:`detect_slider_tracks` + (reused)
    :func:`admorphiq.rotation.detect_rotatable_pieces` for the button widgets
    + :func:`detect_track_markers`. Returns ``None`` when there are no
    tracks, no buttons, or no track has any candidate goal marker at all — so
    the caller only engages the slide phase on a genuine track+marker+button
    layout. Pure / env-free.
    """
    tracks = detect_slider_tracks(layer, background)
    if not tracks:
        return None
    buttons: list[RotatablePiece] = detect_rotatable_pieces(layer, background)
    if not buttons:
        return None
    markers = [detect_track_markers(layer, background, t) for t in tracks]
    if not any(markers):
        return None
    seen: set[tuple[int, int]] = set()
    candidates: list[tuple[int, int]] = []
    for b in buttons:
        pt = (int(round(b.cx)), int(round(b.cy)))
        if pt not in seen:
            seen.add(pt)
            candidates.append(pt)
    return SliderPuzzle(tracks=tracks, markers=markers, candidates=candidates)


# ── plan synthesis ──────────────────────────────────────────────────────────


def resolve_goal(track: SliderTrack, markers: list[TrackMarker]) -> int | None:
    """Nearest candidate marker AHEAD of ``track``'s tip, in its growth direction.

    "Growth direction" is away from the fixed anchor (the only direction the
    tip is structurally able to move, per :func:`detect_slider_tracks`'s own
    tip/anchor assignment). Returns ``None`` when no marker lies ahead — the
    live agent then leaves this track unadjusted rather than guessing. Pure /
    env-free.
    """
    sign = 1 if track.tip >= track.anchor else -1
    ahead = [m.axis_pos for m in markers if (m.axis_pos - track.tip) * sign > 0]
    if not ahead:
        return None
    return min(ahead, key=lambda p: abs(p - track.tip))


def clicks_needed(track: SliderTrack, goal: int, step: int) -> int:
    """Number of grow-clicks to reach or pass ``goal``, at the MEASURED ``step``.

    Ceiling division so the plan reaches or slightly overshoots the goal
    rather than falling short — :func:`track_reached_goal` is checked live
    after every click, so an overshoot-by-design still stops the instant the
    goal is actually reached, never wasting the extra clicks. Returns 0 when
    ``step`` is non-positive (a measurement that could not establish forward
    progress) — the caller must not attempt to click in that case. Pure /
    env-free.
    """
    if step <= 0:
        return 0
    distance = abs(goal - track.tip)
    return -(-distance // step)


def track_reached_goal(layer: np.ndarray, track: SliderTrack, goal: int) -> bool:
    """Has the LIVE tip reached or passed ``goal`` (in the growth direction)?

    Re-measures the tip from ``layer`` via :func:`_measure_tip` (robust to
    connectivity fragmentation — see that function's docstring) rather than
    trusting the click count, the same "let the env confirm" philosophy as
    :func:`admorphiq.rotation.piece_matches_target`. Pure / env-free.
    """
    tip = _measure_tip(layer, track)
    sign = 1 if track.tip >= track.anchor else -1
    return (tip - goal) * sign >= 0


# ── live probing ────────────────────────────────────────────────────────────


def identify_moved_track(
    tracks: list[SliderTrack], before: np.ndarray, after: np.ndarray
) -> tuple[int, int, str] | None:
    """Which track (if any) responded to one probe click, its step and direction.

    Returns ``(track_index, step, direction)`` where ``direction`` is
    ``"grow"`` when the tip moved FARTHER from its anchor, ``"shrink"`` when
    it moved closer, and ``step`` is the MEASURED absolute cell distance
    moved (never assumed). When multiple tracks show a change (not observed
    on the measured board, but not excluded), the one with the LARGEST
    measured step is attributed, mirroring
    :func:`admorphiq.rotation.identify_moved_piece`'s single-attribution
    contract. Pure / env-free.
    """
    if before.shape != after.shape:
        return None
    best: tuple[int, int, str] | None = None
    for i, t in enumerate(tracks):
        tip_before = _measure_tip(before, t)
        tip_after = _measure_tip(after, t)
        if tip_before == tip_after:
            continue
        step = abs(tip_after - tip_before)
        grew = abs(tip_after - t.anchor) > abs(tip_before - t.anchor)
        direction = "grow" if grew else "shrink"
        if best is None or step > best[1]:
            best = (i, step, direction)
    return best
