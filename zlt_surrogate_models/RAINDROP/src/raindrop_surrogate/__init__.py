# src/raindrop_surrogate/__init__.py

from .model import RadialAcousticSurrogate
from .dataset import AcousticDataset, ScaledDatasetWrapper, custom_collate, scale_data
from .utils import load_config, compute_physical_metrics, save_checkpoint, load_model
from .visualize import plot_radial_comparison, plot_training_curves, plot_metrics_table

# __all__ defines what gets imported if someone runs: from acoustics_surrogate import *
__all__ = [
    "RadialAcousticSurrogate",
    "AcousticDataset",
    "load_config",
    "ScaledDatasetWrapper",
    "custom_collate",
    "scale_data",
    "compute_physical_metrics",
    "save_checkpoint",
    "load_model",
    "plot_radial_comparison",
    "plot_training_curves",
    "plot_metrics_table"    

]