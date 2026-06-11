import numpy as np
import torch

from config import (
    WIND_VARS,
    BOUNDARY_VARS,
    BATHY_VARS,
    TARGET_VARS,
    PREVIOUS_INPUT_STEPS,
    PREVIOUS_BOUNDARY_STEPS,
)


def _is_case_group(ds) -> bool:
    return isinstance(ds, dict) and {"wind", "boundary", "bathy", "wave"}.issubset(ds.keys())


def _create_samples_from_case(ds, previous_input_steps=None, previous_boundary_steps=None, num_samples=None):
    """Create (input, target) samples using temporal windows and zero-filled dry points."""
    previous_input_steps = PREVIOUS_INPUT_STEPS if previous_input_steps is None else previous_input_steps
    previous_boundary_steps = PREVIOUS_BOUNDARY_STEPS if previous_boundary_steps is None else previous_boundary_steps

    if not _is_case_group(ds):
        raise TypeError("create_samples expects a case dict with keys: wind, boundary, bathy, wave")

    wind_ds = ds["wind"]
    boundary_ds = ds["boundary"]
    bathy_ds = ds["bathy"]
    wave_ds = ds["wave"]

    n_time = min(
        wave_ds.sizes.get("time", 0),
        wind_ds.sizes.get("time", 0),
        boundary_ds.sizes.get("time", 0),
    )
    start_t = max(previous_input_steps, previous_boundary_steps) - 1
    start_t = max(start_t, 0)

    samples = []
    for t in range(start_t, n_time):
        channels = []

        # Wind history: [u10_t-k, v10_t-k, ...]
        for k in range(t - previous_input_steps + 1, t + 1):
            for var in WIND_VARS:
                channels.append(wind_ds[var].isel(time=k).values)

        # Boundary history: [swh_t-k, pp1d_t-k, mwd_t-k, ...]
        for k in range(t - previous_boundary_steps + 1, t + 1):
            for var in BOUNDARY_VARS:
                channels.append(boundary_ds[var].isel(time=k).values)

        # Static bathymetry (one channel per variable)
        for var in BATHY_VARS:
            da = bathy_ds[var]
            if "time" in da.dims:
                channels.append(da.isel(time=t).values)
            else:
                channels.append(da.values)

        targets = [wave_ds[var].isel(time=t).values for var in TARGET_VARS]
        time_value = str(wave_ds["time"].isel(time=t).values) if "time" in wave_ds.coords else str(t)

        x = np.stack(channels, axis=0).astype(np.float32)
        y = np.stack(targets, axis=0).astype(np.float32)

        samples.append((torch.from_numpy(x), torch.from_numpy(y), time_value))

        if num_samples is not None and len(samples) >= num_samples:
            break

    return samples


def create_samples(ds, previous_input_steps=None, previous_boundary_steps=None, num_samples=None):
    if _is_case_group(ds):
        return _create_samples_from_case(ds, previous_input_steps, previous_boundary_steps, num_samples)

    if isinstance(ds, dict):
        samples = []
        case_names = sorted(ds.keys())
        for case_name in case_names:
            remaining = None if num_samples is None else max(0, num_samples - len(samples))
            if remaining == 0:
                break
            case_samples = _create_samples_from_case(
                ds[case_name],
                previous_input_steps=previous_input_steps,
                previous_boundary_steps=previous_boundary_steps,
                num_samples=remaining,
            )
            samples.extend(case_samples)
        return samples

    raise TypeError("create_samples expects either a case dict or a dict of case dicts.")

import numpy as np
import torch

from config import (
    WIND_VARS,
    BOUNDARY_VARS,
    BATHY_VARS,
    TARGET_VARS,
    PREVIOUS_INPUT_STEPS,
    PREVIOUS_BOUNDARY_STEPS,
)


def resolve_sequence_counts(total_sequences: int | str, train_ratio: float, val_ratio: float, test_ratio: float):
    """Compute train/val/test sequence targets from split ratios or 'All'."""
    if isinstance(total_sequences, str):
        if total_sequences.strip().lower() == "all":
            return [None, None, None]
        try:
            total_sequences = int(total_sequences)
        except ValueError as exc:
            raise ValueError("sequence-count must be a non-negative integer or 'All'.") from exc

    if total_sequences < 0:
        raise ValueError("sequence-count must be non-negative.")

    ratio_sum = train_ratio + val_ratio + test_ratio
    if abs(ratio_sum - 1.0) > 1e-6:
        raise ValueError("Invalid split configuration: TRAIN_RATIO + VAL_RATIO + TEST_RATIO must equal 1.0.")

    train_n = int(total_sequences * train_ratio)
    val_n = int(total_sequences * val_ratio)
    test_n = total_sequences - train_n - val_n

    if test_n < 0:
        raise ValueError("Invalid split configuration: computed negative test sequence count.")

    return [train_n, val_n, test_n]



