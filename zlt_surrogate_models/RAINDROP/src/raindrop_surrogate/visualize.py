"""
visualize.py — plotting utilities for the underwater-acoustics surrogate.

Public API
----------
plot_predicted_spl_radial     Standalone radial/polar output plot with land masking.
plot_predicted_spl_cartesian  Standalone Cartesian interpolated output plot with land masking.
plot_radial_comparison        4-panel figure: GT map, pred map, error map, ray profile.
plot_training_curves          Loss curves from a metrics CSV or dict of lists.
plot_metrics_table            Formatted table of physical-unit metrics.
"""

import os
from typing import Optional, Dict, List

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import torch
import scipy.ndimage as ndimage
from scipy.interpolate import griddata



def plot_predicted_spl_radial(radial_output, spatial_meta, ship_lat, ship_lon, mask_path = "cache/land_mask_1000.npy", save_path=None):
    """
    Plots the raw 360x125 grid of SPL values as a flat 2D heatmap.
    Applies the cached Cartesian land mask to the ray coordinates, rendering land as black.
    """
    
    if not os.path.exists(mask_path):
        raise FileNotFoundError(
            f" Critical Error: The required land mask file was not found at '{mask_path}'. "
            "Please verify the path or run your data preparation pipeline."
        )
        
    land_mask = np.load(mask_path)
    crop_size = spatial_meta["crop_size"]
    num_rays, ray_points = radial_output.shape

    # 1. Map the Cartesian land mask into polar grid space
    target_lats = np.array(spatial_meta["target_lats"])
    target_lons = np.array(spatial_meta["target_lons"])
    lat_idx = np.interp(ship_lat, target_lats, np.arange(crop_size))
    lon_idx = np.interp(ship_lon, target_lons, np.arange(crop_size))
    
    angles = np.deg2rad(np.arange(num_rays))
    cos_a, sin_a = np.cos(angles), np.sin(angles)
    
    with np.errstate(divide="ignore", invalid="ignore"):
        t_x = np.where(cos_a > 0, (crop_size - 1 - lon_idx) / cos_a, np.where(cos_a < 0, -lon_idx / cos_a, np.inf))
        t_y = np.where(sin_a > 0, (crop_size - 1 - lat_idx) / sin_a, np.where(sin_a < 0, -lat_idx / sin_a, np.inf))
    t_max = np.minimum(t_x, t_y)
    
    r = np.linspace(0, 1, ray_points)
    x_pts = lon_idx + np.outer(t_max, r) * cos_a[:, None]
    y_pts = lat_idx + np.outer(t_max, r) * sin_a[:, None]
    
    coords = np.vstack((np.clip(y_pts, 0, crop_size - 1).ravel(), np.clip(x_pts, 0, crop_size - 1).ravel()))
    radial_mask = ndimage.map_coordinates(land_mask.astype(float), coords, order=0).reshape(num_rays, ray_points)
    
    # 2. Mask out land values (<= 0.5) with NaN
    plot_data = radial_output.copy()
    plot_data[radial_mask <= 0.5] = np.nan

    # 3. Setup Colormap to render NaNs (land) as Black
    cmap = plt.cm.viridis.copy()
    cmap.set_bad(color='black')

    # 4. Generate Plot
    fig, ax = plt.subplots(figsize=(12, 7))
    im = ax.imshow(plot_data, aspect="auto", cmap=cmap, origin="lower")
    
    ax.set_title("Predicted SPL field", fontsize=13, pad=12)
    ax.set_ylabel("Ray Angle Index (0 to 359 Degrees)", fontsize=11)
    ax.set_xlabel("Distance Step Index (0 to 124 Along Ray)", fontsize=11)
    
    fig.colorbar(im, ax=ax, label="Sound Pressure Level (dB re 1 µPa)")
    ax.grid(True, alpha=0.15, linestyle="--")

    if save_path:
        os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        plt.close()
        return save_path
    else:
        plt.show()

