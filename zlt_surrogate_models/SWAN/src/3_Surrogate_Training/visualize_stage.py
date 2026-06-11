import json
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

from config import PREPROCESSED_ROOT, VARIABLE_METADATA
from visualize_metrics_helpers import (
    save_prediction_snapshot_all_outputs,
    save_per_variable_metric_bars,
)


def _ensure_dir(path: str | Path) -> Path:
    out = Path(path)
    out.mkdir(parents=True, exist_ok=True)
    return out


def save_training_history(history: dict, out_dir: str | Path, dpi: int = 150) -> str:
    out = _ensure_dir(out_dir)
    fig_path = out / "training_history.png"

    epochs = history.get("epoch", [])
    train_loss = history.get("train_loss", [])
    val_loss = history.get("val_loss", [])

    plt.figure(figsize=(10, 5), dpi=dpi)
    plt.plot(epochs, train_loss, marker="o", label="Train Loss")
    plt.plot(epochs, val_loss, marker="o", label="Validation Loss")
    plt.xlabel("Epoch")
    plt.ylabel("Loss")
    plt.title("Training History")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(fig_path)
    plt.close()

    return str(fig_path)


def save_training_loss_curves(history: dict, out_dir: str | Path, dpi: int = 150) -> str | None:
    out = _ensure_dir(out_dir)
    fig_path = out / "training_and_validation_loss.png"

    epochs = history.get("epoch", [])
    train_loss = history.get("train_loss", [])
    val_loss = history.get("val_loss", [])

    if len(epochs) == 0 or len(train_loss) == 0 or len(val_loss) == 0:
        return None

    fig, axes = plt.subplots(1, 2, figsize=(14, 5), dpi=dpi)

    axes[0].plot(epochs, train_loss, marker="o", markersize=3, linewidth=1.8, label="Training Loss")
    axes[0].plot(epochs, val_loss, marker="s", markersize=3, linewidth=1.8, label="Validation Loss")
    axes[0].set_xlabel("Epoch")
    axes[0].set_ylabel("Loss (MSE)")
    axes[0].set_title("Training and Validation Loss", fontweight="bold")
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()

    axes[1].semilogy(epochs, train_loss, marker="o", markersize=3, linewidth=1.8, label="Training Loss")
    axes[1].semilogy(epochs, val_loss, marker="s", markersize=3, linewidth=1.8, label="Validation Loss")
    axes[1].set_xlabel("Epoch")
    axes[1].set_ylabel("Loss (MSE) - Log Scale")
    axes[1].set_title("Training and Validation Loss (Log Scale)", fontweight="bold")
    axes[1].grid(True, alpha=0.3)
    axes[1].legend()

    plt.tight_layout()
    plt.savefig(fig_path)
    plt.close()
    return str(fig_path)


def save_learning_rate_schedule(history: dict, out_dir: str | Path, dpi: int = 150) -> str | None:
    out = _ensure_dir(out_dir)
    fig_path = out / "learning_rate_schedule.png"

    epochs = history.get("epoch", [])
    learning_rate = history.get("learning_rate", [])
    if len(epochs) == 0 or len(learning_rate) == 0:
        return None

    plt.figure(figsize=(10, 5), dpi=dpi)
    plt.plot(epochs, learning_rate, marker="o", markersize=4, linewidth=1.8)
    plt.xlabel("Epoch")
    plt.ylabel("Learning Rate")
    plt.title("Learning Rate Schedule", fontweight="bold")
    plt.yscale("log")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(fig_path)
    plt.close()

    return str(fig_path)


def save_eval_metrics(eval_results: dict, out_dir: str | Path) -> str:
    out = _ensure_dir(out_dir)
    json_path = out / "evaluation_metrics.json"
    serializable = dict(eval_results)
    serializable.pop("test_arrays", None)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2)
    return str(json_path)


def _label_and_unit(var_name: str) -> tuple[str, str]:
    meta = VARIABLE_METADATA.get(var_name, {})
    label = meta.get("label_long", var_name)
    unit = meta.get("unit", "")
    return label, unit


