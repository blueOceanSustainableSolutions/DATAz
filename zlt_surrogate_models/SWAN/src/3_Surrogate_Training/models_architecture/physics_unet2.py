import torch
import torch.nn as nn
import torch.nn.functional as F

from .common_blocks import AttentionGate, ConvBlock, SEBlock


class PhysicsUNet2(nn.Module):
    """U-Net variant for wave surrogate with boundary/wind encoders and attention skips."""

    def __init__(
        self,
        input_channels: int = 13,
        output_channels: int = 3,
        boundary_channels: int = 8,
        wind_bathy_channels: int = 5,
        base_channels: int = 64,
        dropout: float = 0.1,
    ):
        super().__init__()

        C = base_channels

        # 1. Boundary encoder (simple path, no dilation needed)
        self.boundary_enc = nn.Sequential(
            nn.Conv2d(boundary_channels, C, 3, padding=1, bias=False),
            nn.BatchNorm2d(C),
            nn.GELU(),
        )

        # 2. Wind + bathymetry encoder
        # 2. Wind + bathymetry encoder.
        # Accepts wind_bathy_channels + 2 extra channels: dx_elev, dy_elev.
        # Bathymetric gradients encode slope, the key physics driver of wave
        # refraction (direction changes) and shoaling (HSig amplification near shore).
        # They are computed on-the-fly in forward() so no config change is needed.
        self.wind_enc = nn.Sequential(
            nn.Conv2d(wind_bathy_channels + 2, C, 3, padding=1, bias=False),
            nn.BatchNorm2d(C),
            nn.GELU(),
        )

        # 3. U-Net encoder (fused input: boundary enc + wind enc = 2C)
        self.enc1 = ConvBlock(2 * C,     C,     dropout=0.0)
        self.enc2 = ConvBlock(C,         2 * C, dropout=dropout)
        self.enc3 = ConvBlock(2 * C,     4 * C, dropout=dropout)
        self.enc4 = ConvBlock(4 * C,     8 * C, dropout=dropout)

        self.pool = nn.MaxPool2d(2)

        # Bottleneck
        # Bottleneck + SE channel attention.
        # At 8×8 spatial resolution, local convolutions have limited reach;
        # SE provides complementary global context with minimal overhead.
        self.bottleneck = ConvBlock(8 * C, 16 * C, dropout=dropout)
        self.bottleneck_se = SEBlock(16 * C, reduction=16)

        self.att4 = AttentionGate(f_g=8 * C, f_l=8 * C, f_int=4 * C)
        self.up4 = nn.ConvTranspose2d(16 * C, 8 * C, 2, stride=2)
        self.dec4 = ConvBlock(16 * C, 8 * C, dropout=dropout)

        self.att3 = AttentionGate(f_g=4 * C, f_l=4 * C, f_int=2 * C)
        self.up3 = nn.ConvTranspose2d(8 * C, 4 * C, 2, stride=2)
        self.dec3 = ConvBlock(8 * C, 4 * C, dropout=dropout)

        self.att2 = AttentionGate(f_g=2 * C, f_l=2 * C, f_int=C)
        self.up2 = nn.ConvTranspose2d(4 * C, 2 * C, 2, stride=2)
        self.dec2 = ConvBlock(4 * C, 2 * C, dropout=dropout)

        self.att1 = AttentionGate(f_g=C, f_l=C, f_int=C // 2)
        self.up1 = nn.ConvTranspose2d(2 * C, C, 2, stride=2)
        self.dec1 = ConvBlock(2 * C, C, dropout=0.0)

        self.head_hsig = nn.Sequential(
            nn.Conv2d(C, C // 2, 3, padding=1, bias=False),
            nn.BatchNorm2d(C // 2),
            nn.GELU(),
            nn.Conv2d(C // 2, C // 4, 1),
            nn.GELU(),
            nn.Conv2d(C // 4, 1, 1),
        )

        self.head_pdir = nn.Sequential(
            nn.Conv2d(C, C // 2, 3, padding=1, bias=False),
            nn.BatchNorm2d(C // 2),
            nn.GELU(),
            nn.Conv2d(C // 2, C // 4, 1),
            nn.GELU(),
            nn.Conv2d(C // 4, 2, 1),
            nn.Tanh(),
        )

        self.head_hsig_skip = nn.Conv2d(C, 1, 1, bias=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        boundary = x[:, 4:12, :, :]
        wind_bathy = torch.cat([x[:, 0:4, :, :], x[:, 12:13, :, :]], dim=1)

        elev = wind_bathy[:, 4:5, :, :]
        dx_elev = F.pad(elev[:, :, :, 1:] - elev[:, :, :, :-1], (0, 1, 0, 0))
        dy_elev = F.pad(elev[:, :, 1:, :] - elev[:, :, :-1, :], (0, 0, 0, 1))
        wind_bathy_aug = torch.cat([wind_bathy, dx_elev, dy_elev], dim=1)

        b_enc = self.boundary_enc(boundary)
        w_enc = self.wind_enc(wind_bathy_aug)

        fused = torch.cat([b_enc, w_enc], dim=1)

        e1 = self.enc1(fused)
        e2 = self.enc2(self.pool(e1))
        e3 = self.enc3(self.pool(e2))
        e4 = self.enc4(self.pool(e3))

        bn = self.bottleneck_se(self.bottleneck(self.pool(e4)))

        g4 = self.up4(bn)
        d4 = self.dec4(torch.cat([g4, self.att4(g4, e4)], dim=1))
        g3 = self.up3(d4)
        d3 = self.dec3(torch.cat([g3, self.att3(g3, e3)], dim=1))
        g2 = self.up2(d3)
        d2 = self.dec2(torch.cat([g2, self.att2(g2, e2)], dim=1))
        g1 = self.up1(d2)
        d1 = self.dec1(torch.cat([g1, self.att1(g1, e1)], dim=1))

        hsig = self.head_hsig(d1) + self.head_hsig_skip(d1)
        pdir = self.head_pdir(d1)

        return torch.cat([hsig, pdir], dim=1)
