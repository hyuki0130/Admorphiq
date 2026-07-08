"""Contract tests for the generic online world-model tool.

These pin the tool's three load-bearing behaviours: it learns transitions from
the agent's own probes, it exploits a learned high-progress action, and its
detect confidence tracks how deterministic the observed dynamics are. The world
is synthetic (small numpy frames + a duck-typed fake obs) so the model's logic is
exercised without any game-internal access.
"""

from __future__ import annotations

import numpy as np

from admorphiq.tools.world_model import WorldModelTool


class _State:
    def __init__(self, name: str) -> None:
        self.name = name


class _Obs:
    """Duck-typed stand-in for the arcengine observation the readers expect."""

    def __init__(self, frame, actions, levels=0, state="NOT_FINISHED"):
        self.frame = [np.asarray(frame)]
        self.available_actions = list(actions)
        self.levels_completed = int(levels)
        self.state = _State(state)


def _one_object(size: int = 8) -> np.ndarray:
    """Background frame with a single foreground object (progress = 1)."""
    f = np.zeros((size, size), dtype=np.int64)
    f[1, 1] = 3
    return f


def _two_objects(size: int = 8) -> np.ndarray:
    """Background frame with two foreground objects (progress = 2)."""
    f = np.zeros((size, size), dtype=np.int64)
    f[1, 1] = 3
    f[5, 5] = 4
    return f


def _objects(n: int, size: int = 16) -> np.ndarray:
    """A background frame carrying ``n`` distinct foreground objects.

    Used where the frame must have genuine learnable STRUCTURE (several
    objects), as a real game the world model fits would — the number of objects
    also serves as the frame-only progress value.
    """
    f = np.zeros((size, size), dtype=np.int64)
    for i in range(n):
        f[2 * i + 1, 1] = 3 + i
    return f


def test_observe_populates_the_model():
    """Purpose: observe() must record the transition just taken into the online
    table — occurrence count and change flag — so the model actually learns from
    the agent's probes.

    Expected feedback: pass ⇒ the tool accumulates a per-(state, action) model
    from interaction; fail ⇒ observe is a no-op and nothing can be planned.
    """
    tool = WorldModelTool()
    before = _one_object()
    tool.observe(before, (1, None), changed=True)

    assert tool._table, "observe should create a table entry"
    from admorphiq.tools.base import base_hash

    entry = tool._table[(base_hash(before), 1)]
    assert entry.count == 1
    assert entry.changed == 1
    assert entry.change_prob() > 0.5


def test_propose_exploits_learned_high_progress_action():
    """Purpose: after learning a deterministic 2-action world where action 1
    raises the frame-only progress measure and action 2 does nothing, propose()
    must exploit action 1 (the expected-highest-progress action).

    Expected feedback: pass ⇒ the planner drives toward progress using the learned
    model; fail ⇒ it cannot turn learned dynamics into an effective action.
    """
    tool = WorldModelTool()
    A = _one_object()      # progress 1
    B = _two_objects()     # progress 2  (action 1 grows the frame)
    obs_A = _Obs(A, actions=[1, 2])
    obs_B = _Obs(B, actions=[1, 2])

    # Teach the two transitions through the real propose→observe→propose loop.
    for _ in range(3):
        tool.propose([], obs_A)                      # finalises prior pending
        tool.observe(A, (1, None), changed=True)     # stage A --1--> B
        tool.propose([], obs_B)                      # finalise: progress gain +1
        tool.observe(A, (2, None), changed=False)    # stage A --2--> A
        tool.propose([], obs_A)                      # finalise: progress gain 0

    steps = tool.propose([], obs_A)
    assert steps == [(1, None)], f"should exploit action 1, got {steps}"


def test_detect_lower_confidence_under_nondeterminism():
    """Purpose: detect() must report high confidence when the observed dynamics
    are deterministic (state+action → one reliable next state) and markedly lower
    confidence when the same action from the same state yields varying outcomes.

    Expected feedback: pass ⇒ the orchestrator prefers this tool on learnable,
    predictable games and avoids it on chaotic ones; fail ⇒ detect ignores the
    determinism signal the whole tool is premised on.
    """
    A = _objects(3)
    B = _objects(4)
    C = _objects(5)
    obs_A = _Obs(A, actions=[1])
    obs_B = _Obs(B, actions=[1])
    obs_C = _Obs(C, actions=[1])

    det = WorldModelTool()
    for _ in range(4):
        det.propose([], obs_A)
        det.observe(A, (1, None), changed=True)
        det.propose([], obs_B)      # A --1--> B every time (deterministic)
    det_conf = det.detect([], obs_A)

    nondet = WorldModelTool()
    for i in range(4):
        nondet.propose([], obs_A)
        nondet.observe(A, (1, None), changed=True)
        # A --1--> B or C, alternating: same state+action, different outcome.
        nondet.propose([], obs_B if i % 2 == 0 else obs_C)
    nondet_conf = nondet.detect([], obs_A)

    assert det_conf >= 0.7, f"deterministic world should be HIGH, got {det_conf}"
    assert nondet_conf < det_conf, (
        f"nondeterministic ({nondet_conf}) must be below deterministic ({det_conf})"
    )


def test_no_game_ids_in_tool():
    """Purpose: the tool must be game-agnostic — no game ids/titles/sprite tags —
    so it transfers to unseen games (the whole reason for an online model).

    Expected feedback: pass ⇒ generality guard holds; fail ⇒ a game-specific leak
    crept in and the model would overfit the preview set.
    """
    import admorphiq.tools.world_model as mod

    src = open(mod.__file__).read().lower()
    for tok in ("su15", "ft09", "cd82", "sb26", "game_id", "game_title", "sprite"):
        assert tok not in src, f"game-specific token leaked: {tok!r}"
