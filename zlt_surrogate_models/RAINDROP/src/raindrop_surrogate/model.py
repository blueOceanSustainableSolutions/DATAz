"""
model.py — RadialAcousticSurrogate (v7)

Architecture overview:
  - BathyEncoder   : 1D CNN + point-wise distance refiner
  - AISEncoder     : MLP conditioned on ray scale (comp_ratio)
  - RadialAcousticSurrogate : integrates both encoders with Fourier
                              distance features and a 3-layer decoder.

All tensors follow the convention (B, R, L):
  B = batch size, R = number of rays, L = points per ray.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


class BathyEncoder(nn.Module):
    """
    Encodes a bathymetry ray into point-level latent features.

    Steps:
      1. 1-D CNN extracts global terrain context from the full ray.
      2. Context is expanded to every point along the ray.
      3. A point refiner MLP fuses terrain context, ray scale
         (comp_ratio) and the normalised absolute distance to the
         current point (abs_dist_norm) → per-point latent vector.

    Args:
        latent_dim (int): Output feature dimension per point.
    """

    def __init__(self, latent_dim: int = 128):
        super().__init__()

        self.conv_layers = nn.Sequential(
            nn.Conv1d(1, 16, kernel_size=7, stride=2, padding=3),
            nn.BatchNorm1d(16), nn.ReLU(),
            nn.Conv1d(16, 32, kernel_size=5, stride=2, padding=2),
            nn.BatchNorm1d(32), nn.ReLU(),
            nn.Conv1d(32, 64, kernel_size=3, stride=2, padding=1),
            nn.BatchNorm1d(64), nn.ReLU(),
            nn.AdaptiveAvgPool1d(8),          # → (B*R, 64, 8)
        )
        # Global context dim: 64 × 8 = 512
        # Point refiner input: global_ctx + comp_ratio + abs_dist_norm
        self.point_refiner = nn.Sequential(
            nn.Linear(512 + 1 + 1, 256),
            nn.ReLU(),
            nn.Linear(256, latent_dim),
        )

    def forward(
        self,
        x: torch.Tensor,           # (B*R, 1, L)
        comp_ratio: torch.Tensor,  # (B*R, 1)
        abs_dist_norm: torch.Tensor,  # (B*R*L, 1)
    ) -> torch.Tensor:             # (B*R*L, latent_dim)
        B_R, _, L = x.shape

        # Global ray context
        global_context = torch.flatten(self.conv_layers(x), 1)  # (B*R, 512)

        # Expand to point level
        global_expanded = (
            global_context.unsqueeze(1).expand(-1, L, -1).reshape(B_R * L, -1)
        )
        comp_ratio_exp = (
            comp_ratio.unsqueeze(1).expand(-1, L, -1).reshape(B_R * L, -1)
        )

        combined = torch.cat([global_expanded, comp_ratio_exp, abs_dist_norm], dim=-1)
        return self.point_refiner(combined)  # (B*R*L, latent_dim)


class AISEncoder(nn.Module):
    """
    Encodes AIS ship features into a ray-level latent vector.

    The encoder is conditioned on the ray's comp_ratio so that the
    ship embedding is aware of the propagation scale.

    Args:
        input_dim (int): Number of AIS input features (default 3:
                         speed, ship-type, length).
        latent_dim (int): Output feature dimension per ray.
    """

    def __init__(self, input_dim: int = 3, latent_dim: int = 64):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim + 1, 128), nn.ReLU(),
            nn.Linear(128, latent_dim),    nn.ReLU(),
        )

    def forward(
        self,
        x: torch.Tensor,           # (B*R, ais_features)
        comp_ratio: torch.Tensor,  # (B*R, 1)
    ) -> torch.Tensor:             # (B*R, latent_dim)
        ais_feats = x[:, 2:]       # speed, type, length (skip lat/lon)
        return self.net(torch.cat([ais_feats, comp_ratio], dim=-1))


class RadialAcousticSurrogate(nn.Module):
    """
    Distance-conditioned vectorised surrogate for underwater acoustics.

    Given bathymetry rays, AIS ship data, and ray lengths (t_max),
    predicts normalised SPL along every ray in a single forward pass.

    Args:
        bathy_latent (int): Latent dim for BathyEncoder.
        ais_latent   (int): Latent dim for AISEncoder.
        crop_size    (int): Spatial grid side length used to normalise
                            distances (sets max_grid_dist).
    """

    def __init__(
        self,
        bathy_latent: int = 128,
        ais_latent: int = 64,
        crop_size: int = 256,
    ):
        super().__init__()

        self.bathy_encoder = BathyEncoder(latent_dim=bathy_latent)
        self.ais_encoder   = AISEncoder(latent_dim=ais_latent)

        self.max_grid_dist    = (2 ** 0.5) * crop_size
        self.dist_mapping_dim = 16  # Fourier feature channels (sin + cos pairs)

        # Decoder input: bathy_latent + ais_latent + comp_ratio + Fourier feats
        decoder_in = bathy_latent + ais_latent + 1 + self.dist_mapping_dim
        self.fc1 = nn.Linear(decoder_in, 256)
        self.fc2 = nn.Linear(256 + self.dist_mapping_dim, 256)  # skip Fourier
        self.fc3 = nn.Linear(256, 1)

    def forward(
        self,
        bathy_rays: torch.Tensor,  # (B, R, L)
        ais_info: torch.Tensor,    # (B, ais_features)
        t_max: torch.Tensor,       # (B, R)
    ) -> torch.Tensor:             # (B, R, L)  — normalised SPL in [0, 1]
        B, R, L = bathy_rays.shape

        
        comp_ratio    = t_max.view(B * R, 1) / (self.max_grid_dist + 1e-6)
        dist_step     = torch.linspace(0, 1, steps=L, device=bathy_rays.device)
        abs_dist_norm = (comp_ratio @ dist_step.unsqueeze(0)).view(B * R * L, 1)

        
        b_feat_point = self.bathy_encoder(
            bathy_rays.view(B * R, 1, L), comp_ratio, abs_dist_norm
        )  # (B*R*L, bathy_latent)

        ais_exp  = ais_info.unsqueeze(1).expand(-1, R, -1).reshape(B * R, -1)
        a_feat   = self.ais_encoder(ais_exp, comp_ratio)  # (B*R, ais_latent)

        
        freqs    = torch.pow(
            2,
            torch.arange(self.dist_mapping_dim // 2, device=bathy_rays.device),
        ).float()
        d_scaled  = abs_dist_norm * freqs * 3.14159
        dist_feat = torch.cat([torch.sin(d_scaled), torch.cos(d_scaled)], dim=-1)
        # (B*R*L, dist_mapping_dim)

        
        a_feat_pt      = a_feat.unsqueeze(1).expand(-1, L, -1).reshape(B * R * L, -1)
        comp_ratio_pt  = comp_ratio.unsqueeze(1).expand(-1, L, -1).reshape(B * R * L, -1)

        point_ctx = torch.cat(
            [b_feat_point, a_feat_pt, comp_ratio_pt, dist_feat], dim=-1
        )

        
        x = F.relu(self.fc1(point_ctx))
        x = torch.cat([x, dist_feat], dim=-1)   # Fourier skip connection
        x = F.relu(self.fc2(x))
        out = torch.sigmoid(self.fc3(x))

        return out.view(B, R, L)
