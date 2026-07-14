"""Tests for the M0R0 optimistic goal-directed navigation adapter (R56
backport of DC22/KA59's pattern, 2026-07-15) -- ``_detect_goal``'s two
reading modes (mirror-partner vs DC22-style singleton-marker fallback) and
the Adapter's own restart/hazard bookkeeping. See that module's docstring
for the offline gold-trace investigation this is based on (the mirror
partner is the measured mechanic on both captured gold levels; the
singleton-marker fallback is untested-but-plausible for any level that
turns out not to use it).
"""

from __future__ import annotations

from types import SimpleNamespace

from admorphiq.adapters25.m0r0 import Adapter, _detect_goal


def _region(color: int, bbox: tuple[int, int, int, int], size: int | None = None) -> dict:
    r0, c0, r1, c1 = bbox
    return {"color": color, "bbox": bbox, "size": size or (r1 - r0 + 1) * (c1 - c0 + 1)}


def test_detect_goal_picks_the_nearest_other_same_colour_region_as_the_mirror_partner():
    """Purpose: when >=2 regions share SELF's own colour, _detect_goal must
    return the NEAREST one excluding SELF's own current cell -- the
    measured mechanic (see module docstring: the goal IS the mirror
    partner's current position, not a distinct marker colour).
    Expected feedback: failure means the adapter would route toward the
    wrong same-coloured region (or toward SELF's own position), the exact
    defect that would make the optimistic planner useless on this game."""
    self_cell = (5, 5)
    near_partner = _region(7, (5, 20, 6, 21))
    far_partner = _region(7, (5, 50, 6, 51))
    other_colour = _region(3, (0, 0, 1, 1))
    # SELF's own region (same bbox as self_cell) must be excluded even
    # though it shares SELF's colour.
    self_region = _region(7, (5, 5, 6, 6))
    regions = [near_partner, far_partner, other_colour, self_region]
    color, cell = _detect_goal(regions, self_color=7, self_cell=self_cell, partner_ever_seen=False)
    assert color == 7
    assert cell == (5, 20)


def test_detect_goal_falls_back_to_smallest_singleton_colour_when_no_mirror_partner_exists():
    """Purpose: DC22's own "smallest singleton-coloured region" reading is
    the fallback hypothesis when no second SELF-coloured region exists --
    for any level that turns out to use a plain single-avatar-to-marker
    mechanic instead of the measured mirror-partner one.
    Expected feedback: failure means a level without a mirror partner
    would report no goal at all (self._goal_cell stays None forever),
    stalling the adapter in the probe phase permanently."""
    regions = [
        _region(7, (5, 5, 6, 6)),  # SELF, colour 7, singleton other than itself
        _region(2, (0, 0, 1, 60), size=1200),  # a big non-singleton-shared floor colour
        _region(2, (2, 0, 3, 60), size=1200),
        _region(9, (10, 10, 11, 11)),  # the smallest singleton -- the goal marker
        _region(4, (20, 20, 25, 25)),  # a bigger singleton, not the goal
    ]
    color, cell = _detect_goal(regions, self_color=7, self_cell=(5, 5), partner_ever_seen=False)
    assert color == 9
    assert cell == (10, 10)


def test_detect_goal_returns_none_when_no_candidate_exists_at_all():
    """Purpose: an empty region list (or one where every colour is either
    SELF's own or shared by >1 region) must report (None, None), not raise
    or fabricate a goal.
    Expected feedback: failure means the adapter would crash or silently
    accept a bogus goal cell on a board this rule genuinely can't read."""
    assert _detect_goal([], self_color=7, self_cell=(0, 0), partner_ever_seen=False) == (None, None)
    regions = [_region(2, (0, 0, 1, 1)), _region(2, (5, 5, 6, 6))]  # colour 2 used twice, not singleton
    assert _detect_goal(regions, self_color=7, self_cell=(0, 0), partner_ever_seen=False) == (None, None)


