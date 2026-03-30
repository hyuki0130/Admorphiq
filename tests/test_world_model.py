"""Tests for admorphiq.world_model module."""

import torch

from admorphiq.world_model.encoder import StateEncoder
from admorphiq.world_model.transition import ActionEmbedding, ChangePredictor, TransitionPredictor
from admorphiq.world_model.model import WorldModel


class TestStateEncoder:
    def test_output_shape(self):
        encoder = StateEncoder()
        x = torch.randn(1, 16, 64, 64)
        out = encoder(x)
        assert out.shape == (1, 256, 64, 64)

    def test_batch(self):
        encoder = StateEncoder()
        x = torch.randn(3, 16, 64, 64)
        out = encoder(x)
        assert out.shape == (3, 256, 64, 64)


class TestActionEmbedding:
    def test_simple_action_shape(self):
        emb = ActionEmbedding()
        action_idx = torch.tensor([0])  # ACTION1
        out = emb(action_idx)
        assert out.shape == (1, 33, 64, 64)

    def test_action6_with_coordinates(self):
        emb = ActionEmbedding()
        action_idx = torch.tensor([5])  # ACTION6
        coord_x = torch.tensor([32])
        coord_y = torch.tensor([48])
        out = emb(action_idx, coord_x, coord_y)
        assert out.shape == (1, 33, 64, 64)
        # Coordinate channel should have a 1.0 at (y=48, x=32)
        assert out[0, 32, 48, 32].item() == 1.0  # channel 32 is coord channel

    def test_no_coordinate_channel_for_simple(self):
        emb = ActionEmbedding()
        action_idx = torch.tensor([0])
        out = emb(action_idx)
        # Coordinate channel (index 32) should be all zeros
        assert out[0, 32].sum().item() == 0.0

    def test_batch(self):
        emb = ActionEmbedding()
        action_idx = torch.tensor([0, 1, 5])
        coord_x = torch.tensor([10, 20, 30])
        coord_y = torch.tensor([15, 25, 35])
        out = emb(action_idx, coord_x, coord_y)
        assert out.shape == (3, 33, 64, 64)

    def test_all_action_types(self):
        emb = ActionEmbedding()
        for idx in range(8):
            out = emb(torch.tensor([idx]))
            assert out.shape == (1, 33, 64, 64)


class TestTransitionPredictor:
    def test_output_shape(self):
        pred = TransitionPredictor()
        state = torch.randn(1, 256, 64, 64)
        action = torch.randn(1, 33, 64, 64)
        out = pred(state, action)
        assert out.shape == (1, 16, 64, 64)

    def test_batch(self):
        pred = TransitionPredictor()
        state = torch.randn(2, 256, 64, 64)
        action = torch.randn(2, 33, 64, 64)
        out = pred(state, action)
        assert out.shape == (2, 16, 64, 64)


class TestChangePredictor:
    def test_output_shape(self):
        pred = ChangePredictor()
        state = torch.randn(1, 256, 64, 64)
        action = torch.randn(1, 33, 64, 64)
        out = pred(state, action)
        assert out.shape == (1,)

    def test_batch(self):
        pred = ChangePredictor()
        state = torch.randn(2, 256, 64, 64)
        action = torch.randn(2, 33, 64, 64)
        out = pred(state, action)
        assert out.shape == (2,)


class TestWorldModel:
    def test_forward_shape(self):
        wm = WorldModel()
        frame = torch.randn(1, 16, 64, 64)
        action_idx = torch.tensor([0])
        next_frame, change_logit = wm(frame, action_idx)
        assert next_frame.shape == (1, 16, 64, 64)
        assert change_logit.shape == (1,)

    def test_forward_with_coordinates(self):
        wm = WorldModel()
        frame = torch.randn(1, 16, 64, 64)
        action_idx = torch.tensor([5])  # ACTION6
        coord_x = torch.tensor([10])
        coord_y = torch.tensor([20])
        next_frame, change_logit = wm(frame, action_idx, coord_x, coord_y)
        assert next_frame.shape == (1, 16, 64, 64)
        assert change_logit.shape == (1,)

    def test_residual_prediction(self):
        """next_frame should equal frame + delta (residual)."""
        wm = WorldModel()
        frame = torch.randn(1, 16, 64, 64)
        action_idx = torch.tensor([0])

        # Get encoder output and delta separately to verify residual
        state_features = wm.encoder(frame)
        action_features = wm.action_embedding(action_idx)
        delta = wm.transition(state_features, action_features)
        expected_next = frame + delta

        next_frame, _ = wm(frame, action_idx)
        assert torch.allclose(next_frame, expected_next, atol=1e-6)

    def test_forward_batch(self):
        wm = WorldModel()
        frame = torch.randn(3, 16, 64, 64)
        action_idx = torch.tensor([0, 2, 5])
        coord_x = torch.tensor([0, 0, 32])
        coord_y = torch.tensor([0, 0, 48])
        next_frame, change_logit = wm(frame, action_idx, coord_x, coord_y)
        assert next_frame.shape == (3, 16, 64, 64)
        assert change_logit.shape == (3,)

    def test_predict_change_probs_shape(self):
        wm = WorldModel()
        frame = torch.randn(16, 64, 64)
        action_indices = [0, 1, 2, 5]
        coord_x = [None, None, None, 32]
        coord_y = [None, None, None, 48]
        probs = wm.predict_change_probs(frame, action_indices, coord_x, coord_y)
        assert probs.shape == (4,)
        # Probabilities should be in [0, 1] (sigmoid output)
        assert (probs >= 0).all() and (probs <= 1).all()

    def test_predict_change_probs_single(self):
        wm = WorldModel()
        frame = torch.randn(16, 64, 64)
        probs = wm.predict_change_probs(frame, [0])
        assert probs.shape == (1,)
