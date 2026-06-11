#!/usr/bin/env python3
"""stage1.py – General Preprocessing for the SWAN surrogate user_case pipeline.

Reads raw ERA5 wave/wind NetCDF files from a raw-data directory (default:
``user_case/0_raw_data/``) and produces three preprocessed 128×128 NetCDF
files consumed by Stage 2:
  - wind_inputs_preprocessed_128x128.nc
  - bathymetry_preprocessed_128x128.nc
  - boundary_preprocessed_128x128.nc

The output directory is written to ``--output-dir`` (or a timestamped run
folder under ``user_case/`` by default).

Usage (from user_case dir, with swan_surrogate_env active):
    python stage1.py --date 2025-09-01
    python stage1.py --date 2025-09-01 --raw-data-dir /path/to/raw --output-dir /path/to/out
"""
from __future__ import annotations

import argparse
import glob
import os
import sys
from datetime import datetime
from pathlib import Path
import pandas as pd

# ---------------------------------------------------------------------------
# Thread / process limits before any native import
# ---------------------------------------------------------------------------
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")


def _ensure_runtime_library_path() -> None:
    """Re-exec with the conda C++ runtime first in LD_LIBRARY_PATH.

    Fixes the GLIBCXX_3.4.30 not-found error raised by netCDF4 on systems
    whose system libstdc++ is older than the one packaged in the conda env.
    """
    if os.environ.get("STAGE1_REEXECED") == "1":
        return
    conda_prefix = os.environ.get("CONDA_PREFIX") or sys.prefix
    conda_lib = str(Path(conda_prefix) / "lib")
    ld = os.environ.get("LD_LIBRARY_PATH", "")
    parts = [p for p in ld.split(":") if p]
    if not parts or parts[0] != conda_lib:
        os.environ["LD_LIBRARY_PATH"] = ":".join(
            [conda_lib] + [p for p in parts if p != conda_lib]
        )
        os.environ["STAGE1_REEXECED"] = "1"
        os.execvpe(sys.executable, [sys.executable] + sys.argv, os.environ)


# ---------------------------------------------------------------------------
# Directory constants
# ---------------------------------------------------------------------------
USER_CASE_DIR = Path(__file__).resolve().parent
REPO_ROOT     = USER_CASE_DIR.parent
STAGE1_SRC    = REPO_ROOT / "src" / "1_General_Preprocessing"

DEFAULT_RAW_DATA_DIR = USER_CASE_DIR / "0_raw_data"

# SWAN grid config used for boundary extraction
_SWAN_CFG = {
    "lon_min": -29.2200, "lon_max": -28.22,
    "lat_min": 37.92,    "lat_max": 38.92,
    "lat_points": 128,   "lon_points": 128,
}


# ---------------------------------------------------------------------------
# Core function (also imported by main2.py)
# ---------------------------------------------------------------------------

