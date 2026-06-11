"""
SWAN Surrogate - Preprocessing Pipeline

Purpose:
1. Load raw preprocessed NetCDF case data
2. Replace non-finite values
3. Temporal train/val/test split
4. Fit/apply scaler
5. Build and save tensor sequences for fast training
"""

import argparse
import numpy as np
import warnings
import sys
from pathlib import Path

warnings.filterwarnings("ignore")

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from config import (
    print_config,
    PROJECT_ROOT,
    DATA_PATH,
    SCALER_TYPE,
    SCALER_PATH,
    TRAIN_RATIO,
    VAL_RATIO,
    TEST_RATIO,
    WIND_VARS,
    BOUNDARY_VARS,
    BATHY_VARS,
    TARGET_VARS,
    PREVIOUS_INPUT_STEPS,
    PREVIOUS_BOUNDARY_STEPS,
)

from f_data_processing import (
    load_data_swan, print_load_data, FILE_PATHS,
    split_dataset_temporal,
    create_scaler, scale_data, import_scale, print_summary,
    preprocess_non_finite, fill_boundary_sequences_idw
)
from f_sequence_core import (
    create_samples,
    create_random_sequences, resolve_sequence_counts,
    save_sequences, export_validation_artifacts
)


def parse_args():
    parser = argparse.ArgumentParser(description="Preprocess SWAN data and save sequence datasets")
    parser.add_argument(
        "--sequence-count",
        type=str,
        default="500",
        help="Total sequences to build, or 'All' to use all available train/val/test sequences.",
    )
    parser.add_argument(
        "--sequence-name",
        type=str,
        default=None,
        help="Sequence dataset name (for example: 500, 8000, 20000). Defaults to sequence-count value.",
    )
    parser.add_argument("--train-scaler", action="store_true", help="Fit a new scaler and save it")
    parser.add_argument(
        "--sequences-root",
        type=str,
        default=str(PROJECT_ROOT / "data" / "sequences"),
        help="Root directory for saved sequence sets",
    )
    parser.add_argument(
        "--split-strategy",
        type=str,
        choices=["temporal", "random"],
        default="temporal",
        help="Sequence generation strategy: temporal (by temporal splits) or random (global random from full sequence pool)",
    )
    parser.add_argument(
        "--validation-figures",
        type=int,
        default=2,
        help="Number of sample figures to export per split after saving sequences.",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility (only used with --split-strategy random)")
    return parser.parse_args()


def step1_load_data(folders_path: dict, print_flag: bool = True) -> tuple[dict, dict]:
    """Load grouped xarray datasets from specified folder paths."""
    grouped_dataset, data_summary = load_data_swan(folders_path=folders_path)

    if print_flag:
        print_load_data(grouped_dataset=grouped_dataset, data_summary=data_summary)

    return grouped_dataset, data_summary


def step2_preprocess_data(grouped_dataset: dict, fill_value: float = 0.0):
    """Replace non-finite values in all grouped datasets."""
    return preprocess_non_finite(grouped_dataset, fill_value=fill_value)


def step3_split_data(grouped_dataset: dict, print_flag: bool = True):
    """Split grouped datasets into train/validation/test partitions."""
    return split_dataset_temporal(
        xr_dataset=grouped_dataset,
        train_ratio=TRAIN_RATIO,
        val_ratio=VAL_RATIO,
        test_ratio=TEST_RATIO,
        print_flag=print_flag
    )


def step4_scale_data(train_dataset: dict, val_dataset: dict, test_dataset: dict, train_scaler: bool, print_flag: bool = True):
    """Fit/import scaler and apply scaling to train/val/test datasets."""
    if train_scaler:
        scaler = create_scaler(SCALER_TYPE, train_dataset, SCALER_PATH)
        print(f"Scaler CREATED and saved to {SCALER_PATH}")
    else:
        scaler = import_scale(SCALER_PATH)
        print(f"Scaler IMPORTED from {SCALER_PATH}")

    train_sc = scale_data(train_dataset, scaler)
    val_sc = scale_data(val_dataset, scaler)
    test_sc = scale_data(test_dataset, scaler)

    if print_flag:
        print_summary(train_sc, val_sc, test_sc)

    return train_sc, val_sc, test_sc, scaler


def step5_generate_sequences(
    num_sequences: list[int | None],
    train_sc: dict,
    val_sc: dict,
    test_sc: dict,
    split_strategy: str,
    seed: int,
):
    """Generate train/val/test sequences with temporal or random selection per split."""

    rng = np.random.default_rng(seed)
    use_all_sequences = all(target is None for target in num_sequences)

    def build_split_sequences(split_ds: dict, requested_n: int | None, split_name: str):
        if use_all_sequences or split_strategy == "temporal":
            return create_samples(
                split_ds,
                previous_input_steps=PREVIOUS_INPUT_STEPS,
                previous_boundary_steps=PREVIOUS_BOUNDARY_STEPS,
                num_samples=requested_n,
            )

        return create_random_sequences(split_ds, requested_n or 0, split_name, rng)

    train_sequences = build_split_sequences(train_sc, num_sequences[0], "train")
    val_sequences = build_split_sequences(val_sc, num_sequences[1], "validation")
    test_sequences = build_split_sequences(test_sc, num_sequences[2], "test")

    return train_sequences, val_sequences, test_sequences

########################################################################

def main():
    args = parse_args()
    print_flag = True

    # Use sequence_name if provided, otherwise default to sequence_count
    sequence_name = str(args.sequence_name) if args.sequence_name else str(args.sequence_count)
    sequences_path = Path(args.sequences_root) / sequence_name / "sequences.pt"

    print("STAGE 0 - ENVIRONMENT AND CONFIGURATION")
    if print_flag: 
        print_config()

    print("\nSTAGE 1 - DATA LOADING")
    from f_data_processing import build_all_file_paths, GRID_SIZE as _GRID_SIZE
    file_paths = build_all_file_paths(DATA_PATH, _GRID_SIZE)
    grouped_dataset, data_summary = step1_load_data(folders_path=file_paths, print_flag=print_flag)

    print("\nSTAGE 2 - PREPROCESSING")
    grouped_dataset, n_replaced = step2_preprocess_data(grouped_dataset, fill_value=0.0)
    print(f"  Replaced {n_replaced} non-finite values with 0.0.")

    print("\nSTAGE 3 - DATASET SPLIT")
    train_ds, val_ds, test_ds = step3_split_data(grouped_dataset, print_flag=print_flag)

    print("\nSTAGE 4 - DATA SCALING")
    train_sc, val_sc, test_sc, scaler = step4_scale_data(
        train_dataset=train_ds,
        val_dataset=val_ds,
        test_dataset=test_ds,
        train_scaler=args.train_scaler,
        print_flag=print_flag,
    )

    num_sequences = resolve_sequence_counts(
        args.sequence_count,
        TRAIN_RATIO,
        VAL_RATIO,
        TEST_RATIO,
    )

    print("\nSTAGE 5 - SEQUENCE DATASET GENERATION")
    train_sequences, val_sequences, test_sequences = step5_generate_sequences(
        num_sequences=num_sequences,
        train_sc=train_sc,
        val_sc=val_sc,
        test_sc=test_sc,
        split_strategy=args.split_strategy,
        seed=args.seed,
    )

    print("\nSTAGE 6 - BOUNDARY IDW INTERIOR FILL")
    boundary_channel_start = PREVIOUS_INPUT_STEPS * len(WIND_VARS)
    boundary_channel_count = PREVIOUS_BOUNDARY_STEPS * len(BOUNDARY_VARS)
    train_sequences, val_sequences, test_sequences = fill_boundary_sequences_idw(
        train_sequences,
        val_sequences,
        test_sequences,
        boundary_channel_start=boundary_channel_start,
        boundary_channel_count=boundary_channel_count,
        power=2.0,
    )

    print("\nSTAGE 7 - SAVE SEQUENCES")
    save_sequences(
        sequences_path=sequences_path,
        sequence_name=sequence_name,
        split_strategy=args.split_strategy,
        seed=args.seed,
        num_sequences=num_sequences,
        previous_input_steps=PREVIOUS_INPUT_STEPS,
        previous_boundary_steps=PREVIOUS_BOUNDARY_STEPS,
        scaler_path=str(SCALER_PATH),
        train_sequences=train_sequences,
        val_sequences=val_sequences,
        test_sequences=test_sequences,
    )

    print("\nSTAGE 8 - EXPORT VALIDATION ARTIFACTS")
    export_validation_artifacts(
        sequence_dir=sequences_path.parent,
        train_sequences=train_sequences,
        val_sequences=val_sequences,
        test_sequences=test_sequences,
        wind_vars=WIND_VARS,
        boundary_vars=BOUNDARY_VARS,
        bathy_vars=BATHY_VARS,
        target_vars=TARGET_VARS,
        previous_input_steps=PREVIOUS_INPUT_STEPS,
        previous_boundary_steps=PREVIOUS_BOUNDARY_STEPS,
        max_figures_per_split=args.validation_figures,
    )

    print(f"  Saved sequences: {sequences_path}")
    print(
        "  Saved sequences | "
        f"Train: {len(train_sequences)} | Val: {len(val_sequences)} | Test: {len(test_sequences)}"
    )


if __name__ == "__main__":
    main()
