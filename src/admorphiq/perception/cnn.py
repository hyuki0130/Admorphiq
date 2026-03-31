"""CNN backbone for ARC-AGI-3 frame perception."""

import torch
import torch.nn as nn


class CNNBackbone(nn.Module):
    """4-layer CNN encoder for 16-channel one-hot encoded 64x64 frames."""

    def __init__(self) -> None:
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(16, 32, kernel_size=3, padding=1),   # (B, 32, 64, 64)
            nn.ReLU(inplace=True),
            nn.Conv2d(32, 64, kernel_size=3, padding=1),   # (B, 64, 64, 64)
            nn.ReLU(inplace=True),
            nn.Conv2d(64, 128, kernel_size=3, padding=1),  # (B, 128, 64, 64)
            nn.ReLU(inplace=True),
            nn.Conv2d(128, 256, kernel_size=3, padding=1), # (B, 256, 64, 64)
            nn.ReLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass.

        Args:
            x: Input tensor of shape (batch, 16, 64, 64).

        Returns:
            Feature map of shape (batch, 256, 64, 64).
        """
        return self.features(x)  # (batch, 256, 64, 64)


class ActionHead(nn.Module):
    """Predicts change probability for ACTION1~5."""

    def __init__(self) -> None:
        super().__init__()
        self.pool = nn.MaxPool2d(kernel_size=4)  # (B, 256, 16, 16)
        self.fc1 = nn.Linear(256 * 16 * 16, 512)
        self.dropout = nn.Dropout(0.2)
        self.fc2 = nn.Linear(512, 5)

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        """Forward pass.

        Args:
            features: CNN feature map of shape (batch, 256, 64, 64).

        Returns:
            Action logits of shape (batch, 5).
        """
        x = self.pool(features)          # (batch, 256, 16, 16)
        x = x.flatten(start_dim=1)       # (batch, 256*16*16)
        x = self.dropout(torch.relu(self.fc1(x)))
        return self.fc2(x)               # (batch, 5)


class CoordinateHead(nn.Module):
    """Fully convolutional head for ACTION6 coordinate prediction."""

    def __init__(self) -> None:
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(256, 128, kernel_size=3, padding=1),  # (B, 128, 64, 64)
            nn.ReLU(inplace=True),
            nn.Conv2d(128, 64, kernel_size=3, padding=1),   # (B, 64, 64, 64)
            nn.ReLU(inplace=True),
            nn.Conv2d(64, 32, kernel_size=1),                 # (B, 32, 64, 64)
            nn.ReLU(inplace=True),
            nn.Conv2d(32, 1, kernel_size=1),                 # (B, 1, 64, 64)
        )

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        """Forward pass.

        Args:
            features: CNN feature map of shape (batch, 256, 64, 64).

        Returns:
            Coordinate logits of shape (batch, 4096).
        """
        x = self.conv(features)          # (batch, 1, 64, 64)
        return x.flatten(start_dim=1)    # (batch, 4096)
