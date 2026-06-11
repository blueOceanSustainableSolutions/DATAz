#!/usr/bin/env python3
"""main2.py – Full 3-stage pipeline for the SWAN surrogate user_case.

Stages:
  1  General preprocessing  – reads 0_raw_data/, produces preprocessed NetCDF
  2  Surrogate preprocessing – reads stage-1 NetCDF, produces sequences.pt
  3  Inference              – reads sequences.pt + model checkpoint, produces
                              prediction NetCDF and hourly PNG frames

Each stage can also be run standalone by providing its input path explicitly:
  --raw-data-dir   <path>   Stage 1: where to find raw .nc files   (default: 0_raw_data/)
  --stage1-dir     <path>   Stage 2: where stage-1 NetCDF files live
  --sequences-path <path>   Stage 3: where sequences.pt lives

When running stage123 (default), all paths are wired automatically.

Usage examples
--------------
Full pipeline, date 2025-09-01 (default):
    python main2.py --execute --stage stage123

Stage 1 only, custom raw-data location:
    python main2.py --execute --stage stage1 --raw-data-dir /my/raw

Stage 2 only, pointing at existing stage-1 output:
    python main2.py --execute --stage stage2 --stage1-dir /path/to/stage1_output

Stage 3 only, pointing at existing sequences:
    python main2.py --execute --stage stage3 --sequences-path /path/to/sequences.pt \\
        --stage1-dir /path/to/stage1_output

Dry-run (just print resolved config):
    python main2.py --dry-run
"""
from __future__ import annotations

import argparse
import contextlib
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Thread / process limit (before any heavy import)
# ---------------------------------------------------------------------------
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")


def _ensure_runtime_library_path() -> None:
    """Re-exec with the conda C++ runtime first in LD_LIBRARY_PATH.

    netCDF4 (and several other native extensions) require a newer libstdc++
    than the system provides.  Prepending the conda env's lib/ directory
    before the first import fixes the GLIBCXX_3.4.30 not-found error.
    """
    if os.environ.get("MAIN2_REEXECED") == "1":
        return
    conda_prefix = os.environ.get("CONDA_PREFIX") or sys.prefix
    conda_lib = str(Path(conda_prefix) / "lib")
    ld = os.environ.get("LD_LIBRARY_PATH", "")
    parts = [p for p in ld.split(":") if p]
    if not parts or parts[0] != conda_lib:
        new_parts = [conda_lib] + [p for p in parts if p != conda_lib]
        os.environ["LD_LIBRARY_PATH"] = ":".join(new_parts)
        os.environ["MAIN2_REEXECED"] = "1"
        os.execvpe(sys.executable, [sys.executable] + sys.argv, os.environ)

# ---------------------------------------------------------------------------
# Directory constants
# ---------------------------------------------------------------------------
USER_CASE_DIR = Path(__file__).resolve().parent
REPO_ROOT     = USER_CASE_DIR.parent
STAGE1_SRC    = REPO_ROOT / "src" / "1_General_Preprocessing"
STAGE2_SRC    = REPO_ROOT / "src" / "2_Surrogate_Preprocessing"
STAGE3_SRC    = REPO_ROOT / "src" / "3_Surrogate_Training"

# Default raw-data and model checkpoint
DEFAULT_RAW_DATA_DIR = USER_CASE_DIR / "0_raw_data"
DEFAULT_CHECKPOINT   = REPO_ROOT / "models" / "physics_unet2_All_20260423_221744.pt"

# Stage-3 defaults
_S3_BATCH_SIZE = 8
_S3_MAX_FRAMES = 24


# ===========================================================================
# Utility helpers
# ===========================================================================

