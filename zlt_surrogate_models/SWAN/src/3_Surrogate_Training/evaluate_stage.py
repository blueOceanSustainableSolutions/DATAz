import math
from pathlib import Path

import numpy as np
import torch


def _resolve_device(device_name: str) -> str:
    if device_name == "cuda" and not torch.cuda.is_available():
        return "cpu"
    return device_name


def _compute_metrics(y_true: torch.Tensor, y_pred: torch.Tensor, eps: float = 1e-8) -> dict[str, float]:

    if y_true.numel() == 0:
        return {"rmse": float("nan"), "mae": float("nan"), "r2": float("nan"), "mape": float("nan")}

    err = y_pred - y_true
    abs_err = torch.abs(err)

    mse = torch.mean(err ** 2)
    rmse = torch.sqrt(mse)
    mae = torch.mean(abs_err)

    true_mean = torch.mean(y_true)
    ss_res = torch.sum(err ** 2)
    ss_tot = torch.sum((y_true - true_mean) ** 2)
    r2 = 1.0 - (ss_res / (ss_tot + eps)) if ss_tot > eps else torch.tensor(float("nan"), device=y_true.device)

    denom = torch.clamp(torch.abs(y_true), min=eps)
    mape = torch.mean(abs_err / denom) * 100.0

    return {
        "rmse": float(rmse.detach().cpu()),
        "mae": float(mae.detach().cpu()),
        "r2": float(r2.detach().cpu()),
        "mape": float(mape.detach().cpu()),
    }


def _compute_per_variable_metrics(
    y_true: torch.Tensor,
    y_pred: torch.Tensor,
    target_vars: list[str] | None,
) -> dict[str, dict[str, float]]:
    if target_vars is None:
        target_vars = [f"var_{i}" for i in range(y_true.shape[1])]

    n_channels = min(y_true.shape[1], y_pred.shape[1], len(target_vars))
    out = {}
    for idx in range(n_channels):
        out[target_vars[idx]] = _compute_metrics(y_true[:, idx : idx + 1], y_pred[:, idx : idx + 1])
    return out


def _inverse_scale_targets(y: torch.Tensor, target_vars: list[str], scalers: dict) -> torch.Tensor:
    """Inverse transform output channels back to physical units using target variable scalers."""
    y_np = y.detach().cpu().numpy().astype(np.float64, copy=True)

    n_channels = y_np.shape[1]
    for ch_idx, var_name in enumerate(target_vars[:n_channels]):
        scaler = scalers.get(var_name)
        if scaler is None:
            continue

        flat = y_np[:, ch_idx, :, :].reshape(-1)
        finite = np.isfinite(flat)
        if finite.any():
            flat[finite] = scaler.inverse_transform(flat[finite].reshape(-1, 1)).reshape(-1)
        y_np[:, ch_idx, :, :] = flat.reshape(y_np[:, ch_idx, :, :].shape)

    return torch.from_numpy(y_np)


def evaluate_model(
    model,
    loader,
    device: str = "cpu",
    target_vars: list[str] | None = None,
    scalers: dict | None = None,
    return_predictions: bool = False,
):
    """Evaluate a model on a dataloader and return aggregate metrics."""
    resolved_device = _resolve_device(device)
    model = model.to(resolved_device)
    model.eval()

    y_true_batches = []
    y_pred_batches = []
    time_batches = []

    with torch.no_grad():
        for batch in loader:
            if len(batch) == 3:
                inputs, targets, batch_times = batch
            elif len(batch) == 2:
                inputs, targets = batch
                batch_times = None
            else:
                raise ValueError(f"Unexpected batch size {len(batch)}; expected 2 or 3 items.")

            inputs = inputs.to(resolved_device, non_blocking=True)
            targets = targets.to(resolved_device, non_blocking=True)

            preds = model(inputs)
            y_pred_batches.append(preds)
            y_true_batches.append(targets)
            if batch_times is not None:
                time_batches.extend(batch_times)

    if not y_true_batches:
        empty_metrics = {"rmse": float("nan"), "mae": float("nan"), "r2": float("nan"), "mape": float("nan")}
        if return_predictions:
            return {"metrics": empty_metrics, "y_true": None, "y_pred": None}
        return empty_metrics

    y_true = torch.cat(y_true_batches, dim=0)
    y_pred = torch.cat(y_pred_batches, dim=0)

    if target_vars is not None and scalers is not None:
        y_true = _inverse_scale_targets(y_true, target_vars=target_vars, scalers=scalers)
        y_pred = _inverse_scale_targets(y_pred, target_vars=target_vars, scalers=scalers)

    metrics = _compute_metrics(y_true=y_true, y_pred=y_pred)

    if return_predictions:
        payload = {
            "metrics": metrics,
            "y_true": y_true,
            "y_pred": y_pred,
        }
        if time_batches:
            payload["time_labels"] = [str(t) for t in time_batches]
        return payload
    return metrics


