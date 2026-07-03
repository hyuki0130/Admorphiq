"""CNN backbone for ARC-AGI-3 frame perception.

Capacity is parameterised (``width_mult`` + ``extra_block``) so the online
test-time RL agent can build a LARGER policy per game when the ``RL_CNN_WIDTH`` /
``RL_CNN_CAPACITY`` env knob is set. The DEFAULTS reproduce the committed
architecture byte-for-byte (channels 16->32->64->128->256, no extra block), so a
regression run with the knob unset is unchanged and BC-v6 warm-start weights
still load.
"""

import torch
import torch.nn as nn

# Committed default backbone channel plan (input 16ch one-hot -> 256ch features).
BASE_CHANNELS: tuple[int, int, int, int] = (32, 64, 128, 256)


def _scaled_channels(width_mult: float) -> tuple[int, int, int, int]:
    """Scale the base channel plan by ``width_mult`` (>=1.0), rounding to int.

    ``width_mult == 1.0`` returns ``BASE_CHANNELS`` exactly so the default
    backbone is byte-identical to the committed one.
    """
    if width_mult == 1.0:
        return BASE_CHANNELS
    c1, c2, c3, c4 = BASE_CHANNELS
    return (
        max(1, round(c1 * width_mult)),
        max(1, round(c2 * width_mult)),
        max(1, round(c3 * width_mult)),
        max(1, round(c4 * width_mult)),
    )


class CNNBackbone(nn.Module):
    """CNN encoder for 16-channel one-hot encoded 64x64 frames.

    Args:
        width_mult: Multiplier on the base channel plan (32,64,128,256). Default
            1.0 => committed architecture. Values >1.0 widen every conv.
        extra_block: When True, append one extra conv block (kept at the final
            channel width) after the base plan, deepening the backbone. Default
            False => committed depth. The output channel count is unchanged
            whether or not the extra block is present, so the heads' input
            contract does not depend on this flag.
    """

    def __init__(self, width_mult: float = 1.0, extra_block: bool = False) -> None:
        super().__init__()
        c1, c2, c3, c4 = _scaled_channels(width_mult)
        layers: list[nn.Module] = [
            nn.Conv2d(16, c1, kernel_size=3, padding=1),   # (B, c1, 64, 64)
            nn.ReLU(inplace=True),
            nn.Conv2d(c1, c2, kernel_size=3, padding=1),   # (B, c2, 64, 64)
            nn.ReLU(inplace=True),
            nn.Conv2d(c2, c3, kernel_size=3, padding=1),   # (B, c3, 64, 64)
            nn.ReLU(inplace=True),
            nn.Conv2d(c3, c4, kernel_size=3, padding=1),   # (B, c4, 64, 64)
            nn.ReLU(inplace=True),
        ]
        if extra_block:
            layers += [
                nn.Conv2d(c4, c4, kernel_size=3, padding=1),  # (B, c4, 64, 64)
                nn.ReLU(inplace=True),
            ]
        self.features = nn.Sequential(*layers)
        self.out_channels: int = c4

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass.

        Args:
            x: Input tensor of shape (batch, 16, 64, 64).

        Returns:
            Feature map of shape (batch, out_channels, 64, 64).
        """
        return self.features(x)  # (batch, out_channels, 64, 64)


class ActionHead(nn.Module):
    """Predicts change probability for ACTION1~5.

    Args:
        in_channels: Channel count of the backbone feature map. Default 256 =>
            committed head (fc1 in-dim 256*16*16).
    """

    def __init__(self, in_channels: int = 256) -> None:
        super().__init__()
        self.pool = nn.MaxPool2d(kernel_size=4)  # (B, in_channels, 16, 16)
        self.fc1 = nn.Linear(in_channels * 16 * 16, 512)
        self.dropout = nn.Dropout(0.2)
        self.fc2 = nn.Linear(512, 5)

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        """Forward pass.

        Args:
            features: CNN feature map of shape (batch, in_channels, 64, 64).

        Returns:
            Action logits of shape (batch, 5).
        """
        x = self.pool(features)          # (batch, in_channels, 16, 16)
        x = x.flatten(start_dim=1)       # (batch, in_channels*16*16)
        x = self.dropout(torch.relu(self.fc1(x)))
        return self.fc2(x)               # (batch, 5)


class CoordinateHead(nn.Module):
    """Fully convolutional head for ACTION6 coordinate prediction.

    Args:
        in_channels: Channel count of the backbone feature map. Default 256 =>
            committed head (first conv 256->128).
    """

    def __init__(self, in_channels: int = 256) -> None:
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(in_channels, 128, kernel_size=3, padding=1),  # (B, 128, 64, 64)
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
            features: CNN feature map of shape (batch, in_channels, 64, 64).

        Returns:
            Coordinate logits of shape (batch, 4096).
        """
        x = self.conv(features)          # (batch, 1, 64, 64)
        return x.flatten(start_dim=1)    # (batch, 4096)
