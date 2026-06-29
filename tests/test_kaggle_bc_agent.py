"""Tests for the official-framework KaggleBCAgent wrapper.

These pin the wiring between the official ``Agent`` contract and the composed
``BCPolicyAgent``: the wrapper must return an official ``GameAction``, surface
ACTION6 click coordinates through ``set_data`` (so the framework's
``take_action`` -> ``action_data.model_dump()`` reaches the click), and honour
the MAX_ACTIONS budget. They use a mocked policy so no model weights are
required and the test stays fast and deterministic.
"""

from __future__ import annotations

from admorphiq.adapter import AdmorphiqAdapter
from admorphiq.kaggle_bc_agent import KaggleBCAgent, _action6_data
from admorphiq.types import GameAction as InternalGameAction


def _official_action6(x: int, y: int):
    """Build a real official arcengine ACTION6 GameAction with x/y set_data."""
    return AdmorphiqAdapter._convert_action(InternalGameAction.coordinate(x, y))


def _official_simple(action_id: int):
    """Build a real official simple GameAction (no coordinates)."""
    from admorphiq.types import ActionType

    return AdmorphiqAdapter._convert_action(
        InternalGameAction.simple(ActionType(action_id))
    )


class _FakeBC:
    """Stand-in for BCPolicyAgent that returns a fixed action and never bails."""

    def __init__(self, action) -> None:
        self._loaded = True
        self._action = action
        self.calls = 0

    def choose_action(self, frames, latest_frame):
        self.calls += 1
        return self._action

    def is_done(self, frames, latest_frame) -> bool:
        return False


def _wrapper_with(bc) -> KaggleBCAgent:
    """A KaggleBCAgent with the heavy official/model init bypassed."""
    agent = object.__new__(KaggleBCAgent)
    agent._bc = bc
    agent.action_counter = 0
    agent.MAX_ACTIONS = 200
    return agent


def test_action6_data_extracts_coords_and_ignores_simple():
    """Purpose: ACTION6 click coords are recoverable from the official action.

    Expected feedback: PASS proves the BC policy's ACTION6 pick carries x/y via
    ``set_data`` and the wrapper can mirror them out; a simple action yields no
    data. FAIL means clicks would reach the env without coordinates.
    """
    a6 = _official_action6(7, 2)
    assert a6.value == 6
    assert _action6_data(a6) == {"x": 7, "y": 2}
    assert _action6_data(_official_simple(1)) is None


def test_choose_action_returns_gameaction_and_with_data_carries_coords():
    """Purpose: the wrapper delegates to the policy and exposes ACTION6 coords.

    Expected feedback: PASS proves ``choose_action`` returns the policy's
    official GameAction and ``choose_action_with_data`` returns it paired with
    the click dict — one policy step per call. FAIL means the official run-loop
    would get a wrong/typeless action or lose the click coordinates.
    """
    a6 = _official_action6(40, 12)
    bc = _FakeBC(a6)
    agent = _wrapper_with(bc)

    action = agent.choose_action([], None)
    assert action is a6
    assert action.value == 6
    assert action.action_data.x == 40 and action.action_data.y == 12

    action2, data = agent.choose_action_with_data([], None)
    assert action2 is a6
    assert data == {"x": 40, "y": 12}
    assert bc.calls == 2  # exactly one policy step per entry-point call


def test_is_done_caps_at_max_actions():
    """Purpose: the wrapper enforces its action budget over the policy.

    Expected feedback: PASS proves ``is_done`` returns True once the official
    ``action_counter`` reaches MAX_ACTIONS even when the policy would continue,
    and otherwise defers to the policy. FAIL means an unsolved game could grind
    to the framework's hard cap, tanking the squared-efficiency score.
    """
    agent = _wrapper_with(_FakeBC(_official_simple(1)))
    assert agent.is_done([], None) is False
    agent.action_counter = agent.MAX_ACTIONS
    assert agent.is_done([], None) is True
