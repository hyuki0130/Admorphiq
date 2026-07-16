"""Tests for the AR25 mirror-reflection coverage adapter (R56 reflective-
symmetry rewire, 2026-07-15).

See that module's docstring: AR25 renders a movable piece together with its
reflections across a mirror; a level wins when a static goal glyph is fully
covered by the piece's rendered footprint (piece + reflections). The adapter
probes each direction (move + undo, so every measurement starts from the
level-start board), learns the mirror axis / piece / per-action displacement
via ``learn_reflection_operators``, then plans a covering motion via
``plan_reflection_coverage`` — falling back to generic transition-graph
frontier exploration when no reflection model or covering plan exists.
"""

from __future__ import annotations

from types import SimpleNamespace

from admorphiq.adapters25.ar25 import Adapter, _detect_goal, _mask_hud

_BG = 9
_MIRROR_K = 19  # vertical axis: reflect column c -> 19 - c


def _reflect_v(cells, k=_MIRROR_K):
    return {(r, k - c) for r, c in cells}


def _render(piece_cells, goal_cells=frozenset(), h=24, w=24):
    """A HUD-masked AR25-like board: piece (colour 5) + its vertical
    reflection image (colour 4) + a static goal glyph (colour 3), on a
    background field. No HUD bands (already masked)."""
    g = [[_BG] * w for _ in range(h)]
    for r, c in _reflect_v(piece_cells):
        if 0 <= r < h and 0 <= c < w:
            g[r][c] = 4
    for r, c in piece_cells:
        g[r][c] = 5
    for r, c in goal_cells:
        g[r][c] = 3
    return tuple(tuple(row) for row in g)


def _frame(grid, levels=0, actions=(1, 2, 3, 4, 7)):
    return SimpleNamespace(
        frame=[[list(row) for row in grid]],
        state=SimpleNamespace(name="NOT_FINISHED"),
        levels_completed=levels,
        available_actions=list(actions),
    )


def test_mask_hud_masks_edge_bands_but_keeps_interior_play_area():
    """Purpose: _mask_hud must erase edge-pinned status bands (a shrinking
    step counter, a progress bar) so region detection sees only the play
    area — otherwise the ticking counter makes the piece/goal detection and
    the fallback state key noisy.
    Expected feedback: failure means either a HUD band leaks into the region
    set (corrupting goal/piece detection) or an interior cluster is wrongly
    erased (destroying the very thing being solved)."""
    h = w = 24
    g = [[_BG] * w for _ in range(h)]
    for c in range(w):  # full-width bottom-row HUD band
        g[h - 1][c] = 5
    for r in range(6, 9):  # an interior piece block, must survive
        for c in range(6, 9):
            g[r][c] = 5
    masked = _mask_hud(tuple(tuple(row) for row in g))
    assert all(masked[h - 1][c] == _BG for c in range(w))  # band erased
    assert masked[7][7] == 5  # interior kept


def test_detect_goal_picks_largest_static_non_moving_cluster():
    """Purpose: the goal glyph the coverage plan must target is the biggest
    cluster whose colour was NOT observed to move under the probes (the
    piece, its image, and any marker all move); _detect_goal must exclude
    every moving colour and return the largest remaining cluster's cells.
    Expected feedback: failure means the plan would aim to cover the piece
    or its own reflection instead of the real goal, never winning."""
    piece = {(2, 2), (2, 3), (3, 2), (3, 3)}
    goal = {(r, c) for r in range(14, 20) for c in range(14, 20)}  # 36-cell static block
    grid = _render(piece, goal)
    detected = _detect_goal(grid, _BG, frozenset({5, 4, 0}))
    assert detected == frozenset(goal)


def test_build_plan_arms_a_covering_plan_from_reflection_probes():
    """Purpose: end-to-end at the adapter layer — given column-move and
    row-move probe observations (all starting from the same board) plus a
    goal reachable by the piece's reflection, _build_plan must learn the
    model, detect the goal, and arm a non-empty plan queue in the 'plan'
    phase.
    Expected feedback: failure means the probe→learn→plan wiring is broken
    (wrong observation shape, goal misdetected, or the plan not stored), so
    the adapter would never clear L0 efficiently and silently fall to the
    slow graph path."""
    piece = {(2, 2), (2, 3), (3, 2), (3, 3)}
    # Goal = the image of the piece translated down 6 / left 3 -- reachable.
    goal = _reflect_v({(r + 6, c - 3) for r, c in piece})
    start = _render(piece, goal)
    adapter = Adapter()
    adapter._start_grid = start
    adapter._observations = [
        {"before": start, "after": _render({(r, c + 1) for r, c in piece}, goal), "label": 4},
        {"before": start, "after": _render({(r + 1, c) for r, c in piece}, goal), "label": 2},
    ]
    adapter._build_plan()
    assert adapter._phase == "plan"
    assert adapter._plan_queue  # non-empty covering sequence
    assert all(a in (1, 2, 3, 4) for a in adapter._plan_queue)


