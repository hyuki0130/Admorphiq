"""Unified perception model combining CNN backbone with action and coordinate heads."""

import torch
import torch.nn as nn

from .cnn import ActionHead, CNNBackbone, CoordinateHead


class PerceptionModel(nn.Module):
    """ARC-AGI-3 perception model.

    Produces 4101 logits: 5 action logits (ACTION1~5) + 4096 coordinate logits (ACTION6).
    Supports masking unavailable actions with -inf.
    """

    NUM_ACTIONS: int = 5
    NUM_COORDINATES: int = 4096  # 64 * 64
    TOTAL_LOGITS: int = NUM_ACTIONS + NUM_COORDINATES  # 4101

    def __init__(self, width_mult: float = 1.0, extra_block: bool = False) -> None:
        """Build the perception model at a given capacity.

        Args:
            width_mult: Backbone channel multiplier. Default 1.0 reproduces the
                committed 34.3M-param architecture byte-for-byte; >1.0 widens
                every conv and (via the heads' ``in_channels``) the head input
                dims, growing the net for the online RL learner.
            extra_block: Append one extra backbone conv block (final width) when
                True. Output logit shape (batch, 4101) is invariant to both knobs.
        """
        super().__init__()
        self.backbone = CNNBackbone(width_mult=width_mult, extra_block=extra_block)
        out_ch = self.backbone.out_channels
        self.action_head = ActionHead(in_channels=out_ch)
        self.coordinate_head = CoordinateHead(in_channels=out_ch)

    def forward(
        self,
        x: torch.Tensor,
        available_actions: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Forward pass.

        Args:
            x: Input frames of shape (batch, 16, 64, 64).
            available_actions: Optional bool mask of shape (batch, 5) or (batch, 4101).
                True = available, False = masked with -inf.

        Returns:
            Combined logits of shape (batch, 4101).
        """
        features = self.backbone(x)                    # (batch, 256, 64, 64)
        action_logits = self.action_head(features)     # (batch, 5)
        coord_logits = self.coordinate_head(features)  # (batch, 4096)

        logits = torch.cat([action_logits, coord_logits], dim=1)  # (batch, 4101)

        if available_actions is not None:
            mask = available_actions
            if mask.shape[-1] == self.NUM_ACTIONS:
                # Expand to full logit size — coordinates always available
                coord_mask = torch.ones(
                    mask.shape[0], self.NUM_COORDINATES,
                    dtype=torch.bool, device=mask.device,
                )
                mask = torch.cat([mask, coord_mask], dim=1)  # (batch, 4101)
            logits = logits.masked_fill(~mask, float("-inf"))

        return logits  # (batch, 4101)
