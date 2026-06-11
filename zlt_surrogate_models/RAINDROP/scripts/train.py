# scripts/train.py

import os
import sys
import argparse
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, random_split
from tqdm import tqdm

# Ensure the src/ folder is visible to Python when executing this script directly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

# Clean imports from your package initialization layer
from raindrop_surrogate import (
    RadialAcousticSurrogate,  # Matches your model architecture class name
    AcousticDataset,
    scale_data,
    custom_collate,
    load_config,
    compute_physical_metrics,
    save_checkpoint,
    plot_radial_comparison,
    plot_training_curves,
    plot_metrics_table,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Train the Distance-Conditioned Vectorized Acoustic Surrogate Model."
    )
    parser.add_argument(
        "--config",
        type=str,
        default="configs/default.yaml",
        help="Path to the YAML configuration file (default: configs/default.yaml)",
    )
    return parser.parse_args()


def evaluate_split(model, loader, dataset_wrapper, stats, device, use_pascal):
    """Runs a complete forward pass over a full split to compute overall physical metrics."""
    model.eval()
    all_preds = []
    all_targets = []

    with torch.no_grad():
        for ais_b, bathy_b, spl_b, tmax_b in loader:
            ais_b = ais_b.to(device).float()
            bathy_b = bathy_b.to(device).float()
            spl_b = spl_b.to(device).float()
            tmax_b = tmax_b.to(device).float()

            preds = model(bathy_b, ais_b, tmax_b)
            all_preds.append(preds.cpu())
            all_targets.append(spl_b.cpu())

    final_preds = torch.cat(all_preds, dim=0)
    final_targets = torch.cat(all_targets, dim=0)

    return compute_physical_metrics(
        final_preds, final_targets, stats, use_pascal_input=use_pascal
    )