def _wave_time_size(case_ds: dict) -> int:
    wave_ds = case_ds.get("wave")
    if wave_ds is None or "time" not in wave_ds.sizes:
        return 0
    return int(wave_ds.sizes["time"])


def _map_global_time_index(global_idx: int, case_spans: list[tuple[str, int, int]]) -> tuple[str, int]:
    for case_name, start_idx, end_idx in case_spans:
        if start_idx <= global_idx < end_idx:
            return case_name, global_idx - start_idx
    raise IndexError(f"Global index {global_idx} out of span bounds.")


def _build_sequence_from_case_time(case_ds: dict, t: int):
    required_groups = {"wind", "boundary", "bathy", "wave"}
    if not required_groups.issubset(case_ds.keys()):
        return None

    wind_ds = case_ds["wind"]
    boundary_ds = case_ds["boundary"]
    bathy_ds = case_ds["bathy"]
    wave_ds = case_ds["wave"]

    n_time = min(
        wave_ds.sizes.get("time", 0),
        wind_ds.sizes.get("time", 0),
        boundary_ds.sizes.get("time", 0),
    )
    start_t = max(PREVIOUS_INPUT_STEPS, PREVIOUS_BOUNDARY_STEPS) - 1
    start_t = max(start_t, 0)

    if t < start_t or t >= n_time:
        return None

    channels = []

    try:
        for k in range(t - PREVIOUS_INPUT_STEPS + 1, t + 1):
            for var in WIND_VARS:
                channels.append(wind_ds[var].isel(time=k).values)

        for k in range(t - PREVIOUS_BOUNDARY_STEPS + 1, t + 1):
            for var in BOUNDARY_VARS:
                channels.append(boundary_ds[var].isel(time=k).values)

        for var in BATHY_VARS:
            da = bathy_ds[var]
            if "time" in da.dims:
                channels.append(da.isel(time=t).values)
            else:
                channels.append(da.values)

        targets = [wave_ds[var].isel(time=t).values for var in TARGET_VARS]

        x = np.stack(channels, axis=0).astype(np.float32)
        y = np.stack(targets, axis=0).astype(np.float32)

        if "time" in wave_ds.coords:
            time_value = str(wave_ds["time"].isel(time=t).values)
        else:
            time_value = str(t)

        return torch.from_numpy(x), torch.from_numpy(y), time_value
    except Exception:
        return None


def create_random_sequences(grouped_ds: dict, requested_n: int, split_name: str, rng: np.random.Generator):
    """Create random, unique, valid sequences across all case folders in a split."""
    if requested_n <= 0:
        return []

    case_names = sorted(grouped_ds.keys())
    case_spans = []
    cursor = 0

    for case_name in case_names:
        case_n = _wave_time_size(grouped_ds[case_name])
        if case_n <= 0:
            continue
        case_spans.append((case_name, cursor, cursor + case_n))
        cursor += case_n

    total_timesteps = cursor
    if total_timesteps == 0:
        print(f"  WARNING: No timesteps available for {split_name} random sequence creation.")
        return []

    sequences = []
    selected_indices = set()

    while len(sequences) < requested_n and len(selected_indices) < total_timesteps:
        global_idx = int(rng.integers(0, total_timesteps))
        if global_idx in selected_indices:
            continue

        selected_indices.add(global_idx)
        case_name, local_t = _map_global_time_index(global_idx, case_spans)
        sample = _build_sequence_from_case_time(grouped_ds[case_name], local_t)

        if sample is None:
            continue

        sequences.append(sample)

    if len(sequences) < requested_n:
        print(
            f"  WARNING: Requested {requested_n} random sequences for {split_name}, "
            f"but only {len(sequences)} valid complete sequences were found."
        )

    return sequences

import json
from pathlib import Path

import torch


def _unpack_sequence_item(sample):
    if len(sample) == 3:
        return sample[0], sample[1], sample[2]
    if len(sample) == 2:
        return sample[0], sample[1], None
    raise ValueError("Invalid sequence sample format; expected 2 or 3 items.")


def save_sequences(
    sequences_path: Path,
    sequence_name: str,
    split_strategy: str,
    seed: int,
    num_sequences: list[int | None],
    previous_input_steps: int,
    previous_boundary_steps: int,
    scaler_path: str,
    train_sequences: list,
    val_sequences: list,
    test_sequences: list,
):
    """Persist generated sequences and metadata to disk."""
    sequences_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "train_sequences": train_sequences,
            "val_sequences": val_sequences,
            "test_sequences": test_sequences,
            "meta": {
                "sequence_name": sequence_name,
                "split_strategy": split_strategy,
                "seed": seed,
                "train_sequences_limit": num_sequences[0],
                "val_sequences_limit": num_sequences[1],
                "test_sequences_limit": num_sequences[2],
                "previous_input_steps": previous_input_steps,
                "previous_boundary_steps": previous_boundary_steps,
                "scaler_path": scaler_path,
            },
        },
        sequences_path,
    )


