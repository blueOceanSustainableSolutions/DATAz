import argparse
import glob
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

WAVE_REFERENCE_FILE = "wave_output_preprocessed_128x128.nc"
PLOT_CMAP = "viridis"
DIR_CMAP = "twilight_shifted"
SKIP_TIME_SERIES_VARS = {"elevation", "bathymetry", "depth"}
REFERENCE_BATHY_FILE_HINTS = ("bathymetry_preprocessed", "bathy")
REFERENCE_BATHY_VAR_HINTS = {"elevation", "bathymetry", "depth"}
DIRECTION_VAR_NAMES = {"pdir", "mwd", "direction", "dir"}


def find_nc_files(data_dir: Path, pattern: str) -> list[str]:
    return sorted(glob.glob(str(data_dir / "**" / pattern), recursive=True))


def to_2d_slice(da: xr.DataArray) -> xr.DataArray:
    dims = list(da.dims)
    if "lat" not in dims or "lon" not in dims:
        raise ValueError(f"Variable '{da.name}' is missing lat/lon dimensions")

    indexers = {dim: 0 for dim in dims if dim not in {"lat", "lon"}}
    da2 = da.isel(indexers).transpose("lat", "lon")

    if da2["lat"].values[0] > da2["lat"].values[-1]:
        da2 = da2.sortby("lat")
    if da2["lon"].values[0] > da2["lon"].values[-1]:
        da2 = da2.sortby("lon")
    return da2


def nearest_index(values: np.ndarray, target: float) -> int:
    vals = np.asarray(values, dtype=float)
    return int(np.argmin(np.abs(vals - float(target))))


def is_numeric_latlon_var(da: xr.DataArray, require_time: bool = False) -> bool:
    if not np.issubdtype(da.dtype, np.number):
        return False
    if "lat" not in da.dims or "lon" not in da.dims:
        return False
    if require_time and "time" not in da.dims:
        return False
    return True


def iter_matching_variables(
    nc_files: list[str],
    require_time: bool = False,
    skip_vars: set[str] | None = None,
):
    skip_vars = skip_vars or set()
    for nc_file in nc_files:
        try:
            with xr.open_dataset(nc_file, decode_times=False) as ds:
                for var_name, da in ds.data_vars.items():
                    if var_name.lower() in skip_vars:
                        continue
                    if is_numeric_latlon_var(da, require_time=require_time):
                        yield nc_file, var_name
        except Exception:
            continue


def panel_shape(n_panels: int, n_cols: int = 2) -> tuple[int, int]:
    n_rows = (n_panels + n_cols - 1) // n_cols
    return n_rows, n_cols


