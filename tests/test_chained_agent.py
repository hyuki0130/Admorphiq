"""Contract tests for ChainedAgent (the 3-pass policy as one artifact).

Pin the handover semantics: probe first; a probe WIN ends the game; a probe
give-up hands over to the main agent WITHOUT ending the episode. All offline
with duck-typed fakes.
"""

from __future__ import annotations

from admorphiq.chained_agent import ChainedAgent


class _State:
    def __init__(self, name: str) -> None:
        self.name = name


class _Obs:
    def __init__(self, state: str = "NOT_FINISHED") -> None:
        self.state = _State(state)


class _Fake:
    def __init__(self, name: str, done: bool = False) -> None:
        self.name = name
        self.done = done
        self.calls = 0

    def is_done(self, frames, latest) -> bool:
        return self.done

    def choose_action(self, frames, latest):
        self.calls += 1
        return self.name


def test_probe_owns_until_giveup_then_main_takes_over():
    """Purpose: while the probe is alive it chooses actions; once it reports
    done without a WIN, the chain hands over to main and the episode CONTINUES.
    Expected feedback: pass = the cheap probe never costs the main agent its
    budgetted game; fail = probe give-up ends games the unified stack clears."""
    probe, main = _Fake("probe"), _Fake("main")
    chain = ChainedAgent(probe, main)
    obs = _Obs()
    assert not chain.is_done([], obs)
    assert chain.choose_action([], obs) == "probe"
    probe.done = True                       # probe gives up (no WIN)
    assert not chain.is_done([], obs)       # episode NOT over
    assert chain.choose_action([], obs) == "main"   # handover complete
    main.done = True
    assert chain.is_done([], obs)           # main's verdict is final


def test_probe_win_banks_the_efficient_clear():
    """Purpose: a WIN during the probe ends the game immediately — the
    efficient clear is banked and main never runs (no action pollution).
    Expected feedback: pass = arrangement-class games keep their 58-260-action
    RHAE scores; fail = the chain replays a won game and dilutes the score."""
    probe, main = _Fake("probe", done=True), _Fake("main")
    chain = ChainedAgent(probe, main)
    assert chain.is_done([], _Obs("WIN"))
    assert main.calls == 0


def test_chain_opts_into_game_over_restarts():
    """Purpose: the runner ends the game on the first GAME_OVER unless the
    agent exposes restart_on_game_over — measured: the whole solid card died
    at ~100 actions in the probe prefix (first avatar death ended the run).
    Expected feedback: pass = chained games survive deaths like unified does;
    fail = the chain silently loses every death-prone game."""
    assert ChainedAgent(_Fake("p"), _Fake("m")).restart_on_game_over is True
