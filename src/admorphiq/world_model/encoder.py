"""State encoder for World Model — reuses CNN backbone architecture."""

import torch
import torch.nn as nn

from ..perception.cnn import CNNBackbone


class StateEncoder(nn.Module):
    """Encodes a 16-channel one-hot frame into a latent state representation.

    Uses the same CNN backbone architecture as the Perception Layer but as
    a separate instance to allow independent learning dynamics.
    """

    FEATURE_DIM: int = 256

    def __init__(self) -> None:
        super().__init__()
        self.cnn = CNNBackbone()  # (B, 16, 64, 64) → (B, 256, 64, 64)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Encode a frame.

        Args:
            x: One-hot frame of shape (batch, 16, 64, 64).

        Returns:
            Feature map of shape (batch, 256, 64, 64).
        """
        return self.cnn(x)  # (batch, 256, 64, 64)
