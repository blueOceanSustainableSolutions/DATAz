# Stage 1: General Preprocessing Pipeline

This directory contains the first stage of the SWAN surrogate modeling pipeline: **General Preprocessing**. The pipeline standardizes, aligns, crops, and interpolates raw waves at the boundary, wind, bathymetry, and SWAN output datasets into structured NetCDF files suitable for subsequent surrogate preprocessing and neural network training.

---

## Table of Contents
1. [Pipeline Overview](#pipeline-overview)
2. [Directory Structure & Modules](#directory-structure--modules)
3. [Data Standardization & Processing Steps](#data-standardization--processing-steps)
4. [Preprocessing Components](#preprocessing-components)
    - [Boundary Wave Forcing](#1-boundary-wave-forcing)
    - [Wind & Bathymetry Inputs](#2-wind--bathymetry-inputs)
    - [SWAN Outputs](#3-swan-outputs)
    - [Visualizations](#4-visualizations)
5. [Command Line Usage Guide](#command-line-usage-guide)
6. [HPC Cluster Submission (SLURM)](#hpc-cluster-submission-slurm)

---

## Pipeline Overview

SWAN (Simulating Waves Nearshore) simulations require waves at the boundary, spatial wind inputs, and a bathymetry grid. The output is a set of spatial arrays representing wave height, period, and direction on a fine grid.

The goal of this general preprocessing pipeline is to:
- **Centralize Configurations**: Handle coordinate mapping, grid resolution, and spatial bounds in one place.
- **Normalize Dimensions**: Ensure all spatial arrays are aligned to a canonical shape of `(time, lat, lon)`.
- **Resample & Interpolate**: Perform bilinear spatial interpolation to the desired grid size (e.g., $128 \times 128$) and linear temporal interpolation to hourly intervals.
- **Feature Engineering**: Deconstruct angular variables (wave direction `PDIR` and boundary wave direction) into continuous trigonometric components (`_sin` and `_cos`) to avoid the $0^\circ \leftrightarrow 360^\circ$ wrap-around discontinuity during model training.
- **Establish Temporal Bounds**: Automatically detect and restrict input datasets to the common overlapping time window across simulation outputs.

---
## Directory Structure & Modules

The files in this directory are structured into **Entry Points** (runnable scripts), **Core Processing Modules**, and **Helper Utilities**:

| File Name | Type | Description |
| :--- | :--- | :--- |
| [run_all_preprocessing.py](run_all_preprocessing.py) | **Orchestrator** | Main orchestrator. Parses `config.swn`, determines the overlapping time window, executes boundary/input/output steps, aligns time axes, and generates visualizations. |
| [1_boundary_preprocessing.py](1_boundary_preprocessing.py) | **Entry Point** | Preprocesses wave boundary forcing. Identifies nearest boundary coordinates and saves boundary wave parameters. |
| [1_input_preprocessing.py](1_input_preprocessing.py) | **Entry Point** | Preprocesses wind components (`u10`, `v10`) and bathymetry elevation. |
| [1_output_preprocessing.py](1_output_preprocessing.py) | **Entry Point** | Preprocesses SWAN outputs (`HSig`, `RTP`, `PDIR`). Mirrors latitude, maps -999 to NaN, and generates directional components. |
| [f_preprocessing_core.py](f_preprocessing_core.py) | **Core Module** | Core preprocessing functions including dataset spatial/temporal interpolation wrappers, variable aggregation, and single-threaded NetCDF saving. |
| [f_boundary_core.py](f_boundary_core.py) | **Core Module** | Boundary point generation, nearest neighbor coordinate mapping via `scipy.spatial.KDTree`, and boundary grid extraction. |
| [visualization.py](visualization.py) | **Core Module** | Spatial maps and point-wise time-series visualization scripts. |
| [f_utils.py](f_utils.py) | **Utilities** | Helper functions for canonical grid layout sorting, NetCDF file loading fallback, bathymetry swapping, and dataset merging. |
| [f_coordinates.py](f_coordinates.py) | **Utilities** | Coordinate search wrappers and time formatters. |
| [f_interpolation.py](f_interpolation.py) | **Utilities** | Bilinear spatial grid interpolation and hourly linear temporal interpolation implementations. |
| [f_inspection.py](f_inspection.py) | **Utilities** | Pretty-print tables summarizing NetCDF dimensions, shape, data types, missing values, and min/max metrics. |
| [run.job](run.job) | **HPC Script** | SLURM submission script to run the preprocessing pipeline on a high-performance computing node. |

---

## Data Standardization & Processing Steps

To ensure consistent ingestion into neural network architectures, the data goes through the following normalization steps:

1. **Grid Layout Canonicalization**:
   - Re-orders dimensions to `[..., lat, lon]`.
   - Forces coordinate labels to be strictly named `lat` and `lon`.
   - Sorts latitudes and longitudes in ascending order (south-to-north, west-to-east).

2. **Spatial Bilinear Interpolation**:
   - Uses `xarray.Dataset.interp` to perform bilinear interpolation onto a target uniform grid size ($N \times N$, e.g., $128 \times 128$).
   - Coordinates match the simulation bounds extracted from the `config.swn` file.

3. **Temporal Alignment & Interpolation**:
   - Detects the common temporal overlap across boundary wave files, wind datasets, and SWAN outputs.
   - Interpolates all datasets to a uniform **1-hour** temporal step.
   - Trims datasets to match the exact same time bounds and time step size.

4. **Trigonometric Representation of Angle Vectors**:
   - Deep learning models struggle with the sharp discontinuity at the boundary of directional fields (e.g., $359^\circ \rightarrow 0^\circ$).
   - Direction fields $\theta$ (in degrees) are converted to sine and cosine components.
   - Applied to the SWAN output peak direction (`PDIR`) and the boundary forcing wave directions.
   - Aggregation of these fields (e.g., temporal or spatial averaging) should be made using the arctangent of the sin/cos components to avoid boundary artifacts.
   - Since the predicted components may not lie exactly on the unit circle, they are first normalized:
     $$
     r = \sqrt{\widehat{\sin\theta}^{\,2} + \widehat{\cos\theta}^{\,2}},
     \qquad
     \widetilde{\sin\theta} = \frac{\widehat{\sin\theta}}{r},
     \qquad
     \widetilde{\cos\theta} = \frac{\widehat{\cos\theta}}{r}.
     $$
   - The angular direction is then reconstructed using:
     $$
     \hat{\theta} = \operatorname{atan2}\!\left(\widetilde{\sin\theta}, \widetilde{\cos\theta}\right),
     $$
     ensuring a valid directional estimate and correct quadrant identification.

---

## Preprocessing Components

### 1. Boundary Wave Forcing
- **Module**: `1_boundary_preprocessing.py` & `f_boundary_core.py`
- **Goal**: Build boundary-only wave forcing. The interior of the simulation domain is filled with `NaN` values, while the perimeter cells are populated with the wave parameters extracted from the ERA5 wave dataset.
- **Process**:
  1. Generate coordinates for the north, south, east, and west perimeter points based on the SWAN box configuration.
  2. Map each boundary point to the nearest ERA5 coordinate index using a `KDTree`.
  3. Extract ERA5 wave parameters (`hs`, `tp`, `dp`) onto the boundary perimeter grid.
  4. Convert the wave direction `dp` into `dp_sin` and `dp_cos` components.

### 2. Wind & Bathymetry Inputs
- **Module**: `1_input_preprocessing.py`
- **Goal**: Standardize wind speed vectors and static sea-bed topography.
- **Process**:
  1. Merge multi-file wind forcing datasets (`wind_atlantic*.nc`) along the time dimension.
  2. Extract `u10` (zonal) and `v10` (meridional) wind components and interpolate to the $N \times N$ grid.
  3. Load bathymetry topography dataset, swap coordinate coordinates from index-space $(x, y)$ to geodetic lat/lon coordinates, crop the grid to the simulation box, and interpolate.

### 3. SWAN Outputs
- **Module**: `1_output_preprocessing.py`
- **Goal**: Standardize target output fields generated by SWAN simulations.
- **Process**:
  1. Read simulation results: Significant Wave Height (`HSig`), Peak Wave Period (`RTP`), and Peak Wave Direction (`PDIR`).
  2. Replace SWAN's default missing value sentinel (`-999`) with `NaN`.
  3. Standardize and interpolate the grids.
  4. Flip coordinates along the latitude axis to resolve SWAN-to-NetCDF spatial mirroring.
  5. Compute `PDIR_sin` and `PDIR_cos` components.
  6. Merge the outputs into a single NetCDF file.

### 4. Visualizations
- **Module**: `visualization.py`
- **Goal**: Output visual sanity checks to confirm data alignment and interpolation sanity.
- **Outputs**:
  - `nc_visualization.png`: Panel plots containing spatial maps of bathymetry, wind vectors, boundary masking, and wave outputs. Points of interest are marked.
  - `nc_timeseries_visualization.png`: Line plots comparing the time-series variables at a specified latitude/longitude coordinate.

---

## Command Line Usage Guide

### Centralized Orchestration
Use `run_all_preprocessing.py` to process the entire pipeline for a given simulation case.

```bash
python run_all_preprocessing.py \
  --project-root /projects/F202500265DT4STF2 \
  --case <CASE_NAME> \
  --save-dir /projects/F202500265DT4STF2/HPC_SWAN_Surrogate_Github/data/general_preprocessing/<CASE_NAME> \
  --grid-size 128 \
  --point-lat 38.58383 \
  --point-lon -28.54117
```

**Key Arguments**:
- `--project-root`: Root workspace path (default: `/projects/F202500265DT4STF2`).
- `--case` or `--folder`: Case folder name under `AutoSWAN/cases/` — sets boundary, input, and output to the same case.
- `--boundary-case`, `--input-case`, `--output-case`: Override individual cases independently.
- `--save-dir`: Path to store the processed NetCDF files (auto-derived from `--case` if omitted).
- `--grid-size`: Interpolation spatial grid resolution (e.g. `128` for $128 \times 128$).
- `--point-lat` & `--point-lon`: Coordinates of the target validation point for time-series extraction.

### Running Individual Stages
You can also trigger individual preprocessing stages using the entry points:

```bash
# 1. Process Boundary Forcing
python 1_boundary_preprocessing.py \
  --project-root /projects/F202500265DT4STF2 \
  --case <CASE_NAME> \
  --save-dir /projects/F202500265DT4STF2/HPC_SWAN_Surrogate_Github/data/general_preprocessing/<CASE_NAME> \
  --waves-pattern "waves_atlantic*.nc"

# 2. Process Forcing Inputs (Wind/Bathymetry)
python 1_input_preprocessing.py \
  --project-root /projects/F202500265DT4STF2 \
  --case <CASE_NAME> \
  --save-dir /projects/F202500265DT4STF2/HPC_SWAN_Surrogate_Github/data/general_preprocessing/<CASE_NAME> \
  --grid-size 128

# 3. Process Simulation Outputs
python 1_output_preprocessing.py \
  --project-root /projects/F202500265DT4STF2 \
  --case <CASE_NAME> \
  --save-dir /projects/F202500265DT4STF2/HPC_SWAN_Surrogate_Github/data/general_preprocessing/<CASE_NAME> \
  --grid-size 128
```

---

## HPC Cluster Submission (SLURM)

For long preprocessing runs on the HPC cluster, use the provided SLURM batch script `run.job`. Before submitting, you **MUST edit the following variables** inside the script:

- **`CASE_FOLDER="<YOUR_CASE_FOLDER>"`**: Update this to point to the desired simulation case (e.g., `SWAN_case_001`).
- **`#SBATCH --account=...`**: Your cluster billing account.
- **`#SBATCH --partition=...`**: Target cluster partition.
- **`CONDA_ENV_NAME`**: Name of your Conda environment (default: `swan_surrogate_env`).
- **`WORKDIR`**: Ensure this points to your specific cloned repository location.

```bash
# Edit the variables in run.job, then submit:
sbatch run.job
```

Job logs are written to `logs/<job_id>.out` and `logs/<job_id>.err` under the working directory.

### Key Notes
- **Threading**: `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS`, and `NUMEXPR_NUM_THREADS` are all set to `1` to prevent library thread over-subscription on shared nodes.
- **Environment**: The `swan_surrogate_env` conda environment is activated. Ensure it has all required Python packages installed.
- **Output**: Preprocessed NetCDF files are written to `$PROJECT_ROOT/HPC_SWAN_Surrogate_Github/data/general_preprocessing/<CASE_FOLDER>/`.

