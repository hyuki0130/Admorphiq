"""Unit tests for the frame-only SLIDER-PUZZLE capability (R28 family, sibling
of rotation.py, S5I5-class).

These pin the click-only, attempt-limited RESIZABLE-SLIDER sub-class the
world-model agent uses for levels whose goal is "grow a bar's tip, by a
per-click step MEASURED from a live probe (never assumed), until it reaches a
fixed marker further along its axis" (S5I5 is the measured exemplar — see
slider.py's module docstring for the live-trace evidence that this, not an
in-place rotation, is S5I5's actual mechanic). Every test is env-free on
synthetic frames or hand-built dataclasses: the capability must be
observation-driven with no game-id / internal reads, so its behaviour is
fully exercised without touching the live env.
"""

from __future__ import annotations

import numpy as np

from admorphiq.slider import (
    SliderTrack,
    TrackMarker,
    clicks_needed,
    detect_slider_puzzle,
    detect_slider_tracks,
    detect_track_markers,
    identify_moved_track,
    resolve_goal,
    track_reached_goal,
)

_BG = 0
_FILL = 6
_TIP = 7
_MARKER = 8
_BTN_FRAME = 4
_BTN_INTERIOR = 9

# An asymmetric tight L-shape — reused as the button's interior pattern so
# it satisfies rotation.detect_rotatable_pieces's own anti-symmetry filter
# (mirrors tests/test_rotation.py's `_BASE`).
_BTN_BASE = np.array(
    [
        [True, False],
        [True, False],
        [True, True],
    ],
    dtype=bool,
)


def _blank() -> np.ndarray:
    return np.full((64, 64), _BG, dtype=np.int32)


def _stamp_ring(layer: np.ndarray, r0: int, r1: int, c0: int, c1: int, color: int) -> None:
    layer[r0, c0 : c1 + 1] = color
    layer[r1, c0 : c1 + 1] = color
    layer[r0 : r1 + 1, c0] = color
    layer[r0 : r1 + 1, c1] = color


def _stamp_shape(layer: np.ndarray, mask: np.ndarray, r0: int, c0: int, color: int) -> None:
    for dr, dc in zip(*np.where(mask)):
        layer[r0 + int(dr), c0 + int(dc)] = color


def _stamp_button(layer: np.ndarray, r0: int, c0: int) -> None:
    """A 5x5 frame+interior button ring, reusing rotation.py's own structure."""
    _stamp_ring(layer, r0, r0 + 4, c0, c0 + 4, _BTN_FRAME)
    _stamp_shape(layer, _BTN_BASE, r0 + 1, c0 + 1, _BTN_INTERIOR)


def _horizontal_track_board() -> np.ndarray:
    """A horizontal track (rows 10-12, fill cols 5-14), tip near col14 (the
    movable/right end), a genuine goal marker ahead at col30, a DECOY marker
    behind the anchor at col2 (must be excluded by direction, not by
    detect_track_markers itself), and an unrelated button elsewhere.
    """
    layer = _blank()
    layer[10:13, 5:15] = _FILL
    layer[11, 13] = _TIP
    layer[11, 30] = _MARKER
    layer[11, 2] = _MARKER
    _stamp_button(layer, 40, 40)
    return layer


def _vertical_track_board() -> np.ndarray:
    """A vertical track (cols 20-22, fill rows 5-14), tip near row14, a goal
    marker ahead at row30, and an unrelated button elsewhere."""
    layer = _blank()
    layer[5:15, 20:23] = _FILL
    layer[13, 21] = _TIP
    layer[30, 21] = _MARKER
    _stamp_button(layer, 40, 40)
    return layer


def test_detect_slider_tracks_finds_axis_anchor_and_tip():
    """Purpose: detect_slider_tracks recovers a horizontal track's axis,
    band, fixed anchor (far from the tip marker), and movable tip (near it).

    Expected feedback: a PASS proves the anchor/tip assignment correctly
    identifies which end is fixed vs movable purely from the tip marker's
    position; a FAIL means the agent could click the wrong direction or
    measure distances from the wrong end entirely.
    """
    tracks = detect_slider_tracks(_horizontal_track_board(), _BG)
    assert len(tracks) == 1
    t = tracks[0]
    assert t.axis == "col"
    assert t.band == (10, 12)
    assert t.anchor == 5
    assert t.tip == 14
    assert t.fill_color == _FILL
    assert t.tip_color == _TIP


def test_detect_slider_tracks_vertical_axis():
    """Purpose: detect_slider_tracks also recognises a VERTICAL bar (short
    axis = columns, long axis = rows) with the same anchor/tip logic.

    Expected feedback: a PASS proves the detector is axis-agnostic (not
    hardcoded to horizontal bars); a FAIL means a vertical slider game (like
    S5I5's second track) would never be detected.
    """
    tracks = detect_slider_tracks(_vertical_track_board(), _BG)
    assert len(tracks) == 1
    t = tracks[0]
    assert t.axis == "row"
    assert t.band == (20, 22)
    assert t.anchor == 5
    assert t.tip == 14


