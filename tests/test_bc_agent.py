"""Tests for behavior-cloning target construction and frame one-hot encoding.

These pin the contract between the trace schema and ``PerceptionModel``'s 4101
combined-logit layout, which both the trainer and the deployed agent rely on.
"""

import numpy as np
import torch

from admorphiq.bc_agent import (
    COORD_OFFSET,
    TOTAL_LOGITS,
    build_bc_targets,
    coord_to_index,
    frame_to_onehot,
)


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
