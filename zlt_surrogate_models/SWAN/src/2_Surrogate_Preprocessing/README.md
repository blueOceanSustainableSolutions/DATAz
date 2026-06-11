# Stage 2: Surrogate Preprocessing Pipeline

This directory contains the second stage of the SWAN surrogate modeling pipeline: **Surrogate Preprocessing**. The pipeline takes the standardized NetCDF files generated in Stage 1 and processes them into scaled, split, and sequenced PyTorch tensors (`sequences.pt`) ready for training the neural network surrogate model.

---

## Table of Contents
1. [Pipeline Overview](#pipeline-overview)
2. [Directory Structure & Modules](#directory-structure--modules)
3. [Processing Steps](#processing-steps)
4. [Command Line Usage Guide](#command-line-usage-guide)
5. [HPC Cluster Submission (SLURM)](#hpc-cluster-submission-slurm)

---

## Pipeline Overview

Deep learning models require structured, scaled data partitioned into training, validation, and test sets. Since wave propagation depends on past wind and boundary forcing, the data must be chunked into temporal sequences.

The goal of this surrogate preprocessing pipeline is to:
- **Clean Data**: Identify and replace any non-finite values (`NaN`/`Inf`).
- **Data Splitting**: Split the contiguous time-series datasets temporally into Train, Validation, and Test sets based on predefined ratios.
- **Normalization**: Fit scalers on the training set and apply them to all sets to stabilize neural network training.
- **Temporal Windowing**: Construct sequences with historical windows (e.g., $t-k$ to $t$) for input variables (wind, boundary forcing) alongside static variables (bathymetry) and corresponding target outputs at time $t$.
- **Boundary Fill**: Fill the interior of the boundary grid using Inverse Distance Weighting (IDW) to provide continuous input fields for the model.
- **Sequence Generation**: Save the final constructed tensors to disk as `sequences.pt` for fast loading in Stage 3.

---

## Directory Structure & Modules

The files in this directory include **Entry Points**, **Data Processing Modules**, and **Helper Utilities**:

| File Name | Type | Description |
| :--- | :--- | :--- |
| [1_PREPROCESS.py](1_PREPROCESS.py) | **Entry Point** | Main script. Runs all data loading, cleaning, splitting, scaling, sequence generation, and saving steps end-to-end. |
| [f_data_processing.py](f_data_processing.py) | **Core Module** | Discovers case folders and loads all grouped NetCDF data lazily via `xarray`, handles temporal splitting, missing value cleanup, IDW interior filling, and scales features via `scikit-learn` scalers. |
| [f_sequence_core.py](f_sequence_core.py) | **Core Module** | Contains logic to build temporal input-target sequences, generates sequence combinations across splits, saves PyTorch sequence datasets (`sequences.pt`), and exports validation plots. |
| [config.py](config.py) | **Config Shim** | Forwards configuration from the unified `src/config.py` and provides `print_config()` for Stage 2. |
| [run.job](run.job) | **HPC Script** | SLURM submission script to run the Stage 2 pipeline on a high-performance computing node. |

---

## Processing Steps

1. **Environment and Config Initialization**: Loads configuration and logs paths, variables, and experiment details.
2. **Data Loading**: Recursively finds and opens NetCDF datasets from Stage 1 using `xarray`.
3. **Preprocessing**: Replaces non-finite values with a fallback (e.g., `0.0`).
4. **Dataset Split**: Divides contiguous timesteps into `Train` (70%), `Validation` (15%), and `Test` (15%) splits globally.
5. **Data Scaling**: Fits scalers per variable on the Training split, then scales all splits to standardize feature distributions.
6. **Sequence Generation**: Stacks features into temporal windows, using $k$ past time steps of wind and boundary conditions to predict wave outputs at the current time step.
7. **Boundary IDW Fill**: Fills interior zero-values of the boundary condition maps based on nearest known values.
8. **Save Artifacts**: Dumps the PyTorch tensors into `sequences.pt` and exports a few verification figures.

---

## Command Line Usage Guide

Use `1_PREPROCESS.py` to process datasets into sequences.

```bash
python 1_PREPROCESS.py \
  --sequence-count All \
  --split-strategy temporal \
  --train-scaler \
  --validation-figures 2
```

**Key Arguments**:
- `--sequence-count`: The number of sequences to build, or `"All"` to use all available generated sequences. (Default: `500`)
- `--sequence-name`: Subfolder name for output. If omitted, it defaults to the value of `--sequence-count`.
- `--train-scaler`: If provided, fits a new scaler from scratch. Otherwise, it tries to load an existing scaler.
- `--sequences-root`: Root directory for output sequences.
- `--split-strategy`: Strategy for sampling sequences (`temporal` or `random`). (Default: `temporal`)
- `--validation-figures`: Number of visual verification plots to generate per split. (Default: `2`)

*Note: The script uses the paths (`DATA_PATH`, `SCALER_PATH`) defined in `config.py` by default.*

---

## HPC Cluster Submission (SLURM)

For large sequence generation runs (e.g., `--sequence-count All`), run this on the HPC cluster using the provided SLURM batch script `run.job`. Before submitting, you **MUST edit the following variables** inside the script:

- **`CASE_SEQUENCES_ROOT`**: Path where the output sequences should be generated.
- **`SEQUENCE_COUNT="500"`**: Number of sequences to generate, or `"All"` for the full dataset.
- **`#SBATCH --account=...`**: Your cluster billing account.
- **`#SBATCH --partition=...`**: Target cluster partition.
- **`CONDA_ENV_NAME`**: Name of your Conda environment (default: `swan_surrogate_env`).

```bash
# Edit the variables in run.job, then submit:
sbatch run.job
```

Job logs are written to `logs/<job_id>.out` and `logs/<job_id>.err`.

### Key Notes
- **Environment**: The `swan_surrogate_env` conda environment is activated.
- **Default Output**: Sequences are saved to `$PROJECT_ROOT/data/sequences/<sequence_name>/sequences.pt`.