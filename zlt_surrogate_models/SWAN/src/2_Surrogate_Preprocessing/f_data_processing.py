from pathlib import Path
import xarray as xr
from config import PROJECT_ROOT, DATA_PATH, GRID_SIZE

# =============================================================================
# PATH RESOLUTION
# =============================================================================
def resolve_data_path(data_path: Path | str) -> Path:
    """Resolve absolute path safely."""
    path = Path(data_path)

    candidates = [path] if path.is_absolute() else [
        PROJECT_ROOT / path,
        Path.cwd() / path,
        path
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()

    return candidates[0].resolve()


# =============================================================================
# BUILD FILE PATHS FOR ONE CASE
# =============================================================================
def build_file_paths(
    case_folder: Path,
    grid_size: list[int] = GRID_SIZE
) -> dict[str, Path]:

    return {
        'inputs_wind':
            case_folder / f'wind_inputs_preprocessed_{grid_size[0]}x{grid_size[1]}.nc',

        'inputs_bathy':
            case_folder / f'bathymetry_preprocessed_{grid_size[0]}x{grid_size[1]}.nc',

        'outputs_wave':
            case_folder / f'wave_output_preprocessed_{grid_size[0]}x{grid_size[1]}.nc',

        'boundary_forcing':
            case_folder / f'boundary_preprocessed_{grid_size[0]}x{grid_size[1]}.nc',
    }


# =============================================================================
# GET ALL CASE FOLDERS
# =============================================================================
def get_case_folders(data_path: Path | str = DATA_PATH) -> list[Path]:

    base = resolve_data_path(data_path)

    folders = [
        p for p in base.iterdir()
        if p.is_dir() and p.name not in ["scalers", "sequences", "logs", "__pycache__"]
    ]

    return sorted(folders)


# =============================================================================
# BUILD FILE PATHS FOR ALL CASES
# =============================================================================
def build_all_file_paths(
    data_path: Path | str = DATA_PATH,
    grid_size: list[int] = GRID_SIZE
) -> dict[str, dict[str, Path]]:

    case_paths = {}

    for folder in get_case_folders(data_path):
        case_paths[folder.name] = build_file_paths(folder, grid_size)

    return case_paths


# =============================================================================
# GENERATE PATHS
# =============================================================================
# Only build FILE_PATHS when the training data directory actually exists.
# In user_case inference, DATA_PATH is not present and FILE_PATHS is not needed.
FILE_PATHS: dict = build_all_file_paths(DATA_PATH, GRID_SIZE) if resolve_data_path(DATA_PATH).exists() else {}


def load_data_swan(folders_path: str | dict | None = None, data_path: str | dict | None = None):
    """
    Load all preprocessed NetCDF datasets from multiple case folders.
    
    Returns
    -------
    datasets : dict
        datasets[case_name][variable_type] -> xarray.Dataset
        
    data_summary : dict
        Basic info about each dataset
    """
    source = folders_path if folders_path is not None else data_path
    if source is None:
        raise ValueError("Provide either 'folders_path' or 'data_path'.")

    datasets = {}
    data_summary = {}

    if isinstance(source, dict):
        # source format: {case_name: {'inputs_wind': ..., 'inputs_bathy': ..., ...}}
        for case_name, case_files in source.items():
            files = {
                "wind": Path(case_files["inputs_wind"]),
                "bathy": Path(case_files["inputs_bathy"]),
                "wave": Path(case_files["outputs_wave"]),
                "boundary": Path(case_files["boundary_forcing"]),
            }

            datasets[case_name] = {
                name: xr.open_dataset(path)
                for name, path in files.items()
            }

            ds_wave = datasets[case_name]["wave"]
            data_summary[case_name] = {
                "n_time": ds_wave.sizes.get("time", None),
                "grid": (
                    ds_wave.sizes.get("y", None),
                    ds_wave.sizes.get("x", None)
                ),
                "variables": list(ds_wave.data_vars),
            }
        return datasets, data_summary

    data_path_obj = Path(source)

    # iterate over case folders
    for case_folder in sorted([p for p in data_path_obj.iterdir() if p.is_dir()]):

        case_name = case_folder.name

        files = {
            "wind": list(case_folder.glob("wind_inputs_preprocessed_*.nc"))[0],
            "bathy": list(case_folder.glob("bathymetry_preprocessed_*.nc"))[0],
            "wave": list(case_folder.glob("wave_output_preprocessed_*.nc"))[0],
            "boundary": list(case_folder.glob("boundary_preprocessed_*.nc"))[0],
        }

        # load datasets (lazy loading)
        datasets[case_name] = {
            name: xr.open_dataset(path)
            for name, path in files.items()
        }

        # summary info
        ds_wave = datasets[case_name]["wave"]

        data_summary[case_name] = {
            "n_time": ds_wave.sizes.get("time", None),
            "grid": (
                ds_wave.sizes.get("y", None),
                ds_wave.sizes.get("x", None)
            ),
            "variables": list(ds_wave.data_vars),
        }

    return datasets, data_summary


def print_load_data(grouped_dataset=None, data_summary=None):
    """Print summary of loaded data."""
    print("\nData Summary:")
    if grouped_dataset is not None:
        print(f"  - Total samples: {len(grouped_dataset)}")
    if data_summary is not None:
        for key, value in data_summary.items():
            print(f"  - {key}: {value}")


if __name__ == "__main__":
    grouped_dataset, data_summary = load_data_swan(folders_path=FILE_PATHS)
    print_load_data(grouped_dataset=grouped_dataset, data_summary=data_summary)
import numpy as np
import torch


def preprocess_non_finite(grouped_dataset, fill_value=0.0):
    """Replace non-finite values recursively in grouped xarray datasets.
    Deal with dry-points and other invalid values by forcing to fill_value."""

    def _fill_non_finite(container):
        if isinstance(container, dict):
            out = {}
            total_replaced = 0
            for key, value in container.items():
                out_value, replaced = _fill_non_finite(value)
                out[key] = out_value
                total_replaced += replaced
            return out, total_replaced

        if hasattr(container, "data_vars"):
            ds = container.copy(deep=False)
            replaced_total = 0

            for var_name in ds.data_vars:
                data = ds[var_name].values
                invalid = ~np.isfinite(data)
                replaced = int(invalid.sum())

                if replaced > 0:
                    filled = np.where(invalid, fill_value, data)
                    ds[var_name] = (ds[var_name].dims, filled)
                    replaced_total += replaced

            return ds, replaced_total

        raise TypeError("Expected dict and/or xarray.Dataset objects.")

    return _fill_non_finite(grouped_dataset)



def _prepare_idw_geometry(height: int, width: int, power: float):
    """Precompute boundary/interior geometry and normalized IDW weights."""
    if height < 3 or width < 3:
        return None

    top = [(0, j) for j in range(width)]
    bottom = [(height - 1, j) for j in range(width)]
    left = [(i, 0) for i in range(1, height - 1)]
    right = [(i, width - 1) for i in range(1, height - 1)]

    boundary_coords = np.array(top + bottom + left + right, dtype=np.int32)

    interior_rows, interior_cols = np.meshgrid(
        np.arange(1, height - 1, dtype=np.int32),
        np.arange(1, width - 1, dtype=np.int32),
        indexing="ij",
    )
    interior_coords = np.stack([interior_rows.ravel(), interior_cols.ravel()], axis=1)

    dy = interior_coords[:, 0:1] - boundary_coords[None, :, 0]
    dx = interior_coords[:, 1:2] - boundary_coords[None, :, 1]
    dist = np.sqrt(dx.astype(np.float32) ** 2 + dy.astype(np.float32) ** 2)

    weights = 1.0 / np.power(np.maximum(dist, 1e-12), power)
    weights_sum = np.sum(weights, axis=1, keepdims=True)
    weights = weights / np.maximum(weights_sum, 1e-12)

    return {
        "boundary_rows": boundary_coords[:, 0],
        "boundary_cols": boundary_coords[:, 1],
        "interior_rows": interior_coords[:, 0],
        "interior_cols": interior_coords[:, 1],
        "weights": weights.astype(np.float32),
    }


def apply_idw_fill_to_boundary_sequences(
    sequences: list,
    boundary_channel_start: int,
    boundary_channel_count: int,
    power: float = 2.0,
):
    """Fill interior values of boundary channels using IDW from edge cells."""
    if not sequences or boundary_channel_count <= 0:
        return sequences

    first_sample = sequences[0]
    if len(first_sample) >= 2:
        sample_x = first_sample[0]
    else:
        return sequences

    if sample_x.ndim != 3:
        return sequences

    _, height, width = sample_x.shape
    geometry = _prepare_idw_geometry(height, width, power)
    if geometry is None:
        return sequences

    br = geometry["boundary_rows"]
    bc = geometry["boundary_cols"]
    ir = geometry["interior_rows"]
    ic = geometry["interior_cols"]
    weights = geometry["weights"]

    for idx, sample in enumerate(sequences):
        if len(sample) == 3:
            x_tensor, y_tensor, time_label = sample
        elif len(sample) == 2:
            x_tensor, y_tensor = sample
            time_label = None
        else:
            continue

        if not isinstance(x_tensor, torch.Tensor):
            continue
        if x_tensor.device.type != "cpu":
            x_tensor = x_tensor.cpu()

        x_np = x_tensor.numpy()
        ch_start = max(0, boundary_channel_start)
        ch_end = min(x_np.shape[0], boundary_channel_start + boundary_channel_count)

        for ch in range(ch_start, ch_end):
            boundary_values = x_np[ch, br, bc].astype(np.float32, copy=False)
            interior_values = weights @ boundary_values
            x_np[ch, ir, ic] = interior_values

        if time_label is None:
            sequences[idx] = (x_tensor, y_tensor)
        else:
            sequences[idx] = (x_tensor, y_tensor, time_label)

    return sequences


def fill_boundary_sequences_idw(
    train_sequences: list,
    val_sequences: list,
    test_sequences: list,
    boundary_channel_start: int,
    boundary_channel_count: int,
    power: float = 2.0,
):
    """Apply IDW interior fill to boundary channels for all train/val/test splits."""
    train_sequences = apply_idw_fill_to_boundary_sequences(
        train_sequences,
        boundary_channel_start=boundary_channel_start,
        boundary_channel_count=boundary_channel_count,
        power=power,
    )
    val_sequences = apply_idw_fill_to_boundary_sequences(
        val_sequences,
        boundary_channel_start=boundary_channel_start,
        boundary_channel_count=boundary_channel_count,
        power=power,
    )
    test_sequences = apply_idw_fill_to_boundary_sequences(
        test_sequences,
        boundary_channel_start=boundary_channel_start,
        boundary_channel_count=boundary_channel_count,
        power=power,
    )
    return train_sequences, val_sequences, test_sequences

from config import TRAIN_RATIO, VAL_RATIO, TEST_RATIO
import xarray as xr
from typing import Tuple


def _case_time_size(case_ds) -> int:
    if not isinstance(case_ds, dict):
        raise TypeError("Each case entry must be a dict of xarray.Datasets.")

    time_sizes = [
        ds.sizes.get("time", 0)
        for ds in case_ds.values()
        if hasattr(ds, "sizes") and ds.sizes.get("time", 0) > 0
    ]
    if not time_sizes:
        return 0
    return min(time_sizes)


def _slice_case_dataset(case_ds: dict, start: int, end: int) -> dict:
    if start >= end:
        start = end

    sliced_case = {}
    for group_name, ds in case_ds.items():
        if not hasattr(ds, "dims"):
            raise TypeError("Each group must be an xarray.Dataset.")
        if "time" in ds.dims:
            sliced_case[group_name] = ds.isel(time=slice(start, end))
        else:
            sliced_case[group_name] = ds
    return sliced_case


def _split_case_by_global_marks(case_ds: dict, case_start: int, train_mark: int, val_mark: int) -> tuple[dict, dict, dict]:
    case_n = _case_time_size(case_ds)

    train_end = max(0, min(case_n, train_mark - case_start))
    val_start = train_end
    val_end = max(0, min(case_n, val_mark - case_start))
    test_start = val_end

    train_ds = _slice_case_dataset(case_ds, 0, train_end)
    val_ds = _slice_case_dataset(case_ds, val_start, val_end)
    test_ds = _slice_case_dataset(case_ds, test_start, case_n)

    return train_ds, val_ds, test_ds

def split_dataset_temporal(
    xr_dataset: dict,
    train_ratio: float = TRAIN_RATIO,
    val_ratio: float = VAL_RATIO,
    test_ratio: float = TEST_RATIO,
    print_flag: bool = True,
) -> Tuple[dict, dict, dict]:
    """
    Split grouped case datasets temporally without merging folders.
    
    Args:
        xr_dataset: Dict of case_name -> dict of xarray.Datasets
        train_ratio: Fraction for training
        val_ratio: Fraction for validation
        test_ratio: Fraction for testing
        print_flag: Print a split summary when True
        
    Returns:
        Tuple of nested dicts: (train_dataset, val_dataset, test_dataset)
    """
    if not isinstance(xr_dataset, dict):
        raise TypeError("split_dataset_temporal expects a dict of case folders.")

    # Verify ratios sum to 1
    if abs(train_ratio + val_ratio + test_ratio - 1.0) > 1e-6:
        raise ValueError("Split ratios must sum to 1.0")

    case_names = sorted(xr_dataset.keys())
    if not case_names:
        raise ValueError("xr_dataset must contain at least one case folder.")

    case_sizes = {case_name: _case_time_size(xr_dataset[case_name]) for case_name in case_names}
    total_time = sum(case_sizes.values())
    if total_time <= 0:
        raise ValueError("No time steps found across the provided case folders.")

    train_mark = int(total_time * train_ratio)
    val_mark = int(total_time * (train_ratio + val_ratio))

    train_ds = {}
    val_ds = {}
    test_ds = {}

    case_start = 0
    for case_name in case_names:
        case_ds = xr_dataset[case_name]
        train_case, val_case, test_case = _split_case_by_global_marks(
            case_ds=case_ds,
            case_start=case_start,
            train_mark=train_mark,
            val_mark=val_mark,
        )
        train_ds[case_name] = train_case
        val_ds[case_name] = val_case
        test_ds[case_name] = test_case
        case_start += case_sizes[case_name]

    if print_flag:
        train_total = sum(_case_time_size(case_ds) for case_ds in train_ds.values())
        val_total = sum(_case_time_size(case_ds) for case_ds in val_ds.values())
        test_total = sum(_case_time_size(case_ds) for case_ds in test_ds.values())

        print("\n" + "=" * 80)
        print("DATASET SPLITTING (TEMPORAL ACROSS FOLDERS)")
        print("=" * 80)
        print(f"Total timesteps across folders: {total_time}")
        print(f"Train mark: {train_mark} | Val mark: {val_mark} | Test mark: {total_time}")
        print(f"Train total: {train_total} ({train_total / total_time * 100:.1f}%)")
        print(f"Validation total: {val_total} ({val_total / total_time * 100:.1f}%)")
        print(f"Test total: {test_total} ({test_total / total_time * 100:.1f}%)")
        print("\nPer-folder allocation:")
        print("Split | Folder | Timesteps")
        print("-" * 40)
        for case_name in case_names:
            print(f"Train | {case_name} | {_case_time_size(train_ds[case_name])}")
            print(f"Val   | {case_name} | {_case_time_size(val_ds[case_name])}")
            print(f"Test  | {case_name} | {_case_time_size(test_ds[case_name])}")
        print("=" * 80)

    return train_ds, val_ds, test_ds

from sklearn.preprocessing import StandardScaler, MinMaxScaler
import joblib
import numpy as np
import xarray as xr

SINGLE_DATASET_KEY = "__single__"


def _to_group(container):
    """Flatten input into dict[str, xr.Dataset] and keep original shape info."""
    if isinstance(container, xr.Dataset):
        return {SINGLE_DATASET_KEY: container}, True

    if isinstance(container, dict):
        group = {}
        for name, value in container.items():
            if isinstance(value, xr.Dataset):
                group[str(name)] = value
            elif isinstance(value, dict):
                nested_group, _ = _to_group(value)
                for nested_name, nested_ds in nested_group.items():
                    group[f"{name}/{nested_name}"] = nested_ds
            else:
                raise TypeError("Grouped dataset must contain xarray.Dataset values or nested dicts.")

        if not group:
            raise TypeError("Grouped dataset must contain xarray.Dataset values.")
        return group, False

    raise TypeError("Dataset must be an xarray.Dataset or dict of xarray.Dataset objects.")


def _from_group(group, was_single):
    if was_single:
        return group[SINGLE_DATASET_KEY]
    return group


def _get_variable(group, var_name):
    arrays = []
    for ds in group.values():
        if var_name in ds.data_vars:
            data = ds[var_name].values.reshape(-1).astype(np.float64, copy=False)
            finite = np.isfinite(data)
            if finite.any():
                arrays.append(data[finite])

    if not arrays:
        return None

    return np.concatenate(arrays)


def _transform_preserve_nan(values, scaler):
    flat = values.reshape(-1).astype(np.float64, copy=True)
    mask = np.isfinite(flat)
    if mask.any():
        flat[mask] = scaler.transform(flat[mask].reshape(-1, 1)).reshape(-1)
    return flat.reshape(values.shape)


def _scale_single_dataset(ds, scalers):
    scaled_ds = ds.copy()
    for var_name, scaler in scalers.items():
        if var_name in ds.data_vars:
            scaled_data = _transform_preserve_nan(ds[var_name].values, scaler)
            scaled_ds[var_name] = (ds[var_name].dims, scaled_data)
    return scaled_ds

def create_scaler(SCALER_TYPE, train_ds, SCALER_PATH):
    """Create and save scalers based on training dataset statistics."""

    train_group, _ = _to_group(train_ds)

    scalers = {}
    for var_name, scaler_type in SCALER_TYPE.items():
        var_data = _get_variable(train_group, var_name)
        if var_data is None:
            raise ValueError(f"Variable '{var_name}' specified in SCALER_TYPE not found in training dataset.")
        data = var_data.reshape(-1, 1)

        if scaler_type == 'standard':
            scaler = StandardScaler()
        elif scaler_type == 'minmax':
            scaler = MinMaxScaler()
        else:
            raise ValueError(f"Unsupported scaler type '{scaler_type}' for variable '{var_name}'.")

        scalers[var_name] = scaler.fit(data)

    # Save scalers to disk
    joblib.dump(scalers, SCALER_PATH)
    return scalers

def scale_data(ds, scalers):
    """Apply scalers to the dataset."""
    if isinstance(ds, xr.Dataset):
        return _scale_single_dataset(ds, scalers)

    if isinstance(ds, dict):
        scaled = {}
        for key, value in ds.items():
            if isinstance(value, xr.Dataset):
                scaled[key] = _scale_single_dataset(value, scalers)
            elif isinstance(value, dict):
                scaled[key] = scale_data(value, scalers)
            else:
                raise TypeError("Dataset groups must contain xarray.Dataset values or nested dicts.")
        return scaled

    raise TypeError("Dataset must be an xarray.Dataset or dict of xarray.Dataset objects.")

def import_scale(SCALER_PATH):
    """Load scalers from disk."""
    return joblib.load(SCALER_PATH)

def print_summary(train_ds, val_ds, test_ds):
    from prettytable import PrettyTable

    """Print summary statistics of the scaled datasets."""
    print("\nScaled dataset summary:")

    for ds_name, ds in zip(
        ["Train", "Validation", "Test"], 
        [train_ds, val_ds, test_ds]
    ):
        group, _ = _to_group(ds)

        table = PrettyTable()
        table.field_names = [
            "Variable", "Mean", "Std", "Min", "Max", "Finite"
        ]
        table.float_format = ".4"

        variable_names = sorted(
            {
                var_name
                for sub_ds in group.values()
                for var_name in sub_ds.data_vars
            }
        )

        for var in variable_names:
            pieces = []
            total_size = 0

            for sub_ds in group.values():
                if var not in sub_ds.data_vars:
                    continue
                data = sub_ds[var].values.reshape(-1).astype(np.float64, copy=False)
                total_size += data.size
                finite = np.isfinite(data)
                if finite.any():
                    pieces.append(data[finite])

            if not pieces:
                table.add_row([var, "NaN", "NaN", "NaN", "NaN", f"0/{total_size}"])
                continue

            valid = np.concatenate(pieces)
            table.add_row([
                var,
                valid.mean(),
                valid.std(),
                valid.min(),
                valid.max(),
                f"{valid.size}/{total_size}"
            ])

        print(f"\n{ds_name} set:")
        print(table)