def _sequence_basic_stats(sequences: list) -> dict:
    if not sequences:
        return {
            "count": 0,
            "input_shape": None,
            "target_shape": None,
            "input_min": None,
            "input_max": None,
            "target_min": None,
            "target_max": None,
        }

    x0, y0, _ = _unpack_sequence_item(sequences[0])
    x_min = float("inf")
    x_max = float("-inf")
    y_min = float("inf")
    y_max = float("-inf")

    for sample in sequences:
        x_tensor, y_tensor, _ = _unpack_sequence_item(sample)
        x_min = min(x_min, float(x_tensor.min().item()))
        x_max = max(x_max, float(x_tensor.max().item()))
        y_min = min(y_min, float(y_tensor.min().item()))
        y_max = max(y_max, float(y_tensor.max().item()))

    return {
        "count": len(sequences),
        "input_shape": list(x0.shape),
        "target_shape": list(y0.shape),
        "input_min": x_min,
        "input_max": x_max,
        "target_min": y_min,
        "target_max": y_max,
    }


def export_validation_artifacts(
    sequence_dir: Path,
    train_sequences: list,
    val_sequences: list,
    test_sequences: list,
    wind_vars: list[str],
    boundary_vars: list[str],
    bathy_vars: list[str],
    target_vars: list[str],
    previous_input_steps: int,
    previous_boundary_steps: int,
    max_figures_per_split: int = 2,
):
    """Export summary and quick-look figures for sequence validation."""
    sequence_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "train": _sequence_basic_stats(train_sequences),
        "validation": _sequence_basic_stats(val_sequences),
        "test": _sequence_basic_stats(test_sequences),
    }

    summary_path = sequence_dir / "sequence_validation_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:
        print(f"  WARNING: Could not export validation figures (matplotlib unavailable): {exc}")
        return

    def _build_input_labels() -> list[str]:
        labels = []

        for step_idx in range(previous_input_steps):
            rel = -(previous_input_steps - 1 - step_idx)
            for var_name in wind_vars:
                labels.append(f"{var_name} (t{rel:+d})")

        for step_idx in range(previous_boundary_steps):
            rel = -(previous_boundary_steps - 1 - step_idx)
            for var_name in boundary_vars:
                labels.append(f"{var_name} (t{rel:+d})")

        for var_name in bathy_vars:
            labels.append(f"{var_name} (static)")

        return labels

    input_labels = _build_input_labels()
    target_labels = [f"{var_name} (t+0)" for var_name in target_vars]

    def export_split_figures(split_name: str, sequences: list):
        if not sequences:
            return

        # Export a single figure per split using the first sequence sample.
        # Include all input and output channels for quick visual validation.
        if max_figures_per_split <= 0:
            return

        x, y, _ = _unpack_sequence_item(sequences[0])
        x_np = x.detach().cpu().numpy()
        y_np = y.detach().cpu().numpy()

        n_input = x_np.shape[0]
        n_target = y_np.shape[0]
        n_total = n_input + n_target
        n_cols = min(6, n_total)
        n_rows = (n_total + n_cols - 1) // n_cols

        fig, axes = plt.subplots(n_rows, n_cols, figsize=(3.2 * n_cols, 3.0 * n_rows))
        if hasattr(axes, "ravel"):
            axes = axes.ravel()
        else:
            axes = [axes]

        panel_idx = 0
        for ch in range(n_input):
            ax = axes[panel_idx]
            ax.imshow(x_np[ch], cmap="viridis")
            label = input_labels[ch] if ch < len(input_labels) else f"input ch{ch}"
            ax.set_title(label)
            ax.set_axis_off()
            panel_idx += 1

        for ch in range(n_target):
            ax = axes[panel_idx]
            ax.imshow(y_np[ch], cmap="viridis")
            label = target_labels[ch] if ch < len(target_labels) else f"target ch{ch}"
            ax.set_title(label)
            ax.set_axis_off()
            panel_idx += 1

        for ax in axes[panel_idx:]:
            ax.set_axis_off()

        fig.suptitle(f"{split_name} | sample 0 | all channels", fontsize=12)
        fig.tight_layout()
        fig.savefig(sequence_dir / f"sequence_preview_{split_name}.png", dpi=150)
        plt.close(fig)

    export_split_figures("train", train_sequences)
    export_split_figures("validation", val_sequences)
    export_split_figures("test", test_sequences)
