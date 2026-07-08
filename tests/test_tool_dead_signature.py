"""Contract tests for the generic dead-signature efficiency tool."""

from __future__ import annotations

import numpy as np

from admorphiq.tools.base import Tool, base_hash
from admorphiq.tools.dead_signature import DeadSignatureTool


def _frame(fill: int = 0, size: int = 8) -> np.ndarray:
    return np.full((size, size), fill, dtype=np.int16)


def test_implements_tool_protocol():
    """Purpose: DeadSignatureTool must satisfy the shared Tool protocol (name,
    detect, reset, observe, propose) so the harness can drive it uniformly.

    Expected feedback: pass ⇒ the orchestrator can instantiate and run this
    tool like any other; fail ⇒ the harness's generic dispatch loop breaks.
    """
    tool = DeadSignatureTool()
    assert isinstance(tool, Tool)
    assert tool.name == "deadsig"


def test_inert_action_becomes_dead_and_is_filtered():
    """Purpose: an action class tried >= threshold times at a signature and
    NEVER once changing the frame must be classified dead and dropped from
    live_actions, so the orchestrator stops burning budget on it.

    Expected feedback: pass ⇒ the efficiency lever works (dead actions get
    skipped, saving actions under the squared-efficiency metric); fail ⇒ the
    tool never protects the budget and is useless.
    """
    tool = DeadSignatureTool(threshold=3)
    prev = _frame(0)
    dead_action = (1, None)
    for _ in range(3):
        tool.observe(prev, dead_action, changed=False)

    sig = base_hash(prev)
    assert tool.is_dead(sig, dead_action) is True

    candidates = [dead_action, (2, None)]
    live = tool.live_actions(sig, candidates)
    assert dead_action not in live
    assert (2, None) in live


def test_action_that_ever_changed_stays_live():
    """Purpose: a class with even one observed frame-change at a signature
    must NEVER be marked dead, no matter how many inert tries preceded or
    followed it — a genuinely useful action must not be permanently
    suppressed by an unlucky streak.

    Expected feedback: pass ⇒ the conservative revival rule holds and a real
    action stays available; fail ⇒ the tool could starve the agent of a
    working move, which is worse than never filtering at all.
    """
    tool = DeadSignatureTool(threshold=3)
    prev = _frame(0)
    action = (6, (10, 20))
    tool.observe(prev, action, changed=False)
    tool.observe(prev, action, changed=True)  # one success revives the class
    tool.observe(prev, action, changed=False)
    tool.observe(prev, action, changed=False)

    sig = base_hash(prev)
    assert tool.is_dead(sig, action) is False
    assert action in tool.live_actions(sig, [action])


def test_live_actions_never_returns_empty_when_all_look_dead():
    """Purpose: if every candidate action's class is classified dead at a
    signature, live_actions must fall back to the full candidate list rather
    than returning an empty list — the agent must never stall with zero
    actions to try.

    Expected feedback: pass ⇒ the harness's action loop always has something
    to do; fail ⇒ a fully-inert signature could deadlock the agent.
    """
    tool = DeadSignatureTool(threshold=2)
    prev = _frame(0)
    a1, a2 = (1, None), (2, None)
    for action in (a1, a2):
        for _ in range(2):
            tool.observe(prev, action, changed=False)

    sig = base_hash(prev)
    assert tool.is_dead(sig, a1) is True
    assert tool.is_dead(sig, a2) is True

    live = tool.live_actions(sig, [a1, a2])
    assert live == [a1, a2]


def test_dead_signature_is_scoped_to_state_and_reset_clears_it():
    """Purpose: dead-signature memory is keyed by (state, action-class) — the
    same action class must NOT be dead at a different, never-observed state
    signature, and reset() must drop all memory for a fresh level.

    Expected feedback: pass ⇒ dead-signature tracking never leaks stale
    verdicts across states or levels; fail ⇒ a level transition could
    wrongly suppress actions that were never actually tried there.
    """
    tool = DeadSignatureTool(threshold=2)
    prev_a = _frame(0)
    prev_b = _frame(1)
    action = (3, None)
    for _ in range(2):
        tool.observe(prev_a, action, changed=False)

    sig_a, sig_b = base_hash(prev_a), base_hash(prev_b)
    assert tool.is_dead(sig_a, action) is True
    assert tool.is_dead(sig_b, action) is False  # untried at this signature

    tool.reset()
    assert tool.is_dead(sig_a, action) is False


def test_propose_returns_empty_list():
    """Purpose: this tool is a pure augmentation — it must never propose
    actions of its own; its effect is entirely in is_dead/live_actions.

    Expected feedback: pass ⇒ orchestrators that call propose() on every
    registered tool won't get bogus actions from this one; fail ⇒ the
    documented augmentation-only contract is violated.
    """
    tool = DeadSignatureTool()
    assert tool.propose(frames=[], obs=None) == []


def test_detect_reports_modest_positive_confidence():
    """Purpose: detect() should always be modestly positive since the
    efficiency lever applies to any game where the action budget is tight,
    not just a specific game shape.

    Expected feedback: pass ⇒ an orchestrator that gates tools by detect()
    confidence still includes this one; fail ⇒ the tool would never get a
    chance to run.
    """
    tool = DeadSignatureTool()
    conf = tool.detect(frames=[], obs=None)
    assert 0.0 < conf < 1.0
