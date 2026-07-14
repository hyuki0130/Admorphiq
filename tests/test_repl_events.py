"""Tests for the bench append-only event stream (R55 observability, item 2).

These lock the crash-safety contract: events are written+flushed per-event with
monotonic sequence numbers, executed actions link to their transitions via
action_id, the summary is DERIVED from the log, and a log with no terminal event
is marked run_incomplete (so a killed kernel still yields a truthful record).
"""

from __future__ import annotations

from types import SimpleNamespace

from admorphiq.repl_agent.bench import run_game
from admorphiq.repl_agent.events import EventStream, derive_summary


def _obs(state="PLAYING", levels=0):
    return SimpleNamespace(state=SimpleNamespace(name=state), levels_completed=levels)


class _FakeEnv:
    def __init__(self, game_id, script):
        self.game_id = game_id
        self.observation_space = script[0]
        self._script = script[1:]
        self._i = 0

    def step(self, action, data=None):
        obs = self._script[self._i] if self._i < len(self._script) else self._script[-1]
        self._i += 1
        return obs


class _FakeAgent:
    restart_on_game_over = True

    def is_done(self, frames, obs):
        return False

    def choose_action(self, frames, obs):
        return SimpleNamespace(action="LEFT")


def test_event_stream_seq_and_jsonl(tmp_path):
    """Purpose: emit assigns monotonic seq, timestamps, and flushes JSONL.

    Feedback: failure means a killed kernel loses events / seq ordering.
    """
    path = tmp_path / "g.events.jsonl"
    with EventStream(path) as es:
        e0 = es.emit("game_start", game_id="g")
        e1 = es.emit("transition", action_id=0, changed=True)
    assert e0["seq"] == 0 and e1["seq"] == 1
    lines = path.read_text().strip().splitlines()
    assert len(lines) == 2 and '"type":"game_start"' in lines[0]


def test_derive_summary_complete_and_incomplete():
    """Purpose: a log with a terminal derives a clean summary; one without is
    marked run_incomplete.

    Feedback: failure means the summary could silently claim a clean finish after
    a crash.
    """
    complete = [
        {"seq": 0, "type": "game_start", "game_id": "g"},
        {"seq": 1, "type": "transition", "action_id": 0, "changed": True, "level": 0},
        {"seq": 2, "type": "terminal", "reason": "win", "levels": 1},
    ]
    s = derive_summary(complete)
    assert s["run_incomplete"] is False
    assert s["levels"] == 1 and s["actions"] == 1 and s["terminal_reason"] == "win"

    incomplete = complete[:2]  # no terminal event (killed kernel)
    s2 = derive_summary(incomplete)
    assert s2["run_incomplete"] is True
    assert s2["terminal_reason"] == "incomplete"


def test_run_game_emits_correlated_events():
    """Purpose: run_game emits game_start, action_executed+transition pairs linked
    by action_id, and a terminal.

    Feedback: failure means "which action caused this transition?" is
    unanswerable from the log.
    """
    env = _FakeEnv("g", [_obs(), _obs(levels=1), _obs("WIN", levels=1)])
    es = EventStream()
    run_game(env, _FakeAgent(), max_actions=50, events=es)
    types = [e["type"] for e in es.events]
    assert types[0] == "game_start"
    assert "action_executed" in types and "transition" in types
    assert types[-1] == "terminal"
    # action_executed and its transition share an action_id.
    ae = next(e for e in es.events if e["type"] == "action_executed")
    tr = next(e for e in es.events if e["type"] == "transition")
    assert ae["action_id"] == tr["action_id"]
    # summary derived from the emitted events is consistent.
    summ = derive_summary(es.events)
    assert summ["run_incomplete"] is False and summ["terminal_reason"] == "win"
