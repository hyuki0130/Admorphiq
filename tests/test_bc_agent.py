"""Tests for behavior-cloning target construction and frame one-hot encoding.

These pin the contract between the trace schema and ``PerceptionModel``'s 4101
combined-logit layout, which both the trainer and the deployed agent rely on.
"""

import numpy as np
import torch

from admorphiq.bc_agent import (
    COORD_OFFSET,
    TOTAL_LOGITS,
    BCPolicyAgent,
    build_bc_targets,
    coord_to_index,
    frame_to_onehot,
)


class _FakeObs:
    """Minimal arcengine-observation stand-in for agent unit tests."""

    def __init__(self, frame: np.ndarray, actions: list[int], state: str = "PLAYING",
                 levels: int = 0) -> None:
        self.frame = [frame]            # get_frame() reads obs.frame[0]
        self.available_actions = actions
        self.levels_completed = levels
        self.state = type("S", (), {"name": state})()


def test_build_bc_targets_simple_and_action6():
    """Purpose: a synthetic trace row maps to the correct combined-logit class.

    Expected feedback: PASS proves simple actions land in [0,5) as ``a-1`` and an
    ACTION6 click (x,y) lands at ``5 + y*64 + x`` — the exact index the deployed
    agent decodes back to a click. FAIL means train/deploy coordinate orientation
    has diverged and the policy would click the wrong cell.
    """
    actions = np.array([1, 3, 5, 6], dtype=np.int8)
    coords_x = np.array([-1, -1, -1, 7], dtype=np.int8)
    coords_y = np.array([-1, -1, -1, 2], dtype=np.int8)

    targets = build_bc_targets(actions, coords_x, coords_y)

    assert targets.tolist() == [0, 2, 4, COORD_OFFSET + 2 * 64 + 7]
    assert targets[-1] == coord_to_index(7, 2)
    assert int(targets.max()) < TOTAL_LOGITS


def test_build_bc_targets_rejects_out_of_range():
    """Purpose: BC has no logit slot for RESET(0)/ACTION7(7), so they must error.

    Expected feedback: PASS proves invalid demonstrations are rejected loudly
    rather than silently encoded as a wrong class. FAIL means corrupt targets
    could enter training.
    """
    import pytest

    with pytest.raises(ValueError):
        build_bc_targets(
            np.array([7], dtype=np.int8),
            np.array([-1], dtype=np.int8),
            np.array([-1], dtype=np.int8),
        )


def test_frame_to_onehot_shape_and_channels():
    """Purpose: a (64,64) colour-index frame one-hots to the model's (16,64,64) input.

    Expected feedback: PASS proves the encoder yields exactly one hot channel per
    cell over 16 colour channels, matching ``PerceptionModel``'s Conv2d(16,...).
    FAIL means the policy net would receive a mis-shaped tensor at inference.
    """
    frame = np.zeros((64, 64), dtype=np.uint8)
    frame[0, 0] = 5
    frame[10, 20] = 11

    oh = frame_to_onehot(frame)

    assert oh.shape == (16, 64, 64)
    assert oh.dtype == torch.float32
    # Exactly one channel active per spatial cell.
    assert torch.all(oh.sum(dim=0) == 1)
    assert oh[5, 0, 0] == 1.0
    assert oh[11, 10, 20] == 1.0
    assert oh[0, 1, 1] == 1.0  # background colour 0


def test_cycle_detector_triggers_fallback_on_repeated_noop():
    """Purpose: a frozen frame with one deterministic action (the SB26 loop shape)
    must trip the stuck/cycle detector and hand off to the exploration fallback
    instead of re-emitting the same no-op argmax forever.

    Expected feedback: PASS proves the detector escapes a deterministic
    state-action loop after ``STUCK_THRESHOLD`` unchanged frames. FAIL means the
    argmax policy can still spin in place to the action budget cap.
    """
    agent = BCPolicyAgent(device="cpu", ttt=False)
    sentinel = object()
    agent._fallback_action = lambda obs: sentinel  # avoid the heavy ensemble agent

    frame = np.zeros((64, 64), dtype=np.int32)
    obs = _FakeObs(frame, actions=[1])  # only ACTION1 → deterministic no-op pick

    returned = [agent.choose_action([], obs) for _ in range(agent.STUCK_THRESHOLD + 2)]
    assert returned[-1] is sentinel
    assert not agent._ttt_enabled  # TTT must stay off in tests


