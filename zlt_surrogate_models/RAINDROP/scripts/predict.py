import os
import sys
import time
import argparse
import numpy as np
import torch

# Ensure src/ folder is visible to the runtime context
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from raindrop_surrogate.utils import load_config
from raindrop_surrogate.model import RadialAcousticSurrogate

def get_stats_cache_path(cfg):
    cache_dir = cfg.data.get("cache_dir", "cache")
    return os.path.join(cache_dir, "scaling_stats.pth")

def load_or_compute_stats(cfg):
    """
    Lean Import Strategy optimization loop: Checks for existing cached arrays.
    Only handles heavy framework installations if the file is completely missing.
    """
    cache_path = get_stats_cache_path(cfg)
    
    if os.path.exists(cache_path):
        return torch.load(cache_path)
    
    print("'scaling_stats.pth' not found. Computing dataset statistics and spatial parameters.")
    
    # Isolated heavy imports to prevent overhead on standard production runs
    from torch.utils.data import random_split
    from raindrop_surrogate.dataset import AcousticDataset, scale_data
    
    base_dataset = AcousticDataset(
        ais_dir=cfg.data.ais_dir, spl_dir=cfg.data.spl_dir,
        example_nc_path=cfg.data.example_nc_path, bathy_csv=cfg.data.bathy_csv,
        coastline_shp=cfg.data.coastline_shp, cache_dir=cfg.data.get("cache_dir", "cache"),
        crop_size=cfg.data.crop_size, use_63hz=cfg.data.use_63hz,
        use_pascal=cfg.data.use_pascal, num_rays=cfg.data.num_rays, ray_points=cfg.data.ray_points
    )
    
    torch.manual_seed(cfg.training.get("seed", 42))
    total_len = len(base_dataset)
    train_sz = int(cfg.training.train_split * total_len)
    val_sz = int(cfg.training.val_split * total_len)
    test_sz = total_len - train_sz - val_sz
    
    train_sub, val_sub, test_sub = random_split(base_dataset, [train_sz, val_sz, test_sz])
    _, _, _, stats = scale_data(train_sub, val_sub, test_sub)
    
    # Embed critical coordinate maps and physical parameters directly inside the metadata dictionary
    stats["spatial_grid"] = {
        "lat_min": float(base_dataset.lat_min),
        "lat_max": float(base_dataset.lat_max),
        "lon_min": float(base_dataset.lon_min),
        "lon_max": float(base_dataset.lon_max),
        "target_lats": base_dataset.target_lats.tolist(),
        "target_lons": base_dataset.target_lons.tolist(),
        "crop_size": int(base_dataset.crop_size),
        "num_rays": int(base_dataset.num_rays),
        "ray_points": int(base_dataset.ray_points),
        "use_pascal": bool(base_dataset.use_pascal),
        "aspect_ratio": float(base_dataset.aspect_ratio),
    }
    
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    torch.save(stats, cache_path)
    print(f"Statistics and spatial parameters cached successfully to: {cache_path}\n")
    return stats

def extract_radials_standalone(ship_lat, ship_lon, bathy_grid, spatial_meta):
    """Standalone vectorized polar extraction pipeline avoiding base Dataset overhead."""
    import scipy.ndimage as ndimage
    
    target_lats = np.array(spatial_meta["target_lats"])
    target_lons = np.array(spatial_meta["target_lons"])
    crop_size = spatial_meta["crop_size"]
    num_rays = spatial_meta["num_rays"]
    ray_points = spatial_meta["ray_points"]
    
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
    bathy_rays = ndimage.map_coordinates(bathy_grid, coords, order=1).reshape(num_rays, ray_points)
    
    return torch.from_numpy(bathy_rays).float(), torch.from_numpy(t_max.astype(np.float32)).float()

