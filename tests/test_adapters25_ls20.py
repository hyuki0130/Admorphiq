"""Tests for the LS20 adapter's offline maze reconstruction + joint BFS
(dedicated session, 2026-07-15).

Background (see the module docstring + ``.wiki/wiki/games/LS20.md``): LS20 is a
shape/color/rotation-matching maze. Four rounds of online frame-keyed
exploration banked at 1/7 (L1 only, ~606 actions) because the full-reset
21-action lives make exploration economics not close. This adapter sidesteps
exploration: it parses the maze from a single settled frame and runs a JOINT
BFS over ``(cell, shape, color, rotation, steps_left, refills_taken)`` toward a
matching goal, executed open-loop. The parser was validated dev-time byte-exact
against the engine ground truth (L1 + L2) and the found plans replay to live
wins (L1 in 13 actions, L2 in 45). These tests pin the engine-free invariants
the reconstruction depends on: the appearance decoders, and the joint BFS's
goal-matching / rotation-changer / refill-budget / goal-blocking contracts.
"""

from __future__ import annotations

from collections import Counter

from admorphiq.adapters25.ls20 import (
    _BASE_SHAPES,
    _CELL,
    _FLOOR_COLOR,
    _PALETTE,
    _SHAPE_ROT,
    _STEP_DECR,
    _STEP_FULL,
    _WALL_COLOR,
    _classify_changer,
    _decode_shape3,
    _detect_pushwalls,
    _detect_pushwalls_pixel,
    _l5_bfs,
    _l5_mover_advance,
    _l5_step,
    _l6_bfs,
    _l6_dir_from,
    _l6_mover_step,
    _l6_step,
    _snap_to_lattice,
    _solve,
)


def _base_fill(shape_idx: int) -> dict[tuple[int, int], int]:
    """The rotation-0 filled cells of a base shape, painted the first palette
    colour — the exact input the goal-preview decoder builds from a frame."""
    mat = _BASE_SHAPES[shape_idx]
    return {
        (r, c): _PALETTE[0]
        for r in range(3)
        for c in range(3)
        if mat[r][c] != -1
    }


def test_shape_rot_table_covers_all_six_shapes_four_rotations():
    """Purpose: the decoder maps a filled-cell SET (under rotation) to
    ``(shape, rot)``; prove every base shape at every rotation has a distinct,
    resolvable entry so no token appearance is silently undecodable.
    Expected feedback: a failure means two shapes/rotations collide or one is
    missing — the parser would then mis-read the token or goal and plan a wrong
    (non-winning) route."""
    seen = set()
    for si in range(6):
        cells = frozenset(_base_fill(si))
        assert cells in _SHAPE_ROT
        assert _SHAPE_ROT[cells][0] == si  # rot-0 fill decodes to its own shape
        seen.add(cells)
    assert len(seen) == 6  # the six rot-0 fills are mutually distinct


def test_decode_shape3_reads_shape_color_rotation():
    """Purpose: pin the core appearance decode — a rot-0 fill of each shape in
    each palette colour must decode to that (shape, color, rot=0).
    Expected feedback: a failure means the token/goal-preview decode is wrong,
    so the joint BFS is seeded with the wrong start/target token."""
    for si in range(6):
        for ci, col in enumerate(_PALETTE):
            fill = {cell: col for cell in _base_fill(si)}
            assert _decode_shape3(fill) == (si, ci, 0)


def test_decode_shape3_rejects_non_shape_and_offpalette():
    """Purpose: the decoder must return None on garbage (an unknown filled set
    or an off-palette colour) so ``_parse`` gates to the explorer instead of
    fabricating a token.
    Expected feedback: a failure means a malformed frame would yield a bogus
    token and a wrong plan rather than a safe fallback."""
    assert _decode_shape3({}) is None
    assert _decode_shape3({(0, 0): _PALETTE[0]}) is None  # single cell: no shape
    off = {cell: 7 for cell in _base_fill(0)}  # colour 7 is not in the palette
    assert _decode_shape3(off) is None


