import torch.nn as nn

from .conv_lstm import ConvLSTM
from .ctp_model import CTPModel
from .physics_unet2 import PhysicsUNet2
from .spatial_cnn import SpatialCNN
from .unet import UNet


def create_model(model_name: str, model_config: dict) -> nn.Module:
    """Factory to build model instances from config.py definitions."""
    name = model_name.lower()

    if name == "spatial_cnn":
        return SpatialCNN(
            input_channels=model_config["input_channels"],
            output_channels=model_config["output_channels"],
            base_channels=model_config.get("base_channels", 64),
            num_layers=model_config.get("num_layers", 4),
            kernel_size=model_config.get("kernel_size", 3),
            dropout=model_config.get("dropout", 0.1),
        )

    if name == "unet":
        return UNet(
            input_channels=model_config["input_channels"],
            output_channels=model_config["output_channels"],
            base_channels=model_config.get("base_channels", 64),
            depth=model_config.get("depth", 4),
            dropout=model_config.get("dropout", 0.1),
        )

    if name == "physics_unet2":
        return PhysicsUNet2(
            input_channels=model_config["input_channels"],
            output_channels=model_config["output_channels"],
            boundary_channels=model_config.get("boundary_channels", 8),
            wind_bathy_channels=model_config.get("wind_bathy_channels", 5),
            base_channels=model_config.get("base_channels", 64),
            dropout=model_config.get("dropout", 0.1),
        )

    if name == "ctp":
        return CTPModel(
            input_channels=model_config["input_channels"],
            output_channels=model_config["output_channels"],
            seq_len=model_config.get("seq_len", 7),
            d_model=model_config.get("d_model", 512),
            nhead=model_config.get("nhead", 8),
            num_encoder_layers=model_config.get("num_encoder_layers", 2),
            dim_feedforward=model_config.get("dim_feedforward", 1024),
            dropout=model_config.get("dropout", 0.1),
        )
    
    if name == "convlstm":
        return ConvLSTM(
            input_dim=model_config["input_channels"],
            output_dim=model_config["output_channels"],
            hidden_dim=model_config.get("hidden_dim", [64, 64]),
            kernel_size=model_config.get("kernel_size", (3, 3)),
            num_layers=model_config.get("num_layers", 2),
            batch_first=True
        )

    raise ValueError(f"Unsupported model architecture '{model_name}'.")