def test_detect_slider_tracks_rejects_compact_non_elongated_shape():
    """Purpose: a compact near-square blob (not elongated) — e.g. a
    rotation-style 5x5 piece — is never mistaken for a slider track.

    Expected feedback: a PASS proves the elongation requirement keeps the
    slider detector off unrelated compact structures (so it does not
    conflict with rotation.py's piece detection on a genuine rotation game);
    a FAIL means the two capabilities could false-positive on each other.
    """
    layer = _blank()
    layer[10:15, 10:15] = _FILL
    layer[11, 11] = _TIP
    assert detect_slider_tracks(layer, _BG) == []


def test_detect_slider_tracks_rejects_bar_without_tip_marker():
    """Purpose: a solid bar with NO distinctly-coloured tip cell (a plain
    rectangle, not a slider) is not returned as a track.

    Expected feedback: a PASS proves the tip-marker requirement prevents the
    detector from guessing which end (if any) is movable when there is no
    structural evidence; a FAIL means the agent could plan a click sequence
    for a static decoration.
    """
    layer = _blank()
    layer[10:13, 5:15] = _FILL
    assert detect_slider_tracks(layer, _BG) == []


def test_detect_track_markers_excludes_own_extent_includes_both_sides():
    """Purpose: detect_track_markers returns every distinctly-coloured
    component in the track's band OUTSIDE its current [anchor, tip] extent —
    including markers on EITHER side (ahead of the tip and behind the
    anchor) — since direction filtering is resolve_goal's job, not this
    function's.

    Expected feedback: a PASS proves markers are found by POSITION (not by
    excluding the tip's own colour, which on the real S5I5 board is shared
    with the genuine goal marker); a FAIL means either a real goal marker
    would be silently dropped or the tip's own notch would be
    mis-registered as a goal.
    """
    tracks = detect_slider_tracks(_horizontal_track_board(), _BG)
    markers = detect_track_markers(_horizontal_track_board(), _BG, tracks[0])
    positions = {m.axis_pos for m in markers}
    assert 30 in positions
    assert 2 in positions
    # Nothing from inside the track's own current extent [5, 14] registers.
    assert all(p < 5 or p > 14 for p in positions)


def test_resolve_goal_picks_nearest_marker_ahead_of_tip():
    """Purpose: resolve_goal returns the marker AHEAD of the tip (in the
    away-from-anchor direction), ignoring a decoy marker behind the anchor.

    Expected feedback: a PASS proves the goal resolution correctly filters by
    growth direction, not just proximity; a FAIL means the agent could target
    a marker it can never structurally reach (behind the fixed anchor) or
    pick the wrong one when multiple exist on both sides.
    """
    tracks = detect_slider_tracks(_horizontal_track_board(), _BG)
    markers = detect_track_markers(_horizontal_track_board(), _BG, tracks[0])
    assert resolve_goal(tracks[0], markers) == 30


def test_resolve_goal_none_without_a_marker_ahead():
    """Purpose: resolve_goal returns None when every candidate marker is
    behind the anchor (none ahead of the tip).

    Expected feedback: a PASS proves the agent leaves a track unadjusted
    rather than guessing a direction it has no evidence for; a FAIL means the
    plan could click toward an unreachable or wrong target.
    """
    track = SliderTrack(axis="col", band=(10, 12), anchor=5, tip=14, fill_color=_FILL, tip_color=_TIP)
    markers = [TrackMarker(axis_pos=2, color=_MARKER)]
    assert resolve_goal(track, markers) is None


def test_clicks_needed_uses_the_measured_step_not_a_hardcoded_constant():
    """Purpose: clicks_needed's click count scales with WHATEVER step is
    passed in — a per-click step of 5 (not the S5I5-measured 3) yields a
    different, correctly-computed (ceiling-divided) click count.

    Expected feedback: a PASS proves the plan is driven by the LIVE-MEASURED
    step (per the round's explicit "don't hardcode 3" requirement); a FAIL
    means a game whose slider moves a different distance per click would get
    a wrong, unmeasured click count.
    """
    track = SliderTrack(axis="col", band=(10, 12), anchor=5, tip=14, fill_color=_FILL, tip_color=_TIP)
    # Distance to goal is 30 - 14 = 16.
    assert clicks_needed(track, goal=30, step=3) == 6  # ceil(16/3)
    assert clicks_needed(track, goal=30, step=5) == 4  # ceil(16/5), NOT the step=3 answer
    assert clicks_needed(track, goal=30, step=16) == 1  # exact single click
    assert clicks_needed(track, goal=30, step=0) == 0  # non-positive step -> no plan


