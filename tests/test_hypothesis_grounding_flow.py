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

    The targets here are NOTCHED, as this family's targets are — a shortlist entry has
    to be satisfiable to be a target at all (see the shortlist invariants test).

    Expected feedback: pass proves the shortlist names the targets separately and never
    the band. Fail reproduces the merge trap that once had a planner moving a blob the
    engine could not move."""
    left = {(6, 0): 2, (6, 2): 2, (5, 0): 2, (5, 1): 2, (5, 2): 2}    # notch at (6, 1)
    right = {(6, 4): 2, (6, 6): 2, (5, 4): 2, (5, 5): 2, (5, 6): 2}   # notch at (6, 5)
    layers = []
    flow = {}
    for k in range(1, 6):
        flow[(k, 3)] = 6
        band = {(7, c): (9 if k % 2 else 3) for c in range(N)}  # oscillates
        settled = ({c: 5 for c in {**left, **right}} if k >= 3 else {**left, **right})
        layers.append(_frame({**flow, **band, **settled}))

    g = FlowGrounding()
    g.observe(0, None, [_frame({**left, **right, **{(7, c): 3 for c in range(N)}})])
    g.observe(5, None, layers)

    sinks = g.sink_candidates()
    assert sinks is not UNKNOWN
    named = {c for _, cells in sinks.value for c in cells}
    assert not any(r == 7 for r, _ in named), f"the band was named as a target: {sinks.value}"
    assert len(sinks.value) == 2, f"the targets did not stay separate: {sinks.value}"


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
    assert 4 in columns.value, f"the landing column was not grounded: {columns.value}"
    # column 0 is grounded too, and correctly: the plain stream that fixes the direction
    # is itself a source. A lane is recognised wherever flow appears with nothing behind
    # or beside it, landing or not — a source can start in mid-air, and the engine has
    # one on the covered board.
    assert 0 in columns.value, f"the plain stream is a source too: {columns.value}"


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


def test_lanes_accumulate_across_spills():
    """Purpose: a lane is a standing property of the board — the same source pours down
    it whatever the pieces do — so a lane learned from one spill is still true at the
    next. Measured on idx3: the probe spill reveals lanes 5 and 6 and the committed spill
    reveals 11 and 12, and reading only the last animation threw away half the board's
    sources every time.

    Expected feedback: pass proves a lane seen in an earlier spill survives a later one.
    Fail means the model plans with whatever subset the most recent commit happened to
    expose."""
    left = {(4, c): 7 for c in range(1, 4)}
    right = {(4, c): 7 for c in range(6, 8)}
    g = FlowGrounding()
    g.observe(0, None, [_frame({**left, **right})])
    g.observe(6, (4, 1), [_frame({**{c: 9 for c in left}, **right})])
    g.observe(4, None, [_frame({**{(r, c + 1): 9 for (r, c) in left}, **right})])

    board = {**{(r, c + 1): 9 for (r, c) in left}, **right}

    def _spill(landing, beside):
        """A plain descending stream (so the direction is measurable) plus a landing."""
        run = {}
        frames = []
        for k in range(1, 4):
            run[(k, 0)] = 6
            frames.append(_frame({**board, **run}))
        run[landing] = 6
        frames.append(_frame({**board, **run}))
        run[beside] = 6
        frames.append(_frame({**board, **run}))
        return frames

    # first spill: a stream lands on the left piece, in lane 2
    g.observe(5, None, _spill((3, 2), (3, 1)))
    first = g.falling_columns()
    assert first is not UNKNOWN and 2 in first.value, f"lane 2 not found: {first}"

    # second spill: a stream lands in lane 3 — and lane 2 must survive it
    g.observe(5, None, _spill((3, 3), (3, 4)))
    both = g.falling_columns()
    assert both is not UNKNOWN
    assert {2, 3} <= set(both.value), f"a lane was forgotten between spills: {both.value}"


def test_the_shortlist_holds_no_duplicate_and_no_notchless_target():
    """Purpose: measured on idx3 after its first commit — the shortlist had grown to five
    entries, one of them a solid block with no notch and another a straight duplicate of
    a target already listed. "Cover every target" was then unreachable by construction,
    and the compiler kept reporting exactly that.

    Expected feedback: pass proves a region is listed once and only when it has a notch
    to be satisfied at. Fail means the objective can be made impossible by the shortlist
    rather than by the board."""
    notched = {(6, 0): 4, (6, 2): 4, (7, 0): 4, (7, 1): 4, (7, 2): 4}   # notch at (6, 1)
    blocker = {(6, c): 4 for c in range(4, 7)}
    wall = {(3, 1): 4, (3, 2): 4, (4, 1): 4, (4, 2): 4}                  # no notch
    static = {**notched, **blocker, **wall}

    layers = []
    flow = {}
    for k in range(1, 7):
        if k <= 5:
            flow[(k, 5)] = 6
        if k == 6:
            flow[(5, 4)] = 6
            flow[(5, 6)] = 6
        layers.append(_frame({**static, **flow}))

    g = FlowGrounding()
    g.observe(0, None, [_frame(static)])
    g.observe(5, None, layers)

    sinks = g.sink_candidates()
    assert sinks is not UNKNOWN
    groups = [frozenset(cells) for _, cells in sinks.value]
    assert len(groups) == len(set(groups)), f"a target is listed twice: {sinks.value}"
    for group in groups:
        assert g._mouths(group), f"a target with no notch was listed: {sorted(group)}"
    assert set(wall) <= g.absorbers(), "the notchless block was not carried as an absorber"


def test_the_move_budget_is_learned_from_a_loss_and_not_guessed():
    """Purpose: some levels spend a piece on its second move along the flow — measured on
    idx3, where a piece moves once and the next move takes it off the board, while on idx0
    one travels five steps untouched. A planner that does not know this writes plans that
    destroy their own pieces; a planner that GUESSES a limit loses the levels that have
    none, which is exactly what happened when a row-axis limit was applied globally.

    Expected feedback: pass proves the budget stays UNKNOWN until the board has actually
    taken a piece, and is then the number of moves that piece survived. Fail means the
    harness either plans self-destructive moves or invents a constraint no level stated."""
    bar = {(2, 2): 7, (2, 3): 7}
    g = FlowGrounding()
    g.observe(0, None, [_frame(bar)])
    g.observe(6, (2, 2), [_frame({(2, 2): 9, (2, 3): 9})])           # select it
    piece = {(2, 2): 9, (2, 3): 9}
    run = {}
    frames = [_frame(piece)]
    for r in range(1, 6):                                            # a spill long enough
        run[(r, 6)] = 6                                              # to fix the direction
        frames.append(_frame({**piece, **run}))
    g.observe(5, None, frames)
    assert g.initial_direction() is not UNKNOWN, "the direction must be measurable"
    assert g.move_budget() is UNKNOWN, "a budget was claimed before any piece was lost"

    g.observe(2, None, [_frame({(3, 2): 9, (3, 3): 9})])             # one move along it
    assert g.move_budget() is UNKNOWN, "a surviving move must not look like a loss"

    g.observe(2, None, [_frame({})])                                 # and the piece goes
    budget = g.move_budget()
    assert budget is not UNKNOWN, "the loss taught nothing"
    assert budget.value == 1, f"the budget should be what the piece survived: {budget}"


def test_a_piece_that_has_already_moved_has_less_budget_left():
    """Purpose: the budget is per piece and partly SPENT by the time it is known — it is
    learned only when a piece is lost, and by then the survivors have moved too. A planner
    that gives every piece the full budget plans a move a piece has no room left for,
    which is what the replan after idx3's first loss did.

    Expected feedback: pass proves the harness reports what each piece has spent, so the
    compiler can plan within what is LEFT. Fail means the remaining budget is invisible
    and every plan after the first is written against a number that no longer applies."""
    bar = {(2, 2): 7, (2, 3): 7}
    g = FlowGrounding()
    g.observe(0, None, [_frame(bar)])
    g.observe(6, (2, 2), [_frame({(2, 2): 9, (2, 3): 9})])

    piece = {(2, 2): 9, (2, 3): 9}
    run = {}
    frames = [_frame(piece)]
    for r in range(1, 6):
        run[(r, 6)] = 6
        frames.append(_frame({**piece, **run}))
    g.observe(5, None, frames)

    assert g.moves_spent() is UNKNOWN, "nothing is spent before anything moves"

    g.observe(2, None, [_frame({(3, 2): 9, (3, 3): 9, **run})])   # one step along the flow
    spent = g.moves_spent()
    assert spent is not UNKNOWN
    assert dict(spent.value) == {((3, 2), (3, 3)): 1}, f"the step was not counted: {spent}"

    g.observe(4, None, [_frame({(3, 3): 9, (3, 4): 9, **run})])   # ACROSS the flow: free
    spent = g.moves_spent()
    assert dict(spent.value) == {((3, 3), (3, 4)): 1}, \
        f"a move across the flow changed the tally: {spent}"

    # and coming BACK restores it: what a level spends is displacement, not moves —
    # measured on idx3, where up-down-up survives three moves while up-up takes the
    # piece on the second
    g.observe(1, None, [_frame({(2, 3): 9, (2, 4): 9, **run})])
    spent = g.moves_spent()
    assert dict(spent.value) == {((2, 3), (2, 4)): 0}, \
        f"returning to the starting line did not restore the allowance: {spent}"


def test_a_framed_board_is_smaller_than_its_frame():
    """Purpose: measured across three captured boards of one level — the engine's flow
    never enters the last row or the last column, both filled with a single non-background
    colour. Treating them as board let the model run streams into the frame; nine of its
    invented cells on the covered board sat there. They are not hazards either, since
    nothing dies at them.

    Expected feedback: pass proves a uniformly framed edge is trimmed from the playable
    board, and that an edge which merely happens to be empty is not. Fail means the model
    predicts flow in cells the engine cannot use."""
    # scattered interior content, so the cell scale resolves at the intended size
    framed = {(1, 1): 5, (2, 4): 7, (4, 2): 5, (5, 5): 7}
    framed.update({(N - 1, c): 3 for c in range(N)})
    framed.update({(r, N - 1): 3 for r in range(N)})
    g = FlowGrounding()
    g.observe(0, None, [_frame(framed)])
    assert g.playable_size() == N - 1, f"the frame was not trimmed: {g.playable_size()}"

    plain = FlowGrounding()
    plain.observe(0, None, [_frame({(1, 1): 5, (2, 4): 7, (4, 2): 5, (5, 5): 7})])
    assert plain.playable_size() == N, \
        f"an unframed board was trimmed anyway: {plain.playable_size()}"


def test_two_sources_in_one_column_are_both_kept():
    """Purpose: measured on the covered board — the level has a source at (3,6) and another
    at (9,6), the same column at different rows. The lane list was keyed by column, so one
    silently replaced the other and the model poured from whichever was seen last.

    Expected feedback: pass proves both are held. Fail means a board with stacked sources is
    predicted with half of them."""
    piece_hi = {(4, c): 7 for c in range(5, 8)}
    piece_lo = {(6, c): 7 for c in range(5, 8)}
    static = {**piece_hi, **piece_lo}

    layers = []
    flow = {}
    for k in range(1, 7):
        if k <= 3:
            flow[(k, 0)] = 6            # a plain stream, so the direction is measurable
        if k == 4:
            flow[(3, 6)] = 6            # a source above the upper piece
        if k == 5:
            flow[(5, 6)] = 6            # and another above the lower one
        layers.append(_frame({**static, **flow}))

    g = FlowGrounding()
    g.observe(0, None, [_frame(static)])
    g.observe(5, None, layers)

    sources = g.falling_sources()
    assert sources is not UNKNOWN
    lines = sorted(line for lane, _tick, line in sources.value if lane == 6)
    assert lines == [3, 5], f"the two sources in column 6 were not both kept: {sources.value}"


def test_a_pair_over_a_piece_edge_is_one_source_not_half_of_one():
    """Purpose: an entry whose behind-cell is a piece is dropped as the output of a source
    embedded in that piece. Measured on the covered board, that rule cuts a real source in
    half: (9,5) sits over the piece and is dropped while (9,6) beside it is admitted, and
    the dropped half is the one whose flow the engine walks along row 9. The exclusion is
    kept for an entry that stands ALONE and lifted for one that appears beside an admitted
    lane in the same layer.

    Expected feedback: pass proves both halves of a straddling pair are grounded. Fail means
    the model pours from one half of a source and misses everything the other half feeds."""
    piece = {(4, c): 7 for c in range(0, 3)}

    layers = []
    flow = {}
    for k in range(1, 6):
        if k <= 3:
            flow[(k, 7)] = 6            # a plain stream, so the direction is measurable
        if k == 4:
            flow[(5, 2)] = 6            # over the piece's last column — behind it IS piece
            flow[(5, 3)] = 6            # and beside it, clear of the piece
        layers.append(_frame({**piece, **flow}))

    g = FlowGrounding()
    g.observe(0, None, [_frame(piece)])
    g._piece = frozenset(piece)      # the bar, without having watched it move
    g.observe(5, None, layers)

    sources = g.falling_sources()
    assert sources is not UNKNOWN
    lanes = sorted(lane for lane, _tick, line in sources.value if line == 5)
    assert lanes == [2, 3], f"the straddling pair was not grounded whole: {sources.value}"


def test_an_orphan_with_no_piece_to_hide_under_is_not_a_hidden_source():
    """Purpose: `hidden_sources` reports flow that appeared with nothing feeding it, and the
    verifier turns that into "hidden under a piece" and downgrades its verdict to UNKNOWN.
    Measured on the live walk, it was reporting the two ORDINARY lane sources at the top of
    the board, with no piece anywhere near them — so a real one-cell mismatch was being
    excused by a reason the evidence did not support.

    Expected feedback: pass proves an orphan that cannot name a piece is not reported. Fail
    means the harness can excuse any mismatch it likes by pointing at its own sources."""
    layers = []
    flow = {}
    for k in range(1, 5):
        flow[(k, 2)] = 6                 # a plain stream, so the direction is measurable
        if k == 3:
            flow[(1, 5)] = 6             # flow appearing with nothing above it, no piece
        layers.append(_frame(flow.copy()))

    g = FlowGrounding()
    g.observe(0, None, [_frame({})])
    g.observe(5, None, layers)

    assert g.hidden_sources() is UNKNOWN, \
        f"a hostless orphan was reported as hidden: {g.hidden_sources()}"


def test_selection_that_takes_the_idle_colour_exchanges_the_roles():
    """Purpose: exactly one piece is selected, so the two piece appearances are distinct. If
    a selection is observed in the colour previously recorded as IDLE, the roles exchanged —
    what was selected is now what the rest wear. Recording both as the same colour collapses
    the inventory: measured on idx3, the piece count runs 5 -> 4 -> 5 -> 4 -> 1, and at the
    collapse selected and idle are both 9, so only one colour is scanned, one region is found,
    and the compiler then reports — correctly for a one-piece board — that no layout satisfies
    the objective.

    Expected feedback: pass proves the two appearances stay distinct across an exchange. Fail
    means one frame can erase the harness's whole notion of what a piece looks like."""
    g = FlowGrounding()
    a, b = (4, 1), (4, 3)                  # two separate one-cell pieces
    g.observe(0, None, [_frame({a: 8, b: 9})])
    g.observe(6, (4, 4), [_frame({a: 8, b: 8})])   # b becomes 8: 8 is selected, 9 idle
    first = g.piece_appearances()
    assert first[0] is not None and first[0] != first[1], f"appearances not established: {first}"

    g.observe(6, (4, 12), [_frame({a: 9, b: 8})])  # a takes 9, the colour recorded as idle
    second = g.piece_appearances()
    assert second[0] != second[1], f"the two appearances collapsed to one: {second}"


