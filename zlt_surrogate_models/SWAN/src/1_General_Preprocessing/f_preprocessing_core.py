"""Core preprocessing helpers for deployable 1_preprocessing scripts."""

import contextlib
import io
import os

import numpy as np
import xarray as xr

from f_interpolation import spatial_bilinear_interpolation, temporal_interpolation_to_hourly
from f_utils import canonicalize_spatial_layout


def apply_preprocessing(
    ds: xr.Dataset,
    target_grid_size: int = 128,
    apply_temporal: bool = True,
    silent: bool = True,
) -> xr.Dataset:
    """Apply spatial interpolation and optional hourly temporal interpolation."""
    if silent:
        with contextlib.redirect_stdout(io.StringIO()):
            return apply_preprocessing(ds, target_grid_size, apply_temporal, silent=False)

    ds_interp = spatial_bilinear_interpolation(ds, target_grid_size)
    if apply_temporal:
        ds_interp = temporal_interpolation_to_hourly(ds_interp)
    return ds_interp


def aggregate_single_var_datasets(
    datasets_dict: dict[str, xr.Dataset],
    rename_map: dict[str, str],
) -> xr.Dataset:
    """Merge single-variable datasets into one dataset with normalized variable names."""
    aggregated = None
    for key, ds in datasets_dict.items():
        var_name = list(ds.data_vars)[0]
        ds_renamed = ds.rename({var_name: rename_map[key]})
        if aggregated is None:
            aggregated = ds_renamed
        else:
            aggregated = xr.merge([aggregated, ds_renamed], join="inner", compat="override")

    if aggregated is None:
        raise ValueError("No datasets provided for aggregation.")
    return aggregated


def add_direction_trig_components(ds: xr.Dataset) -> xr.Dataset:
    """Add <var>_sin and <var>_cos features from a detected direction variable."""
    direction_candidates = [
        "PDIR",
        "pdir",
        "dir",
        "DIR",
        "mwd",
        "MWD",
        "mean_wave_direction",
        "direction",
    ]
    direction_var = next((name for name in direction_candidates if name in ds.data_vars), None)
    if direction_var is None:
        return ds

    angle_rad = np.deg2rad(ds[direction_var])
    sin_name = f"{direction_var}_sin"
    cos_name = f"{direction_var}_cos"
    ds[sin_name] = np.sin(angle_rad)
    ds[cos_name] = np.cos(angle_rad)
    ds[sin_name].attrs = {
        "long_name": f"sine of {direction_var}",
        "source_direction_variable": direction_var,
        "units": "1",
    }
    ds[cos_name].attrs = {
        "long_name": f"cosine of {direction_var}",
        "source_direction_variable": direction_var,
        "units": "1",
    }
    return ds


def save_clean_netcdf(ds: xr.Dataset, output_path: str) -> None:
    """Save dataset to NetCDF after normalizing coords, dims, and malformed attrs."""
    if os.path.exists(output_path):
        os.remove(output_path)

    ds_out = canonicalize_spatial_layout(ds.copy())

    if "expver" in ds_out.variables:
        ds_out = ds_out.drop_vars("expver")

    for var in ds_out.data_vars:
        da = ds_out[var]
        dims = list(da.dims)
        if "lat" in dims and "lon" in dims:
            non_spatial_dims = [dim for dim in dims if dim not in {"lat", "lon"}]
            if "time" in non_spatial_dims:
                non_spatial_dims = ["time"] + [dim for dim in non_spatial_dims if dim != "time"]
            target_order = non_spatial_dims + ["lat", "lon"]
            ds_out[var] = da.transpose(*target_order)

    if "lat" in ds_out.coords:
        ds_out = ds_out.sortby("lat")
    if "lon" in ds_out.coords:
        ds_out = ds_out.sortby("lon")

    for var in ds_out.data_vars:
        if "encoding" in ds_out[var].attrs:
            del ds_out[var].attrs["encoding"]

    if "time" in ds_out.coords and "calendar" in ds_out["time"].attrs:
        calendar_attr = ds_out["time"].attrs["calendar"]
        if isinstance(calendar_attr, np.ndarray) or not isinstance(calendar_attr, str) or not calendar_attr.strip():
            del ds_out["time"].attrs["calendar"]

    # Use a single-threaded compute path to avoid thread-spawn failures on shared HPC nodes.
    delayed = ds_out.to_netcdf(
        output_path,
        engine="netcdf4",
        format="NETCDF4",
        compute=False,
    )
    delayed.compute(scheduler="single-threaded")