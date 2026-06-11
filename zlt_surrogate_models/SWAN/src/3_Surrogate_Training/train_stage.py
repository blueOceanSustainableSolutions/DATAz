from pathlib import Path
import time

import torch
from torch.optim.lr_scheduler import CosineAnnealingWarmRestarts

from loss_functions import build_loss, compute_loss


def _resolve_device(device_name: str) -> str:
    if device_name == "cuda" and not torch.cuda.is_available():
        return "cpu"
    return device_name


def _build_optimizer(model, config: dict):
    name = (config.get("optimizer") or "adam").lower()
    lr = config.get("learning_rate", 1e-3)
    weight_decay = config.get("weight_decay", 0.0)

    if name == "adam":
        return torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)
    if name == "adamw":
        return torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    if name == "sgd":
        return torch.optim.SGD(model.parameters(), lr=lr, momentum=0.9, weight_decay=weight_decay)

    raise ValueError(f"Unsupported optimizer '{config.get('optimizer')}'.")


def _run_epoch(model, loader, criterion, device: str, loss_name: str, optimizer=None):
    is_train = optimizer is not None
    model.train(is_train)

    running_loss = 0.0
    n_samples = 0

    with torch.set_grad_enabled(is_train):
        for batch in loader:
            if len(batch) == 3:
                inputs, targets, _ = batch
            elif len(batch) == 2:
                inputs, targets = batch
            else:
                raise ValueError(f"Unexpected batch size {len(batch)}; expected 2 or 3 items.")

            inputs = inputs.to(device, non_blocking=True)
            targets = targets.to(device, non_blocking=True)

            # Check for NaN/Inf in inputs
            if torch.isnan(inputs).any() or torch.isinf(inputs).any():
                print(f"    WARNING: NaN/Inf detected in inputs. Skipping batch.")
                continue
            if torch.isnan(targets).any() or torch.isinf(targets).any():
                print(f"    WARNING: NaN/Inf detected in targets. Skipping batch.")
                continue

            preds = model(inputs)
            loss = compute_loss(preds, targets, inputs, criterion, loss_name)
            batch_size = inputs.size(0)

            # Check for NaN loss
            if torch.isnan(loss) or torch.isinf(loss):
                print(f"    WARNING: NaN/Inf loss detected. Skipping update.")
                if is_train:
                    optimizer.zero_grad(set_to_none=True)
                continue

            if is_train:
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                # Gradient clipping to prevent exploding gradients
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                optimizer.step()

            if batch_size > 0:
                running_loss += loss.item() * batch_size
                n_samples += batch_size

    if n_samples == 0:
        return float("inf")
    return running_loss / n_samples