def _format_sample_time(time_value) -> str:
    if time_value is None:
        return ""

    try:
        timestamp = np.datetime64(time_value).astype("datetime64[m]")
        parsed = datetime.strptime(str(timestamp), "%Y-%m-%dT%H:%M")
        return parsed.strftime("%d/%m/%Y, %H:%M")
    except Exception:
        return str(time_value)


def _load_map_coordinates(test_arrays: dict | None) -> tuple[np.ndarray | None, np.ndarray | None]:
    if test_arrays is not None:
        lat_vals = test_arrays.get("lat_vals")
        lon_vals = test_arrays.get("lon_vals")
        if lat_vals is not None and lon_vals is not None:
            return np.asarray(lat_vals, dtype=float), np.asarray(lon_vals, dtype=float)

    for nc_path in sorted(PREPROCESSED_ROOT.rglob("wave_output_preprocessed_*.nc")):
        try:
            with xr.open_dataset(nc_path, decode_times=False) as ds:
                if "lat" in ds.coords and "lon" in ds.coords:
                    return np.asarray(ds["lat"].values, dtype=float), np.asarray(ds["lon"].values, dtype=float)
                if "latitude" in ds.coords and "longitude" in ds.coords:
                    return np.asarray(ds["latitude"].values, dtype=float), np.asarray(ds["longitude"].values, dtype=float)
        except Exception:
            continue

    return None, None


def _plot_map_panel(ax: plt.Axes, data: np.ndarray, lat_vals: np.ndarray | None, lon_vals: np.ndarray | None, **kwargs):
    if lat_vals is not None and lon_vals is not None:
        return ax.pcolormesh(lon_vals, lat_vals, data, shading="auto", **kwargs)
    return ax.imshow(data, origin="lower", aspect="auto", **kwargs)


def save_scatter_comparison(
    test_arrays: dict | None,
    out_dir: str | Path,
    target_vars: list[str],
    dpi: int = 150,
    n_samples: int = 5000,
) -> str | None:
    if test_arrays is None:
        return None

    y_true = test_arrays.get("y_true")
    y_pred = test_arrays.get("y_pred")
    if y_true is None or y_pred is None:
        return None

    n_vars = min(len(target_vars), y_true.shape[1], y_pred.shape[1])
    if n_vars == 0:
        return None

    out = _ensure_dir(out_dir)
    fig_path = out / "predicted_vs_true_scatter.png"

    fig, axes = plt.subplots(1, n_vars, figsize=(6 * n_vars, 5), dpi=dpi)
    if n_vars == 1:
        axes = [axes]

    rng = np.random.default_rng(42)
    for i in range(n_vars):
        true_flat = y_true[:, i, :, :].reshape(-1)
        pred_flat = y_pred[:, i, :, :].reshape(-1)
        finite = np.isfinite(true_flat) & np.isfinite(pred_flat)
        true_flat = true_flat[finite]
        pred_flat = pred_flat[finite]

        if true_flat.size == 0:
            continue

        size = min(n_samples, true_flat.size)
        idx = rng.choice(true_flat.size, size=size, replace=False)
        true_sample = true_flat[idx]
        pred_sample = pred_flat[idx]

        label, unit = _label_and_unit(target_vars[i])
        axes[i].scatter(true_sample, pred_sample, alpha=0.3, s=10)
        min_val = float(min(true_sample.min(), pred_sample.min()))
        max_val = float(max(true_sample.max(), pred_sample.max()))
        axes[i].plot([min_val, max_val], [min_val, max_val], "r--", linewidth=2, label="Perfect Prediction")
        axes[i].set_xlabel(f"True {label} [{unit}]" if unit else f"True {label}")
        axes[i].set_ylabel(f"Predicted {label} [{unit}]" if unit else f"Predicted {label}")
        axes[i].set_title(label, fontweight="bold")
        axes[i].legend()
        axes[i].grid(True, alpha=0.3)

    plt.suptitle("Predicted vs. True Values", fontsize=16, fontweight="bold")
    plt.tight_layout()
    plt.savefig(fig_path)
    plt.close()
    return str(fig_path)