def _wall_and_spill() -> tuple[dict, list]:
    """A board whose spill the grounding will actually READ, and the three things that
    took three ticks to discover about making one.

    1. A colour is read as flow only if it grows over at least three layers AND grows on at
       least three of them. Fixtures that added three cells were two growth steps short and
       were silently ignored, so every assertion written on them passed on nothing.
    2. The flow has to SPLIT within a single frame. The blocker test wants both perpendicular
       neighbours present in the next layer; rendered on separate frames it finds nothing.
    3. The first frame must resolve the scale. `_infer_scale` takes the LARGEST uniform block
       size, so a board whose content happens to align to 4 is read at 4 and everything after
       is nonsense — and a marker on the outer rows does not help, because the margin excuses
       it exactly as that function's docstring warns. (3,6) is interior and odd, so it does.
    """
    wall = {(6, c): 7 for c in range(0, 8) if c not in (1, 6)}
    wall.update({(7, c): 7 for c in range(0, 8)})
    wall[(3, 6)] = 5
    steps = [[(1, 4)], [(2, 4)], [(3, 4)], [(4, 4)], [(5, 4)],
             [(5, 3), (5, 5)], [(5, 2), (5, 6)]]
    layers = [_frame(wall)]
    flow: dict = {}
    for group in steps:
        for cell in group:
            flow[cell] = 6
        layers.append(_frame({**wall, **flow}))
    return wall, layers


