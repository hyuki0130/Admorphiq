"""Offline tests for the UnifiedAgent retry loop (harness/loop.py).

Purpose: prove the self-improving loop's control flow — tool selection from the
LLM, queue refill, transition feedback to every tool, stall-triggered
re-decision, and per-level reset — works without a network or arcengine, using
fake tools and a fake LLM.
Expected feedback: a pass means the orchestration spine is correct and any
game-clearing shortfall is a tool-quality issue, not a loop bug; a failure
localises the defect to the loop itself.
"""

from __future__ import annotations

import numpy as np
import pytest

from admorphiq.harness.loop import UnifiedAgent
from admorphiq.tools.base import Step


class _State:
    def __init__(self, name: str) -> None:
        self.name = name


class _Obs:
    """Duck-typed observation matching the adapter API readers."""

    def __init__(self, grid: np.ndarray, actions: list[int], levels: int = 0,
                 state: str = "NOT_FINISHED") -> None:
        self.frame = [grid.tolist()]
        self.available_actions = actions
        self.levels_completed = levels
        self.state = _State(state)


class _FakeTool:
    """Records lifecycle calls; proposes a fixed legal step."""

    def __init__(self, name: str, step: Step, confidence: float = 0.5) -> None:
        self.name = name
        self._step = step
        self._conf = confidence
        self.observed = 0
        self.resets = 0
        self.proposed = 0

    def detect(self, frames, obs) -> float:
        return self._conf

    def reset(self) -> None:
        self.resets += 1

    def observe(self, prev, action, changed) -> None:
        self.observed += 1

    def propose(self, frames, obs):
        self.proposed += 1
        return [self._step]


def _agent(tools, choice: str):
    """Build an agent whose fake LLM always picks ``choice``."""
    def llm(messages):
        return f'{{"mode":"tool","tool":"{choice}"}}'
    return UnifiedAgent(tools, llm, giveup=1000, stall=3)


def test_llm_tool_choice_drives_refill():
    """Purpose: the LLM's chosen tool is the one asked to propose the queue.
    Expected feedback: pass = decision->tool->propose wiring is intact."""
    grid = np.zeros((64, 64), dtype=np.int64)
    up = _FakeTool("graph", (1, None), 0.9)
    click = _FakeTool("paint", (6, (10, 10)), 0.4)
    agent = _agent([up, click], "paint")
    agent.choose_action([], _Obs(grid, [1, 2, 3, 4, 6]))
    assert click.proposed == 1 and up.proposed == 0
    assert "paint" in agent._tried


def test_transition_feedback_reaches_only_the_active_tool():
    """Purpose: a transition is fed to observe() ONLY on the tool that chose the
    action, not every tool — feeding all pollutes a stateful tool's model with
    another tool's actions (measured to break the graph tool in the harness).
    Expected feedback: pass = each tool learns from only its own actions; fail =
    cross-tool pollution corrupts graph/world-model state."""
    g = np.zeros((64, 64), dtype=np.int64)
    t1 = _FakeTool("graph", (1, None), 0.9)          # the picked (active) tool
    t2 = _FakeTool("world_model", (2, None), 0.8)    # never active
    agent = _agent([t1, t2], "graph")
    agent.choose_action([], _Obs(g, [1, 2, 3, 4]))       # step 1, no prev yet
    g2 = g.copy()
    g2[0, 0] = 5
    agent.choose_action([], _Obs(g2, [1, 2, 3, 4]))      # step 2 records transition
    assert t1.observed == 1 and t2.observed == 0


def test_level_up_resets_all_tools():
    """Purpose: a level transition resets tool state and clears the queue.
    Expected feedback: pass = per-level learning does not leak across levels."""
    g = np.zeros((64, 64), dtype=np.int64)
    tool = _FakeTool("graph", (1, None), 0.9)
    agent = _agent([tool], "graph")
    agent.choose_action([], _Obs(g, [1, 2, 3, 4], levels=0))
    before = tool.resets
    agent.choose_action([], _Obs(g, [1, 2, 3, 4], levels=1))
    # level-up resets every tool (plus a switch-reset when it is re-picked clean)
    assert tool.resets >= before + 1
    assert agent._last_levels == 1


