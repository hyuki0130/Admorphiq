"""Tests for the M0R0 joint-state hill-climbing navigation adapter (R56
second backport, 2026-07-15) -- ``_gap_score``/``_detect_singleton_marker``,
the per-side ``_observe_piece`` measurement (dir_map/dir_sign bootstrap and
disambiguation), and the Adapter's own restart/hazard/level-up bookkeeping.
See that module's docstring for the offline gold-trace investigation this
is based on: EVERY action moves BOTH the SELF and PARTNER regions on the
same frame (not "SELF moves, partner is a separate goal"), and the win
condition is NOT uniform bbox-adjacency across the two captured levels --
the planner therefore hill-climbs a combined gap score rather than routing
to a fixed target cell.
"""

from __future__ import annotations

from types import SimpleNamespace

from admorphiq.adapters25.m0r0 import Adapter, _detect_singleton_marker, _gap_score, _rematch_radius


def _region(color: int, bbox: tuple[int, int, int, int], size: int | None = None) -> dict:
    r0, c0, r1, c1 = bbox
    return {"color": color, "bbox": bbox, "size": size or (r1 - r0 + 1) * (c1 - c0 + 1)}


def test_gap_score_is_manhattan_distance_between_the_two_pieces():
    """Purpose: _gap_score is the scalar the joint planner hill-climbs
    downward every decision -- it must be a plain Manhattan distance (no
    axis-specific "closing direction" baked in, since the module docstring
    found the two captured levels close DIFFERENT axes to win: level 0
    closes columns to 0, level 1 closes rows to 0 while columns plateau at
    a wall-capped floor). Manhattan distance decreases under both observed
    win patterns without assuming either one is universal.
    Expected feedback: failure means the planner's improvement signal is
    wrong, which would make _route_joint's goal_test either never fire
    (no state ever "improves") or fire on the wrong states."""
    assert _gap_score((0, 0), (0, 10)) == 10
    assert _gap_score((0, 0), (5, 10)) == 15
    assert _gap_score((3, 3), (3, 3)) == 0


def test_detect_singleton_marker_picks_the_smallest_singleton_colour():
    """Purpose: the DC22-style fallback goal (used ONLY when no second
    SELF-coloured region is ever seen this level -- a non-mirrored M0R0
    variant, unobserved in gold but not ruled out) must pick the smallest
    singleton-coloured region excluding SELF's own colour, exactly like
    DC22's own marker detection.
    Expected feedback: failure means a non-mirrored variant level would
    never find a goal at all, stalling the adapter in the probe phase
    permanently."""
    regions = [
        _region(7, (5, 5, 6, 6)),  # SELF, colour 7, singleton other than itself
        _region(2, (0, 0, 1, 60), size=1200),  # a big non-singleton-shared floor colour
        _region(2, (2, 0, 3, 60), size=1200),
        _region(9, (10, 10, 11, 11)),  # the smallest singleton -- the goal marker
        _region(4, (20, 20, 25, 25)),  # a bigger singleton, not the goal
    ]
    cell = _detect_singleton_marker(regions, self_color=7)
    assert cell == (10, 10)


def test_detect_singleton_marker_returns_none_when_no_candidate_exists():
    """Purpose: an empty region list (or one where every colour is either
    SELF's own or shared by >1 region) must report None, not raise or
    fabricate a marker.
    Expected feedback: failure means the adapter would crash or silently
    accept a bogus goal cell on a board this rule genuinely can't read."""
    assert _detect_singleton_marker([], self_color=7) is None
    regions = [_region(2, (0, 0, 1, 1)), _region(2, (5, 5, 6, 6))]  # colour 2 used twice, not singleton
    assert _detect_singleton_marker(regions, self_color=7) is None


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
    adapter._partner_cell = (3, 9)

    game_over_frame = SimpleNamespace(state=SimpleNamespace(name="GAME_OVER"))
    adapter.choose_action([], game_over_frame)
    assert adapter._hazards == {(3, 3): {1, 2}}
    assert adapter._dead_cells == {(3, 3)}
    assert adapter._known_blocked == {(4, 4)}
    assert adapter._tried_from == {(3, 3): {1, 2}}
    assert adapter._active_cell is None  # only the current positions reset
    assert adapter._partner_cell is None

    not_played_frame = SimpleNamespace(state=SimpleNamespace(name="NOT_PLAYED"))
    adapter.choose_action([], not_played_frame)
    assert adapter._levels_seen == -1  # forces a full _on_level_up on the next real frame


