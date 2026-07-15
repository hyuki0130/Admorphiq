"""Tests for the SP80 water-routing coverage adapter (R56 flow-kernel rewire,
2026-07-15).

See that module's docstring: SP80 commits a piece layout, then a spill drops
water that flows around the pieces; a level wins when the settled flow covers
every target's interior. The adapter commits ONE sacrificial spill (whose
whole animation is exposed as the observation's frame LAYERS) to learn the
fall direction via ``learn_flow_operators``, probes the movable piece's
per-action deltas, then plans a covering layout via ``plan_flow_coverage`` —
falling back to generic transition-graph frontier exploration when the flow
model or a covering placement is unavailable.
"""

from __future__ import annotations

from types import SimpleNamespace

from admorphiq.adapters25.sp80 import (
    Adapter,
    _detect_translated_color,
    _mask_hud,
)

_BG = 12


def _grid(h, w, stamps, bg=_BG):
    g = [[bg] * w for _ in range(h)]
    for color, cells in stamps:
        for r, c in cells:
            g[r][c] = color
    return tuple(tuple(row) for row in g)


def test_mask_hud_masks_edge_bands_but_keeps_play_area():
    """Purpose: _mask_hud must erase the edge-pinned HUD bands (top strip /
    bottom counter) so the canonical key and region detection see only the
    play area, not the ticking counter.
    Expected feedback: failure means HUD noise corrupts the fallback state
    key (every tick a new state) or an interior cluster is wrongly erased."""
    h = w = 20
    g = [[_BG] * w for _ in range(h)]
    for c in range(w):
        g[h - 1][c] = 1  # full-width bottom HUD band
    for r in range(8, 10):
        for c in range(8, 12):
            g[r][c] = 9  # interior movable block, must survive
    masked = _mask_hud(tuple(tuple(row) for row in g))
    assert all(masked[h - 1][c] == _BG for c in range(w))
    assert masked[8][8] == 9


def test_detect_translated_color_identifies_the_moved_piece():
    """Purpose: the movable piece is found generically as the colour whose
    cells RIGIDLY translated between a before/after move probe — no hardcoded
    'the block is colour 9'. _detect_translated_color must return that colour
    and its shift, ignoring static clusters.
    Expected feedback: failure means the adapter can't identify which cluster
    it controls, so it can't measure deltas or plan a layout."""
    before = _grid(20, 20, [(9, {(4, 4), (4, 5)}), (11, {(18, 2), (18, 3)})])
    after = _grid(20, 20, [(9, {(4, 8), (4, 9)}), (11, {(18, 2), (18, 3)})])  # block +4 cols
    color, shift = _detect_translated_color(before, after, _BG)
    assert color == 9
    assert shift == (0, 4)


def test_detect_translated_color_returns_none_when_nothing_moves():
    """Purpose: when no cluster translated (a blocked move, or a non-move
    frame), the detector must report None rather than inventing a shift.
    Expected feedback: failure means a spurious delta poisons the delta_map
    and the layout plan."""
    g = _grid(20, 20, [(9, {(4, 4), (4, 5)})])
    color, shift = _detect_translated_color(g, g, _BG)
    assert color is None
    assert shift == (0, 0)


def test_detect_targets_excludes_upstream_emitter_keeps_downstream_regions():
    """Purpose: the goal regions are the static clusters DOWNSTREAM of the
    source along the fall direction; the upstream emitter (above the source)
    must be excluded so it is never mistaken for a target the flow must
    cover.
    Expected feedback: failure means the emitter is treated as a target the
    flow can never cover, so every plan fails and L0 falls to slow search."""
    adapter = Adapter()
    # source centroid at row 5; emitter cluster at row 1 (upstream), two
    # target regions at row 18 (downstream). fall = down.
    grid = _grid(
        24, 24,
        [
            (4, {(1, 10), (1, 11)}),  # emitter, upstream
            (9, {(6, 10), (6, 11)}),  # movable, excluded by colour
            (11, {(18, 3), (18, 4), (18, 5)}),
            (11, {(18, 18), (18, 19), (18, 20)}),
        ],
    )
    targets = adapter._detect_targets(grid, _BG, {9, 6}, (5.0, 10.5), (1, 0))
    assert len(targets) == 2
    all_cells = frozenset().union(*targets)
    assert (1, 10) not in all_cells  # emitter excluded
    assert (18, 3) in all_cells and (18, 18) in all_cells


