import numpy as np
import torch
import torch.nn.functional as F

from config import BATHY_VARS, BOUNDARY_VARS, PREVIOUS_BOUNDARY_STEPS, PREVIOUS_INPUT_STEPS, SCALER_PATH, WIND_VARS
from f_data_processing import import_scale


def build_loss(loss_name: str):
    name = (loss_name or "mse").lower()
    if name == "mse":
        return torch.nn.MSELoss()
    if name in ("l1", "mae"):
        return torch.nn.L1Loss()
    if name in ("weighted_physics", "ctp_front"):
        return None
    raise ValueError(f"Unsupported loss_function '{loss_name}'.")


def _elevation_channel_index() -> int:
    base_idx = PREVIOUS_INPUT_STEPS * len(WIND_VARS) + PREVIOUS_BOUNDARY_STEPS * len(BOUNDARY_VARS)
    if "elevation" in BATHY_VARS:
        return base_idx + BATHY_VARS.index("elevation")
    return base_idx


def _scaled_elevation_ocean_threshold() -> float:
    """Map physical sea level (0.0 m) to the scaled elevation space."""
    try:
        scalers = import_scale(SCALER_PATH)
        elevation_scaler = scalers.get("elevation") if isinstance(scalers, dict) else None
        if elevation_scaler is None:
            return 0.0

        transformed = elevation_scaler.transform(np.array([[0.0]], dtype=np.float64))
        return float(transformed[0, 0])
    except Exception:
        return 0.0


OCEAN_THRESHOLD_SCALED = _scaled_elevation_ocean_threshold()


def masked_mse(pred, target, mask, eps=1e-8):
    sq_err = (pred - target) ** 2
    return (sq_err * mask).sum() / torch.clamp(mask.sum(), min=eps)


def masked_huber(pred, target, mask, delta=1.0, eps=1e-8, weight=None):
    err = torch.abs(pred - target)
    huber = torch.where(err < delta, 0.5 * err**2, delta * (err - 0.5 * delta))
    if weight is not None:
        mask = mask * weight
    return (huber * mask).sum() / torch.clamp(mask.sum(), min=eps)


def gradient_loss(pred, target, mask, eps=1e-8):
    dy_p = pred[:, :, 1:, :] - pred[:, :, :-1, :]
    dx_p = pred[:, :, :, 1:] - pred[:, :, :, :-1]
    dy_t = target[:, :, 1:, :] - target[:, :, :-1, :]
    dx_t = target[:, :, :, 1:] - target[:, :, :, :-1]
    mask_dy = mask[:, :, 1:, :]
    mask_dx = mask[:, :, :, 1:]
    loss_dy = (torch.abs(dy_p - dy_t) * mask_dy).sum() / torch.clamp(mask_dy.sum(), min=eps)
    loss_dx = (torch.abs(dx_p - dx_t) * mask_dx).sum() / torch.clamp(mask_dx.sum(), min=eps)
    return loss_dy + loss_dx


def angular_loss(pred, target, mask, eps=1e-8):
    """
    Penalize the angle between predicted and target direction vectors.
    dot product of unit vectors = cos(angle_error), so loss = 1 - dot.
    This is rotation-aware and avoids the stripe artifact from independent MSE.
    """
    pred_sin, pred_cos = pred[:, 1:2], pred[:, 2:3]
    tgt_sin,  tgt_cos  = target[:, 1:2], target[:, 2:3]

    # Normalize predictions to unit circle
    pred_norm = torch.sqrt(pred_sin**2 + pred_cos**2 + eps)
    pred_sin_n = pred_sin / pred_norm
    pred_cos_n = pred_cos / pred_norm

    dot = pred_sin_n * tgt_sin + pred_cos_n * tgt_cos  # cosine similarity
    angle_loss = 1.0 - dot  # in [0, 2], 0 = perfect

    return (angle_loss * mask).sum() / torch.clamp(mask.sum(), min=eps)


def pdir_gradient_loss(pred, target, mask, eps=1e-8):
    """Gradient loss applied to both sin and cos channels."""
    pdir_mask_2ch = mask.expand(-1, 2, -1, -1)
    return gradient_loss(pred[:, 1:3], target[:, 1:3], pdir_mask_2ch, eps=eps)



def weighted_physics_loss(pred: torch.Tensor, target: torch.Tensor, elevation: torch.Tensor) -> torch.Tensor:
    """Ocean-masked weighted physics loss for [HSig, PDIR_sin, PDIR_cos]."""
    ocean_mask = (elevation < OCEAN_THRESHOLD_SCALED).float()
    land_mask  = 1.0 - ocean_mask

    if ocean_mask.sum().item() == 0:
        ocean_mask = torch.ones_like(elevation)
        land_mask  = torch.zeros_like(elevation)

    # Safe peak weight in [1, 3]: upweight large positive anomalies only.
    # Clamp denominator to ≥0.5 so standardized (near-zero or negative) batches
    # never cause division explosion. Clamp ratio to [0,1] for a bounded weight.
    hsig_target = target[:, 0:1]
    hsig_max = hsig_target.amax(dim=(2, 3), keepdim=True).clamp(min=0.5)
    peak_weight = 1.0 + 2.0 * (hsig_target / hsig_max).clamp(min=0.0, max=1.0)

    # HSig — ocean (weighted Huber + gradient) + land (soft anchor)
    hsig_ocean = masked_huber(pred[:, 0:1], target[:, 0:1], ocean_mask, weight=peak_weight)
    grad_loss  = gradient_loss(pred[:, 0:1], target[:, 0:1], ocean_mask)
    hsig_land  = masked_huber(pred[:, 0:1], target[:, 0:1], land_mask)

    # PDIR — ocean only
    pdir_mask   = ocean_mask.expand(-1, 2, -1, -1)
    pdir_loss   = masked_mse(pred[:, 1:3], target[:, 1:3], pdir_mask)
    norm        = pred[:, 1:2] ** 2 + pred[:, 2:3] ** 2
    circle_loss = masked_mse(norm, torch.ones_like(norm), ocean_mask)

    return (
        5.00 * hsig_ocean    +
        0.50 * grad_loss     +
        0.05 * hsig_land     +
        0.50 * pdir_loss     +   # reduced — angular_loss now handles this better
        3.00 * angular_loss(pred, target, ocean_mask) +  # NEW: dominant direction signal
        1.00 * pdir_gradient_loss(pred, target, ocean_mask) +  # NEW: smoothness
        0.10 * circle_loss       # slightly upweighted — unit norm matters more now
    )

