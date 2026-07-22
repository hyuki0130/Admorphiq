"""R95b step (iii) tests: the runtime grounding service.

Synthetic fixtures with KNOWN ground truth (recolouring, layout replacement,
identity loss, cycle acquisition) plus one real-trace fixture per game asserting
the decoded cell/glyph/cycle-edge counts. Also pins the lifted parse against the
quarantined adapter so the lift cannot silently drift.
"""

from __future__ import annotations

import numpy as np

import admorphiq.adapters25.ft09 as _adapter
from admorphiq.hypothesis_select import parse as P
from admorphiq.hypothesis_select.grounding import (
    UNKNOWN,
    Grounded,
    GroundingService,
    RebindEvent,
)


def _lattice(cell_rows, cell_cols, overrides=None):
    """A grid (20x20, bg 0) of 2x2 cells at the given row/col starts, all colour 2
    unless overridden. ``overrides`` maps (row0, col0) -> colour."""
    overrides = overrides or {}
    grid = [[0] * 20 for _ in range(20)]
    for r0 in cell_rows:
        for c0 in cell_cols:
            colour = overrides.get((r0, c0), 2)
            for dr in (0, 1):
                for dc in (0, 1):
                    grid[r0 + dr][c0 + dc] = colour
    return tuple(tuple(row) for row in grid)


def test_ids_stable_across_recolour():
    """Purpose: a cell keeps its ID and click coordinate when it merely changes
    colour — identity is geometry (anchor + footprint), not colour.

    Expected feedback: pass proves the grounding service tracks the same board
    cell across a recolour (the core requirement for a hypothesis that reasons
    about a cell over its colour cycle). Fail means a recolour spawns a new ID
    and the model would lose the cell mid-solve."""
    rows, cols = (4, 8, 12), (6, 10, 14)
    before = _lattice(rows, cols)
    after = _lattice(rows, cols, overrides={(4, 6): 7, (8, 10): 7})  # recolour two cells

    gs = GroundingService()
    gs.feed(before)
    ids_before = {cid: gs.resolve_click(cid) for cid, _c in gs.cells().value}
    gs.feed(after)
    listing_after = dict(gs.cells().value)

    assert set(ids_before) == set(listing_after)  # same IDs
    for cid, grounded in ids_before.items():
        assert gs.resolve_click(cid) == grounded  # same coordinate after recolour


def test_rebind_epoch_invalidates_stale_ids():
    """Purpose: a wholesale layout replacement emits a RebindEvent under a NEW
    epoch, and every pre-rebind ID becomes UNKNOWN (a stale ID can never alias a
    new cell).

    Expected feedback: pass proves cross-epoch IDs are namespaced so a stale
    binding can't silently resolve to the wrong new cell. Fail means a click on a
    dead ID would land somewhere arbitrary after a level/layout change."""
    a = _lattice((4, 8, 12), (6, 10, 14))
    c = _lattice((4, 8, 12), (0, 3, 6))  # moved lattice -> disjoint bboxes -> wholesale

    gs = GroundingService()
    assert gs.feed(a) is None  # initial parse is not a rebind
    old_ids = [cid for cid, _ in gs.cells().value]

    event = gs.feed(c)
    assert isinstance(event, RebindEvent)
    assert event.epoch == 1 and event.reason == "layout_replaced"
    assert gs.epoch == 1
    for old in old_ids:
        assert gs.resolve_click(old) is UNKNOWN  # stale epoch -> UNKNOWN
    assert all(cid.startswith("e1:") for cid, _ in gs.cells().value)


def test_unknown_on_identity_loss():
    """Purpose: a cell that vanishes (recolours to background) within an epoch
    becomes UNBOUND — its query returns UNKNOWN — while its neighbours stay
    bound; and an ID from a foreign epoch is UNKNOWN.

    Expected feedback: pass proves the service reports identity loss honestly
    instead of guessing a stale coordinate. Fail means a lost cell would resolve
    to a phantom location."""
    rows, cols = (4, 8, 12, 16), (6, 10, 14)  # 12 cells; removing one leaves >= 9
    before = _lattice(rows, cols)
    gs = GroundingService()
    gs.feed(before)
    victim = next(cid for cid, _ in gs.cells().value)
    victim_anchor_cell = gs._cells[victim]
    r0, c0 = victim_anchor_cell.bbox[0], victim_anchor_cell.bbox[1]

    after = _lattice(rows, cols, overrides={(r0, c0): 0})  # recolour to background -> vanishes
    assert gs.feed(after) is None  # not wholesale (11/12 cells unchanged)
    assert gs.resolve_click(victim) is UNKNOWN  # the vanished cell
    bound_now = [cid for cid, _ in gs.cells().value]
    assert victim not in bound_now
    assert len(bound_now) >= 9  # the rest stayed bound
    assert gs.resolve_click("e9:c0") is UNKNOWN  # a foreign-epoch id


