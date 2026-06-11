"""
Interpolation functions for spatial and temporal resampling of xarray datasets.

Functions for bilinear spatial interpolation and linear temporal interpolation.
"""

import numpy as np
import xarray as xr
from f_coordinates import get_lat_lon_coords, get_time_info
from f_utils import canonicalize_spatial_layout


def spatial_bilinear_interpolation(ds: xr.Dataset, target_grid_size: int = 128) -> xr.Dataset:
    """
    Resample dataset to target grid size using bilinear interpolation.
    
    Parameters:
    -----------
    ds : xarray.Dataset
        Input dataset with spatial coordinates
    target_grid_size : int
        Target grid size (default: 128x128)
    
    Returns:
    --------
    xarray.Dataset
        Interpolated dataset
    """
    ds = canonicalize_spatial_layout(ds)
    lat_coord, lon_coord = get_lat_lon_coords(ds)
    
    if lat_coord is None or lon_coord is None:
        print(f"Warning: Could not identify lat/lon coordinates. Skipping interpolation.")
        return ds
    
    # Get current grid info
    current_lat_size = len(ds[lat_coord])
    current_lon_size = len(ds[lon_coord])
    
    print(f"  Current grid: {current_lat_size} x {current_lon_size}")
    
    if current_lat_size == target_grid_size and current_lon_size == target_grid_size:
        print(f"  Already at target grid size {target_grid_size}x{target_grid_size}. No interpolation needed.")
        return ds
    
    # Create target grid
    lat_min, lat_max = float(ds[lat_coord].min()), float(ds[lat_coord].max())
    lon_min, lon_max = float(ds[lon_coord].min()), float(ds[lon_coord].max())
    
    new_lat = np.linspace(lat_min, lat_max, target_grid_size)
    new_lon = np.linspace(lon_min, lon_max, target_grid_size)
    
    print(f"  Interpolating to {target_grid_size} x {target_grid_size}...")
    
    # Perform bilinear interpolation
    ds_interp = ds.interp(
        {lat_coord: new_lat, lon_coord: new_lon},
        method='linear'
    )
    
    print(f"  New grid: {len(ds_interp[lat_coord])} x {len(ds_interp[lon_coord])}")
    
    # Standardize coordinate names to 'lat' and 'lon'
    if lat_coord != 'lat' or lon_coord != 'lon':
        rename_dict = {}
        if lat_coord != 'lat':
            rename_dict[lat_coord] = 'lat'
        if lon_coord != 'lon':
            rename_dict[lon_coord] = 'lon'
        ds_interp = ds_interp.rename(rename_dict)
        print(f"  Standardized coordinates to 'lat' and 'lon'")
    
    ds_interp = canonicalize_spatial_layout(ds_interp)
    return ds_interp


def temporal_interpolation_to_hourly(ds: xr.Dataset) -> xr.Dataset:
    """
    Interpolate dataset to hourly time steps using linear interpolation.
    
    Parameters:
    -----------
    ds : xarray.Dataset
        Input dataset with time dimension
    
    Returns:
    --------
    xarray.Dataset
        Interpolated dataset with hourly time steps
    """
    time_info = get_time_info(ds)
    
    if time_info.get('coord_name') is None:
        print(f"  No time coordinate found. Skipping temporal interpolation.")
        return ds
    
    time_coord = time_info['coord_name']
    
    # Check current time resolution
    if time_info['n_steps'] < 2:
        print(f"  Only one time step. No interpolation needed.")
        return ds
    
    time_values = time_info['values']
    time_units = time_info.get('units', '')
    
    # Calculate current resolution
    time_diff = time_values[1] - time_values[0]
    
    # Check if times are datetime-like or numeric
    if np.issubdtype(time_values.dtype, np.datetime64):
        # Times are datetime objects
        time_diff_hours = time_diff / np.timedelta64(1, 'h')
    else:
        # Times are numeric (not decoded) - get units from attributes
        if 'hours' in time_units.lower():
            time_diff_hours = float(time_diff)
        elif 'days' in time_units.lower():
            time_diff_hours = float(time_diff) * 24
        elif 'minutes' in time_units.lower():
            time_diff_hours = float(time_diff) / 60
        elif 'seconds' in time_units.lower():
            time_diff_hours = float(time_diff) / 3600
        else:
            # Assume hours if not specified
            print(f"  Warning: Could not determine time units from '{time_units}'. Assuming hours.")
            time_diff_hours = float(time_diff)
    
    print(f"  Current time resolution: {time_diff_hours:.2f} hours")
    
    if abs(time_diff_hours - 1.0) < 0.01:
        print(f"  Already at 1-hour resolution. No interpolation needed.")
        return ds
    
    # Create hourly time steps
    time_start = time_values[0]
    time_end = time_values[-1]
    
    if np.issubdtype(time_values.dtype, np.datetime64):
        # For datetime types
        hourly_times = np.arange(time_start, time_end + np.timedelta64(1, 'h'), np.timedelta64(1, 'h'))
    else:
        # For numeric types, create hourly steps based on the unit
        if 'hours' in time_units.lower():
            step = 1
        elif 'days' in time_units.lower():
            step = 1/24
        elif 'minutes' in time_units.lower():
            step = 60
        elif 'seconds' in time_units.lower():
            step = 3600
        else:
            step = 1  # assume hours
        
        hourly_times = np.arange(time_start, time_end + step, step)
    
    print(f"  Interpolating from {len(ds[time_coord])} to {len(hourly_times)} time steps...")
    
    # Perform linear interpolation
    ds_interp = ds.interp({time_coord: hourly_times})
    
    # Report new time resolution
    new_time_values = ds_interp[time_coord].values
    if len(new_time_values) > 1:
        new_time_diff = new_time_values[1] - new_time_values[0]
        if np.issubdtype(new_time_values.dtype, np.datetime64):
            new_time_diff_hours = new_time_diff / np.timedelta64(1, 'h')
        else:
            if 'hours' in time_units.lower():
                new_time_diff_hours = float(new_time_diff)
            elif 'days' in time_units.lower():
                new_time_diff_hours = float(new_time_diff) * 24
            else:
                new_time_diff_hours = float(new_time_diff)
        print(f"  New time resolution: {new_time_diff_hours:.2f} hours")
    
    # Standardize time coordinate name to 'time'
    if time_coord != 'time':
        ds_interp = ds_interp.rename({time_coord: 'time'})
        print(f"  Standardized time coordinate to 'time'")
    
    return ds_interp