def main():
    args = parse_args()

    # 1. Load Configuration Structure via Dot-Access Dict
    cfg = load_config(args.config)

    # Setup directories
    os.makedirs(cfg.training.output_dir, exist_ok=True)
    os.makedirs(cfg.training.checkpoint_dir, exist_ok=True)

    # Setup device
    device = torch.device(
        "cuda"
        if torch.cuda.is_available() and cfg.training.get("use_cuda", True)
        else "cpu"
    )
    print(f"Using device: {device}")

    # 2. Optional MLflow Setup Initialization
    use_mlflow = cfg.get("mlflow", {}).get("enabled", False)
    if use_mlflow:
        import mlflow

        mlflow.set_tracking_uri(cfg.mlflow.tracking_uri)
        mlflow.set_experiment(cfg.mlflow.experiment_name)
        active_run = mlflow.start_run(
            run_name=f"hz_{cfg.data.use_63hz}_pascal_{cfg.data.use_pascal}"
        )
        # Log config items flatly
        mlflow.log_params(
            {
                "batch_size": cfg.training.batch_size,
                "epochs": cfg.training.num_epochs,
                "lr": cfg.training.lr,
                "use_63hz": cfg.data.use_63hz,
                "use_pascal": cfg.data.use_pascal,
            }
        )

    # 3. Data Pipeline & Data Scaling Setup
    print("Initializing base dataset...")
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

    # Generate Deterministic Splits
    torch.manual_seed(cfg.training.get("seed", 42))
    total_len = len(base_dataset)
    train_sz = int(cfg.training.train_split * total_len)
    val_sz = int(cfg.training.val_split * total_len)
    test_sz = total_len - train_sz - val_sz

    train_sub, val_sub, test_sub = random_split(
        base_dataset, [train_sz, val_sz, test_sz]
    )

    # Build scaled dataset wrappers
    sc_train, sc_val, sc_test, stats = scale_data(train_sub, val_sub, test_sub)

    # Construct Data Loaders using our Custom Variable-Length Collate function
    train_loader = DataLoader(
        sc_train,
        batch_size=cfg.training.batch_size,
        shuffle=True,
        collate_fn=custom_collate,
    )
    val_loader = DataLoader(
        sc_val, batch_size=cfg.training.batch_size, collate_fn=custom_collate
    )
    test_loader = DataLoader(
        sc_test, batch_size=cfg.training.batch_size, collate_fn=custom_collate
    )

    # 4. Instantiate Model & Optimization Engine
    model = RadialAcousticSurrogate(
        bathy_latent=cfg.model.bathy_latent,
        ais_latent=cfg.model.ais_latent,
        crop_size=cfg.data.crop_size,
    ).to(device)

    optimizer = optim.Adam(model.parameters(), lr=cfg.training.lr)
    criterion = nn.MSELoss()

    # 5. Model Execution Training Optimization Loop
    best_val_loss = float("inf")
    train_losses, val_losses = [], []
    checkpoint_path = os.path.join(cfg.training.checkpoint_dir, "best_model.pth")

    pbar = tqdm(range(cfg.training.num_epochs), desc="Training Model")
    for epoch in pbar:
        model.train()
        running_train_loss = 0.0

        for ais_b, bathy_b, spl_b, tmax_b in train_loader:
            ais_b = ais_b.to(device).float()
            bathy_b = bathy_b.to(device).float()
            spl_b = spl_b.to(device).float()
            tmax_b = tmax_b.to(device).float()

            optimizer.zero_grad()

            # Forward pass: order matches signature (bathy_rays, ais_info, t_max)
            preds = model(bathy_b, ais_b, tmax_b)

            # Spatial Land Masking Layer (Water > 0)
            mask = (bathy_b > 0).float()
            loss = criterion(preds * mask, spl_b * mask)

            loss.backward()
            optimizer.step()
            running_train_loss += loss.item()

        # Validation Tracking Execution Pass
        model.eval()
        running_val_loss = 0.0
        with torch.no_grad():
            for ais_b, bathy_b, spl_b, tmax_b in val_loader:
                ais_b = ais_b.to(device).float()
                bathy_b = bathy_b.to(device).float()
                spl_b = spl_b.to(device).float()
                tmax_b = tmax_b.to(device).float()

                v_preds = model(bathy_b, ais_b, tmax_b)
                v_mask = (bathy_b > 0).float()
                v_loss = criterion(v_preds * v_mask, spl_b * v_mask)
                running_val_loss += v_loss.item()

        epoch_train_loss = running_train_loss / len(train_loader)
        epoch_val_loss = running_val_loss / len(val_loader)

        train_losses.append(epoch_train_loss)
        val_losses.append(epoch_val_loss)

        pbar.set_postfix(
            {"Train MSE": f"{epoch_train_loss:.4e}", "Val MSE": f"{epoch_val_loss:.4e}"}
        )

        if use_mlflow:
            mlflow.log_metrics(
                {"train_mse": epoch_train_loss, "val_mse": epoch_val_loss},
                step=epoch,
            )

        # Checkpoint Saving Layer
        if epoch_val_loss < best_val_loss:
            best_val_loss = epoch_val_loss
            save_checkpoint(
                model=model,
                optimizer=optimizer,
                epoch=epoch,
                val_loss=best_val_loss,
                path=checkpoint_path,
            )

    print(f"\nTraining Complete! Best Validation Loss: {best_val_loss:.5e}")

    # 6. Post-Evaluation & Visualizations Generation
    print("Loading optimized checkpoint weights for evaluation...")
    checkpoint = torch.load(checkpoint_path, map_location=device)
    model.load_state_dict(checkpoint["model_state_dict"])

    # Gather metrics over all dataset branches
    metrics_by_split = {
        "train": evaluate_split(
            model, train_loader, sc_train, stats, device, cfg.data.use_pascal
        ),
        "val": evaluate_split(
            model, val_loader, sc_val, stats, device, cfg.data.use_pascal
        ),
        "test": evaluate_split(
            model, test_loader, sc_test, stats, device, cfg.data.use_pascal
        ),
    }

    # Generate & save tracking charts using visualize.py utilities
    curve_fig = os.path.join(cfg.training.output_dir, "loss_curves.png")
    table_fig = os.path.join(cfg.training.output_dir, "metrics_table.png")

    plot_training_curves(train_losses, val_losses, save_path=curve_fig)
    plot_metrics_table(metrics_by_split, save_path=table_fig)

    # Generate a sample prediction radial profile chart from the validation set
    comp_fig = os.path.join(cfg.training.output_dir, "val_radial_comparison.png")
    plot_radial_comparison(
        model=model,
        dataset=sc_val,
        stats=stats,
        device=device,
        sample_idx=0,
        save_path=comp_fig,
    )

    # Wrap metrics and log arrays directly to Mlflow tracking workspace
    if use_mlflow:
        for split_name, metrics in metrics_by_split.items():
            mlflow.log_metrics(
                {f"{split_name}_{k}": v for k, v in metrics.items()}
            )

        mlflow.log_artifact(checkpoint_path, artifact_path="checkpoints")
        mlflow.log_artifact(curve_fig, artifact_path="plots")
        mlflow.log_artifact(table_fig, artifact_path="plots")
        mlflow.log_artifact(comp_fig, artifact_path="plots")
        mlflow.end_run()

    print(f"All evaluation outputs successfully saved to '{cfg.training.output_dir}'")


if __name__ == "__main__":
    main()