def test_build_plan_arms_a_covering_layout_from_the_learned_model():
    """Purpose: end-to-end at the adapter layer — given a learned flow model
    (fall down + source cells), a detected movable colour + delta, and a goal
    reachable by re-centring the block, _build_plan must arm a non-empty plan
    queue ending in the ACTION5 commit, in the 'plan' phase.
    Expected feedback: failure means the learn→probe→plan wiring is broken,
    so the adapter never clears L0 efficiently and silently falls back."""
    # Board: source water col 12 (rows 4-5), a 3-wide movable block (colour 9)
    # one column left of centred, two targets flanking below.
    movable_cells = {(8, 10), (8, 11), (8, 12)}
    targets = [(18, 9), (18, 10), (18, 11), (18, 13), (18, 14), (18, 15)]
    grid = _grid(
        24, 24,
        [
            (6, {(4, 12), (5, 12)}),  # flow substance / source location
            (9, movable_cells),
            (11, {(18, 9), (18, 10), (18, 11)}),
            (11, {(18, 13), (18, 14), (18, 15)}),
        ],
    )
    adapter = Adapter()
    adapter._flow_model = {"flow_color": 6, "fall_dir": (1, 0), "source_cells": frozenset({(6, 12)})}
    adapter._movable_color = 9
    adapter._delta_map = {4: (0, 1), 3: (0, -1)}
    adapter._build_plan(grid)
    assert adapter._phase == "plan"
    assert adapter._plan_queue
    assert adapter._plan_queue[-1] == 5  # commit appended
    assert all(a in (1, 2, 3, 4, 5) for a in adapter._plan_queue)
    _ = targets  # documents the intended flanking geometry


def test_build_plan_falls_back_to_graph_without_a_movable_or_model():
    """Purpose: missing any of the model / movable colour / deltas must send
    _build_plan to the 'graph' phase rather than plan against an incomplete
    model — keeping non-modelled levels at the generic-explorer baseline.
    Expected feedback: failure means the adapter crashes or plans on an
    incomplete model on a level it can't describe."""
    adapter = Adapter()
    adapter._flow_model = None
    adapter._build_plan(_grid(10, 10, [(9, {(4, 4)})]))
    assert adapter._phase == "graph"


def test_learn_step_commits_a_sacrificial_spill_then_learns_from_layers():
    """Purpose: the learn phase must (a) commit a sacrificial spill (ACTION5)
    from the single-layer change phase, and (b) when the multi-layer spill
    animation arrives, learn the flow model and advance — the 'spill exposes
    its whole trajectory as frame layers' contract this whole approach rests
    on.
    Expected feedback: failure means the adapter never learns the flow (wrong
    layer handling), collapsing to the slow blind-search baseline."""
    adapter = Adapter()
    change = SimpleNamespace(
        frame=[[list(row) for row in _grid(16, 16, [(9, {(4, 4)}), (6, {(1, 8)})])]],
        state=SimpleNamespace(name="NOT_FINISHED"),
        levels_completed=0,
        available_actions=[1, 2, 3, 4, 5],
    )
    a1 = adapter.choose_action([], change)
    assert a1.value == 5  # commit the sacrificial spill

    # Spill animation: water (colour 6) descends one row per layer.
    spill_layers = [
        [list(row) for row in _grid(16, 16, [(6, {(1, 8)})])],
        [list(row) for row in _grid(16, 16, [(6, {(1, 8), (2, 8)})])],
        [list(row) for row in _grid(16, 16, [(6, {(1, 8), (2, 8), (3, 8)})])],
    ]
    spill = SimpleNamespace(
        frame=spill_layers,
        state=SimpleNamespace(name="NOT_FINISHED"),
        levels_completed=0,
        available_actions=[1, 2, 3, 4, 5],
    )
    adapter.choose_action([], spill)
    assert adapter._learned is True
    assert adapter._flow_model["fall_dir"] == (1, 0)
    assert adapter._flow_model["source_cells"] == frozenset({(1, 8)})


def test_level_up_and_game_over_reset_the_flow_pipeline():
    """Purpose: a new level (or a GAME_OVER attempt reset) must restart the
    learn→probe→plan pipeline from scratch — none of the prior level's flow
    model / movable colour / plan applies; GAME_OVER additionally keeps the
    fallback graph (same board) while a level-up wipes it.
    Expected feedback: failure means a stale flow model or plan leaks into a
    new level/attempt, producing wrong moves from the first frame."""
    adapter = Adapter()
    adapter._phase = "graph"
    adapter._learned = True
    adapter._flow_model = {"flow_color": 6, "fall_dir": (1, 0), "source_cells": frozenset({(1, 1)})}
    adapter._movable_color = 9
    adapter._plan_queue = [4, 5]
    adapter._transitions = [("k0", 1, "k1")]

    adapter._on_level_up(1)
    assert adapter._phase == "learn"
    assert adapter._learned is False
    assert adapter._flow_model is None
    assert adapter._movable_color is None
    assert adapter._plan_queue == []
    assert adapter._transitions == []

    # GAME_OVER path keeps the graph but restarts the flow pipeline.
    adapter._phase = "plan"
    adapter._learned = True
    adapter._transitions = [("k0", 1, "k1")]
    action = adapter.choose_action([], SimpleNamespace(state=SimpleNamespace(name="GAME_OVER")))
    assert action.value == 0  # RESET
    assert adapter._phase == "learn"
    assert adapter._learned is False
    assert adapter._transitions == [("k0", 1, "k1")]  # graph kept
