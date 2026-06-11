import importlib.util
from dataclasses import dataclass
from pathlib import Path
import argparse
import xarray as xr
import numpy as np
import glob
import json
import re

from f_preprocessing_core import save_clean_netcdf
from f_utils import load_dataset_standardized


BASE_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class PreprocessingConfig:
    project_root: Path
    boundary_case: str
    input_case: str
    output_case: str
    save_dir: Path
    grid_size: int
    point_lat: float
    point_lon: float


def extract_case_metadata(project_root: str, output_case: str) -> dict:
    """Extract simulation metadata (time window, lat/lon bounds) from case config.swn."""
    config_file = Path(project_root) / output_case / "config.swn"
    if not config_file.exists():
        print(f"[metadata] Warning: config.swn not found at {config_file}, using defaults", flush=True)
        return {}
    
    metadata = {}
    content = config_file.read_text()
    
    # Extract CGRID parameters
    cgrid_match = re.search(r'CGRID\s+REGular\s+xpc=([\d\.-]+)\s+ypc=([\d\.-]+).*?xlenc=([\d\.-]+)\s+ylenc=([\d\.-]+)', content, re.DOTALL)
    if cgrid_match:
        xpc, ypc, xlenc, ylenc = map(float, cgrid_match.groups())
        lon_min = xpc
        lon_max = xpc + xlenc
        lat_min = ypc
        lat_max = ypc + ylenc
        metadata["grid_bounds"] = {
            "lon_min": float(lon_min),
            "lon_max": float(lon_max),
            "lat_min": float(lat_min),
            "lat_max": float(lat_max),
        }
        print(f"[metadata] Extracted CGRID bounds: lon=[{lon_min}, {lon_max}], lat=[{lat_min}, {lat_max}]", flush=True)
    
    # Extract time window from NONSTATIONARY
    time_match = re.search(r'NONSTATIONARY\s+([\d\.]+)\s+(\d+)\s+(\w+)\s+([\d\.]+)', content)
    if time_match:
        time_start_str, interval, unit, time_end_str = time_match.groups()
        metadata["time_window"] = {
            "start": time_start_str,
            "end": time_end_str,
            "interval": int(interval),
            "unit": unit,
        }
        print(f"[metadata] Extracted time window: {time_start_str} to {time_end_str} ({interval} {unit})", flush=True)
    
    return metadata


def save_case_metadata(metadata: dict, output_dir: Path) -> None:
    """Save extracted case metadata as JSON."""
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata_file = output_dir / "case_metadata.json"
    with open(metadata_file, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"[metadata] Saved case metadata to {metadata_file}", flush=True)


def apply_bathymetry_bounds(bathymetry_ds: xr.Dataset, bounds: dict) -> xr.Dataset:
    """Crop bathymetry to the simulation grid bounds."""
    if "grid_bounds" not in bounds:
        return bathymetry_ds
    
    b = bounds["grid_bounds"]
    lon_min, lon_max = b["lon_min"], b["lon_max"]
    lat_min, lat_max = b["lat_min"], b["lat_max"]
    
    # Determine coordinate names (may be 'lon'/'lat' or 'longitude'/'latitude')
    lon_coord = None
    lat_coord = None
    for name in ["lon", "longitude"]:
        if name in bathymetry_ds.coords:
            lon_coord = name
            break
    for name in ["lat", "latitude"]:
        if name in bathymetry_ds.coords:
            lat_coord = name
            break
    
    if lon_coord is None or lat_coord is None:
        print(f"[bathy_bounds] Warning: Could not find lon/lat coordinates in bathymetry", flush=True)
        return bathymetry_ds
    
    # Select region
    ds_bounded = bathymetry_ds.sel(
        {lon_coord: slice(lon_min, lon_max), lat_coord: slice(lat_min, lat_max)},
        method="nearest"
    )
    print(f"[bathy_bounds] Cropped bathymetry to bounds: lon=[{lon_min}, {lon_max}], lat=[{lat_min}, {lat_max}]", flush=True)
    return ds_bounded

CASE_FOLDERS = [
    "BC_run10_022024_042024",
    "FAIAL",
]

DEFAULT_FOLDER_INDEX = 0
folder = CASE_FOLDERS[DEFAULT_FOLDER_INDEX]  # Default case folder for all cases if --folder/--case is not set
DEFAULT_PREPROCESSED_ROOT = Path("/projects/F202500265DT4STF2/HPC_SWAN_Surrogate_Github/data/preprocessed_ZLT2")
DEFAULT_CONFIG = PreprocessingConfig(
    project_root=Path("/projects/F202500265DT4STF2"),
    boundary_case=folder,
    input_case=folder,
    output_case=folder,
    save_dir=DEFAULT_PREPROCESSED_ROOT / folder,
    grid_size=128,
    point_lat=38.58383,
    point_lon=-28.54117,
)


