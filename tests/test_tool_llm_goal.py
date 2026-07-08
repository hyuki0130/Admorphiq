"""Contract tests for the generic LLM goal-inference tool (transform/arrangement class).

No test touches a live ollama server: the LLM is always injected via the
``llm_chat`` constructor param, and one test proves a raising callable
degrades to an empty proposal rather than crashing.
"""

from __future__ import annotations

import numpy as np

from admorphiq.planner.goal_inference import GoalSpec, GoalType
from admorphiq.tools.llm_goal import LLMGoalTool


class _Obs:
    """Minimal FrameData-shaped stand-in (frame + available_actions)."""

    def __init__(self, frame: np.ndarray, available_actions=(1, 2, 3, 4, 6)):
        self.frame = frame
        self.available_actions = list(available_actions)
        self.state = "NOT_FINISHED"
        self.levels_completed = 0


def _transform_frames(n: int = 5, size: int = 20) -> list[_Obs]:
    """A transform/arrangement signature: a large region recolors each step
    while a 1-cell avatar stays fixed in place (mobility ~0)."""
    obs_list = []
    for i in range(n):
        g = np.zeros((size, size), dtype=np.int64)
        block_color = 1 if i % 2 == 0 else 2
        g[0:10, 0:10] = block_color  # 100 of 400 cells = 25% per transition
        g[19, 19] = 9  # stationary 1-cell avatar
        obs_list.append(_Obs(g))
    return obs_list


def _navigation_frames(n: int = 5, size: int = 20) -> list[_Obs]:
    """A navigation signature: only a small avatar moves; nothing else changes."""
    obs_list = []
    for i in range(n):
        g = np.zeros((size, size), dtype=np.int64)
        y, x = i * 3, i * 3  # 2x2 avatar block, moving each frame
        g[y : y + 2, x : x + 2] = 3
        obs_list.append(_Obs(g))
    return obs_list


def test_detect_high_on_transform_signature():
    """Purpose: detect() must recognize "big region recolors, avatar barely
    moves" as a transform/arrangement game — the class this tool targets.

    Expected feedback: pass ⇒ the orchestrator routes transform-class games to
    this tool; fail ⇒ the frontier bottleneck games never get goal inference.
    """
    frames = _transform_frames()
    tool = LLMGoalTool(llm_chat=lambda _prompt: "")
    score = tool.detect(frames[:-1], frames[-1])
    assert score >= 0.6


def test_detect_low_on_navigation_signature():
    """Purpose: detect() must NOT fire on pure navigation (small avatar moves,
    nothing else changes) — that class belongs to movement/BFS tools.

    Expected feedback: pass ⇒ no false-positive routing away from navigation
    tools; fail ⇒ this tool wastes an LLM call on games it can't help with.
    """
    frames = _navigation_frames()
    tool = LLMGoalTool(llm_chat=lambda _prompt: "")
    score = tool.detect(frames[:-1], frames[-1])
    assert score < 0.4


def test_propose_degrades_to_empty_when_llm_unreachable():
    """Purpose: if the injected LLM callable raises (network down / model
    unloaded), propose() must degrade to [] rather than crash the harness.

    Expected feedback: pass ⇒ offline-safe by construction; fail ⇒ a network
    hiccup at Kaggle-time would take down the whole agent loop.
    """
    def _boom(_prompt: str) -> str:
        raise ConnectionError("ollama unreachable")

    tool = LLMGoalTool(llm_chat=_boom)
    obs = _transform_frames(1)[0]
    steps = tool.propose([], obs)
    assert steps == []
    assert tool.goal_frame() is None


def test_propose_only_calls_llm_once_per_level():
    """Purpose: goal inference is a discovery-time call (cost control), not a
    per-action one — propose() must not re-invoke the LLM after the first call.

    Expected feedback: pass ⇒ the 9h Kaggle budget isn't burned on repeated
    per-action LLM calls; fail ⇒ cost blowup on long levels.
    """
    calls = []

    def _chat(prompt: str) -> str:
        calls.append(prompt)
        return '{"goal_type": "FILL_COLOR", "color": 5}'

    tool = LLMGoalTool(llm_chat=_chat)
    obs = _transform_frames(1)[0]
    tool.propose([], obs)
    tool.propose([], obs)
    tool.propose([], obs)
    assert len(calls) == 1