def run_evaluation(
    model,
    val_loader,
    test_loader,
    eval_config: dict,
    device: str = "cpu",
    target_vars: list[str] | None = None,
    scalers: dict | None = None,
    return_test_snapshot: bool = False,
    return_test_arrays: bool = False,
) -> dict[str, dict[str, float]]:
    """Run validation and test evaluation using configured metric names."""
    requested = [m.lower() for m in eval_config.get("metrics", ["rmse", "mae", "r2", "mape"])]

    val_all = evaluate_model(
        model=model,
        loader=val_loader,
        device=device,
        target_vars=target_vars,
        scalers=scalers,
    )
    if return_test_snapshot:
        test_eval = evaluate_model(
            model=model,
            loader=test_loader,
            device=device,
            target_vars=target_vars,
            scalers=scalers,
            return_predictions=True,
        )
        test_all = test_eval["metrics"]
    else:
        test_eval = None
        test_all = evaluate_model(
            model=model,
            loader=test_loader,
            device=device,
            target_vars=target_vars,
            scalers=scalers,
        )

    val_metrics = {k: v for k, v in val_all.items() if k in requested}
    test_metrics = {k: v for k, v in test_all.items() if k in requested}

    result = {
        "validation": val_metrics,
        "test": test_metrics,
    }

    if eval_config.get("compute_per_variable", False):
        val_pred = evaluate_model(
            model=model,
            loader=val_loader,
            device=device,
            target_vars=target_vars,
            scalers=scalers,
            return_predictions=True,
        )
        test_pred = evaluate_model(
            model=model,
            loader=test_loader,
            device=device,
            target_vars=target_vars,
            scalers=scalers,
            return_predictions=True,
        )

        if val_pred["y_true"] is not None and val_pred["y_pred"] is not None:
            result["validation_per_variable"] = _compute_per_variable_metrics(
                val_pred["y_true"],
                val_pred["y_pred"],
                target_vars,
            )

        if test_pred["y_true"] is not None and test_pred["y_pred"] is not None:
            result["test_per_variable"] = _compute_per_variable_metrics(
                test_pred["y_true"],
                test_pred["y_pred"],
                target_vars,
            )

    if return_test_snapshot:
        snapshot = None
        if test_eval is not None and test_eval["y_true"] is not None and test_eval["y_pred"] is not None:
            snapshot = {
                "y_true": test_eval["y_true"][0].detach().cpu().numpy(),
                "y_pred": test_eval["y_pred"][0].detach().cpu().numpy(),
            }
        result["test_snapshot"] = snapshot

    if return_test_arrays:
        arrays = None
        if test_eval is not None and test_eval["y_true"] is not None and test_eval["y_pred"] is not None:
            arrays = {
                "y_true": test_eval["y_true"].detach().cpu().numpy(),
                "y_pred": test_eval["y_pred"].detach().cpu().numpy(),
            }
            if "time_labels" in test_eval:
                arrays["time_labels"] = test_eval["time_labels"]
        result["test_arrays"] = arrays

    return result
