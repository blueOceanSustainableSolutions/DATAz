# Forwarding shim — actual config lives at src/config.py
import sys
import importlib.util
from pathlib import Path
import torch

_shared_config_path = Path(__file__).resolve().parents[1] / "config.py"
_spec = importlib.util.spec_from_file_location("shared_config", str(_shared_config_path))
_shared_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_shared_module)

# Re-export all attributes from shared config
for _attr in dir(_shared_module):
    if not _attr.startswith("_"):
        globals()[_attr] = getattr(_shared_module, _attr)
def print_config():
    """Print configuration summary"""
    from f_data_processing import resolve_data_path, FILE_PATHS
    
    print("=" * 80)
    print("CONFIGURATION SUMMARY for Experiment:", EXPERIMENT_NAME)
    print("=" * 80)
    print(f"\nPaths:")
    print(f"  Project root:     {PROJECT_ROOT}")
    print(f"  Data path:        {resolve_data_path(DATA_PATH)}")
    
    print(f"\nData:")    
    print(f" Compression Grid size: {GRID_SIZE[0]}x{GRID_SIZE[1]}")
    print(f" Number of folders found:{len(FILE_PATHS)}")

    print(f"\nModel Configuration:")
    print(f"  Previous wind steps:      {PREVIOUS_INPUT_STEPS}")
    print(f"  Previous boundary steps:  {PREVIOUS_BOUNDARY_STEPS}")
    print(f"  Input variables:  {len(INPUT_VARS)} ({', '.join(INPUT_VARS)})")
    print(f"  Target variables: {len(TARGET_VARS)} ({', '.join(TARGET_VARS)})")
    print(f"  Input channels:   {get_num_input_channels()}")
    print(f"  Output channels:  {get_num_output_channels()}")
    
    print(f"\n Training:")
    print(f"  Batch size:       {TRAINING_CONFIG['batch_size']}")
    print(f"  Learning rate:    {TRAINING_CONFIG['learning_rate']}")
    print(f"  Max epochs:       {TRAINING_CONFIG['num_epochs']}")
    print(f"  Early stopping:   {TRAINING_CONFIG['early_stopping']} (patience={TRAINING_CONFIG['patience']})")
    print(f"  Device:           {TRAINING_CONFIG['device']}")
    print(f"  Train: {TRAIN_RATIO*100:.0f}% | Val: {VAL_RATIO*100:.0f}% | Test: {TEST_RATIO*100:.0f}%")
    print("=" * 80)

    print("GPU:", torch.cuda.is_available())

if __name__ == "__main__":
    print_config()
