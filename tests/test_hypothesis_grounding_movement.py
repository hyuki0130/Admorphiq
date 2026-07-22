"""R96 step (iii) tests: the movement grounding — two-actor state reconstruction.

Pins the 55%-risk component: two-actor tracking through crossing / adjacency /
merge, per-actor delta acquisition (min-probe, collision-safe), static occupancy,
no-op attribution, and hazard evidence — plus a real-trace fixture asserting the
decoded m0r0 ground truth. Also pins that movement capabilities DON'T activate on
a cell-state board (family auto-detection leaves the R95 paths untouched).
"""

from __future__ import annotations

import numpy as np

from admorphiq.hypothesis_select.grounding import UNKNOWN, GroundingService

_SCALE = 4
_N = 48
_BG = 0
_ACTOR = 9
_WALL = 7
# A dense static scatter of isolated wall blocks (top + bottom bands, away from
# the row 3-5 actor lane). This gives the frame MANY stable region bboxes so a
# two-actor move is a small fraction of the region set — otherwise the Jaccard
# wholesale-change detector (correctly, for a sparse board) reads the move as a
# layout replacement and rebinds, exactly as a real dense maze board never does.
_STRUCT = tuple((r, c) for r in (0, 2, 8, 10) for c in range(0, 12, 2))


def _frame(actors, walls=(), actor_colour=_ACTOR):
    """A ``_N x _N`` grid (background ``_BG``): each (row, col) CELL is a
    ``_SCALE x _SCALE`` block. Always includes the static ``_STRUCT`` scatter;
    ``actors`` and ``walls`` are lists of cells drawn on top."""
    g = [[_BG] * _N for _ in range(_N)]
    for (r, c) in (*_STRUCT, *walls):
        for dr in range(_SCALE):
            for dc in range(_SCALE):
                g[r * _SCALE + dr][c * _SCALE + dc] = _WALL
    for (r, c) in actors:
        for dr in range(_SCALE):
            for dc in range(_SCALE):
                g[r * _SCALE + dr][c * _SCALE + dc] = actor_colour
    return tuple(tuple(row) for row in g)


def _frame_with_transient(actors, transient_cells, transient_colour):
    """A movement frame plus a transient blob of ``transient_colour`` — a colour that
    is present in one frame and gone in the next (a level-transition trail / HUD flip),
    the kind of noise that must NOT be mistaken for a controllable actor."""
    g = [list(row) for row in _frame(actors)]
    for (r, c) in transient_cells:
        for dr in range(_SCALE):
            for dc in range(_SCALE):
                g[r * _SCALE + dr][c * _SCALE + dc] = transient_colour
    return tuple(tuple(row) for row in g)


def test_actor_colour_detection_ignores_a_vanishing_transient():
    """Purpose: actor-colour detection picks the colour that PERSISTS across the
    transition (present + moving in both frames), never a transient whose regions
    vanish — even when the transient is the smaller footprint the moved/-count
    heuristic would otherwise prefer.

    Expected feedback: pass proves the idx1 mis-lock is fixed — on a level-transition
    frame where the real actors briefly show as one blob and a background-ish colour
    shows two vanishing regions, the persistent actor colour is chosen. Fail means a
    transient can poison the whole delta table (all edges unacquirable)."""
    gs = GroundingService()
    # before: two colour-9 actors (persist + move) + a single small colour-5 transient;
    # after: the actors moved and the transient is GONE.
    before = _frame_with_transient([(3, 2), (3, 5)], [(7, 7)], 5)
    after = _frame([(3, 1), (3, 6)])
    gs.feed_transition(before, 3, (0, 0), after)
    assert gs._move_actor_colour == 9  # the persistent mover, not the vanishing colour 5


def test_two_actors_and_per_actor_deltas_are_acquired_min_probe():
    """Purpose: from directional probes the service identifies the two controlled
    actors and acquires per-(actor, action) deltas only after >= 2 consistent
    observations (the min-probe rule).

    Expected feedback: pass proves the per-actor delta table is built from mobility
    evidence, not guessed. Fail means actor identity or the delta acquisition is
    broken (the transition-model evidence the verifier consumes)."""
    gs = GroundingService()
    walls = [(0, c) for c in range(6)]
    # action 3 = columns diverge (a left, b right); feed it twice to confirm.
    for _ in range(2):
        gs.feed_transition(_frame([(3, 2), (3, 5)], walls), 3, (0, 0), _frame([(3, 1), (3, 6)], walls))
    actors = gs.movement_actors()
    assert actors is not UNKNOWN and len(actors.value) == 2
    deltas = gs.movement_deltas()
    assert deltas is not UNKNOWN
    assert deltas.value[("actor_a", 3)] == (0, -1)  # left actor moves left
    assert deltas.value[("actor_b", 3)] == (0, 1)   # right actor moves right (antisymmetric)


