#!/usr/bin/env python3
"""stage2.py – Surrogate Preprocessing for the SWAN surrogate user_case pipeline.

Reads the three preprocessed NetCDF files produced by stage1.py, applies the
pre-fitted scalers, builds input-only sequences (with IDW boundary fill), and
saves ``sequences.pt`` ready for Stage-3 inference.

The Stage-1 output directory is auto-detected from the most recent
``user_case/run*/stage1/`` folder if ``--stage1-dir`` is not supplied.

Usage (from user_case dir, with swan_surrogate_env active):
    python stage2.py
    python stage2.py --stage1-dir /path/to/stage1_output
    python stage2.py --stage1-dir /path/to/stage1_output --sequences-dir /path/to/seqs
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

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

    Fixes the GLIBCXX_3.4.30 not-found error raised by native extensions on
    systems whose system libstdc++ is older than the conda-packaged one.
    """
    if os.environ.get("STAGE2_REEXECED") == "1":
        return
    conda_prefix = os.environ.get("CONDA_PREFIX") or sys.prefix
    conda_lib = str(Path(conda_prefix) / "lib")
    ld = os.environ.get("LD_LIBRARY_PATH", "")
    parts = [p for p in ld.split(":") if p]
    if not parts or parts[0] != conda_lib:
        os.environ["LD_LIBRARY_PATH"] = ":".join(
            [conda_lib] + [p for p in parts if p != conda_lib]
        )
        os.environ["STAGE2_REEXECED"] = "1"
        os.execvpe(sys.executable, [sys.executable] + sys.argv, os.environ)


# ---------------------------------------------------------------------------
# Directory constants
# ---------------------------------------------------------------------------
USER_CASE_DIR = Path(__file__).resolve().parent
REPO_ROOT     = USER_CASE_DIR.parent
STAGE2_SRC    = REPO_ROOT / "src" / "2_Surrogate_Preprocessing"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_on_path(directory: Path) -> None:
    s = str(directory)
    if s not in sys.path:
        sys.path.insert(0, s)


