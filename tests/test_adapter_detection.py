"""Pins for the adapter DETECTION contract (the port from game_id dispatch).

Purpose: a submission may not select a solver by game id — the 110 private games carry no
id we know — so a ported adapter must recognise its own mechanic from the frame. These
pin the two properties that make that safe, both of which were established by measurement
rather than by design.

Expected feedback: a failure means detection has become either unsafe (an adapter's
discovery code can now crash the dispatcher on a foreign board) or unported (the base
default started firing), and no adapter should be shipped under detection until it passes.
"""

from typing import Any

from admorphiq.adapters25 import discover_adapters
from admorphiq.adapters25.base import GameAdapter


def test_unported_adapters_never_fire():
    """An adapter that has not been ported must return False, not guess.

    Expected feedback: a pass means detection dispatch costs nothing for the adapters
    still waiting their turn. A failure means the default became permissive and every
    unported adapter can now hijack an unrelated board.
    """
    class Unported(GameAdapter):
        def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
            return False

        def choose_action(self, frames: list[Any], latest_frame: Any) -> Any:
            raise AssertionError("never reached")

    assert Unported._detect_mechanic(object()) is False


def test_detect_treats_a_crash_as_not_my_mechanic():
    """A detector that raises on a foreign board must read as NO, never propagate.

    This is measured, not hypothetical: ft09's ring discovery raises IndexError reading a
    glyph compass on a board with no rings. Adapter internals are entitled to assume their
    own mechanic, so the guard lives once in `detect`.

    Expected feedback: a pass means one adapter's assumptions cannot take down dispatch
    for the other 24. A failure means a single foreign board crashes the submission.
    """
    class Exploding(GameAdapter):
        @classmethod
        def _detect_mechanic(cls, latest_frame: Any) -> bool:
            raise IndexError("tuple index out of range")

        def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
            return False

        def choose_action(self, frames: list[Any], latest_frame: Any) -> Any:
            raise AssertionError("never reached")

    class _Frame:
        frame = [[[0]]]

    assert Exploding.detect(_Frame()) is False


def test_every_adapter_still_imports_and_exposes_detect():
    """Detection must exist on every adapter, ported or not.

    Expected feedback: a pass means the registry can dispatch by detection uniformly. A
    failure means an adapter is missing the contract and would be skipped silently.
    """
    adapters = discover_adapters()
    assert adapters, "the adapter registry must not be empty"
    for name, cls in adapters.items():
        assert hasattr(cls, "detect"), f"{name} has no detect()"
        assert hasattr(cls, "_detect_mechanic"), f"{name} has no _detect_mechanic()"


def test_dispatch_forwards_harness_capability_flags():
    """Purpose: pin that the wrapper exposes the flags the RUNNER reads off the agent
    object, not just the two contract methods.

    This is measured, not hypothetical. `restart_on_game_over` decides whether a
    GAME_OVER revives the attempt or ends the run, and the runner reads it with
    getattr(agent, ...). Without forwarding, lf52 lost a real level: the card scored
    0.000132 with 1 level on two runs while dispatch scored 0.0000 with 0 levels on two
    runs, deterministically, on a game where no detector even fires.

    Expected feedback: a pass means wrapping the card in dispatch cannot silently change
    how the harness drives it. A failure means capability flags are being dropped again
    and games with GAME_OVER dynamics will quietly lose levels.
    """
    from admorphiq.detect_dispatch_agent import DetectDispatchAgent

    class Fallback:
        restart_on_game_over = True

        def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
            return False

        def choose_action(self, frames: list[Any], latest_frame: Any) -> Any:
            return None

    agent = DetectDispatchAgent(Fallback())
    assert getattr(agent, "restart_on_game_over", False) is True
    assert agent.dispatched_to == "fallback"
