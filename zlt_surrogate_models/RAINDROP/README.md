# RAINDROP AI Surrogate Model

A deep learning surrogate model for the **RAINDROP** underwater acoustic propagation model. This repository provides a data-driven alternative to full numerical simulations, enabling GPU-accelerated sound pressure level (SPL) predictions from AIS ship data and Bathymetry inputs.

---

## Overview

RAINDROP computes spatial SPL fields resulting from ship-radiated noise, accounting for seafloor bathymetry, coastline geometry, and vessel data (AIS). 

This surrogate replaces the RAINDROP solver with a **RadialAcousticSurrogate** — a neural network that predicts normalised SPL along radial profiles emanating from each ship position. The architecture combines:

- A **1-D CNN bathymetry encoder** with point-wise distance awareness
- An **AIS encoder** conditioned on ray scale (propagation reach)
- A **SPL prediction module** with distance skip connections for physically consistent decay

The model operates on radial ray representations `(B, R, L)` — batch × rays × points per ray — and outputs normalised SPL values in `[0, 1]`, which can be remapped to physical units (dB re 1 µPa or Pa) using the dataset statistics.

---

## Repository Structure

```
raindrop-surrogate/
├── README.md
├── requirements.txt
├── checkpoints.dvc
├── train.sh
├── user_example.ipynb
├── configs/
│   └── default.yaml            # Configure training, evaluation, dataset, model and visualization parameters.
├── checkpoints/
│   └── raindrop_surrogate.pth  # Pre-trained model weights (see below)
├── results/
│   └── figures/                # Output plots from training / evaluation
├── src/
│   └── raindrop_surrogate/
│       ├── __init__.py
│       ├── model.py            # RadialAcousticSurrogate architecture
│       ├── dataset.py          # AcousticDataset, scaling, collation
│       ├── utils.py            # Metrics, checkpoint I/O, config loader
│       └── visualize.py        # Plotting utilities
├── scripts/
│   ├── train.py                # Training entry point
│   ├── evaluate.py             # Evaluation on a trained checkpoint
│   └── predict.py              # Lightwheight predictions and CLI tool 
└── data/
    └── raw/                    
    
```

---

## Software Setup

### 1. PyTorch

Install PyTorch first, selecting the version that matches your hardware (CPU, CUDA, ROCm, ...):

