"""
Utility functions for common data operations and analysis.

Functions for dataset manipulation, value extraction, distribution analysis,
and interpolation comparison visualizations.
"""

import os
import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
from netCDF4 import num2date
from typing import Optional, Dict, Tuple
from f_coordinates import get_lat_lon_coords, get_time_info


def standardize_coords(ds: xr.Dataset) -> xr.Dataset:
    """
    Standardize coordinate names to 'lat', 'lon', 'time' for universal compatibility.
    
    Parameters:
    -----------
    ds : xarray.Dataset
        Input dataset
    
    Returns:
    --------
    xarray.Dataset
        Dataset with standardized coordinate names
    """
    if ds is None:
        return None
    
    rename_dict = {}
    for coord in ds.coords:
        coord_lower = str(coord).lower()
        # Rename any lat-like coordinate to 'lat'
        if 'lat' in coord_lower and coord != 'lat':
            rename_dict[coord] = 'lat'
        # Rename any lon-like coordinate to 'lon'
        elif 'lon' in coord_lower and coord != 'lon':
            rename_dict[coord] = 'lon'
        # Standardize time coordinates
        elif coord in ['valid_time', 'time_counter'] and 'time' not in ds.coords:
            rename_dict[coord] = 'time'
    
    if rename_dict:
        ds = ds.rename(rename_dict)
    
    return ds


def canonicalize_spatial_layout(ds: xr.Dataset) -> xr.Dataset:
    """
    Enforce canonical spatial layout for plotting/interpolation consistency.

    - Coordinate names standardized to lat/lon/time when possible.
    - Spatial coordinates sorted ascending (south->north, west->east).
    - Variables with spatial dimensions transposed to [..., lat, lon].
    """
    if ds is None:
        return None

    ds = standardize_coords(ds)

    if "lat" in ds.coords:
        ds = ds.sortby("lat")
    if "lon" in ds.coords:
        ds = ds.sortby("lon")

    for var in ds.data_vars:
        da = ds[var]
        dims = list(da.dims)
        if "lat" in dims and "lon" in dims:
            non_spatial_dims = [dim for dim in dims if dim not in {"lat", "lon"}]
            if "time" in non_spatial_dims:
                non_spatial_dims = ["time"] + [dim for dim in non_spatial_dims if dim != "time"]
            target_order = non_spatial_dims + ["lat", "lon"]
            ds[var] = da.transpose(*target_order)

    return ds


def load_dataset_standardized(
    file_path: str,
    decode_times: bool = False,
    chunks: Optional[Dict[str, int]] = None,
) -> Optional[xr.Dataset]:
    """
    Load NetCDF dataset and standardize coordinates.
    
    Parameters:
    -----------
    file_path : str
        Path to NetCDF file
    decode_times : bool
        Whether to decode time values (default: False)
    
    Returns:
    --------
    xarray.Dataset or None
        Loaded and standardized dataset, or None if file not found
    """
    if not os.path.isfile(file_path):
        return None

    try:
        ds = xr.open_dataset(
            file_path,
            decode_times=decode_times,
            engine='netcdf4',
            chunks=chunks,
        )
    except ValueError:
        # Some legacy files store malformed calendar attrs (e.g., empty float arrays),
        # which breaks xarray CF decoding. Fallback to raw load and decode best-effort.
        ds = xr.open_dataset(
            file_path,
            decode_times=False,
            engine='netcdf4',
            chunks=chunks,
        )
        if decode_times:
            time_coord = None
            for coord in ds.coords:
                if 'time' in str(coord).lower():
                    time_coord = coord
                    break

            if time_coord is not None:
                coord = ds[time_coord]
                units = coord.attrs.get('units', '')
                calendar = coord.attrs.get('calendar', 'standard')
                if not isinstance(calendar, str) or not calendar.strip():
                    calendar = 'standard'

                if units and not np.issubdtype(coord.values.dtype, np.datetime64):
                    try:
                        decoded = num2date(coord.values, units=units, calendar=calendar)
                        ds = ds.assign_coords({time_coord: np.array(decoded, dtype='datetime64[ns]')})
                    except Exception:
                        pass

    ds = canonicalize_spatial_layout(ds)
    return ds