def load_module(module_file: str, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, BASE_DIR / module_file)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise ImportError(f"Cannot load module from {module_file}")
    spec.loader.exec_module(module)
    return module


def resolve_case_simulation_path(case_value: str) -> str:
    if case_value.startswith("AutoSWAN/"):
        return case_value
    return f"AutoSWAN/cases/{case_value}"


def folder_name_from_case(case_value: str) -> str:
    case_path = Path(case_value)
    return case_path.name



def get_common_time_window_from_data(
    project_root: str,
    boundary_sim: str,
    input_sim: str, 
    output_sim: str,
) -> tuple[object, object]:
    """Determine common time window by reading actual data files from boundary/input/output."""

    def read_source_range(source_name: str, file_paths: list[str]) -> tuple[object, object] | None:
        starts = []
        ends = []
        for file_path in file_paths:
            ds = load_dataset_standardized(file_path, decode_times=True)
            if ds is None:
                continue
            try:
                if "time" not in ds.coords or ds.sizes.get("time", 0) == 0:
                    continue
                starts.append(ds["time"].values[0])
                ends.append(ds["time"].values[-1])
            finally:
                ds.close()

        if not starts:
            return None

        source_start = min(starts)
        source_end = max(ends)
        print(f"[run_all] {source_name} data time range: {source_start} to {source_end}", flush=True)
        return source_start, source_end

    time_ranges = []

    boundary_storage = Path(project_root) / boundary_sim / "storage"
    boundary_files = sorted(glob.glob(str(boundary_storage / "waves_atlantic*.nc")))
    if boundary_files:
        boundary_range = read_source_range("boundary", boundary_files)
        if boundary_range is not None:
            time_ranges.append(("boundary", boundary_range[0], boundary_range[1]))

    input_storage = Path(project_root) / input_sim / "storage"
    input_files = sorted(glob.glob(str(input_storage / "wind_atlantic*.nc")))
    if input_files:
        input_range = read_source_range("input", input_files)
        if input_range is not None:
            time_ranges.append(("input", input_range[0], input_range[1]))

    output_results = Path(project_root) / output_sim / "results"
    output_files = sorted(glob.glob(str(output_results / "HSig_atlantic*.nc")))
    if output_files:
        output_range = read_source_range("output", output_files)
        if output_range is not None:
            time_ranges.append(("output", output_range[0], output_range[1]))

    if not time_ranges:
        raise ValueError("Could not read time ranges from any data source")

    common_start = max(t_min for _, t_min, _ in time_ranges)
    common_end = min(t_max for _, _, t_max in time_ranges)
    if common_start > common_end:
        raise ValueError(f"No overlapping time window: {time_ranges}")

    common_end_ns = np.datetime64(common_end, "ns")
    midnight_ns = common_end_ns.astype("datetime64[D]").astype("datetime64[ns]")
    if common_end_ns == midnight_ns:
        common_end = common_end_ns - np.timedelta64(1, "m")
        print(f"[run_all] adjusted end from midnight to: {common_end}", flush=True)

    print(f"[run_all] common time window: {common_start} to {common_end}", flush=True)
    return common_start, common_end


def validate_required_paths(config: PreprocessingConfig) -> None:
    project_root = config.project_root
    boundary_sim = resolve_case_simulation_path(config.boundary_case)
    input_sim = resolve_case_simulation_path(config.input_case)
    output_sim = resolve_case_simulation_path(config.output_case)

    checks = {
        "boundary storage": project_root / boundary_sim / "storage",
        "input storage": project_root / input_sim / "storage",
        "input data": project_root / input_sim / "data",
        "output results": project_root / output_sim / "results",
    }

    missing = [f"{label}: {path}" for label, path in checks.items() if not path.exists()]
    if missing:
        raise FileNotFoundError("Required folders not found:\n" + "\n".join(missing))