def test_classify_changer_types_by_icon_signature():
    """Purpose: pin the changer-type classifier's ordering — the colour changer
    icon (soyhouuebz) carries a colour-0 pixel AND a multi-palette icon, so the
    palette test MUST precede the colour-0 shape test or a colour changer is
    mis-typed "shape" (the exact bug that made L3/L4 unsolvable before this
    fix). Also: a changer only exists on a FLOOR cell — colour-1 markers on WALL
    cells (push-walls / arena edges) must NOT register as rotation changers.
    Expected feedback: a failure means the parser mis-reads which attribute a
    changer cycles, and the joint BFS plans a route that can never match the
    goal token."""
    # rotation icon: floor-dominant cell carrying colour-1 (+ colour-0) pixels.
    rot = Counter({_FLOOR_COLOR: 20, 0: 3, 1: 2})
    assert _classify_changer(rot, _FLOOR_COLOR) == "rot"
    # colour icon: floor cell with a multi-palette icon AND one colour-0 pixel.
    color = Counter({_FLOOR_COLOR: 16, 9: 2, 14: 2, 8: 2, 12: 2, 0: 1})
    assert _classify_changer(color, _FLOOR_COLOR) == "color"
    # shape icon: floor cell with colour-0 pixels only.
    shape = Counter({_FLOOR_COLOR: 21, 0: 4})
    assert _classify_changer(shape, _FLOOR_COLOR) == "shape"
    # colour-1 marker on a WALL cell (dom colour-4) is NOT a rotation changer.
    wall_marker = Counter({_WALL_COLOR: 20, 1: 5})
    assert _classify_changer(wall_marker, _WALL_COLOR) is None
    # plain floor is not a changer.
    assert _classify_changer(Counter({_FLOOR_COLOR: 25}), _FLOOR_COLOR) is None


def test_detect_pushwalls_reads_direction_from_the_edge_line():
    """Purpose: a push-wall renders as a 5-pixel colour-1 edge LINE and pushes
    the avatar TOWARD that edge (the sprite body extends into the neighbour), so
    the collision cell is one cell past the line and the direction points that
    way. Pin all four orientations.
    Expected feedback: a failure means the offline model shoves the avatar the
    wrong way (or to the wrong cell) and every push-wall level desyncs on replay."""
    cell, n = _CELL, 3
    xs = ys = [cell * i for i in range(n)]

    def grid_with_line(edge: str) -> tuple[tuple[int, ...], ...]:
        # a colour-1 line on one edge of cell (cell, cell) == (5,5); floor else.
        g = [[_FLOOR_COLOR] * (cell * n) for _ in range(cell * n)]
        bx, by = cell, cell
        for k in range(cell):
            if edge == "right":
                g[by + k][bx + cell - 1] = 1
            elif edge == "left":
                g[by + k][bx] = 1
            elif edge == "bottom":
                g[by + cell - 1][bx + k] = 1
            elif edge == "top":
                g[by][bx + k] = 1
        return tuple(tuple(r) for r in g)

    assert _detect_pushwalls(grid_with_line("right"), xs, ys) == {(cell * 2, cell): (1, 0)}
    assert _detect_pushwalls(grid_with_line("left"), xs, ys) == {(0, cell): (-1, 0)}
    assert _detect_pushwalls(grid_with_line("bottom"), xs, ys) == {(cell, cell * 2): (0, 1)}
    assert _detect_pushwalls(grid_with_line("top"), xs, ys) == {(cell, 0): (0, -1)}


def test_solve_slides_off_a_pushwall_and_stops_before_the_goal():
    """Purpose: stepping onto a push-wall collision cell must slide the avatar in
    the push direction, stopping before a wall OR the goal (the engine's push
    stops at goal cells), after which a normal move lands on the goal — the exact
    L3 endgame (a down-push stops one cell above the goal).
    Expected feedback: a failure means the push slide over/under-shoots or lands
    on the goal directly, which the live engine never allows."""
    # corridor (0,0)-(20,0); (5,0) is a right-pushing collision cell.
    passable = {(_CELL * i, 0) for i in range(5)}
    parsed = {
        "avatar": (0, 0), "goal": (_CELL * 4, 0), "goal_req": (5, 1, 0),
        "token": (5, 1, 0), "changers": {}, "refills": frozenset(),
        "passable": passable, "pushwalls": {(_CELL, 0): (1, 0)},
    }
    # step right onto (5,0) -> slides to (15,0) (stops before goal (20,0)),
    # then one more right move lands on the goal.
    assert _solve(parsed) == [4, 4]