def choose_reference_point(nc_files: list[str], req_lat: float, req_lon: float) -> tuple[float, float, str]:
    # Prefer bathymetry as canonical spatial reference when available.
    bathy_priority_files = [
        f
        for f in nc_files
        if any(hint in Path(f).name.lower() for hint in REFERENCE_BATHY_FILE_HINTS)
    ]
    ordered_files = bathy_priority_files + [f for f in nc_files if f not in bathy_priority_files]

    for nc_file in ordered_files:
        try:
            with xr.open_dataset(nc_file, decode_times=False) as ds:
                bathy_vars = [
                    var_name
                    for var_name, da in ds.data_vars.items()
                    if var_name.lower() in REFERENCE_BATHY_VAR_HINTS and is_numeric_latlon_var(da, require_time=False)
                ]
                for var_name in bathy_vars:
                    da2 = to_2d_slice(ds[var_name])
                    lat_vals = da2["lat"].values
                    lon_vals = da2["lon"].values
                    i = nearest_index(lat_vals, req_lat)
                    j = nearest_index(lon_vals, req_lon)
                    ref_lat = float(lat_vals[i])
                    ref_lon = float(lon_vals[j])
                    src = f"{Path(nc_file).name}:{var_name}"
                    return ref_lat, ref_lon, src
        except Exception:
            continue

    # Fallback to wave output time-varying variables.
    preferred_wave = [f for f in nc_files if WAVE_REFERENCE_FILE in Path(f).name]
    wave_candidates = preferred_wave + [f for f in nc_files if f not in preferred_wave]

    for nc_file, var_name in iter_matching_variables(wave_candidates, require_time=True):
        try:
            with xr.open_dataset(nc_file, decode_times=False) as ds:
                da2 = to_2d_slice(ds[var_name])
                lat_vals = da2["lat"].values
                lon_vals = da2["lon"].values
                i = nearest_index(lat_vals, req_lat)
                j = nearest_index(lon_vals, req_lon)
                ref_lat = float(lat_vals[i])
                ref_lon = float(lon_vals[j])
                src = f"{Path(nc_file).name}:{var_name}"
                return ref_lat, ref_lon, src
        except Exception:
            continue

    # Final fallback: accept any lat/lon numeric variable.
    for nc_file, var_name in iter_matching_variables(ordered_files, require_time=False):
        try:
            with xr.open_dataset(nc_file, decode_times=False) as ds:
                da2 = to_2d_slice(ds[var_name])
                lat_vals = da2["lat"].values
                lon_vals = da2["lon"].values
                i = nearest_index(lat_vals, req_lat)
                j = nearest_index(lon_vals, req_lon)
                ref_lat = float(lat_vals[i])
                ref_lon = float(lon_vals[j])
                src = f"{Path(nc_file).name}:{var_name}"
                return ref_lat, ref_lon, src
        except Exception:
            continue

    raise ValueError("No lat/lon numeric variable found to pick reference point")


def wave_color_limits(var_name: str, values: np.ndarray) -> tuple[float | None, float | None]:
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return None, None

    if var_name == "PDIR":
        return 0.0, 360.0

    if var_name in {"HSig", "RTP"}:
        q_low, q_high = np.nanpercentile(finite, [2, 98])
        if q_high > q_low:
            return float(q_low), float(q_high)

    return None, None


def is_direction_variable(var_name: str) -> bool:
    lower = var_name.lower()
    if lower in DIRECTION_VAR_NAMES:
        return True
    return lower.endswith("dir") or lower.endswith("direction")


