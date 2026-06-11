# scripts/evaluate.py

import os
import sys
import argparse
import torch
from torch.utils.data import DataLoader, random_split
from tqdm import tqdm

# Ensure the src/ folder is visible to Python
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from raindrop_surrogate import (
    RadialAcousticSurrogate,
    AcousticDataset,
    scale_data,
    custom_collate,
    load_config,
    load_model,
    compute_physical_metrics,
    plot_radial_comparison,
    plot_metrics_table,
)

def parse_args():
    parser = argparse.ArgumentParser(
        description="Evaluate the trained Distance-Conditioned Vectorized Acoustic Surrogate Model."
    )
    parser.add_argument(
        "--config",
        type=str,
        default="configs/default.yaml",
        help="Path to the YAML configuration file.",
    )
    parser.add_argument(
        "--checkpoint",
        type=str,
        default=None,
        help="Path to the model checkpoint. Overrides the config file if provided.",
    )
    parser.add_argument(
        "--split",
        type=str,
        choices=["train", "val", "test"],
        default="test",
        help="Which dataset split to evaluate on (default: test).",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    cfg = load_config(args.config)

    # 1. Setup Directories & Device
    out_dir = cfg.get("evaluation", {}).get("output_dir", "results/evaluation")
    os.makedirs(out_dir, exist_ok=True)

    device = torch.device(
        "cuda" if torch.cuda.is_available() and cfg.training.get("use_cuda", True) else "cpu"
    )
    print(f"Using device: {device}")

    # 2. Data Pipeline
    print("Initializing base dataset (this may take a moment to load cache)...")
    base_dataset = AcousticDataset(
        ais_dir=cfg.data.ais_dir,
        spl_dir=cfg.data.spl_dir,
        example_nc_path=cfg.data.example_nc_path,
        bathy_csv=cfg.data.bathy_csv,
        coastline_shp=cfg.data.coastline_shp,
        cache_dir=cfg.data.get("cache_dir", "cache"),
        crop_size=cfg.data.crop_size,
        use_63hz=cfg.data.use_63hz,
        use_pascal=cfg.data.use_pascal,
        num_rays=cfg.data.num_rays,
        ray_points=cfg.data.ray_points,
    )

    # Recreate the exact same splits using the training seed
    torch.manual_seed(cfg.training.get("seed", 42))
    total_len = len(base_dataset)
    train_sz = int(cfg.training.train_split * total_len)
    val_sz = int(cfg.training.val_split * total_len)
    test_sz = total_len - train_sz - val_sz

    train_sub, val_sub, test_sub = random_split(
        base_dataset, [train_sz, val_sz, test_sz]
    )

    # We must run scale_data on all splits to compute training stats properly
    sc_train, sc_val, sc_test, stats = scale_data(train_sub, val_sub, test_sub)

    # Select the target split based on user arguments
    split_map = {"train": sc_train, "val": sc_val, "test": sc_test}
    target_dataset = split_map[args.split]

    loader = DataLoader(
        target_dataset,
        batch_size=cfg.evaluation.get("batch_size", cfg.training.batch_size),
        shuffle=False,
        collate_fn=custom_collate,
    )

    # 3. Model & Weights Setup
    model = RadialAcousticSurrogate(
        bathy_latent=cfg.model.bathy_latent,
        ais_latent=cfg.model.ais_latent,
        crop_size=cfg.data.crop_size,
    )

    ckpt_path = args.checkpoint or cfg.evaluation.checkpoint_path
    print(f"Loading model weights from: {ckpt_path}")
    model = load_model(model=model, path=ckpt_path, device=device)

    # 4. Evaluation Loop
    print(f"Evaluating on the '{args.split}' split ({len(target_dataset)} samples)...")
    all_preds = []
    all_targets = []
    all_masks = []

    with torch.no_grad():
        for ais_b, bathy_b, spl_b, tmax_b in tqdm(loader, desc="Running Inference"):
            ais_b = ais_b.to(device).float()
            bathy_b = bathy_b.to(device).float()
            spl_b = spl_b.to(device).float()
            tmax_b = tmax_b.to(device).float()

            preds = model(bathy_b, ais_b, tmax_b)
            
            all_preds.append(preds.cpu())
            all_targets.append(spl_b.cpu())
            all_masks.append((bathy_b.cpu() > 0).float())

    final_preds = torch.cat(all_preds, dim=0)
    final_targets = torch.cat(all_targets, dim=0)
    final_masks = torch.cat(all_masks, dim=0)

    # Mask land out completely before metrics (optional, but cleaner for physics)
    final_preds = final_preds * final_masks
    final_targets = final_targets * final_masks

    # 5. Compute Metrics & Visualizations
    metrics = compute_physical_metrics(
        preds=final_preds,
        targets=final_targets,
        stats=stats,
        use_pascal_input=cfg.data.use_pascal,
    )

    print("\n--- Physical-Unit Metrics ---")
    for k, v in metrics.items():
        print(f"  {k}: {v:.4e}")

    # Generate Metrics Table Graphic
    tbl_path = os.path.join(out_dir, f"{args.split}_metrics_table.png")
    plot_metrics_table({args.split: metrics}, save_path=tbl_path)

    # Generate sample radial comparison plots
    num_plots = cfg.evaluation.get("num_plots", 3)
    num_plots = min(num_plots, len(target_dataset))
    
    print(f"\nGenerating {num_plots} visualization plots...")
    for i in range(num_plots):
        fig_path = os.path.join(out_dir, f"{args.split}_comparison_sample_{i}.png")
        plot_radial_comparison(
            model=model,
            dataset=target_dataset,
            stats=stats,
            device=device,
            sample_idx=i,
            save_path=fig_path,
        )

    print(f"\nEvaluation complete. Outputs saved to '{out_dir}'.")


if __name__ == "__main__":
    main()