import os
import sys
import argparse
import pickle
import numpy as np
import pandas as pd
import torch
import scipy.ndimage as ndimage
import matplotlib.pyplot as plt
from tqdm import tqdm

# Ensure src/ folder is visible to the runtime context
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from raindrop_surrogate.utils import load_config
from raindrop_surrogate.model import RadialAcousticSurrogate

def get_stats_cache_path(cfg):
    cache_dir = cfg.data.get("cache_dir", "cache")
    return os.path.join(cache_dir, "scaling_stats.pth")

def load_or_compute_stats(cfg):
    cache_path = get_stats_cache_path(cfg)
    if os.path.exists(cache_path):
        return torch.load(cache_path)
    raise FileNotFoundError(f"Scaling stats missing at {cache_path}. Run train.py first.")

def extract_radials_standalone(ship_lat, ship_lon, bathy_grid, spatial_meta):
    """Standalone vectorized polar extraction pipeline."""
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

def polar_to_cartesian(prediction_radial, t_max, ship_lat, ship_lon, spatial_meta):
    """Interpolates a vessel-centric radial acoustic prediction back onto the global Cartesian ROI grid."""
    crop_size = spatial_meta["crop_size"]
    num_rays = spatial_meta["num_rays"]
    ray_points = spatial_meta["ray_points"]
    
    target_lats = np.array(spatial_meta["target_lats"])
    target_lons = np.array(spatial_meta["target_lons"])
    
    lat_idx = np.interp(ship_lat, target_lats, np.arange(crop_size))
    lon_idx = np.interp(ship_lon, target_lons, np.arange(crop_size))
    
    # Create Cartesian target mesh
    Y, X = np.indices((crop_size, crop_size))
    dy = Y - lat_idx
    dx = X - lon_idx
    
    # Calculate geometric angle and grid distance
    theta = np.mod(np.arctan2(dy, dx), 2 * np.pi)
    theta_idx = (theta / (2 * np.pi)) * num_rays
    dist = np.hypot(dx, dy)
    
    # Interpolate t_max at each angle to normalize distance
    t_max_interp = ndimage.map_coordinates(t_max, [theta_idx], order=1, mode='wrap')
    
    # Map normalized distance to the radial ray point indices
    r_idx = np.zeros_like(dist)
    valid_mask = dist <= (t_max_interp + 1e-5)
    r_idx[valid_mask] = (dist[valid_mask] / (t_max_interp[valid_mask] + 1e-8)) * (ray_points - 1)
    r_idx[~valid_mask] = ray_points  # Push invalid spatial coords out-of-bounds
    
    # Perform 2D bilinear interpolation from the predicted radial map to the Cartesian grid
    coords = np.stack([theta_idx, r_idx])
    cart_spl = ndimage.map_coordinates(prediction_radial, coords, order=1, cval=0.0, mode='nearest')
    
    # Explicitly clear areas outside the ray tracing boundaries
    cart_spl[~valid_mask] = 0.0
    return cart_spl

def parse_args():
    parser = argparse.ArgumentParser(description="Multi-Ship Batch Inference from Pickle File or Folder")
    parser.add_argument("--config", type=str, default="configs/default.yaml")
    parser.add_argument("--input", type=str, required=True, help="Path to a single AIS pickle file OR a directory of AIS pickle files")
    parser.add_argument("--batch-size", type=int, default=32, help="GPU batch size per forward pass")
    parser.add_argument("--output-dir", type=str, default="results/batch_inference", help="Directory for output maps")
    return parser.parse_args()

def save_empty_output(output_dir, time_str, crop_size):
    base_filename = os.path.join(output_dir, f"spl_map_{time_str}")
    empty_map = np.zeros((crop_size, crop_size), dtype=np.float32)
    with open(base_filename + ".pkl", "wb") as f:
        pickle.dump(empty_map, f)
    print(f"[{time_str}] No valid AIS data found or file missing/empty. Saved 0s matrix to {base_filename}.pkl")