def save_error_distributions(
    test_arrays: dict | None,
    out_dir: str | Path,
    target_vars: list[str],
    dpi: int = 150,
) -> str | None:
    if test_arrays is None:
        return None

    y_true = test_arrays.get("y_true")
    y_pred = test_arrays.get("y_pred")
    if y_true is None or y_pred is None:
        return None

    n_vars = min(len(target_vars), y_true.shape[1], y_pred.shape[1])
    if n_vars == 0:
        return None

    out = _ensure_dir(out_dir)
    fig_path = out / "error_distributions.png"

    fig, axes = plt.subplots(1, n_vars, figsize=(6 * n_vars, 5), dpi=dpi)
    if n_vars == 1:
        axes = [axes]

    for i in range(n_vars):
        errors = (y_pred[:, i, :, :] - y_true[:, i, :, :]).reshape(-1)
        errors = errors[np.isfinite(errors)]
        if errors.size == 0:
            continue

        label, unit = _label_and_unit(target_vars[i])
        axes[i].hist(errors, bins=50, alpha=0.7, edgecolor="black")
        axes[i].axvline(0.0, color="r", linestyle="--", linewidth=2, label="Zero Error")
        mean_err = float(np.mean(errors))
        axes[i].axvline(mean_err, color="g", linestyle="--", linewidth=2, label=f"Mean: {mean_err:.3f}")
        axes[i].set_xlabel(f"Error [{unit}]" if unit else "Error")
        axes[i].set_ylabel("Frequency")
        axes[i].set_title(f"{label}\nError Distribution", fontweight="bold")
        axes[i].legend()
        axes[i].grid(True, alpha=0.3, axis="y")

    plt.suptitle("Prediction Error Distributions", fontsize=16, fontweight="bold")
    plt.tight_layout()
    plt.savefig(fig_path)
    plt.close()
    return str(fig_path)


def save_prediction_comparisons(
    test_arrays: dict | None,
    out_dir: str | Path,
    target_vars: list[str],
    dpi: int = 150,
    n_visualization_samples: int = 5,
) -> list[str]:
    if test_arrays is None:
        return []

    y_true = test_arrays.get("y_true")
    y_pred = test_arrays.get("y_pred")
    time_labels = test_arrays.get("time_labels")
    if y_true is None or y_pred is None:
        return []

    lat_vals, lon_vals = _load_map_coordinates(test_arrays)

    n_samples = min(int(n_visualization_samples), y_true.shape[0], y_pred.shape[0])
    n_vars = min(len(target_vars), y_true.shape[1], y_pred.shape[1])
    if n_samples == 0 or n_vars == 0:
        return []

    out = _ensure_dir(out_dir)
    saved_paths: list[str] = []
    step = 18
    for sample_idx in range(n_samples):
        sample_idx = sample_idx * step
        fig_path = out / f"comparison_sample_{sample_idx}.png"
        fig, axes = plt.subplots(n_vars, 3, figsize=(18, 5 * n_vars), dpi=dpi)
        if n_vars == 1:
            axes = np.expand_dims(axes, axis=0)

        sample_time = None
        if isinstance(time_labels, (list, tuple)) and sample_idx < len(time_labels):
            sample_time = _format_sample_time(time_labels[sample_idx])
        elif time_labels is not None:
            sample_time = _format_sample_time(time_labels[sample_idx])

        for i in range(n_vars):
            true_map = y_true[sample_idx, i, :, :]
            pred_map = y_pred[sample_idx, i, :, :]
            err_map = pred_map - true_map
            label, unit = _label_and_unit(target_vars[i])

            vmin = float(min(np.nanmin(true_map), np.nanmin(pred_map)))
            vmax = float(max(np.nanmax(true_map), np.nanmax(pred_map)))

            im0 = _plot_map_panel(axes[i, 0], true_map, lat_vals, lon_vals, cmap="viridis", vmin=vmin, vmax=vmax)
            axes[i, 0].set_title(f"True {label}", fontweight="bold")
            axes[i, 0].set_ylabel("Latitude")
            axes[i, 0].set_xlabel("Longitude")
            plt.colorbar(im0, ax=axes[i, 0], fraction=0.046, label=unit)

            im1 = _plot_map_panel(axes[i, 1], pred_map, lat_vals, lon_vals, cmap="viridis", vmin=vmin, vmax=vmax)
            axes[i, 1].set_title(f"Predicted {label}", fontweight="bold")
            axes[i, 1].set_ylabel("Latitude")
            axes[i, 1].set_xlabel("Longitude")
            plt.colorbar(im1, ax=axes[i, 1], fraction=0.046, label=unit)

            err_abs = float(np.nanmax(np.abs(err_map)))
            if err_abs == 0:
                err_abs = 0.1
            im2 = _plot_map_panel(
                axes[i, 2],
                err_map,
                lat_vals,
                lon_vals,
                cmap="RdBu_r",
                vmin=-err_abs,
                vmax=err_abs,
            )
            axes[i, 2].set_title("Error (Pred - True)", fontweight="bold")
            axes[i, 2].set_ylabel("Latitude")
            axes[i, 2].set_xlabel("Longitude")
            plt.colorbar(im2, ax=axes[i, 2], fraction=0.046, label=unit)

        if sample_time:
            plt.suptitle(
                f"Prediction Comparison - Sample {sample_idx} ({sample_time})",
                fontsize=16,
                fontweight="bold",
            )
        else:
            plt.suptitle(f"Prediction Comparison - Sample {sample_idx}", fontsize=16, fontweight="bold")
        plt.tight_layout()
        plt.savefig(fig_path)
        plt.close()
        saved_paths.append(str(fig_path))

    return saved_paths