def draw_direction_arrows(
    ax: plt.Axes,
    lon_vals: np.ndarray,
    lat_vals: np.ndarray,
    angles_deg: np.ndarray,
) -> None:
    # SWAN/metocean directions are commonly clockwise from North and indicate where waves come from.
    # Convert to propagation direction by adding 180 degrees, then map to (u, v) components.
    theta = np.deg2rad((angles_deg + 180.0) % 360.0)
    u = np.sin(theta)
    v = np.cos(theta)

    lon_grid, lat_grid = np.meshgrid(lon_vals, lat_vals)
    mask = np.isfinite(angles_deg)

    step_lat = max(1, len(lat_vals) // 18)
    step_lon = max(1, len(lon_vals) // 18)

    lon_s = lon_grid[::step_lat, ::step_lon]
    lat_s = lat_grid[::step_lat, ::step_lon]
    u_s = u[::step_lat, ::step_lon]
    v_s = v[::step_lat, ::step_lon]
    mask_s = mask[::step_lat, ::step_lon]

    # Soft background for land/NaN context while emphasizing arrow directions.
    bg = np.where(np.isfinite(angles_deg), 1.0, np.nan)
    ax.pcolormesh(lon_vals, lat_vals, bg, shading="auto", cmap="Greys", alpha=0.10)

    ax.quiver(
        lon_s[mask_s],
        lat_s[mask_s],
        u_s[mask_s],
        v_s[mask_s],
        angles="xy",
        scale_units="xy",
        scale=38,
        width=0.003,
        headwidth=3.2,
        headlength=4.8,
        headaxislength=4.2,
        color="black",
        alpha=0.85,
    )


def is_output_wave_file(nc_file: str) -> bool:
    file_name = Path(nc_file).name
    return file_name.startswith("wave_output_preprocessed_")


def plot_output_direction(
    ax: plt.Axes,
    lon_vals: np.ndarray,
    lat_vals: np.ndarray,
    angles_deg: np.ndarray,
) -> plt.cm.ScalarMappable:
    wrapped = np.mod(angles_deg, 360.0)

    # Cyclic colormap provides smooth transitions near 0/360 degrees.
    mesh = ax.pcolormesh(
        lon_vals,
        lat_vals,
        wrapped,
        shading="auto",
        cmap=DIR_CMAP,
        vmin=0.0,
        vmax=360.0,
    )

    draw_direction_arrows(ax, lon_vals, lat_vals, wrapped)
    return mesh


def configure_map_axes(ax: plt.Axes, lon_vals: np.ndarray, lat_vals: np.ndarray, ref_lon: float, ref_lat: float) -> None:
    ax.plot(ref_lon, ref_lat, marker="o", markersize=6, markerfacecolor="none", markeredgecolor="red", markeredgewidth=1.4)
    ax.set_xlim(float(np.nanmin(lon_vals)), float(np.nanmax(lon_vals)))
    ax.set_ylim(float(np.nanmin(lat_vals)), float(np.nanmax(lat_vals)))
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")


def generate_visualization(
    data_dir: str | Path = ".",
    pattern: str = "*.nc",
    point_lat: float = 38.60,
    point_lon: float = -28.70,
) -> Path | None:
    data_dir = Path(data_dir).resolve()
    nc_files = find_nc_files(data_dir, pattern)

    if not nc_files:
        print(f"No .nc files found under: {data_dir}")
        return None

    ref_lat, ref_lon, ref_src = choose_reference_point(nc_files, point_lat, point_lon)
    print(
        "Reference point from canonical grid (bathymetry-priority): "
        f"req=({point_lat:.6f}, {point_lon:.6f}) -> ref=({ref_lat:.6f}, {ref_lon:.6f}) from {ref_src}"
    )

    targets = list(iter_matching_variables(nc_files, require_time=False))

    if not targets:
        print("No lat/lon numeric variables found for spatial visualization")
        return None

    n_panels = len(targets)
    n_rows, n_cols = panel_shape(n_panels)

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(12, 5 * n_rows), squeeze=False)
    axes_flat = axes.flatten()

    for idx, (nc_file, var_name) in enumerate(targets):
        ax = axes_flat[idx]
        try:
            with xr.open_dataset(nc_file, decode_times=False) as ds:
                da2 = to_2d_slice(ds[var_name])
            z = np.asarray(da2.values, dtype=float)
            lat_vals = np.asarray(da2["lat"].values, dtype=float)
            lon_vals = np.asarray(da2["lon"].values, dtype=float)

            mesh = None
            if is_direction_variable(var_name):
                if is_output_wave_file(nc_file):
                    mesh = plot_output_direction(ax, lon_vals, lat_vals, z)
                else:
                    # Keep non-output direction variables (for example boundary) on color scale.
                    vmin, vmax = wave_color_limits(var_name, z)
                    mesh = ax.pcolormesh(lon_vals, lat_vals, z, shading="auto", cmap=PLOT_CMAP, vmin=vmin, vmax=vmax)
            else:
                vmin, vmax = wave_color_limits(var_name, z)
                mesh = ax.pcolormesh(lon_vals, lat_vals, z, shading="auto", cmap=PLOT_CMAP, vmin=vmin, vmax=vmax)
            configure_map_axes(ax, lon_vals, lat_vals, ref_lon, ref_lat)

            file_label = str(Path(nc_file).relative_to(data_dir))
            ax.set_title(
                (
                    f"{file_label}\n"
                    f"var={var_name} | desired=({point_lat:.4f}, {point_lon:.4f})\n"
                    f"approximated=({ref_lat:.4f}, {ref_lon:.4f})"
                ),
                fontsize=9,
                pad=6,
            )
            if mesh is not None:
                cbar = plt.colorbar(mesh, ax=ax)
                if is_direction_variable(var_name) and is_output_wave_file(nc_file):
                    cbar.set_ticks([0, 45, 90, 135, 180, 225, 270, 315, 360])
                    cbar.set_label("Wave direction (degrees)")
        except Exception as exc:
            ax.text(0.5, 0.5, f"Error: {exc}", ha="center", va="center")
            ax.set_title(str(Path(nc_file).name))

    for idx in range(len(targets), len(axes_flat)):
        axes_flat[idx].set_visible(False)

    plt.tight_layout()
    out = data_dir / "nc_visualization.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved figure: {out}")
    return out


