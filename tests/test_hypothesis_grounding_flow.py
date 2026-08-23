"""R98 step (iii) tests: flow-family grounding — animation-based state recovery.

Pins the round's pre-declared dominant risk. The harness must earn its slots from
observation alone, and must do so without falling into the traps this family
actually contains: an edge-pinned status strip that breaks the cell grid, a piece
that never emits a selection event because it starts pre-selected, a status band
that oscillates during a failure animation and merges with the real targets under
4-connectivity, and a layer stack whose tail belongs to a different board.

Synthetic frames only — no engine, no game ids, no colour constants.
"""

from __future__ import annotations

from admorphiq.hypothesis_select.grounding_flow import UNKNOWN, FlowGrounding, _infer_scale

SCALE = 2
N = 8
BG = 0


def _frame(cells: dict[tuple[int, int], int], strip: int | None = None) -> list[list[int]]:
    """An N-cell board rendered at SCALE pixels per cell, optionally with a
    one-pixel status strip painted across the top row."""
    px = N * SCALE
    grid = [[BG] * px for _ in range(px)]
    for (r, c), v in cells.items():
        for y in range(r * SCALE, r * SCALE + SCALE):
            for x in range(c * SCALE, c * SCALE + SCALE):
                grid[y][x] = v
    if strip is not None:
        grid[0] = [strip] * px
    return grid


def _bar(row: int, cols: range, colour: int) -> dict[tuple[int, int], int]:
    return {(row, c): colour for c in cols}


def test_scale_inference_tolerates_an_edge_strip_but_not_interior_noise():
    """Purpose: a status bar drawn over the top pixel row is a rendering overlay,
    not board structure, so it must not defeat scale inference — while genuine
    interior non-uniformity still must, because there the candidate scale is wrong.

    Expected feedback: pass proves the harness can read boards whose HUD breaks the
    cell grid (measured live: this alone reduced every downstream slot to UNKNOWN).
    Fail means grounding silently mis-scales and every cell coordinate is wrong."""
    clean = _frame(_bar(3, range(2, 5), 7))
    assert _infer_scale(clean) == SCALE

    striped = _frame(_bar(3, range(2, 5), 7), strip=9)
    assert _infer_scale(striped) == SCALE

    noisy = _frame(_bar(3, range(2, 5), 7))
    noisy[7][7] = 5  # interior, mid-cell
    assert _infer_scale(noisy) != SCALE


def test_translation_is_attributed_without_any_selection_event():
    """Purpose: on a board whose single piece is pre-selected, no click produces a
    frame change, so there is no selection event to observe. Coherent movement is
    the strong positive and must stand on its own.

    Expected feedback: pass proves delta acquisition does not depend on a selection
    the level cannot show. Fail means grounding returns UNKNOWN on exactly the
    criterion-level board."""
    g = FlowGrounding()
    g.observe(0, None, [_frame(_bar(3, range(2, 5), 7))])
    g.observe(4, None, [_frame(_bar(3, range(3, 6), 7))])
    g.observe(4, None, [_frame(_bar(3, range(4, 7), 7))])

    tracked = g.tracked_region()
    assert tracked is not UNKNOWN
    assert tracked.value == ((3, 4), (3, 5), (3, 6))
    deltas = g.piece_deltas()
    assert deltas is UNKNOWN  # family-gated until a scripted consequence is seen


