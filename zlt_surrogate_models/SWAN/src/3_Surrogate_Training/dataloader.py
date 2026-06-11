import numpy as np
import torch
from torch.utils.data import Dataset

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


class TensorDataset(Dataset):
    """Simple tensor sample wrapper compatible with multiprocessing DataLoader on Windows."""

    def __init__(self, samples):
        self.samples = samples

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        return self.samples[idx]

def create_dataloaders(train_ds, val_ds, test_ds, batch_size, num_workers, pin_memory, save_scalers=False, previous_input_steps=None, previous_boundary_steps=None, num_samples=None):
    """Create PyTorch DataLoaders with temporal windowing."""
    from torch.utils.data import DataLoader

    if num_samples is None:
        num_samples = (None, None, None)

    train_sa = TensorDataset(create_samples(train_ds, previous_input_steps, previous_boundary_steps, num_samples=num_samples[0]))
    val_sa = TensorDataset(create_samples(val_ds, previous_input_steps, previous_boundary_steps, num_samples=num_samples[1]))
    test_sa = TensorDataset(create_samples(test_ds, previous_input_steps, previous_boundary_steps, num_samples=num_samples[2]))

    train_loader = DataLoader(train_sa, batch_size=batch_size, shuffle=True, num_workers=num_workers, pin_memory=pin_memory, drop_last=True)
    val_loader = DataLoader(val_sa, batch_size=batch_size, shuffle=False, num_workers=num_workers, pin_memory=pin_memory, drop_last=False)
    test_loader = DataLoader(test_sa, batch_size=batch_size, shuffle=False, num_workers=num_workers, pin_memory=pin_memory, drop_last=False)

    return train_loader, val_loader, test_loader