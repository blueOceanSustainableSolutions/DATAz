import torch
import torch.nn as nn

from .common_blocks import DebugConvBlock


class SpatialCNN(nn.Module):
    """Configurable simple CNN for spatial surrogate debugging."""

    def __init__(
        self,
        input_channels: int,
        output_channels: int,
        base_channels: int = 64,
        num_layers: int = 4,
        kernel_size: int = 3,
        dropout: float = 0.1,
    ):
        super().__init__()
        if num_layers < 1:
            raise ValueError("num_layers must be >= 1")

        layers = []
        in_ch = input_channels
        for layer_idx in range(num_layers):
            out_ch = base_channels
            layers.append(
                DebugConvBlock(
                    in_channels=in_ch,
                    out_channels=out_ch,
                    kernel_size=kernel_size,
                    dropout=dropout if layer_idx > 0 else 0.0,
                )
            )
            in_ch = out_ch

        self.encoder = nn.Sequential(*layers)
        self.head = nn.Conv2d(in_ch, output_channels, kernel_size=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.encoder(x)
        x = self.head(x)
        return x