def test_a_bare_noop_is_never_a_constraint_but_a_contrast_is():
    """Purpose: the asymmetric-mobility rule. Failure to move is weak evidence and
    must stay unattributed; only a contrast — the same action confirmed to displace
    the piece elsewhere, producing nothing here — licenses a blocked claim.

    Expected feedback: pass proves grounding cannot invent a wall from a dropped
    input or a settle frame. Fail means constraints get fabricated from no-ops."""
    g = FlowGrounding()
    g.observe(0, None, [_frame(_bar(3, range(2, 5), 7))])
    g.observe(4, None, [_frame(_bar(3, range(2, 5), 7))])  # no-op, no prior delta
    g.observe(4, None, [_frame(_bar(3, range(3, 6), 7))])  # confirms the delta
    g.observe(4, None, [_frame(_bar(3, range(3, 6), 7))])  # no-op AFTER the delta

    # a multi-layer observation activates the family so the query answers
    g.observe(5, None, [
        _frame({**_bar(3, range(3, 6), 7), (0, 1): 4, **{(i, 1): 4 for i in range(1, 1 + k)}})
        for k in range(1, 5)
    ])
    ev = g.placement_evidence()
    assert ev is not UNKNOWN
    assert len(ev.value["blocked_contrasts"]) == 1
    assert ev.value["unattributed_noops"] == 1


def test_animation_picks_the_incrementally_growing_colour_not_the_one_that_jumps():
    """Purpose: a target that lights up when satisfied also grows, but in one jump;
    the flow grows a little at a time across many layers. Growth STEPS, not final
    size, is the separator.

    Expected feedback: pass proves the trajectory is read off the flow. Fail means
    the verifier would be handed a status change and compare it to a predicted
    spill."""
    layers = []
    flow = {}
    for k in range(1, 8):
        flow[(k, 3)] = 6
        lit = {(7, c): 8 for c in range(0, 6)} if k >= 6 else {}
        layers.append(_frame({**flow, **lit}))

    g = FlowGrounding()
    g.observe(0, None, [_frame({})])
    g.observe(5, None, layers)

    traj = g.trajectory()
    assert traj is not UNKNOWN
    assert [list(f) for f in traj.value][:3] == [[(1, 3)], [(2, 3)], [(3, 3)]]
    emitters = g.emitters()
    assert emitters is not UNKNOWN and emitters.value == ((1, 3),)
    assert g.initial_direction().value == (1, 0)


def test_growth_run_stops_at_a_board_reset():
    """Purpose: within one spill the trail only grows, so the first layer that is
    not a superset belongs to a different board (a restore, or the next level) and
    must not be read as part of the trajectory.

    Expected feedback: pass proves the tail of a layer stack cannot contaminate the
    trajectory. Fail means the verifier compares a prediction against frames from a
    board that no longer exists."""
    layers = []
    flow = {}
    for k in range(1, 6):
        flow[(k, 3)] = 6
        layers.append(_frame(dict(flow)))
    layers.append(_frame({(1, 3): 6}))  # the board reset

    g = FlowGrounding()
    g.observe(0, None, [_frame({})])
    g.observe(5, None, layers)

    traj = g.trajectory()
    assert traj is not UNKNOWN
    assert len([f for f in traj.value if f]) == 5


def test_sink_shortlist_excludes_an_oscillating_edge_band():
    """Purpose: a failure animation makes status bands oscillate, and an
    edge-pinned band touches the cells below the real targets — so without a
    stability rule the targets and the band merge under 4-connectivity into one
    phantom region. Only a change that is STABLE at the end of the run counts.

    Expected feedback: pass proves the shortlist names the targets separately.
    Fail reproduces the merge trap that once had a planner moving a blob the engine
    could not move."""
    layers = []
    flow = {}
    for k in range(1, 6):
        flow[(k, 1)] = 6
        band = {(7, c): (9 if k % 2 else 3) for c in range(N)}  # oscillates
        settled = {(6, 1): 5, (6, 5): 5} if k >= 3 else {(6, 1): 2, (6, 5): 2}
        layers.append(_frame({**flow, **band, **settled}))

    g = FlowGrounding()
    g.observe(0, None, [_frame({(6, 1): 2, (6, 5): 2, **{(7, c): 3 for c in range(N)}})])
    g.observe(5, None, layers)

    sinks = g.sink_candidates()
    assert sinks is not UNKNOWN
    assert [name for name, _ in sinks.value] == ["sink_0", "sink_1"]
    assert all(len(cells) == 1 for _, cells in sinks.value)


