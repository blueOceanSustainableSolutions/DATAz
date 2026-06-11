# Stage 3: Surrogate Training Pipeline

This directory contains the third stage of the SWAN surrogate modeling pipeline: **Surrogate Training**. The pipeline takes the scaled, split, and sequenced PyTorch tensors (`sequences.pt`) generated in Stage 2 and trains a neural network surrogate model, then evaluates and visualizes the results.

---

## Table of Contents
1. [Pipeline Overview](#pipeline-overview)
2. [Directory Structure & Modules](#directory-structure--modules)
3. [Processing Steps](#processing-steps)
4. [Command Line Usage Guide](#command-line-usage-guide)
5. [HPC Cluster Submission (SLURM)](#hpc-cluster-submission-slurm)

---

## Pipeline Overview

The goal of this surrogate training pipeline is to:

- **Load Sequences**: Read the pre-built `sequences.pt` tensors produced by Stage 2.
- **Build DataLoaders**: Wrap sequences into batched PyTorch `DataLoader` objects.
- **Build Model**: Instantiate the neural network architecture defined in `src/config.py`.
- **Train**: Run the full training loop with early stopping, cosine annealing LR schedule, and gradient clipping.
- **Evaluate**: Compute RMSE, MAE, and R² on validation and test splits (inverse-scaled to physical units).
- **Visualize**: Export loss curves, spatial error heatmaps, and comparison sample figures.

---

## Directory Structure & Modules

| File | Type | Description |
| :--- | :--- | :--- |
| [2_TRAIN.py](2_TRAIN.py) | **Entry Point** | Main training script. Runs all stages: load → build → train → evaluate → visualize. |
| [train_stage.py](train_stage.py) | **Core Module** | Training loop, optimizer, LR scheduler, checkpointing, and model import/export utilities. |
| [dataloader.py](dataloader.py) | **Core Module** | `TensorDataset` wrapper and `DataLoader` factory. |
| [evaluate_stage.py](evaluate_stage.py) | **Core Module** | Post-training evaluation: RMSE, MAE, R² per variable on inverse-scaled predictions. |
| [visualize_stage.py](visualize_stage.py) | **Core Module** | Loss curves, spatial heatmaps, and side-by-side comparison figures. |
| [loss_functions.py](loss_functions.py) | **Core Module** | Loss function factory (`mse`, `mae`, `weighted_physics`). |
| [config.py](config.py) | **Config Shim** | Forwards configuration from the unified `src/config.py`. |
| [models_architecture/](models_architecture/) | **Package** | Neural network architectures (`physics_unet2`, `unet`, `spatial_cnn`, `ctp`, `convlstm`). |
| [run.job](run.job) | **HPC Script** | SLURM batch script to submit the training job to a GPU node. |

*Note: `import_scale` is imported from `f_data_processing.py` in Stage 2 (`src/2_Surrogate_Preprocessing/`), which must be on `PYTHONPATH`.*

---

## Processing Steps

1. **Stage 0 – Configuration**: Prints full experiment config from `src/config.py`.
2. **Stage 1 – Load Sequences**: Loads `sequences.pt`, creates `train/val/test` `DataLoader`s.
3. **Stage 2 – Build Model**: Instantiates the model from `MODEL_ARCHITECTURE` config, runs a debug forward pass to confirm shapes.
4. **Stage 3 – Training**: Runs the training loop with `AdamW`, cosine annealing LR, gradient clipping, early stopping. Saves best checkpoint to `MODEL_DIR`.
5. **Stage 4 – Evaluation**: Runs inference on val and test splits. Computes RMSE/MAE/R² per variable (inverse-scaled).
6. **Stage 5 – Visualization**: Exports loss curves, error heatmaps, and spatial comparison figures to `RESULTS_DIR/<model_name>/`.

---

## Command Line Usage Guide

Use `2_TRAIN.py` to train and evaluate the surrogate model.

**Standard training run:**
```bash
python 2_TRAIN.py \
  --sequence-name 500 \
  --batch-size 16 \
  --num-workers 0
```

**Training from a custom sequences root:**
```bash
python 2_TRAIN.py \
  --sequences-root /path/to/data/sequences \
  --sequence-name 20000 \
  --batch-size 16
```

**Key Arguments**:
| Argument | Default | Description |
| :--- | :--- | :--- |
| `--sequence-name` | `500` | Sub-folder name under `--sequences-root` to load (e.g. `500`, `8000`, `All`). |
| `--sequences-root` | `$PROJECT_ROOT/data/sequences` | Root directory containing sequence folders. |
| `--batch-size` | from `config.py` | Override training batch size. |
| `--num-workers` | `0` | DataLoader worker processes (0 = safe for HPC). |
| `--pin-memory` | `False` | Enable `pin_memory` in DataLoaders (auto-enabled if CUDA). |

*Sequences are loaded from `<sequences-root>/<sequence-name>/sequences.pt`.*
*All other hyperparameters (LR, epochs, architecture, etc.) are controlled via `src/config.py`.*

---

## HPC Cluster Submission (SLURM)

For GPU-accelerated training, submit the job to the HPC cluster using the provided SLURM batch script. Before submitting, you **MUST edit the following variables** inside the script:

- **`SEQUENCES_ROOT`**: Must point to the root folder generated in Stage 2.
- **`SEQUENCE_NAME`**: The specific dataset folder name to train on (e.g., `"500"` or `"All"`).
- **`#SBATCH --account=...`**: Your cluster billing account.
- **`#SBATCH --partition=...`**: Target cluster partition (must support GPUs, e.g., `dev-a100-40`).
- **`CONDA_ENV_NAME`**: Name of your Conda environment (default: `swan_surrogate_env`).

```bash
# Edit the variables in run.job, then submit:
sbatch run.job
```

Job logs are written to `logs/<job_id>.out` and `logs/<job_id>.err`.

### Key Notes
- **Environment**: The `swan_surrogate_env` conda environment is activated.
- **PYTHONPATH**: `src/2_Surrogate_Preprocessing` is added to resolve `f_data_processing` (required for `import_scale`).
- **Output**:
  - Best checkpoint → `$PROJECT_ROOT/models/<model_name>.pt`
  - Evaluation metrics → `$PROJECT_ROOT/results/<model_name>/`
- **PyTorch CUDA**: Requires `torch>=2.6.0+cu124`. Install with:
  ```bash
  pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
  ```

### Recommended Workflow
1. Run Stage 2 (`1_PREPROCESS.py` or `sbatch run.job` in Stage 2) to generate `sequences.pt`.
2. Edit `SEQUENCES_ROOT` and `SEQUENCE_NAME` in Stage 3's `run.job` to match.
3. Submit: `sbatch run.job`.
4. Monitor: `tail -f logs/<job_id>.out`.