def test_detect_goal_reports_self_as_arrived_when_a_previously_seen_partner_merges():
    """Purpose: regression pin for the exact bug a first live smoke
    measured directly -- once a mirror partner has been seen at least once
    this level, a LATER frame where the two pieces are touching/merged
    (no longer a separate region) must report SELF's own cell as the goal
    ("already arrived"), NOT fall through to the singleton-colour fallback
    and fabricate a goal from an unrelated region (a HUD/border colour in
    the measured case, which sent the planner chasing it for dozens of
    wasted actions).
    Expected feedback: failure means the merge-vs-never-had-a-partner
    cases are indistinguishable again, reintroducing the exact defect this
    fix closed."""
    self_cell = (5, 5)
    # No separate colour-7 region exists this frame (merged with SELF) --
    # only an unrelated singleton colour is present.
    regions = [_region(7, (5, 5, 6, 6)), _region(9, (0, 0, 1, 1))]
    color, cell = _detect_goal(regions, self_color=7, self_cell=self_cell, partner_ever_seen=True)
    assert (color, cell) == (7, self_cell)

    # The SAME frame, but the partner was NEVER seen before -- must still
    # use the singleton fallback (a level that genuinely has no mirror
    # partner at all).
    color2, cell2 = _detect_goal(regions, self_color=7, self_cell=self_cell, partner_ever_seen=False)
    assert (color2, cell2) == (9, (0, 0))


def _make_frame(grid: list[list[int]], levels_completed: int = 0) -> SimpleNamespace:
    return SimpleNamespace(
        frame=[[list(row) for row in grid]],
        state=SimpleNamespace(name="NOT_FINISHED"),
        levels_completed=levels_completed,
        available_actions=[1, 2, 3, 4],
    )


def test_game_over_preserves_hazards_and_known_blocked_unlike_not_played():
    """Purpose: regression pin for the real bug found while porting DC22's
    control-flow shape into this file -- the PRE-backport version routed
    state == "GAME_OVER" through the SAME full-wipe path as NOT_PLAYED
    (forcing _levels_seen = -1, which discards _hazards/_known_blocked/
    _tried_from on the very next frame), silently defeating the documented
    hazard-memory mechanism on every single restart. GAME_OVER must call
    _on_restart() (preserve everything, only clear the current position)
    exactly like DC22's own correct handling; NOT_PLAYED must still fully
    reset (a genuinely fresh env).
    Expected feedback: failure means a live run would re-discover the same
    hazard on every attempt instead of learning it once, exactly the
    pre-backport defect this file's own docstring described."""
    adapter = Adapter()
    adapter._levels_seen = 0
    adapter._hazards = {(3, 3): {1, 2}}
    adapter._dead_cells = {(3, 3)}
    adapter._known_blocked = {(4, 4)}
    adapter._tried_from = {(3, 3): {1, 2}}
    adapter._active_cell = (3, 3)

    game_over_frame = SimpleNamespace(state=SimpleNamespace(name="GAME_OVER"))
    adapter.choose_action([], game_over_frame)
    assert adapter._hazards == {(3, 3): {1, 2}}
    assert adapter._dead_cells == {(3, 3)}
    assert adapter._known_blocked == {(4, 4)}
    assert adapter._tried_from == {(3, 3): {1, 2}}
    assert adapter._active_cell is None  # only the current position resets

    not_played_frame = SimpleNamespace(state=SimpleNamespace(name="NOT_PLAYED"))
    adapter.choose_action([], not_played_frame)
    assert adapter._levels_seen == -1  # forces a full _on_level_up on the next real frame


def test_on_level_up_resets_spatial_state_but_keeps_dir_map():
    """Purpose: pin the exact carryover contract -- dir_map (the measured
    control scheme) survives a level transition, but every spatial fact
    about the layout just left (hazards, dead cells, known_blocked,
    tried_from, goal) does not, since a new level is a new maze.
    Expected feedback: failure means either the control scheme is
    re-learned needlessly every level (wasted actions) or stale spatial
    facts from a DIFFERENT layout leak into the new level's routing."""
    adapter = Adapter()
    adapter._dir_map = {1: (-1, 0), 2: (1, 0)}
    adapter._hazards = {(3, 3): {1}}
    adapter._dead_cells = {(3, 3)}
    adapter._known_blocked = {(4, 4)}
    adapter._tried_from = {(3, 3): {1}}
    adapter._goal_cell = (9, 9)

    grid = tuple(tuple(0 for _ in range(10)) for _ in range(10))
    adapter._on_level_up(1, grid)

    assert adapter._dir_map == {1: (-1, 0), 2: (1, 0)}
    assert adapter._hazards == {}
    assert adapter._dead_cells == set()
    assert adapter._known_blocked == set()
    assert adapter._tried_from == {}
    assert adapter._goal_cell is None
    assert adapter._level_start_cell is None