def train_model(model, train_loader, val_loader, training_config: dict, model_dir: str | Path, model_name: str = "best_model"):
    """Train model and return history + checkpoint metadata."""
    model_dir = Path(model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)

    device = _resolve_device(training_config.get("device", "cpu"))
    model = model.to(device)

    # Validate loaders before training
    n_train = len(train_loader) if train_loader is not None else 0
    n_val = len(val_loader) if val_loader is not None else 0
    if n_train == 0:
        raise ValueError("FATAL: Training loader is empty!")
    if n_val == 0:
        print(f"  WARNING: Validation loader is empty ({n_val} batches). Validation loss will always be inf.")
        print(f"           This will trigger early stopping at epoch 1!")

    criterion = build_loss(training_config.get("loss_function", "mse"))
    loss_name = (training_config.get("loss_function", "mse") or "mse").lower()
    optimizer = _build_optimizer(model, training_config)

    # Learning rate scheduler: cosine annealing with warm restarts.
    # T_0=50 gives longer cycles (restarts at ~50, 150, 350 for 600 epochs),
    # allowing finer convergence between resets compared to the old T_0=20.
    scheduler = CosineAnnealingWarmRestarts(optimizer, T_0=50, T_mult=2, eta_min=1e-6)

    num_epochs = int(training_config.get("num_epochs", 1))
    early_stopping = bool(training_config.get("early_stopping", True))
    patience = int(training_config.get("patience", 10))
    min_delta = float(training_config.get("min_delta", 1e-4))
    save_best = bool(training_config.get("save_best_model", True))

    best_val = float("inf")
    best_epoch = -1
    epochs_without_improvement = 0

    history = {
        "epoch": [],
        "train_loss": [],
        "val_loss": [],
        "epoch_time_sec": [],
        "learning_rate": [],
    }

    ckpt_path = model_dir / f"{model_name}.pt"

    for epoch in range(1, num_epochs + 1):
        t0 = time.perf_counter()

        train_loss = _run_epoch(model, train_loader, criterion, device, loss_name=loss_name, optimizer=optimizer)
        val_loss = _run_epoch(model, val_loader, criterion, device, loss_name=loss_name, optimizer=None)

        epoch_time = time.perf_counter() - t0
        current_lr = float(optimizer.param_groups[0]["lr"])

        history["epoch"].append(epoch)
        history["train_loss"].append(train_loss)
        history["val_loss"].append(val_loss)
        history["epoch_time_sec"].append(epoch_time)
        history["learning_rate"].append(current_lr)

        improved = (best_val - val_loss) > min_delta
        if improved:
            best_val = val_loss
            best_epoch = epoch
            epochs_without_improvement = 0
            if save_best:
                torch.save(
                    {
                        "epoch": epoch,
                        "model_state_dict": model.state_dict(),
                        "optimizer_state_dict": optimizer.state_dict(),
                        "train_loss": train_loss,
                        "val_loss": val_loss,
                        "training_config": training_config,
                    },
                    ckpt_path,
                )
        else:
            epochs_without_improvement += 1

        print(
            f"  Epoch {epoch:03d}/{num_epochs} | "
            f"train_loss={train_loss:.6f} | val_loss={val_loss:.6f} | "
            f"lr={scheduler.get_last_lr()[0]:.2e} | "
            f"time={epoch_time:.2f}s | "
            f"Best Epoch={best_epoch:03d} (val_loss={best_val:.6f}) | "
        )

        scheduler.step(epoch)

        if early_stopping and epochs_without_improvement >= patience:
            print(f"  Early stopping triggered at epoch {epoch}. Best epoch: {best_epoch}.")
            break

    info = {
        "device": device,
        "best_epoch": best_epoch,
        "best_val_loss": best_val,
        "checkpoint_path": str(ckpt_path) if save_best else None,
    }
    return history, info


def load_model_checkpoint(model, checkpoint_path: str | Path, device: str = "cpu") -> dict:
    """Load model weights from a saved checkpoint file."""
    ckpt_path = Path(checkpoint_path)
    if not ckpt_path.exists():
        raise FileNotFoundError(f"Checkpoint file not found: {ckpt_path}")

    resolved_device = _resolve_device(device)
    checkpoint = torch.load(ckpt_path, map_location=resolved_device)

    if "model_state_dict" not in checkpoint:
        raise KeyError(f"Checkpoint does not contain 'model_state_dict': {ckpt_path}")

    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(resolved_device)

    return {
        "device": resolved_device,
        "best_epoch": checkpoint.get("epoch", None),
        "best_val_loss": checkpoint.get("val_loss", None),
        "checkpoint_path": str(ckpt_path),
    }


def import_model(model, checkpoint_path: str | Path, device: str = "cpu"):
    """Import model weights from checkpoint and return model + metadata."""
    info = load_model_checkpoint(model, checkpoint_path, device)
    best_val = info.get("best_val_loss")
    best_val_text = f"{best_val:.6f}" if isinstance(best_val, (int, float)) else "N/A"
    print(f"Model IMPORTED from {checkpoint_path} (epoch {info['best_epoch']}, val_loss={best_val_text})")
    return None, info