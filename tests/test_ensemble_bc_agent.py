"""Tests for the EnsembleBCAgent efficient-first / coverage-fallback switch.

These pin the routing contract between the two BC sub-policies WITHOUT loading
any real model weights — sub-agents are mocked so the test isolates the switch
decision (when to abandon the efficient policy for the coverage policy).
"""

from admorphiq.ensemble_bc_agent import EnsembleBCAgent


class _FakeObs:
    """Minimal arcengine-observation stand-in (state name + levels_completed)."""

    def __init__(self, levels: int = 0, state: str = "PLAYING") -> None:
        self.levels_completed = levels
        self.state = type("S", (), {"name": state})()


class _FakeSub:
    """Stand-in BC sub-agent recording calls and exposing the give-up flag."""

    def __init__(self, action: str) -> None:
        self._action = action
        self._give_up = False
        self.calls = 0
        self.reset_calls = 0

    def choose_action(self, frames, latest_frame):
        self.calls += 1
        return self._action

    def is_done(self, frames, latest_frame):
        return self._give_up

    def _reset_action(self):
        self.reset_calls += 1
        return "RESET"


def _make(probe_budget: int = 5) -> tuple[EnsembleBCAgent, _FakeSub, _FakeSub]:
    eff, cov = _FakeSub("V3"), _FakeSub("V2")
    agent = EnsembleBCAgent(probe_budget=probe_budget, efficient=eff, coverage=cov)
    return agent, eff, cov


def test_stays_on_efficient_while_clearing():
    """Purpose: prove a clearing efficient policy is never abandoned.

    Expected feedback: PASS proves that as long as v3 keeps incrementing
    levels_completed the ensemble keeps routing to v3 (its efficient, ~1.0-score
    path) and never resets or switches. FAIL means an efficient clear would be
    thrown away and re-run by the bloated coverage policy.
    """
    agent, eff, cov = _make(probe_budget=3)
    # Each call clears another level, so the per-level probe budget keeps resetting.
    for lvl in range(1, 6):
        action = agent.choose_action([], _FakeObs(levels=lvl))
        assert action == "V3"
    assert not agent._switched
    assert cov.calls == 0
    assert eff.reset_calls == 0
    assert agent.last_hypothesis == "efficient(v3)"


def test_switches_to_coverage_after_probe_budget():
    """Purpose: prove a stalled efficient policy hands off to coverage via RESET.

    Expected feedback: PASS proves that after probe_budget non-clearing actions
    the ensemble emits exactly one RESET and routes all subsequent actions to the
    coverage policy — capturing v2's coverage where v3 cannot clear. FAIL means
    the agent would burn the whole game budget on the failing efficient policy.
    """
    agent, eff, cov = _make(probe_budget=3)
    # Three probe actions stay on v3 (levels never advance from 0).
    for _ in range(3):
        assert agent.choose_action([], _FakeObs(levels=0)) == "V3"
    assert not agent._switched
    # The 4th call exceeds the budget → switch: one RESET, then coverage drives.
    assert agent.choose_action([], _FakeObs(levels=0)) == "RESET"
    assert agent._switched
    assert eff.reset_calls == 1
    assert agent.choose_action([], _FakeObs(levels=0)) == "V2"
    assert cov.calls == 1
    assert "coverage(v2)" in agent.last_hypothesis


def test_proven_efficient_gets_wider_budget_on_later_levels():
    """Purpose: prove an efficient policy that cleared a level earns a wider budget.

    Expected feedback: PASS proves that after v3 clears level 1 (under the tight
    initial budget) it is allowed MORE probe actions on later levels before
    fallback — capturing legitimately-slower v3 clears (e.g. M0R0 L2 ~25 actions)
    instead of abandoning a proven solver. FAIL means the tight initial cap would
    prematurely hand a winning game to the bloated coverage policy.
    """
    agent, eff, cov = _make(probe_budget=2)
    agent.PROBE_BUDGET_PROVEN = 10  # widen the post-proof budget for the test
    # First observation establishes the level-0 baseline (game start).
    assert agent.choose_action([], _FakeObs(levels=0)) == "V3"
    # Level 1 clears on the 2nd action (within the tight initial budget of 2).
    assert agent.choose_action([], _FakeObs(levels=1)) == "V3"
    assert agent._proven
    # On level 2 the proven (wider) budget applies: 5 non-clearing actions all
    # stay on v3 — they would have exceeded the initial budget of 2.
    for _ in range(5):
        assert agent.choose_action([], _FakeObs(levels=1)) == "V3"
    assert not agent._switched


def test_proven_stall_continues_coverage_without_reset():
    """Purpose: prove a proven-then-stalled game hands off WITHOUT a RESET.

    Expected feedback: PASS proves that once v3 has cleared a level, a later stall
    switches to the coverage policy IN PLACE (no RESET) so it continues the current
    level instead of replaying the cleared ones — the CD82-style hybrid where v3
    does the early level and v2 finishes. FAIL means a RESET would re-run cleared
    levels and charge those actions to the next level's squared-efficiency score.
    """
    agent, eff, cov = _make(probe_budget=2)
    agent.PROBE_BUDGET_PROVEN = 3
    assert agent.choose_action([], _FakeObs(levels=0)) == "V3"  # baseline
    assert agent.choose_action([], _FakeObs(levels=1)) == "V3"  # clears L1 → proven
    # Proven budget (3) lets two more non-clearing actions ride on v3 …
    for _ in range(2):
        assert agent.choose_action([], _FakeObs(levels=1)) == "V3"
    # … then the next exceeds it: switch to coverage IN PLACE (no RESET emitted).
    assert agent.choose_action([], _FakeObs(levels=1)) == "V2"
    assert agent._switched
    assert eff.reset_calls == 0
    assert "continuing" in agent.last_hypothesis


def test_switches_when_efficient_gives_up_early():
    """Purpose: prove the efficient sub-agent's own give-up triggers fallback.

    Expected feedback: PASS proves that if v3's cycle detector sets ``_give_up``
    before the probe budget is exhausted, the ensemble switches immediately rather
    than waiting out the budget. FAIL means a hopeless v3 loop would waste actions.
    """
    agent, eff, cov = _make(probe_budget=100)
    assert agent.choose_action([], _FakeObs(levels=0)) == "V3"
    eff._give_up = True
    assert agent.choose_action([], _FakeObs(levels=0)) == "RESET"
    assert agent._switched
    assert "give_up" in agent.last_hypothesis


def test_is_done_reports_win_and_defers_to_coverage():
    """Purpose: prove is_done is WIN-aware and only consults coverage post-switch.

    Expected feedback: PASS proves a WIN state ends the game regardless of active
    policy, and that while the efficient policy is active the ensemble never ends
    the game early (a stall switches instead of finishing). FAIL means a v3 give-up
    could terminate the game before coverage ever runs. After switching, the
    coverage sub-agent's give-up cap governs is_done.
    """
    agent, eff, cov = _make(probe_budget=3)
    eff._give_up = True
    # Efficient active: not done despite eff give-up (we will switch, not finish).
    assert agent.is_done([], _FakeObs(levels=0, state="PLAYING")) is False
    # WIN always ends.
    assert agent.is_done([], _FakeObs(levels=1, state="WIN")) is True
    # After a forced switch, is_done defers to the coverage sub-agent.
    agent._switched = True
    cov._give_up = True
    assert agent.is_done([], _FakeObs(levels=0, state="PLAYING")) is True
