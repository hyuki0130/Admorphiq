"""Tests for admorphiq.perception module (CNN backbone, heads, model)."""

import torch

from admorphiq.perception.cnn import ActionHead, CNNBackbone, CoordinateHead
from admorphiq.perception.model import PerceptionModel


class TestCNNBackbone:
    def test_output_shape(self):
        model = CNNBackbone()
        x = torch.randn(1, 16, 64, 64)
        out = model(x)
        assert out.shape == (1, 256, 64, 64)

    def test_batch(self):
        model = CNNBackbone()
        x = torch.randn(4, 16, 64, 64)
        out = model(x)
        assert out.shape == (4, 256, 64, 64)


class TestActionHead:
    def test_output_shape(self):
        head = ActionHead()
        features = torch.randn(1, 256, 64, 64)
        out = head(features)
        assert out.shape == (1, 5)

    def test_batch(self):
        head = ActionHead()
        features = torch.randn(3, 256, 64, 64)
        out = head(features)
        assert out.shape == (3, 5)


class TestCoordinateHead:
    def test_output_shape(self):
        head = CoordinateHead()
        features = torch.randn(1, 256, 64, 64)
        out = head(features)
        assert out.shape == (1, 4096)

    def test_batch(self):
        head = CoordinateHead()
        features = torch.randn(2, 256, 64, 64)
        out = head(features)
        assert out.shape == (2, 4096)


class TestPerceptionModel:
    def test_output_shape(self):
        model = PerceptionModel()
        x = torch.randn(1, 16, 64, 64)
        out = model(x)
        assert out.shape == (1, 4101)

    def test_batch(self):
        model = PerceptionModel()
        x = torch.randn(2, 16, 64, 64)
        out = model(x)
        assert out.shape == (2, 4101)

    def test_available_actions_mask_5(self):
        """Mask shape (batch, 5) — masked actions should be -inf."""
        model = PerceptionModel()
        x = torch.randn(1, 16, 64, 64)
        mask = torch.tensor([[True, False, True, False, True]])  # (1, 5)
        out = model(x, available_actions=mask)
        assert out.shape == (1, 4101)
        # Masked positions (index 1 and 3) should be -inf
        assert out[0, 1].item() == float("-inf")
        assert out[0, 3].item() == float("-inf")
        # Unmasked positions should be finite
        assert torch.isfinite(out[0, 0])
        assert torch.isfinite(out[0, 2])
        assert torch.isfinite(out[0, 4])
        # Coordinate logits should all be finite (always available)
        assert torch.isfinite(out[0, 5:]).all()

    def test_available_actions_mask_full(self):
        """Mask shape (batch, 4101) — full logit mask."""
        model = PerceptionModel()
        x = torch.randn(1, 16, 64, 64)
        mask = torch.ones(1, 4101, dtype=torch.bool)
        mask[0, 0] = False
        mask[0, 100] = False
        out = model(x, available_actions=mask)
        assert out[0, 0].item() == float("-inf")
        assert out[0, 100].item() == float("-inf")
        assert torch.isfinite(out[0, 1])

    def test_no_mask(self):
        """Without mask, all logits should be finite."""
        model = PerceptionModel()
        x = torch.randn(1, 16, 64, 64)
        out = model(x)
        assert torch.isfinite(out).all()