def fix_bathymetry_dataset(ds: xr.Dataset) -> xr.Dataset:
    """
    Standardize bathymetry dataset to use (lat, lon) dimensions.
    
    Converts dimensions from (y, x) to (lat, lon) if needed and ensures
    proper coordinate assignment.
    
    Parameters:
    -----------
    ds : xarray.Dataset
        Input bathymetry dataset
    
    Returns:
    --------
    xarray.Dataset
        Fixed dataset with (lat, lon) dimensions
    """
    # First, standardize coordinate names to lat/lon when they already exist as coordinates.
    rename_dict = {}
    for coord in ds.coords:
        coord_lower = str(coord).lower()
        if 'lat' in coord_lower and coord != 'lat':
            rename_dict[coord] = 'lat'
        elif 'lon' in coord_lower and coord != 'lon':
            rename_dict[coord] = 'lon'
    if rename_dict:
        ds = ds.rename(rename_dict)

    # Many bathymetry sources store lon/lat as data variables (not coords) on x/y dims.
    # Promote them to coordinates and swap dims so spatial axes become true geodetic axes.
    if 'lat' in ds.variables and 'lon' in ds.variables:
        ds = ds.set_coords(['lat', 'lon'])

        if 'y' in ds.dims and ds['lat'].dims == ('y',):
            ds = ds.swap_dims({'y': 'lat'})
        if 'x' in ds.dims and ds['lon'].dims == ('x',):
            ds = ds.swap_dims({'x': 'lon'})
    else:
        # Fallback for old format datasets without explicit lon/lat variables.
        if 'y' in ds.dims and 'lat' not in ds.dims:
            ds = ds.rename({'y': 'lat'})
        if 'x' in ds.dims and 'lon' not in ds.dims:
            ds = ds.rename({'x': 'lon'})

    # Ensure elevation uses the correct dimension order
    if 'elevation' in ds.data_vars:
        ds['elevation'] = ds['elevation'].transpose('lat', 'lon')

    ds = canonicalize_spatial_layout(ds)

    return ds


def merge_datasets_in_time(ds1: xr.Dataset, ds2: xr.Dataset, 
                           time_dim: Optional[str] = None) -> xr.Dataset:
    """
    Merge two datasets along the time dimension.
    
    Parameters:
    -----------
    ds1 : xarray.Dataset
        First dataset
    ds2 : xarray.Dataset
        Second dataset
    time_dim : str, optional
        Name of time dimension (auto-detected if None)
    
    Returns:
    --------
    xarray.Dataset
        Merged dataset sorted by time
    """
    if time_dim is None:
        time_info = get_time_info(ds1)
        time_dim = time_info.get('coord_name', 'valid_time')
    
    merged = xr.concat([ds1, ds2], dim=time_dim).sortby(time_dim)
    
    # Remove potential duplicate timestamps
    time_vals = merged[time_dim].values
    _, unique_idx = np.unique(time_vals, return_index=True)
    merged = merged.isel({time_dim: np.sort(unique_idx)})
    
    # Standardize time coordinate name to 'time'
    if time_dim != 'time':
        merged = merged.rename({time_dim: 'time'})
    
    return merged