def test_stall_triggers_redecision():
    """Purpose: after `stall` inert actions the loop re-decides (re-proposes).
    Expected feedback: pass = the loop escapes a dead tool instead of looping."""
    g = np.zeros((64, 64), dtype=np.int64)  # frame never changes -> every action inert
    tool = _FakeTool("graph", (1, None), 0.9)
    agent = _agent([tool], "graph")
    for _ in range(6):
        agent.choose_action([], _Obs(g, [1, 2, 3, 4]))
    # stall=3 -> at least two refills beyond the initial one
    assert tool.proposed >= 2


def test_agent_restarts_on_game_over():
    """Purpose: the agent must expose restart_on_game_over=True so the score
    harness revives the env on death and the agent gets its full per-game budget.
    Expected feedback: pass = deep-level games run to budget; fail = the game
    stops at the first avatar death (tens of actions, measured 0)."""
    tool = _FakeTool("graph", (1, None), 0.9)
    agent = _agent([tool], "graph")
    assert getattr(agent, "restart_on_game_over", False) is True


def test_progressing_tool_does_not_call_llm_every_action():
    """Purpose: while the current tool keeps changing the frame, the queue may
    empty each step but the LLM is consulted only at decision boundaries, not per
    action — the latency bound the SWA-cache finding (r53) demands.
    Expected feedback: pass = LLM-call rate is bounded; fail = a per-action LLM
    call would blow the 9h/110-game budget."""
    calls = {"n": 0}

    def counting_llm(messages):
        calls["n"] += 1
        return '{"mode":"tool","tool":"graph"}'

    # a tool that proposes ONE step at a time -> queue empties every action
    tool = _FakeTool("graph", (1, None), 0.9)
    agent = UnifiedAgent([tool], counting_llm, giveup=1000, stall=50)
    g = np.zeros((64, 64), dtype=np.int64)
    for i in range(10):
        gi = g.copy()
        gi[0, i] = 1  # every action changes the frame (progress)
        agent.choose_action([], _Obs(gi, [1, 2, 3, 4]))
    # 10 progressing actions, stall=50 never hit -> exactly one decision (the first)
    assert calls["n"] == 1
    assert tool.proposed >= 5  # tool refilled repeatedly WITHOUT the LLM


def test_stalled_tool_is_retired_and_swapped():
    """Purpose: a tool that reaches no new state for `stall` steps is retired for
    the level; the next decision must pick a DIFFERENT tool even if the LLM
    keeps naming the failed one — the architecture's swap-on-failure behavior.
    Expected feedback: pass = the loop escapes a wandering wrong tool; fail = it
    re-picks the proven-failed tool and burns the whole budget (the cd82 bug)."""
    # LLM always names 'paint'; once paint is retired, the loop must swap to graph.
    # Both tools are LOW-confidence (< primary-owns threshold) so the stall-swap
    # applies — a high-confidence tool would instead OWN the game (tested below).
    def stubborn_llm(messages):
        return '{"mode":"tool","tool":"paint"}'

    graph = _FakeTool("graph", (1, None), 0.5)
    paint = _FakeTool("paint", (6, (5, 5)), 0.4)
    agent = UnifiedAgent([graph, paint], stubborn_llm, giveup=1000, stall=3)
    g = np.zeros((64, 64), dtype=np.int64)  # frame never gains a NEW state
    for _ in range(8):
        agent.choose_action([], _Obs(g, [1, 2, 3, 4, 6]))
    assert "paint" in agent._failed          # paint stalled and was retired
    assert graph.proposed >= 1               # the loop swapped to graph despite the LLM