def plot_predicted_spl_cartesian(radial_output, spatial_meta, ship_lat, ship_lon, mask_path = "cache/land_mask_1000.npy", save_path=None):
    """
    Interpolates the polar prediction matrix onto a geographic Cartesian grid.
    Overlays the static land mask, rendering land as black.
    """
    
    if not os.path.exists(mask_path):
        raise FileNotFoundError(
            f" Critical Error: The required land mask file was not found at '{mask_path}'. "
        )
        
    land_mask = np.load(mask_path)
    crop_size = spatial_meta["crop_size"]
    num_rays, ray_points = radial_output.shape
    
    target_lats = np.array(spatial_meta["target_lats"])
    target_lons = np.array(spatial_meta["target_lons"])
    lat_idx = np.interp(ship_lat, target_lats, np.arange(crop_size))
    lon_idx = np.interp(ship_lon, target_lons, np.arange(crop_size))
    
    angles = np.deg2rad(np.arange(num_rays))
    cos_a, sin_a = np.cos(angles), np.sin(angles)
    
    with np.errstate(divide="ignore", invalid="ignore"):
        t_x = np.where(cos_a > 0, (crop_size - 1 - lon_idx) / cos_a, np.where(cos_a < 0, -lon_idx / cos_a, np.inf))
        t_y = np.where(sin_a > 0, (crop_size - 1 - lat_idx) / sin_a, np.where(sin_a < 0, -lat_idx / sin_a, np.inf))
    t_max = np.minimum(t_x, t_y)
    
    r = np.linspace(0, 1, ray_points)
    x_pts = lon_idx + np.outer(t_max, r) * cos_a[:, None]
    y_pts = lat_idx + np.outer(t_max, r) * sin_a[:, None]
    
    # 1. Map irregular polar ray distributions onto standard Cartesian square
    points = np.vstack((y_pts.ravel(), x_pts.ravel())).T
    values = radial_output.ravel()
    
    grid_y, grid_x = np.mgrid[0:crop_size, 0:crop_size]
    cartesian_grid = griddata(points, values, (grid_y, grid_x), method='linear')
    
    # 2. Mask Cartesian land with NaN (values <= 0.5)
    cartesian_grid[land_mask <= 0.5] = np.nan
    
    # 3. Setup Colormap to render NaNs (land) as Black
    cmap = plt.cm.viridis.copy()
    cmap.set_bad(color='black')

    # 4. Generate Plot
    fig, ax = plt.subplots(figsize=(8, 8))
    im = ax.imshow(cartesian_grid, aspect="equal", cmap=cmap, origin="lower")
    
    # Indicator for the target ship coordinate
    ax.plot(lon_idx, lat_idx, color="crimson", marker="*", markersize=14, markeredgecolor="white", label="Source Vessel")
    
    ax.set_title("Predicted SPL field", fontsize=13)
    ax.set_xlabel("Horizontal Grid Steps (Pixels)")
    ax.set_ylabel("Vertical Grid Steps (Pixels)")
    fig.colorbar(im, ax=ax, label="Sound Pressure Level (dB re 1 µPa)", shrink=0.8)
    ax.legend(loc="upper right")
    
    if save_path:
        os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        plt.close()
        return save_path
    else:
        plt.show()


# ─────────────────────────────────────────────────────────────────────────────
# 1.  Radial comparison (4-panel)
# ─────────────────────────────────────────────────────────────────────────────