def test_build_plan_hands_off_to_geared_probe_without_a_reflection_model():
    """Purpose: when the probes reveal no mirror (no axis-splitting
    observation), _build_plan must NOT plan against a hallucinated reflection
    model — it hands off to the geared integer-multiple co-motion probe, which
    itself falls to the generic graph explorer if no geared plan is found. This
    is what keeps deeper / non-reflective levels off an invalid reflection plan
    while giving the geared regime (AR25 L1) a chance before graph.
    Expected feedback: failure means the adapter would either crash or execute
    an invalid reflection plan on a level its mirror model can't describe."""
    piece = {(2, 2), (2, 3)}

    def _plain(cells, h=12, w=12):
        g = [[_BG] * w for _ in range(h)]
        for r, c in cells:
            g[r][c] = 5
        return tuple(tuple(row) for row in g)

    start = _plain(piece)
    adapter = Adapter()
    adapter._start_grid = start
    adapter._observations = [
        {"before": start, "after": _plain({(r, c + 1) for r, c in piece}), "label": 4},
    ]
    adapter._build_plan()
    assert adapter._phase == "geared_probe"
    assert adapter._plan_queue == []


def test_probe_phase_interleaves_moves_with_undo():
    """Purpose: the probe schedule must issue each direction followed by an
    UNDO (ACTION7), so every measured transition starts from the identical
    level-start board (the reference the plan is computed from). The first
    probe call emits a move; the next emits the undo.
    Expected feedback: failure means observations would start from drifting
    boards, so the learned piece footprint would not match the live
    start-of-plan footprint and coverage would miss."""
    piece = {(2, 2), (2, 3), (3, 2), (3, 3)}
    start = _render(piece)
    adapter = Adapter()
    a1 = adapter.choose_action([], _frame(start))
    # First real action is a move (ACTION1..4), with the undo queued next.
    assert a1.value in (1, 2, 3, 4)
    assert adapter._pending_probe_action in (1, 2, 3, 4)
    a2 = adapter.choose_action([], _frame(start))
    assert a2.value == 7  # the undo restoring the start board


def test_game_over_resets_probe_pipeline_but_keeps_graph_transitions():
    """Purpose: a GAME_OVER resets the attempt to the level start; the
    reflection probe/plan pipeline must restart cleanly (board is back at
    start) while the fallback graph's learned transitions — same board —
    are preserved so exploration compounds across attempts.
    Expected feedback: failure means either stale probe observations survive
    across a restart (corrupting the next model) or the graph is wiped every
    death (re-discovering the same states forever)."""
    adapter = Adapter()
    adapter._phase = "probe"
    adapter._observations = [{"before": (), "after": (), "label": 4}]
    adapter._transitions = [("k0", 1, "k1")]
    adapter._tried_from = {"k0": {1}}

    action = adapter.choose_action([], SimpleNamespace(state=SimpleNamespace(name="GAME_OVER")))
    assert action.value == 0  # RESET
    assert adapter._observations == []  # probe pipeline restarted
    assert adapter._transitions == [("k0", 1, "k1")]  # graph kept
    assert adapter._tried_from == {"k0": {1}}


def test_level_up_wipes_reflection_and_graph_state():
    """Purpose: a new level is a new board — the reflection model, probe
    observations, plan, AND the fallback graph must all reset, since none of
    the previous level's geometry or state keys apply.
    Expected feedback: failure means a stale axis/plan or old graph state
    leaks into a new level, producing wrong moves from the first frame."""
    adapter = Adapter()
    adapter._phase = "graph"
    adapter._plan_queue = [2, 3]
    adapter._observations = [{"before": (), "after": (), "label": 1}]
    adapter._transitions = [("k0", 1, "k1")]
    adapter._tried_from = {"k0": {1}}
    adapter._start_grid = ((1,),)

    adapter._on_level_up(1)
    assert adapter._phase == "probe"
    assert adapter._plan_queue == []
    assert adapter._observations == []
    assert adapter._transitions == []
    assert adapter._tried_from == {}
    assert adapter._start_grid is None
