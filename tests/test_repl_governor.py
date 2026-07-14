"""Tests for the code-REPL action governor (R55 module 5).

These lock the action discipline that protects RHAE: illegal / out-of-bounds
actions are refused, the same action in the same state is prevented, macros are
admitted only with a precondition + predicted invariant per step and ABORT on
surprise (stop-on-surprise), and undo is charged as a real environment action.
The governor is deterministic so the transcript replayer can re-derive it.
"""

from __future__ import annotations

from admorphiq.repl_agent.governor import (
    ActionGovernor,
    ActionRequest,
    MacroStep,
)

_LEGAL = {"UP", "DOWN", "LEFT", "RIGHT", "MOUSE", "UNDO"}
_HW = (64, 64)


def test_illegal_action_rejected():
    """Purpose: an action not in the legal set is refused.

    Feedback: failure means the agent could emit an action the env rejects,
    wasting a turn.
    """
    g = ActionGovernor()
    d = g.check_single(ActionRequest("SPACE"), legal=_LEGAL, board_hw=_HW, state_hash="s0")
    assert not d.accepted and "illegal" in d.reason


def test_legal_action_accepted():
    """Purpose: a legal action passes and yields its canonical dict.

    Feedback: failure means valid moves are blocked.
    """
    g = ActionGovernor()
    d = g.check_single(ActionRequest("LEFT"), legal=_LEGAL, board_hw=_HW, state_hash="s0")
    assert d.accepted and d.action == {"action": "LEFT"}


def test_mouse_bounds_and_missing_coords():
    """Purpose: MOUSE needs in-bounds row/col (row=y, col=x, zero-based).

    Feedback: failure means coordinate hallucinations reach the env.
    """
    g = ActionGovernor()
    assert not g.check_single(ActionRequest("MOUSE"), legal=_LEGAL,
                              board_hw=_HW, state_hash="s").accepted
    assert not g.check_single(ActionRequest("MOUSE", row=64, col=0), legal=_LEGAL,
                              board_hw=_HW, state_hash="s").accepted
    ok = g.check_single(ActionRequest("MOUSE", row=10, col=20), legal=_LEGAL,
                        board_hw=_HW, state_hash="s")
    assert ok.accepted and ok.action == {"action": "MOUSE", "row": 10, "col": 20}


def test_repeated_state_action_prevented():
    """Purpose: the same action in the same state is rejected the second time.

    Feedback: failure means the agent loops on a known-inert experiment.
    """
    g = ActionGovernor()
    req = ActionRequest("LEFT")
    first = g.check_single(req, legal=_LEGAL, board_hw=_HW, state_hash="sX")
    assert first.accepted
    g.record_executed(first.action, "sX")
    second = g.check_single(req, legal=_LEGAL, board_hw=_HW, state_hash="sX")
    assert not second.accepted and "repeated" in second.reason
    # a different state with the same action is fine.
    assert g.check_single(req, legal=_LEGAL, board_hw=_HW, state_hash="sY").accepted


def test_undo_accounting():
    """Purpose: UNDO is charged as one environment action (probe+undo = two).

    Feedback: failure means efficiency accounting under-counts undo cost.
    """
    g = ActionGovernor()
    g.record_executed({"action": "RIGHT"}, "s0")
    g.record_executed({"action": "UNDO"}, "s1")
    assert g.total_actions == 2
    assert g.undo_count == 1


def test_macro_length_gating():
    """Purpose: macros must be 2-8 steps.

    Feedback: failure means a 1-step 'macro' or an over-long batch slips through.
    """
    g = ActionGovernor()
    one = [MacroStep("LEFT", "player left of goal", "player moves left")]
    assert not g.submit_macro(one, legal=_LEGAL, board_hw=_HW).accepted


def test_macro_requires_precondition_and_invariant():
    """Purpose: every macro step must state a precondition AND a predicted
    invariant.

    Feedback: failure means speculative batches without guards are admitted — the
    exact behavior the design forbids.
    """
    g = ActionGovernor()
    steps = [
        MacroStep("LEFT", "corridor is clear", "player moves left one cell"),
        MacroStep("LEFT", "", "player moves left one cell"),  # missing precondition
    ]
    d = g.submit_macro(steps, legal=_LEGAL, board_hw=_HW)
    assert not d.accepted and "precondition" in d.reason


def test_macro_arms_and_stops_on_surprise():
    """Purpose: a valid macro arms + returns step 1; a predicted change that does
    NOT occur aborts the remaining macro (stop-on-surprise).

    Feedback: failure means the agent keeps executing a plan whose premise broke.
    """
    g = ActionGovernor()
    steps = [
        MacroStep("LEFT", "corridor clear", "board changes: player moves left"),
        MacroStep("LEFT", "corridor clear", "board changes: player moves left"),
    ]
    d = g.submit_macro(steps, legal=_LEGAL, board_hw=_HW)
    assert d.accepted and d.action == {"action": "LEFT"}
    # step 1 produced the predicted change -> continue to step 2
    assert g.observe_after(board_changed=True) == "continue"
    # step 2 predicted a change but the board did NOT change -> abort
    assert g.observe_after(board_changed=False).startswith("macro_aborted:unexpected_no_change")
    assert g.current_macro_step() is None


def test_macro_completes_and_level_complete_aborts():
    """Purpose: a fully-satisfied macro reports macro_done; a level completion
    mid-macro aborts (a terminal surprise).

    Feedback: failure means macro lifecycle transitions are wrong.
    """
    g = ActionGovernor()
    steps = [
        MacroStep("RIGHT", "path open", "player moves right"),
        MacroStep("RIGHT", "path open", "player moves right"),
    ]
    g.submit_macro(steps, legal=_LEGAL, board_hw=_HW)
    assert g.observe_after(board_changed=True) == "continue"
    assert g.observe_after(board_changed=True) == "macro_done"

    g.submit_macro(steps, legal=_LEGAL, board_hw=_HW)
    assert g.observe_after(board_changed=True, level_completed=True) == \
        "macro_aborted:level_completed"