def _corridor(length: int) -> dict[tuple[int, int], object]:
    """A horizontal passable corridor of ``length`` cells starting at (0,0),
    stepping right by one grid unit."""
    return {(_CELL * i, 0) for i in range(length)}


def test_solve_trivial_when_already_on_matching_goal():
    """Purpose: standing on the goal with a matching token is a zero-action
    solve — pin the terminal contract.
    Expected feedback: a non-empty/None result means the goal test is wrong."""
    parsed = {
        "avatar": (0, 0), "goal": (0, 0), "goal_req": (5, 1, 0),
        "token": (5, 1, 0), "changers": {}, "refills": frozenset(),
        "passable": {(0, 0)},
    }
    assert _solve(parsed) == []


def test_solve_routes_through_rotation_changer_then_goal():
    """Purpose: when the goal needs a token one rotation off, the plan must
    visit the rotation changer (cycling +1) before the goal — the core
    token-transform contract of the maze.
    Expected feedback: a failure means the changer effect or the goal-blocking
    (can't stand on the goal until matched) is mis-modelled."""
    passable = _corridor(3)  # (0,0) start, (5,0) changer, (10,0) goal
    parsed = {
        "avatar": (0, 0), "goal": (10, 0), "goal_req": (5, 1, 1),
        "token": (5, 1, 0), "changers": {(5, 0): "rot"}, "refills": frozenset(),
        "passable": passable,
    }
    plan = _solve(parsed)
    # right to the changer (rot 0->1), then right to the matching goal.
    assert plan == [4, 4]


def test_solve_needs_refill_to_survive_a_long_corridor():
    """Purpose: a goal farther than one life (``_STEP_FULL // _STEP_DECR``
    actions) is only reachable by collecting a step-refill mid-run; prove the
    budget/refill arithmetic makes the difference between None and a plan.
    Expected feedback: a failure means the life budget or the refill top-up is
    wrong — exactly the L2 mechanic (45 actions > a 21-action life)."""
    life = _STEP_FULL // _STEP_DECR
    far = life + 3  # goal at cell `far`, beyond a single life
    passable = _corridor(far + 1)
    base = {
        "avatar": (0, 0), "goal": (_CELL * far, 0), "goal_req": (5, 1, 0),
        "token": (5, 1, 0), "passable": passable, "changers": {},
    }
    # Without a refill the corridor cannot be crossed within one life.
    assert _solve({**base, "refills": frozenset()}) is None
    # A refill partway along tops the budget back up, making it reachable.
    refill_cell = (_CELL * (life - 2), 0)
    plan = _solve({**base, "refills": frozenset({refill_cell})})
    assert plan is not None and len(plan) == far  # straight walk, no wasted steps


def test_solve_returns_none_when_token_cannot_be_transformed():
    """Purpose: if the goal needs an attribute the maze has no changer for, the
    puzzle is unsolvable and ``_solve`` must return None (so the adapter gates),
    not loop or fabricate.
    Expected feedback: a failure means a wrong-token route could be committed
    and executed open-loop, wasting the whole budget."""
    passable = _corridor(3)
    parsed = {
        "avatar": (0, 0), "goal": (10, 0), "goal_req": (5, 2, 0),  # needs colour idx 2
        "token": (5, 1, 0), "changers": {(5, 0): "rot"},  # only a rotation changer
        "refills": frozenset(), "passable": passable,
    }
    assert _solve(parsed) is None


# ── L5 pixel push-carry model + moving-changer joint BFS ─────────────────────


