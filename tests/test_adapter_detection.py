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


def test_ported_sets_are_identified_by_function_not_bound_method():
    """Purpose: pin that "is this adapter ported?" compares the underlying FUNCTIONS.

    A classmethod accessed on a class yields a NEW bound object every access, so
    `cls._detect_mechanic is not GameAdapter._detect_mechanic` is always true. That
    marked all 25 adapters as ported: the dispatcher then spent a probe action on every
    board it did not statically recognise, and the false-positive gate ran every adapter
    as probe-capable — so the measurement was not checking the contract it claimed to.

    Expected feedback: a pass means only genuinely ported adapters are dispatched to or
    probed for. A failure means the identity test has regressed to the bound form and the
    probe is being spent on games nothing can claim.
    """
    from admorphiq.detect_dispatch_agent import DetectDispatchAgent

    class Fallback:
        def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
            return False

        def choose_action(self, frames: list[Any], latest_frame: Any) -> Any:
            return None

    agent = DetectDispatchAgent(Fallback())
    everything = set(discover_adapters())
    assert set(agent._ported) < everything, "not every adapter is statically ported"
    assert set(agent._probed) < everything, "not every adapter is probe-ported"
    assert set(agent._ported) & set(agent._probed) == set(), (
        "an adapter should read statically OR ask for the probe, not both"
    )


def test_probe_is_armed_and_read_in_separate_steps():
    """Purpose: pin that the probe is READ only after it has actually been SPENT.

    The runner calls is_done and choose_action with the SAME frame in one iteration. A
    version that read the probe as soon as it was armed compared a frame with itself, saw
    no displacement, and fell back on every board — measured, dispatched_to stayed
    "fallback" for a whole m0r0 run that should have scored 1.0000.

    Expected feedback: a pass means arming and reading are separate states, so a probe
    detector sees a genuine transition. A failure means the probe is being read against
    its own before-frame and every probe port is silently dead.
    """
    from admorphiq.detect_dispatch_agent import DetectDispatchAgent

    class Fallback:
        def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
            return False

        def choose_action(self, frames: list[Any], latest_frame: Any) -> Any:
            return None

    class Frame:
        state = None
        frame = [[[0, 0], [0, 0]]]
        available_actions = [1, 2, 3, 4]

    agent = DetectDispatchAgent(Fallback())
    frame = Frame()
    assert agent.is_done([], frame) is False          # arms the probe
    assert agent._probe_sent is False, "arming must not count as spending"
    agent.choose_action([], frame)                    # spends it
    assert agent._probe_sent is True


def test_shipped_measurement_refuses_a_silent_env_override():
    """Purpose: pin that measuring "as shipped" REFUSES when the environment overrides a
    deployed default.

    The wrapper uses os.environ.setdefault, which respects an existing value, so a runner
    exporting GF_GIVEUP=100000 measured a 100,000-action budget and called it the shipped
    card. The benched-vs-shipped comparison could not catch it: both sides inherited the same
    export, and a comparison is only as good as the axis it varies. The tell sat in the Kaggle
    server run for hours — cn04 clearing L1 at 56,048 actions locally against 9,358 and zero
    levels on the server.

    Expected feedback: a pass means a shipped-configuration measurement cannot be silently
    retuned by the environment. A failure means that class of number can reappear, and it
    reappears looking correct.
    """
    import subprocess
    import sys

    env = {"PATH": "/usr/bin:/bin", "GF_GIVEUP": "100000", "HOME": "/tmp"}
    result = subprocess.run(
        [sys.executable, "scripts/score_efficiency.py", "--agent", "kaggle_detect",
         "--titles", "ft09", "--max-actions", "1", "--out", "/tmp/_pin.json"],
        capture_output=True, text=True, env=env,
    )
    combined = result.stdout + result.stderr
    assert "GF_GIVEUP" in combined and "DEPLOYED" in combined, combined[-400:]