def test_confident_primary_owns_game_and_is_not_retired():
    """Purpose: a tool whose frame-based detect() is high (>= primary threshold)
    OWNS the game — it is NOT retired on a stall, so it gets the FULL budget it
    needs to clear (the graph tool clears m0r0/vc33 alone but was retired after
    one tenure inside the harness).
    Expected feedback: pass = the right tool runs uninterrupted; fail = a strong
    tool is swapped away mid-solve and the harness underperforms the tool alone."""
    def llm(messages):
        return '{"mode":"tool","tool":"graph"}'

    graph = _FakeTool("graph", (1, None), 0.9)   # confident primary
    other = _FakeTool("paint", (6, (5, 5)), 0.3)
    agent = UnifiedAgent([graph, other], llm, giveup=1000, stall=3)
    g = np.zeros((64, 64), dtype=np.int64)        # never a NEW state -> would stall
    for _ in range(12):
        agent.choose_action([], _Obs(g, [1, 2, 3, 4, 6]))
    assert "graph" not in agent._failed           # primary was never retired
    assert other.proposed == 0                    # no swap away from the primary


def test_target_frame_drawn_and_injected_after_warmup():
    """Purpose: once per level, after warmup, the loop asks the LLM to DRAW the
    solved board and injects a VALID draw into the active graph-like tool via
    set_target_frame — the productized richer-goal lever (measured to crack cd82).
    Expected feedback: pass = the deployed harness carries the targetgrid
    breakthrough; fail = it lives only in the diagnostic probe."""
    calls: dict = {}

    class _FakeGraph(_FakeTool):
        def set_target_frame(self, target, res=8):
            calls["target"] = target
            calls["res"] = res

    # A valid 8x8 draw: two colours (0/3), both in the frame's palette, and
    # different from the current downsample.
    grid_txt = "\n".join(
        " ".join("3" if (i + j) % 2 == 0 else "0" for j in range(8)) for i in range(8)
    )

    def llm(messages):
        if "SOLVED board" in messages[-1]["content"]:
            return grid_txt
        return '{"mode":"tool","tool":"graph"}'

    tool = _FakeGraph("graph", (1, None), 0.9)
    agent = UnifiedAgent([tool], llm, giveup=1000, stall=50)
    g = np.zeros((64, 64), dtype=np.int64)
    g[0, 0] = 3  # palette = {0, 3} so the drawn target passes validation
    for i in range(45):
        gi = g.copy()
        gi[1, i % 60] = 3  # every action changes the frame (no stall)
        agent.choose_action([], _Obs(gi, [1, 2, 3, 4]))
    assert "target" in calls and calls["res"] == 8


