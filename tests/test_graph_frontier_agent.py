"""Unit tests for the HUD-masked state-graph + frontier-BFS agent.

These prove the six load-bearing mechanisms of :class:`GraphFrontierAgent`
independently of arcengine: a lightweight mock observation stands in for the
arcengine frame, and ``_convert_action`` falls back to its dict representation
when the official framework is absent (as it is in the test env). No network,
no live environment, no long measurement — the parent harness measures score
via background shells; these tests only verify the mechanism is correct.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from admorphiq.graph_frontier_agent import (
    _N_TIERS,
    _SIMPLE_TIER,
    GraphFrontierAgent,
    _availability,
    _dilate_grid,
    _max_pool,
    _segment_click_candidates,
    _segment_click_candidates_tiered,
)


def _drive_row_marker(agent, row, cols, extra=None):
    """Feed transitions where a single marker cell walks ``row`` across ``cols``.

    A fresh (64,64) frame is used each step with the marker painted at (row, c)
    and an optional list of stable ``extra`` (r, c, colour) cells, exercising the
    real ``_record_transition`` -> ``_band_observe`` path. The marker is colour 4.
    """
    base = np.zeros((64, 64), dtype=np.int64)
    for (r, c, v) in (extra or []):
        base[r, c] = v
    prev = base.copy()
    prev[row, cols[0]] = 4
    for c in cols[1:]:
        cur = base.copy()
        cur[row, c] = 4
        agent._prev_frame = prev
        agent._prev_hash = "src"
        agent._prev_action_key = 1
        agent._record_transition(cur)
        prev = cur
    return base


@dataclass
class _MockState:
    """Stand-in for the arcengine GameState enum member (only .name is read)."""

    name: str


@dataclass
class _MockObs:
    """Minimal arcengine-observation shape the agent reads.

    Fields mirror exactly what the agent's helpers pull off the obs:
    ``frame`` (layers, 64, 64), ``state`` (has ``.name``),
    ``available_actions`` (ints), ``levels_completed``.
    """

    frame: np.ndarray
    state: _MockState = field(default_factory=lambda: _MockState("PLAYING"))
    available_actions: list[int] = field(default_factory=lambda: [1, 2, 3, 4])
    levels_completed: int = 0


def _layered(grid: np.ndarray) -> np.ndarray:
    """Wrap a (64,64) grid as a (1,64,64) layered frame."""
    return grid[np.newaxis, :, :]


def _action_id(action: Any) -> int:
    """Read the action id from either the dict fallback or an official action."""
    if isinstance(action, dict):
        name = action["action"]
        return {
            "ACTION1": 1, "ACTION2": 2, "ACTION3": 3, "ACTION4": 4,
            "ACTION5": 5, "ACTION6": 6, "RESET": 8,
        }[name]
    return int(getattr(action, "value", getattr(action, "id", action)))


def _is_reset(action: Any) -> bool:
    """True if the action is a RESET, tolerant of both action encodings.

    The dict fallback tags RESET as id 8; the official arcengine GameAction
    enumerates RESET as value 0. This helper accepts either so the test does
    not depend on whether the official framework is installed in the env.
    """
    if isinstance(action, dict):
        return action["action"] == "RESET"
    return _action_id(action) == 0 or getattr(action, "name", "") == "RESET"


# ── (a) HUD mask flags an always-changing cell, stable cells stay unmasked ────


def test_hud_mask_flags_animated_cell_and_spares_stable_cells():
    """Purpose: prove HUD detection masks a cell that changes on every
    transition while leaving cells that never change unmasked.

    Expected feedback: if this fails, the change-rate threshold is either
    masking real (stable-most-of-the-time) game cells — collapsing distinct
    states — or failing to mask a counter cell — making the graph infinite.
    """
    agent = GraphFrontierAgent(hud_threshold=0.8)
    base = np.zeros((64, 64), dtype=np.int64)
    # Feed enough transitions for the mask to be trusted, each changing ONLY the
    # HUD cell (0, 0). Every other cell is stable across all transitions.
    prev = base.copy()
    for step in range(20):
        cur = base.copy()
        cur[0, 0] = step % 7 + 1  # always different from prev at (0,0)
        agent._prev_frame = prev
        agent._prev_hash = "src"
        agent._prev_action_key = 1
        agent._record_transition(cur)
        prev = cur

    mask = agent._hud_mask_grid()
    assert mask is not None, "mask should be trusted after >= min samples"
    assert bool(mask[0, 0]) is True, "always-changing cell must be masked"
    # Region masking (R36c) DILATES around the animated cell so a moving-digit
    # display is covered as a REGION; a small dilated neighbourhood (<=9 cells
    # for a single animated cell at the corner) is the intended behaviour.
    assert int(mask.sum()) <= 9, "mask should stay a small dilated region"
    assert bool(mask[10, 10]) is False, "a stable cell must NOT be masked"


# ── (b) two frames differing only in a masked cell hash EQUAL ─────────────────


def test_masked_cell_difference_produces_equal_hash():
    """Purpose: prove states that differ only in HUD cells hash to the same
    node, so real game states RECUR and the graph stays finite.

    Expected feedback: if this fails, the state hash still sees the counter and
    every step is a fresh node — the whole graph mechanism collapses to the
    near-unique-state wall this round exists to dissolve.
    """
    agent = GraphFrontierAgent(hud_threshold=0.8)
    base = np.zeros((64, 64), dtype=np.int64)
    base[5, 5] = 9  # a real, stable game cell
    prev = base.copy()
    for step in range(20):
        cur = base.copy()
        cur[0, 0] = step % 5 + 1  # only the HUD cell moves
        agent._prev_frame = prev
        agent._prev_hash = "src"
        agent._prev_action_key = 1
        agent._record_transition(cur)
        prev = cur

    a = base.copy()
    a[0, 0] = 1
    b = base.copy()
    b[0, 0] = 4  # differs from `a` ONLY at the masked HUD cell
    assert agent._hash(a) == agent._hash(b)
    # ... but a change in a NON-masked cell must produce a different hash.
    c = base.copy()
    c[0, 0] = 1
    c[5, 5] = 2
    assert agent._hash(a) != agent._hash(c)


# ── (c) graph records an exact edge and marks the action tried ────────────────


def test_graph_records_exact_edge_and_marks_action_tried():
    """Purpose: prove an observed (state, action) -> next_state becomes a graph
    edge and the action is removed from the source state's untried set.

    Expected feedback: if this fails, either transitions are not being learned
    (frontier BFS has nothing to walk) or actions are re-tried forever (the
    agent never advances past a state).
    """
    agent = GraphFrontierAgent()
    src = np.zeros((64, 64), dtype=np.int64)
    dst = src.copy()
    dst[3, 3] = 7

    # Register the source state and take action 2 from it.
    obs1 = _MockObs(frame=_layered(src), available_actions=[1, 2, 3])
    agent.choose_action([], obs1)  # picks untried action 1 first
    # Force the recorded "previous action" to a known key, then feed the result.
    src_hash = agent._hash(src)
    agent._prev_hash = src_hash
    agent._prev_action_key = 2
    agent._prev_frame = src

    agent._record_transition(dst)

    dst_hash = agent._hash(dst)
    assert agent._edges[src_hash][2] == dst_hash
    assert 2 not in agent._untried[src_hash]
    assert agent._tries[src_hash][2] == 1


# ── (d) frontier BFS returns first action of shortest path to a frontier ──────


def test_bfs_to_frontier_returns_first_action_of_shortest_path():
    """Purpose: prove frontier BFS finds the nearest state with untried actions
    and returns the FIRST action of the shortest path to it.

    Expected feedback: if this fails, the agent either wanders (not shortest) or
    returns a mid-path action (mis-tracked first action) — both waste the action
    budget the squared-efficiency metric punishes.
    """
    agent = GraphFrontierAgent()
    # Hand-build a graph: A --1--> B --3--> C, and A --2--> D.
    # C is a frontier (has untried actions); B and D are exhausted.
    agent._edges = {
        "A": {1: "B", 2: "D"},
        "B": {3: "C"},
        "C": {},
        "D": {},
    }
    agent._untried = {"A": [], "B": [], "C": [5], "D": []}

    first = agent._bfs_to_frontier("A")
    # Shortest path A->B->C starts with action 1 (2 hops) vs A->D dead end.
    assert first == 1

    # If no frontier is reachable, return None (graceful-fallback territory).
    agent._untried["C"] = []
    assert agent._bfs_to_frontier("A") is None


# ── (e) click candidates = component centroids, capped at K ───────────────────


def test_click_candidates_are_component_centroids_capped_at_k():
    """Purpose: prove ACTION6's 4096 coords reduce to connected-component
    centroids, salience-ordered and capped at ``max_clicks``.

    Expected feedback: if this fails, ACTION6 either explodes the branching
    factor (no cap) or misses the small buttons (wrong centroid / ordering),
    and click-driven games become unsolvable within budget.
    """
    frame = np.zeros((64, 64), dtype=np.int64)  # background = 0 (most frequent)
    # Blob 1: colour 3 at rows 2-3, cols 2-3 -> centroid (row≈2, col≈2).
    frame[2:4, 2:4] = 3
    # Blob 2: colour 5 single cell at (10, 20) -> centroid (10, 20).
    frame[10, 20] = 5
    # Blob 3: colour 7 at (40, 50)-(40, 51) -> centroid (40, 50-51 -> 50).
    frame[40, 50:52] = 7

    cands = _segment_click_candidates(frame, max_clicks=14)
    # (x, y) = (col, row). Three blobs -> three centroids.
    assert (20, 10) in cands  # single cell, x=col=20, y=row=10
    assert (2, 2) in cands  # 2x2 blob centroid
    assert len(cands) == 3

    # Salience: smallest area first — the single-cell blob (area 1) ranks first.
    assert cands[0] == (20, 10)

    # Cap: with a lower K, only the top-K salient centroids survive.
    assert len(_segment_click_candidates(frame, max_clicks=2)) == 2


# ── (f) agent emits a valid GameAction (simple + ACTION6 carry x/y) ───────────


def test_agent_emits_valid_action_simple_and_click():
    """Purpose: prove the agent produces a well-formed action for both simple
    actions and ACTION6, with coordinates carried through the converter.

    Expected feedback: if this fails, the action plumbing to arcengine is
    broken — the agent would step the env with a malformed action and score 0.
    """
    agent = GraphFrontierAgent(max_clicks=4)
    grid = np.zeros((64, 64), dtype=np.int64)
    grid[8, 12] = 4  # one small blob -> one click candidate at (x=12, y=8)

    # Simple actions available -> the first choice is an untried simple action.
    obs = _MockObs(frame=_layered(grid), available_actions=[1, 2, 3])
    action = agent.choose_action([], obs)
    assert _action_id(action) in (1, 2, 3)

    # ACTION6-only: the agent must fall back to a click candidate carrying x/y.
    agent2 = GraphFrontierAgent(max_clicks=4)
    obs6 = _MockObs(frame=_layered(grid), available_actions=[6])
    action6 = agent2.choose_action([], obs6)
    assert _action_id(action6) == 6
    if isinstance(action6, dict):
        assert action6["x"] == 12 and action6["y"] == 8


# ── level-up resets the graph (durable contract, not feedback-gated) ──────────


def test_level_up_resets_graph_and_hud_stats():
    """Purpose: prove a level-up (levels_completed increase) drops the graph and
    HUD stats so the new level's distinct state space starts fresh.

    Expected feedback: if this fails, stale edges from the previous level's
    layout pollute the new level's graph and frontier BFS walks toward states
    that no longer exist.
    """
    agent = GraphFrontierAgent()
    grid = np.zeros((64, 64), dtype=np.int64)
    obs = _MockObs(frame=_layered(grid), available_actions=[1, 2], levels_completed=0)
    agent.choose_action([], obs)
    assert len(agent._untried) >= 1  # graph has at least the initial state

    obs_up = _MockObs(
        frame=_layered(grid), available_actions=[1, 2], levels_completed=1
    )
    agent.choose_action([], obs_up)
    # After the reset the only state registered is the fresh post-level frame.
    assert len(agent._untried) == 1
    assert agent._level_steps == 1


def test_policy_random_escapes_when_globally_stuck():
    """Purpose: prove that when the current state has no untried action AND no
    frontier is reachable through the observed graph BUT actions are available,
    the policy returns a live random action (the sink-escape), never None.

    Expected feedback: if this fails, the agent has regressed to the pre-R36d
    behaviour of RESETting into a self-absorbing sink — the revived frame
    re-hashes to the same dead node and the whole budget burns on RESET
    (measured SP80: bfs_fires froze at 55, recent_distinct 1/30, 0 clears;
    FT09: states=1 forever). A pass proves the agent breaks the loop by acting
    against the live env instead of resetting into the same dead state.
    """
    agent = GraphFrontierAgent()
    # A single, fully-explored self-looping state: no untried actions, every
    # edge loops back to itself so BFS finds no frontier. This is the sink shape.
    agent._edges = {"A": {1: "A", 2: "A"}}
    agent._untried = {"A": []}
    agent._tries = {"A": {1: 3, 2: 1}}
    frame = np.zeros((64, 64), dtype=np.int64)
    result = agent._policy("A", [1, 2], False, frame)
    assert result is not None, "stuck-but-live state must escape, not reset"
    assert result in (1, 2), "escape must be one of the available simple actions"


def test_policy_returns_none_only_when_no_action_available():
    """Purpose: prove the policy returns None (-> RESET) strictly when there is
    NO legal action at all, not merely when the graph is exhausted.

    Expected feedback: if this fails, the RESET fallback either fires too eagerly
    (wasting the random-escape lever on live states) or never (looping on an
    empty-availability screen). A pass pins the None contract to genuine dead
    ends only.
    """
    agent = GraphFrontierAgent()
    agent._edges = {"A": {}}
    agent._untried = {"A": []}
    frame = np.zeros((64, 64), dtype=np.int64)
    assert agent._policy("A", [], False, frame) is None


def test_max_pool_coarsens_frame_and_is_identity_at_factor_one():
    """Purpose: prove _max_pool reduces a (64,64) frame to (64/k, 64/k) via block
    max, and returns the frame unchanged at k<=1.

    Expected feedback: a fail means the hash-pooling that fixes the M0R0/CD82
    sub-cell-jitter state explosion is either not coarsening (states still never
    recur) or dropping information incorrectly. Pins the pooling shape contract.
    """
    frame = np.arange(64 * 64, dtype=np.int64).reshape(64, 64)
    assert _max_pool(frame, 1).shape == (64, 64)
    assert np.array_equal(_max_pool(frame, 1), frame)
    pooled = _max_pool(frame, 2)
    assert pooled.shape == (32, 32)
    # Block max: top-left 2x2 block is {0,1,64,65} -> max 65.
    assert pooled[0, 0] == 65


def test_hash_pool_makes_sub_cell_jitter_states_recur():
    """Purpose: prove two frames that differ only inside a single pooled block
    (sub-cell jitter) hash to the SAME state under the default pool factor.

    Expected feedback: a fail means the pooling absorber is not engaging in the
    real _hash path, so jittery games (M0R0/CD82) would fork a new state every
    step and the graph would explode — the R36d regression this fix removes.
    """
    agent = GraphFrontierAgent(hash_pool=2, region_mask=False)
    base = np.zeros((64, 64), dtype=np.int64)
    jittered = base.copy()
    jittered[0, 1] = 0  # same block as (0,0); pooled max unchanged since all zero
    jittered[0, 0] = 0
    # A change confined within one 2x2 block that does not raise the block max
    # must not change the pooled hash.
    base[2, 2] = 5
    jittered2 = base.copy()
    jittered2[2, 3] = 3  # same 2x2 block (rows2-3,cols2-3); max stays 5
    assert agent._hash(base) == agent._hash(jittered2)


def test_game_over_resets_and_keeps_graph():
    """Purpose: prove GAME_OVER emits a RESET action and does NOT wipe the graph
    (observed transitions stay valid across a revive) but drops the in-flight
    edge so the pre-reset -> revived-frame jump is not recorded.

    Expected feedback: if this fails, either the agent forgets everything it
    learned on GAME_OVER (re-explores from scratch every death) or it records a
    phantom edge across the reset boundary that corrupts the graph.
    """
    agent = GraphFrontierAgent()
    grid = np.zeros((64, 64), dtype=np.int64)
    obs = _MockObs(frame=_layered(grid), available_actions=[1, 2])
    agent.choose_action([], obs)
    graph_size = len(agent._untried)

    over = _MockObs(
        frame=_layered(grid),
        state=_MockState("GAME_OVER"),
        available_actions=[1, 2],
    )
    action = agent.choose_action([], over)
    assert _is_reset(action)  # RESET
    assert len(agent._untried) == graph_size  # graph preserved
    assert agent._prev_hash is None  # in-flight edge dropped


# ── R38 salience-tiered prioritization ────────────────────────────────────────


def test_click_tiers_rank_salient_widgets_above_background_blobs():
    """Purpose: prove the tiered segmenter puts a small, rare, high-contrast
    widget in a better (lower-index) tier than a large background-hugging blob,
    and returns candidates tier-first.

    Expected feedback: if this fails, the tier ranking is not distinguishing
    likely-interactive buttons from passive fill, so R38's "try high tiers first"
    lever is inert and deep discovery keeps wasting the budget uniformly.
    """
    frame = np.zeros((64, 64), dtype=np.int64)  # background = 0
    # A large blob of a common colour hugging the background (passive board).
    frame[10:40, 10:40] = 2
    # A tiny rare-coloured widget sitting inside the background (a control).
    frame[55, 5] = 7

    tiered = _segment_click_candidates_tiered(frame, max_clicks=14)
    tier_of = {(x, y): t for x, y, t in tiered}
    widget_tier = tier_of[(5, 55)]  # (x=col, y=row)
    blob_tier = tier_of[(24, 24)]  # centroid of the 30x30 blob
    assert widget_tier < blob_tier, (widget_tier, blob_tier)
    # The big background-adjacent blob is demoted to the bottom tier.
    assert blob_tier == _N_TIERS - 1
    # Returned tier-first: the widget precedes the blob in the ordered list.
    order = [(x, y) for x, y, _ in tiered]
    assert order.index((5, 55)) < order.index((24, 24))


def test_tiered_local_pick_prefers_simple_then_low_tier_click():
    """Purpose: prove the current-state untried pick takes a simple action before
    any click (R38 §3), and among clicks takes the lowest (best) tier first.

    Expected feedback: if this fails, the agent squanders early actions on
    low-promise clicks instead of the cheap simple/movement actions and the
    salient control, inflating actions-to-clear.
    """
    agent = GraphFrontierAgent()  # tier_priority on by default
    s = "S"
    click_hi = ("click", 5, 5)  # tier 0
    click_lo = ("click", 9, 9)  # tier 2
    agent._untried[s] = [click_lo, 2, click_hi]  # deliberately click-first order
    agent._action_tier = {2: _SIMPLE_TIER, click_hi: 0, click_lo: 2}
    agent._edges[s] = {}

    # Simple action (tier -1) beats every click regardless of list order.
    assert agent._best_untried_within_tier(s) == 2
    # Once the simple action is consumed, the lower-tier click wins over tier-2.
    agent._untried[s] = [click_lo, click_hi]
    assert agent._best_untried_within_tier(s) == click_hi


def test_frontier_nearest_first_when_promise_inactive_matches_bfs():
    """Purpose: prove that with promise scoring off (the safe default), the
    promise frontier picker returns the SAME first action as plain nearest-BFS,
    so barely-in-budget deep-goal trajectories are never disturbed.

    Expected feedback: if this fails, the R38 frontier reorders the nearest-BFS
    walk even in its safe mode and can lose fragile deep clears (measured: CD82
    L2 clears at 26,965/30,000 actions — any reordering drops it).
    """
    agent = GraphFrontierAgent(visit_penalty=0.0, recency_bonus=0.0)
    agent._edges = {
        "A": {1: "B", 2: "D"},
        "B": {3: "C"},
        "C": {},
        "D": {},
    }
    agent._untried = {"A": [], "B": [], "C": [5], "D": []}
    agent._action_tier = {5: 0}
    assert agent._best_frontier("A") == agent._bfs_to_frontier("A") == 1


def test_frontier_promise_breaks_ties_within_nearest_shell():
    """Purpose: prove that with promise scoring on, two EQUIDISTANT frontiers are
    disambiguated by promise (recency bonus toward the recently-changed region),
    while distance is never overridden.

    Expected feedback: if this fails, the promise lever either does nothing
    (never nudges toward the changed region) or wrongly overrides distance
    (walking to a far frontier), both defeating cost-benefit frontier selection.
    """
    agent = GraphFrontierAgent(visit_penalty=0.0, recency_bonus=1.0)
    # A reaches two frontiers at equal distance 1: B (via action 1) and D (via 2).
    agent._edges = {"A": {1: "B", 2: "D"}, "B": {}, "D": {}}
    agent._untried = {"A": [], "B": [7], "D": [7]}
    agent._action_tier = {7: 0}
    # D is the recently-changed region -> promise favours the action toward D.
    agent._last_change_hash = "D"
    assert agent._best_frontier("A") == 2
    # Move the recency to B -> the pick flips to the action toward B.
    agent._last_change_hash = "B"
    assert agent._best_frontier("A") == 1


def test_tier_gate_defers_low_tier_until_high_tier_exhausted():
    """Purpose: prove that with the tier gate on, the local pick withholds a
    low-tier click while a within-gate (simple/tier-0) untried action exists, and
    only surfaces the low-tier action after the gate widens.

    Expected feedback: if this fails, the gate is not deferring the large mass of
    low-promise clicks (its whole purpose), so enabling it cannot cut
    deep-discovery cost on games that benefit.
    """
    agent = GraphFrontierAgent(tier_gate=True)
    assert agent._unlocked_tier == 0
    s = "S"
    click_hi = ("click", 1, 1)  # tier 0
    click_lo = ("click", 2, 2)  # tier 2
    agent._untried[s] = [click_lo, click_hi]
    agent._action_tier = {click_hi: 0, click_lo: 2}
    # Gate at tier 0: only the tier-0 click is eligible.
    assert agent._best_untried_within_tier(s) == click_hi
    # Simulate the tier-0 click being consumed; now nothing is in-gate.
    agent._untried[s] = [click_lo]
    assert agent._best_untried_within_tier(s) is None
    # Widening the gate surfaces the deferred low-tier click.
    agent._unlocked_tier = _N_TIERS - 1
    assert agent._best_untried_within_tier(s) == click_lo


# ── R39: sticky (monotonic) HUD mask + play-field area cap ────────────────────


def _feed_changes(agent: GraphFrontierAgent, changing_cells, n_steps: int) -> None:
    """Drive ``n_steps`` transitions that change only ``changing_cells`` each step.

    Each step writes a fresh colour into every (row, col) in ``changing_cells`` so
    those cells register as "changed" while all others stay stable, exercising the
    HUD change-rate estimator through the real ``_record_transition`` path.
    """
    base = np.zeros((64, 64), dtype=np.int64)
    prev = base.copy()
    for step in range(n_steps):
        cur = base.copy()
        for (r, c) in changing_cells:
            cur[r, c] = step % 7 + 1
        agent._prev_frame = prev
        agent._prev_hash = "src"
        agent._prev_action_key = 1
        agent._record_transition(cur)
        agent._hud_mask = None  # mimic per-step cache invalidation
        agent._hud_mask_grid()  # force a recompute so sticky accumulates
        prev = cur


def test_sticky_mask_is_monotonic_across_phases():
    """Purpose: prove the sticky mask KEEPS a cell masked after that cell stops
    changing, whereas the non-sticky mask lets it un-mask once the rolling window
    flushes — i.e. the sticky hash is stationary, the rolling one oscillates.

    Expected feedback: if the sticky agent's phase-1 region un-masks, the R39
    fix is not monotonic and the state-hash will still oscillate (the exact
    non-stationary-hash defect that leaves 9/17 games in unbounded state
    explosion). If the non-sticky agent still shows phase-1, the control is wrong.
    """
    early = [(1, 1)]      # masked during phase 1, then goes stable
    late = [(40, 40)]     # masked during phase 2
    # Phase 2 is longer than the 64-step rolling window so phase-1 flushes out.
    sticky = GraphFrontierAgent(sticky_mask=True)
    _feed_changes(sticky, early, 40)
    _feed_changes(sticky, late, 90)
    m_sticky = sticky._hud_mask_grid()
    assert bool(m_sticky[1, 1]) is True, "sticky must retain the phase-1 HUD cell"
    assert bool(m_sticky[40, 40]) is True, "sticky must also hold the phase-2 cell"

    rolling = GraphFrontierAgent(sticky_mask=False)
    _feed_changes(rolling, early, 40)
    _feed_changes(rolling, late, 90)
    m_roll = rolling._hud_mask_grid()
    assert bool(m_roll[1, 1]) is False, (
        "non-sticky mask must drop the phase-1 cell once the window flushes "
        "(this is the oscillation the sticky knob removes)"
    )
    assert bool(m_roll[40, 40]) is True


def test_region_area_cap_leaves_playfield_visible():
    """Purpose: prove a changing region wider than ``region_max_frac`` of the
    frame is treated as the play field and left VISIBLE, while a small animated
    widget is still masked — the guard against whole-board-animation blindness.

    Expected feedback: if the large region gets masked, the sticky union will
    grow to cover the board and every frame hashes equal (the measured LS20
    masked=4096 total-blindness failure). If the small widget is not masked,
    the cap is too aggressive and real HUD noise leaks into the hash.
    """
    agent = GraphFrontierAgent(
        sticky_mask=False, region_max_frac=0.30, hud_threshold=0.8
    )
    # A big block (rows 0..40, cols 0..40 = 1681 cells > 0.30*4096) whose cells
    # each change on ~half the steps (below the 0.8 per-cell threshold) but whose
    # region changes EVERY step (high aggregate) — only region masking could
    # catch it, so the area cap is the deciding factor. Plus one always-changing
    # corner widget that must be masked.
    # Persist colours between repaints so a cell only "changes" on its repaint
    # step — keeping per-cell change-rate well below the 0.8 per-cell threshold.
    block = np.zeros((41, 41), dtype=np.int64)
    prev = np.zeros((64, 64), dtype=np.int64)
    for step in range(24):
        # Rotating stripe: repaint one-third of the block rows each step, so every
        # cell changes on ~1/3 of steps (< 0.8) yet the region changes EVERY step.
        rows = [r for r in range(41) if (r + step) % 3 == 0]
        block[rows, :] = step % 5 + 1
        cur = np.zeros((64, 64), dtype=np.int64)
        cur[0:41, 0:41] = block
        cur[63, 63] = step % 5 + 1  # small always-changing widget
        agent._prev_frame = prev
        agent._prev_hash = "src"
        agent._prev_action_key = 1
        agent._record_transition(cur)
        agent._hud_mask = None
        prev = cur

    mask = agent._hud_mask_grid()
    assert mask is not None
    assert bool(mask[20, 20]) is False, "the >cap play-field region must stay visible"
    assert bool(mask[63, 63]) is True, "the small animated widget must be masked"


def test_sticky_and_cap_knobs_default_on_and_env_overridable(monkeypatch):
    """Purpose: pin the R39 defaults (sticky ON, cap 0.30) and prove the env
    knobs override them, so deployment behaviour is explicit and reversible.

    Expected feedback: if the defaults drift, a future run silently loses the
    state-explosion fix; if the env override stops working, the fix can't be
    ablated for A/B measurement (how CN04's before/after was established).
    """
    default = GraphFrontierAgent()
    assert default.sticky_mask is True
    assert default.region_max_frac == 0.30

    monkeypatch.setenv("GF_STICKY_MASK", "0")
    monkeypatch.setenv("GF_REGION_MAX_FRAC", "0.5")
    overridden = GraphFrontierAgent()
    assert overridden.sticky_mask is False
    assert overridden.region_max_frac == 0.5


# ── (R41) goal-directed frontier ranking ──────────────────────────────────────


def _goal_ready_agent(**kwargs) -> GraphFrontierAgent:
    """Build a goal-rank agent with a tiny hand-wired graph for ranker tests.

    Graph: START --a1--> A, START --a2--> B. A and B are both in-gate frontiers
    (each holds an untried simple action). A's frame is goal-poor, B's frame is
    goal-rich under FILL_COLOR(3), so a goal-following ranker prefers a2.
    """
    from admorphiq.planner.goal import GoalSpec, GoalType

    agent = GraphFrontierAgent(goal_rank=True, **kwargs)
    agent._edges = {"START": {1: "A", 2: "B"}, "A": {}, "B": {}}
    agent._untried = {"START": [], "A": [3], "B": [4]}
    agent._action_tier = {3: _SIMPLE_TIER, 4: _SIMPLE_TIER}
    agent._unlocked_tier = _N_TIERS - 1
    poor = np.zeros((64, 64), dtype=np.int8)
    poor[0, 0] = 3  # one target-colour cell
    rich = np.zeros((64, 64), dtype=np.int8)
    rich[:10, :10] = 3  # 100 target-colour cells
    agent._state_frame = {"A": poor, "B": rich}
    agent._goal = GoalSpec(goal_type=GoalType.FILL_COLOR, color=3)
    return agent


def test_goal_shell_mode_preserves_nearest_distance():
    """Purpose: prove that in shell mode the ranker never picks a farther
    frontier over a nearer one — it only reorders within the nearest shell — so
    the BFS shell expansion that reaches barely-in-budget deep goals is intact.

    Expected feedback: if this fails, shell mode leaks into the aggressive
    global-override behaviour that lost CD82 L2 (measured R41), and the
    no-level-lost acceptance guarantee is void.
    """
    from admorphiq.planner.goal import GoalSpec, GoalType

    agent = GraphFrontierAgent(goal_rank=True, goal_shell=True, goal_blend=1.0)
    # NEAR (dist 1) is goal-poor; FAR (dist 2) is goal-rich. Shell mode must
    # still pick the near frontier because it never crosses the nearest shell.
    agent._edges = {"START": {1: "NEAR"}, "NEAR": {2: "FAR"}, "FAR": {}}
    agent._untried = {"START": [], "NEAR": [3], "FAR": [4]}
    agent._action_tier = {3: _SIMPLE_TIER, 4: _SIMPLE_TIER}
    agent._unlocked_tier = _N_TIERS - 1
    near = np.zeros((64, 64), dtype=np.int8)
    near[0, 0] = 3  # 1 target cell
    far = np.full((64, 64), 3, dtype=np.int8)  # all target cells
    agent._state_frame = {"NEAR": near, "FAR": far}
    agent._goal = GoalSpec(goal_type=GoalType.FILL_COLOR, color=3)
    assert agent._goal_ranked_frontier("START") == 1, "shell mode stays nearest"


def test_goal_ranked_frontier_prefers_goal_rich_frontier():
    """Purpose: prove that with goal_blend=1.0 the ranker walks toward the
    frontier whose cached frame scores highest under the inferred goal, not the
    merely-nearest one.

    Expected feedback: if this fails, score_goal is not steering the frontier
    choice — the core R41 lever (walk toward the level-complete condition) is
    inert and the agent falls back to uniform exploration.
    """
    agent = _goal_ready_agent(goal_blend=1.0)
    action = agent._goal_ranked_frontier("START")
    assert action == 2, "goal-rich frontier B (via a2) must win at blend=1.0"


def test_goal_blend_zero_reduces_to_nearest_tiebreak():
    """Purpose: prove goal_blend=0.0 makes the ranker distance-only, so both
    equidistant frontiers tie and the first-registered action is chosen —
    identical to nearest-first behaviour.

    Expected feedback: if this fails, the blend knob does not actually collapse
    to nearest, so the graceful-degradation guarantee (goal never overrides
    distance when blend is low) is broken.
    """
    agent = _goal_ready_agent(goal_blend=0.0)
    action = agent._goal_ranked_frontier("START")
    assert action == 1, "at blend=0 the nearer/first frontier action wins"


def test_goal_score_cache_invalidates_on_goal_version_bump():
    """Purpose: prove _goal_score memoises per goal_version and recomputes after
    a re-inference bumps the version.

    Expected feedback: if this fails, re-inferred goals would read stale cached
    scores and rank frontiers against an outdated objective.
    """
    from admorphiq.planner.goal import GoalSpec, GoalType

    agent = _goal_ready_agent()
    first = agent._goal_score("B")
    assert first == 100.0
    # Change the goal to a different colour and bump the version.
    agent._goal = GoalSpec(goal_type=GoalType.FILL_COLOR, color=5)
    agent._goal_version += 1
    second = agent._goal_score("B")
    assert second == 0.0, "score must recompute against the new goal after bump"


def test_goal_ranker_disengages_after_stall_cap():
    """Purpose: prove that once goal_walks_since_progress reaches goal_max_walks
    the goal branch in _best_frontier is skipped, so a WRONG goal cannot trap
    the agent — it reverts to nearest-frontier BFS.

    Expected feedback: if this fails, a mis-inferred goal keeps redirecting the
    agent indefinitely (the R38 promise-frontier stall this cap exists to
    prevent).
    """
    agent = _goal_ready_agent(goal_blend=1.0, goal_max_walks=3)
    # Under the cap: goal branch active, prefers goal-rich B (a2).
    assert agent._best_frontier("START") == 2
    # Exhaust the cap; the counter now equals goal_max_walks.
    agent._goal_walks_since_progress = 3
    # Goal branch is skipped -> nearest BFS returns the first frontier (a1).
    assert agent._best_frontier("START") == 1


def test_goal_inference_confidence_gate_stays_goalless_without_new_colors():
    """Purpose: prove goal inference declines (leaves _goal None) when no probe
    introduced a non-background colour — the 'stay goal-less' contract.

    Expected feedback: if this fails, the agent would fabricate a goal from
    noise and rank frontiers toward a meaningless objective on games where the
    heuristic has no real signal.
    """
    agent = GraphFrontierAgent(goal_rank=True, goal_infer_after=2)
    agent._level_steps = 5
    # Probes that changed cells but introduced no non-background colour.
    agent._probe_changes.extend(
        [{"action": 1, "changed_cells": 4, "top_new_color": None} for _ in range(3)]
    )
    frame = np.zeros((64, 64), dtype=np.int64)
    agent._maybe_infer_goal(frame)
    assert agent._goal is None, "no confident signal -> remain goal-less"


def test_goal_rank_off_by_default_and_env_overridable(monkeypatch):
    """Purpose: pin GF_GOAL_RANK OFF by default (pre-R41 behaviour ships) and
    prove the env knob turns it on.

    Expected feedback: if the default drifts to ON before acceptance promotes
    it, an unvalidated ranker ships silently; if the override breaks, the lever
    cannot be A/B measured.
    """
    assert GraphFrontierAgent().goal_rank is False
    monkeypatch.setenv("GF_GOAL_RANK", "1")
    assert GraphFrontierAgent().goal_rank is True


# ── adaptive pool downshift (R42) ─────────────────────────────────────────────


def _fill_windows(agent, *, selfloop_frac: float, mismatch_frac: float) -> None:
    """Saturate the instability windows to the given fractions (window = maxlen).

    The downshift guard requires a FULL window, so both deques are filled to
    their maxlen with the requested True fraction.
    """
    n = agent._sl_window.maxlen
    for i in range(n):
        agent._sl_window.append(i < round(selfloop_frac * n))
        agent._mm_window.append(i < round(mismatch_frac * n))


def _set_recent_distinct(agent, distinct: int) -> None:
    """Load the 30-wide recency window so exactly ``distinct`` hashes appear."""
    agent._recent_states.clear()
    for i in range(agent._recent_states.maxlen):
        agent._recent_states.append(f"s{i % distinct}")


def test_pool_downshift_fires_on_selfloop_sink():
    """Purpose: prove that after the no-progress guard opens, a windowed self-loop
    fraction above threshold drops the effective pool to 1 and rebuilds the graph.

    Expected feedback: a fail means the pool-collapse sink (SB26/S5I5 — a real
    move hashing back to the same state, ~95% self-loop, 0 clears under pooling)
    would never get the finer hash that unblocks it; the sink stays dead.
    """
    agent = GraphFrontierAgent(hash_pool=2, downshift_after=250)
    agent._edges = {"A": {1: "A"}}  # some stale graph to prove it is rebuilt
    agent._untried = {"A": [2]}
    agent._level_steps = 300
    _fill_windows(agent, selfloop_frac=0.95, mismatch_frac=0.0)
    _set_recent_distinct(agent, 2)  # low mobility — sink trigger must not need it

    agent._maybe_downshift_pool()

    assert agent._effective_pool == 1
    assert agent._pool_downshifted is True
    assert agent._untried == {}  # level graph was reset


def test_pool_downshift_moving_collapse_requires_mobility():
    """Purpose: prove the mismatch (moving-object) trigger fires ONLY when the
    agent is still mobile (distinct-recent >= threshold), so a stuck sink whose
    edges merely mismatch (TR87: mismatch 0.38 but distinct 9/30) is spared while
    a mobile moving-object game (TU93: mismatch 0.19, distinct 26/30) downshifts.

    Expected feedback: a fail means either TU93-class moving games never get the
    finer hash that clears them, or TR87/DC22-class sinks get wrongly downshifted
    (measured pool=1 BREAKS TR87/SK48), losing a clearing game.
    """
    # High mismatch but LOW mobility -> spared.
    stuck = GraphFrontierAgent(hash_pool=2, downshift_after=250)
    stuck._level_steps = 300
    _fill_windows(stuck, selfloop_frac=0.0, mismatch_frac=0.30)
    _set_recent_distinct(stuck, 9)
    stuck._maybe_downshift_pool()
    assert stuck._effective_pool == 2, "low-mobility sink must keep pooling"

    # Same mismatch but MOBILE -> fires.
    mobile = GraphFrontierAgent(hash_pool=2, downshift_after=250)
    mobile._level_steps = 300
    _fill_windows(mobile, selfloop_frac=0.0, mismatch_frac=0.30)
    _set_recent_distinct(mobile, 28)
    mobile._maybe_downshift_pool()
    assert mobile._effective_pool == 1, "mobile moving-collapse must downshift"


def test_pool_downshift_jitter_gate_spares_high_mask_level():
    """Purpose: prove a level with a large HUD mask (real sub-cell jitter that
    pooling absorbs) is NOT downshifted even when its self-loop window is maxed,
    because pooling is load-bearing there (SK48: mask ~1100 cells, pool=1 breaks
    its clear and does not even unstick it).

    Expected feedback: a fail means the downshift strips pooling from a jittery
    clearing game (SK48 1->0), violating the 15-game no-loss constraint; the mask
    gate is what separates a true pool-collapse (tiny mask) from a jitter game.
    """
    agent = GraphFrontierAgent(hash_pool=2, downshift_after=250)
    agent._level_steps = 300
    _fill_windows(agent, selfloop_frac=0.99, mismatch_frac=0.0)
    _set_recent_distinct(agent, 2)
    # Large HUD mask -> jitter gate blocks the downshift.
    mask = np.zeros((64, 64), dtype=bool)
    mask[:20, :20] = True  # 400 masked cells > default 256 cap
    agent._hud_mask = mask
    agent._maybe_downshift_pool()
    assert agent._effective_pool == 2, "high-mask jitter level must keep pooling"


def test_pool_downshift_guard_blocks_before_min_actions():
    """Purpose: prove no downshift happens before ``downshift_after`` in-level
    actions, even with a maxed-out sink window.

    Expected feedback: a fail means a level that would clear quickly under pooling
    (M0R0-L1 @751, CD82-L1 @342, LP85 @809 — all high self-loop yet clearing via
    pooling) could be downshifted mid-clear and break, violating the 15-game
    no-loss constraint. The guard is the primary safety.
    """
    agent = GraphFrontierAgent(hash_pool=2, downshift_after=1500)
    agent._level_steps = 900  # below the guard
    _fill_windows(agent, selfloop_frac=0.99, mismatch_frac=0.0)
    _set_recent_distinct(agent, 2)
    agent._maybe_downshift_pool()
    assert agent._effective_pool == 2
    assert agent._pool_downshifted is False


def test_pool_downshift_spares_healthy_deep_level():
    """Purpose: prove a slow-but-healthy deep clear (CD82-L2: self-loop ~0.51,
    mismatch ~0.02, still discovering) never downshifts, so its pooling — which
    absorbs the sub-cell jitter it depends on — is preserved.

    Expected feedback: a fail means the deep clears the metric rewards most
    (CD82 L2 @26,965 actions, VC33 L3 @55,209) get their graph reset mid-search
    and are lost — the exact regression this gate exists to prevent.
    """
    agent = GraphFrontierAgent(hash_pool=2, downshift_after=1500)
    agent._level_steps = 20000  # long-running, but NOT collapsing
    _fill_windows(agent, selfloop_frac=0.51, mismatch_frac=0.02)
    _set_recent_distinct(agent, 12)
    agent._maybe_downshift_pool()
    assert agent._effective_pool == 2
    assert agent._pool_downshifted is False


def test_pool_downshift_fires_at_most_once_per_level():
    """Purpose: prove a level downshifts once and then stays at pool=1 without
    repeatedly resetting its (now finer-hashed) graph.

    Expected feedback: a fail means every subsequent step re-resets the graph,
    so exploration can never accumulate and the unblocked game still cannot
    clear.
    """
    agent = GraphFrontierAgent(hash_pool=2, downshift_after=250)
    agent._level_steps = 300
    _fill_windows(agent, selfloop_frac=0.99, mismatch_frac=0.0)
    _set_recent_distinct(agent, 2)
    agent._maybe_downshift_pool()
    assert agent._effective_pool == 1

    # Re-arm the windows to the sink shape and re-run: the once-per-level guard
    # (and the pool already being 1) must prevent a second reset.
    agent._untried = {"B": [1]}
    _fill_windows(agent, selfloop_frac=0.99, mismatch_frac=0.0)
    agent._maybe_downshift_pool()
    assert agent._untried == {"B": [1]}, "must not reset a second time"


def test_pool_downshift_resets_to_pool_on_level_up():
    """Purpose: prove a genuine level-up restores the configured pool (a fresh
    level may carry the sub-cell jitter that pooling absorbs), independent of a
    prior level's downshift.

    Expected feedback: a fail means once any level downshifted, every later level
    ran unpooled — re-introducing the state explosion pooling was added to fix on
    the jitter games.
    """
    agent = GraphFrontierAgent(hash_pool=2)
    agent._effective_pool = 1
    agent._pool_downshifted = True
    agent._reset_level_state()
    assert agent._effective_pool == 2
    assert agent._pool_downshifted is False


def test_pool_downshift_off_by_env_knob(monkeypatch):
    """Purpose: pin the feature ON by default (it ships) and prove GF_POOL_DOWNSHIFT=0
    fully disables it, so the lever can be A/B measured against the pooled baseline.

    Expected feedback: a fail means the adaptive downshift cannot be turned off for
    a clean baseline comparison, or it silently defaults off and never ships.
    """
    assert GraphFrontierAgent().pool_downshift is True
    monkeypatch.setenv("GF_POOL_DOWNSHIFT", "0")
    off = GraphFrontierAgent(hash_pool=2, downshift_after=250)
    off._level_steps = 300
    _fill_windows(off, selfloop_frac=0.99, mismatch_frac=0.0)
    _set_recent_distinct(off, 2)
    off._maybe_downshift_pool()
    assert off._effective_pool == 2


# ── ACTION7 availability gate (R43 action-space-miss) ─────────────────────────


class _AvailObs:
    """Minimal obs stand-in exposing only ``available_actions`` for _availability."""

    def __init__(self, actions: list[int]) -> None:
        self.available_actions = actions


def test_availability_includes_action7_only_when_no_movement() -> None:
    """Purpose: pin the R43 gate — ACTION7 joins the simple-action set ONLY when
    the game exposes no 1-5 movement (e.g. SU15's ``[6, 7]``), because ACTION7 is
    a real level-advancing command there yet the pre-R43 code silently dropped it,
    leaving the agent a single usable action (click) and the game unclearable.

    Expected feedback: pass means a no-movement title surfaces action id 7 as a
    coordinate-free simple action (with ACTION6 still flagged), so the agent can
    actually issue the command. Fail means the action-space-miss regressed and
    SU15-class games are back to click-only.
    """
    simple, action6 = _availability(_AvailObs([6, 7]))
    assert simple == [7]
    assert action6 is True


def test_availability_drops_action7_when_movement_present() -> None:
    """Purpose: guarantee zero regression on the movement-having clearers — AR25
    ``[1..7]``, SB26 ``[5, 6, 7]``, LF52/SK48/BP35 all expose 1-5 AND ACTION7, and
    all clear WITHOUT ACTION7. Adding a mostly-self-looping cancel command as a
    top-priority simple action there destabilised them (SB26 collapsed into a
    self-loop sink), so the gate must exclude ACTION7 whenever any 1-5 is offered.

    Expected feedback: pass means an env offering movement never picks up ACTION7,
    so its action set (and therefore its exploration trajectory) is byte-identical
    to the pre-R43 baseline. Fail means the gate leaked and a clearer is at risk.
    """
    # AR25-style full set: 7 dropped, 1-5 kept, 6 flagged.
    assert _availability(_AvailObs([1, 2, 3, 4, 5, 6, 7])) == ([1, 2, 3, 4, 5], True)
    # SB26-style [5, 6, 7]: has movement (5) -> 7 dropped.
    assert _availability(_AvailObs([5, 6, 7])) == ([5], True)
    # Pure click-only [6]: no 7 present, no movement -> empty simple set.
    assert _availability(_AvailObs([6])) == ([], True)
    # Pure movement [1-4]: unchanged, no click.
    assert _availability(_AvailObs([1, 2, 3, 4])) == ([1, 2, 3, 4], False)


# ── R44 monotone-moving-band mask ─────────────────────────────────────────────


def test_dilate_grid_expands_true_cells_by_one():
    """Purpose: pin _dilate_grid — a single True cell dilates to its 8-neighbour
    3x3 block at d=1, and d=0 is an identity copy.

    Expected feedback: fail => the band mask fails to cover the marker's LEADING
    edge (its next position lies one cell beyond the swept union), so the marker
    peeks out of the mask and re-forks the state hash every step — defeating the
    whole point of masking the band.
    """
    g = np.zeros((10, 10), dtype=bool)
    g[5, 5] = True
    identity = _dilate_grid(g, 0)
    assert np.array_equal(identity, g)
    assert identity is not g  # a copy, not the same object
    d = _dilate_grid(g, 1)
    assert d[4:7, 4:7].all()
    assert int(d.sum()) == 9


def test_moving_band_along_row_eventually_hashes_equal():
    """Purpose: prove the CORE R44 contract — a small marker that DRIFTS one cell
    per transition along a fixed row is detected as a monotone-moving band and
    masked, so two frames differing ONLY in the marker's column hash to the SAME
    state (real states recur again).

    Expected feedback: fail => the 1-cell-per-action counter/cursor that defeats
    both the per-cell and region masks (S5I5 row-63, DC22 row-63) still forks a
    fresh state every action; the graph never recurs at pool=1 and the game is
    unclearable (measured pre-fix: S5I5 states 21 -> 454 over 4000 actions).
    """
    # Isolate the band: per-cell (0.99) and region masks off, pool=1, so ONLY the
    # band mask can equalise the two frames.
    agent = GraphFrontierAgent(region_mask=False, hud_threshold=0.99, hash_pool=1)
    base = _drive_row_marker(agent, row=30, cols=list(range(0, 30)), extra=[(5, 5, 9)])

    assert agent._band_confirmed is True
    assert agent._band_horizontal is True
    assert agent._band_lo_line <= 30 <= agent._band_hi_line

    a = base.copy()
    a[30, 5] = 4  # marker at column 5
    b = base.copy()
    b[30, 12] = 4  # SAME game state, marker at a different swept column
    assert agent._hash(a) == agent._hash(b), "marker-only difference must hash equal"

    # A change OUTSIDE the band (a real game cell) must still fork the state.
    c = base.copy()
    c[30, 5] = 4
    c[5, 5] = 1
    assert agent._hash(a) != agent._hash(c), "a real-cell change must NOT be masked"


def test_band_rejects_reversing_marker():
    """Purpose: prove a marker that REVERSES direction (a controlled player, not a
    monotone auto-counter) is NOT confirmed as a band even though it drifts a long
    way — monotonicity, not mere motion, is the discriminator.

    Expected feedback: fail => the detector masks a controlled entity, erasing the
    position information the agent navigates by (would regress movement games —
    this is why band_density stays at 0.5: lowering it falsely masked CD82/AR25).
    """
    agent = GraphFrontierAgent(region_mask=False, hud_threshold=0.99)
    # Hand-populate the records with a single-cell marker whose column OSCILLATES
    # 10<->20 across a wide extent (col_ext = 11 >= min_drift, thin in rows) but
    # whose per-record centroid flips direction every step, so the dominant-sign
    # fraction is ~0.5 (< band_monotone 0.7). Populating directly and confirming
    # once isolates the MONOTONE gate from the incremental confirm path (a genuine
    # monotone counter is correctly confirmed the moment 16 such records exist).
    for t in range(20):
        col = 10 if t % 2 == 0 else 20
        agent._band_records.append(
            (t, np.array([30], dtype=np.intp), np.array([col], dtype=np.intp))
        )
    agent._band_t = 20
    agent._try_confirm_band()
    assert agent._band_confirmed is False


def test_band_rejects_stationary_flicker():
    """Purpose: prove a single cell that flickers IN PLACE (changes value without
    moving) is NOT a band — that is the per-cell HUD mask's job, and a band
    requires real drift (>= band_min_drift extent along the track axis).

    Expected feedback: fail => the band detector fires on stationary noise and
    claims a track a coherent-drift signature should never assert, over-masking a
    fixed cell.
    """
    agent = GraphFrontierAgent(region_mask=False, hud_threshold=0.99)
    base = np.zeros((64, 64), dtype=np.int64)
    prev = base.copy()
    prev[30, 10] = 1
    for i in range(20):
        cur = base.copy()
        cur[30, 10] = (i % 5) + 1  # same cell, changing colour, never moving
        agent._prev_frame = prev
        agent._prev_hash = "src"
        agent._prev_action_key = 1
        agent._record_transition(cur)
        prev = cur
    assert agent._band_confirmed is False


def test_band_needs_min_samples_before_confirming():
    """Purpose: prove the band is not confirmed before ``band_min_samples`` marker
    records exist, so a couple of coincidental small moves cannot trigger masking.

    Expected feedback: fail => the detector confirms on scant evidence and can
    mask a transient early-game animation, corrupting the hash before the graph
    has stabilised.
    """
    agent = GraphFrontierAgent(region_mask=False, hud_threshold=0.99, band_min_samples=16)
    # Only 6 drift steps: well below the 16-sample floor.
    _drive_row_marker(agent, row=30, cols=list(range(0, 7)))
    assert agent._band_confirmed is False
    assert len(agent._band_records) == 6


def test_band_knobs_default_on_and_env_overridable(monkeypatch):
    """Purpose: pin the R44 defaults (band mask ON, density floor 0.5) and prove
    the GF_BAND_* env knobs override them, so the lever ships on and is A/B
    ablatable for measurement.

    Expected feedback: fail => the band mask silently defaults off (the
    S5I5/DC22 state explosion returns) or a tuned threshold cannot be ablated to
    reproduce the before/after the round measured.
    """
    default = GraphFrontierAgent()
    assert default.band_mask is True
    assert default.band_density == 0.5
    assert default.band_thickness == 3

    monkeypatch.setenv("GF_BAND_MASK", "0")
    monkeypatch.setenv("GF_BAND_DENSITY", "0.6")
    monkeypatch.setenv("GF_BAND_THICKNESS", "5")
    overridden = GraphFrontierAgent()
    assert overridden.band_mask is False
    assert overridden.band_density == 0.6
    assert overridden.band_thickness == 5


def test_band_mask_unions_into_hud_mask_and_is_sticky():
    """Purpose: prove a confirmed band is OR-ed into the mask returned by
    _hud_mask_grid (so the hash uses it) and, once swept, its cells persist
    (monotone) even as the marker moves on.

    Expected feedback: fail => the band is detected but never reaches the hash
    path (states still fork), or the swept track un-masks behind the marker so
    old positions re-fork — either way the recurrence the band buys is lost.
    """
    agent = GraphFrontierAgent(region_mask=False, hud_threshold=0.99, hash_pool=1)
    _drive_row_marker(agent, row=40, cols=list(range(0, 30)))
    assert agent._band_confirmed is True
    mask = agent._hud_mask_grid()
    assert mask is not None
    # The band's row (dilated) is present in the combined mask.
    assert bool(mask[40, 10]) is True
    assert bool(mask[40, 25]) is True
    # A row far from the band is untouched.
    assert bool(mask[10, 10]) is False