def predict_single_ship(model, stats, raw_ship_features, bathy_grid, device):
    """
    Executes an isolated scaling and inference pass for an explicit observation array.
    Expects raw_ship_features list or array: [lat, lon, speed, feature_3, length]
    """
    spatial_meta = stats["spatial_grid"]
    
    # 1. Coordinate Validation Check
    lat, lon = raw_ship_features[0], raw_ship_features[1]
    if not (spatial_meta["lat_min"] <= lat <= spatial_meta["lat_max"]) or \
       not (spatial_meta["lon_min"] <= lon <= spatial_meta["lon_max"]):
        raise ValueError(f"Target ship position ({lat}, {lon}) is outside cached model boundaries.")
        
    # 2. Extract Polar Structural Arrays
    bathy_rays, t_max = extract_radials_standalone(lat, lon, bathy_grid, spatial_meta)
    
    # 3. Apply Decoupled Scaling Transformation Layouts
    scaled_ais = torch.tensor(raw_ship_features, dtype=torch.float32).clone()
    
    # Min-max spatial normalization using static grid boundaries
    scaled_ais[0] = (scaled_ais[0] - spatial_meta["lat_min"]) / (spatial_meta["lat_max"] - spatial_meta["lat_min"])
    scaled_ais[1] = (scaled_ais[1] - spatial_meta["lon_min"]) / (spatial_meta["lon_max"] - spatial_meta["lon_min"])
    
    # Z-score normalization for speed and length indices (columns 2 & 4)
    m = stats["ais"]["means"]
    s = stats["ais"]["stds"]
    scaled_ais[[2, 4]] = (scaled_ais[[2, 4]] - m) / s
    
    # Min-max bathymetry normalization
    b_min, b_max = stats["bathy"]["min"], stats["bathy"]["max"]
    water_mask = (bathy_rays > 0).float()
    scaled_bathy = torch.clamp((bathy_rays - b_min) / (b_max - b_min + 1e-8), 0, 1) * water_mask

    # 4. Construct Inference Batches and Forward Pass
    bathy_in = scaled_bathy.unsqueeze(0).to(device)
    ais_in = scaled_ais.unsqueeze(0).to(device)
    tmax_in = t_max.unsqueeze(0).to(device)
    
    with torch.no_grad():
        scaled_preds = model(bathy_in, ais_in, tmax_in).squeeze(0).cpu()
        
    # 5. Reverse Scaling Transformation to Real Physical Units
    s_min, s_max = stats["spl"]["min"], stats["spl"]["max"]
    physical_preds = (scaled_preds * (s_max - s_min + 1e-8)) + s_min
    physical_preds = physical_preds * water_mask  # Force structural zeroing over land zones
    
    # If the network output represents Pascal variations, process reverse-decibel scaling
    if spatial_meta["use_pascal"]:
        # Convert back from raw linear pressure maps to dB re 1 uPa
        physical_preds = 20.0 * torch.log10(torch.clamp(physical_preds / 1e-6, min=1.0))
        physical_preds = physical_preds * water_mask

    return physical_preds.numpy()

def parse_args():
    parser = argparse.ArgumentParser(description="Swift Production Surrogate Inference Interface")
    parser.add_argument("--config", type=str, default="configs/default.yaml")
    parser.add_argument("--lat", type=float, required=True, help="Target ship latitude coordinate")
    parser.add_argument("--lon", type=float, required=True, help="Target ship longitude coordinate")
    parser.add_argument("--speed", type=float, default=12.5, help="Ship speed parameter")
    parser.add_argument("--type", type=float, default=0.0, help="Ship type feature")
    parser.add_argument("--length", type=float, default=180.0, help="Physical ship vessel length metric")
    parser.add_argument("--output", type=str, default="results/prediction.npy", help="Target output array destination")
    return parser.parse_args()

def main():
    args = parse_args()
    cfg = load_config(args.config)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    # Load cached parameters or lazy evaluate them on initial execution
    stats = load_or_compute_stats(cfg)
    crop_size = stats["spatial_grid"]["crop_size"]
    # Retrieve aspect_ratio safely with a default fallback of 1.0 for legacy cache compatibility
    aspect_ratio = stats["spatial_grid"].get("aspect_ratio", 1.0)
    cache_dir = cfg.data.get("cache_dir", "cache")
    
    # Swift-load localized static grid arrays bypassing base Dataset instantiations
    bathy_path = os.path.join(cache_dir, f"bathy_aligned_{crop_size}.npy")
    if not os.path.exists(bathy_path):
        raise FileNotFoundError(f"Static layout missing at: {bathy_path}. Please execute 'train.py' once.")
    bathy_grid = np.load(bathy_path)

    # Initialize model network wrapper using the cached aspect_ratio
    model = RadialAcousticSurrogate(
        bathy_latent=cfg.model.bathy_latent,
        ais_latent=cfg.model.ais_latent,
        crop_size=crop_size,
        aspect_ratio=aspect_ratio
    ).to(device)

    checkpoint_path = cfg.evaluation.checkpoint_path

    if os.path.exists(checkpoint_path):
        checkpoint = torch.load(checkpoint_path, map_location=device)
        model.load_state_dict(checkpoint["model_state_dict"])
    else:
        # Raise an explicit error instead of falling back to random garbage weights
        raise FileNotFoundError(
            f"Critical Error: Model checkpoint not found at '{checkpoint_path}'. "
            "Inference cannot proceed without trained weights."
        )

    model.eval()

    # Consolidate raw observation array structures
    ship_features = [args.lat, args.lon, args.speed, args.type, args.length]
    
    print(f"Evaluating sound map output for Vessel at: Lat={args.lat}, Lon={args.lon}...")
    t0 = time.perf_counter()
    prediction_radial = predict_single_ship(model, stats, ship_features, bathy_grid, device)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    print(f"Prediction execution completed in {elapsed_ms:.2f} ms")
    
    # Save processed prediction matrix out to disk destination
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    np.save(args.output, prediction_radial)
    print(f"Radial prediction matrix saved successfully -> {args.output}")

if __name__ == "__main__":
    main()