def test_on_level_up_resets_spatial_state_but_keeps_dir_sign():
    """Purpose: pin the exact carryover contract -- dir_sign (which button
    is up/down/left/right, a genuine game-wide constant), for BOTH sides,
    survives a level transition, but dir_map's CONFIRMED magnitudes do NOT
    (a level's own pixel-per-step scale is a property of that level's
    grid, measured directly to differ between levels -- 5px vs 4px -- so a
    magnitude carried over from a different level is actively wrong, not
    just stale), and every other spatial fact about the layout just left
    (hazards, dead cells, known_blocked, tried_from, the singleton-marker
    fallback goal) does not survive either, since a new level is a new
    maze.
    Expected feedback: failure means either a wrong magnitude leaks into
    the new level's routing (reproducing the measured oscillation bug) or
    the direction priors are lost and every action needs re-discovering
    from scratch every level (wasted actions)."""
    adapter = Adapter()
    adapter._dir_map = {1: (-5, 0), 2: (5, 0)}
    adapter._dir_sign = {1: (-1, 0), 2: (1, 0)}
    adapter._partner_dir_map = {1: (-5, 0), 2: (5, 0)}
    adapter._partner_dir_sign = {1: (-1, 0), 2: (1, 0)}
    adapter._hazards = {(3, 3): {1}}
    adapter._dead_cells = {(3, 3)}
    adapter._known_blocked = {(4, 4)}
    adapter._partner_known_blocked = {(4, 9)}
    adapter._tried_from = {(3, 3): {1}}
    adapter._marker_cell = (9, 9)

    grid = tuple(tuple(0 for _ in range(10)) for _ in range(10))
    adapter._on_level_up(1, grid)

    assert adapter._dir_map == {}
    assert adapter._partner_dir_map == {}
    assert adapter._dir_sign == {1: (-1, 0), 2: (1, 0)}
    assert adapter._partner_dir_sign == {1: (-1, 0), 2: (1, 0)}
    assert adapter._hazards == {}
    assert adapter._dead_cells == set()
    assert adapter._known_blocked == set()
    assert adapter._partner_known_blocked == set()
    assert adapter._tried_from == {}
    assert adapter._marker_cell is None
    assert adapter._level_start_cell is None
    assert adapter._partner_start_cell is None


def _grid(size: int, bg: int, stamps: list[tuple[int, int, int, int]]) -> tuple[tuple[int, ...], ...]:
    """A blank ``size``x``size`` grid of ``bg`` with each ``(colour, r0, c0,
    r1, c1)`` stamp painted on top."""
    g = [[bg] * size for _ in range(size)]
    for colour, r0, c0, r1, c1 in stamps:
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                g[r][c] = colour
    return tuple(tuple(row) for row in g)


def test_observe_result_prefers_the_dir_sign_matched_candidate_when_re_measuring():
    """Purpose: regression pin for the per-level dir_map bootstrap's
    disambiguation step -- when an action's magnitude is unconfirmed for
    the CURRENT level (dir_map has no entry, e.g. freshly wiped by
    _on_level_up) and more than one same-colour region falls within the
    bounded re-measurement radius, the one matching dir_sign's PRIOR
    direction (carried over from an earlier level -- the control scheme
    itself is a genuine game-wide constant, unlike the magnitude) must be
    preferred over a merely-closer candidate with the WRONG sign -- e.g. a
    mirror partner that happens to have drifted nearer than SELF's own
    true (correctly-signed) new position.
    Expected feedback: failure means a nearer wrong-sign candidate (the
    mirror partner) gets misidentified as SELF instead of SELF's own true
    position, corrupting dir_map/known_blocked exactly like the bug this
    whole bootstrap redesign was built to close."""
    self_colour = 7
    bg = 0
    ref_cell = (10, 10)
    before = _grid(30, bg, [(self_colour, 10, 10, 11, 11)])

    # "Correct" SELF position after moving UP (action 1's prior sign is
    # (-1, 0)) is (8, 10); a mirror partner of the SAME colour has drifted
    # to (11, 10) -- CLOSER to ref_cell (distance 1) than the true new
    # position (distance 2), and with the WRONG sign relative to the
    # prior.
    after = _grid(30, bg, [(self_colour, 8, 10, 9, 11), (self_colour, 11, 10, 12, 11)])

    adapter = Adapter()
    adapter._self_color = self_colour
    adapter._dir_sign = {1: (-1, 0)}
    adapter._dir_map = {}  # unconfirmed this level -- see _on_level_up
    adapter._pending_action = 1
    adapter._pending_ref_cell = ref_cell
    adapter._prev_grid = before
    adapter._level_start_grid = before  # avoid the silent-reposition branch

    adapter._observe_result(after)

    assert adapter._active_cell == (8, 10)
    assert adapter._dir_map[1] == (-2, 0)


