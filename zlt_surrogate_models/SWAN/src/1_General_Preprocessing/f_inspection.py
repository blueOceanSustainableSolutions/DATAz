"""
Data inspection and summary functions for NetCDF/xarray datasets.

Functions for printing headers, checking missing values, and displaying dataset metrics.
"""

import xarray as xr
import prettytable
from f_coordinates import get_time_info



def print_dataset_summary(ds: xr.Dataset, name: str):
    """
    Print summary information for a dataset.
    
    Parameters:
    -----------
    ds : xarray.Dataset
        Dataset to summarize
    name : str
        Name of the dataset
    """
    pt = prettytable.PrettyTable()
    pt.field_names = ["Variable", "Dimensions", "Shape", "Data Type", "Missing Values", "Memory (MB)"]
    
    for var_name in ds.data_vars:
        var = ds[var_name]
        dims_str = str(var.dims)
        shape_str = str(var.shape)
        dtype_str = str(var.dtype)
        missing_count = var.isnull().sum().item()
        memory_mb = var.nbytes / (1024**2)

        pt.add_row([var_name, dims_str, shape_str, dtype_str, missing_count, f"{memory_mb:.2f}"])
    
    print(f"\n{name}:")
    print(pt)
    
    # Print coordinate information
    print(f"\nCoordinates:")
    for coord_name in ds.coords:
        coord = ds[coord_name]
        
        # Check if coordinate is scalar (0-dimensional)
        if coord.ndim == 0:
            print(f"  {coord_name}: scalar value = {float(coord.values):.4f}")
            continue
        
        # Check for time coordinates
        time_info = get_time_info(ds)
        if coord_name == time_info.get('coord_name'):
            if time_info['n_steps'] > 1:
                print(f"  {coord_name}: {time_info['n_steps']} steps")
                print(f"      from {time_info['start_fmt']} to {time_info['end_fmt']}")
                if 'resolution_hours' in time_info:
                    print(f"      resolution: {time_info['resolution_hours']:.2f} hours")
        else:
            print(f"  {coord_name}: {len(coord)} points, "
                  f"range: [{float(coord.min()):.4f}, {float(coord.max()):.4f}]")


def print_dataset_metrics(ds: xr.Dataset):
    """
    Display comprehensive metrics for a dataset.
    
    Parameters:
    -----------
    ds : xarray.Dataset
        Dataset to analyze
    """
    print("=" * 70)
    print("DATASET METRICS")
    print("=" * 70)
    
    # Create detailed metrics table
    pt = prettytable.PrettyTable()
    pt.field_names = ["Variable", "Min", "Max", "Mean", "Median", "Std Dev", "P05", "P95", "Shape"]
    
    for var_name in ds.data_vars:
        var = ds[var_name]
        var_min = float(var.min().values)
        var_max = float(var.max().values)
        var_mean = float(var.mean().values)
        var_std = float(var.std().values)
        var_median = float(var.median().values)
        var_p05 = float(var.quantile(0.05).values)
        var_p95 = float(var.quantile(0.95).values)
        shape_str = str(var.shape)
        
        pt.add_row([
            var_name,
            f"{var_min:.4f}",
            f"{var_max:.4f}",
            f"{var_mean:.4f}",
            f"{var_median:.4f}",
            f"{var_std:.4f}",
            f"{var_p05:.4f}",
            f"{var_p95:.4f}",
            shape_str
        ])
    
    print(pt)