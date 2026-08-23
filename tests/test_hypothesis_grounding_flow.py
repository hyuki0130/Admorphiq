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
    copy of a confirmed one. Measured on the fourth sp80 level: three targets of
    five cells were named and a fourth of FOUR cells was not, so the plan was
    compiled for three targets on a board that needed four — unwinnable however
    precisely it was executed. What the fourth still shared was its APPEARANCE.

    Expected feedback: pass proves a differently-sized region wearing the agreed
    target appearance is named. Fail means "satisfy every target" silently means
    "satisfy the ones that happen to match a shape I have already seen"."""
    odd = {(6, c): 4 for c in range(0, 2)}           # two cells: no shape match
    blocker = {(6, c): 4 for c in range(3, 6)}       # three cells: stops the flow
    layers = []
    flow = {}
    for k in range(1, 7):
        if k <= 5:
            flow[(k, 4)] = 6
        if k == 6:  # the cell ahead is blocked, so it splits to either side
            flow[(5, 3)] = 6
            flow[(5, 5)] = 6
        layers.append(_frame({**odd, **blocker, **flow}))

    g = FlowGrounding()
    g.observe(0, None, [_frame({**odd, **blocker})])
    g.observe(5, None, layers)

    sinks = g.sink_candidates()
    assert sinks is not UNKNOWN
    named = {cells[0] for _, cells in sinks.value}
    assert (6, 0) in named, f"the two-cell target was not named: {sinks.value}"
