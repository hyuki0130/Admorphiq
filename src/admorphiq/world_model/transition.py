"""Transition predictor and change predictor for World Model."""

import torch
import torch.nn as nn


class ActionEmbedding(nn.Module):
    """Embeds action type + optional (x, y) coordinates into a spatial feature map.

    For ACTION1-5, ACTION7: only the action type embedding is used, broadcast spatially.
    For ACTION6: action type embedding + a one-hot coordinate map at (x, y).
    """

    NUM_ACTION_TYPES: int = 8  # ACTION1-7 + RESET
    EMBED_DIM: int = 32

    def __init__(self) -> None:
        super().__init__()
        self.type_embed = nn.Embedding(self.NUM_ACTION_TYPES, self.EMBED_DIM)
        # Coordinate channel: 1 extra channel for spatial coordinate info
        # Total output channels: EMBED_DIM + 1 = 33

    def forward(
        self,
        action_idx: torch.Tensor,
        coord_x: torch.Tensor | None = None,
        coord_y: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Produce spatial action embedding.

        Args:
            action_idx: Action type indices of shape (batch,), values 0-7.
            coord_x: X coordinates of shape (batch,), 0-63. None for non-ACTION6.
            coord_y: Y coordinates of shape (batch,), 0-63. None for non-ACTION6.

        Returns:
            Action feature map of shape (batch, 33, 64, 64).
        """
        batch = action_idx.shape[0]
        device = action_idx.device

        # Action type embedding broadcast to spatial dims
        type_emb = self.type_embed(action_idx)  # (B, 32)
        type_spatial = type_emb[:, :, None, None].expand(-1, -1, 64, 64)  # (B, 32, 64, 64)

        # Coordinate channel: one-hot spatial map
        coord_map = torch.zeros(batch, 1, 64, 64, device=device)  # (B, 1, 64, 64)
        if coord_x is not None and coord_y is not None:
            for i in range(batch):
                cx = coord_x[i].clamp(0, 63).long()
                cy = coord_y[i].clamp(0, 63).long()
                coord_map[i, 0, cy, cx] = 1.0

        return torch.cat([type_spatial, coord_map], dim=1)  # (B, 33, 64, 64)


class TransitionPredictor(nn.Module):
    """Predicts the next state delta given encoded state + action embedding.

    Uses residual prediction: next_state = current_frame + predicted_delta.
    """

    def __init__(self, state_dim: int = 256, action_dim: int = 33) -> None:
        super().__init__()
        in_channels = state_dim + action_dim  # 289
        self.net = nn.Sequential(
            nn.Conv2d(in_channels, 256, kernel_size=3, padding=1),  # (B, 256, 64, 64)
            nn.ReLU(inplace=True),
            nn.Conv2d(256, 128, kernel_size=3, padding=1),          # (B, 128, 64, 64)
            nn.ReLU(inplace=True),
            nn.Conv2d(128, 64, kernel_size=3, padding=1),           # (B, 64, 64, 64)
            nn.ReLU(inplace=True),
            nn.Conv2d(64, 16, kernel_size=3, padding=1),            # (B, 16, 64, 64)
        )

    def forward(self, state_features: torch.Tensor, action_features: torch.Tensor) -> torch.Tensor:
        """Predict frame delta.

        Args:
            state_features: Encoded state of shape (batch, 256, 64, 64).
            action_features: Action embedding of shape (batch, 33, 64, 64).

        Returns:
            Predicted delta of shape (batch, 16, 64, 64).
        """
        x = torch.cat([state_features, action_features], dim=1)  # (B, 289, 64, 64)
        return self.net(x)  # (B, 16, 64, 64)


class ChangePredictor(nn.Module):
    """Predicts the probability that an action will cause a frame change."""

    def __init__(self, state_dim: int = 256, action_dim: int = 33) -> None:
        super().__init__()
        in_channels = state_dim + action_dim  # 289
        self.conv = nn.Sequential(
            nn.Conv2d(in_channels, 64, kernel_size=3, padding=1),  # (B, 64, 64, 64)
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d(1),                                # (B, 64, 1, 1)
        )
        self.fc = nn.Linear(64, 1)

    def forward(self, state_features: torch.Tensor, action_features: torch.Tensor) -> torch.Tensor:
        """Predict change probability.

        Args:
            state_features: Encoded state of shape (batch, 256, 64, 64).
            action_features: Action embedding of shape (batch, 33, 64, 64).

        Returns:
            Change logit of shape (batch,).
        """
        x = torch.cat([state_features, action_features], dim=1)  # (B, 289, 64, 64)
        x = self.conv(x)          # (B, 64, 1, 1)
        x = x.flatten(start_dim=1)  # (B, 64)
        return self.fc(x).squeeze(1)  # (B,)