def save_time_series_comparisons(
    test_arrays: dict | None,
    out_dir: str | Path,
    target_vars: list[str],
    vis_config: dict,
    dpi: int = 150,
) -> list[str]:
    if test_arrays is None:
        return []

    y_true = test_arrays.get("y_true")
    y_pred = test_arrays.get("y_pred")
    if y_true is None or y_pred is None:
        return []

    n_time = y_true.shape[0]
    n_vars = min(len(target_vars), y_true.shape[1], y_pred.shape[1])
    if n_time == 0 or n_vars == 0:
        return []

    points = vis_config.get("timeseries_points", [])
    if not points:
        return []

    out = _ensure_dir(out_dir)
    saved_paths: list[str] = []

    for lat_idx, lon_idx in points:
        if not (0 <= lat_idx < y_true.shape[2] and 0 <= lon_idx < y_true.shape[3]):
            continue

        fig_path = out / f"timeseries_point_{lat_idx}_{lon_idx}.png"
        fig, axes = plt.subplots(n_vars, 1, figsize=(15, 4 * n_vars), dpi=dpi)
        if n_vars == 1:
            axes = [axes]

        t = np.arange(n_time)
        for i in range(n_vars):
            label, unit = _label_and_unit(target_vars[i])
            true_series = y_true[:, i, lat_idx, lon_idx]
            pred_series = y_pred[:, i, lat_idx, lon_idx]

            axes[i].plot(t, true_series, label="True", marker="o", linewidth=1.6, markersize=3, alpha=0.8)
            axes[i].plot(t, pred_series, label="Predicted", marker="s", linewidth=1.6, markersize=3, alpha=0.8)
            axes[i].set_xlabel("Time Step")
            axes[i].set_ylabel(f"{label} [{unit}]" if unit else label)
            axes[i].set_title(f"{label} at Grid Point ({lat_idx}, {lon_idx})", fontweight="bold")
            axes[i].legend()
            axes[i].grid(True, alpha=0.3)

        plt.suptitle(f"Time Series Comparison at Grid Point ({lat_idx}, {lon_idx})", fontsize=16, fontweight="bold")
        plt.tight_layout()
        plt.savefig(fig_path)
        plt.close()
        saved_paths.append(str(fig_path))

    return saved_paths


