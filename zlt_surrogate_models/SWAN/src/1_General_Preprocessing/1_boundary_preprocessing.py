import os
import argparse
import glob

from f_utils import load_dataset_standardized
from f_boundary_core import (
    generate_boundary_points,
    find_nearest_points,
    extract_boundary_on_swan_grid,
)
from f_preprocessing_core import (
    save_clean_netcdf,
    add_direction_trig_components,
)


PROJECT_ROOT = "/projects/F202500265DT4STF2"
SIMULATION_PATH = "AutoSWAN/cases/TEST"
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "SWAN_Surrogate", "data", "preprocessed")

SWAN_CONFIG = {
    "lon_min": -29.2200,
    "lon_max": -28.22,
    "lat_min": 37.92,
    "lat_max": 38.92,
    "lat_points": 128,
    "lon_points": 128,
}


def resolve_case_simulation_path(case_value: str) -> str:
    if case_value.startswith("AutoSWAN/"):
        return case_value
    return f"AutoSWAN/cases/{case_value}"


def find_first_nc_by_pattern(folder: str, pattern: str) -> str:
    matches = sorted(glob.glob(os.path.join(folder, pattern)))
    if not matches:
        raise FileNotFoundError(f"No files found matching '{pattern}' in {folder}")
    return matches[0]


def run(
    project_root: str = PROJECT_ROOT,
    simulation_path: str = SIMULATION_PATH,
    output_dir: str = OUTPUT_DIR,
    waves_pattern: str = "waves_atlantic*.nc",
    swan_config: dict[str, float | int] | None = None,
    time_start: object | None = None,
    time_end: object | None = None,
) -> str:
    os.makedirs(output_dir, exist_ok=True)
    cfg = swan_config or SWAN_CONFIG

    storage_dir = os.path.join(project_root, simulation_path, "storage")
    waves_file = find_first_nc_by_pattern(storage_dir, waves_pattern)

    ds_waves = load_dataset_standardized(waves_file, decode_times=True)
    if ds_waves is None:
        raise FileNotFoundError(f"Could not load waves dataset: {waves_file}")

    if time_start is not None and time_end is not None and "time" in ds_waves.coords:
        ds_waves = ds_waves.sel(time=slice(time_start, time_end))
        if ds_waves.sizes.get("time", 0) == 0:
            raise ValueError(
                f"No boundary data inside requested time window [{time_start}, {time_end}]"
            )

    era5_lats = ds_waves["lat"].values
    era5_lons = ds_waves["lon"].values

    boundary_dict = generate_boundary_points(
        lon_min=cfg["lon_min"],
        lon_max=cfg["lon_max"],
        lat_min=cfg["lat_min"],
        lat_max=cfg["lat_max"],
        lat_points=cfg["lat_points"],
        lon_points=cfg["lon_points"],
    )
    mapping_dict = find_nearest_points(boundary_dict, era5_lons, era5_lats)

    ds_boundary = extract_boundary_on_swan_grid(ds_waves, mapping_dict, cfg)
    ds_boundary = add_direction_trig_components(ds_boundary)
    ds_boundary.attrs["description"] = "Boundary-only wave data with NaN-filled interior for SWAN forcing"
    ds_boundary.attrs["swan_domain"] = str(cfg)

    output_file = os.path.join(
        output_dir,
        f"boundary_preprocessed_{cfg['lat_points']}x{cfg['lon_points']}.nc",
    )
    save_clean_netcdf(ds_boundary, output_file)
    return output_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Boundary preprocessing")
    parser.add_argument("--project-root", default=PROJECT_ROOT)
    parser.add_argument("--case", default=SIMULATION_PATH)
    parser.add_argument("--save-dir", default=OUTPUT_DIR)
    parser.add_argument("--waves-pattern", default="waves_atlantic*.nc")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(
        project_root=args.project_root,
        simulation_path=resolve_case_simulation_path(args.case),
        output_dir=args.save_dir,
        waves_pattern=args.waves_pattern,
    )