def test_family_specific_queries_stay_unknown_until_a_scripted_consequence():
    """Purpose: family auto-detection. Until some action returns more than one
    layer, this board is not known to be a flow board, so every family-specific
    claim must be UNKNOWN — the other families' paths stay untouched.

    Expected feedback: pass proves flow grounding cannot activate on a movement or
    cell-state board. Fail means a foreign board would receive flow answers."""
    g = FlowGrounding()
    g.observe(0, None, [_frame(_bar(3, range(2, 5), 7))])
    g.observe(4, None, [_frame(_bar(3, range(3, 6), 7))])

    assert not g.detected()
    for query in (g.commit_action, g.control_mode, g.pieces, g.piece_deltas,
                  g.emitters, g.trajectory, g.sink_candidates):
        assert query() is UNKNOWN, query.__name__
    # the family-agnostic fact is still available
    assert g.tracked_region() is not UNKNOWN


def test_a_target_of_a_DIFFERENT_SIZE_is_still_named():
    """Purpose: shape congruence names an untouched target only when it is an exact
    copy of a confirmed one. Measured on the fourth sp80 level: three notched targets
    of five cells were named and a fourth region was not, so the plan was compiled
    against a short target list — and "cover every target" silently became "cover the
    ones I saw". What an unnamed target still shares is its APPEARANCE.

    Appearance alone is not enough, though. On that same level a solid two-by-two
    block wears the target colour and has no notch, and this family's satisfaction
    runs THROUGH a notch — so naming it made the objective unreachable. The weak
    source therefore names notched regions only; the stronger sources, which have
    direct evidence, keep their say.

    Expected feedback: pass proves a differently-shaped NOTCHED region wearing the
    agreed appearance is named while a solid block of the same colour is not. Fail
    means the target list is either short or padded with a wall that can never be
    satisfied."""
    odd = {(6, 0): 4, (6, 2): 4, (7, 0): 4, (7, 1): 4, (7, 2): 4}  # notch at (6, 1)
    blocker = {(6, c): 4 for c in range(4, 7)}      # three cells: stops the flow
    wall = {(3, 1): 4, (3, 2): 4, (4, 1): 4, (4, 2): 4}  # same colour, NO notch
    static = {**odd, **blocker, **wall}

    layers = []
    flow = {}
    for k in range(1, 7):
        if k <= 5:
            flow[(k, 5)] = 6
        if k == 6:  # the cell ahead is blocked, so it splits to either side
            flow[(5, 4)] = 6
            flow[(5, 6)] = 6
        layers.append(_frame({**static, **flow}))

    g = FlowGrounding()
    g.observe(0, None, [_frame(static)])
    g.observe(5, None, layers)

    sinks = g.sink_candidates()
    assert sinks is not UNKNOWN
    groups = [set(cells) for _, cells in sinks.value]
    assert any((6, 0) in group for group in groups), \
        f"the notched target of a different shape was not named: {sinks.value}"
    assert not any((3, 1) in group for group in groups), \
        f"a solid block wearing the target colour was named: {sinks.value}"


def test_the_tracked_piece_is_READ_from_the_board_not_remembered():
    """Purpose: the tracked region was maintained by matching translations, and a
    piece that comes to rest against a neighbour is drawn as ONE region from then on —
    so the remembered set describes a piece that is no longer there. Measured on idx3:
    six cells wore the selected appearance while this query returned ONE, and the
    driver pressed on that answer.

    Expected feedback: pass proves the query reports what currently wears the selected
    appearance. Fail means a driver can aim at a piece the board no longer has."""
    a = {(3, 2): 7, (3, 3): 7}
    b = {(3, 5): 8, (3, 6): 8}
    g = FlowGrounding()
    g.observe(0, None, [_frame({**a, **b})])
    g.observe(6, (3, 2), [_frame({(3, 2): 9, (3, 3): 9, **b})])   # select the left one
    g.observe(4, None, [_frame({(3, 3): 9, (3, 4): 9, **b})])     # and move it right

    # now it comes to rest against its neighbour: one run wears the selected
    # appearance
    merged = {(3, c): 9 for c in range(4, 7)}
    g.observe(4, None, [_frame(merged)])

    tracked = g.tracked_region()
    assert tracked is not UNKNOWN
    assert set(tracked.value) == set(merged), \
        f"the tracked piece was remembered, not read: {tracked.value}"


