import torch
import torch.nn as nn

from .common_blocks import DebugConvBlock


class UNet(nn.Module):
    """Small fallback model when 'unet' is selected in config for debugging only."""

    def __init__(
        self,
        input_channels: int,
        output_channels: int,
        base_channels: int = 64,
        depth: int = 4,
        dropout: float = 0.1,
    ):
        super().__init__()
        _ = depth
        self.net = nn.Sequential(
            DebugConvBlock(input_channels, base_channels, kernel_size=3, dropout=0.0),
            DebugConvBlock(base_channels, base_channels, kernel_size=3, dropout=dropout),
            nn.Conv2d(base_channels, output_channels, kernel_size=1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)
