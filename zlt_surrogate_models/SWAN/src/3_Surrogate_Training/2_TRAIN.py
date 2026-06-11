"""
SWAN Surrogate - Training Pipeline

Purpose:
1. Load saved tensor sequences
2. Build dataloaders
3. Train model
4. Evaluate and visualize outputs
"""

import argparse
from datetime import datetime
import torch
import warnings
from pathlib import Path
from torch.utils.data import DataLoader

warnings.filterwarnings("ignore")

from config import (
    print_config,
    MODEL_DIR,
    PROJECT_ROOT,
    RESULTS_DIR,
    TRAINING_CONFIG,
    MODEL_ARCHITECTURE,
    MODEL_CONFIG,
    EVAL_CONFIG,
    VIS_CONFIG,
    SCALER_PATH,
    TARGET_VARS,
    get_num_input_channels,
    get_num_output_channels,
)
from dataloader import TensorDataset
from models_architecture import create_model
from train_stage import train_model, import_model
from evaluate_stage import run_evaluation
from visualize_stage import run_visualization
from f_data_processing import import_scale
# MLflow removed from workflow. No MLflow imports or trackers remain.


def parse_args():
    parser = argparse.ArgumentParser(description="Train SWAN model from saved sequence datasets")
    parser.add_argument("--batch-size", type=int, default=TRAINING_CONFIG.get("batch_size", 4), help="Batch size")
    parser.add_argument("--num-workers", type=int, default=0, help="DataLoader workers")
    parser.add_argument("--pin-memory", action="store_true", help="Enable DataLoader pin_memory")
    parser.add_argument(
        "--sequence-name",
        type=str,
        default="500",
        help="Sequence dataset name to load (for example: 500, 8000, 20000)",
    )
    parser.add_argument(
        "--sequences-root",
        type=str,
        default=str(PROJECT_ROOT / "data" / "sequences"),
        help="Root directory that contains saved sequence sets",
    )
    # MLflow options removed from CLI
    return parser.parse_args()


def step1_load_sequences(sequences_path: Path, print_flag: bool = True):
    """Load saved sequences and create train/val/test dataloaders."""
    if not sequences_path.exists():
        raise FileNotFoundError(
            f"Sequence file not found: {sequences_path}. Run 1_PREPROCESS.py first."
        )

    saved_sequences = torch.load(sequences_path, map_location="cpu")

    train_key = "train_sequences" if "train_sequences" in saved_sequences else "train_samples"
    val_key = "val_sequences" if "val_sequences" in saved_sequences else "val_samples"
    test_key = "test_sequences" if "test_sequences" in saved_sequences else "test_samples"

    train_sa = TensorDataset(saved_sequences[train_key])
    val_sa = TensorDataset(saved_sequences[val_key])
    test_sa = TensorDataset(saved_sequences[test_key])

    def _sample_has_time(split_samples) -> bool:
        if not split_samples:
            return False
        sample = split_samples[0]
        return isinstance(sample, (tuple, list)) and len(sample) >= 3

    has_time_train = _sample_has_time(saved_sequences[train_key])
    has_time_val = _sample_has_time(saved_sequences[val_key])
    has_time_test = _sample_has_time(saved_sequences[test_key])

    train_loader = DataLoader(
        train_sa,
        batch_size=TRAINING_CONFIG["batch_size"],
        shuffle=True,
        num_workers=TRAINING_CONFIG["num_workers"],
        pin_memory=TRAINING_CONFIG["pin_memory"],
        drop_last=True,
    )
    val_loader = DataLoader(
        val_sa,
        batch_size=TRAINING_CONFIG["batch_size"],
        shuffle=False,
        num_workers=TRAINING_CONFIG["num_workers"],
        pin_memory=TRAINING_CONFIG["pin_memory"],
        drop_last=False,
    )
    test_loader = DataLoader(
        test_sa,
        batch_size=TRAINING_CONFIG["batch_size"],
        shuffle=False,
        num_workers=TRAINING_CONFIG["num_workers"],
        pin_memory=TRAINING_CONFIG["pin_memory"],
        drop_last=False,
    )

    if print_flag:
        print(f"  Loaded sequence file: {sequences_path}")
        print(f"  Train batches: {len(train_loader)} | Val batches: {len(val_loader)} | Test batches: {len(test_loader)}")
        if not (has_time_train and has_time_val and has_time_test):
            print("  WARNING: Loaded sequences do not include sample timestamps.")
            print("           Comparison titles will not include data time until sequences are regenerated.")

    return train_loader, val_loader, test_loader


