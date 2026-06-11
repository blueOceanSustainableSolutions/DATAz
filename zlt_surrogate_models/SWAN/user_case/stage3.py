#!/usr/bin/env python3
"""stage3.py – Prediction-only Stage-3 for the SWAN surrogate user_case pipeline.

Reads the sequence path from main2.py, filters by date, runs inference, and
saves one PNG per hour (up to --max-frames) each showing three side-by-side
spatial maps: HSig | PDIR_sin | PDIR_cos.

Usage (from user_case dir, with swan_surrogate_env active):
    python stage3.py \\
        --sequences-path /path/to/sequences.pt \\
        --date 2025-09-01 \\
        --max-frames 24 \\
        --output-dir stage3_predictions
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

# ---------------------------------------------------------------------------
# sys.path setup
# Each sys.path.insert(0, x) pushes x to the front, so the LAST call wins.
# Desired priority (highest first): USER_CASE_DIR > TRAIN_DIR > PREPROCESS_DIR
# Therefore insert in REVERSE order: PREPROCESS_DIR first, USER_CASE_DIR last.
# ---------------------------------------------------------------------------
USER_CASE_DIR  = Path(__file__).resolve().parent
PROJECT_ROOT   = USER_CASE_DIR.parent
PREPROCESS_DIR = PROJECT_ROOT / "src" / "2_Surrogate_Preprocessing"
TRAIN_DIR      = PROJECT_ROOT / "src" / "3_Surrogate_Training"

for _p in (str(PREPROCESS_DIR), str(TRAIN_DIR), str(USER_CASE_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
# Result: USER_CASE_DIR=0, TRAIN_DIR=1, PREPROCESS_DIR=2
# → `from dataloader import TensorDataset` finds TRAIN_DIR/dataloader.py ✓

# ---------------------------------------------------------------------------
# Imports from TRAIN_DIR (must come after sys.path setup)
# ---------------------------------------------------------------------------
from config import (                           # TRAIN_DIR/config.py  # noqa: E402
    MODEL_ARCHITECTURE,
    MODEL_CONFIG,
    MODEL_DIR,
    SCALER_PATH,
    TARGET_VARS,
)
from dataloader import TensorDataset           # TRAIN_DIR/dataloader.py  # noqa: E402
from models_architecture.factory import create_model  # noqa: E402
from f_data_processing import import_scale            # PREPROCESS_DIR/scale_data.py  # noqa: E402
from train_stage import load_model_checkpoint  # TRAIN_DIR/train_stage.py  # noqa: E402

import numpy as np
import pandas as pd
import torch
import xarray as xr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ---------------------------------------------------------------------------
# Import sequence location + checkpoint from main2.py
# ---------------------------------------------------------------------------
sys.modules.pop("main2", None)
from main2 import (  # noqa: E402
    SEQUENCES_PATH   as _DEFAULT_SEQUENCES_PATH,
    STAGE1_OUTPUT_DIR as _DEFAULT_STAGE1_DIR,
    CHECKPOINT_PATH  as _DEFAULT_CHECKPOINT,
)

print(f"[stage3] default sequences : {_DEFAULT_SEQUENCES_PATH}", flush=True)
print(f"[stage3] default stage1 dir: {_DEFAULT_STAGE1_DIR}",    flush=True)
print(f"[stage3] default checkpoint: {_DEFAULT_CHECKPOINT}",    flush=True)

# ---------------------------------------------------------------------------
# Visual metadata for the three output variables
# ---------------------------------------------------------------------------
_VAR_META = {
    "HSig": {
        "title": "Predicted Significant Wave Height",
        "unit": "m",
        "cmap": "viridis",
        "symmetric": False,
        "vmin_fixed": 0.0,          # HSig is always non-negative
        "vmax_fixed": None,
    },
    "PDIR_sin": {
        "title": "Predicted Peak Wave Direction\nSine Component",
        "unit": "",
        "cmap": "viridis",
        "symmetric": True,
        "vmin_fixed": -1.0,
        "vmax_fixed":  1.0,
    },
    "PDIR_cos": {
        "title": "Predicted Peak Wave Direction\nCosine Component",
        "unit": "",
        "cmap": "viridis",
        "symmetric": True,
        "vmin_fixed": -1.0,
        "vmax_fixed":  1.0,
    },
}

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Stage-3 prediction-only pipeline (HSig, PDIR_sin, PDIR_cos)."
    )
    p.add_argument("--sequences-path", type=str, default=str(_DEFAULT_SEQUENCES_PATH),
                   help="Path to sequences.pt produced by Stage 2.")
    p.add_argument("--checkpoint",     type=str, default=str(_DEFAULT_CHECKPOINT),
                   help="Model checkpoint (.pt) to load.")
    p.add_argument("--stage1-dir",     type=str, default=str(_DEFAULT_STAGE1_DIR),
                   help="Stage-1 output dir containing preprocessed NetCDF files.")
    p.add_argument("--output-dir",     type=str,
                   default=str(USER_CASE_DIR / "stage3_predictions"),
                   help="Output directory for frames and NetCDF.")
    p.add_argument("--date",           type=str, default=None,
                   help="Filter to a specific date YYYY-MM-DD (searches all splits).")
    p.add_argument("--split",          type=str, default="test",
                   help="Split to use when --date is not set: train/val/test.")
    p.add_argument("--max-frames",     type=int, default=24,
                   help="Maximum PNG frames to generate (default: 24).")
    p.add_argument("--batch-size",     type=int, default=8)
    p.add_argument("--device",         type=str, default="cpu")
    return p.parse_args()


import gc

def _load_split(sequences_path: Path, split: str) -> list:
    """Load one named split with memory-mapped tensors."""
    payload = torch.load(str(sequences_path), map_location="cpu", mmap=True)
    key = f"{split}_sequences"
    data = payload.get(key)
    if data is None:
        available = [k for k in payload if k.endswith("_sequences")]
        raise KeyError(f"Split '{split}' not found in {sequences_path}. Available: {available}")
    return list(data)


def _load_all_splits_filtered(sequences_path: Path, date_str: str) -> list:
    """Load each split with mmap, filter immediately, free before loading next.

    This avoids loading the full dataset into RAM — only the matching
    samples for `date_str` are ever fully materialised.
    """
    matched: list = []
    # load the payload once with mmap so tensors are memory-mapped (not copied)
    payload = torch.load(str(sequences_path), map_location="cpu", mmap=True)
    for key in ("train_sequences", "val_sequences", "test_sequences"):
        split_data = payload.get(key)
        if not split_data:
            continue
        n_before = len(matched)
        for s in split_data:
            ts = s[-1] if len(s) > 1 else None
            if ts is None:
                continue
            try:
                if pd.to_datetime(str(ts)).strftime("%Y-%m-%d") == date_str:
                    # Clone now so the tensor is materialised and detached from mmap
                    matched.append(tuple(x.clone() if isinstance(x, torch.Tensor) else x for x in s))
            except Exception:
                pass
        print(f"[stage3]   {key}: {len(matched) - n_before} samples matched", flush=True)
    del payload
    gc.collect()
    return matched



def _filter_by_date(samples: list, date_str: str) -> list:
    out = []
    for s in samples:
        ts = s[-1] if len(s) > 1 else None
        if ts is None:
            continue
        try:
            if pd.to_datetime(str(ts)).strftime("%Y-%m-%d") == date_str:
                out.append(s)
        except Exception:
            pass
    return out


def _clean_nans(samples: list) -> list:
    cleaned = []
    for s in samples:
        tensor = s[0].clone()
        rest   = s[1:]
        if torch.isnan(tensor).any():
            tensor = torch.nan_to_num(tensor, nan=0.0)
        cleaned.append((tensor, *rest))
    return cleaned


def _inverse_scale(y: torch.Tensor, target_vars: list, scalers: dict) -> np.ndarray:
    arr = y.detach().cpu().numpy().astype(np.float64, copy=True)
    for ch, var in enumerate(target_vars[: arr.shape[1]]):
        if var.endswith("_sin") or var.endswith("_cos"):
            continue
        scaler = scalers.get(var) or scalers.get(var.rsplit("_", 1)[0])
        if scaler is None:
            continue
        flat   = arr[:, ch].reshape(-1)
        mask   = np.isfinite(flat)
        if mask.any():
            flat[mask] = scaler.inverse_transform(flat[mask].reshape(-1, 1)).reshape(-1)
        arr[:, ch] = flat.reshape(arr[:, ch].shape)
    return arr.astype(np.float32)


def _load_spatial_reference(stage1_dir: Path) -> dict:
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


def _save_frame(
    frame_idx: int,
    time_str: str,
    data_dict: dict[str, np.ndarray],
    lat: np.ndarray,
    lon: np.ndarray,
    out_dir: Path,
) -> Path:
    """Save a single 1×3 PNG matching the reference comparison_sample style."""
    PLOT_VARS = ["HSig", "PDIR_sin", "PDIR_cos"]

    fig, axes = plt.subplots(
        1, 3,
        figsize=(18, 5.5),
        facecolor="white",
        constrained_layout=True,
    )

    for ax, var in zip(axes, PLOT_VARS):
        meta = _VAR_META[var]
        arr  = data_dict.get(var)
        if arr is None:
            ax.axis("off")
            continue

        # ── colour limits ──────────────────────────────────────────────
        finite = arr[np.isfinite(arr)]
        if finite.size == 0:
            vmin, vmax = 0.0, 1.0
        else:
            # Use fixed limits when available to keep colourbar consistent
            # across frames; fall back to data-driven limits.
            if meta["vmin_fixed"] is not None and meta["vmax_fixed"] is not None:
                vmin = meta["vmin_fixed"]
                vmax = meta["vmax_fixed"]
            elif meta["symmetric"]:
                absmax = max(abs(float(finite.min())), abs(float(finite.max()))) or 1.0
                vmin, vmax = -absmax, absmax
            else:
                vmin = meta["vmin_fixed"] if meta["vmin_fixed"] is not None else float(finite.min())
                vmax = meta["vmax_fixed"] if meta["vmax_fixed"] is not None else float(finite.max())

        # ── imshow with real geographic extent ─────────────────────────
        if lat.ndim == 1 and lon.ndim == 1:
            extent = [float(lon.min()), float(lon.max()),
                      float(lat.min()), float(lat.max())]
        else:
            extent = None

        im = ax.imshow(
            arr,
            origin="lower",
            aspect="auto",
            extent=extent,
            cmap=meta["cmap"],
            vmin=vmin,
            vmax=vmax,
        )

        # ── colourbar ──────────────────────────────────────────────────
        cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        if meta["unit"]:
            cb.set_label(meta["unit"], fontsize=10)
        cb.ax.tick_params(labelsize=9)

        # ── axis decoration ────────────────────────────────────────────
        ax.set_title(meta["title"], fontsize=11, fontweight="bold", pad=6)
        ax.set_xlabel("Longitude", fontsize=10)
        ax.set_ylabel("Latitude",  fontsize=10)

        # Real coordinate ticks (5 ticks per axis)
        if lat.ndim == 1 and lon.ndim == 1:
            lon_ticks = np.linspace(lon.min(), lon.max(), 5)
            lat_ticks = np.linspace(lat.min(), lat.max(), 5)
            ax.set_xticks(lon_ticks)
            ax.set_yticks(lat_ticks)
            ax.set_xticklabels([f"{v:.1f}" for v in lon_ticks], fontsize=8)
            ax.set_yticklabels([f"{v:.1f}" for v in lat_ticks], fontsize=8)

        ax.tick_params(direction="in", length=4, width=0.8)
        for spine in ax.spines.values():
            spine.set_linewidth(0.8)

    # ── super-title ────────────────────────────────────────────────────
    fig.suptitle(
        f"SWAN Surrogate Model Prediction  —  {_fmt_ts(time_str)}",
        fontsize=14,
        fontweight="bold",
        y=1.03,
    )

    out_path = out_dir / f"pred_frame_{frame_idx:03d}.png"
    fig.savefig(
        str(out_path),
        dpi=150,
        bbox_inches="tight",
        facecolor="white",
    )
    plt.close(fig)
    return out_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = _parse_args()

    sequences_path = Path(args.sequences_path)
    checkpoint_path = Path(args.checkpoint)
    stage1_dir  = Path(args.stage1_dir)
    output_dir  = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 1. Load & filter sequences
    # ------------------------------------------------------------------
    print(f"\n[stage3] Loading sequences from: {sequences_path}", flush=True)

    if args.date:
        print(f"[stage3] Date filter '{args.date}' — memory-mapped scan across all splits ...",
              flush=True)
        samples = _load_all_splits_filtered(sequences_path, args.date)
        print(f"[stage3] Total samples matching {args.date}: {len(samples)}", flush=True)
        if not samples:
            raise ValueError(
                f"No samples found for date '{args.date}' in {sequences_path}.\n"
                "Verify the date exists in one of the splits (train/val/test)."
            )
        try:
            samples.sort(key=lambda s: pd.to_datetime(str(s[-1])))
        except Exception:
            pass
    else:
        samples = _load_split(sequences_path, args.split)
        print(f"[stage3] Loaded {len(samples)} samples from '{args.split}' split", flush=True)

    samples = _clean_nans(samples)

    # ------------------------------------------------------------------
    # 2. Build model using create_model factory
    # ------------------------------------------------------------------
    n_channels = int(samples[0][0].shape[0])
    model_cfg  = dict(MODEL_CONFIG)
    model_cfg["input_channels"] = n_channels
    print(f"\n[stage3] Building '{MODEL_ARCHITECTURE}' with {n_channels} input channels ...",
          flush=True)
    model = create_model(MODEL_ARCHITECTURE, model_cfg)

    device = args.device
    if device == "cuda" and not torch.cuda.is_available():
        print("[stage3] CUDA unavailable, using CPU.", flush=True)
        device = "cpu"

    # Fall back to latest checkpoint in MODEL_DIR if the given path doesn't exist
    if not checkpoint_path.exists():
        candidates = sorted(MODEL_DIR.glob("physics_unet2*.pt"),
                            key=lambda p: p.stat().st_mtime)
        if not candidates:
            raise FileNotFoundError(f"No checkpoint found at {checkpoint_path} or in {MODEL_DIR}")
        checkpoint_path = candidates[-1]

    print(f"[stage3] Loading checkpoint: {checkpoint_path}", flush=True)
    load_model_checkpoint(model, str(checkpoint_path), device=device)
    model.to(device)
    model.eval()
    print(f"[stage3] Model ready on {device}", flush=True)

    # ------------------------------------------------------------------
    # 3. Inference
    # ------------------------------------------------------------------
    loader = torch.utils.data.DataLoader(
        TensorDataset(samples), batch_size=args.batch_size, shuffle=False
    )
    pred_batches: list[torch.Tensor] = []
    time_labels: list[str] = []

    print(f"\n[stage3] Running inference over {len(samples)} samples ...", flush=True)
    with torch.no_grad():
        for batch_idx, batch in enumerate(loader, start=1):
            if batch_idx == 1 or batch_idx % 5 == 0 or batch_idx == len(loader):
                print(f"  batch {batch_idx}/{len(loader)}", flush=True)
            if len(batch) == 3:
                inputs, _targets, batch_times = batch
            elif len(batch) == 2:
                inputs, batch_times = batch
            else:
                (inputs,) = batch
                batch_times = [None] * len(inputs)
            preds = model(inputs.to(device, non_blocking=True))
            pred_batches.append(preds.detach().cpu())
            time_labels.extend([str(t) for t in batch_times])

    y_pred = torch.cat(pred_batches, dim=0)
    print(f"[stage3] Inference complete. Output shape: {y_pred.shape}", flush=True)

    # ------------------------------------------------------------------
    # 4. Inverse-scale to physical units
    # ------------------------------------------------------------------
    print("[stage3] Inverse-scaling to physical units ...", flush=True)
    scalers   = import_scale(SCALER_PATH)
    y_pred_np = _inverse_scale(y_pred, list(TARGET_VARS), scalers)

    for ch, var in enumerate(TARGET_VARS[: y_pred_np.shape[1]]):
        finite = y_pred_np[:, ch][np.isfinite(y_pred_np[:, ch])]
        if finite.size:
            print(f"  {var:12s}: min={finite.min():.4f}  max={finite.max():.4f}  "
                  f"mean={finite.mean():.4f}", flush=True)
        else:
            print(f"  {var:12s}: all NaN", flush=True)

    # ------------------------------------------------------------------
    # 5. Spatial reference (lat / lon / elevation)
    # ------------------------------------------------------------------
    spatial = _load_spatial_reference(stage1_dir)
    lat, lon = spatial["lat"], spatial["lon"]

    # ------------------------------------------------------------------
    # 6. Save NetCDF
    # ------------------------------------------------------------------
    parsed_times = pd.to_datetime(time_labels, errors="coerce")
    time_coord = (parsed_times.to_numpy()
                  if not parsed_times.isna().all()
                  else np.array(time_labels, dtype="U"))

    data_vars: dict = {}
    for ch, var in enumerate(TARGET_VARS[: y_pred_np.shape[1]]):
        data_vars[f"{var}_pred"] = (("time", "lat", "lon"), y_pred_np[:, ch])
    if spatial.get("elevation") is not None:
        data_vars["elevation"] = (("lat", "lon"), spatial["elevation"])

    ds = xr.Dataset(
        data_vars=data_vars,
        coords={"time": time_coord, "lat": lat, "lon": lon},
    )
    ds.attrs.update({
        "model_architecture": MODEL_ARCHITECTURE,
        "checkpoint": str(checkpoint_path),
        "sequences_path": str(sequences_path),
        "sample_count": int(len(samples)),
    })
    nc_path = output_dir / "stage3_predictions.nc"
    ds.to_netcdf(str(nc_path))
    print(f"\n[stage3] Saved NetCDF → {nc_path}", flush=True)

    # ------------------------------------------------------------------
    # 7. Generate hourly PNG frames (up to max_frames)
    # ------------------------------------------------------------------
    n_time   = y_pred_np.shape[0]
    n_frames = min(args.max_frames, n_time)

    if n_frames >= n_time:
        frame_indices = list(range(n_time))
    else:
        # User requested that frames start from the beginning rather than spreading evenly
        frame_indices = list(range(n_frames))

    frames_dir = output_dir / "frames"
    frames_dir.mkdir(exist_ok=True)
    for old in frames_dir.glob("pred_frame_*.png"):
        old.unlink()

    print(f"[stage3] Generating {len(frame_indices)} frames → {frames_dir}", flush=True)
    saved: list[Path] = []
    for seq_pos, t_idx in enumerate(frame_indices):
        data_dict = {
            var: y_pred_np[t_idx, ch]
            for ch, var in enumerate(TARGET_VARS[: y_pred_np.shape[1]])
            if var in _VAR_META
        }
        out = _save_frame(seq_pos, time_labels[t_idx], data_dict, lat, lon, frames_dir)
        saved.append(out)
        print(f"  [{seq_pos + 1:02d}/{len(frame_indices)}] {out.name}  "
              f"{_fmt_ts(time_labels[t_idx])}", flush=True)

    # ------------------------------------------------------------------
    print("\n" + "=" * 72)
    print("[stage3] Done!")
    print(f"  NetCDF   : {nc_path}")
    print(f"  Frames   : {frames_dir}  ({len(saved)} images)")
    print("=" * 72)


if __name__ == "__main__":
    main()