def test_observe_result_tracks_the_partner_independently_from_self():
    """Purpose: the core joint-dynamics claim this whole redesign is built
    on -- a SINGLE action can move SELF and the PARTNER by DIFFERENT
    amounts (measured directly: horizontal actions are antisymmetric,
    vertical actions are symmetric, and either side can be independently
    blocked). _observe_result must therefore populate _partner_dir_map
    from the partner's OWN measured displacement, never assumed equal to
    or derived from _dir_map.
    Expected feedback: failure means the joint successors function would
    use a wrong (e.g. self-derived) partner delta, producing a joint
    search that doesn't match the real game -- silently wrong routing
    that would be very hard to diagnose from live smoke alone."""
    self_colour = 7
    bg = 0
    self_ref = (10, 10)
    partner_ref = (10, 30)
    before = _grid(40, bg, [(self_colour, 10, 10, 11, 11), (self_colour, 10, 30, 11, 31)])
    # SELF moves UP by 2 (an ordinary vertical shift); the PARTNER moves
    # RIGHT by 3 under the SAME action -- deliberately a DIFFERENT axis
    # and magnitude than SELF's own, so a bug that derives partner motion
    # from self's dir_map would be caught immediately.
    after = _grid(
        40,
        bg,
        [(self_colour, 8, 10, 9, 11), (self_colour, 10, 33, 11, 34)],
    )

    adapter = Adapter()
    adapter._self_color = self_colour
    adapter._active_cell = self_ref
    adapter._partner_cell = partner_ref
    adapter._pending_action = 1
    adapter._pending_ref_cell = self_ref
    adapter._pending_partner_ref_cell = partner_ref
    adapter._prev_grid = before
    adapter._level_start_grid = before

    adapter._observe_result(after)

    assert adapter._active_cell == (8, 10)
    assert adapter._dir_map[1] == (-2, 0)
    assert adapter._partner_cell == (10, 33)
    assert adapter._partner_dir_map[1] == (0, 3)


def test_observe_result_reports_partner_none_when_it_merges_with_self():
    """Purpose: when the partner's own region is no longer separately
    visible (merged with SELF, or genuinely gone), _observe_result must
    set _partner_cell to None rather than fabricating a position from an
    unrelated region -- _decide reads this to idle/probe safely and let
    the live engine's own WIN signal decide, instead of routing toward a
    bogus target (the exact class of bug the first backport's goal-jump
    fix closed for the old single-target design; this pins the equivalent
    contract for the joint design).
    Expected feedback: failure means the joint planner could compute a
    _route_joint call with a stale or wrong partner cell after a merge,
    producing nonsensical joint-state search results."""
    self_colour = 7
    bg = 0
    self_ref = (10, 10)
    partner_ref = (10, 14)
    before = _grid(30, bg, [(self_colour, 10, 10, 11, 11), (self_colour, 10, 14, 11, 15)])
    # Only ONE colour-7 region after the action -- SELF and the partner
    # merged into a single connected component.
    after = _grid(30, bg, [(self_colour, 10, 10, 11, 15)])

    adapter = Adapter()
    adapter._self_color = self_colour
    adapter._active_cell = self_ref
    adapter._partner_cell = partner_ref
    adapter._dir_map = {4: (0, 2)}
    adapter._partner_dir_map = {4: (0, -2)}
    adapter._pending_action = 4
    adapter._pending_ref_cell = self_ref
    adapter._pending_partner_ref_cell = partner_ref
    adapter._prev_grid = before
    adapter._level_start_grid = before

    adapter._observe_result(after)

    assert adapter._partner_cell is None