def step2_build_model(train_loader, print_flag: bool = True):
    """Build model from config and run one debug forward pass."""
    configured_device = TRAINING_CONFIG.get("device", "cpu")
    cuda_available = torch.cuda.is_available()
    resolved_device = configured_device if cuda_available else "cpu"

    if configured_device == "cuda" and not cuda_available:
        print("    WARNING: CUDA configured but not available. Falling back to CPU.")

    model_cfg = dict(MODEL_CONFIG)
    model_cfg["input_channels"] = get_num_input_channels()
    model_cfg["output_channels"] = get_num_output_channels()

    model = create_model(MODEL_ARCHITECTURE, model_cfg).to(resolved_device)

    if print_flag:
        n_params = sum(p.numel() for p in model.parameters())
        n_trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
        print(f"  Architecture: {MODEL_ARCHITECTURE}")
        print(f"  Input channels: {model_cfg['input_channels']} | Output channels: {model_cfg['output_channels']}")
        print(f"  Device: {resolved_device}")
        print(f"  Parameters: total={n_params:,} | trainable={n_trainable:,}")

        model.eval()
        with torch.no_grad():
            for batch in train_loader:
                if len(batch) == 3:
                    inputs, targets, _ = batch
                elif len(batch) == 2:
                    inputs, targets = batch
                else:
                    raise ValueError(f"Unexpected batch size {len(batch)}; expected 2 or 3 items.")

                # Models like ConvLSTM and CTP expect a 5D tensor: 
                # (batch, seq_len, channels, height, width)
                inputs_for_model = inputs
                if MODEL_ARCHITECTURE.lower() in ["convlstm", "ctp"]:
                    if inputs.dim() == 4:
                        # Add sequence dimension: (batch, channels, h, w) -> (batch, 1, channels, h, w)
                        # Treat all input channels as a single timestep
                        inputs_for_model = inputs.unsqueeze(1)

                preds = model(inputs_for_model.to(resolved_device))
                print(f"  Debug forward: {inputs_for_model.shape} -> {preds.shape} (target: {targets.shape})")
                break

    return model


def step3_train_model(model, train_loader, val_loader, model_name: str, TRAIN_MODEL: bool = True):
    """Train model or import checkpoint and return history + training info."""
    checkpoint_path = MODEL_DIR / f"{model_name}.pt"

    if TRAIN_MODEL:
        return train_model(
            model=model,
            train_loader=train_loader,
            val_loader=val_loader,
            training_config=TRAINING_CONFIG,
            model_dir=MODEL_DIR,
            model_name=model_name,
        )

    _, train_info = import_model(
        model=model,
        checkpoint_path=checkpoint_path,
        device=TRAINING_CONFIG.get("device", "cpu"),
    )
    empty_history = {
        "epoch": [],
        "train_loss": [],
        "val_loss": [],
        "epoch_time_sec": [],
        "learning_rate": [],
    }
    return empty_history, train_info
    


def step4_evaluate_model(model, val_loader, test_loader, train_info, print_flag: bool = True):
    """Evaluate model and return metrics plus optional snapshot data."""
    scaler = import_scale(SCALER_PATH)
    eval_payload = run_evaluation(
        model=model,
        val_loader=val_loader,
        test_loader=test_loader,
        eval_config=EVAL_CONFIG,
        device=train_info.get("device"),
        target_vars=TARGET_VARS,
        scalers=scaler,
        return_test_snapshot=True,
        return_test_arrays=True,
    )
    snapshot_data = eval_payload.pop("test_snapshot", None)
    test_arrays = eval_payload.pop("test_arrays", None)
    eval_results = eval_payload

    if print_flag:
        print("  Validation metrics:")
        for name, value in eval_results["validation"].items():
            print(f"    {name}: {value:.6f}")

        print("  Test metrics:")
        for name, value in eval_results["test"].items():
            print(f"    {name}: {value:.6f}")

    return eval_results, snapshot_data, test_arrays


def step5_visualize_results(
    train_history,
    eval_results,
    snapshot_data,
    test_arrays,
    model_name: str,
    print_flag: bool = True,
):
    """Generate and save visualization artifacts."""
    model_results_dir = Path(RESULTS_DIR) / model_name
    artifacts = run_visualization(
        train_history=train_history,
        eval_results=eval_results,
        results_dir=model_results_dir,
        vis_config=VIS_CONFIG,
        target_vars=TARGET_VARS,
        snapshot_data=snapshot_data,
        test_arrays=test_arrays,
    )

    if print_flag:
        print("  Saved artifacts:")
        for name, path in artifacts.items():
            print(f"    {name}: {path}")

    return artifacts


def main():
    args = parse_args()

    TRAINING_CONFIG["batch_size"] = args.batch_size
    TRAINING_CONFIG["num_workers"] = args.num_workers
    TRAINING_CONFIG["pin_memory"] = args.pin_memory

    print_flag = True
    sequences_path = Path(args.sequences_root) / args.sequence_name / "sequences.pt"
    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_name = f"{MODEL_ARCHITECTURE}_{args.sequence_name}_{run_timestamp}"
    try:
        print("STAGE 0 - ENVIRONMENT AND CONFIGURATION")
        if print_flag:
            print_config()

        print("\nSTAGE 1 - LOAD SAVED SEQUENCES")
        train_loader, val_loader, test_loader = step1_load_sequences(sequences_path, print_flag=print_flag)

        print("\nSTAGE 2 - BUILD MODEL")
        model = step2_build_model(train_loader, print_flag=print_flag)

        print("\nSTAGE 3 - TRAINING")
        TRAIN_MODEL = True
        train_history, train_info = step3_train_model(
            model,
            train_loader,
            val_loader,
            model_name=model_name,
            TRAIN_MODEL=TRAIN_MODEL,
        )

        print("\nSTAGE 4 - EVALUATION")
        eval_results, snapshot_data, test_arrays = step4_evaluate_model(
            model,
            val_loader,
            test_loader,
            train_info,
            print_flag=print_flag,
        )

        print("\nSTAGE 5 - VISUALIZATION")
        artifacts = step5_visualize_results(
            train_history,
            eval_results,
            snapshot_data,
            test_arrays,
            model_name=model_name,
            print_flag=print_flag,
        )
    except Exception:
        # No MLflow tracker to mark failure; re-raise exception
        raise


if __name__ == "__main__":
    main()
