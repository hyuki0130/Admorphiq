"""Contract tests for the generic graph-search (frontier-BFS) tool.

These pin the tool's public :class:`Tool` contract: frame-only movement
detection, edge building from observed transitions, and frontier-reaching
proposal. All fixtures are tiny synthetic numpy frames + a duck-typed fake
observation, so no arcengine is needed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from admorphiq.tools.base import base_hash
from admorphiq.tools.graph_search import GraphSearchTool


@dataclass
class _State:
    name: str = "NOT_FINISHED"


@dataclass
class _Obs:
    """Duck-typed stand-in for an arcengine observation (.frame/.state/etc.)."""

    frame: np.ndarray
    available_actions: list[int] = field(default_factory=list)
    levels_completed: int = 0
    state: _State = field(default_factory=_State)


def _grid_with_dot(y: int, x: int, size: int = 8) -> np.ndarray:
    """A background grid with a single 1-cell 'avatar' at (y, x)."""
    g = np.zeros((size, size), dtype=np.int64)
    g[y, x] = 1
    return g


def test_detect_high_on_movement_signature():
    """Purpose: prove detect fires HIGH when movement actions exist AND the
    observed transitions move a small localized region (avatar mobility) —
    exactly the games this graph engine owns.

    Expected feedback: pass ⇒ the orchestrator routes navigation games here;
    fail ⇒ the tool's own home turf is not recognized from frame signals.
    """
    tool = GraphSearchTool()
    f1 = _grid_with_dot(2, 2)
    f2 = _grid_with_dot(2, 3)  # avatar shifted one cell — 2 cells changed
    frames = [_Obs(f1, [1, 2, 3, 4]), _Obs(f2, [1, 2, 3, 4])]
    conf = tool.detect(frames, frames[-1])
    assert conf >= 0.7


def test_detect_moderate_on_click_only_lowest_without_any_action():
    """Purpose: graph is a MODERATE candidate on a click-only game (it is a
    general discrete-state search that clears click-state games like vc33/lp85),
    but LOWEST when neither movement nor click is offered.

    Expected feedback: pass ⇒ graph is considered (not dismissed) on click games,
    yet not forced where it has no actions to search; fail ⇒ either graph is
    wrongly excluded from click games it clears, or mis-fires with no actions.
    """
    tool = GraphSearchTool()
    f = _grid_with_dot(2, 2)
    click_only = _Obs(f, [6])       # ACTION6 (click) only, no movement
    no_action = _Obs(f, [])         # neither movement nor click
    assert 0.3 <= tool.detect([click_only], click_only) < 0.7
    assert tool.detect([no_action], no_action) <= 0.2


def test_observe_builds_edges():
    """Purpose: prove observe records a state->next_state edge for a change
    transition (resolved on the following propose) and a self-loop for a
    no-change transition.

    Expected feedback: pass ⇒ the transition graph reflects real dynamics; fail
    ⇒ BFS reasons over a corrupt graph and exploration breaks.
    """
    tool = GraphSearchTool()
    a = _grid_with_dot(1, 1)
    b = _grid_with_dot(1, 2)
    ha, hb = base_hash(a), base_hash(b)

    # See state A, take action 1, frame changes to B, then observe B.
    tool.propose([_Obs(a, [1])], _Obs(a, [1]))
    tool.observe(a, (1, None), changed=True)
    tool.propose([_Obs(b, [1])], _Obs(b, [1]))
    assert tool._edges[ha][1] == hb  # change edge resolved to B

    # From B, action 1 changes nothing -> self-loop edge.
    tool.observe(b, (1, None), changed=False)
    assert tool._edges[hb][1] == hb


def test_propose_reaches_unexplored_frontier():
    """Purpose: prove that when the current state has no untried actions, propose
    BFS-walks the known graph and returns a legal action path that reaches the
    nearest state which still has an untried action (the frontier).

    Expected feedback: pass ⇒ the engine keeps discovering new states instead of
    stalling on an exhausted node; fail ⇒ deep exploration dies early.
    """
    tool = GraphSearchTool()
    a = _grid_with_dot(1, 1)
    b = _grid_with_dot(1, 2)
    ha, hb = base_hash(a), base_hash(b)

    # State A has a single action (1); B has two (1, 2). Build edge A --1--> B.
    tool.propose([_Obs(a, [1])], _Obs(a, [1]))          # register A, untried={1}
    tool.observe(a, (1, None), changed=True)             # 1 tried at A, pending
    tool.propose([_Obs(b, [1, 2])], _Obs(b, [1, 2]))    # resolve A--1-->B, register B

    assert tool._untried[ha] == []          # A is now exhausted
    assert tool._untried[hb]                # B is a frontier (has untried)

    # Observe A again: no untried here, so BFS must return the path to frontier B.
    steps = tool.propose([_Obs(a, [1])], _Obs(a, [1]))
    assert steps == [(1, None)]             # legal action id 1, leads to B
    assert tool._edges[ha][steps[0][0]] == hb  # and that action reaches frontier B


def test_hud_masking_stabilizes_aliased_state():
    """Purpose: a churning HUD (a step counter that changes every action) makes
    every true-state hash differently and explodes the graph. After warmup the
    tool must freeze a HUD mask so two frames that differ ONLY in the HUD hash
    identically — the fix for the measured cd82 aliasing (nondeterminism 0.77).

    Expected feedback: pass ⇒ HUD is masked and BFS sees a stable state space;
    fail ⇒ aliasing persists and navigation games with a counter stay unclearable.
    """
    from admorphiq.tools.graph_search import _HUD_WARMUP, GraphSearchTool

    tool = GraphSearchTool()
    size = 8
    # Feed transitions whose ONLY per-step change is a HUD counter at (0,0);
    # the avatar sits still at (4,4) so any residual hash change is pure HUD.
    for i in range(_HUD_WARMUP + 3):
        f = np.zeros((size, size), dtype=np.int64)
        f[4, 4] = 1              # static avatar
        f[0, 0] = i % 5 + 1      # HUD counter cycling 1..5
        tool.observe(f, (1, None), True)

    # Two frames identical but for the HUD must now hash the same under the mask.
    a = np.zeros((size, size), dtype=np.int64)
    a[4, 4] = 1
    a[0, 0] = 2
    b = np.zeros((size, size), dtype=np.int64)
    b[4, 4] = 1
    b[0, 0] = 5
    assert tool._mask is not None                    # mask was frozen at warmup
    assert bool(tool._mask[0, 0])                    # the HUD cell is masked
    assert tool._node_key(a) == tool._node_key(b)    # HUD-only difference is erased


def test_dealias_composition_splits_hidden_state():
    """Purpose: when the same masked frame + same action is observed to lead to
    DIFFERENT next frames (hidden-state aliasing, cd82's 0.77-nondeterminism
    class), the composed de-aliasing must split that frame's node key by recent
    history so BFS stops corrupting one node.

    Expected feedback: pass ⇒ graph composes HUD-masking + de-aliasing and can
    navigate hidden-state games; fail ⇒ aliased games keep stalling the graph.
    """
    tool = GraphSearchTool()
    size = 8
    amb = np.zeros((size, size), dtype=np.int64)
    amb[3, 3] = 2                                   # the ambiguous frame
    out1 = np.zeros((size, size), dtype=np.int64)
    out1[3, 4] = 2
    out2 = np.zeros((size, size), dtype=np.int64)
    out2[3, 2] = 2
    # Same (frame, action=UP) observed leading to two different next frames.
    tool.observe(amb, (1, None), True)
    tool.observe(out1, (2, None), True)
    tool.observe(amb, (1, None), True)
    tool.observe(out2, (2, None), True)
    # base hash of the ambiguous frame is now flagged aliased by the composed tool
    assert base_hash(amb) in tool._dealias.aliased_bases
    # and its node key gains a history suffix (differs from the bare hash)
    tool._recent.clear()
    tool._recent.extend([(3, None), (4, None)])
    assert tool._node_key(amb) != base_hash(amb)


def test_explicit_target_dominates_frontier_choice():
    """Purpose: with an injected target frame, proximity must DOMINATE the
    frontier ranking — at the old 0.05 blend the steering was provably inert
    (±0.05 against integer untried counts), measured as a plausible drawn L2
    target that was never pursued.

    Expected feedback: pass ⇒ graph actually drives to an injected target; fail
    ⇒ target injection is cosmetic and the goal-evidence lever is dead."""
    tool = GraphSearchTool()
    target = np.zeros((64, 64), dtype=np.int64)
    target[:32, :] = 3
    tool.set_target_frame(target)

    near = np.zeros((64, 64), dtype=np.int64)
    near[:32, :] = 3          # matches the target (proximity ~0)
    far = np.zeros((64, 64), dtype=np.int64)  # all-background (proximity ~-0.5)

    # Build a graph: start --1--> near_node (1 untried), start --2--> far_node
    # (3 untried). Old behavior picked far (more untried); dominant steering
    # must pick near.
    tool._state_frame["start"] = far
    tool._state_frame["near"] = near
    tool._state_frame["far"] = far
    tool._edges["start"] = {1: "near", 2: "far"}
    tool._untried["start"] = []
    tool._untried["near"] = [("click", 1, 1)]
    tool._untried["far"] = [("click", 2, 2), ("click", 3, 3), ("click", 4, 4)]
    tool._tries = {"start": {}, "near": {}, "far": {}}

    path = tool._bfs_path_to_frontier("start")
    assert path == [1]   # steered to the target-matching frontier


def test_no_game_specifics_in_source():
    """Purpose: generality guard — the tool must contain no game ids, titles, or
    sprite tags so it transfers to the unseen private games.

    Expected feedback: pass ⇒ frame-only and portable; fail ⇒ a game-specific
    leak crept in and the tool won't generalize.
    """
    import re

    import admorphiq.tools.graph_search as mod

    src = open(mod.__file__).read().lower()
    for tok in ("game_id", "game_title", "sprite"):
        assert tok not in src
    # No 4-char ARC-style game-id tokens (e.g. two letters + two digits) as
    # standalone words — word boundaries exclude numeric type names like int64.
    assert not re.search(r"\b[a-z]{2}\d{2}\b", src)


def test_tier_gate_defers_low_tier_clicks_until_globally_exhausted():
    """Purpose: prove the R38 global tier gate — a tier-1 click is NOT picked
    while any tier-0 untried action is reachable anywhere in the graph; once
    tier-0 is globally exhausted the gate unlocks and the tier-1 click fires.
    Legacy measured this gate as the fix for deep discovery burning ~27k
    actions trying every centroid at every state (cd82 L2).

    Expected feedback: pass ⇒ low-promise clicks are deferred exactly as in the
    legacy engine (the ft09-class budget saver); fail ⇒ the gate is cosmetic
    and click games re-enter exhaustive-centroid behavior.
    """
    tool = GraphSearchTool()
    a = _grid_with_dot(1, 1)
    ha = base_hash(a)
    # Hand-build one state with a tier-0 and a tier-1 click untried.
    k0, k1 = ("click", 1, 1), ("click", 2, 2)
    tool._untried[ha] = [k1, k0]          # list order says k1 first...
    tool._tier[ha] = {k0: 0, k1: 1}       # ...but k1 is tier-1 (gated off)
    tool._edges[ha] = {}
    tool._tries[ha] = {}
    obs = _Obs(a, [6])
    # First pick must be the tier-0 click despite k1 preceding it in the list.
    assert tool.propose([obs], obs) == [(6, (1, 1))]
    # Exhaust tier-0; the gate must then unlock and hand out the tier-1 click.
    tool._untried[ha] = [k1]
    assert tool.propose([obs], obs) == [(6, (2, 2))]
    assert tool._unlocked_tier >= 1


def test_object_key_absorbs_jitter_keeps_movement():
    """Purpose: the R45 object hash must give the SAME key when only a
    component's interior pixels flip (jitter/animation) but a DIFFERENT key
    when a component's centroid moves one cell — the property that fixes
    pixel-graph explosion on big-recolor movement games.

    Expected feedback: pass ⇒ object mode separates noise from movement; fail ⇒
    the ladder rebuilds into an equally broken graph.
    """
    from admorphiq.tools.graph_search import _object_key

    base = np.zeros((16, 16), dtype=np.int64)
    base[4:9, 4:9] = 3            # a 5x5 colour-3 object (area 25)
    jitter = base.copy()
    jitter[5, 5] = 0              # interior pixel flips: area 25 -> 24, SAME
    #                               bit_length bucket (5), same rounded centroid
    moved = np.zeros((16, 16), dtype=np.int64)
    moved[4:9, 5:10] = 3          # whole object shifted one cell right
    assert _object_key(base) == _object_key(jitter)
    assert _object_key(base) != _object_key(moved)


def test_hash_ladder_escalates_pool2_then_object():
    """Purpose: prove the adaptive hash ladder — after the warmup gates, a
    windowed explosion signature escalates ONE rung per fire: full-res pixel ->
    2x2 max-pooled pixel (the rung legacy cleared its jitter class at) ->
    object multiset; each fire drops the broken graph.

    Expected feedback: pass ⇒ games whose every action mints a fresh pixel hash
    get the pooled then object-level state space; fail ⇒ the ladder never arms
    and such games stay random walks.
    """
    from admorphiq.tools.graph_search import _OBJ_MIN_STEPS, _OBJ_WINDOW, GraphSearchTool

    def _prime(tool):
        tool._propose_calls = _OBJ_MIN_STEPS  # past the no-progress guard
        for i in range(_OBJ_WINDOW):          # explosion: all new, mobile
            tool._new_window.append(True)
            tool._loop_window.append(False)
            tool._recent_states.append(f"h{i}")
        tool._edges["stale"] = {}

    tool = GraphSearchTool()
    _prime(tool)
    tool._maybe_fire_object_hash()
    assert tool._pool == 2 and tool._hash_mode == "pixel"   # rung 1: pool2
    assert not tool._edges                                  # broken graph dropped
    _prime(tool)
    tool._maybe_fire_object_hash()
    assert tool._hash_mode == "object"                      # rung 2: object
    tool.reset()
    assert tool._hash_mode == "pixel" and tool._pool == 1   # per-level re-lock


def test_tier_gate_bypassed_while_explicit_target_active():
    """Purpose: the tier gate must NOT gate anything while an explicit target
    frame is injected — measured on cd82 (4/4 -> 0/3): the click its drawn
    target needed was tier-gated out, so dominant steering had nothing to walk
    to. Blind discovery keeps the gate; goal pursuit sees the full action set.

    Expected feedback: pass ⇒ target pursuit and gated discovery compose; fail
    ⇒ any drawn-target game whose winning click ranks below tier-0 is lost.
    """
    tool = GraphSearchTool()
    a = _grid_with_dot(1, 1)
    ha = base_hash(a)
    k1 = ("click", 2, 2)
    tool._untried[ha] = [k1]
    tool._tier[ha] = {k1: 1}          # gated out at unlocked_tier=0...
    tool._edges[ha] = {}
    tool._tries[ha] = {}
    target = np.zeros_like(a)
    target[0, 0] = 7
    tool.set_target_frame(np.kron(target, np.ones((8, 8), dtype=np.int64)))
    obs = _Obs(a, [6])
    # ...but with a target active the tier-1 click must be offered immediately.
    assert tool.propose([obs], obs) == [(6, (2, 2))]
    assert tool._unlocked_tier == 0   # the gate itself was not consumed
