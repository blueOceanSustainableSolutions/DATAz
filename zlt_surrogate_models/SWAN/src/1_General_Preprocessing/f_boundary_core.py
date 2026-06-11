"""Boundary extraction helpers for SWAN preprocessing."""

from typing import Dict, List, Tuple

import numpy as np
import xarray as xr
from scipy.spatial import KDTree

from f_utils import standardize_coords


def generate_boundary_points(
    lon_min: float,
    lon_max: float,
    lat_min: float,
    lat_max: float,
    lat_points: int,
    lon_points: int,
) -> Dict[str, np.ndarray]:
    """Generate north/south/east/west boundary points for a rectangular SWAN domain."""
    return {
        "north": np.column_stack([np.linspace(lon_min, lon_max, lon_points), np.full(lon_points, lat_max)]),
        "south": np.column_stack([np.linspace(lon_min, lon_max, lon_points), np.full(lon_points, lat_min)]),
        "east": np.column_stack([np.full(lat_points, lon_max), np.linspace(lat_min, lat_max, lat_points)]),
        "west": np.column_stack([np.full(lat_points, lon_min), np.linspace(lat_min, lat_max, lat_points)]),
    }


def find_nearest_points(
    boundary_dict: Dict[str, np.ndarray],
    era5_lons: np.ndarray,
    era5_lats: np.ndarray,
) -> Dict[str, Dict[str, np.ndarray]]:
    """Map each boundary point to its nearest ERA5 grid point using KDTree."""
    lon_grid, lat_grid = np.meshgrid(era5_lons, era5_lats)
    era5_points = np.column_stack([lon_grid.ravel(), lat_grid.ravel()])
    tree = KDTree(era5_points)

    mapping_dict: Dict[str, Dict[str, np.ndarray]] = {}
    for side, boundary_coords in boundary_dict.items():
        distances, flat_indices = tree.query(boundary_coords)
        lat_indices = flat_indices // len(era5_lons)
        lon_indices = flat_indices % len(era5_lons)
        mapping_dict[side] = {
            "nearest_indices": np.column_stack([lat_indices, lon_indices]),
            "nearest_coords": era5_points[flat_indices],
            "distances": distances,
        }
    return mapping_dict


def compute_boundary_segments(
    mapping_dict: Dict[str, Dict[str, np.ndarray]],
    era5_lons: np.ndarray,
    era5_lats: np.ndarray,
) -> List[Dict[str, float]]:
    """Compute contiguous segments that share the same source ERA5 grid point."""
    segments_list = []
    for side in ["north", "south", "east", "west"]:
        nearest_indices = mapping_dict[side]["nearest_indices"]
        segment_start = 0
        for i in range(1, len(nearest_indices)):
            if not np.array_equal(nearest_indices[i], nearest_indices[i - 1]):
                lat_idx, lon_idx = nearest_indices[i - 1]
                segments_list.append(
                    {
                        "boundary_side": side,
                        "segment_start_index": segment_start,
                        "segment_end_index": i - 1,
                        "n_points": i - segment_start,
                        "era5_lat": era5_lats[lat_idx],
                        "era5_lon": era5_lons[lon_idx],
                    }
                )
                segment_start = i

        lat_idx, lon_idx = nearest_indices[-1]
        segments_list.append(
            {
                "boundary_side": side,
                "segment_start_index": segment_start,
                "segment_end_index": len(nearest_indices) - 1,
                "n_points": len(nearest_indices) - segment_start,
                "era5_lat": era5_lats[lat_idx],
                "era5_lon": era5_lons[lon_idx],
            }
        )
    return segments_list


def extract_boundary_on_swan_grid(
    ds_waves: xr.Dataset,
    mapping_dict: Dict[str, Dict[str, np.ndarray]],
    swan_config: Dict[str, float],
) -> xr.Dataset:
    """Create boundary-only dataset on a SWAN grid with NaN-filled interior."""
    ds_waves = standardize_coords(ds_waves)
    required_coords = {"time", "lat", "lon"}
    if not required_coords.issubset(set(ds_waves.coords)):
        raise ValueError("Dataset must contain time, lat, and lon coordinates.")

    n_lat = int(swan_config["lat_points"])
    n_lon = int(swan_config["lon_points"])

    swan_lats = np.linspace(float(swan_config["lat_min"]), float(swan_config["lat_max"]), n_lat)
    swan_lons = np.linspace(float(swan_config["lon_min"]), float(swan_config["lon_max"]), n_lon)

    target_indices: Dict[str, List[Tuple[int, int]]] = {
        "north": [(n_lat - 1, j) for j in range(n_lon)],
        "south": [(0, j) for j in range(n_lon)],
        "east": [(i, n_lon - 1) for i in range(n_lat)],
        "west": [(i, 0) for i in range(n_lat)],
    }

    for side in ["north", "south", "east", "west"]:
        if side not in mapping_dict:
            raise ValueError(f"Missing mapping information for side: {side}")
        n_source = len(mapping_dict[side]["nearest_indices"])
        n_target = len(target_indices[side])
        if n_source != n_target:
            raise ValueError(
                f"Mapping length mismatch for side '{side}': source={n_source}, target={n_target}."
            )

    data_vars_dict = {}
    for var_name in ds_waves.data_vars:
        var = ds_waves[var_name]
        if not all(dim in var.dims for dim in ["time", "lat", "lon"]):
            continue

        var_t = var.transpose("time", "lat", "lon")
        data = np.full((var_t.sizes["time"], n_lat, n_lon), np.nan, dtype=np.float64)

        assigned_targets = set()
        for side in ["north", "south", "east", "west"]:
            source_indices = mapping_dict[side]["nearest_indices"]
            for (src_lat_idx, src_lon_idx), (tgt_lat_idx, tgt_lon_idx) in zip(source_indices, target_indices[side]):
                target_key = (int(tgt_lat_idx), int(tgt_lon_idx))
                if target_key in assigned_targets:
                    continue
                data[:, tgt_lat_idx, tgt_lon_idx] = var_t.values[:, int(src_lat_idx), int(src_lon_idx)]
                assigned_targets.add(target_key)

        data_vars_dict[var_name] = (("time", "lat", "lon"), data, var_t.attrs)

    if not data_vars_dict:
        raise ValueError("No wave variables with time/lat/lon dimensions were found.")

    out_attrs = dict(ds_waves.attrs)
    out_attrs["grid_type"] = "swan_boundary_mask"

    return xr.Dataset(
        data_vars=data_vars_dict,
        coords={"time": ds_waves["time"], "lat": swan_lats, "lon": swan_lons},
        attrs=out_attrs,
    )