def test_a_falling_source_is_grounded_by_its_COLUMN_where_it_lands():
    """Purpose: what the harness recorded as an "emergence" is where a falling stream
    came to rest on something, so it moves when the pieces move and cannot be replayed
    onto a layout the plan has changed. Measured on idx3: a piece at row 4 gives entries
    at (3,5) and (3,6), the same piece at row 5 gives (4,5) and (4,6) — always the cell
    directly above the obstacle, always the same two columns.

    The COLUMN is the invariant, and it is derivable for a layout never observed, which
    is what planning needs.

    Expected feedback: pass proves a landing stream grounds its column. Fail means the
    model can only replay entries it has already seen, and a plan that moves a piece
    predicts flow in the wrong place."""
    idle = {(5, c): 7 for c in range(2, 5)}
    g = FlowGrounding()
    g.observe(0, None, [_frame(idle)])
    g.observe(6, (5, 2), [_frame({(5, c): 9 for c in range(2, 5)})])   # select it
    g.observe(4, None, [_frame({(5, c): 9 for c in range(3, 6)})])     # and move it right

    piece = {(5, c): 9 for c in range(3, 6)}
    layers = []
    flow = {}
    for k in range(1, 6):
        if k <= 3:
            flow[(k, 0)] = 6          # a plain stream, so the direction is measurable
        if k == 4:
            flow[(4, 4)] = 6          # lands on the piece: nothing behind it
        if k == 5:
            flow[(4, 3)] = 6          # and runs along the top
            flow[(4, 5)] = 6
        layers.append(_frame({**piece, **flow}))
    g.observe(5, None, layers)

    columns = g.falling_columns()
    assert columns is not UNKNOWN, "a landing stream must ground its column"
    assert columns.value == (4,), f"grounded the wrong column: {columns.value}"


def test_a_cell_in_the_MOVING_appearance_does_not_become_a_phantom_piece():
    """Purpose: measured on idx3 — one cell of a stationary five-cell bar rendered in
    the appearance the harness had learned for a piece in motion. Plain segmentation
    then reported the bar as a five-cell piece PLUS a one-cell piece at the same place,
    and, because that cell split the bar's own colour into two regions, the harness
    also read the selected and idle appearances the wrong way round.

    Expected feedback: pass proves a region already contained in another is not
    reported as a second piece, and that the appearance count bridges such a cell.
    Fail means the planner addresses a piece that is not there and can invert which
    piece it believes is selected."""
    bar = {(5, 1): 9, (5, 2): 9, (5, 4): 9, (5, 5): 9}
    odd = {(5, 3): 4}                      # the moving appearance, mid-bar
    other = {(4, 7): 8}
    board = {**bar, **odd, **other}
    selected = {c: 8 for c in bar}

    g = FlowGrounding()
    g.observe(0, None, [_frame(board)])
    g.observe(6, (5, 1), [_frame({**selected, **odd, **other})])   # select the bar
    g.observe(4, None, [_frame({**{(r, c + 1): 8 for (r, c) in bar}, **odd, **other})])
    g.observe(5, None, [_frame(board), _frame({**board, (1, 0): 6}),
                        _frame({**board, (1, 0): 6, (2, 0): 6})])

    inventory = g.pieces()
    assert inventory is not UNKNOWN
    reported = [set(cells) for _, cells in inventory.value]
    assert not any(a < b for a in reported for b in reported if a is not b), \
        f"a region contained in another was reported as its own piece: {inventory.value}"
    assert not any(len(cells) == 1 and (5, 3) in cells for _, cells in inventory.value), \
        f"the foreign cell became a phantom piece: {inventory.value}"