**→ [https://pytorch.org/get-started/locally/](https://pytorch.org/get-started/locally/)**

Follow the instructions on that page to get the correct install command for your platform and CUDA version before proceeding.

### 2. Python Dependencies

Once PyTorch is installed, install the remaining dependencies:

```bash
pip install -r requirements.txt
```

---

## HPC Cluster Setup

If you are running training or inference on an HPC cluster (e.g. SLURM), create a `job.sh` submission script in the project root. Adjust the resource flags to match your cluster's partition names and available GPUs.

A minimal SLURM template:

```bash
#!/bin/bash
#SBATCH --job-name=
#SBATCH --partition=                  # Replace with your cluster's GPU partition
#SBATCH --cpus-per-task=              # DataLoader workers + overhead
#SBATCH --time=12:00:00               
#SBATCH --output=results/%j_train.out
#SBATCH --error=results/%j_train.err


# Activate your virtual environment
source PATH_TO_YOUR_ENV/bin/activate

# Run training from the project root
python scripts/train.py --config configs/default.yaml
```

Key points:
- Always run scripts **from the project root directory** so that relative imports resolve correctly.
- Submit with: `sbatch job.sh`

---

## Dataset Preparation

The surrogate is trained on outputs produced by a RAINDROP simulation run. You will need to locate three categories of files from that run.
Note: Currently the model only supports one ship per simulation timestep, so if providing it with AIS data please do so in accordance. 

### RAINDROP Output Files

These live inside the **`out/`** folder of your RAINDROP simulation:

| Config key | Description | Typical path inside `out/` |
|---|---|---|
| `data.ais_dir` | Directory of AIS pickle files (`AIS_<timestamp>.pickle`) | `out/ais/` |
| `data.spl_dir` | Directory of SPL pickle files (`SPL_<timestamp>.pickle`) | `out/pickles/` |
| `data.example_nc_path` | Any single NetCDF file used to infer the spatial grid | `out/nc/SPL_<timestamp>.nc` |

### RAINDROP Input Files

These are the static geospatial inputs that RAINDROP itself requires, typically prepared before the simulation:

| Config key | Description |
|---|---|
| `data.bathy_csv` | Bathymetry CSV with columns `lat`, `lon`, `z` (depth in metres) |
| `data.coastline_shp` | Coastline shapefile used by RAINDROP for land masking |

Set all six paths in `configs/default.yaml` (or in your own config file) before running any script:

```yaml
data:
  ais_dir:          "/path/to/raindrop/out/ais"
  spl_dir:          "/path/to/raindrop/out/pickles"
  example_nc_path:  "/path/to/raindrop/out/nc/SPL_2025-06-01T00:00:00.nc"
  bathy_csv:        "/path/to/raindrop/inputs/bathymetry.csv"
  coastline_shp:    "/path/to/raindrop/inputs/coastline/coastline.shp"
```

---

## Configuration

All training hyperparameters, model settings, and data paths are controlled through a single YAML file. The default configuration is provided at `configs/default.yaml`.

### Using the Default Config

```bash
python scripts/train.py --config configs/default.yaml
```

### Creating a Custom Config

You can create your own YAML file for a new experiment with different parameters or a different simulation:

The scripts (`train.py`, `evaluate.py`) accept a `--config` argument and will read every setting — including data paths, model dimensions, and training schedule — from the file you pass.

---

## Training

```bash
python scripts/train.py --config configs/default.yaml
```

Training will:
1. Load and pair AIS / SPL files from the paths set in the config.
2. Compute scaling statistics from the training split only (no data leakage).
3. Train the RadialAcousticSurrogate and save the best checkpoint to `checkpoints/`.
4. Write loss curves and visualisations to `results/figures/`.

---

## Evaluation

Run evaluation on a saved checkpoint against the test split:

```bash
python scripts/evaluate.py --config configs/default.yaml --weights checkpoints/best_model.pth
```

Evaluation reports MSE and MAE in both Pa and dB re 1 µPa, and saves a metrics summary plot to `results/figures/`.

---

## Pre-trained Weights

This repository ships a sample model state dict. It can be downloaded to skip the training step by using the checkpoints.dvc file.

```
weights/raindrop_surrogate.pth
```

These weights were trained with the hyperparameters defined in `configs/default.yaml`. They can be used directly for inference or for testing.

## Making Predictions via Command Line

You can quickly generate Sound Pressure Level (SPL) predictions using the included command-line interface. This allows you to run inference on your data without writing custom code.

Run the prediction script from your terminal by passing your trained weights, vessel coordinates, and desired output path:

```bash
python predict.py --config configs/default.yaml \
                  --lat 38.5 \
                  --lon  -27.5 \
                  --speed 11.8 \
                  --type 36 \
                  --length 155 \  
                  --output results/spl_prediction.npy
```

### Required Inputs and Cache Dependencies

After running the training execution, the preprocessed bathymetry and land mask `.npy` files are automatically saved in the `cache/` folder. The command-line inference tool depends on these cached files to structure the target grid coordinates correctly.

### Spatial Boundary Constraints

The inference command will only execute successfully if the provided latitude (`--ship_lat`) and longitude (`--ship_lon`) values fall within the geographical boundaries of the bathymetry grid used during model training.

### Data Pipeline and Automated Scaling

When you call this tool, it automatically executes the underlying data pipeline to prepare and scale your input AIS data:

- The pipeline scales the single observation using the reference statistics computed during training.
- If these scaling statistics are not found in your environment, the pipeline will automatically compute and save them on the spot. Please note that this baseline calculation will cause a slight execution overhead the first time the command is run.

### Command Line Arguments

| Argument | Description |
|---|---|
| `--config` | Path to the configuration (contains the model_wheights `.pth` file) |
| `--lat` | Latitude coordinate of the source vessel |
| `--lon` | Longitude coordinate of the source vessel |
| `--speed` | Speed the source vessel |
| `--type` | Type of the source vessel |
| `--length` | Length of the source vessel |
| `--output` | Destination path for the radial SPL prediction matrix (`.npy`) |

### Interactive Notebook Walkthrough

Complete, step-by-step instructions on how to manually preprocess the datasets, call the model programmatically in Python, and map the outputs into clean radial or Cartesian geographic plots are detailed inside the `user_example.ipynb` file included in this repository.
