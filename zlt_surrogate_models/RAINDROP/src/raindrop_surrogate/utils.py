"""
utils.py — shared utilities for the underwater-acoustics surrogate.

Contents
--------
compute_physical_metrics   Physical-unit error metrics (Pa and dB)
load_model                 One-liner to restore a model from disk
save_checkpoint            Save model weights and training state
load_config                Load a YAML config with dot-access
"""

import os
from pathlib import Path
from typing import Dict, Any

import torch
import yaml



# Physical metrics


def compute_physical_metrics(
    preds: torch.Tensor,
    targets: torch.Tensor,
    stats: Dict[str, Any],
    use_pascal_input: bool,
) -> Dict[str, float]:
    """
    Compute MSE and MAE in both Pascal and dB re 1 µPa.

    Predictions and targets are assumed to be *normalised* (output of
    the model / dataset wrapper).  They are inverse-scaled to physical
    units using ``stats`` before computing the metrics.

    Parameters
    ----------
    preds, targets : torch.Tensor
        Normalised model outputs and ground-truth tensors.
    stats : dict
        Must contain ``stats["spl"]["min"]`` and ``stats["spl"]["max"]``.
    use_pascal_input : bool
        If the dataset was created with ``use_pascal=True``, the raw
        values are in Pa; otherwise they are already in dB re 1 µPa.

    Returns
    -------
    dict with keys: ``mse_pa``, ``mae_pa``, ``mse_db``, ``mae_db``.
    """
    s_min, s_max = stats["spl"]["min"], stats["spl"]["max"]

    raw_preds   = torch.clamp(preds   * (s_max - s_min) + s_min, min=1e-12)
    raw_targets = torch.clamp(targets * (s_max - s_min) + s_min, min=1e-12)

    if use_pascal_input:
        pa_preds,   pa_targets   = raw_preds, raw_targets
        db_preds   = 20 * torch.log10(pa_preds   / 1e-6)
        db_targets = 20 * torch.log10(pa_targets / 1e-6)
    else:
        db_preds,   db_targets   = raw_preds, raw_targets
        pa_preds   = 1e-6 * torch.pow(10.0, db_preds   / 20.0)
        pa_targets = 1e-6 * torch.pow(10.0, db_targets / 20.0)

    return {
        "mse_pa": torch.mean((pa_preds - pa_targets) ** 2).item(),
        "mae_pa": torch.mean(torch.abs(pa_preds - pa_targets)).item(),
        "mse_db": torch.mean((db_preds - db_targets) ** 2).item(),
        "mae_db": torch.mean(torch.abs(db_preds - db_targets)).item(),
    }



# Model I/O


def save_checkpoint(
    model: torch.nn.Module,
    optimizer: torch.optim.Optimizer,
    epoch: int,
    val_loss: float,
    path: str,
) -> None:
    """
    Save model weights, optimiser state, epoch, and validation loss.

    Parameters
    ----------
    model     : the PyTorch model to persist.
    optimizer : the current optimiser (state is saved for resuming).
    epoch     : current epoch index.
    val_loss  : best validation loss achieved so far.
    path      : full file path (e.g. ``checkpoints/best.pth``).
    """
    os.makedirs(Path(path).parent, exist_ok=True)
    torch.save(
        {
            "epoch":      epoch,
            "val_loss":   val_loss,
            "model_state_dict":     model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
        },
        path,
    )


def load_model(
    model: torch.nn.Module,
    path: str,
    device: torch.device = torch.device("cpu"),
) -> torch.nn.Module:
    """
    Load model weights from a checkpoint produced by :func:`save_checkpoint`
    *or* a plain ``torch.save(model.state_dict(), path)`` file.

    Parameters
    ----------
    model  : uninitialised model instance (architecture must match).
    path   : path to the ``.pth`` / ``.pt`` checkpoint file.
    device : device to map the weights onto.

    Returns
    -------
    The model with weights loaded, set to eval mode.
    """
    checkpoint = torch.load(path, map_location=device)

    # Support both full checkpoint dicts and bare state-dicts
    state_dict = (
        checkpoint["model_state_dict"]
        if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint
        else checkpoint
    )
    model.load_state_dict(state_dict)
    model.to(device)
    model.eval()
    return model



# Config loading


class _DotDict(dict):
    """A dict subclass that allows attribute-style access."""
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__

    def __init__(self, data: dict):
        super().__init__({
            k: _DotDict(v) if isinstance(v, dict) else v
            for k, v in data.items()
        })


def load_config(path: str) -> _DotDict:
    """
    Load a YAML config file and return it as a dot-accessible dict.

    Example
    -------
    >>> cfg = load_config("configs/default.yaml")
    >>> cfg.training.lr
    0.0001
    """
    with open(path, "r") as f:
        raw = yaml.safe_load(f)
    return _DotDict(raw)