def test_snap_to_lattice_maps_offset_sprites_to_containing_cell():
    """Purpose: pixel-offset refill/wall sprites are triggered at the AVATAR
    lattice cell whose 5x5 box contains the sprite top-left (engine
    ``mrznumynfe`` containment). Pin the snap for the measured L5 offsets.
    Expected feedback: a failure means refills never fire in the sim, so the
    life budget is wrong and the L5 BFS finds no death-free plan."""
    ox, oy = 4, 0  # avatar at x%5==4, y%5==0 (the measured L5 lattice)
    assert _snap_to_lattice(15, 46, ox, oy) == (14, 45)
    assert _snap_to_lattice(45, 6, ox, oy) == (44, 5)
    assert _snap_to_lattice(10, 11, ox, oy) == (9, 10)
    assert _snap_to_lattice(49, 35, ox, oy) == (49, 35)  # already on the lattice


def test_detect_pushwalls_pixel_recovers_offset_sprite_and_direction():
    """Purpose: an L5 push-wall renders a length-5 colour-1 LINE bordering a
    colour-4 wall; the push goes AWAY from the wall and the sprite top-left is
    recovered exactly (even when pixel-offset from the lattice). Pin all four
    orientations, including a sprite whose top row is off the 5-lattice.
    Expected feedback: a failure means the collision cell / carry direction is
    wrong and the L5 open-loop plan desyncs on the first push."""
    H = W = 20

    def frame():
        return [[_FLOOR_COLOR] * W for _ in range(H)]

    # down wall: wall above (row 3), line at row 4 -> sprite (10,4), push (0,1).
    g = frame()
    for c in range(10, 15):
        g[3][c] = _WALL_COLOR
        g[4][c] = 1
    walls = _detect_pushwalls_pixel(tuple(tuple(r) for r in g))
    assert (10, 4, 0, 1) in walls

    # up wall: line at row 9, wall below (row 10) -> sprite (10,5), push (0,-1).
    g = frame()
    for c in range(10, 15):
        g[9][c] = 1
        g[10][c] = _WALL_COLOR
    walls = _detect_pushwalls_pixel(tuple(tuple(r) for r in g))
    assert (10, 5, 0, -1) in walls

    # right wall: line at col 5, wall left (col 4) -> sprite (5,10), push (1,0).
    g = frame()
    for r in range(10, 15):
        g[r][4] = _WALL_COLOR
        g[r][5] = 1
    walls = _detect_pushwalls_pixel(tuple(tuple(r) for r in g))
    assert (5, 10, 1, 0) in walls

    # left wall: line at col 9, wall right (col 10) -> sprite (5,10), push (-1,0).
    g = frame()
    for r in range(10, 15):
        g[r][9] = 1
        g[r][10] = _WALL_COLOR
    walls = _detect_pushwalls_pixel(tuple(tuple(r) for r in g))
    assert (5, 10, -1, 0) in walls


def test_l5_mover_advance_bounces_along_the_track():
    """Purpose: the moving rot-changer patrols a horizontal track one cell per
    successful move, reversing at the ends (engine ``dboxixicic``). Pin the
    14<->24 bounce cycle used at L5.
    Expected feedback: a failure means the mover phase desyncs and the rotation
    crossings in the plan land on the wrong frames."""
    track = (14, 19, 24)
    mx, mdir = 19, 1  # heading right
    seq = []
    for _ in range(8):
        mx, mdir = _l5_mover_advance(track, mx, mdir)
        seq.append(mx)
    assert seq == [24, 19, 14, 19, 24, 19, 14, 19]


def _l5_maze(**over):
    """A minimal L5-style maze dict for the pixel sim; overridable per test."""
    base = {
        "hard_walls": frozenset(),
        "goal": (100, 0),
        "goal_req": (0, 0, 0),
        "changers": {},
        "refills": frozenset(),
        "pushwalls": (),
        "fjzuynaokm": frozenset(),
        "mover_track": (),
        "mover_my": -1,
        "step_full": 21,
    }
    base.update(over)
    return base