def test_propose_and_rank_use_a_cached_llm_inferred_goal():
    """Purpose: a fake LLM returning a parseable goal must be cached (visible
    via goal_frame()) and used to order candidate frames by closeness via
    rank() — the hook other tools consult.

    Expected feedback: pass ⇒ the goal-inference -> ranking pipeline works
    end-to-end without a live model; fail ⇒ other tools can't consult the
    inferred goal.
    """
    def _chat(_prompt: str) -> str:
        return '{"goal_type": "FILL_COLOR", "color": 5}'

    tool = LLMGoalTool(llm_chat=_chat)
    obs = _transform_frames(1)[0]
    tool.propose([], obs)

    goal = tool.goal_frame()
    assert goal is not None
    assert goal.goal_type is GoalType.FILL_COLOR
    assert goal.color == 5

    size = 8
    few_filled = np.zeros((size, size), dtype=np.int64)
    few_filled[0, 0] = 5  # 1 cell of the target colour
    more_filled = np.zeros((size, size), dtype=np.int64)
    more_filled[0:3, 0:3] = 5  # 9 cells of the target colour

    ranked = tool.rank([few_filled, more_filled])
    assert ranked[0] is more_filled
    assert ranked[1] is few_filled


def test_rank_is_identity_when_no_goal_cached():
    """Purpose: before any goal is inferred, rank() must return candidates
    unchanged rather than raising or silently reordering.

    Expected feedback: pass ⇒ callers can consult rank() unconditionally; fail
    ⇒ callers would need a None-check special case, defeating the hook.
    """
    tool = LLMGoalTool(llm_chat=lambda _p: "")
    a = np.zeros((4, 4), dtype=np.int64)
    b = np.ones((4, 4), dtype=np.int64)
    assert tool.rank([a, b]) == [a, b]


def test_observe_accumulates_evidence_from_consecutive_prev_frames():
    """Purpose: observe() must recover the actual per-action diff by comparing
    consecutive ``prev`` frames across calls (it never receives the post-action
    frame directly) — this is the evidence fed to the goal prompt.

    Expected feedback: pass ⇒ the LLM prompt gets real transition evidence;
    fail ⇒ goal inference runs on an empty evidence list, weakening the guess.
    """
    tool = LLMGoalTool(llm_chat=lambda _p: "")
    f0 = np.zeros((6, 6), dtype=np.int64)
    f1 = f0.copy()
    f1[0, 0] = 7
    tool.observe(f0, (6, (1, 1)), changed=True)
    tool.observe(f1, (6, (2, 2)), changed=True)
    assert len(tool._evidence) == 1
    assert tool._evidence[0]["changed_cells"] == 1
    assert tool._evidence[0]["top_new_color"] == 7
    assert tool._evidence[0]["action"] == 6


def test_reset_clears_cached_goal_and_evidence():
    """Purpose: reset() (called on level-up) must drop the cached goal and
    evidence so the next level gets a fresh inference, not a stale one.

    Expected feedback: pass ⇒ per-level goal caching is correct; fail ⇒ a goal
    from level N would wrongly leak into level N+1.
    """
    def _chat(_prompt: str) -> str:
        return '{"goal_type": "FILL_COLOR", "color": 5}'

    tool = LLMGoalTool(llm_chat=_chat)
    obs = _transform_frames(1)[0]
    tool.observe(obs.frame, (1, None), changed=False)
    tool.propose([], obs)
    assert tool.goal_frame() is not None

    tool.reset()
    assert tool.goal_frame() is None
    assert tool._evidence == []
    assert tool._goal_attempted is False


def test_no_game_ids_in_tool():
    """Purpose: the tool must be game-agnostic (generality guard) — no game id,
    title, or sprite-tag string anywhere in the module source.

    Expected feedback: pass ⇒ transfers to unseen private games; fail ⇒ a
    game-specific leak crept in and this tool would not generalize.
    """
    import admorphiq.tools.llm_goal as mod

    src = open(mod.__file__).read().lower()
    for tok in ("re86", "su15", "game_id", "game_title"):
        assert tok not in src


def test_goal_spec_import_smoke():
    """Purpose: sanity-check the test file's own GoalSpec import resolves via
    the goal_inference re-export path this tool relies on.

    Expected feedback: pass ⇒ the import surface this tool depends on is
    stable; fail ⇒ a refactor of goal_inference silently broke the tool.
    """
    spec = GoalSpec(goal_type=GoalType.FILL_COLOR, color=3)
    assert spec.goal_type is GoalType.FILL_COLOR
