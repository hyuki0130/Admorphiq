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


def test_max_actions_is_a_per_game_budget_not_a_run_total():
    """Purpose: pin that the deployed MAX_ACTIONS bounds ONE game, not the whole run.

    The wrapper stops on `self.action_counter >= MAX_ACTIONS`, and the budget was just cut from
    100,000 to 4,000. If that counter accumulated across games, 4,000 would end the entire
    submission after the first game or two — and local scoring would never show it, because
    scripts/score_efficiency.py drives the agent through its own loop and never touches the
    wrapper's counter.

    Expected feedback: a pass means the notebook builds a fresh agent per game and the counter
    starts at zero each time, so the cap is per-game. A failure means the submission would
    silently score near zero on everything after the first game.
    """
    from pathlib import Path

    notebook = Path("notebooks/kaggle_submission.py").read_text()
    loop = notebook[notebook.index("for game_id in"):]
    construct = loop.index("AVAILABLE_AGENTS[AGENT_KEY](")
    run = loop.index("agent.main()")
    assert construct < run, "the agent must be constructed INSIDE the per-game loop"

    base = Path("ARC-AGI-3-Agents/agents/agent.py").read_text()
    assert "action_counter: int = 0" in base, (
        "action_counter must be an instance field initialised per agent"
    )


def test_the_deployed_cap_actually_fires():
    """Purpose: execute the deployed MAX_ACTIONS path, which no local card measurement touches.

    There are TWO capping mechanisms and only one of them ships. The local measurement caps via
    `score_efficiency.py --max-actions`, which ends the runner's loop; the submission caps via
    `KaggleDetectAgent.is_done` returning True at MAX_ACTIONS. `--agent kaggle_detect` builds
    `build_detect()`, which returns the DISPATCHER — the wrapper carrying MAX_ACTIONS is never
    constructed locally, so cutting the budget from 100,000 to 4,000 was verified against a
    mechanism that does not ship.

    Expected feedback: a pass means the deployed cap stops a game at its budget and not before.
    A failure means the submission either never stops (9-hour risk returns) or stops early
    (score lost), and neither would show up in any local score.
    """
    from admorphiq.kaggle_detect_agent import KaggleDetectAgent

    class Frame:
        state = None
        frame = [[[0, 0], [0, 0]]]
        available_actions = [1, 2, 3, 4]

    class Stub:
        def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
            return False

        def choose_action(self, frames: list[Any], latest_frame: Any) -> Any:
            return None

    agent = KaggleDetectAgent.__new__(KaggleDetectAgent)  # the official __init__ needs an env
    agent._agent = Stub()

    cap = KaggleDetectAgent.MAX_ACTIONS
    agent.action_counter = 0
    assert agent.is_done([], Frame()) is False
    agent.action_counter = cap - 1
    assert agent.is_done([], Frame()) is False, "the cap must not fire before the budget"
    agent.action_counter = cap
    assert agent.is_done([], Frame()) is True, "the cap must fire at the budget"


def test_the_deployed_budget_fits_the_competition_time_limit():
    """Purpose: pin that the per-game budget, times the hidden game count, fits in 9 hours.

    MAX_ACTIONS bounds ONE game. What the competition bounds is the WHOLE run, and nothing
    connected the two until a submission had been pending for eight hours. The arithmetic,
    from this repo's own measurements:

        rate            51 actions/sec   (148,018 actions in 48.4 minutes over 25 games)
        hidden games   110               (project_kaggle_eval_and_metric)
        limit            9 hours

        100,000/game -> 11,000,000 actions -> 59.9 hours   the SUBMITTED card
          4,000/game ->    440,000 actions ->  2.4 hours   the current card

    Expected feedback: a pass means a card cannot be shipped with a budget whose worst case
    exceeds the limit. A failure means the run can be killed by the clock, which scores zero on
    everything regardless of how good the agent is — the one failure mode that no local score
    and no amount of card measurement can reveal.
    """
    from admorphiq.kaggle_detect_agent import KaggleDetectAgent

    actions_per_second = 51      # measured, 25-game server run
    hidden_games = 110           # the evaluation set
    # ⚠️ 9 hours is what CLAUDE.md records from the 2026-06-25 overview, and it is IN DOUBT for
    # this kernel: submission 55774529 (a CPU kernel, enable_gpu false) passed nine hours still
    # PENDING. Either the figure does not apply to CPU notebooks, or the scoring re-run is
    # bounded differently, or the status lagged a failure. The guard's SHAPE — multiply the
    # per-game cap by the evaluation set at the measured rate, compare to the platform's limit —
    # holds regardless; only this constant is unverified, and it is deliberately the
    # conservative reading.
    limit_hours = 9

    worst_case_hours = (
        KaggleDetectAgent.MAX_ACTIONS * hidden_games / actions_per_second / 3600
    )
    assert worst_case_hours < limit_hours, (
        f"per-game budget {KaggleDetectAgent.MAX_ACTIONS:,} projects to "
        f"{worst_case_hours:.1f}h over {hidden_games} games at {actions_per_second} actions/sec, "
        f"past the {limit_hours}h limit"
    )


def test_dispatch_bails_to_the_fallback_when_the_adapter_clears_nothing():
    """Purpose: pin that a WRONG dispatch cannot cost a whole game.

    A dispatch is decided from one frame and was never revisited, so a detector firing on
    an unseen private game spent that game's entire budget on a mechanic the board does not
    have — and the fallback, which would have scored something, never ran. The public 25
    cannot show this because every detector is gated to 0/24 there.

    Expected feedback: a pass means an adapter that has cleared no level within
    _BAIL_ACTIONS hands the remaining budget back to the fallback. A fail means one wrong
    detection again costs the whole game.
    """
    from admorphiq.detect_dispatch_agent import _BAIL_ACTIONS, DetectDispatchAgent

    class Stub:
        def __init__(self, name):
            self.name = name
            self.calls = 0

        def is_done(self, frames, latest_frame):
            return False

        def choose_action(self, frames, latest_frame):
            self.calls += 1
            return self.name

    class Frame:
        levels_completed = 0

    fallback, adapter = Stub("fallback"), Stub("adapter")
    agent = DetectDispatchAgent(fallback)
    agent._chosen = adapter

    frame = Frame()
    for _ in range(_BAIL_ACTIONS - 1):
        assert agent.choose_action([], frame) == "adapter"
    assert agent.choose_action([], frame) == "fallback", "did not bail at the threshold"
    assert agent.choose_action([], frame) == "fallback", "bail must be permanent"


def test_the_bail_threshold_clears_every_dispatched_public_game():
    """Purpose: pin that the bail is a NO-OP on the public 25.

    The threshold is a measurement, not a preference: among the thirteen dispatched public
    games the slowest first clear is sc25 at 461 actions and every other is <= 25. Games
    slower than that (lf52 377, tu93 696, vc33 3656) run the FALLBACK, which the bail
    cannot touch.

    Expected feedback: a pass means no dispatched public game can trip the bail, so the
    card is unchanged. A fail means the threshold was lowered below a real clear and the
    public card is about to regress.
    """
    from admorphiq.detect_dispatch_agent import _BAIL_ACTIONS

    slowest_dispatched_first_clear = 461  # sc25, measured in scripts/rounds/R99CARD4
    assert _BAIL_ACTIONS > slowest_dispatched_first_clear
