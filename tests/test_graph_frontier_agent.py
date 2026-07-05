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
    _max_pool,
    _segment_click_candidates,
    _segment_click_candidates_tiered,
)


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