def test_redraw_gated_on_target_stall():
    """Purpose: after the first draw, further draws must NOT overwrite a target
    whose pursuit is still improving (target_stalled() False) and MUST fire once
    the tool reports a stall — blind periodic redraws measurably replaced good
    targets mid-pursuit (harness cd82 0/4 vs single-draw probe 2/3).
    Expected feedback: pass = a paying-off target is pursued to the end and a
    dead one is replaced; fail = the overwrite bug is back (or stalled targets
    are never refreshed)."""
    draws: list = []

    class _FakeGraph(_FakeTool):
        stalled = False

        def set_target_frame(self, target, res=8):
            draws.append(res)

        def target_stalled(self, window):
            return self.stalled

    grid_txt = "\n".join(
        " ".join("3" if (i + j) % 2 == 0 else "0" for j in range(8)) for i in range(8)
    )

    def llm(messages):
        if "SOLVED board" in messages[-1]["content"]:
            return grid_txt
        return '{"mode":"tool","tool":"graph"}'

    tool = _FakeGraph("graph", (1, None), 0.9)
    agent = UnifiedAgent([tool], llm, giveup=5000, stall=10_000)
    g = np.zeros((64, 64), dtype=np.int64)
    g[0, 0] = 3
    step = 0

    def act():
        nonlocal step
        gi = g.copy()
        gi[1 + (step // 60) % 60, step % 60] = 3  # always a fresh frame (no stall)
        agent.choose_action([], _Obs(gi, [1, 2, 3, 4]))
        step += 1

    for _ in range(460):   # past warmup(40) + redraw gap(400)
        act()
    assert len(draws) == 1  # progressing target was never overwritten

    tool.stalled = True
    for _ in range(5):
        act()
    assert len(draws) == 2  # stalled target got refreshed


def test_clear_evidence_captured_and_cited_in_next_level_draw():
    """Purpose: at level-up the loop captures the just-cleared level's final board
    (game-scoped, survives per-level reset), and the NEXT level's target draw
    cites it as a solved-example analogy — evidence-based goal inference, the
    direct attack on the measured wall (inference accuracy, not representation).
    Expected feedback: pass = later levels draw with real evidence; fail = every
    level's draw stays blind and deep levels stay locked."""
    prompts: list = []

    class _FakeGraph(_FakeTool):
        def set_target_frame(self, target, res=8):
            pass

    grid_txt = "\n".join(
        " ".join("3" if (i + j) % 2 == 0 else "0" for j in range(8)) for i in range(8)
    )

    def llm(messages):
        content = messages[-1]["content"]
        if "SOLVED board" in content:
            prompts.append(content)
            return grid_txt
        return '{"mode":"tool","tool":"graph"}'

    tool = _FakeGraph("graph", (1, None), 0.9)
    agent = UnifiedAgent([tool], llm, giveup=5000, stall=10_000)
    g = np.zeros((64, 64), dtype=np.int64)
    g[0, 0] = 3
    # Level 0: run past warmup (first draw fires blind), then level-up.
    for i in range(45):
        gi = g.copy()
        gi[1, i % 60] = 3
        agent.choose_action([], _Obs(gi, [1, 2, 3, 4]))
    assert prompts and "PREVIOUS level" not in prompts[0]   # level-1 draw is blind
    agent.choose_action([], _Obs(g, [1, 2, 3, 4], levels=1))  # level-up
    assert len(agent._clear_frames) == 1                     # evidence captured
    # Level 1: run past warmup again -> the new draw must cite the evidence.
    for i in range(45):
        gi = g.copy()
        gi[2, i % 60] = 3
        agent.choose_action([], _Obs(gi, [1, 2, 3, 4], levels=1))
    assert len(prompts) >= 2 and "PREVIOUS level" in prompts[-1]


def test_llm_failure_falls_back_to_signature_default():
    """Purpose: if the LLM raises, the highest-detect tool is used (offline-safe).
    Expected feedback: pass = the agent never crashes when the model is down."""
    g = np.zeros((64, 64), dtype=np.int64)
    hi = _FakeTool("graph", (1, None), 0.95)
    lo = _FakeTool("paint", (6, (5, 5)), 0.1)

    def broken_llm(messages):
        raise RuntimeError("ollama down")

    agent = UnifiedAgent([hi, lo], broken_llm, giveup=1000, stall=3)
    agent.choose_action([], _Obs(g, [1, 2, 3, 4, 6]))
    assert hi.proposed == 1 and lo.proposed == 0


if __name__ == "__main__":
    pytest.main([__file__, "-q"])


def test_code_escalation_after_persistent_nochurn_stall():
    """Purpose: when the owning tool makes no new-state progress for 3 stall
    windows and no better tool exists, the CODE path must get a tenure
    MECHANICALLY — measured: the model never chooses {"mode":"code"} (0 picks
    across every wall bench) and the no-churn policy otherwise runs the stalled
    tool to the end of the budget, so the code loop never executes at all.

    Expected feedback: pass = wall games eventually exercise code synthesis;
    fail = the refine loop is dead code and wall benches only measure graph.
    """
    g = np.zeros((64, 64), dtype=np.int64)
    calls = {"code": 0}

    def llm(messages):
        body = messages[-1]["content"] if isinstance(messages, list) else str(messages)
        if "```python" in body or "python block" in body:
            calls["code"] += 1
            return "```python\nact('UP')\n```"
        return '{"mode":"tool","tool":"graph"}'

    tool = _FakeTool("graph", (1, None), 0.9)   # owns the game, never progresses
    agent = UnifiedAgent([tool], llm, giveup=1000, stall=3)
    for _ in range(11):                          # static grid -> no novelty
        agent.choose_action([], _Obs(g, [1, 2, 3, 4]))
    assert agent._current == "code"              # escalation fired (3 windows)
    assert calls["code"] >= 1                    # a real code prompt was asked
    for _ in range(26):                          # code also stalls (short
        agent.choose_action([], _Obs(g, [1, 2, 3, 4]))   # _CODE_STALL window)...
    assert "code" in agent._failed               # ...and retires normally
    assert agent._current == "graph"             # tools resume (full lifecycle)