def run_stage1(
    raw_data_dir: Path,
    output_dir: Path,
    date: str = "2025-09-01",
    duration_hours: int = 24,
) -> dict:
    """Preprocess wind, bathymetry, and boundary forcing from raw NetCDF files.

    Parameters
    ----------
    raw_data_dir : Path
        Folder containing ``wind_atlantic*.nc``, ``waves_atlantic*.nc``, and
        ``bathy_atlantic.nc``.
    output_dir : Path
        Destination for the three preprocessed NetCDF outputs.
    date : str
        Date ``YYYY-MM-DD`` to slice from the raw data (one calendar day).

    Returns
    -------
    dict
        Paths to the three output files plus the ``date`` used.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Put Stage-1 source dir on sys.path so local imports resolve
    stage1_path = str(STAGE1_SRC)
    if stage1_path not in sys.path:
        sys.path.insert(0, stage1_path)

    from f_utils import (  # type: ignore
        load_dataset_standardized,
        merge_datasets_in_time,
        fix_bathymetry_dataset,
    )
    from f_preprocessing_core import (  # type: ignore
        apply_preprocessing,
        aggregate_single_var_datasets,
        save_clean_netcdf,
        add_direction_trig_components,
    )
    from f_boundary_core import (  # type: ignore
        generate_boundary_points,
        find_nearest_points,
        extract_boundary_on_swan_grid,
    )

    # ------------------------------------------------------------------ wind
    print(f"[stage1] Processing wind data for {date} …", flush=True)
    wind_files = sorted(glob.glob(str(raw_data_dir / "wind_atlantic*.nc")))
    if not wind_files:
        raise FileNotFoundError(
            f"No files matching 'wind_atlantic*.nc' in {raw_data_dir}"
        )
    wind_datasets = [load_dataset_standardized(f, decode_times=True) for f in wind_files]
    wind_merged = wind_datasets[0]
    for ds_part in wind_datasets[1:]:
        wind_merged = merge_datasets_in_time(wind_merged, ds_part, time_dim="time")
    
    start_date = pd.to_datetime(date)
    end_date = start_date + pd.Timedelta(hours=duration_hours - 1)
    wind_merged = wind_merged.sel(time=slice(start_date, end_date))
    
    if wind_merged.sizes.get("time", 0) == 0:
        raise ValueError(f"No wind data found for date '{date}' in {raw_data_dir}")

    preprocessed_wind = {
        k: apply_preprocessing(wind_merged[[k]], target_grid_size=128,
                               apply_temporal=True, silent=True)
        for k in ["u10", "v10"]
    }
    wind_agg = aggregate_single_var_datasets(
        preprocessed_wind, {"u10": "u10", "v10": "v10"}
    )
    wind_out = output_dir / "wind_inputs_preprocessed_128x128.nc"
    save_clean_netcdf(wind_agg, str(wind_out))
    print(f"[stage1] Wind   → {wind_out}", flush=True)

    # -------------------------------------------------------------- bathymetry
    print("[stage1] Processing bathymetry …", flush=True)
    bathy_file = raw_data_dir / "bathy_atlantic.nc"
    if not bathy_file.exists():
        raise FileNotFoundError(f"Bathymetry file not found: {bathy_file}")
    bathy = load_dataset_standardized(str(bathy_file))
    bathy_fixed = fix_bathymetry_dataset(bathy)[["elevation"]]
    bathy_pre = apply_preprocessing(
        bathy_fixed, target_grid_size=128, apply_temporal=False, silent=True
    )
    bathy_out = output_dir / "bathymetry_preprocessed_128x128.nc"
    save_clean_netcdf(bathy_pre, str(bathy_out))
    print(f"[stage1] Bathy  → {bathy_out}", flush=True)

    # --------------------------------------------------------------- boundary
    print(f"[stage1] Processing boundary wave data for {date} …", flush=True)
    wave_files = sorted(glob.glob(str(raw_data_dir / "waves_atlantic*.nc")))
    if not wave_files:
        raise FileNotFoundError(
            f"No files matching 'waves_atlantic*.nc' in {raw_data_dir}"
        )
    wave_parts = [load_dataset_standardized(f, decode_times=True) for f in wave_files]
    ds_waves = wave_parts[0]
    for part in wave_parts[1:]:
        ds_waves = merge_datasets_in_time(ds_waves, part, time_dim="time")
    
    ds_waves = ds_waves.sel(time=slice(start_date, end_date))
    
    if ds_waves.sizes.get("time", 0) == 0:
        raise ValueError(f"No boundary wave data found for date '{date}' in {raw_data_dir}")

    boundary_dict = generate_boundary_points(**_SWAN_CFG)
    mapping_dict  = find_nearest_points(
        boundary_dict, ds_waves["lon"].values, ds_waves["lat"].values
    )
    ds_boundary = extract_boundary_on_swan_grid(ds_waves, mapping_dict, _SWAN_CFG)
    ds_boundary = add_direction_trig_components(ds_boundary)
    boundary_out = output_dir / "boundary_preprocessed_128x128.nc"
    save_clean_netcdf(ds_boundary, str(boundary_out))
    print(f"[stage1] Bound  → {boundary_out}", flush=True)

    print("\n[stage1] Stage 1 complete.", flush=True)
    return {
        "output_dir": str(output_dir),
        "wind":       str(wind_out),
        "bathy":      str(bathy_out),
        "boundary":   str(boundary_out),
        "date":       date,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Stage-1 General Preprocessing: converts raw ERA5 NetCDF files "
            "into preprocessed 128×128 inputs for the SWAN surrogate."
        )
    )
    p.add_argument(
        "--raw-data-dir",
        type=str,
        default=str(DEFAULT_RAW_DATA_DIR),
        help=(
            f"Directory with raw .nc files "
            f"(wind_atlantic*.nc, waves_atlantic*.nc, bathy_atlantic.nc). "
            f"Default: {DEFAULT_RAW_DATA_DIR}"
        ),
    )
    p.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help=(
            "Where to write the preprocessed NetCDF files. "
            "Default: user_case/run<timestamp>_stage1/stage1/"
        ),
    )
    p.add_argument(
        "--date",
        type=str,
        default="2025-09-01",
        help="Date (YYYY-MM-DD) to extract from the raw data. Default: 2025-09-01",
    )
    p.add_argument(
        "--duration-hours",
        type=int,
        default=24,
        help="Number of hours to extract starting from --date. Default: 24",
    )
    return p.parse_args()


def main() -> None:
    _ensure_runtime_library_path()
    args = _parse_args()

    raw_data_dir = Path(args.raw_data_dir).resolve()

    if args.output_dir:
        output_dir = Path(args.output_dir).resolve()
    else:
        run_id     = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = USER_CASE_DIR / f"run{run_id}_stage1" / "stage1"

    print(f"\n[stage1] raw_data_dir : {raw_data_dir}")
    print(f"[stage1] output_dir   : {output_dir}")
    print(f"[stage1] date         : {args.date}")
    print(f"[stage1] duration     : {args.duration_hours} hours\n")

    result = run_stage1(
        raw_data_dir=raw_data_dir,
        output_dir=output_dir,
        date=args.date,
        duration_hours=args.duration_hours,
    )

    print("\n" + "=" * 72)
    print("[stage1] Done!")
    print(f"  Wind      : {result['wind']}")
    print(f"  Bathymetry: {result['bathy']}")
    print(f"  Boundary  : {result['boundary']}")
    print("=" * 72)


if __name__ == "__main__":
    main()