def save_prediction_snapshot(
    snapshot_data: dict | None,
    out_dir: str | Path,
    dpi: int = 150,
    n_channels: int = 2,
) -> str | None:
    if snapshot_data is None:
        return None

    out = _ensure_dir(out_dir)
    fig_path = out / "prediction_snapshot.png"

    y_true = snapshot_data["y_true"]
    y_pred = snapshot_data["y_pred"]
    n_show = min(n_channels, y_true.shape[0], y_pred.shape[0])

    fig, axes = plt.subplots(n_show, 3, figsize=(12, 4 * n_show), dpi=dpi)
    if n_show == 1:
        axes = np.expand_dims(axes, axis=0)

    for c in range(n_show):
        true_map = y_true[c]
        pred_map = y_pred[c]
        err_map = pred_map - true_map

        # Use a shared scale so target and prediction are directly comparable.
        cmin = float(np.nanmin([true_map.min(), pred_map.min()]))
        cmax = float(np.nanmax([true_map.max(), pred_map.max()]))

        im0 = axes[c, 0].imshow(true_map, cmap="viridis", vmin=cmin, vmax=cmax)
        axes[c, 0].set_title(f"Target c={c}")
        plt.colorbar(im0, ax=axes[c, 0], fraction=0.046, pad=0.04)

        im1 = axes[c, 1].imshow(pred_map, cmap="viridis", vmin=cmin, vmax=cmax)
        axes[c, 1].set_title(f"Prediction c={c}")
        plt.colorbar(im1, ax=axes[c, 1], fraction=0.046, pad=0.04)

        im2 = axes[c, 2].imshow(err_map, cmap="RdBu_r")
        axes[c, 2].set_title(f"Error c={c}")
        plt.colorbar(im2, ax=axes[c, 2], fraction=0.046, pad=0.04)

        for col in range(3):
            axes[c, col].set_xticks([])
            axes[c, col].set_yticks([])

    plt.tight_layout()
    plt.savefig(fig_path)
    plt.close()
    return str(fig_path)


def run_visualization(
    train_history: dict,
    eval_results: dict,
    results_dir: str | Path,
    vis_config: dict,
    target_vars: list[str] | None = None,
    snapshot_data: dict | None = None,
    test_arrays: dict | None = None,
) -> dict:
    """Generate and save core diagnostic artifacts for training and evaluation."""
    out_dir = _ensure_dir(results_dir)
    dpi = int(vis_config.get("dpi", 150))

    artifacts = {}
    artifacts["training_history"] = save_training_history(train_history, out_dir=out_dir, dpi=dpi)
    artifacts["training_loss_curves"] = save_training_loss_curves(train_history, out_dir=out_dir, dpi=dpi)
    artifacts["learning_rate_schedule"] = save_learning_rate_schedule(train_history, out_dir=out_dir, dpi=dpi)
    artifacts["evaluation_metrics"] = save_eval_metrics(eval_results, out_dir=out_dir)

    if target_vars is None:
        target_vars = ["output_0", "output_1", "output_2"]

    artifacts["validation_per_variable_plot"] = save_per_variable_metric_bars(
        eval_results=eval_results,
        out_dir=out_dir,
        split_name="validation",
        dpi=dpi,
    )
    artifacts["test_per_variable_plot"] = save_per_variable_metric_bars(
        eval_results=eval_results,
        out_dir=out_dir,
        split_name="test",
        dpi=dpi,
    )

    artifacts["scatter_comparison"] = save_scatter_comparison(
        test_arrays=test_arrays,
        out_dir=out_dir,
        target_vars=target_vars,
        dpi=dpi,
        n_samples=int(vis_config.get("scatter_n_samples", 5000)),
    )
    artifacts["error_distributions"] = save_error_distributions(
        test_arrays=test_arrays,
        out_dir=out_dir,
        target_vars=target_vars,
        dpi=dpi,
    )
    artifacts["comparison_samples"] = save_prediction_comparisons(
        test_arrays=test_arrays,
        out_dir=out_dir,
        target_vars=target_vars,
        dpi=dpi,
        n_visualization_samples=int(vis_config.get("n_visualization_samples", 5)),
    )
    artifacts["timeseries_plots"] = save_time_series_comparisons(
        test_arrays=test_arrays,
        out_dir=out_dir,
        target_vars=target_vars,
        vis_config=vis_config,
        dpi=dpi,
    )

    return artifacts
