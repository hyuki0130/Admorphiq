"""Contract tests for the generic hidden-state de-aliasing tool.

DealiasTool detects frame-hash aliasing (same visible base_hash + same action
leading to two DIFFERENT resulting hashes across visits — the signature of a
hidden state the frame does not fully expose) and, once flagged, hands out a
de-aliased key that splits the corrupted node by recent action history.
"""

from __future__ import annotations

import numpy as np

from admorphiq.tools.base import base_hash
from admorphiq.tools.dealias import DealiasTool

_SHAPE = (4, 4)


def _frame(fill: int) -> np.ndarray:
    """A trivially distinguishable synthetic frame (distinct fill -> distinct hash)."""
    return np.full(_SHAPE, fill, dtype=np.int16)


def test_key_matches_base_hash_when_no_aliasing_observed():
    """Purpose: a game that never exhibits aliasing must get byte-identical keys
    to plain ``base_hash`` — the tool is a pure augmentation that must not touch
    unaffected games.

    Expected feedback: pass ⇒ de-aliasing is a no-op absent measured
    nondeterminism; fail ⇒ the tool would perturb every game's state keys.
    """
    tool = DealiasTool()
    frame = _frame(1)
    assert tool.key(frame, recent_actions=[(3, None)]) == base_hash(frame)


def test_observe_flags_alias_on_same_state_action_diverging_outcome():
    """Purpose: observe() must flag a from-hash as aliased exactly when the SAME
    (state, action) pair is seen to lead to two DIFFERENT next states across
    two visits — the measured nondeterminism signature of a hidden state.

    Expected feedback: pass ⇒ aliasing is detected purely from frame-hash
    transitions (frame-only, no game internals); fail ⇒ the graph-search
    plateau this tool exists to break would go undiagnosed.
    """
    tool = DealiasTool()
    a = _frame(1)
    b1 = _frame(2)
    b2 = _frame(3)
    action = (3, None)
    bridge = (4, None)

    # Visit 1: A --action--> B1.
    tool.observe(a, action, changed=True)
    tool.observe(b1, bridge, changed=True)
    assert base_hash(a) not in tool.aliased_bases

    # Visit 2: the SAME (A, action) pair now leads to a DIFFERENT state, B2.
    tool.observe(a, action, changed=True)
    tool.observe(b2, bridge, changed=True)

    assert base_hash(a) in tool.aliased_bases


def test_observe_does_not_flag_consistent_deterministic_transitions():
    """Purpose: repeated visits to the same (state, action) pair that always
    lead to the SAME next state must never be flagged — aliasing is only a
    genuine outcome mismatch, not mere repetition.

    Expected feedback: pass ⇒ no false positives on ordinary deterministic
    games; fail ⇒ every revisited state would spuriously fragment its key.
    """
    tool = DealiasTool()
    a = _frame(1)
    b = _frame(2)
    action = (3, None)
    bridge = (4, None)

    for _ in range(3):
        tool.observe(a, action, changed=True)
        tool.observe(b, bridge, changed=True)

    assert base_hash(a) not in tool.aliased_bases
    assert tool.key(a, recent_actions=[action]) == base_hash(a)


def test_key_gains_action_suffix_and_distinguishes_the_two_visits():
    """Purpose: once a base is flagged aliased, key() must append the recent
    action-history suffix so the two colliding visits produce DIFFERENT keys
    — this is the whole point of de-aliasing for downstream graph search.

    Expected feedback: pass ⇒ search can tell the two hidden states apart;
    fail ⇒ the de-aliased key collapses back to the ambiguous base_hash and
    the plateau this tool targets is not actually broken.
    """
    tool = DealiasTool()
    a = _frame(1)
    b1 = _frame(2)
    b2 = _frame(3)
    action = (3, None)
    bridge = (4, None)

    tool.observe(a, action, changed=True)
    tool.observe(b1, bridge, changed=True)
    tool.observe(a, action, changed=True)
    tool.observe(b2, bridge, changed=True)
    assert base_hash(a) in tool.aliased_bases

    # Visit 1 arrived at `a` via history [...,  action_id 1]; visit 2 via [...,
    # action_id 2] — distinct incoming histories for the two ambiguous visits.
    key_visit_1 = tool.key(a, recent_actions=[(1, None)])
    key_visit_2 = tool.key(a, recent_actions=[(2, None)])

    assert key_visit_1 != key_visit_2
    assert key_visit_1.startswith(base_hash(a) + "|")
    assert key_visit_2.startswith(base_hash(a) + "|")


def test_detect_is_zero_until_aliasing_then_high():
    """Purpose: detect() must report ~0 confidence before any nondeterminism has
    been measured, and a HIGH confidence once it has — a frame-only signal
    derived solely from the tool's own observed transitions.

    Expected feedback: pass ⇒ the orchestrator can gate on this tool becoming
    relevant; fail ⇒ de-aliasing would either never activate or always claim
    relevance regardless of evidence.
    """
    tool = DealiasTool()
    a = _frame(1)
    b1 = _frame(2)
    b2 = _frame(3)
    action = (3, None)
    bridge = (4, None)

    assert tool.detect(frames=[a], obs=None) == 0.0

    tool.observe(a, action, changed=True)
    tool.observe(b1, bridge, changed=True)
    tool.observe(a, action, changed=True)
    tool.observe(b2, bridge, changed=True)

    assert tool.detect(frames=[a], obs=None) > 0.5


def test_reset_clears_aliasing_memory():
    """Purpose: reset() (called on a level transition) must drop all aliasing
    state — a hidden-state ambiguity from one level must not leak into the
    next level's fresh, unrelated layout.

    Expected feedback: pass ⇒ each level starts with a clean slate; fail ⇒
    stale aliasing flags would corrupt an unrelated level's state keys.
    """
    tool = DealiasTool()
    a = _frame(1)
    b1 = _frame(2)
    b2 = _frame(3)
    action = (3, None)
    bridge = (4, None)

    tool.observe(a, action, changed=True)
    tool.observe(b1, bridge, changed=True)
    tool.observe(a, action, changed=True)
    tool.observe(b2, bridge, changed=True)
    assert base_hash(a) in tool.aliased_bases

    tool.reset()

    assert tool.aliased_bases == frozenset()
    assert tool.detect(frames=[a], obs=None) == 0.0
    assert tool.key(a, recent_actions=[action]) == base_hash(a)


def test_propose_returns_no_actions():
    """Purpose: de-aliasing is documented as a pure augmentation — it must
    never propose actions of its own, only sharpen the keys other tools use.

    Expected feedback: pass ⇒ the orchestrator never mistakes this tool for a
    primary mover; fail ⇒ it could be invoked expecting a move and get none.
    """
    tool = DealiasTool()
    assert tool.propose(frames=[_frame(1)], obs=None) == []


def test_name_and_protocol_shape():
    """Purpose: pin the tool's identity and confirm it structurally satisfies
    the harness Tool protocol (name + all four lifecycle methods present).

    Expected feedback: pass ⇒ the orchestrator can discover and dispatch this
    tool uniformly with every other tool; fail ⇒ wiring into the harness
    would silently break.
    """
    tool = DealiasTool()
    assert tool.name == "dealias"
    for method in ("detect", "reset", "observe", "propose"):
        assert callable(getattr(tool, method))
