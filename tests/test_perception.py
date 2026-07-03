"""Tests for admorphiq.perception module (CNN backbone, heads, model)."""

import torch

from admorphiq.perception.cnn import (
    BASE_CHANNELS,
    ActionHead,
    CNNBackbone,
    CoordinateHead,
)
from admorphiq.perception.model import PerceptionModel

# The committed (R24-baseline) PerceptionModel parameter count. This exact number
# is the regression guard: the default architecture must never change.
DEFAULT_PERCEPTION_PARAMS = 34_320_614


def _param_count(module: torch.nn.Module) -> int:
    return sum(p.numel() for p in module.parameters())


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


class TestPerceptionCapacity:
    """R24: the env-gated CNN capacity knob widens/deepens the online-RL policy net.

    These pin the three deliverables for the capacity axis: (a) default capacity
    reproduces the committed architecture, (b) the knob produces a strictly larger
    net with the correct 4101 dual-head output shape, (c) forward passes work on a
    16x64x64 one-hot input for every capacity variant.
    """

    def test_default_param_count_unchanged(self):
        """Purpose: default capacity must reproduce the committed architecture
        byte-for-byte (the regression guard for the online-RL card).

        Expected feedback: pass => PerceptionModel() has EXACTLY the committed
        34,320,614 params, so RL_CNN_WIDTH-unset runs are architecturally
        identical to the a550070 baseline. Fail => the default net drifted and the
        baseline card is no longer reproducible.
        """
        assert _param_count(PerceptionModel()) == DEFAULT_PERCEPTION_PARAMS

    def test_default_backbone_channels_are_base_plan(self):
        """Purpose: prove width_mult=1.0 leaves the backbone channel plan and
        output-channel contract exactly at the committed (32,64,128,256).

        Expected feedback: pass => the default backbone emits BASE_CHANNELS[-1]
        (256) feature channels, so the heads' input dims are unchanged. Fail =>
        the default channel plan changed, breaking warm-start weight loading.
        """
        backbone = CNNBackbone()
        assert backbone.out_channels == BASE_CHANNELS[-1] == 256
        x = torch.randn(1, 16, 64, 64)
        assert backbone(x).shape == (1, 256, 64, 64)

    def test_default_extra_block_off_matches_explicit_defaults(self):
        """Purpose: the explicit-default construction path must equal the
        no-args path (no hidden divergence between callers).

        Expected feedback: pass => PerceptionModel() and
        PerceptionModel(width_mult=1.0, extra_block=False) have identical param
        counts. Fail => the two construction paths disagree.
        """
        assert _param_count(
            PerceptionModel(width_mult=1.0, extra_block=False)
        ) == _param_count(PerceptionModel())

    def test_wider_net_is_larger_with_correct_output_shape(self):
        """Purpose: prove the width knob produces a strictly larger net while
        preserving the dual-head 4101-logit output shape.

        Expected feedback: pass => width_mult=2.0 has more params than default
        AND still emits (batch, 4101) = 5 action + 4096 coord logits. Fail => the
        knob either did not grow the net or broke the output contract the agent
        depends on.
        """
        big = PerceptionModel(width_mult=2.0)
        assert _param_count(big) > DEFAULT_PERCEPTION_PARAMS
        x = torch.randn(3, 16, 64, 64)
        out = big(x)
        assert out.shape == (3, 4101)
        assert out.shape[1] == 5 + 4096

    def test_extra_block_is_larger_with_correct_output_shape(self):
        """Purpose: prove the depth knob (extra_block) adds params without
        changing the 4101-logit dual-head output shape.

        Expected feedback: pass => extra_block=True has more params than default
        and still emits (batch, 4101). Fail => the extra block changed the output
        contract or was a no-op.
        """
        deeper = PerceptionModel(extra_block=True)
        assert _param_count(deeper) > DEFAULT_PERCEPTION_PARAMS
        x = torch.randn(1, 16, 64, 64)
        assert deeper(x).shape == (1, 4101)

    def test_forward_on_onehot_input_for_all_capacities(self):
        """Purpose: a forward pass on a realistic 16x64x64 one-hot frame must
        succeed and stay finite for default, wider, deeper, and combined nets.

        Expected feedback: pass => every capacity variant produces finite (1,4101)
        logits from a one-hot input, so the online agent can run inference/train
        at any configured capacity. Fail => some capacity variant errors or emits
        non-finite logits.
        """
        onehot = torch.zeros(1, 16, 64, 64)
        # one active colour channel per cell — a valid one-hot frame
        onehot[:, 0, :, :] = 1.0
        for kwargs in (
            {},
            {"width_mult": 2.0},
            {"extra_block": True},
            {"width_mult": 1.5, "extra_block": True},
        ):
            out = PerceptionModel(**kwargs)(onehot)
            assert out.shape == (1, 4101)
            assert torch.isfinite(out).all()

    def test_masking_works_at_larger_capacity(self):
        """Purpose: available-action masking (the RL agent's action gating) must
        behave identically on a widened net.

        Expected feedback: pass => a (1,5) availability mask on a width_mult=2.0
        net masks the intended action logits to -inf while coords stay finite.
        Fail => capacity scaling broke the masking contract the planner relies on.
        """
        model = PerceptionModel(width_mult=2.0)
        x = torch.randn(1, 16, 64, 64)
        mask = torch.tensor([[True, False, True, False, True]])
        out = model(x, available_actions=mask)
        assert out[0, 1].item() == float("-inf")
        assert out[0, 3].item() == float("-inf")
        assert torch.isfinite(out[0, 0])
        assert torch.isfinite(out[0, 5:]).all()