def align_time_axes(output_files: list[str]) -> dict[str, object] | None:
    """Trim time-dependent files to the common overlap window."""
    time_files: list[str] = []
    starts = []
    ends = []

    for path in output_files:
        with xr.open_dataset(path, decode_times=True, engine="netcdf4") as ds:
            if "time" not in ds.coords or ds.sizes.get("time", 0) == 0:
                continue
            time_files.append(path)
            starts.append(ds["time"].values[0])
            ends.append(ds["time"].values[-1])

    if not time_files:
        return None

    common_start = max(starts)
    common_end = min(ends)
    if common_start > common_end:
        raise ValueError(
            f"No overlapping time window across outputs: start={common_start}, end={common_end}"
        )

    aligned_sizes: dict[str, int] = {}
    for path in time_files:
        with xr.open_dataset(path, decode_times=True, engine="netcdf4") as ds:
            ds_aligned = ds.sel(time=slice(common_start, common_end))
            if ds_aligned.sizes.get("time", 0) == 0:
                raise ValueError(f"Alignment produced empty time axis for file: {path}")
            aligned_sizes[Path(path).name] = int(ds_aligned.sizes["time"])
            save_clean_netcdf(ds_aligned, path)

    return {
        "common_start": str(common_start),
        "common_end": str(common_end),
        "time_sizes": aligned_sizes,
    }


def build_boundary_window_source_file(
    project_root: str,
    boundary_sim: str,
    time_start: object,
    time_end: object,
) -> str:
    """Create a temporary single boundary file constrained to the requested window."""
    storage_dir = Path(project_root) / boundary_sim / "storage"
    wave_files = sorted(glob.glob(str(storage_dir / "waves_atlantic*.nc")))
    if not wave_files:
        raise FileNotFoundError(f"No files found matching 'waves_atlantic*.nc' in {storage_dir}")

    window_parts = []
    for file_path in wave_files:
        ds = load_dataset_standardized(file_path, decode_times=True)
        if ds is None:
            continue
        try:
            if "time" not in ds.coords or ds.sizes.get("time", 0) == 0:
                continue
            ds_window = ds.sel(time=slice(time_start, time_end))
            if ds_window.sizes.get("time", 0) == 0:
                continue
            # Remove optional non-index coords (e.g., expver) that may differ across files.
            ds_window = ds_window.reset_coords(drop=True)
            window_parts.append(ds_window.load())
        finally:
            ds.close()

    if not window_parts:
        raise ValueError(
            f"No boundary data found across waves_atlantic*.nc for window [{time_start}, {time_end}]"
        )

    ds_concat = xr.concat(window_parts, dim="time").sortby("time")
    _, unique_indices = np.unique(ds_concat["time"].values, return_index=True)
    ds_concat = ds_concat.isel(time=np.sort(unique_indices))

    temp_filename = "waves_atlantic_000_window.nc"
    temp_path = storage_dir / temp_filename
    save_clean_netcdf(ds_concat, str(temp_path))
    ds_concat.close()
    return temp_filename