def _ocean_mask(elevation: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    ocean = (elevation < OCEAN_THRESHOLD_SCALED).float()
    land = 1.0 - ocean
    if ocean.sum().item() == 0:
        ocean = torch.ones_like(elevation)
        land = torch.zeros_like(elevation)
    return ocean, land


def _masked_bce(pred: torch.Tensor, target: torch.Tensor, mask: torch.Tensor, pos_weight: torch.Tensor | None = None) -> torch.Tensor:
    eps = 1e-6
    pred = pred.clamp(eps, 1.0 - eps)
    bce = F.binary_cross_entropy(pred, target, reduction="none")
    if pos_weight is not None:
        bce = bce * (1.0 + (pos_weight - 1.0) * target)
    denom = mask.sum().clamp(min=1.0)
    return (bce * mask).sum() / denom


def _masked_mse(pred: torch.Tensor, target: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    denom = mask.sum().clamp(min=1.0)
    return (F.mse_loss(pred, target, reduction="none") * mask).sum() / denom


def _focal_bce(pred: torch.Tensor, target: torch.Tensor, mask: torch.Tensor, gamma: float = 2.0, alpha: float = 0.75) -> torch.Tensor:
    eps = 1e-6
    pred_c = pred.clamp(eps, 1.0 - eps)
    ce = -target * torch.log(pred_c) - (1 - target) * torch.log(1 - pred_c)
    pt = target * pred_c + (1 - target) * (1 - pred_c)
    focal = (1 - pt) ** gamma * ce
    weight = target * alpha + (1 - target) * (1 - alpha)
    denom = mask.sum().clamp(min=1.0)
    return (weight * focal * mask).sum() / denom


def _gradient_loss(pred: torch.Tensor, target: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    def grad_xy(t: torch.Tensor):
        gx = t[:, :, :, 1:] - t[:, :, :, :-1]
        gy = t[:, :, 1:, :] - t[:, :, :-1, :]
        return gx, gy

    px, py = grad_xy(pred)
    tx, ty = grad_xy(target)
    mx = mask[:, :, :, 1:]
    my = mask[:, :, 1:, :]

    loss_x = ((px - tx) ** 2 * mx).sum() / mx.sum().clamp(min=1.0)
    loss_y = ((py - ty) ** 2 * my).sum() / my.sum().clamp(min=1.0)
    return loss_x + loss_y


def _unit_circle_loss(sin_pred: torch.Tensor, cos_pred: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    norm = sin_pred**2 + cos_pred**2
    denom = mask.sum().clamp(min=1.0)
    return ((norm - 1.0) ** 2 * mask).sum() / denom


def ctp_front_loss(pred: torch.Tensor, target: torch.Tensor, elevation: torch.Tensor) -> torch.Tensor:
    ocean_mask, land_mask = _ocean_mask(elevation)

    front_pred = pred[:, 0:1]
    front_target = target[:, 0:1]

    focal = _focal_bce(front_pred, front_target, ocean_mask, gamma=2.0, alpha=0.75)
    grad = _gradient_loss(front_pred, front_target, ocean_mask)
    land_anchor = _masked_bce(front_pred, torch.zeros_like(front_pred), land_mask)

    pdir_mask = ocean_mask.expand(-1, 2, -1, -1)
    pdir_loss = _masked_mse(pred[:, 1:3], target[:, 1:3], pdir_mask)

    circle = _unit_circle_loss(pred[:, 1:2], pred[:, 2:3], ocean_mask)

    return 4.00 * focal + 1.00 * grad + 0.10 * land_anchor + 1.50 * pdir_loss + 0.05 * circle


def compute_loss(
    preds: torch.Tensor,
    targets: torch.Tensor,
    inputs: torch.Tensor,
    criterion,
    loss_name: str,
) -> torch.Tensor:
    name = (loss_name or "mse").lower()
    if name in ("weighted_physics", "ctp_front"):
        elev_idx = _elevation_channel_index()
        if inputs.size(1) <= elev_idx:
            raise ValueError(
                f"Elevation channel index {elev_idx} is out of bounds for input with {inputs.size(1)} channels."
            )
        elevation = inputs[:, elev_idx : elev_idx + 1, :, :]
        if name == "weighted_physics":
            return weighted_physics_loss(preds, targets, elevation)
        return ctp_front_loss(preds, targets, elevation)

    if criterion is None:
        raise ValueError(f"Loss '{loss_name}' requires a valid criterion or dedicated handler.")
    return criterion(preds, targets)