def test_ordered_cycle_min_probe_rule():
    """Purpose: the ordered colour cycle is UNKNOWN until every edge has >= 2
    independent confirmations, then it is acquired.

    Expected feedback: pass proves the min-probe rule (a single observation of a
    transition edge is not enough) — the guard against acquiring a spurious cycle
    from one noisy click. Fail means the service would report a cycle on
    insufficient evidence."""
    rows, cols = (4, 8, 12), (6, 10, 14)
    all_two = _lattice(rows, cols)
    cell_on = _lattice(rows, cols, overrides={(4, 6): 7})
    click = (6, 4)  # (x, y) inside the (4,6) cell

    gs = GroundingService()
    gs.feed_transition(all_two, 6, click, cell_on)  # edge (2->7) obs 1
    gs.feed_transition(cell_on, 6, click, all_two)  # edge (7->2) obs 1
    assert gs.get_ordered_cycle() is UNKNOWN  # only one confirmation per edge

    gs.feed_transition(all_two, 6, click, cell_on)  # edge (2->7) obs 2
    gs.feed_transition(cell_on, 6, click, all_two)  # edge (7->2) obs 2
    cycle = gs.get_ordered_cycle()
    assert isinstance(cycle, Grounded)
    assert cycle.value == (2, 7)  # canonical start = min colour


def test_lifted_parse_matches_the_quarantined_adapter():
    """Purpose: the ring/glyph parse lifted into hypothesis_select.parse produces
    byte-identical results to the quarantined adapter on real frames.

    Expected feedback: pass proves the lift (done so the runtime never imports
    quarantined game code) did not alter behaviour. Fail means parse.py drifted
    from the proven adapter and R95a/grounding would silently diverge."""
    d = np.load("data/traces/ft09.npz")
    for i in (0, 5, 20, 100):
        grid = tuple(tuple(int(v) for v in row) for row in d["frames"][i])
        rings_a = _adapter._discover_rings(grid)
        rings_p = P._discover_rings(grid)
        assert [r["glyph_bbox"] for r in rings_a] == [r["glyph_bbox"] for r in rings_p]
        cov_a = _adapter._collect_constraints(grid, rings_a)
        cov_p = P._collect_constraints(grid, rings_p)
        assert sorted(cov_a) == sorted(cov_p)


def test_real_trace_ft09_cells_glyphs_incidence_and_cycle_edges():
    """Purpose: on the real ft09 frame the service grounds the decoded structure
    (32 ring-member cells, 4 glyphs, non-empty incidence) and acquires a confirmed
    colour-transition edge from the gold clicks.

    Expected feedback: pass proves the grounding service materializes the
    harness-owned structures the model must not enumerate, and that cycle-edge
    acquisition works on real data. Fail means grounding under-parses the real
    board or never confirms an edge."""
    d = np.load("data/traces/ft09.npz")
    fr, nf = d["frames"], d["next_frames"]
    act, cx, cy = d["actions"], d["coords_x"], d["coords_y"]
    lvl, gold = d["level_index"], d["is_gold"]

    gs = GroundingService()
    gs.feed(fr[0])
    cells = gs.cells()
    glyphs = gs.glyphs()
    assert isinstance(cells, Grounded) and len(cells.value) == 32
    assert isinstance(glyphs, Grounded) and len(glyphs.value) == 4
    first_cell = cells.value[0][0]
    assert isinstance(gs.incidence(first_cell), Grounded)
    assert len(gs.incidence(first_cell).value) >= 1  # covered by >= 1 glyph

    gs2 = GroundingService()
    for i in range(len(fr)):
        if gold[i] and act[i] == 6 and lvl[i] == 0:
            gs2.feed_transition(fr[i], int(act[i]), (int(cx[i]), int(cy[i])), nf[i])
    assert gs2._cycle_obs[(9, 8)] >= 2  # the 9->8 edge is confirmed on real gold clicks


def test_real_trace_sc25_lattice_cells_and_no_glyphs():
    """Purpose: on the real sc25 frame the service grounds the 9-cell lattice and
    reports UNKNOWN for glyphs (a lattice-only family member has none).

    Expected feedback: pass proves the generic parse handles the second family
    member without a game id, and reports the honest absence of glyphs rather than
    fabricating them. Fail means the family generality or the honest-UNKNOWN
    contract broke."""
    d = np.load("data/traces/sc25.npz")
    gs = GroundingService()
    gs.feed(d["frames"][0])
    cells = gs.cells()
    assert isinstance(cells, Grounded) and len(cells.value) == 9
    assert gs.glyphs() is UNKNOWN


def test_wholesale_transition_not_recorded_as_cycle_edge():
    """Purpose: a click whose transition is a WHOLESALE board replacement (a
    decoy->reveal trigger or level boundary) must NOT contribute a cycle edge —
    the clicked cell before vs after is a different physical cell, so its colour
    change is not a same-cell cycle step.

    Expected feedback: pass proves the ordered-cycle acquisition ignores
    board-replacement clicks (the measured ft09 L3 12->8 artifact). Fail means
    reveal/level frames poison the cycle with cross-board edges."""
    before = _lattice((4, 8, 12), (6, 10, 14))          # decoy board
    after = _lattice((4, 8, 12), (0, 3, 6), overrides={(4, 0): 7})  # moved board = wholesale
    gs = GroundingService()
    gs.feed_transition(before, 6, (6, 4), after)
    assert dict(gs._cycle_obs) == {}          # no edge from a wholesale click
    assert gs.get_ordered_cycle() is UNKNOWN
