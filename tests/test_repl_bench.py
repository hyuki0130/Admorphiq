"""Tests for the code-REPL bench driver (R55 Round-1 second half).

These lock the driver contract the Kaggle repl-bench kernel relies on: the action
cap and wall-clock soft deadline both terminate the game with the right reason, a
level clear / GAME_OVER are detected (with restart revival), a crashing agent is
isolated into an error record instead of killing the run, and the observability
counters are read off the agent into the diagnostics.
"""

from __future__ import annotations

from types import SimpleNamespace

from admorphiq.repl_agent.bench import (
    MATCHED_12_GAMES,
    GameDiagnostics,
    matched_run_plan,
    run_game,
    single_arm_plan,
)


def test_single_arm_plan():
    """Purpose: the full-25 extension is one audit-ON run per game.

    Feedback: failure means the full-25 run is mis-armed or duplicated.
    """
    plan = single_arm_plan(["a", "b", "c"], "on")
    assert len(plan) == 3 and all(p["arm"] == "on" and p["rep"] == 0 for p in plan)


def test_matched_run_plan():
    """Purpose: the matched experiment plan pairs OFF/ON per game and gives su15
    3 replicate pairs (Codex v8 ruling).

    Feedback: failure means the OFF/ON comparison is unbalanced or su15 lacks
    replicates.
    """
    plan = matched_run_plan(MATCHED_12_GAMES)
    assert len(plan) == 28              # 11 games x2 + su15 x6
    su15 = [p for p in plan if p["game"] == "su15"]
    assert len(su15) == 6 and sum(1 for p in su15 if p["arm"] == "on") == 3
    for g in MATCHED_12_GAMES:
        if g != "su15":
            arms = sorted(p["arm"] for p in plan if p["game"] == g)
            assert arms == ["off", "on"]


def _obs(state="PLAYING", levels=0):
    return SimpleNamespace(state=SimpleNamespace(name=state), levels_completed=levels)


class _FakeEnv:
    """Replays a scripted list of observations on each step()."""

    def __init__(self, game_id, script):
        self.game_id = game_id
        self.observation_space = script[0]
        self._script = script[1:]
        self._i = 0

    def step(self, action, data=None):
        if self._i < len(self._script):
            obs = self._script[self._i]
            self._i += 1
            return obs
        return self._script[-1] if self._script else self.observation_space


class _FakeAgent:
    """Returns a constant action; optional counters + crash injection."""

    restart_on_game_over = True

    def __init__(self, *, crash_on=None, llm_calls=0):
        self.llm_calls = llm_calls
        self.parse_failures = 0
        self.governor_rejections = 0
        self.sandbox_errors = 0
        self._n = 0
        self._crash_on = crash_on

    def is_done(self, frames, obs):
        return False

    def choose_action(self, frames, obs):
        self._n += 1
        if self._crash_on is not None and self._n >= self._crash_on:
            raise RuntimeError("boom")
        return SimpleNamespace(action="LEFT")


def test_win_terminates():
    """Purpose: a WIN observation ends the game with terminal 'win' + level count.

    Feedback: failure means clears aren't detected / scored.
    """
    env = _FakeEnv("g", [_obs(), _obs(levels=1), _obs("WIN", levels=1)])
    diag = run_game(env, _FakeAgent(), max_actions=50)
    assert diag.terminal_reason == "win"
    assert diag.levels == 1


def test_action_budget_cap():
    """Purpose: the game stops at max_actions with terminal 'budget'.

    Feedback: failure means a game could run past its action cap.
    """
    env = _FakeEnv("g", [_obs()] + [_obs() for _ in range(20)])
    diag = run_game(env, _FakeAgent(), max_actions=5)
    assert diag.terminal_reason == "budget"
    assert diag.actions == 5


def test_wall_deadline():
    """Purpose: the wall-clock soft deadline ends the game with terminal 'wall'.

    Feedback: failure means one slow game could blow the 9h / 110-game budget.
    """
    ticks = iter([0.0, 0.0, 1.0, 100.0, 200.0])  # third check crosses the deadline

    def clock():
        return next(ticks)

    env = _FakeEnv("g", [_obs()] + [_obs() for _ in range(20)])
    diag = run_game(env, _FakeAgent(), max_actions=50, wall_s=10.0, clock=clock)
    assert diag.terminal_reason == "wall"


def test_game_over_without_restart_and_with_restart():
    """Purpose: GAME_OVER ends the game when the agent doesn't restart, but is
    revived via reset_action when it does.

    Feedback: failure means restart accounting / revival is wrong.
    """
    class _NoRestart(_FakeAgent):
        restart_on_game_over = False

    env1 = _FakeEnv("g", [_obs(), _obs("GAME_OVER")])
    d1 = run_game(env1, _NoRestart(), max_actions=50)
    assert d1.terminal_reason == "game_over"

    env2 = _FakeEnv("g", [_obs(), _obs("GAME_OVER"), _obs(), _obs("WIN")])
    d2 = run_game(env2, _FakeAgent(), max_actions=50, reset_action="RESET")
    assert d2.terminal_reason == "win"


def test_agent_crash_isolated():
    """Purpose: an exception in the agent becomes an error record, not a raised
    exception that kills the whole bench run.

    Feedback: failure means one buggy game aborts all 110.
    """
    env = _FakeEnv("g", [_obs()] + [_obs() for _ in range(10)])
    diag = run_game(env, _FakeAgent(crash_on=2), max_actions=50)
    assert diag.terminal_reason == "error"
    assert "RuntimeError" in diag.error


def test_counters_passed_through():
    """Purpose: observability counters are read off the agent into diagnostics.

    Feedback: failure means the kernel's diagnostics lose the LLM/parse/governor/
    sandbox signal that debugs a run.
    """
    env = _FakeEnv("g", [_obs(), _obs("WIN")])
    agent = _FakeAgent(llm_calls=3)
    agent.governor_rejections = 2
    diag = run_game(env, agent, max_actions=50)
    assert diag.llm_calls == 3
    assert diag.governor_rejections == 2
    assert isinstance(diag.to_dict(), dict)
    assert diag.to_dict()["game_id"] == "g"


def test_diagnostics_dataclass_defaults():
    """Purpose: GameDiagnostics is JSON-serializable with sane defaults.

    Feedback: failure means diagnostics files can't be written/round-tripped.
    """
    d = GameDiagnostics(game_id="x")
    assert d.to_dict()["terminal_reason"] == ""
    assert d.to_dict()["levels"] == 0