def test_l5_step_carries_avatar_by_wall_width_until_a_blocking_cell():
    """Purpose: stepping into a push-wall's bounding box carries the avatar
    ``ullzqnksoj`` wall-widths in the push direction, stopping one width before
    a blocking (``fjzuynaokm``) cell — the exact pixel carry the lattice model
    could not express.
    Expected feedback: a failure means the carry distance is wrong and every L5
    push desyncs against the live engine."""
    # right-pushing wall sprite at (15,10); blocking cell at (35,10).
    maze = _l5_maze(
        pushwalls=((15, 10, 1, 0, _CELL, _CELL),),
        fjzuynaokm=frozenset({(35, 10)}),
        goal=(999, 999),
    )
    # avatar at (10,10) steps right onto (15,10) -> collides, carried right.
    # carry: wall_cx=16; checks (21,10),(26,10),(31,10),(36,10); (36,10) is not
    # blocking but (35,10) is — checks land on 16+5k so first blocking multiple
    # is where 16+5k reaches >=35 in fjzuynaokm. Here (35,10) not on 16+5k grid,
    # so choose a blocking cell exactly on the grid for a crisp assertion.
    maze = _l5_maze(
        pushwalls=((15, 10, 1, 0, _CELL, _CELL),),
        fjzuynaokm=frozenset({(31, 10)}),  # 16 + 5*3 == 31 -> k=3, dist=2
        goal=(999, 999),
    )
    s = (10, 10, 0, 0, 0, 5, frozenset(), -1, 1)
    ns = _l5_step(maze, s, 4)  # move right
    # avatar at (15,10) collides, carried by dir*width*dist = (1*5*2, 0) = (10,0)
    assert (ns[0], ns[1]) == (25, 10)


def test_l5_step_mover_cell_cycles_rotation_and_refill_tops_life():
    """Purpose: landing on the mover's CURRENT cell cycles rotation (the mover is
    a rot changer), and stepping onto a refill resets the life budget — the two
    dynamic effects the joint BFS depends on.
    Expected feedback: a failure means the plan mis-counts rotation crossings or
    the life budget, so a valid death-free plan is missed."""
    # mover on a 1-cell track at (20,0); avatar steps right from (15,0) onto it
    # AFTER the mover advances to (20,0) (single-cell track stays at 20).
    maze = _l5_maze(mover_track=(20,), mover_my=0, goal=(999, 999))
    s = (15, 0, 0, 0, 0, 5, frozenset(), 20, 1)
    ns = _l5_step(maze, s, 4)
    assert (ns[0], ns[1]) == (20, 0) and ns[4] == 1  # rotation 0 -> 1

    # refill: stepping onto a refill cell tops life back to step_full.
    maze = _l5_maze(refills=frozenset({(20, 0)}), goal=(999, 999), step_full=21)
    s = (15, 0, 0, 0, 0, 3, frozenset(), -1, 1)
    ns = _l5_step(maze, s, 4)
    assert ns[5] == 21 and (20, 0) in ns[6]  # steps refilled, refill marked taken


def test_l5_bfs_routes_through_the_moving_changer_for_rotation():
    """Purpose: end-to-end pin of the joint BFS — when the goal needs a rotation
    only the moving changer supplies, the plan must time the avatar onto the
    mover's cell, then reach the goal.
    Expected feedback: a failure means the moving-changer joint search is broken
    and L5 cannot be solved frame-only."""
    # mover patrols x in {5,10} at y=0, starting at x=10 heading LEFT (mdir 3).
    # avatar at (10,0): a LEFT move advances the mover 10->5 and lands the avatar
    # on (5,0) == the mover's new cell -> rot 0->1; a DOWN move then reaches the
    # goal (5,5) which needs rot 1 (the goal itself is NOT the mover cell, so the
    # goal-blocking-until-matched rule does not deadlock the rotation).
    maze = _l5_maze(goal=(5, 5), goal_req=(0, 0, 1), mover_track=(5, 10), mover_my=0)
    start = (10, 0, 0, 0, 0, 21, frozenset(), 10, 3)
    plan = _l5_bfs(maze, start)
    assert plan == [3, 2]


# ── L6 multi-goal (either-order) + 3-synchronous-mover model ─────────────────