def run_all(config: PreprocessingConfig = DEFAULT_CONFIG) -> dict[str, object]:
    print(f"[run_all] starting with boundary={config.boundary_case}, input={config.input_case}, output={config.output_case}", flush=True)
    config.save_dir.mkdir(parents=True, exist_ok=True)
    validate_required_paths(config)
    print(f"[run_all] validated required paths, save_dir={config.save_dir}", flush=True)

    boundary_sim = resolve_case_simulation_path(config.boundary_case)
    input_sim = resolve_case_simulation_path(config.input_case)
    output_sim = resolve_case_simulation_path(config.output_case)

    # Extract and save case metadata (time window, lat/lon bounds)
    case_metadata = extract_case_metadata(str(config.project_root), output_sim)
    save_case_metadata(case_metadata, config.save_dir)

    boundary_mod = load_module("1_boundary_preprocessing.py", "boundary_preprocessing")
    input_mod = load_module("1_input_preprocessing.py", "input_preprocessing")
    output_mod = load_module("1_output_preprocessing.py", "output_preprocessing")
    visualization_mod = load_module("visualization.py", "preprocessed_visualization")

    # Get common time window from actual data files
    time_start, time_end = get_common_time_window_from_data(
        str(config.project_root),
        boundary_sim,
        input_sim,
        output_sim,
    )
    print(f"[run_all] using shared time window: start={time_start}, end={time_end}", flush=True)

    boundary_waves_pattern = build_boundary_window_source_file(
        str(config.project_root),
        boundary_sim,
        time_start,
        time_end,
    )
    print(f"[run_all] boundary source file prepared: {boundary_waves_pattern}", flush=True)

    print("[run_all] running boundary preprocessing", flush=True)
    boundary_output = boundary_mod.run(
        project_root=str(config.project_root),
        simulation_path=boundary_sim,
        output_dir=str(config.save_dir),
        waves_pattern=boundary_waves_pattern,
        time_start=time_start,
        time_end=time_end,
    )
    print(f"[run_all] boundary done: {boundary_output}", flush=True)

    print("[run_all] running input preprocessing", flush=True)
    input_outputs = input_mod.run(
        project_root=str(config.project_root),
        simulation_path=input_sim,
        output_dir=str(config.save_dir),
        target_grid_size=config.grid_size,
        time_start=time_start,
        time_end=time_end,
        bathymetry_bounds=case_metadata.get("grid_bounds"),
    )
    print(f"[run_all] input done: {input_outputs}", flush=True)

    print("[run_all] generating spatial visualization", flush=True)
    visualization_output = visualization_mod.generate_visualization(
        data_dir=str(config.save_dir),
        point_lat=config.point_lat,
        point_lon=config.point_lon,
    )
    print(f"[run_all] spatial visualization: {visualization_output}", flush=True)

    print("[run_all] generating time-series visualization", flush=True)
    timeseries_output = visualization_mod.generate_time_series_visualization(
        data_dir=str(config.save_dir),
        point_lat=config.point_lat,
        point_lon=config.point_lon,
    )
    print(f"[run_all] time-series visualization: {timeseries_output}", flush=True)

    print("[run_all] running output preprocessing", flush=True)
    output_output = output_mod.run(
        project_root=str(config.project_root),
        simulation_path=output_sim,
        output_dir=str(config.save_dir),
        target_grid_size=config.grid_size,
        time_start=time_start,
        time_end=time_end,
    )
    print(f"[run_all] output done: {output_output}", flush=True)

    alignment_info = align_time_axes([boundary_output, input_outputs[0], output_output])
    if alignment_info is not None:
        print(
            "[run_all] aligned time axes "
            f"to [{alignment_info['common_start']}, {alignment_info['common_end']}] "
            f"with sizes={alignment_info['time_sizes']}",
            flush=True,
        )

    return {
        "config": {
            "project_root": str(config.project_root),
            "boundary_case": config.boundary_case,
            "input_case": config.input_case,
            "output_case": config.output_case,
            "save_dir": str(config.save_dir),
            "grid_size": config.grid_size,
            "point_lat": config.point_lat,
            "point_lon": config.point_lon,
            "time_start": str(time_start),
            "time_end": str(time_end),
            "aligned_time_start": alignment_info["common_start"] if alignment_info is not None else None,
            "aligned_time_end": alignment_info["common_end"] if alignment_info is not None else None,
        },
        "case_metadata": case_metadata,
        "boundary": boundary_output,
        "inputs": input_outputs,
        "outputs": output_output,
        "visualization": str(visualization_output) if visualization_output is not None else None,
        "timeseries_visualization": str(timeseries_output) if timeseries_output is not None else None,
    }


def parse_args() -> PreprocessingConfig:
    parser = argparse.ArgumentParser(description="Run all preprocessing steps with centralized path config.")
    parser.add_argument("--project-root", default=str(DEFAULT_CONFIG.project_root))
    parser.add_argument(
        "--folder",
        help="Case folder name under AutoSWAN/cases used for boundary/input/output when specific cases are not provided.",
    )
    parser.add_argument("--case", help="Set the same case for boundary/input/output.")
    parser.add_argument("--boundary-case", default=DEFAULT_CONFIG.boundary_case)
    parser.add_argument("--input-case", default=DEFAULT_CONFIG.input_case)
    parser.add_argument("--output-case", default=DEFAULT_CONFIG.output_case)
    parser.add_argument("--save-dir", default=None)
    parser.add_argument("--grid-size", type=int, default=DEFAULT_CONFIG.grid_size)
    parser.add_argument("--point-lat", type=float, default=DEFAULT_CONFIG.point_lat)
    parser.add_argument("--point-lon", type=float, default=DEFAULT_CONFIG.point_lon)
    args = parser.parse_args()

    shared_case = args.case or args.folder
    boundary_case = shared_case or args.boundary_case
    input_case = shared_case or args.input_case
    output_case = shared_case or args.output_case

    if args.save_dir:
        save_dir = Path(args.save_dir).resolve()
    else:
        case_folder = folder_name_from_case(args.case) if args.case else folder_name_from_case(boundary_case)
        save_dir = DEFAULT_PREPROCESSED_ROOT / case_folder

    return PreprocessingConfig(
        project_root=Path(args.project_root).resolve(),
        boundary_case=boundary_case,
        input_case=input_case,
        output_case=output_case,
        save_dir=save_dir,
        grid_size=args.grid_size,
        point_lat=args.point_lat,
        point_lon=args.point_lon,
    )


if __name__ == "__main__":
    run_all(parse_args())
