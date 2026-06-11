# SWAN Surrogate Model

A deep learning surrogate model for the **SWAN** (Simulating Waves Nearshore) numerical simulation model. Developed as part of the DATAz (2025.00265.DT4ST) – Digital Twin for the Azores Free Technological Zone project, this repository provides a data-driven alternative to full numerical simulations, enabling rapid predictions of wave fields without the heavy computational cost of solving physical equations.

---

## Overview

The SWAN Surrogate Model predicts Significant Wave Height (`HSig`) and Peak Direction (`PDIR`) over a target area. 

This surrogate replaces the SWAN numerical solver with a deep learning pipeline (typically based on a **PhysicsUNet2** architecture) that learns the non-linear relationship between atmospheric forcing, bathymetry, and the resulting wave fields. The architecture handles:

- **General Preprocessing**: Alignment and interpolation of raw wind, boundary wave forcing, and bathymetry NetCDF data onto a uniform spatial grid.
- **Surrogate Preprocessing**: Construction of temporal "sliding window" sequences, handling of missing data, feature scaling, and Inverse Distance Weighting (IDW) boundary filling.
- **Surrogate Training**: Training, evaluation, and visualization of the deep neural network to predict the wave parameters.
- **Inference Orchestration**: A streamlined orchestrator (`main.py`) for running forward predictions on new data.

---

## Repository Structure

```
HPC_SWAN_Surrogate_Github/
├── README.md
├── Program Manual.md           # Detailed technical and architecture documentation
├── User Manual.md              # User guide for running inference
├── src/
│   ├── 1_General_Preprocessing/ # Stage 1 scripts and HPC job files
│   ├── 2_Surrogate_Preprocessing/ # Stage 2 scripts and HPC job files
│   ├── 3_Surrogate_Training/    # Stage 3 scripts and HPC job files
│   ├── config.py                # Central configuration file
│   └── requirements.txt         # Python dependencies
└── user_case/                   # Streamlined orchestrator for inference
    ├── main.py                  # CLI Orchestrator script
    ├── setup_env.sh             # Environment setup script
    ├── stage1.py                # User case stage 1 wrapper
    ├── stage2.py                # User case stage 2 wrapper
    └── stage3.py                # User case stage 3 wrapper
```

---

## Software Setup

### 1. PyTorch

Install PyTorch first, selecting the version that matches your hardware (CPU, CUDA, ...):

**→ [https://pytorch.org/get-started/locally/](https://pytorch.org/get-started/locally/)**

For example, to install with CUDA 12.4 support:
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
```

### 2. Python Dependencies

Create an isolated Conda environment and install the remaining dependencies:

```bash
conda create -n swan_surrogate_env python=3.10
conda activate swan_surrogate_env
pip install -r src/requirements.txt
```

---

## HPC Cluster Setup

The core training pipeline is divided into three stages located in the `src/` directory. HPC SLURM scripts (`run.job`) are provided in each folder.

Before submitting a job, you **MUST update the `run.job` files** to match your cluster environment and target datasets:
- `#SBATCH --account=...`: Your cluster billing account.
- `#SBATCH --partition=...`: Target cluster partition (e.g., `dev-a100-40`).
- `CONDA_ENV_NAME`: Name of your Conda environment (default: `swan_surrogate_env`).
- `WORKDIR` / `PROJECT_ROOT`: Ensure these paths point to your specific cloned repository location.

---

## Configuration

Central configuration is managed in `src/config.py`. Key project-specific variables that you must verify or update include:

- **`PROJECT_ROOT`**: Usually auto-resolved, but ensure it correctly points to the root of the repository.
- **`PREPROCESSED_ROOT`**: Directory where intermediate datasets are saved.
- **`MODEL_DIR`**, **`RESULTS_DIR`**, **`SCALER_DIR`**: Directories where training checkpoints, evaluation artifacts, and normalization scalers are saved.
- **`WIND_VARS`**, **`BOUNDARY_VARS`**, **`BATHY_VARS`**, **`TARGET_VARS`**: Variable names expected from the raw NetCDF files.
- **`TRAINING_CONFIG`**: Dictionary containing `batch_size`, `learning_rate`, `num_epochs`, and early stopping `patience`.
- **`MODEL_ARCHITECTURE`**: Selection of the neural network backbone (e.g., `'physics_unet2'`).

---

## Training Pipeline

The training process is divided into three stages. Run each step sequentially from the respective folder in `src/`.

### Stage 1: General Preprocessing
In `src/1_General_Preprocessing/run.job`, ensure you update `CASE_FOLDER` to your specific raw data folder name (e.g., `SWAN_case_001`).
```bash
cd src/1_General_Preprocessing
sbatch run.job
```

### Stage 2: Surrogate Preprocessing
In `src/2_Surrogate_Preprocessing/run.job`, ensure you update `CASE_SEQUENCES_ROOT` and `SEQUENCE_COUNT`.
```bash
cd src/2_Surrogate_Preprocessing
sbatch run.job
```

### Stage 3: Surrogate Training
In `src/3_Surrogate_Training/run.job`, ensure you update `SEQUENCES_ROOT` and `SEQUENCE_NAME`.
```bash
cd src/3_Surrogate_Training
sbatch run.job
```

Results are output directly to the file system as NetCDF files and Metric Plots.

---

## Running Inference (User Case)

For fast wave prediction on new data without needing to trigger the training loop, a streamlined orchestrator (`main.py`) is provided in the `user_case` folder. It automatically handles raw data alignment, sequence generation, and model inference in a single command.

1. Navigate to the user case directory:
   ```bash
   cd user_case
   ```

2. Execute the pipeline for a specific date and duration:
   ```bash
   conda run -n swan_surrogate_env python main.py --execute --stage stage123 \
       --date 2025-09-01 \
       --duration-hours 48 \
       --max-frames 24
   ```

**Key CLI parameters:**
- `--date`: The start date (YYYY-MM-DD) to slice from the raw data.
- `--duration-hours`: How many consecutive hours to process starting from `--date` (defaults to 24).
- `--max-frames`: How many hourly PNG plots to generate starting from the first hour (defaults to 24).
- `--stage`: Which stage(s) to execute (`stage123` for full pipeline, or individual stages).

**Outputs:**
- A NetCDF file (`stage3_predictions.nc`) containing the predicted spatial wave fields.
- A `frames/` directory containing PNG visualizations of the wave fields.
