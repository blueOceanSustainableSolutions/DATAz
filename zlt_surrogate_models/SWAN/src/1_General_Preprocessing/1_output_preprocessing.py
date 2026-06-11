import os
import argparse
import glob
import gc
from pathlib import Path

import numpy as np
import xarray as xr

from f_utils import load_dataset_standardized
from f_preprocessing_core import apply_preprocessing, save_clean_netcdf, add_direction_trig_components



PROJECT_ROOT = "/projects/F202500265DT4STF2"
SIMULATION_PATH = "AutoSWAN/cases/TEST2"
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "SWAN_Surrogate", "data", "preprocessed")
TARGET_GRID_SIZE = 128


def mirror_data_along_x_axis(ds):
    """Mirror fields along x-axis by flipping data along latitude."""
    if "lat" not in ds.coords:
        return ds

    lat_values = ds["lat"].copy()
    updates = {}
    for var_name, da in ds.data_vars.items():
        if "lat" in da.dims:
            flipped = da.isel(lat=slice(None, None, -1)).assign_coords(lat=lat_values)
            updates[var_name] = flipped

    if updates:
        ds = ds.assign(updates)
    return ds


def find_first_nc_by_pattern(folder: str, pattern: str) -> str:
    matches = sorted(glob.glob(os.path.join(folder, pattern)))
    if not matches:
        raise FileNotFoundError(f"No files found matching '{pattern}' in {folder}")
    return matches[0]


def resolve_case_simulation_path(case_value: str) -> str:
    if case_value.startswith("AutoSWAN/"):
        return case_value
    return f"AutoSWAN/cases/{case_value}"


def get_results_time_window(
    project_root: str,
    simulation_path: str,
    reference_pattern: str = "HSig_atlantic*.nc",
) -> tuple[object, object]:
    """Return the native results time window used as reference for all preprocess steps."""
    results_dir = os.path.join(project_root, simulation_path, "results")
    ref_file = find_first_nc_by_pattern(results_dir, reference_pattern)
    ds_ref = load_dataset_standardized(ref_file, decode_times=True)
    if ds_ref is None or "time" not in ds_ref.coords:
        raise ValueError(f"Reference results file has no 'time' coordinate: {ref_file}")

    time_values = ds_ref["time"].values
    if len(time_values) == 0:
        raise ValueError(f"Reference results file has an empty time axis: {ref_file}")
    return time_values[0], time_values[-1]


def run(
    project_root: str = PROJECT_ROOT,
    simulation_path: str = SIMULATION_PATH,
    output_dir: str = OUTPUT_DIR,
    target_grid_size: int = TARGET_GRID_SIZE,
    time_start: object | None = None,
    time_end: object | None = None,
) -> str:
    os.makedirs(output_dir, exist_ok=True)

    results_dir = os.path.join(project_root, simulation_path, "results")
    print(f"[output] results_dir={results_dir}", flush=True)
    print(f"[output] target_grid_size={target_grid_size}", flush=True)

    file_paths = {
        "HSig": find_first_nc_by_pattern(results_dir, "HSig_atlantic*.nc"),
        "RTP": find_first_nc_by_pattern(results_dir, "RTP_atlantic*.nc"),
        "PDIR": find_first_nc_by_pattern(results_dir, "PDIR_atlantic*.nc"),
    }
    for key, path in file_paths.items():
        print(f"[output] {key} file: {path}", flush=True)

    if time_start is None or time_end is None:
        time_start, time_end = get_results_time_window(project_root, simulation_path)
    print(f"[output] time window: start={time_start}, end={time_end}", flush=True)

    temp_files: list[str] = []
    for key in ["HSig", "RTP", "PDIR"]:
        print(f"[output] loading {key}", flush=True)
        ds = load_dataset_standardized(
            file_paths[key],
            decode_times=True,
            chunks={"time": 24},
        )
        if ds is None:
            raise FileNotFoundError(f"Could not load dataset for {key}: {file_paths[key]}")

        if "time" in ds.coords:
            ds = ds.sel(time=slice(time_start, time_end))
            if ds.sizes.get("time", 0) == 0:
                raise ValueError(
                    f"No {key} data inside requested time window "
                    f"[{time_start}, {time_end}] in {file_paths[key]}"
                )

        var_name = list(ds.data_vars)[0]
        if key == "PDIR":
            print("[output] replacing PDIR missing sentinel -999 with NaN", flush=True)
            ds[var_name] = ds[var_name].where(ds[var_name] != -999, np.nan)

        print(f"[output] preprocessing {key}", flush=True)
        ds_pre = apply_preprocessing(
            ds,
            target_grid_size=target_grid_size,
            apply_temporal=True,
            silent=True,
        )
        ds_pre = mirror_data_along_x_axis(ds_pre)
        ds_pre = ds_pre.rename({list(ds_pre.data_vars)[0]: key})

        temp_file = os.path.join(
            output_dir,
            f"_tmp_output_{key}_{target_grid_size}x{target_grid_size}.nc",
        )
        print(f"[output] saving temporary {key} dataset to {temp_file}", flush=True)
        save_clean_netcdf(ds_pre, temp_file)
        temp_files.append(temp_file)

        # Free intermediates before processing the next large source file.
        del ds
        del ds_pre
        gc.collect()

    if not temp_files:
        raise RuntimeError("No output datasets were processed.")

    output_file = os.path.join(
        output_dir,
        f"wave_output_preprocessed_{target_grid_size}x{target_grid_size}.nc",
    )

    print("[output] merging temporary datasets", flush=True)
    merged_parts = [
        xr.open_dataset(path, decode_times=False, engine="netcdf4", chunks={"time": 24})
        for path in temp_files
    ]
    final_dataset = xr.merge(merged_parts, join="inner", compat="override")
    final_dataset = add_direction_trig_components(final_dataset)

    print(f"[output] saving merged output to {output_file}", flush=True)
    save_clean_netcdf(final_dataset, output_file)

    for ds_part in merged_parts:
        ds_part.close()

    print("[output] removing temporary files", flush=True)
    for path in temp_files:
        try:
            Path(path).unlink(missing_ok=True)
        except OSError:
            pass

    print("[output] done", flush=True)

    return output_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Output preprocessing")
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