def process_single_pickle(file_path, model, device, bathy_grid, water_mask, stats, spatial_meta, args):
    crop_size = spatial_meta["crop_size"]
    filename_base = os.path.basename(file_path)
    time_str = os.path.splitext(filename_base)[0].replace("AIS_", "").replace(":", "")

    # 1. Read input pickle
    try:
        df = pd.read_pickle(file_path)
        if df.empty:
            save_empty_output(args.output_dir, time_str, crop_size)
            return
    except (FileNotFoundError, EOFError, Exception) as e:
        save_empty_output(args.output_dir, time_str, crop_size)
        return

    # 2. Accumulate Acoustic Fields across Batches
    accumulated_power = np.zeros((crop_size, crop_size), dtype=np.float32)
    valid_ships = 0
    
    for i in range(0, len(df), args.batch_size):
        batch_df = df.iloc[i : i + args.batch_size]
        batch_bathy, batch_ais, batch_tmax, batch_meta = [], [], [], []
        
        for _, row in batch_df.iterrows():
            lat, lon = row["Latitude"], row["Longitude"]
            sog, stype, length = row["Velocity [kts]"], row["Type"], row["Length [m]"]
            
            # Filter bounded vessels
            if not (spatial_meta["lat_min"] <= lat <= spatial_meta["lat_max"]) or \
               not (spatial_meta["lon_min"] <= lon <= spatial_meta["lon_max"]):
                continue
            
            # Polar spatial extraction & normalization
            bathy_rays, t_max = extract_radials_standalone(lat, lon, bathy_grid, spatial_meta)
            
            scaled_ais = torch.tensor([lat, lon, sog, stype, length], dtype=torch.float32)
            scaled_ais[0] = (scaled_ais[0] - spatial_meta["lat_min"]) / (spatial_meta["lat_max"] - spatial_meta["lat_min"])
            scaled_ais[1] = (scaled_ais[1] - spatial_meta["lon_min"]) / (spatial_meta["lon_max"] - spatial_meta["lon_min"])
            
            m, s = stats["ais"]["means"], stats["ais"]["stds"]
            scaled_ais[[2, 4]] = (scaled_ais[[2, 4]] - m) / s
            
            b_min, b_max = stats["bathy"]["min"], stats["bathy"]["max"]
            ship_water_mask = (bathy_rays > 0).float()
            scaled_bathy = torch.clamp((bathy_rays - b_min) / (b_max - b_min + 1e-8), 0, 1) * ship_water_mask

            batch_bathy.append(scaled_bathy)
            batch_ais.append(scaled_ais)
            batch_tmax.append(t_max)
            batch_meta.append({'lat': lat, 'lon': lon, 't_max': t_max.numpy()})

        if not batch_bathy:
            continue

        # Inference
        bathy_in = torch.stack(batch_bathy).to(device)
        ais_in = torch.stack(batch_ais).to(device)
        tmax_in = torch.stack(batch_tmax).to(device)

        with torch.no_grad():
            scaled_preds = model(bathy_in, ais_in, tmax_in).cpu()
        
        # Inverse Scaling
        s_min, s_max = stats["spl"]["min"], stats["spl"]["max"]
        physical_preds = (scaled_preds * (s_max - s_min + 1e-8)) + s_min
        
        if spatial_meta["use_pascal"]:
            physical_preds = 20.0 * torch.log10(torch.clamp(physical_preds / 1e-6, min=1.0))

        # Accumulate linear acoustic power
        for idx in range(len(physical_preds)):
            pred_radial = physical_preds[idx].numpy()
            cart_spl_db = polar_to_cartesian(pred_radial, batch_meta[idx]['t_max'], batch_meta[idx]['lat'], batch_meta[idx]['lon'], spatial_meta)
            linear_power = 10.0 ** (cart_spl_db / 10.0)
            accumulated_power += linear_power
            valid_ships += 1

    # 3. Save Output Artifacts
    base_filename = os.path.join(args.output_dir, f"spl_map_{time_str}")
    
    if valid_ships > 0:
        total_spl_db = 10.0 * np.log10(accumulated_power + 1e-12)
        total_spl_db *= water_mask
    else:
        total_spl_db = np.zeros((crop_size, crop_size), dtype=np.float32)
        
    # Pickle export
    with open(base_filename + ".pkl", "wb") as f:
        pickle.dump(total_spl_db, f)

    # PNG export
    plt.figure(figsize=(10, 8))
    plt.imshow(total_spl_db, cmap="jet", origin="lower", 
               extent=[spatial_meta["lon_min"], spatial_meta["lon_max"], 
                       spatial_meta["lat_min"], spatial_meta["lat_max"]])
    plt.colorbar(label="Cumulative SPL (dB re 1 $\mu$Pa)")
    
    display_time = df["Time"].iloc[0] if not df.empty else time_str
    plt.title(f"Aggregated Acoustic Map - {display_time} ({valid_ships} ships)")
    plt.xlabel("Longitude")
    plt.ylabel("Latitude")
    
    plt.contour((bathy_grid <= 0), levels=[0.5], colors='black', linewidths=0.5, 
                extent=[spatial_meta["lon_min"], spatial_meta["lon_max"], 
                        spatial_meta["lat_min"], spatial_meta["lat_max"]])

    plt.savefig(base_filename + ".png", dpi=150, bbox_inches="tight")
    plt.close()

def main():
    args = parse_args()
    cfg = load_config(args.config)
    os.makedirs(args.output_dir, exist_ok=True)
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Executing batch predictions using: {device}")
    
    # 1. Determine input file list (Directory vs Single File)
    if os.path.isdir(args.input):
        input_files = sorted([
            os.path.join(args.input, f) for f in os.listdir(args.input)
            if f.endswith(".pickle") or f.endswith(".pkl")
        ])
        print(f"Directory detected: Found {len(input_files)} AIS pickle files to process.")
    elif os.path.isfile(args.input):
        input_files = [args.input]
        print(f"Single file detected: Processing {args.input}")
    else:
        raise FileNotFoundError(f"Input path '{args.input}' does not exist.")

    if not input_files:
        print("No pickle files found to process.")
        return

    # 2. Load Caches and Model
    stats = load_or_compute_stats(cfg)
    spatial_meta = stats["spatial_grid"]
    crop_size = spatial_meta["crop_size"]
    
    bathy_path = os.path.join(cfg.data.get("cache_dir", "cache"), f"bathy_aligned_{crop_size}.npy")
    bathy_grid = np.load(bathy_path)
    water_mask = (bathy_grid > 0).astype(np.float32)

    model = RadialAcousticSurrogate(
        bathy_latent=cfg.model.bathy_latent,
        ais_latent=cfg.model.ais_latent,
        crop_size=crop_size,
        aspect_ratio=spatial_meta.get("aspect_ratio", 1.0)
    ).to(device)

    checkpoint = torch.load(cfg.evaluation.checkpoint_path, map_location=device)
    model.load_state_dict(checkpoint["model_state_dict"] if "model_state_dict" in checkpoint else checkpoint)
    model.eval()

    # 3. Batch Iterate over all pickle files
    for file_path in tqdm(input_files, desc="Overall Progress"):
        process_single_pickle(file_path, model, device, bathy_grid, water_mask, stats, spatial_meta, args)

    print(f"\nBatch processing finished for all files! Outputs saved to: '{args.output_dir}'")

if __name__ == "__main__":
    main()