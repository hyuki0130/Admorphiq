"""Tests for the R32 neural forward (change-mask) model shapes + prediction API.

These pin the tensor-shape contract of ForwardModel and the predict_next_frame
interface the R33 planner depends on (returns an int frame of the same shape
plus a scalar confidence in [0, 1]). No training is exercised here — planning
correctness is covered in test_goal_planning.py with a deterministic stub.
"""

from __future__ import annotations

import numpy as np
import torch

from admorphiq.world_model.forward_model import COORD_OFFSET, ForwardModel, _action_planes


def test_forward_model_head_shapes() -> None:
    """Purpose: the two heads must emit change_logits (B,1,64,64) and
    colour_logits (B,16,64,64) for a batched one-hot frame + action planes.

    Expected feedback: pass => the conv trunk/heads are shaped for planning;
    fail => the model can't be trained or rolled out against 64x64 frames.
    """
    fm = ForwardModel()
    frame = torch.zeros(2, 16, 64, 64)
    planes = torch.zeros(2, 2, 64, 64)
    change_logits, colour_logits = fm(frame, planes)
    assert change_logits.shape == (2, 1, 64, 64)
    assert colour_logits.shape == (2, 16, 64, 64)


def test_predict_next_frame_shape_and_confidence_range() -> None:
    """Purpose: predict_next_frame must return a (64,64) int frame matching the
    input dtype and a confidence in [0, 1].

    Expected feedback: pass => the planner receives a concrete next frame it can
    score and a trustworthy confidence for the fallback gate; fail => the
    rollout decode or confidence computation is broken.
    """
    fm = ForwardModel()
    frame = np.random.randint(0, 16, size=(64, 64), dtype=np.int64)
    nxt, conf = fm.predict_next_frame(frame, action_idx=2)
    assert nxt.shape == (64, 64)
    assert nxt.dtype == frame.dtype
    assert 0.0 <= conf <= 1.0


def test_action_planes_encode_simple_vs_coordinate() -> None:
    """Purpose: _action_planes must localise an ACTION6 click to one cell in the
    coordinate plane while simple actions leave that plane all-zero.

    Expected feedback: pass => the forward model can distinguish where a click
    lands vs a global simple action; fail => coordinate information is lost.
    """
    device = torch.device("cpu")
    simple = _action_planes(1, device)
    assert simple.shape == (2, 64, 64)
    assert float(simple[1].sum()) == 0.0  # no coord spike for a simple action

    # ACTION6 at coordinate 0 => cell (0, 0) spiked.
    coord = _action_planes(COORD_OFFSET + 0, device)
    assert float(coord[1].sum()) == 1.0
    assert float(coord[1, 0, 0]) == 1.0