def generate_time_series_visualization(
    data_dir: str | Path = ".",
    pattern: str = "*.nc",
    point_lat: float = 38.60,
    point_lon: float = -28.70,
) -> Path | None:
    data_dir = Path(data_dir).resolve()
    nc_files = find_nc_files(data_dir, pattern)

    if not nc_files:
        print(f"No .nc files found under: {data_dir}")
        return None

    ref_lat, ref_lon, ref_src = choose_reference_point(nc_files, point_lat, point_lon)
    print(
        "Time-series point from canonical grid (bathymetry-priority): "
        f"req=({point_lat:.6f}, {point_lon:.6f}) -> ref=({ref_lat:.6f}, {ref_lon:.6f}) from {ref_src}"
    )

    series: list[tuple[str, str, np.ndarray, np.ndarray, float, float]] = []

    for nc_file, var_name in iter_matching_variables(
        nc_files,
        require_time=True,
        skip_vars=SKIP_TIME_SERIES_VARS,
    ):
        try:
            with xr.open_dataset(nc_file) as ds:
                ts = ds[var_name].sel(lat=ref_lat, lon=ref_lon, method="nearest")
                if "time" in ts.dims:
                    series.append((nc_file, var_name, ts["time"].values, ts.values, ref_lat, ref_lon))
        except Exception:
            continue

    if not series:
        print("No temporal lat/lon variables found for time-series visualization")
        return None

    n_panels = len(series)
    n_rows, n_cols = panel_shape(n_panels)
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(14, 4 * n_rows), squeeze=False)
    axes_flat = axes.flatten()

    for idx, (nc_file, var_name, times, values, lat_ref, lon_ref) in enumerate(series):
        ax = axes_flat[idx]
        ax.plot(times, values, linewidth=1.2)
        file_label = str(Path(nc_file).relative_to(data_dir))
        ax.set_title(
            (
                f"{file_label}\n"
                f"var={var_name} | desired=({point_lat:.4f}, {point_lon:.4f})\n"
                f"approximated=({lat_ref:.4f}, {lon_ref:.4f})"
            ),
            fontsize=9,
            pad=6,
        )
        ax.set_xlabel("time")
        ax.set_ylabel(var_name)
        ax.grid(True, alpha=0.3)

    for idx in range(len(series), len(axes_flat)):
        axes_flat[idx].set_visible(False)

    fig.autofmt_xdate(rotation=30)
    plt.tight_layout()
    out = data_dir / "nc_timeseries_visualization.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved time-series figure: {out}")
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Visualize preprocessed NetCDF files")
    parser.add_argument("--data-dir", default=".", help="Directory to search .nc files recursively")
    parser.add_argument("--pattern", default="*.nc", help="Glob pattern for NetCDF files")
    parser.add_argument("--point-lat", type=float, default=38.60, help="Target latitude")
    parser.add_argument("--point-lon", type=float, default=-28.70, help="Target longitude")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    generate_visualization(args.data_dir, args.pattern, args.point_lat, args.point_lon)
    generate_time_series_visualization(args.data_dir, args.pattern, args.point_lat, args.point_lon)
