import torch
import torch.nn as nn
import torch.nn.functional as F


class ConvBlock(nn.Module):
    """Double conv block with residual skip."""

    def __init__(self, in_ch, out_ch, dropout=0.0):
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(in_ch, out_ch, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.GELU(),
            nn.Conv2d(out_ch, out_ch, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.GELU(),
            nn.Dropout2d(p=dropout),
        )
        self.skip = nn.Conv2d(in_ch, out_ch, 1, bias=False) if in_ch != out_ch else nn.Identity()
        if isinstance(self.skip, nn.Conv2d):
            nn.init.zeros_(self.skip.weight)

    def forward(self, x):
        return self.block(x) + self.skip(x)


class AttentionGate(nn.Module):
    """Spatial attention gate for skip connections."""

    def __init__(self, f_g, f_l, f_int):
        super().__init__()
        self.W_g = nn.Sequential(
            nn.Conv2d(f_g, f_int, 1, bias=False),
            nn.BatchNorm2d(f_int),
        )
        self.W_x = nn.Sequential(
            nn.Conv2d(f_l, f_int, 1, bias=False),
            nn.BatchNorm2d(f_int),
        )
        self.psi = nn.Sequential(
            nn.Conv2d(f_int, 1, 1, bias=False),
            nn.BatchNorm2d(1),
            nn.Sigmoid(),
        )

    def forward(self, g, x):
        g1 = self.W_g(g)
        x1 = self.W_x(x)
        psi = F.relu(g1 + x1, inplace=True)
        psi = self.psi(psi)
        return x * psi


class SEBlock(nn.Module):
    """Squeeze-and-Excitation channel attention.

    Learns a per-channel recalibration from global average-pooled context.
    Applied at the bottleneck (8×8 spatial) where local convolutions cannot
    capture cross-domain relationships (e.g. which boundary frequency matters
    most for this wind pattern). Adds negligible parameter count.
    """
    def __init__(self, channels: int, reduction: int = 16):
        super().__init__()
        self.pool = nn.AdaptiveAvgPool2d(1)
        mid = max(channels // reduction, 8)
        self.fc = nn.Sequential(
            nn.Linear(channels, mid, bias=False),
            nn.GELU(),
            nn.Linear(mid, channels, bias=False),
            nn.Sigmoid(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        b, c = x.shape[:2]
        scale = self.pool(x).view(b, c)
        scale = self.fc(scale).view(b, c, 1, 1)
        return x * scale


class BoundaryPropagationPrior(nn.Module):
    """Learnable boundary propagation with dilated convolutions."""

    def __init__(self, boundary_ch, out_ch):
        super().__init__()
        self.dilated = nn.Sequential(
            nn.Conv2d(boundary_ch, out_ch, 3, padding=1, dilation=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.GELU(),
            nn.Conv2d(out_ch, out_ch, 3, padding=2, dilation=2, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.GELU(),
            nn.Conv2d(out_ch, out_ch, 3, padding=4, dilation=4, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.GELU(),
            nn.Conv2d(out_ch, out_ch, 3, padding=8, dilation=8, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.GELU(),
            nn.Conv2d(out_ch, out_ch, 3, padding=16, dilation=16, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.GELU(),
            nn.Conv2d(out_ch, out_ch, 3, padding=32, dilation=32, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.GELU(),
        )
        self.skip = nn.Conv2d(boundary_ch, out_ch, 1, bias=False)

    def forward(self, x):
        return self.dilated(x) + self.skip(x)


class CNNEncoder(nn.Module):
    """2-layer CNN encoder: (B, C, 300, 300) -> (B, 32, 75, 75)."""

    def __init__(self, input_channels: int):
        super().__init__()
        self.layer1 = nn.Sequential(
            nn.Conv2d(input_channels, 16, kernel_size=3, stride=2, padding=1),
            nn.GroupNorm(num_groups=4, num_channels=16),
            nn.ReLU(inplace=True),
        )
        self.layer2 = nn.Sequential(
            nn.Conv2d(16, 32, kernel_size=3, stride=2, padding=1),
            nn.GroupNorm(num_groups=8, num_channels=32),
            nn.ReLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.layer1(x)
        x = self.layer2(x)
        return x


class CNNDecoder(nn.Module):
    """2-layer CNN decoder: (B, 32, 75, 75) -> (B, output_channels, 300, 300)."""

    def __init__(self, output_channels: int):
        super().__init__()
        self.layer1 = nn.Sequential(
            nn.ConvTranspose2d(32, 16, kernel_size=4, stride=2, padding=1),
            nn.GroupNorm(num_groups=4, num_channels=16),
            nn.ReLU(inplace=True),
        )
        self.layer2 = nn.ConvTranspose2d(16, output_channels, kernel_size=4, stride=2, padding=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.layer1(x)
        x = self.layer2(x)
        return x


class DebugConvBlock(nn.Module):
    """Simple Conv-BN-ReLU-Dropout block used by debug models."""

    def __init__(self, in_channels: int, out_channels: int, kernel_size: int = 3, dropout: float = 0.0):
        super().__init__()
        padding = kernel_size // 2
        self.block = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, kernel_size=kernel_size, padding=padding, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Dropout2d(p=dropout),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.block(x)