def test_one_observation_is_not_yet_acquired():
    """Purpose: a single observation of an (actor, action) edge is NOT reported as
    acquired — the min-probe rule holds for movement as for the cycle.

    Expected feedback: pass proves a lone probe cannot fix a delta (noise safety).
    Fail means the delta table is trusted on one sample."""
    gs = GroundingService()
    gs.feed_transition(_frame([(3, 2), (3, 5)]), 3, (0, 0), _frame([(3, 1), (3, 6)]))
    assert gs.movement_deltas() is UNKNOWN  # one obs -> not yet acquired


def test_crossing_keeps_stable_ids_via_delta_prediction():
    """Purpose: after the antisymmetric column delta is acquired, a CROSSING (the
    actors swap column order) does not swap their IDs — delta-prediction keeps each
    actor's identity, so the delta table is not corrupted by the crossing.

    Expected feedback: pass proves the swap-ambiguity hard case is resolved by
    scheme consistency, not nearest-centroid. Fail means a crossing silently
    relabels the actors (identity loss the risk register flags)."""
    gs = GroundingService()
    # acquire converge deltas (action 4: a right, b left) from two non-crossing probes
    for _ in range(2):
        gs.feed_transition(_frame([(3, 1), (3, 6)]), 4, (0, 0), _frame([(3, 2), (3, 5)]))
    before = gs.movement_deltas().value
    # now a crossing convergence: a (col2) -> col4, b (col5) -> col3 : they cross columns
    gs.feed_transition(_frame([(3, 2), (3, 5)]), 4, (0, 0), _frame([(3, 4), (3, 3)]))
    # ids preserved: actor_a is the one that moved RIGHT (its acquired +col delta), not relabelled
    after = gs.movement_deltas().value
    assert after[("actor_a", 4)] == before[("actor_a", 4)] == (0, 1)
    assert after[("actor_b", 4)] == before[("actor_b", 4)] == (0, -1)


def test_adjacency_is_not_reported_as_merge():
    """Purpose: two actors becoming ADJACENT (touching = one 2x-size blob) is NOT a
    merge — merge is reserved for coalescence onto ONE cell (a 1x-size blob).

    Expected feedback: pass proves adjacency and merge are distinguished by region
    size (a terminal merge is not falsely declared when actors merely touch). Fail
    means an adjacency ends tracking prematurely."""
    gs = GroundingService()
    gs.feed_transition(_frame([(3, 1), (3, 5)]), 4, (0, 0), _frame([(3, 2), (3, 4)]))  # seed 2 actors
    # actors move to touching cells (3,2)&(3,3) -> one connected 2x blob
    gs.feed_transition(_frame([(3, 2), (3, 4)]), 4, (0, 0), _frame([(3, 2), (3, 3)]))
    assert gs.movement_merge_event() is UNKNOWN  # touching != merged


def test_merge_onto_one_cell_is_a_named_terminal_event():
    """Purpose: when the two actors coalesce onto ONE cell (a single 1x-size region)
    the service reports a named ``merged(actor_a, actor_b)`` terminal event — never
    an identity loss.

    Expected feedback: pass proves the terminal observation (the m0r0 win) is
    reported as a merge, not a dropped actor. Fail means the win state looks like a
    tracking failure."""
    gs = GroundingService()
    gs.feed_transition(_frame([(3, 1), (3, 5)]), 4, (0, 0), _frame([(3, 2), (3, 4)]))  # seed
    gs.feed_transition(_frame([(3, 2), (3, 4)]), 4, (0, 0), _frame([(3, 3)]))  # both onto (3,3)
    merge = gs.movement_merge_event()
    assert merge is not UNKNOWN and merge.value == ("actor_a", "actor_b")


def test_collision_stay_feeds_collision_evidence_not_the_delta_table():
    """Purpose: when one actor is wall-blocked (stays) while the other moves, the
    stay is recorded as collision evidence + a collision_stay no-op — and the
    blocked actor's (0,0) does NOT enter the delta table (only the mover's delta).

    Expected feedback: pass proves a collision-affected probe cannot corrupt the
    delta table and instead feeds the independent-stay collision-policy evidence.
    Fail means a blocked probe poisons the transition model."""
    gs = GroundingService()
    # a wall at (3,0) blocks actor_a (col1 -> col0 into the wall) under action 4 (a moves left)
    walls = [(3, 0)]
    # action 4 here defined so a moves col-1 (into wall), b moves col-1 (free)
    gs.feed_transition(_frame([(3, 1), (3, 5)], walls), 4, (0, 0), _frame([(3, 1), (3, 4)], walls))
    ev = gs.movement_collision_evidence()
    assert ev.value >= 1
    noop = gs.movement_noop_attribution().value
    assert noop.get("collision_stay", 0) >= 1
    deltas = gs.movement_deltas()
    # the mover (actor_b) delta may be single-obs (UNKNOWN); crucially no (actor_a,4)->(0,0)
    if deltas is not UNKNOWN:
        assert deltas.value.get(("actor_a", 4)) != (0, 0)


