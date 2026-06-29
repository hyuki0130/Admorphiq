"""Tests for the pure RL maths in ``scripts/train_rl.py``.

These pin the three correctness-critical helpers that have no env/training
dependency: the sparse reward computation, the discounted return-to-go, and the
masked action sampling. A regression in any of them silently corrupts the policy
gradient, so they are guarded before the multi-hour RL run.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from train_rl import (  # noqa: E402
    RewardConfig,
    build_full_mask,
    compute_returns,
    compute_step_reward,
    index_to_action_parts,
    sample_action_index,
)

from admorphiq.bc_agent import (  # noqa: E402
    COORD_OFFSET,
    NUM_SIMPLE_ACTIONS,
    TOTAL_LOGITS,
)


def test_step_reward_sparse_level_dominates_shaping():
    """Purpose: a level clear must reward +level_reward, frame-change adds the
    tiny shaping bonus, GAME_OVER subtracts the penalty, and no-op stays ~0.

    Expected feedback: PASS proves the StochasticGoose sparse-level signal is the
    dominant term and the shaping terms are correctly additive/subtractive. FAIL
    means the reward channel feeding the policy gradient is mis-specified.
    """
    cfg = RewardConfig()
    # Level cleared + frame changed: +1.0 and +0.02.
    assert compute_step_reward(1, True, False, cfg) == 1.02
    # Frame change only.
    assert compute_step_reward(0, True, False, cfg) == 0.02
    # No-op (nothing happened).
    assert compute_step_reward(0, False, False, cfg) == 0.0
    # GAME_OVER with no change: −0.5.
    assert compute_step_reward(0, False, True, cfg) == -0.5
    # Negative/zero level deltas never produce negative level reward.
    assert compute_step_reward(-3, False, False, cfg) == 0.0


def test_step_reward_step_penalty_applied():
    """Purpose: the optional per-step penalty must subtract from every step.

    Expected feedback: PASS proves ``--step-penalty`` is wired into the reward so
    longer solutions are discouraged (squared-efficiency metric). FAIL means the
    knob is inert.
    """
    cfg = RewardConfig(step_penalty=0.01)
    assert compute_step_reward(0, False, False, cfg) == -0.01
    assert abs(compute_step_reward(1, False, False, cfg) - 0.99) < 1e-9


def test_compute_returns_discounting():
    """Purpose: returns-to-go must be the discounted reverse-cumulative sum.

    Expected feedback: PASS proves G_t = r_t + γ·G_{t+1} exactly, so a terminal
    +1 is correctly propagated (discounted) to earlier steps — this is what makes
    RL prefer SHORTER paths to a level clear. FAIL corrupts the advantage signal.
    """
    rewards = [0.0, 0.0, 1.0]
    gamma = 0.99
    got = compute_returns(rewards, gamma)
    assert got[2] == 1.0
    assert abs(got[1] - 0.99) < 1e-9
    assert abs(got[0] - 0.99 ** 2) < 1e-9
    # Earlier steps must value the future clear strictly less (discounting).
    assert got[0] < got[1] < got[2]


def test_compute_returns_empty():
    """Purpose: an empty episode yields no returns without raising.

    Expected feedback: PASS proves the update loop tolerates a zero-length
    rollout. FAIL would crash training on a degenerate episode.
    """
    assert compute_returns([], 0.99) == []


def test_sample_action_index_respects_mask():
    """Purpose: sampling must never pick a masked-out (unavailable) action.

    Expected feedback: PASS proves the policy only ever emits actions the env
    actually offers — across many draws and with a deterministic generator the
    single available action is always returned. FAIL means the agent could send
    illegal actions to the env.
    """
    logits = torch.randn(TOTAL_LOGITS)
    # Only ACTION3 (index 2) available, ACTION6 disabled.
    simple = np.zeros(NUM_SIMPLE_ACTIONS, dtype=bool)
    simple[2] = True
    mask = build_full_mask(simple, action6_ok=False)
    gen = torch.Generator().manual_seed(0)
    for _ in range(50):
        assert sample_action_index(logits, mask, generator=gen) == 2

    # With several simple actions + ACTION6 available, every draw lands in-set.
    simple2 = np.array([True, False, True, False, True])
    mask2 = build_full_mask(simple2, action6_ok=True)
    allowed = set(np.flatnonzero(mask2.numpy()).tolist())
    gen2 = torch.Generator().manual_seed(1)
    for _ in range(200):
        assert sample_action_index(logits, mask2, generator=gen2) in allowed


def test_build_full_mask_coord_block():
    """Purpose: ACTION6 availability must open the entire 4096-coord block.

    Expected feedback: PASS proves coord availability matches BCPolicyAgent
    deploy masking (any cell clickable when ACTION6 is offered). FAIL would let
    the coord head be silently masked, killing click games.
    """
    simple = np.zeros(NUM_SIMPLE_ACTIONS, dtype=bool)
    m_no6 = build_full_mask(simple, action6_ok=False)
    assert m_no6.sum().item() == 0
    m_6 = build_full_mask(simple, action6_ok=True)
    assert m_6[NUM_SIMPLE_ACTIONS:].all()
    assert m_6.sum().item() == TOTAL_LOGITS - NUM_SIMPLE_ACTIONS


def test_index_to_action_parts_roundtrip():
    """Purpose: combined-logit index → (action_id, x, y) must match the BC decode.

    Expected feedback: PASS proves an RL-sampled index maps to the SAME env
    action the BC agent would emit (simple a→a-1; ACTION6 idx = 5+y*64+x). FAIL
    means RL and BC disagree on action semantics and the warm-start is invalid.
    """
    assert index_to_action_parts(0) == (1, None, None)
    assert index_to_action_parts(4) == (5, None, None)
    # ACTION6 at (x=3, y=2): index = 5 + 2*64 + 3.
    idx = COORD_OFFSET + 2 * 64 + 3
    assert index_to_action_parts(idx) == (6, 3, 2)