def test_joint_successors_applies_independent_per_side_deltas_and_blocking():
    """Purpose: _joint_successors is the closure kernels.configuration_path
    searches over -- it must apply EACH side's own measured delta
    independently, and respect EACH side's own known_blocked set
    independently (the core "each side is independently blockable"
    finding). A destination blocked for the partner must not affect
    SELF's own move under the identical action, and vice versa.
    Expected feedback: failure means the joint search doesn't match
    reality (e.g. one side's wall silently freezes both pieces, or a
    block is ignored), producing a plan that fails to reproduce live."""
    adapter = Adapter()
    adapter._dir_map = {1: (-1, 0), 4: (0, 1)}
    adapter._partner_dir_map = {1: (-1, 0), 4: (0, -1)}
    # The partner's destination under action 1 is blocked; SELF's is not.
    adapter._partner_known_blocked = {(4, 20)}

    successors = adapter._joint_successors([1, 4])
    results = dict(successors(((5, 20), (5, 20))))

    # Action 1 (vertical, symmetric): SELF moves to (4, 20); the partner's
    # predicted (4, 20) is blocked, so it stays at (5, 20).
    assert results[1] == ((4, 20), (5, 20))
    # Action 4 (horizontal, antisymmetric): SELF moves right, partner
    # moves left -- both unblocked.
    assert results[4] == ((5, 21), (5, 19))


def test_rematch_radius_is_peer_relative_not_a_fixed_constant():
    """Purpose: pin the exact bound formula -- before any peer magnitude
    is confirmed, a conservative absolute cap (8, comfortably above both
    measured per-level scales of 4px/5px); once >=1 peer exists, 2x the
    MEDIAN confirmed magnitude, never a fixed constant regardless of scale.
    Expected feedback: failure means the bound doesn't actually track
    peer evidence, reopening the fixed-radius outlier bug this whole fix
    closes."""
    assert _rematch_radius({}) == 8
    assert _rematch_radius({1: (-4, 0)}) == 8  # 2x4
    assert _rematch_radius({1: (-4, 0), 2: (4, 0), 4: (0, 4)}) == 8  # 2x median(4,4,4)
    assert _rematch_radius({1: (-10, 0)}) == 20  # scales up for a genuinely larger-stepping level


def test_observe_piece_rejects_a_magnitude_outlier_against_confirmed_peers():
    """Purpose: regression pin for the exact live bug found and reported
    to the team -- dir_map[3] measured as (0, -20) while three peer
    actions all correctly measured magnitude 4, because the OLD fixed-20px
    radius accepted a spurious candidate sitting exactly at its own
    boundary. Once >=1 peer magnitude is confirmed for this piece/level, a
    candidate farther than 2x the peers' median magnitude must be REJECTED
    even though a generic wide radius would have accepted it, leaving the
    TRUE near candidate as the only surviving one.
    Expected feedback: failure means the peer-relative bound isn't
    actually applied, reproducing the exact corrupted-magnitude bug that
    poisoned _joint_successors' own move set live."""
    adapter = Adapter()
    ref_cell = (20, 20)
    dir_map = {1: (-4, 0), 2: (4, 0), 4: (0, 4)}  # 3 peers, all magnitude 4
    dir_sign: dict[int, tuple[int, int]] = {}
    tried_from: dict[tuple[int, int], set[int]] = {}
    known_blocked: set[tuple[int, int]] = set()
    true_near = _region(9, (20, 16, 21, 17))  # distance 4 from ref_cell -- the real position
    outlier = _region(9, (20, 40, 21, 41))  # distance 20 -- the spurious match, measured live
    same_colour_cur = [true_near, outlier]

    new_cell = adapter._observe_piece(
        ref_cell, 3, same_colour_cur, dir_map, dir_sign, tried_from, known_blocked, exclude_cell=None
    )

    assert new_cell == (20, 16)
    assert dir_map[3] == (0, -4)


def test_observe_piece_leaves_the_action_unconfirmed_when_only_an_outlier_exists():
    """Purpose: the companion case -- when the ONLY candidate within a
    generic wide radius is an outlier relative to confirmed peers, the
    action must stay UNCONFIRMED (no dir_map entry at all) rather than
    ever storing the bad magnitude -- the "never store a suspect
    magnitude" contract this fix exists to guarantee.
    Expected feedback: failure means a corrupted magnitude gets stored
    anyway, silently poisoning every plan built from it afterward."""
    adapter = Adapter()
    ref_cell = (20, 20)
    dir_map = {1: (-4, 0), 2: (4, 0), 4: (0, 4)}
    dir_sign: dict[int, tuple[int, int]] = {}
    tried_from: dict[tuple[int, int], set[int]] = {}
    known_blocked: set[tuple[int, int]] = set()
    outlier = _region(9, (20, 40, 21, 41))  # distance 20 -- the ONLY candidate
    same_colour_cur = [outlier]

    new_cell = adapter._observe_piece(
        ref_cell, 3, same_colour_cur, dir_map, dir_sign, tried_from, known_blocked, exclude_cell=None
    )

    assert new_cell is None
    assert 3 not in dir_map
    assert 3 in tried_from.get(ref_cell, set())