def test_no_progress_hard_cap_sets_done():
    """Purpose: a game that never clears a level (e.g. SB26) must be abandoned via
    ``is_done`` once the no-progress action cap is hit, rather than running to the
    50k action budget.

    Expected feedback: PASS proves the hard cap flips ``is_done`` to True after
    ``_give_up_no_progress`` actions without a level clear. FAIL means a hopeless
    game still burns the full budget.
    """
    agent = BCPolicyAgent(device="cpu", ttt=False)
    agent.STUCK_THRESHOLD = 10_000      # disable the fallback path for this test
    agent._give_up_no_progress = 6      # tiny cap so the test is fast

    frame = np.zeros((64, 64), dtype=np.int32)
    obs = _FakeObs(frame, actions=[1])

    assert not agent.is_done([], obs)
    for _ in range(agent._give_up_no_progress):
        agent.choose_action([], obs)
    assert agent.is_done([], obs)


def test_ttt_triggers_and_adapts_on_level_clear():
    """Purpose: clearing a level must fine-tune the per-game policy copy on its
    accumulated successful (frame->action) transitions (test-time training),
    bounded to a few steps, mutating only the in-memory working model.

    Expected feedback: PASS proves a level-up event flushes the pending
    transitions into the TTT buffer and runs a bounded finetune that changes the
    working model's weights — the depth lever that lets cleared-level mechanics
    carry into the next level. FAIL means deeper levels get no per-game
    adaptation, so depth cannot improve.
    """
    agent = BCPolicyAgent(device="cpu", ttt=True)
    # Bounded, fast finetune — no real long training in the test suite.
    agent.TTT_STEPS = 1
    agent.TTT_MAX_SAMPLES = 4
    agent.TTT_MIN_SAMPLES = 1
    # Keep the policy path (avoid the heavy exploration fallback) for recording.
    agent.REPEAT_LIMIT = 10_000
    agent.STUCK_THRESHOLD = 10_000
    agent._fallback_action = lambda obs: None  # must never be hit in this test

    frame = np.zeros((64, 64), dtype=np.int32)
    obs0 = _FakeObs(frame, actions=[1], levels=0)
    for _ in range(3):
        agent.choose_action([], obs0)
    assert agent._ttt_pending  # policy picks recorded as TTT candidates

    before = next(agent.model.parameters()).detach().clone()
    obs1 = _FakeObs(frame, actions=[1], levels=1)  # levels 0->1 == level clear
    agent.choose_action([], obs1)

    after = next(agent.model.parameters()).detach()
    assert agent._levels_cleared_this_game == 1
    # The 3 pre-clear demos were flushed into the buffer; the current post-clear
    # step is freshly recorded into the emptied pending list.
    assert len(agent._ttt_buffer) == 3
    assert len(agent._ttt_pending) == 1
    assert not torch.equal(before, after)  # finetune mutated the working model
    assert agent.ttt_seconds > 0.0         # wall-time was measured/recorded


def test_official_action_maps_back_to_logit_index():
    """Purpose: explored fallback moves must be recordable as TTT supervision,
    which requires mapping an official GameAction back to its combined-logit
    class — the inverse of ``_index_to_action``.

    Expected feedback: PASS proves simple actions and ACTION6 clicks round-trip
    to the exact class the policy decodes (so a discovered clearing move becomes
    a valid demonstrated target), and RESET/ACTION7 (no logit slot) map to None.
    FAIL means search-discovered moves cannot be learned by TTT.
    """
    from arcengine import GameAction

    agent = BCPolicyAgent(device="cpu", ttt=True)

    assert agent._official_to_index(GameAction.from_id(1)) == 0
    assert agent._official_to_index(GameAction.from_id(5)) == 4

    a6 = GameAction.from_id(6)
    a6.set_data({"x": 7, "y": 2})
    assert agent._official_to_index(a6) == coord_to_index(7, 2)

    assert agent._official_to_index(GameAction.RESET) is None
    assert agent._official_to_index(GameAction.from_id(7)) is None