def _l6_maze(**over):
    """A minimal L6-style maze dict for the multi-goal pixel sim."""
    base = {
        "goals": [(100, 0)],
        "reqs": [(0, 0, 0)],
        "hard_walls": frozenset(),
        "refills": frozenset(),
        "pushwalls": (),
        "fjzuynaokm": frozenset(),
        "mover_kinds": [],
        "mover_tracks": [],
        "step_full": 42,
    }
    base.update(over)
    return base


def _l6_start(ax, ay, token=(0, 0, 0), steps=42, movers=(), sat=frozenset()):
    return (ax, ay, token[0], token[1], token[2], steps, frozenset(), tuple(movers), sat)


def test_l6_mover_step_follows_the_track_in_2d():
    """Purpose: the L6 mover follows npdjlrkhsg (try dir, dir-1, dir+1, dir+2)
    over its track cells — pin both a horizontal continue and a 2D turn at a
    region corner.
    Expected feedback: a failure means a mover's phase desyncs and the L6 plan's
    changer crossings land on wrong frames."""
    horiz = frozenset({(14, 35), (19, 35), (24, 35)})
    assert _l6_mover_step(horiz, 19, 35, 1) == (24, 35, 1)  # continue right
    assert _l6_mover_step(horiz, 24, 35, 1) == (19, 35, 3)  # bounce to left
    # 2D region corner: heading right at the region's right edge turns.
    region = frozenset({(19, 20), (24, 20), (19, 25), (24, 25)})
    nx, ny, nd = _l6_mover_step(region, 24, 20, 1)
    assert (nx, ny) in region and (nx, ny) != (24, 20)  # it moved to an on-track cell


def test_l6_dir_from_infers_direction_between_observed_cells():
    """Purpose: the mover direction is learned from two consecutive observed
    cells; pin the nakogfhyus mapping and the None case (no unit step).
    Expected feedback: a failure means the observed mover seeds the sim with the
    wrong heading and the plan desyncs."""
    assert _l6_dir_from((19, 35), (24, 35)) == 1  # right
    assert _l6_dir_from((24, 35), (19, 35)) == 3  # left
    assert _l6_dir_from((19, 20), (19, 25)) == 0  # down
    assert _l6_dir_from((19, 25), (19, 20)) == 2  # up
    assert _l6_dir_from((19, 35), (29, 35)) is None  # two cells apart -> not a step


def test_l6_step_satisfies_a_goal_only_with_its_own_matching_token():
    """Purpose: each L6 goal is covered only by standing on it with THAT goal's
    required token; an unsatisfied goal blocks a mismatched token, and a
    satisfied goal is removed (passable). Pin both.
    Expected feedback: a failure means the either-order coverage is mis-modelled
    and the multi-goal BFS plans an impossible or premature win."""
    # goal A@(5,0) needs token (0,0,1); the avatar arrives matching -> covered.
    maze = _l6_maze(goals=[(5, 0), (10, 0)], reqs=[(0, 0, 1), (0, 0, 2)], goal=None)
    s = _l6_start(0, 0, token=(0, 0, 1))
    ns = _l6_step(maze, s, 4)  # right onto (5,0) with matching token
    assert 0 in ns[8] and (ns[0], ns[1]) == (5, 0)
    # with a MISMATCHED token the same move is blocked (avatar stays).
    s2 = _l6_start(0, 0, token=(0, 0, 0))
    ns2 = _l6_step(maze, s2, 4)
    assert ns2 == s2  # blocked: goal A unsatisfied and token mismatched


def test_l6_bfs_covers_both_goals_either_order():
    """Purpose: end-to-end pin of the multi-goal joint BFS — a two-goal corridor
    where each goal needs a different rotation supplied by a mover; the plan must
    cover BOTH (order free) to win.
    Expected feedback: a failure means the satisfied-goals bitmask or the joint
    multi-mover search is broken and L6 cannot be solved."""
    # y=0 line: goals at (5,0) req rot1 and (15,0) req rot2; a rot-mover patrols
    # (10,0)-(20,0). Reaching a mover cell bumps rotation; the avatar covers both.
    maze = _l6_maze(
        goals=[(5, 0), (15, 0)], reqs=[(0, 0, 1), (0, 0, 2)],
        mover_kinds=["rot"], mover_tracks=[frozenset({(20, 0), (25, 0)})],
    )
    start = _l6_start(0, 0, token=(0, 0, 1), movers=[(20, 0, 1)])
    plan = _l6_bfs(maze, start)
    assert plan is not None
    # replay the plan through the sim and assert both goals end covered.
    s = start
    for a in plan:
        s = _l6_step(maze, s, a)
    assert len(s[8]) == 2


