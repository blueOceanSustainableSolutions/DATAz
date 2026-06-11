"""
Coordinate handling functions for xarray datasets.

Functions for identifying and formatting spatial and temporal coordinates
with support for various naming conventions.
"""

import numpy as np
import xarray as xr
from typing import Tuple, Optional, Dict
from datetime import datetime


def get_lat_lon_coords(ds: xr.Dataset) -> Tuple[Optional[str], Optional[str]]:
    """
    Identify latitude and longitude coordinate names in a dataset.
    
    Handles different naming conventions:
    - lat/lon
    - nav_lat/nav_lon
    - latitude/longitude
    
    Parameters:
    -----------
    ds : xarray.Dataset
        Input dataset
    
    Returns:
    --------
    tuple: (lat_coord_name, lon_coord_name)
    """
    lat_coord = None
    lon_coord = None
    
    for coord in ds.coords:
        coord_lower = str(coord).lower()
        if 'lat' in coord_lower and lat_coord is None:
            lat_coord = coord
        if 'lon' in coord_lower and lon_coord is None:
            lon_coord = coord
    
    return lat_coord, lon_coord


def format_time_value(time_val, time_units: str = '') -> str:
    """
    Format a time value to a readable string (DD/MM/YYYY HH:MM:SS).
    
    Parameters:
    -----------
    time_val : various
        Time value (datetime64, float, etc.)
    time_units : str
        Units string from NetCDF time variable
    
    Returns:
    --------
    str: Formatted time string
    """
    try:
        # Handle numpy datetime64
        if isinstance(time_val, np.datetime64):
            dt = time_val.astype('datetime64[s]').astype(datetime)
            return dt.strftime('%d/%m/%Y %H:%M:%S')
        
        # Handle pandas timestamp
        elif hasattr(time_val, 'strftime'):
            return time_val.strftime('%d/%m/%Y %H:%M:%S')
        
        # Handle numeric times with units
        elif time_units:
            # Try to parse units like "hours since 1970-01-01"
            if 'since' in time_units.lower():
                from netCDF4 import num2date
                try:
                    dt = num2date(time_val, time_units)
                    return dt.strftime('%d/%m/%Y %H:%M:%S')
                except:
                    pass
        
        # Fallback to string representation
        return str(time_val)[:19]
    
    except Exception:
        return str(time_val)[:19]


def get_time_coord(ds: xr.Dataset) -> Optional[str]:
    """
    Identify time coordinate name in a dataset.
    
    Parameters:
    -----------
    ds : xarray.Dataset
        Input dataset
    
    Returns:
    --------
    str or None: Time coordinate name
    """
    for coord in ds.coords:
        if 'time' in str(coord).lower():
            return coord
    return None


def get_time_info(ds: xr.Dataset) -> Dict:
    """
    Get comprehensive time coordinate information including raw values and formatted strings.
    
    Parameters:
    -----------
    ds : xarray.Dataset
        Input dataset
    
    Returns:
    --------
    dict: Dictionary containing:
        - 'coord_name': Name of time coordinate
        - 'values': Raw time values
        - 'start_raw': First time value (raw)
        - 'end_raw': Last time value (raw)
        - 'start_fmt': First time value (formatted as DD/MM/YYYY HH:MM:SS)
        - 'end_fmt': Last time value (formatted as DD/MM/YYYY HH:MM:SS)
        - 'n_steps': Number of time steps
        - 'resolution_hours': Time resolution in hours
        - 'units': Time units from attributes
    """
    time_coord = get_time_coord(ds)
    
    if time_coord is None:
        return {'coord_name': None}
    
    coord = ds[time_coord]
    time_values = coord.values
    time_units = coord.attrs.get('units', '')
    
    result = {
        'coord_name': time_coord,
        'values': time_values,
        'units': time_units,
        'n_steps': len(time_values)
    }
    
    if len(time_values) == 0:
        return result
    
    # Get start and end times
    result['start_raw'] = time_values[0]
    result['end_raw'] = time_values[-1]
    result['start_fmt'] = format_time_value(time_values[0], time_units)
    result['end_fmt'] = format_time_value(time_values[-1], time_units)
    
    # Calculate resolution
    if len(time_values) > 1:
        time_diff = time_values[1] - time_values[0]
        
        if np.issubdtype(time_values.dtype, np.datetime64):
            time_diff_hours = time_diff / np.timedelta64(1, 'h')
        else:
            if 'hours' in time_units.lower():
                time_diff_hours = float(time_diff)
            elif 'days' in time_units.lower():
                time_diff_hours = float(time_diff) * 24
            elif 'minutes' in time_units.lower():
                time_diff_hours = float(time_diff) / 60
            elif 'seconds' in time_units.lower():
                time_diff_hours = float(time_diff) / 3600
            else:
                time_diff_hours = float(time_diff)
        
        result['resolution_hours'] = float(time_diff_hours)
    
    return result


