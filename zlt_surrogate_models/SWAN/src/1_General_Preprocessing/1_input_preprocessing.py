import os
import argparse
import glob

from f_utils import (
    fix_bathymetry_dataset,
    merge_datasets_in_time,
    load_dataset_standardized,
)
from f_preprocessing_core import apply_preprocessing, aggregate_single_var_datasets, save_clean_netcdf


PROJECT_ROOT = "/projects/F202500265DT4STF2"
SIMULATION_PATH = "AutoSWAN/cases/TEST"
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "SWAN_Surrogate", "data", "preprocessed")
TARGET_GRID_SIZE = 128


def list_wind_files(storage_dir: str) -> list[str]:
    return sorted(glob.glob(os.path.join(storage_dir, "wind_atlantic*.nc")))


def resolve_case_simulation_path(case_value: str) -> str:
    if case_value.startswith("AutoSWAN/"):
        return case_value
    return f"AutoSWAN/cases/{case_value}"


def run(
    project_root: str = PROJECT_ROOT,
    simulation_path: str = SIMULATION_PATH,
    output_dir: str = OUTPUT_DIR,
    target_grid_size: int = TARGET_GRID_SIZE,
    time_start: object | None = None,
    time_end: object | None = None,
    bathymetry_bounds: dict | None = None,
) -> tuple[str, str]:
    os.makedirs(output_dir, exist_ok=True)

    storage_dir = os.path.join(project_root, simulation_path, "storage")
    data_dir = os.path.join(project_root, simulation_path, "data")

    wind_paths = list_wind_files(storage_dir)
    if not wind_paths:
        raise FileNotFoundError(f"No files found matching 'wind_atlantic*.nc' in {storage_dir}")
    wind_datasets = [load_dataset_standardized(path, decode_times=True) for path in wind_paths]

    wind_merged = wind_datasets[0]
    for ds_part in wind_datasets[1:]:
        wind_merged = merge_datasets_in_time(wind_merged, ds_part, time_dim="time")

    if time_start is not None and time_end is not None and "time" in wind_merged.coords:
        wind_merged = wind_merged.sel(time=slice(time_start, time_end))
        if wind_merged.sizes.get("time", 0) == 0:
            raise ValueError(
                f"No wind input data inside requested time window [{time_start}, {time_end}]"
            )

    datasets = {
        "u10": wind_merged[["u10"]],
        "v10": wind_merged[["v10"]],
    }

    bathy = load_dataset_standardized(os.path.join(data_dir, "bathy_atlantic.nc"))
    bathy_fixed = fix_bathymetry_dataset(bathy)
    if bathymetry_bounds:
        lon_min = bathymetry_bounds.get("lon_min")
        lon_max = bathymetry_bounds.get("lon_max")
        lat_min = bathymetry_bounds.get("lat_min")
        lat_max = bathymetry_bounds.get("lat_max")
        if None not in (lon_min, lon_max, lat_min, lat_max):
            bathy_fixed = bathy_fixed.sel(
                lon=slice(lon_min, lon_max),
                lat=slice(lat_min, lat_max),
            )
    datasets["bathy"] = bathy_fixed[["elevation"]]

    datasets_preprocessed = {
        key: apply_preprocessing(
            ds,
            target_grid_size=target_grid_size,
            apply_temporal=(key in ["u10", "v10"]),
            silent=True,
        )
        for key, ds in datasets.items()
    }

    wind_output_file = os.path.join(
        output_dir,
        f"wind_inputs_preprocessed_{target_grid_size}x{target_grid_size}.nc",
    )
    bathy_output_file = os.path.join(
        output_dir,
        f"bathymetry_preprocessed_{target_grid_size}x{target_grid_size}.nc",
    )

    wind_agg = aggregate_single_var_datasets(
        {"u10": datasets_preprocessed["u10"], "v10": datasets_preprocessed["v10"]},
        {"u10": "u10", "v10": "v10"},
    )
    save_clean_netcdf(wind_agg, wind_output_file)
    save_clean_netcdf(datasets_preprocessed["bathy"], bathy_output_file)

    return wind_output_file, bathy_output_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Input preprocessing")
    parser.add_argument("--project-root", default=PROJECT_ROOT)
    parser.add_argument("--case", default=SIMULATION_PATH)
    parser.add_argument("--save-dir", default=OUTPUT_DIR)
    parser.add_argument("--grid-size", type=int, default=TARGET_GRID_SIZE)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(
        project_root=args.project_root,
        simulation_path=resolve_case_simulation_path(args.case),
        output_dir=args.save_dir,
        target_grid_size=args.grid_size,
    )