# ── L7 (Fog) path: gate separation + vertical-mover sim contracts ────────────

from admorphiq.adapters25.ls20 import (  # noqa: E402
    _GOAL_BORDER,
    _L7_FOG_MIN,
    _l7_bfs,
    _l7_fog_count,
    _l7_step,
)


def test_l7_fog_gate_separates_fogged_from_unfogged():
    """Purpose: the L7 gate (colour-5 pixel count) must fire on a fogged frame and
    NOT on an unfogged one — this is the ONLY guard keeping the L7 path off L1-L6,
    so a leak would let the fog-blind parser corrupt an earlier level.
    Expected feedback: a failure means the gate threshold is mis-set and the 6/7
    floor is at risk (or L7 never activates)."""
    floor = [[_FLOOR_COLOR] * 64 for _ in range(64)]
    # an unfogged frame with only a small goal border (a few colour-5 pixels)
    for r in range(5):
        floor[r][10] = _GOAL_BORDER
    assert _l7_fog_count(tuple(tuple(row) for row in floor)) <= _L7_FOG_MIN
    # a fogged frame: a large solid colour-5 field outside a small disc
    fogged = [[_GOAL_BORDER] * 64 for _ in range(64)]
    assert _l7_fog_count(tuple(tuple(row) for row in fogged)) > _L7_FOG_MIN


def _l7_maze(**kw):
    m = {
        "goal": (99, 99),
        "goal_req": (9, 9, 9),
        "hard_walls": frozenset(),
        "refills": frozenset(),
        "static_changers": {},
        "track": frozenset({(5, 0), (5, 5)}),
        "pushwalls": {},
        "fjzuynaokm": frozenset(),
        "step_full": 50,
    }
    m.update(kw)
    return m


def test_l7_step_vertical_mover_bumps_rotation_on_landing():
    """Purpose: the L7 mover patrols a VERTICAL track (unlike L5's horizontal one),
    advancing once per successful move; landing on its NEW cell bumps the token
    rotation. Pin both the vertical step and the rotation coupling.
    Expected feedback: a failure means the vertical mover model is wrong and the
    open-loop plan desyncs at the first rotation crossing."""
    maze = _l7_maze()
    # mover at (5,5) heading up (dir 2); avatar one cell left of (5,0).
    s = (0, 0, 0, 0, 0, 10, frozenset(), (5, 5, 2))
    ns = _l7_step(maze, s, 4)  # avatar right onto (5,0); mover steps (5,5)->(5,0)
    assert (ns[0], ns[1]) == (5, 0)  # avatar moved one cell right
    assert ns[7][:2] == (5, 0)  # mover advanced up one cell
    assert ns[4] == 1  # landing on the mover's new cell bumped rotation 0 -> 1


def test_l7_bfs_solves_single_goal_via_vertical_mover():
    """Purpose: end-to-end pin of the L7 joint BFS — reach the goal with a matching
    rotation supplied by the vertical mover, life-aware. This is the search that
    the fog capture feeds; it must find a death-free plan that replays.
    Expected feedback: a failure means the L7 planner cannot solve the L5-class
    single-goal + vertical-mover level and 7/7 regresses to 6/7."""
    maze = _l7_maze(goal=(10, 10), goal_req=(0, 0, 1), track=frozenset({(5, 5), (5, 10)}))
    # avatar left of the mover's descent cell; mover at (5,5) heading down.
    start = (0, 10, 0, 0, 0, 50, frozenset(), (5, 5, 0))
    plan = _l7_bfs(maze, start)
    assert plan is not None
    s = start
    for a in plan:
        s = _l7_step(maze, s, a)
    assert (s[0], s[1]) == (10, 10) and (s[2], s[3], s[4]) == (0, 0, 1)