def test_an_obstruction_names_the_part_that_blocked_not_the_wall_it_touches():
    """Purpose: the obstruction source seeds from cells that stopped the flow and then takes
    the whole connected region of that colour. A board's walls are one colour and all
    connected, so measured on idx2 it named a single 198-cell region on a 16x16 board — 77%
    of it — which the mouth split carved into seven "targets" of 14 to 39 cells beside the
    three real ones of five. Only parts containing a cell that ACTUALLY obstructed the flow
    are the obstruction.

    Expected feedback: pass proves a blocker does not drag its whole wall into the shortlist.
    Fail means a level whose plan depends on covering every target has an objective that is
    unreachable by construction — the failure idx3 spent three ticks inside."""
    wall, layers = _wall_and_spill()

    g = FlowGrounding()
    g.observe(0, None, [_frame(wall)])
    g.observe(5, None, layers)

    regions = g._obstruction_regions()
    assert regions, "the spill was not read at all — check the scale and the growth steps"
    sizes = sorted(len(r) for r in regions)
    assert sizes == [7], f"the blocker dragged its wall in: {sizes}"
    assert (6, 4) in regions[0], "the part that actually blocked the flow was dropped"


def test_an_observed_spill_that_hits_nothing_reports_no_barriers_not_UNKNOWN():
    """Purpose: `barriers()` used to return UNKNOWN when it found none, and `board()` refuses
    to assemble without an answer — so the walk reported "grounding incomplete" on a board it
    had measured completely. Measured on idx3 the moment the last false hazard was removed.

    Expected feedback: pass proves an empty set is an ANSWER. Fail means removing a wrong
    barrier costs the whole board."""
    wall, layers = _wall_and_spill()

    g = FlowGrounding()
    g.observe(0, None, [_frame(wall)])
    g.observe(5, None, layers)

    bars = g.barriers()
    assert bars is not UNKNOWN, "an observed spill reported no answer at all"
    assert bars.value == (), f"this spill hits nothing it cannot pass: {bars.value}"


def test_a_background_cell_past_a_spills_end_is_not_a_barrier():
    """Purpose: a barrier is read as "flow reached the cell before it and that cell never
    became flow", which a cell of EMPTY BOARD past a stream's end satisfies without blocking
    anything — the spill simply ended there. Measured on idx3: four background cells at row
    12 were grounded as hazards, and with a hazard fatal every one of the 22464 reachable
    layouts failed, so the compiler reported — truthfully, for that board — that no layout
    satisfies the objective. Excluding the animation's final front instead was measured and
    REJECTED, because idx0's real hazard at (15,3) sits exactly there.

    Expected feedback: pass proves a barrier has to look like something. Fail means a level
    can be declared unwinnable by cells that are not there."""
    wall, layers = _wall_and_spill()
    # (6,6) is a notch in the wall — empty board, one step past where the flow stops at (5,6)
    assert (6, 6) not in wall, "the fixture no longer has a gap past the spill's end"

    g = FlowGrounding()
    g.observe(0, None, [_frame(wall)])
    g.observe(5, None, layers)

    bars = g.barriers()
    assert bars is not UNKNOWN, "the spill was not read at all"
    assert (6, 6) not in bars.value, \
        f"empty board past the spill's end was called a barrier: {bars.value}"
