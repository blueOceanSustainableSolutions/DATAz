# SWAN Wave Surrogate

A deep learning surrogate model for **SWAN (Simulating Waves Nearshore)** numerical simulations. This repository provides a data-driven alternative to full physical wave modeling, enabling fast, GPU-accelerated predictions of Significant Wave Height (`HSig`) and Peak Wave Direction (`PDIR`) from wind inputs and boundary wave forcing over a static bathymetry grid.

---

## Overview

SWAN simulations solve wave action balance equations, which are computationally expensive. This surrogate replaces the numerical solver with a deep neural network (e.g., **PhysicsUNet2**) that predicts spatial wave fields. The architecture combines:

- A **Boundary Encoder** to ingest wave forcing parameters (`swh`, `pp1d`, `mwd_sin`, `mwd_cos`) at the boundaries.
- A **Wind & Bathymetry Encoder** that accepts wind components (`u10`, `v10`) and bathymetry elevation, dynamically computing spatial gradients (slopes) to model wave refraction and shoaling physics.
- A **U-Net Decoder** with attention skip connections to generate high-resolution target fields.

The model maps temporal input sequences to physical target fields, outputting predictions aligned to a uniform grid (e.g., $128 \times 128$).

---

## Repository Structure

```
HPC_SWAN_Surrogate_Github/
├── src/
│   ├── README.md                      # This file
│   ├── requirements.txt               # Python package dependencies
│   ├── config.py                      # Shared configuration for Stage 2 & 3
│   │
│   ├── 1_General_Preprocessing/       # Stage 1: Raw data alignment & interpolation
│   │   ├── run_all_preprocessing.py   # Entry point for Stage 1 orchestration
│   │   ├── 1_boundary_preprocessing.py
│   │   ├── 1_input_preprocessing.py
│   │   ├── 1_output_preprocessing.py
│   │   ├── f_*.py                     # Core logic modules (interpolation, coords, utils)
│   │   ├── visualization.py           # QA plotting utilities
│   │   └── run.job                    # SLURM script for Stage 1 preprocessing
│   │
│   ├── 2_Surrogate_Preprocessing/     # Stage 2: Temporal sequence construction
│   │   ├── 1_PREPROCESS.py            # Entry point for sequence extraction
│   │   ├── config.py                  # Config shim pointing to src/config.py
│   │   ├── f_data_processing.py       # Data loading and scaling logic
│   │   ├── f_sequence_core.py         # Temporal window sequencing logic
│   │   └── run.job                    # SLURM script for Stage 2 preprocessing
│   │
│   └── 3_Surrogate_Training/          # Stage 3: Model training and evaluation
│       ├── 2_TRAIN.py                 # Training entry point
│       ├── config.py                  # Config shim pointing to src/config.py
│       ├── dataloader.py              # PyTorch DataLoader wrappers
│       ├── evaluate_stage.py          # Post-training evaluation logic
│       ├── loss_functions.py          # Custom physics-weighted losses
│       ├── models_architecture/       # Neural network architecture definitions
│       ├── train_stage.py             # Core PyTorch training loop
│       ├── visualize_stage.py         # Artifact and plot generation
│       └── run.job                    # SLURM script for model training
│
├── models/                            # Directory for saved checkpoints and scalers
└── results/                           # Evaluation plots and training metric logs
```

---

## Software Setup

### 1. PyTorch

Install PyTorch first, selecting the version that matches your hardware (CPU, CUDA, ...):

**→ [https://pytorch.org/get-started/locally/](https://pytorch.org/get-started/locally/)**

Follow the instructions on that page to get the correct install command for your platform and CUDA version before proceeding.

### 2. Python Dependencies

Once PyTorch is installed, install the remaining dependencies using the `requirements.txt` file located in the `src` folder:

```bash
# Run this from the root of the swan surrogate model folder:
pip install -r src/requirements.txt
```

---

## HPC Cluster Setup

If you are running preprocessing or training on a SLURM cluster, a batch script (`run.job`) is provided in each respective step directory. Adjust the partition names, accounts, and conda environment names within the scripts to match your cluster's settings.

Example to submit a training job:
```bash
cd src/3_Surrogate_Training
sbatch run.job
```

Key points:
- Always run scripts from their respective directory or configure `PYTHONPATH` properly.
- Submissions output logs directly into a `logs/` directory in the target folder.

---

## Workflow Steps

### 1. General Preprocessing (Stage 1)
Aligns wind, boundary wave, bathymetry, and SWAN outputs to a common spatial grid and temporal overlapping window.

**Running Locally:**
```bash
cd src/1_General_Preprocessing
python run_all_preprocessing.py --case <CASE_FOLDER_NAME>
```

**Running on HPC (SLURM):**
```bash
cd src/1_General_Preprocessing
# Edit the CASE_FOLDER variable in run.job, then submit:
sbatch run.job
```

### 2. Surrogate Preprocessing (Stage 2)
Packs preprocessed NetCDF datasets into temporal sequence tensors (`.pt` files) for PyTorch training.

**Running Locally:**
```bash
cd src/2_Surrogate_Preprocessing
python 1_PREPROCESS.py
```

**Running on HPC (SLURM):**
```bash
cd src/2_Surrogate_Preprocessing
sbatch run.job
```

### 3. Model Training (Stage 3)
Trains the chosen surrogate model architecture using the configured hyperparameters.

**Running Locally:**
```bash
cd src/3_Surrogate_Training
python 2_TRAIN.py
```

**Running on HPC (SLURM):**
```bash
cd src/3_Surrogate_Training
sbatch run.job
```

---

## Configuration

Configurations for data splits, variables, model configurations, and training schedules are centralized in `src/config.py`. The `config.py` files within the `2_Surrogate_Preprocessing` and `3_Surrogate_Training` folders are forwarding shims that point to this shared configuration.

**Key project-specific variables that you must verify or update in `src/config.py` include:**
- **`PROJECT_ROOT`**: Usually auto-resolved, but ensure it correctly points to the root of the repository.
- **`PREPROCESSED_ROOT`**: Directory where intermediate datasets are saved.
- **`MODEL_DIR`**, **`RESULTS_DIR`**, **`SCALER_DIR`**: Directories for training checkpoints, evaluation artifacts, and normalization scalers.
- **`WIND_VARS`**, **`BOUNDARY_VARS`**, **`BATHY_VARS`**, **`TARGET_VARS`**: Variable names expected from the raw NetCDF files.
- **`TRAINING_CONFIG`**: Dictionary containing `batch_size`, `learning_rate`, `num_epochs`, and early stopping `patience`.
- **`MODEL_ARCHITECTURE`**: Selection of the neural network backbone (e.g., `'physics_unet2'`).
