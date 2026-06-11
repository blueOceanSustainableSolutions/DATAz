from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def ensure_dir(path: str | Path) -> Path:
    out = Path(path)
    out.mkdir(parents=True, exist_ok=True)
    return out


def save_prediction_snapshot_all_outputs(
    snapshot_data: dict | None,
    out_dir: str | Path,
    target_vars: list[str],
    dpi: int = 150,
) -> str | None:
    """Save one figure with target/prediction/error for all output variables."""
    if snapshot_data is None:
        return None

    out = ensure_dir(out_dir)
    fig_path = out / "prediction_snapshot_all_outputs.png"

    y_true = snapshot_data["y_true"]
    y_pred = snapshot_data["y_pred"]
    n_vars = min(len(target_vars), y_true.shape[0], y_pred.shape[0])

    fig, axes = plt.subplots(n_vars, 3, figsize=(13, 4 * n_vars), dpi=dpi)
    if n_vars == 1:
        axes = np.expand_dims(axes, axis=0)

    for c in range(n_vars):
        var_name = target_vars[c]
        true_map = y_true[c]
        pred_map = y_pred[c]
        err_map = pred_map - true_map

        cmin = float(np.nanmin([true_map.min(), pred_map.min()]))
        cmax = float(np.nanmax([true_map.max(), pred_map.max()]))

        im0 = axes[c, 0].imshow(true_map, cmap="viridis", vmin=cmin, vmax=cmax)
        axes[c, 0].set_title(f"{var_name} target")
        plt.colorbar(im0, ax=axes[c, 0], fraction=0.046, pad=0.04)

        im1 = axes[c, 1].imshow(pred_map, cmap="viridis", vmin=cmin, vmax=cmax)
        axes[c, 1].set_title(f"{var_name} prediction")
        plt.colorbar(im1, ax=axes[c, 1], fraction=0.046, pad=0.04)

        # Error map: symmetric RdBu_r centered at zero (white)
        err_min = float(np.nanmin(err_map))
        err_max = float(np.nanmax(err_map))
        abs_max = max(abs(err_min), abs(err_max))
        if abs_max == 0:
            abs_max = 0.1

        im2 = axes[c, 2].imshow(err_map, cmap="RdBu_r", vmin=-abs_max, vmax=abs_max)
        axes[c, 2].set_title(f"{var_name} error")
        cbar2 = plt.colorbar(im2, ax=axes[c, 2], fraction=0.046, pad=0.04)
        if err_min < err_max:
            cbar2.ax.set_ylim(err_min, err_max)

        for col in range(3):
            axes[c, col].set_xticks([])
            axes[c, col].set_yticks([])

    plt.tight_layout()
    plt.savefig(fig_path)
    plt.close()
    return str(fig_path)


def save_per_variable_metric_bars(
    eval_results: dict,
    out_dir: str | Path,
    split_name: str,
    dpi: int = 150,
) -> str | None:
    """Save bar charts for per-variable metrics if available in eval_results."""
    key = f"{split_name}_per_variable"
    per_var = eval_results.get(key)
    if not per_var:
        return None

    out = ensure_dir(out_dir)
    fig_path = out / f"{split_name}_per_variable_metrics.png"

    var_names = list(per_var.keys())
    metrics = ["rmse", "mae", "r2", "mape"]

    fig, axes = plt.subplots(2, 2, figsize=(14, 8), dpi=dpi)
    axes = axes.ravel()

    x = np.arange(len(var_names))
    for i, metric in enumerate(metrics):
        values = [per_var[var].get(metric, np.nan) for var in var_names]
        axes[i].bar(x, values)
        axes[i].set_title(f"{split_name} {metric.upper()} by output")
        axes[i].set_xticks(x)
        axes[i].set_xticklabels(var_names)
        axes[i].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(fig_path)
    plt.close()
    return str(fig_path)