def plot_interpolation_comparison(ds_raw: xr.Dataset, ds_interp: xr.Dataset,
                                   var_name: str, config_item: Dict,
                                   time_idx: int = 0,
                                   figsize: Tuple[int, int] = (18, 14)) -> Optional[plt.Figure]:
    """
    Create a comprehensive 4-panel comparison of raw vs interpolated data.
    
    Panels:
    1. Raw grid
    2. Interpolated grid
    3. Difference map
    4. Distribution comparison histogram
    
    Parameters:
    -----------
    ds_raw : xarray.Dataset
        Raw (original) dataset
    ds_interp : xarray.Dataset
        Interpolated dataset
    var_name : str
        Name of the variable to compare
    config_item : dict
        Configuration for this variable (label, cmap, unit)
    time_idx : int
        Time index to compare (default: 0)
    figsize : tuple
        Figure size (width, height)
    
    Returns:
    --------
    matplotlib.figure.Figure or None: The figure object
    """
    # Get coordinates
    lat_raw, lon_raw = get_lat_lon_coords(ds_raw)
    lat_int, lon_int = get_lat_lon_coords(ds_interp)
    time_info = get_time_info(ds_raw)
    
    if var_name not in ds_raw.data_vars or var_name not in ds_interp.data_vars:
        print(f"Variable '{var_name}' not found in datasets")
        return None
    
    print(f"\n{'#'*70}")
    print(f"  VARIABLE: {config_item['label_long'].upper()}")
    print(f"{'#'*70}")
    
    # Grid transformation statistics
    raw_pts = len(ds_raw[lat_raw]) * len(ds_raw[lon_raw])
    int_pts = len(ds_interp[lat_int]) * len(ds_interp[lon_int])
    raw_mb = ds_raw.nbytes / (1024**2)
    int_mb = ds_interp.nbytes / (1024**2)
    change_pct = (int_pts/raw_pts - 1) * 100
    
    print(f"\nGRID TRANSFORMATION:")
    print(f"   Raw:          {len(ds_raw[lat_raw])}×{len(ds_raw[lon_raw])} = {raw_pts:,} points")
    print(f"   Interpolated: {len(ds_interp[lat_int])}×{len(ds_interp[lon_int])} = {int_pts:,} points")
    print(f"   Change:       {change_pct:+.1f}% ({'Upsampling' if change_pct > 0 else 'Downsampling'})")
    print(f"   Memory:       {raw_mb:.2f} MB → {int_mb:.2f} MB ({int_mb - raw_mb:+.2f} MB)")
    
    # Extract time slices
    if time_info.get('coord_name'):
        raw_slice = ds_raw[var_name].isel({time_info['coord_name']: time_idx})
        int_slice = ds_interp[var_name].isel({time_info['coord_name']: time_idx})
    else:
        raw_slice = ds_raw[var_name]
        int_slice = ds_interp[var_name]
    
    # Calculate vmin and vmax for consistent color scales
    vmin = float(min(raw_slice.min().values, int_slice.min().values))
    vmax = float(max(raw_slice.max().values, int_slice.max().values))
    
    # Augment interpolated grid to raw grid size for direct comparison
    int_slice_aug = int_slice.interp({lat_int: raw_slice[lat_raw], lon_int: raw_slice[lon_raw]}, 
                                     method='nearest')
    
    # Create 4-panel visualization
    fig, axes = plt.subplots(2, 2, figsize=figsize)
    
    # Panel 1: Raw grid
    raw_slice.plot(ax=axes[0,0], x=lon_raw, y=lat_raw, 
                  cmap=config_item['cmap'], vmin=vmin, vmax=vmax,
                  cbar_kwargs={'label': f'{config_item["unit"]}'})
    axes[0,0].set_title(f"Raw Grid: {len(ds_raw[lat_raw])}×{len(ds_raw[lon_raw])}", 
                      fontweight='bold', fontsize=12)
    axes[0,0].grid(True, alpha=0.3, linestyle='--')
    
    # Panel 2: Interpolated grid
    int_slice.plot(ax=axes[0,1], x=lon_int, y=lat_int, 
                  cmap=config_item['cmap'], vmin=vmin, vmax=vmax,
                  cbar_kwargs={'label': f'{config_item["unit"]}'})
    axes[0,1].set_title(f"Interpolated Grid: {len(ds_interp[lat_int])}×{len(ds_interp[lon_int])}", 
                      fontweight='bold', fontsize=12)
    axes[0,1].grid(True, alpha=0.3, linestyle='--')
    
    # Panel 3: Difference map
    diff = int_slice_aug - raw_slice
    max_diff = round(float(np.abs(diff).max()), 4)
    diff.plot(ax=axes[1,0], x=lon_raw, y=lat_raw, 
              cmap='RdBu_r', vmin=-max_diff, vmax=max_diff,
              cbar_kwargs={'label': f'Difference ({config_item["unit"]})'})
    axes[1,0].set_title("Difference (Interpolated - Raw)", fontweight='bold', fontsize=12)
    axes[1,0].grid(True, alpha=0.3, linestyle='--')
    
    # Panel 4: Distribution comparison histogram
    raw_vals = raw_slice.values.flatten()
    int_vals = int_slice.values.flatten()
    raw_vals = raw_vals[~np.isnan(raw_vals)]
    int_vals = int_vals[~np.isnan(int_vals)]
    
    axes[1,1].hist(raw_vals, bins=50, alpha=0.5, label='Raw', 
                  color=plt.get_cmap(config_item['cmap'])(0.4), 
                  density=True, edgecolor='black')
    axes[1,1].hist(int_vals, bins=50, alpha=0.5, label='Interpolated', 
                  color=plt.get_cmap(config_item['cmap'])(0.8), 
                  density=True, edgecolor='black')
    axes[1,1].set_xlabel(f'{config_item["label_short"]} ({config_item["unit"]})', fontsize=11)
    axes[1,1].set_ylabel('Density', fontsize=11)
    axes[1,1].set_title('Value Distribution Comparison', fontweight='bold', fontsize=12)
    axes[1,1].legend(fontsize=10)
    axes[1,1].grid(True, alpha=0.3, axis='y')
    
    plt.suptitle(f'{config_item["label_long"]} - Interpolation Analysis', 
                fontsize=16, fontweight='bold')
    plt.tight_layout(rect=[0, 0, 1, 0.98])
    
    print(f"Maximum absolute difference: {max_diff} {config_item['unit']}")
    
    return fig