def _find_latest_stage1() -> Path:
    """Return the most recent stage1 output directory under user_case/run*/."""
    candidates = sorted(
        USER_CASE_DIR.glob("run*/stage1/wind_inputs_preprocessed_128x128.nc"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if candidates:
        return candidates[0].parent
    raise FileNotFoundError(
        "No Stage-1 output found under user_case/. "
        "Run stage1.py (or main2.py --stage stage1) first."
    )


def _load_stage2_config():
    _ensure_on_path(STAGE2_SRC)
    sys.modules.pop("config", None)
    import config as cfg  # type: ignore
    return cfg


def _load_scalers(cfg):
    _ensure_on_path(STAGE2_SRC)
    from f_data_processing import import_scale  # type: ignore
    scalers = import_scale(cfg.SCALER_PATH)
    if not isinstance(scalers, dict):
        raise TypeError(f"Expected dict of scalers, got {type(scalers)}")
    print(
        f"[stage2] Loaded scalers from {cfg.SCALER_PATH}: {list(scalers.keys())}",
        flush=True,
    )
    return scalers


def _scale_dataset(ds, scalers: dict):
    """Apply pre-fitted scalers to an xarray Dataset, preserving NaNs."""
    import numpy as np

    ds = ds.copy(deep=True)
    for var_name in list(ds.data_vars):
        if var_name.endswith("_sin") or var_name.endswith("_cos"):
            continue
        scaler = scalers.get(var_name)
        if scaler is None:
            base = var_name.rsplit("_", 1)[0]
            scaler = scalers.get(base)
        if scaler is None:
            continue
        data = ds[var_name].values.astype(np.float64, copy=True)
        flat = data.reshape(-1)
        mask = np.isfinite(flat)
        if mask.any():
            flat[mask] = scaler.transform(flat[mask].reshape(-1, 1)).reshape(-1)
        ds[var_name] = (ds[var_name].dims, flat.reshape(data.shape).astype(np.float32))
    return ds


def _build_samples(stage1_dir: Path, cfg, scalers: dict) -> list:
    """Read preprocessed NetCDF files and build input-only sequences."""
    import numpy as np
    import torch
    import xarray as xr

    wind_path     = stage1_dir / "wind_inputs_preprocessed_128x128.nc"
    boundary_path = stage1_dir / "boundary_preprocessed_128x128.nc"
    bathy_path    = stage1_dir / "bathymetry_preprocessed_128x128.nc"

    for p in (wind_path, boundary_path, bathy_path):
        if not p.exists():
            raise FileNotFoundError(f"Required Stage-1 file missing: {p}")

    wind_vars    = list(cfg.WIND_VARS)
    boundary_vars = list(cfg.BOUNDARY_VARS)
    bathy_vars   = list(cfg.BATHY_VARS)
    n_wind_steps = int(cfg.PREVIOUS_INPUT_STEPS)
    n_bnd_steps  = int(cfg.PREVIOUS_BOUNDARY_STEPS)

    samples: list = []
    with (xr.open_dataset(wind_path)     as wind_raw,
          xr.open_dataset(boundary_path) as boundary_raw,
          xr.open_dataset(bathy_path)    as bathy_raw):

        wind_ds     = _scale_dataset(wind_raw,     scalers)
        boundary_ds = _scale_dataset(boundary_raw, scalers)
        bathy_ds    = _scale_dataset(bathy_raw,    scalers)

        n_time  = min(
            wind_ds.sizes.get("time", 0),
            boundary_ds.sizes.get("time", 0),
        )
        start_t = max(n_wind_steps, n_bnd_steps) - 1

        for t in range(start_t, n_time):
            channels = []
            for k in range(t - n_wind_steps + 1, t + 1):
                for v in wind_vars:
                    channels.append(wind_ds[v].isel(time=k).values)
            for k in range(t - n_bnd_steps + 1, t + 1):
                for v in boundary_vars:
                    channels.append(boundary_ds[v].isel(time=k).values)
            for v in bathy_vars:
                da = bathy_ds[v]
                channels.append(da.isel(time=t).values if "time" in da.dims else da.values)

            time_val = (
                str(wind_raw["time"].isel(time=t).values)
                if "time" in wind_raw.coords else str(t)
            )
            tensor = torch.from_numpy(np.stack(channels, axis=0).astype(np.float32))
            samples.append((tensor, time_val))

    return samples


# ---------------------------------------------------------------------------
# Core function (also imported by main2.py)
# ---------------------------------------------------------------------------

def run_stage2(
    stage1_dir: Path,
    sequences_dir: Path,
) -> dict:
    """Build input-only sequences from Stage-1 preprocessed NetCDF files.

    Parameters
    ----------
    stage1_dir : Path
        Directory with the three preprocessed NetCDF outputs from Stage 1.
    sequences_dir : Path
        Destination directory; ``sequences.pt`` is written here.

    Returns
    -------
    dict
        ``sequences_path``, ``sequences_dir``, and ``sample_count``.
    """
    import torch

    _ensure_on_path(STAGE2_SRC)
    cfg     = _load_stage2_config()
    scalers = _load_scalers(cfg)

    sequences_dir.mkdir(parents=True, exist_ok=True)

    print("[stage2] Building input sequences …", flush=True)
    samples = _build_samples(stage1_dir, cfg, scalers)
    if not samples:
        raise ValueError(f"No samples could be built from {stage1_dir}")
    print(f"[stage2] Built {len(samples)} samples.", flush=True)

    # IDW fill – propagate boundary edge values into the interior
    try:
        from f_data_processing import apply_idw_fill_to_boundary_sequences  # type: ignore
        bnd_ch_start = int(cfg.PREVIOUS_INPUT_STEPS) * len(cfg.WIND_VARS)
        bnd_ch_count = int(cfg.PREVIOUS_BOUNDARY_STEPS) * len(cfg.BOUNDARY_VARS)
        samples = apply_idw_fill_to_boundary_sequences(
            samples,
            boundary_channel_start=bnd_ch_start,
            boundary_channel_count=bnd_ch_count,
            power=2.0,
        )
        print("[stage2] IDW fill applied to boundary channels.", flush=True)
    except Exception as exc:
        print(f"[stage2] Warning: IDW fill skipped ({exc}).", flush=True)

    sequences_path = sequences_dir / "sequences.pt"
    if sequences_path.exists():
        sequences_path.unlink()

    torch.save(
        {
            "train_sequences": [],
            "val_sequences":   [],
            "test_sequences":  samples,
            "meta": {
                "pipeline":                "stage2.py",
                "input_only":              True,
                "scaled":                  True,
                "scaler_path":             str(cfg.SCALER_PATH),
                "previous_input_steps":    int(cfg.PREVIOUS_INPUT_STEPS),
                "previous_boundary_steps": int(cfg.PREVIOUS_BOUNDARY_STEPS),
                "sample_count":            len(samples),
                "stage1_dir":              str(stage1_dir),
            },
        },
        sequences_path,
    )
    print(f"[stage2] Sequences saved → {sequences_path}", flush=True)

    summary = {
        "sample_count": len(samples),
        "train_count":  0,
        "val_count":    0,
        "test_count":   len(samples),
        "stage1_dir":   str(stage1_dir),
    }
    (sequences_dir / "sequence_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    print("\n[stage2] Stage 2 complete.", flush=True)
    return {
        "sequences_path": str(sequences_path),
        "sequences_dir":  str(sequences_dir),
        "sample_count":   len(samples),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Stage-2 Surrogate Preprocessing: builds input-only sequences "
            "from Stage-1 preprocessed NetCDF files and saves sequences.pt."
        )
    )
    p.add_argument(
        "--stage1-dir",
        type=str,
        default=None,
        help=(
            "Directory containing the three Stage-1 preprocessed NetCDF files. "
            "Auto-detected from the most recent user_case/run*/stage1/ if omitted."
        ),
    )
    p.add_argument(
        "--sequences-dir",
        type=str,
        default=None,
        help=(
            "Where to write sequences.pt and sequence_summary.json. "
            "Default: user_case/run<timestamp>_stage2/stage2/"
        ),
    )
    return p.parse_args()


def main() -> None:
    _ensure_runtime_library_path()
    args = _parse_args()

    if args.stage1_dir:
        stage1_dir = Path(args.stage1_dir).resolve()
    else:
        stage1_dir = _find_latest_stage1()
        print(f"[stage2] Auto-detected Stage-1 output: {stage1_dir}", flush=True)

    if args.sequences_dir:
        sequences_dir = Path(args.sequences_dir).resolve()
    else:
        run_id        = datetime.now().strftime("%Y%m%d_%H%M%S")
        sequences_dir = USER_CASE_DIR / f"run{run_id}_stage2" / "stage2"

    print(f"\n[stage2] stage1_dir    : {stage1_dir}")
    print(f"[stage2] sequences_dir : {sequences_dir}\n")

    result = run_stage2(
        stage1_dir=stage1_dir,
        sequences_dir=sequences_dir,
    )

    print("\n" + "=" * 72)
    print("[stage2] Done!")
    print(f"  Sequences : {result['sequences_path']}")
    print(f"  Samples   : {result['sample_count']}")
    print("=" * 72)


if __name__ == "__main__":
    main()