def test_static_occupancy_parses_walls_and_excludes_actors():
    """Purpose: the static occupancy parse returns a StaticOccupancy whose blocked
    cells are the wall cells and exclude the actor cells + background.

    Expected feedback: pass proves the full-frame static parse (the M0R0 lesson)
    produces the typed occupancy the schema needs. Fail means walls/floor/actors are
    conflated."""
    gs = GroundingService()
    walls = [(0, 0), (0, 1), (5, 5)]
    gs.feed_transition(_frame([(3, 2), (3, 5)], walls), 3, (0, 0), _frame([(3, 1), (3, 6)], walls))
    occ = gs.movement_occupancy()
    assert occ is not UNKNOWN
    blocked = set(occ.value.blocked_cells)
    assert {(0, 0), (0, 1), (5, 5)} <= blocked
    assert (3, 1) not in blocked and (3, 6) not in blocked  # actor cells are floor, not walls
    assert occ.value.confidence == "high" and occ.value.layout_epoch >= 0


def test_hazard_soft_reset_records_cells_and_skips_the_delta_table():
    """Purpose: a soft-reset transition (both actors jump back to spawn) is detected
    as a hazard, its target cell recorded, and it does NOT enter the delta table.

    Expected feedback: pass proves hazard terminal_cells evidence is captured
    without corrupting the motion model. Fail means a reset is read as a giant
    move."""
    gs = GroundingService()
    start = _frame([(5, 2), (5, 5)])
    # seed IDs + move them away from spawn
    gs.feed_transition(start, 1, (0, 0), _frame([(4, 2), (4, 5)]))
    gs.feed_transition(_frame([(4, 2), (4, 5)]), 1, (0, 0), _frame([(3, 2), (3, 5)]))
    n_before = len(gs.movement_deltas().value) if gs.movement_deltas() is not UNKNOWN else 0
    # now action 1 triggers a soft-reset: both snap back to spawn positions
    gs.feed_transition(_frame([(3, 2), (3, 5)]), 1, (0, 0), start)
    assert len(gs.movement_hazard_cells().value) >= 1
    after = gs.movement_deltas()
    n_after = len(after.value) if after is not UNKNOWN else 0
    assert n_after == n_before  # the reset added no delta edge


def test_movement_capabilities_are_inert_on_a_cell_state_board():
    """Purpose: on a glyph/lattice cell-state board no actor colour is confirmed, so
    every movement query is UNKNOWN — family auto-detection leaves the R95 paths
    untouched.

    Expected feedback: pass proves the two families coexist on one GroundingService
    without interference. Fail means movement machinery fires on a cell-state frame
    (a cross-family regression)."""
    d = np.load("data/traces/ft09.npz")
    gs = GroundingService()
    gs.feed(tuple(tuple(int(v) for v in row) for row in d["frames"][0]))
    assert gs.movement_actors() is UNKNOWN
    assert gs.movement_deltas() is UNKNOWN
    assert gs.movement_occupancy() is UNKNOWN


def _to_grid(frame):
    arr = np.asarray(frame)
    if arr.ndim == 3:
        arr = arr[-1]
    return tuple(tuple(int(v) for v in row) for row in arr)


def test_real_m0r0_trace_yields_the_decoded_ground_truth():
    """Purpose: on the real m0r0 gold trace the service finds exactly two actors,
    acquires the decoded mirror scheme (one action-pair antisymmetric in COLUMNS,
    the other symmetric in ROWS), and detects the terminal MERGE at the gold win.

    Expected feedback: pass proves the two-actor reconstruction works on the real
    board (the pre-declared 55%-risk falsification gate). Fail on grounding here is
    the contract's 'pivot to grounding work' signal."""
    d = np.load("data/traces/m0r0.npz")
    fr, nf, act, gold = d["frames"], d["next_frames"], d["actions"], d["is_gold"]
    gs = GroundingService()
    for i in range(len(act)):
        if gold[i] and 1 <= act[i] <= 4:
            gs.feed_transition(_to_grid(fr[i]), int(act[i]), (0, 0), _to_grid(nf[i]))

    dv = gs.movement_deltas().value
    # exactly two actors were tracked (both appear in the acquired delta table)
    assert {aid for aid, _action in dv} == {"actor_a", "actor_b"}
    # rows-symmetric action pair (both actors same delta) + columns-antisymmetric pair (opposite)
    row_pairs = [
        a for a in (1, 2, 3, 4)
        if dv.get(("actor_a", a)) == dv.get(("actor_b", a)) and dv.get(("actor_a", a), (0, 0))[0] != 0
    ]
    col_pairs = [
        a for a in (1, 2, 3, 4)
        if dv.get(("actor_a", a)) == tuple(-x for x in dv.get(("actor_b", a), (0, 0)))
        and dv.get(("actor_a", a), (0, 0))[1] != 0
    ]
    assert len(row_pairs) == 2 and len(col_pairs) == 2  # the mirror structure
    assert gs.movement_merge_event().value == ("actor_a", "actor_b")  # terminal merge detected
