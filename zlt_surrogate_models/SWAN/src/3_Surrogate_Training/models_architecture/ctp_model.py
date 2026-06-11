import torch
import torch.nn as nn

from .common_blocks import CNNDecoder, CNNEncoder


class CTPModel(nn.Module):
    """CNN-Transformer-PINN model for ocean front forecasting."""

    ENC_CHANNELS = 32
    ENC_H = 75
    ENC_W = 75
    ENC_FLAT = ENC_CHANNELS * ENC_H * ENC_W

    def __init__(
        self,
        input_channels: int,
        output_channels: int,
        seq_len: int = 7,
        d_model: int = 512,
        nhead: int = 8,
        num_encoder_layers: int = 2,
        dim_feedforward: int = 1024,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.seq_len = seq_len
        self.output_channels = output_channels

        self.cnn_encoder = CNNEncoder(input_channels)
        self.input_proj = nn.Linear(self.ENC_FLAT, d_model)

        self.pos_embedding = nn.Parameter(torch.zeros(1, seq_len, d_model))
        nn.init.trunc_normal_(self.pos_embedding, std=0.02)

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=dim_feedforward,
            dropout=dropout,
            batch_first=True,
            norm_first=False,
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_encoder_layers)

        self.output_proj = nn.Linear(d_model, self.ENC_FLAT)
        self.cnn_decoder = CNNDecoder(output_channels)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if x.dim() == 4:
            batch_size, tc, h, w = x.shape
            channels = tc // self.seq_len
            x = x.view(batch_size, self.seq_len, channels, h, w)

        batch_size, time_steps, channels, h, w = x.shape
        x = x.reshape(batch_size * time_steps, channels, h, w)
        x = self.cnn_encoder(x)
        x = x.reshape(batch_size, time_steps, self.ENC_FLAT)

        x = self.input_proj(x)
        x = x + self.pos_embedding[:, :time_steps, :]

        x = self.transformer(x)
        x = x.mean(dim=1)

        x = self.output_proj(x)
        x = x.reshape(batch_size, self.ENC_CHANNELS, self.ENC_H, self.ENC_W)

        x = self.cnn_decoder(x)

        if self.output_channels >= 1:
            frontal = torch.sigmoid(x[:, :1, :, :])
            rest = x[:, 1:, :, :]
            x = torch.cat([frontal, rest], dim=1)

        return x