def _fmt_dur(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    m, s = divmod(seconds, 60)
    if m < 60:
        return f"{int(m)}m {s:04.1f}s"
    h, m = divmod(int(m), 60)
    return f"{h}h {m:02d}m {s:04.1f}s"


def _section(title: str) -> None:
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


class _Tee:
    def __init__(self, *streams):
        self._streams = streams
    def write(self, text):
        for s in self._streams:
            s.write(text)
            s.flush()
    def flush(self):
        for s in self._streams:
            s.flush()


@contextlib.contextmanager
def _open_log(log_path: Path):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as fh:
        yield fh


def _ensure_on_path(directory: Path) -> None:
    s = str(directory)
    if s not in sys.path:
        sys.path.insert(0, s)


# ===========================================================================
# Stage 1 & 2 – delegate to dedicated modules
# ===========================================================================
# Import the core functions from stage1.py and stage2.py so that main2.py
# acts purely as the orchestrator without duplicating any stage logic.
from stage1 import run_stage1   # noqa: E402
from stage2 import run_stage2   # noqa: E402



def _load_stage3_runtime():
    """Put Stage-3 and Stage-2 source dirs on sys.path and import runtime."""
    _ensure_on_path(STAGE2_SRC)
    _ensure_on_path(STAGE3_SRC)

    # Pop stale cached modules so we get the versions from the correct dirs
    for mod in (
        "config", "dataloader", "train_stage", "loss_functions",
        "models_architecture", "models_architecture.factory",
        "models_architecture.common_blocks", "models_architecture.conv_lstm",
        "models_architecture.ctp_model", "models_architecture.physics_unet2",
        "models_architecture.spatial_cnn", "models_architecture.unet",
    ):
        sys.modules.pop(mod, None)

    import config as s3_cfg                               # STAGE3_SRC/config.py
    from dataloader import TensorDataset                  # STAGE3_SRC/dataloader.py
    from models_architecture.factory import create_model  # noqa: PLC0415
    from train_stage import load_model_checkpoint         # noqa: PLC0415
    return s3_cfg, TensorDataset, create_model, load_model_checkpoint


def _load_spatial_reference(stage1_dir: Path) -> dict:
    import numpy as np
    import xarray as xr

    wind_path  = stage1_dir / "wind_inputs_preprocessed_128x128.nc"
    bathy_path = stage1_dir / "bathymetry_preprocessed_128x128.nc"
    if not wind_path.exists():
        raise FileNotFoundError(f"Wind file not found: {wind_path}")

    with xr.open_dataset(str(wind_path)) as ds:
        lat_name = "lat" if "lat" in ds.coords else "latitude"
        lon_name = "lon" if "lon" in ds.coords else "longitude"
        lat = ds[lat_name].values.astype(np.float64)
        lon = ds[lon_name].values.astype(np.float64)

    elevation = None
    if bathy_path.exists():
        with xr.open_dataset(str(bathy_path)) as ds:
            if "elevation" in ds.data_vars:
                elevation = ds["elevation"].values.astype(np.float64)

    return {"lat": lat, "lon": lon, "elevation": elevation}


def _fmt_ts(value: str) -> str:
    t = str(value).replace("T", " ").replace("Z", "")
    if "." in t:
        t = t[: t.index(".")]
    return t[:16] if len(t) >= 16 else t


_VAR_META = {
    "HSig":     {"title": "Predicted Significant Wave Height",           "unit": "m",  "cmap": "viridis", "vmin": 0.0,  "vmax": None, "sym": False},
    "PDIR_sin": {"title": "Predicted Peak Direction\nSine Component",   "unit": "",   "cmap": "viridis", "vmin": -1.0, "vmax":  1.0, "sym": True},
    "PDIR_cos": {"title": "Predicted Peak Direction\nCosine Component", "unit": "",   "cmap": "viridis", "vmin": -1.0, "vmax":  1.0, "sym": True},
}


def _save_frame(idx: int, ts: str, data: dict, lat, lon, out_dir: Path) -> Path:
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plot_vars = ["HSig", "PDIR_sin", "PDIR_cos"]
    fig, axes = plt.subplots(1, 3, figsize=(18, 5.5), facecolor="white",
                              constrained_layout=True)
    for ax, var in zip(axes, plot_vars):
        meta = _VAR_META[var]
        arr  = data.get(var)
        if arr is None:
            ax.axis("off")
            continue
        finite = arr[np.isfinite(arr)]
        if finite.size == 0:
            vmin, vmax = 0.0, 1.0
        elif meta["vmin"] is not None and meta["vmax"] is not None:
            vmin, vmax = meta["vmin"], meta["vmax"]
        elif meta["sym"]:
            absmax = max(abs(float(finite.min())), abs(float(finite.max()))) or 1.0
            vmin, vmax = -absmax, absmax
        else:
            vmin = meta["vmin"] if meta["vmin"] is not None else float(finite.min())
            vmax = meta["vmax"] if meta["vmax"] is not None else float(finite.max())

        extent = (
            [float(lon.min()), float(lon.max()), float(lat.min()), float(lat.max())]
            if lat.ndim == 1 and lon.ndim == 1 else None
        )
        im = ax.imshow(arr, origin="lower", aspect="auto", extent=extent,
                       cmap=meta["cmap"], vmin=vmin, vmax=vmax)
        cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        if meta["unit"]:
            cb.set_label(meta["unit"], fontsize=10)
        cb.ax.tick_params(labelsize=9)
        ax.set_title(meta["title"], fontsize=11, fontweight="bold", pad=6)
        ax.set_xlabel("Longitude", fontsize=10)
        ax.set_ylabel("Latitude",  fontsize=10)
        if lat.ndim == 1 and lon.ndim == 1:
            ax.set_xticks(np.linspace(lon.min(), lon.max(), 5))
            ax.set_yticks(np.linspace(lat.min(), lat.max(), 5))
            ax.set_xticklabels([f"{v:.1f}" for v in np.linspace(lon.min(), lon.max(), 5)], fontsize=8)
            ax.set_yticklabels([f"{v:.1f}" for v in np.linspace(lat.min(), lat.max(), 5)], fontsize=8)
        ax.tick_params(direction="in", length=4, width=0.8)

    fig.suptitle(f"SWAN Surrogate – {_fmt_ts(ts)}", fontsize=14,
                 fontweight="bold", y=1.03)
    out_path = out_dir / f"pred_frame_{idx:03d}.png"
    fig.savefig(str(out_path), dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out_path


def run_stage3(
    sequences_path: Path,
    stage1_dir: Path,
    output_dir: Path,
    checkpoint: Path = DEFAULT_CHECKPOINT,
    date: str | None = "2025-09-01",
    max_frames: int = _S3_MAX_FRAMES,
    batch_size: int = _S3_BATCH_SIZE,
    device: str = "cpu",
) -> dict:
    """Run inference with the surrogate model.

    Parameters
    ----------
    sequences_path : Path
        Path to ``sequences.pt`` produced by Stage 2.
    stage1_dir : Path
        Stage-1 output dir (used for lat/lon/elevation spatial reference).
    output_dir : Path
        Destination for the prediction NetCDF and PNG frames.
    checkpoint : Path
        Model checkpoint (.pt file).
    date : str | None
        Filter sequences to this ``YYYY-MM-DD`` date.  ``None`` uses all.
    max_frames : int
        Maximum PNG frames to generate.
    batch_size : int
        Inference batch size.
    device : str
        ``"cpu"`` or ``"cuda"``.
    """
    import gc
    import numpy as np
    import pandas as pd
    import torch
    import xarray as xr

    _section("STAGE 3 – Inference")

    s3_cfg, TensorDataset, create_model, load_model_checkpoint = _load_stage3_runtime()
    # Also need scale_data from STAGE2_SRC (already on path)
    from f_data_processing import import_scale  # type: ignore  # noqa: PLC0415

    # ---------------------------------------------------------------- samples
    print(f"[stage3] Loading sequences from: {sequences_path}", flush=True)
    payload = torch.load(str(sequences_path), map_location="cpu", mmap=True)

    if date:
        print(f"[stage3] Filtering to date {date} …", flush=True)
        matched: list = []
        for key in ("train_sequences", "val_sequences", "test_sequences"):
            split_data = payload.get(key) or []
            for s in split_data:
                ts = s[-1] if len(s) > 1 else None
                if ts is None:
                    continue
                try:
                    if pd.to_datetime(str(ts)).strftime("%Y-%m-%d") == date:
                        matched.append(
                            tuple(x.clone() if isinstance(x, torch.Tensor) else x for x in s)
                        )
                except Exception:
                    pass
        del payload
        gc.collect()
        samples = matched
        print(f"[stage3] {len(samples)} samples match {date}.", flush=True)
        if not samples:
            raise ValueError(f"No samples found for date '{date}' in {sequences_path}")
        try:
            samples.sort(key=lambda s: pd.to_datetime(str(s[-1])))
        except Exception:
            pass
    else:
        raw = payload.get("test_sequences") or []
        samples = list(raw)
        del payload
        gc.collect()
        print(f"[stage3] Using all {len(samples)} test samples.", flush=True)

    # NaN → 0
    cleaned: list = []
    for s in samples:
        t = s[0].clone()
        if torch.isnan(t).any():
            t = torch.nan_to_num(t, nan=0.0)
        cleaned.append((t, *s[1:]))
    samples = cleaned

    # ----------------------------------------------------------------- model
    if device == "cuda" and not torch.cuda.is_available():
        print("[stage3] CUDA unavailable, using CPU.", flush=True)
        device = "cpu"

    n_channels = int(samples[0][0].shape[0])
    model_cfg  = dict(s3_cfg.MODEL_CONFIG)
    model_cfg["input_channels"] = n_channels
    print(f"[stage3] Building {s3_cfg.MODEL_ARCHITECTURE} ({n_channels} ch) …", flush=True)
    model = create_model(s3_cfg.MODEL_ARCHITECTURE, model_cfg)

    if not checkpoint.exists():
        # Fall back to any available checkpoint in the models dir
        candidates = sorted(s3_cfg.MODEL_DIR.glob("physics_unet2*.pt"),
                            key=lambda p: p.stat().st_mtime)
        if not candidates:
            raise FileNotFoundError(f"No checkpoint found at {checkpoint} or in {s3_cfg.MODEL_DIR}")
        checkpoint = candidates[-1]
        print(f"[stage3] Using fallback checkpoint: {checkpoint}", flush=True)

    print(f"[stage3] Loading checkpoint: {checkpoint}", flush=True)
    load_model_checkpoint(model, str(checkpoint), device=device)
    model.to(device)
    model.eval()

    # --------------------------------------------------------------- inference
    loader = torch.utils.data.DataLoader(
        TensorDataset(samples), batch_size=batch_size, shuffle=False
    )
    pred_batches: list[torch.Tensor] = []
    time_labels: list[str] = []
    print(f"[stage3] Running inference over {len(samples)} samples …", flush=True)
    with torch.no_grad():
        for bi, batch in enumerate(loader, start=1):
            if bi == 1 or bi % 5 == 0 or bi == len(loader):
                print(f"  batch {bi}/{len(loader)}", flush=True)
            if len(batch) == 3:
                inputs, _, batch_times = batch
            elif len(batch) == 2:
                inputs, batch_times = batch
            else:
                (inputs,) = batch
                batch_times = [None] * len(inputs)
            preds = model(inputs.to(device, non_blocking=True))
            pred_batches.append(preds.detach().cpu())
            time_labels.extend(str(t) for t in batch_times)

    y_pred = torch.cat(pred_batches, dim=0)
    print(f"[stage3] Inference done. Output shape: {y_pred.shape}", flush=True)

    # ----------------------------------------------------------- inverse scale
    print("[stage3] Inverse-scaling …", flush=True)
    scalers   = import_scale(s3_cfg.SCALER_PATH)
    pred_np   = y_pred.detach().cpu().numpy().astype(np.float64, copy=True)
    for ch, var in enumerate(s3_cfg.TARGET_VARS[: pred_np.shape[1]]):
        if var.endswith("_sin") or var.endswith("_cos"):
            continue
        scaler = scalers.get(var) or scalers.get(var.rsplit("_", 1)[0])
        if scaler is None:
            continue
        flat = pred_np[:, ch].reshape(-1)
        mask = np.isfinite(flat)
        if mask.any():
            flat[mask] = scaler.inverse_transform(flat[mask].reshape(-1, 1)).reshape(-1)
        pred_np[:, ch] = flat.reshape(pred_np[:, ch].shape)
    pred_np = pred_np.astype(np.float32)

    # ---------------------------------------------------------- spatial ref
    spatial = _load_spatial_reference(stage1_dir)
    lat, lon = spatial["lat"], spatial["lon"]

    # ------------------------------------------------------------ save NetCDF
    output_dir.mkdir(parents=True, exist_ok=True)
    parsed = pd.to_datetime(time_labels, errors="coerce")
    time_coord = (
        parsed.to_numpy() if not parsed.isna().all()
        else np.array(time_labels, dtype="U")
    )
    data_vars: dict = {}
    for ch, var in enumerate(s3_cfg.TARGET_VARS[: pred_np.shape[1]]):
        data_vars[f"{var}_pred"] = (("time", "lat", "lon"), pred_np[:, ch])
    if spatial.get("elevation") is not None:
        data_vars["elevation"] = (("lat", "lon"), spatial["elevation"])
    ds_out = xr.Dataset(
        data_vars=data_vars,
        coords={"time": time_coord, "lat": lat, "lon": lon},
        attrs={
            "model_architecture": s3_cfg.MODEL_ARCHITECTURE,
            "checkpoint": str(checkpoint),
            "sequences_path": str(sequences_path),
        },
    )
    nc_path = output_dir / "stage3_predictions.nc"
    ds_out.to_netcdf(str(nc_path))
    print(f"[stage3] NetCDF saved → {nc_path}", flush=True)

    # ------------------------------------------------------------ PNG frames
    n_time = pred_np.shape[0]
    n_frames = min(max_frames, n_time)
    if n_frames >= n_time:
        frame_indices = list(range(n_time))
    else:
        frame_indices = list(range(n_frames))
    frames_dir = output_dir / "frames"
    frames_dir.mkdir(exist_ok=True)
    for old in frames_dir.glob("pred_frame_*.png"):
        old.unlink()

    print(f"[stage3] Generating {len(frame_indices)} frames …", flush=True)
    saved: list[Path] = []
    for pos, t_idx in enumerate(frame_indices):
        data_dict = {
            var: pred_np[t_idx, ch]
            for ch, var in enumerate(s3_cfg.TARGET_VARS[: pred_np.shape[1]])
            if var in _VAR_META
        }
        out = _save_frame(pos, time_labels[t_idx], data_dict, lat, lon, frames_dir)
        saved.append(out)
        print(f"  [{pos + 1:02d}/{len(frame_indices)}] {out.name}  {_fmt_ts(time_labels[t_idx])}", flush=True)

    print("\n" + "=" * 72)
    print("[stage3] Done!")
    print(f"  NetCDF : {nc_path}")
    print(f"  Frames : {frames_dir}  ({len(saved)} images)")
    print("=" * 72)

    return {
        "netcdf":      str(nc_path),
        "frames_dir":  str(frames_dir),
        "frame_count": len(saved),
        "sample_count": n_time,
    }


# ===========================================================================
# Path resolvers for standalone stage execution
# ===========================================================================

def _find_latest_stage1(run_root: Path) -> Path:
    """Find most recent stage1 output under user_case/run*."""
    candidates = sorted(
        USER_CASE_DIR.glob("run*/stage1/wind_inputs_preprocessed_128x128.nc"),
        key=lambda p: p.stat().st_mtime, reverse=True,
    )
    if candidates:
        return candidates[0].parent
    raise FileNotFoundError(
        "No Stage-1 output found under user_case/. "
        "Run with --stage stage1 or --stage stage123 first."
    )


def _find_latest_sequences(run_root: Path) -> Path:
    """Find most recent sequences.pt under user_case/run*."""
    candidates = sorted(
        USER_CASE_DIR.glob("run*/stage2/sequences.pt"),
        key=lambda p: p.stat().st_mtime, reverse=True,
    )
    if candidates:
        return candidates[0]
    raise FileNotFoundError(
        "No sequences.pt found under user_case/. "
        "Run with --stage stage2 or --stage stage123 first."
    )


# ===========================================================================
# CLI
# ===========================================================================

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="main2.py – full SWAN surrogate pipeline (stages 1→2→3).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--stage",
        choices=["stage1", "stage2", "stage3", "stage123"],
        default="stage123",
        help="Which stage(s) to run (default: stage123).",
    )
    p.add_argument(
        "--execute", action="store_true",
        help="Actually run the pipeline (dry-run if omitted).",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Print resolved configuration and exit.",
    )

    # Stage-1 inputs
    p.add_argument(
        "--raw-data-dir", type=str, default=str(DEFAULT_RAW_DATA_DIR),
        help=f"Directory with raw .nc files for Stage 1 (default: {DEFAULT_RAW_DATA_DIR}).",
    )
    p.add_argument(
        "--date", type=str, default="2025-09-01",
        help="Date (YYYY-MM-DD) to extract from the raw data (default: 2025-09-01).",
    )
    p.add_argument(
        "--duration-hours", type=int, default=24,
        help="Number of hours to extract starting from --date (default: 24).",
    )

    # Stage-2/3 explicit overrides
    p.add_argument(
        "--stage1-dir", type=str, default=None,
        help="Stage-1 output dir to use for Stage 2/3 (auto-detected if omitted).",
    )
    p.add_argument(
        "--sequences-path", type=str, default=None,
        help="Explicit path to sequences.pt for Stage 3 (auto-detected if omitted).",
    )
    p.add_argument(
        "--checkpoint", type=str, default=str(DEFAULT_CHECKPOINT),
        help=f"Model checkpoint for Stage 3 (default: {DEFAULT_CHECKPOINT}).",
    )

    # Stage-3 options
    p.add_argument("--max-frames",  type=int, default=_S3_MAX_FRAMES,  help="Max PNG frames (default: 24).")
    p.add_argument("--batch-size",  type=int, default=_S3_BATCH_SIZE,  help="Inference batch size (default: 8).")
    p.add_argument("--device",      type=str, default="cpu",            help="Device: cpu or cuda (default: cpu).")
    p.add_argument(
        "--no-date-filter", action="store_true",
        help="Disable the date filter in Stage 3 (use all sequences).",
    )
    return p.parse_args()


def main() -> None:
    _ensure_runtime_library_path()
    args = _parse_args()

    # ---------------------------------------------------------------- run dir
    run_id   = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_root = USER_CASE_DIR / f"run{run_id}_{args.stage}"

    # Resolve stage-1 output dir
    if args.stage1_dir:
        stage1_dir = Path(args.stage1_dir).resolve()
    elif args.stage in {"stage1", "stage123"}:
        stage1_dir = run_root / "stage1"   # will be created by stage1
    else:
        # standalone stage2 or stage3: auto-detect
        stage1_dir = _find_latest_stage1(run_root)

    # Resolve sequences dir / path
    if args.sequences_path:
        sequences_path = Path(args.sequences_path).resolve()
        sequences_dir  = sequences_path.parent
    elif args.stage in {"stage2", "stage123"}:
        sequences_dir  = run_root / "stage2"
        sequences_path = sequences_dir / "sequences.pt"
    else:
        # standalone stage3: auto-detect
        sequences_path = _find_latest_sequences(run_root)
        sequences_dir  = sequences_path.parent

    stage3_dir  = run_root / "stage3"
    checkpoint  = Path(args.checkpoint).resolve()
    if args.stage == "stage3":
        date_filter = None if args.no_date_filter else args.date
    else:
        # If sequences were just built by stage1/2, they are already perfectly 
        # sliced to the requested duration. Don't discard them with a daily filter.
        date_filter = None

    # ------------------------------------------------------------------ print
    _section("main2.py – SWAN Surrogate Pipeline")
    print(f"  stage(s)          : {args.stage}")
    print(f"  date              : {args.date}")
    print(f"  duration_hours    : {args.duration_hours}")
    print(f"  run_root          : {run_root}")
    print(f"  raw_data_dir      : {args.raw_data_dir}")
    print(f"  stage1_dir        : {stage1_dir}")
    print(f"  sequences_path    : {sequences_path}")
    print(f"  checkpoint        : {checkpoint}")
    print(f"  stage3_output_dir : {stage3_dir}")
    print(f"  date_filter (s3)  : {date_filter}")
    print(f"  max_frames        : {args.max_frames}")
    print(f"  batch_size        : {args.batch_size}")
    print(f"  device            : {args.device}")

    if args.dry_run or not args.execute:
        print("\n[main2] Dry-run mode – use --execute to actually run the pipeline.")
        return

    # ---------------------------------------------------------------- run dir
    run_root.mkdir(parents=True, exist_ok=True)
    log_path = run_root / f"run{run_id}_{args.stage}.log"

    with _open_log(log_path) as log_fh:
        with (contextlib.redirect_stdout(_Tee(sys.stdout, log_fh)),
              contextlib.redirect_stderr(_Tee(sys.stderr, log_fh))):

            t_total = time.perf_counter()
            durations: dict[str, float] = {}

            # -------------------------------------------- stage 1
            if args.stage in {"stage1", "stage123"}:
                t0 = time.perf_counter()
                run_stage1(
                    raw_data_dir=Path(args.raw_data_dir),
                    output_dir=stage1_dir,
                    date=args.date,
                    duration_hours=args.duration_hours,
                )
                durations["stage1"] = time.perf_counter() - t0
                print(f"\n[main2] Stage 1 finished in {_fmt_dur(durations['stage1'])}.")

            # -------------------------------------------- stage 2
            if args.stage in {"stage2", "stage123"}:
                t0 = time.perf_counter()
                run_stage2(
                    stage1_dir=stage1_dir,
                    sequences_dir=sequences_dir,
                )
                durations["stage2"] = time.perf_counter() - t0
                print(f"\n[main2] Stage 2 finished in {_fmt_dur(durations['stage2'])}.")

            # -------------------------------------------- stage 3
            if args.stage in {"stage3", "stage123"}:
                t0 = time.perf_counter()
                run_stage3(
                    sequences_path=sequences_path,
                    stage1_dir=stage1_dir,
                    output_dir=stage3_dir,
                    checkpoint=checkpoint,
                    date=date_filter,
                    max_frames=args.max_frames,
                    batch_size=args.batch_size,
                    device=args.device,
                )
                durations["stage3"] = time.perf_counter() - t0
                print(f"\n[main2] Stage 3 finished in {_fmt_dur(durations['stage3'])}.")

            # ------------------------------------------- summary
            _section("Timing Summary")
            for name, dur in durations.items():
                print(f"  {name}: {_fmt_dur(dur)}")
            print(f"  total: {_fmt_dur(time.perf_counter() - t_total)}")
            print(f"\n[main2] Run artefacts → {run_root}")
            print(f"[main2] Log            → {log_path}")


# ---------------------------------------------------------------------------
# When imported by stage3.py (legacy shim – provides the three constants it
# expects: SEQUENCES_PATH, STAGE1_OUTPUT_DIR, CHECKPOINT_PATH)
# ---------------------------------------------------------------------------
if __name__ != "__main__":
    def _find_latest_seq() -> Path:
        candidates = sorted(
            USER_CASE_DIR.glob("run*/stage2/sequences.pt"),
            key=lambda p: p.stat().st_mtime, reverse=True,
        )
        if candidates:
            return candidates[0]
        direct = USER_CASE_DIR / "2_sequences" / "sequences.pt"
        if direct.exists():
            return direct
        raise FileNotFoundError(
            "No sequences.pt found under user_case/. "
            "Run main2.py --stage stage2 --execute first."
        )

    def _find_latest_s1() -> Path:
        candidates = sorted(
            USER_CASE_DIR.glob("run*/stage1/wind_inputs_preprocessed_128x128.nc"),
            key=lambda p: p.stat().st_mtime, reverse=True,
        )
        if candidates:
            return candidates[0].parent
        legacy = USER_CASE_DIR / "1_preprocessed_data"
        if (legacy / "wind_inputs_preprocessed_128x128.nc").exists():
            return legacy
        raise FileNotFoundError(
            "No Stage-1 output found under user_case/. "
            "Run main2.py --stage stage1 --execute first."
        )

    try:
        SEQUENCES_PATH:   Path = _find_latest_seq()
        STAGE1_OUTPUT_DIR: Path = _find_latest_s1()
    except FileNotFoundError:
        SEQUENCES_PATH    = Path("/dev/null")
        STAGE1_OUTPUT_DIR = Path("/dev/null")

    CHECKPOINT_PATH: Path = DEFAULT_CHECKPOINT

    STAGE2_DIR = STAGE2_SRC
    STAGE3_DIR = STAGE3_SRC


if __name__ == "__main__":
    main()