def test_track_reached_goal_reads_the_live_frame():
    """Purpose: track_reached_goal reports whether the LIVE tip position (not
    the detection-time snapshot) has reached or passed the goal.

    Expected feedback: a PASS proves the live commit loop can tell "goal
    reached" from the current frame after clicks have grown the bar; a FAIL
    means the agent could click past the goal (wasting attempts) or stop
    short of it (never confirming the plan is done).
    """
    track = SliderTrack(axis="col", band=(10, 12), anchor=5, tip=14, fill_color=_FILL, tip_color=_TIP)
    not_yet = _blank()
    not_yet[10:13, 5:20] = _FILL  # tip now at col19, short of goal 30
    assert track_reached_goal(not_yet, track, goal=30) is False
    reached = _blank()
    reached[10:13, 5:31] = _FILL  # tip now at col30, exactly at goal
    assert track_reached_goal(reached, track, goal=30) is True
    past = _blank()
    past[10:13, 5:36] = _FILL  # tip overshot to col35
    assert track_reached_goal(past, track, goal=30) is True


def test_identify_moved_track_measures_grow_step_and_direction():
    """Purpose: identify_moved_track measures the EXACT step size a probe
    click moved a track's tip (here, 7 cells — deliberately not the
    S5I5-measured 3, proving nothing is hardcoded) and correctly labels it
    "grow" (tip moved farther from the anchor).

    Expected feedback: a PASS proves per-click step measurement is read from
    the actual before/after frames; a FAIL means the plan could use a wrong,
    assumed step and mis-time the click count.
    """
    track = SliderTrack(axis="col", band=(10, 12), anchor=5, tip=14, fill_color=_FILL, tip_color=_TIP)
    before = _blank()
    before[10:13, 5:15] = _FILL
    after = _blank()
    after[10:13, 5:22] = _FILL  # tip grew from col14 to col21 -> step 7
    result = identify_moved_track([track], before, after)
    assert result == (0, 7, "grow")


def test_identify_moved_track_measures_shrink_and_returns_none_for_no_change():
    """Purpose: identify_moved_track also recognises a SHRINK (tip moved
    closer to the anchor) with its own measured step, and returns None when
    no track's tip moved at all (a probe that only burned the attempt
    counter, matching a non-widget click).

    Expected feedback: a PASS proves both directions are distinguished
    correctly and a truly inert probe is never mis-attributed; a FAIL means
    the agent could build a wrong grow/shrink button mapping or waste clicks
    on candidates that do nothing.
    """
    track = SliderTrack(axis="col", band=(10, 12), anchor=5, tip=14, fill_color=_FILL, tip_color=_TIP)
    before = _blank()
    before[10:13, 5:15] = _FILL
    shrunk = _blank()
    shrunk[10:13, 5:11] = _FILL  # tip shrank from col14 to col10 -> step 4
    assert identify_moved_track([track], before, shrunk) == (0, 4, "shrink")
    assert identify_moved_track([track], before, before.copy()) is None


def test_detect_slider_puzzle_full_pipeline():
    """Purpose: detect_slider_puzzle end-to-end on a genuine track + marker +
    button board returns the track, its candidate markers, and the button
    centroid as a probe candidate.

    Expected feedback: a PASS proves the composed detection entry point (the
    one the world-model agent's probe-phase gate calls) works on a realistic
    synthetic board; a FAIL means the agent would never enter the slide
    phase on a genuine layout.
    """
    puzzle = detect_slider_puzzle(_horizontal_track_board(), _BG)
    assert puzzle is not None
    assert len(puzzle.tracks) == 1
    assert len(puzzle.markers) == 1
    assert {m.axis_pos for m in puzzle.markers[0]} == {30, 2}
    assert puzzle.candidates == [(42, 42)]  # the button's centroid


def test_detect_slider_puzzle_none_without_button():
    """Purpose: a board with a genuine track+marker but NO clickable button
    anywhere returns None — there is nothing to probe, so the slide phase
    must not engage.

    Expected feedback: a PASS proves the plan stays dormant when there is no
    discoverable widget at all; a FAIL means the agent could enter the slide
    phase with an empty probe queue and immediately fall through, wasting a
    detection cycle for nothing.
    """
    layer = _blank()
    layer[10:13, 5:15] = _FILL
    layer[11, 13] = _TIP
    layer[11, 30] = _MARKER
    assert detect_slider_puzzle(layer, _BG) is None


def test_detect_slider_puzzle_none_without_track():
    """Purpose: a board with a button but no track at all returns None (not
    a false-positive slider puzzle).

    Expected feedback: a PASS proves an unrelated click game with a
    frame+interior button (e.g. a genuine rotation-puzzle piece) does not
    trigger the slide phase; a FAIL would mean this detector fires on nearly
    any click game with a button-shaped object.
    """
    layer = _blank()
    _stamp_button(layer, 40, 40)
    assert detect_slider_puzzle(layer, _BG) is None