def plot_radial_comparison(
    model: torch.nn.Module,
    dataset,           # ScaledDatasetWrapper or AcousticDataset
    stats: dict,
    device: torch.device,
    sample_idx: int = 0,
    save_path: Optional[str] = None,
    target_ray: int = 0,
) -> str:
    """
    Generate a 4-panel comparison between ground truth and prediction.

    Panels
    ------
    (0,0) Ground-truth SPL map
    (0,1) Predicted SPL map
    (1,0) Residual map   (pred - GT), capped at ±10
    (1,1) 1-D ray profile along ``target_ray``

    Parameters
    ----------
    model      : trained RadialAcousticSurrogate (eval mode after call).
    dataset    : dataset that returns (ais, bathy, spl, t_max) tuples.
    stats      : statistics dict from ``scale_data``.
    device     : torch device.
    sample_idx : index of the sample to visualise.
    save_path  : if given, figure is saved here; otherwise a path is
                 auto-generated in the current directory.
    target_ray : ray index shown in the 1-D profile panel.

    Returns
    -------
    str — the path where the figure was saved.
    """
    model.eval()
    s_min, s_max = stats["spl"]["min"], stats["spl"]["max"]

    with torch.no_grad():
        ais_sc, bathy_sc, spl_gt_sc, t_max = dataset[sample_idx]

        ais_in   = ais_sc.squeeze().unsqueeze(0).to(device).float()
        bathy_in = bathy_sc.squeeze().unsqueeze(0).to(device).float()
        t_max_in = t_max.squeeze().unsqueeze(0).to(device).float()

        pred_sc = model(bathy_in, ais_in, t_max_in).squeeze().cpu()

    # Denormalise
    spl_gt_plot   = (spl_gt_sc.squeeze()  * (s_max - s_min) + s_min).numpy()
    spl_pred_plot = (pred_sc              * (s_max - s_min) + s_min).numpy()
    bathy_plot    = bathy_sc.squeeze().cpu().numpy()

    # Mask land
    land_mask = bathy_plot <= 0
    spl_gt_plot  = spl_gt_plot.copy();  spl_gt_plot[land_mask]   = np.nan
    spl_pred_plot = spl_pred_plot.copy(); spl_pred_plot[land_mask] = np.nan

    # ── Figure ────────────────────────────────────────────────────────
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle(f"Radial Comparison — Sample {sample_idx}", fontsize=14, y=0.98)
    plt.subplots_adjust(hspace=0.35, wspace=0.3)

    im_kw = dict(aspect="auto", cmap="viridis", vmin=s_min, vmax=s_max)

    im1 = axes[0, 0].imshow(spl_gt_plot, **im_kw)
    axes[0, 0].set_title("Ground Truth SPL", fontsize=12)
    fig.colorbar(im1, ax=axes[0, 0], label="SPL")

    im2 = axes[0, 1].imshow(spl_pred_plot, **im_kw)
    axes[0, 1].set_title("Predicted SPL", fontsize=12)
    fig.colorbar(im2, ax=axes[0, 1], label="SPL")

    error = spl_pred_plot - spl_gt_plot
    im3   = axes[1, 0].imshow(error, aspect="auto", cmap="RdBu_r", vmin=-10, vmax=10)
    axes[1, 0].set_title("Residuals (Pred - GT)", fontsize=12)
    fig.colorbar(im3, ax=axes[1, 0], label="Error")

    axes[1, 1].plot(spl_gt_plot[target_ray, :],   label="GT",   color="black", linewidth=2)
    axes[1, 1].plot(spl_pred_plot[target_ray, :], label="Pred", color="crimson", linestyle="--")
    axes[1, 1].set_title(f"Ray Decay Profile (angle {target_ray}°)", fontsize=12)
    axes[1, 1].set_xlabel("Distance index")
    axes[1, 1].set_ylabel("SPL")
    axes[1, 1].legend()
    axes[1, 1].grid(True, alpha=0.3)

    if save_path is None:
        save_path = f"radial_comparison_sample{sample_idx}.png"
    os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()
    return save_path


# ─────────────────────────────────────────────────────────────────────────────
# 2.  Training curves
# ─────────────────────────────────────────────────────────────────────────────

def plot_training_curves(
    train_losses: List[float],
    val_losses: List[float],
    save_path: Optional[str] = None,
    title: str = "Training & Validation Loss",
) -> str:
    """
    Plot train / val MSE curves over epochs.

    Parameters
    ----------
    train_losses, val_losses : lists of per-epoch average MSE values.
    save_path : where to save the figure.
    title     : figure title.

    Returns
    -------
    str — save path.
    """
    epochs = range(1, len(train_losses) + 1)

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(epochs, train_losses, label="Train MSE", color="steelblue", linewidth=1.8)
    ax.plot(epochs, val_losses,   label="Val MSE",   color="tomato",    linewidth=1.8)
    ax.set_xlabel("Epoch")
    ax.set_ylabel("MSE (normalised)")
    ax.set_title(title)
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_yscale("log")

    if save_path is None:
        save_path = "training_curves.png"
    os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()
    return save_path


# ─────────────────────────────────────────────────────────────────────────────
# 3.  Metrics summary table
# ─────────────────────────────────────────────────────────────────────────────

def plot_metrics_table(
    metrics_by_split: Dict[str, Dict[str, float]],
    save_path: Optional[str] = None,
) -> str:
    """
    Render a clean table of physical-unit metrics across data splits.

    Parameters
    ----------
    metrics_by_split : dict  e.g. ``{"train": {...}, "val": {...}, "test": {...}}``.
        Each inner dict is the output of :func:`~utils.compute_physical_metrics`.
    save_path : where to save the figure.

    Returns
    -------
    str — save path.
    """
    splits  = list(metrics_by_split.keys())
    columns = ["MSE (Pa²)", "MAE (Pa)", "MSE (dB²)", "MAE (dB)"]
    keys    = ["mse_pa", "mae_pa", "mse_db", "mae_db"]

    cell_text = [
        [f"{metrics_by_split[s][k]:.4e}" for k in keys]
        for s in splits
    ]

    fig, ax = plt.subplots(figsize=(10, 1.5 + 0.5 * len(splits)))
    ax.axis("off")
    tbl = ax.table(
        cellText   = cell_text,
        rowLabels  = splits,
        colLabels  = columns,
        cellLoc    = "center",
        loc        = "center",
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(10)
    tbl.scale(1.2, 1.6)
    ax.set_title("Physical-unit Metrics Summary", fontsize=13, pad=12)

    if save_path is None:
        save_path = "metrics_table.png"
    os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()
    return save_path
