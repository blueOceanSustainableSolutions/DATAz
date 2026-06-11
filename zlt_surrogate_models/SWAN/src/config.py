"""
Configuration module for SWAN CNN Surrogate Model

This module contains all configuration parameters for:
- Data paths and grid specifications
- Variable metadata and groupings
- Model hyperparameters
- Training settings
- Data splitting ratios
"""

import os
from pathlib import Path
from torch import cuda
import torch

# =============================================================================
# PROJECT PATHS
# =============================================================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent

PREPROCESSED_ROOT = PROJECT_ROOT / 'data' / 'general_preprocessing'
MODEL_DIR = PROJECT_ROOT / 'models'
RESULTS_DIR = PROJECT_ROOT / 'results'
SCALER_DIR = PROJECT_ROOT / 'models' / 'scalers' 

# Create directories if they don't exist
for directory in [MODEL_DIR, RESULTS_DIR, SCALER_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# =============================================================================
# DATA SPECIFICATIONS
# =============================================================================
GRID_SIZE = [128, 128]

# parent folder containing all case folders
DATA_PATH = PREPROCESSED_ROOT / f"grid_{GRID_SIZE[0]}_{GRID_SIZE[1]}"

# =============================================================================
# VARIABLE CONFIGURATION
# =============================================================================
# Wind input variables (temporal)
WIND_VARS = ['u10', 'v10']

# Boundary forcing variables (temporal)
BOUNDARY_VARS = ['swh', 'pp1d', 'mwd_sin', 'mwd_cos']

# Bathymetry (static)
BATHY_VARS = ['elevation']

# Wave output variables (targets)
TARGET_VARS = ['HSig', 'PDIR_sin', 'PDIR_cos']  # 'RTP' is excluded for now due to data quality issues

# All input variables (used for model)
INPUT_VARS = WIND_VARS + BOUNDARY_VARS + BATHY_VARS

# Variable metadata for visualization and analysis
VARIABLE_METADATA = { 
    # Wind inputs
    'u10': {
        'label_short': 'U10',
        'label_long': 'U-component Wind at 10m',
        'cmap': 'RdBu_r',
        'unit': 'm/s',
        'type': 'input',
        'temporal': True
    },
    'v10': {
        'label_short': 'V10',
        'label_long': 'V-component Wind at 10m',
        'cmap': 'RdBu_r',
        'unit': 'm/s',
        'type': 'input',
        'temporal': True
    },
    # Bathymetry input
    'elevation': {
        'label_short': 'Depth',
        'label_long': 'Bathymetry',
        'cmap': 'terrain',
        'unit': 'm',
        'type': 'input',
        'temporal': False
    },
    # Boundary forcing
    'swh': {
        'label_short': 'SWH',
        'label_long': 'Significant Wave Height (Boundary)',
        'cmap': 'Blues',
        'unit': 'm',
        'type': 'input',
        'temporal': True
    },
    'pp1d': {
        'label_short': 'PP1D',
        'label_long': 'Peak Period (Boundary)',
        'cmap': 'Greens',
        'unit': 's',
        'type': 'input',
        'temporal': True
    },
    'mwd_sin': {
        'label_short': 'MWD_SIN',
        'label_long': 'Mean Wave Direction Sine (Boundary)',
        'cmap': 'Reds',
        'unit': '',
        'type': 'input',
        'temporal': True
    },
    'mwd_cos': {
        'label_short': 'MWD_COS',
        'label_long': 'Mean Wave Direction Cosine (Boundary)',
        'cmap': 'Reds',
        'unit': '',
        'type': 'input',
        'temporal': True
    },
        
    # Wave outputs (targets)
    'HSig': {
        'label_short': 'HSig',
        'label_long': 'Significant Wave Height',
        'cmap': 'Blues',
        'unit': 'm',
        'type': 'output',
        'temporal': False
    },

    'RTP': {
        'label_short': 'RTP',
        'label_long': 'Peak Period',
        'cmap': 'Greens',
        'unit': 's',
        'type': 'output',
        'temporal': False
    },
    'PDIR_sin': {
        'label_short': 'PDIR_SIN',
        'label_long': 'Peak Wave Direction Sine Component',
        'cmap': 'hsv',
        'unit': '',
        'type': 'output',
        'temporal': False
    },
    'PDIR_cos': {
        'label_short': 'PDIR_COS',
        'label_long': 'Peak Wave Direction Cosine Component',
        'cmap': 'hsv',
        'unit': '',
        'type': 'output',
        'temporal': False
    }
}

# =============================================================================
# TEMPORAL WINDOWING
# =============================================================================
# Number of previous time steps used to predict wave outputs at current time t.
PREVIOUS_INPUT_STEPS = 2
PREVIOUS_BOUNDARY_STEPS = 2

# =============================================================================
# DATA SPLITTING
# =============================================================================
TRAIN_RATIO = 0.70
VAL_RATIO = 0.15
TEST_RATIO = 0.15

# =============================================================================
# SCALE
# =============================================================================
SCALER_NAME = 'scaler1.pkl'
SCALER_PATH = SCALER_DIR / SCALER_NAME
SCALER_TYPE = {
    'u10': 'standard',
    'v10': 'standard',
    'elevation': 'minmax',
    'swh': 'standard',
    'pp1d': 'standard',
    'mwd': 'standard',
    'HSig': 'standard',
    'RTP': 'standard',
    'PDIR': 'standard'
}

# =============================================================================
# MODEL HYPERPARAMETERS
# =============================================================================
MODEL_CONFIG_All = {
    'spatial_cnn': {
        'input_channels': None,  # Will be computed dynamically
        'output_channels': len(TARGET_VARS),
        'base_channels': 64,
        'num_layers': 4,
        'kernel_size': 3,
        'dropout': 0.1
    },
    'unet': {
        'input_channels': None,  # Will be computed dynamically
        'output_channels': len(TARGET_VARS),
        'base_channels': 64,
        'depth': 4,
        'dropout': 0.1
    },
    'physics_unet2': {
        'input_channels': None,        # set dynamically
        'output_channels': 3,          # HSig, PDIR_sin, PDIR_cos
        'boundary_channels': 8,        # swh, pp1d, mwd_sin, mwd_cos × 2 timesteps
        'wind_bathy_channels': 5,      # u10, v10 × 2 timesteps + elevation
        'base_channels': 64,
        'dropout': 0.1,
    },
    'ctp': {
        'input_channels':      None,   # set dynamically (C per timestep)
        'output_channels':     3,      # e.g. frontal_prob, PDIR_sin, PDIR_cos
        'seq_len':             7,      # T input timesteps
        'd_model':             512,
        'nhead':               8,
        'num_encoder_layers':  2,
        'dim_feedforward':     1024,
        'dropout':             0.1,
    },
    # Override to a simpler, more robust model for debugging
    'convLSTM': {
        "input_channels": None,  # set dynamically
        "output_channels": 3,     # HSig, PDIR_sin, PDIR_cos
        "hidden_dim": [64, 128],
        "kernel_size": (3, 3),
        "num_layers": 2,
    }
}

MODEL_ARCHITECTURE = 'physics_unet2'  # Choose model architecture
MODEL_CONFIG = MODEL_CONFIG_All[MODEL_ARCHITECTURE]

# =============================================================================
# TRAINING CONFIGURATION
# =============================================================================
TRAINING_CONFIG = {
    'batch_size': 16,
    'num_epochs': 600,
    'learning_rate': 2e-4,
    'weight_decay': 1e-5,
    'optimizer': 'adamw',
    'loss_function': 'weighted_physics',
    
    # Early stopping
    'early_stopping': True,
    'patience': 50,
    'min_delta': 1e-4,
    
    # Checkpointing
    'save_best_model': True,
    
    # Device
    'device': 'cuda',  # 'cuda' or 'cpu'
    
    # Random seed for reproducibility
    'random_seed': 42,
    
    # Number of workers for data loading
    'num_workers': os.cpu_count() // 2 if os.cpu_count() > 1 else 0,
    'pin_memory': cuda.is_available(),
}

# =============================================================================
# EVALUATION CONFIGURATION
# =============================================================================
EVAL_CONFIG = {
    'metrics': ['rmse', 'mae', 'r2', 'mape'],
    'compute_per_gridpoint': True,
    'compute_per_variable': True,
    'compute_global': True
}

# =============================================================================
# VISUALIZATION CONFIGURATION
# =============================================================================
VIS_CONFIG = {
    'dpi': 150,
    'figsize_single': (10, 8),
    'figsize_comparison': (20, 6),
    'figsize_timeseries': (15, 5),
    'save_format': 'png',
    
    # Sample indices for visualization
    'n_visualization_samples': 5,
    
    # Grid points for time series analysis
    'timeseries_points': [
        (64, 64),   # Center
        (32, 32),   # Lower-left quadrant
        (96, 96),   # Upper-right quadrant
        (32, 96),   # Lower-right quadrant
        (96, 32)    # Upper-left quadrant
    ]
}

# =============================================================================
# NORMALIZATION CONFIGURATION
# =============================================================================
NORM_CONFIG = {
    'method': 'standardscaler',  # 'standardscaler' or 'minmax'
    'per_variable': True,
    'fit_on_train_only': True,
    'save_scalers': True
}

if MODEL_ARCHITECTURE == 'spatial_cnn':
    model_tag = f'{MODEL_CONFIG["num_layers"]}layers_{MODEL_CONFIG["base_channels"]}channels'
elif MODEL_ARCHITECTURE == 'unet':
    model_tag = f'depth{MODEL_CONFIG["depth"]}layers_{MODEL_CONFIG["base_channels"]}channels'
elif MODEL_ARCHITECTURE == 'physics_unet':
    model_tag = f'boundary{MODEL_CONFIG["boundary_channels"]}wind{MODEL_CONFIG["wind_bathy_channels"]}base{MODEL_CONFIG["base_channels"]}'
elif MODEL_ARCHITECTURE == 'physics_unet2':
    model_tag = f'boundary{MODEL_CONFIG["boundary_channels"]}wind{MODEL_CONFIG["wind_bathy_channels"]}base{MODEL_CONFIG["base_channels"]}_filled'
elif MODEL_ARCHITECTURE == 'ctp':
    model_tag = f'seq{MODEL_CONFIG["seq_len"]}dmodel{MODEL_CONFIG["d_model"]}nhead{MODEL_CONFIG["nhead"]}'
else:
    model_tag = 'model'

EXPERIMENT_NAME = (
    f'swan_surrogate_grid{GRID_SIZE[0]}x{GRID_SIZE[1]}_{MODEL_ARCHITECTURE}_'
    f'with_{model_tag}_{PREVIOUS_INPUT_STEPS}windsteps_{PREVIOUS_BOUNDARY_STEPS}boundarysteps'
)

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================
def get_num_input_channels(
    previous_input_steps: int = PREVIOUS_INPUT_STEPS,
    previous_boundary_steps: int = PREVIOUS_BOUNDARY_STEPS,
):
    """
    Calculate the number of input channels for the model.
    
    Temporal variables are replicated across the time window, while
    static variables (bathymetry) are included once.
    """
    if previous_input_steps < 0 or previous_boundary_steps < 0:
        raise ValueError("Previous step counts must be non-negative")

    wind_channels = len(WIND_VARS) * previous_input_steps
    boundary_channels = len(BOUNDARY_VARS) * previous_boundary_steps
    static_vars = len(BATHY_VARS)
    return wind_channels + boundary_channels + static_vars

def get_num_output_channels():
    """Get the number of output channels (target variables)."""
    return len(TARGET_VARS)
