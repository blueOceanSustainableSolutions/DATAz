# User-Case Surrogate Pipeline Manual

This folder provides a complete, modular, and easy-to-use pipeline for running the SWAN Surrogate model inference. You can execute the entire pipeline end-to-end with a single command, or you can run each stage independently for debugging and partial re-runs.

## 0. Setup Environment

Before running the pipeline, set up the required Conda environment by running the setup script:
```bash
chmod +x setup_env.sh
./setup_env.sh
```
This will create a Conda environment named `swan_surrogate_env` and install the necessary dependencies from `src/requirements.txt`. After installation, activate it:
```bash
conda activate swan_surrogate_env
```


## 1. Raw Data Structure (`0_raw_data/`)

The pipeline relies on a strict set of raw NetCDF input files placed in the `0_raw_data` directory. 

```text
0_raw_data/
├── bathy_atlantic.nc             # Static bathymetry data (elevation)
├── waves_atlantic_YYYYMM.nc      # Monthly wave data for boundary conditions
└── wind_atlantic_YYYY-MM-01.nc   # Monthly wind forcing data (u10, v10)
```

- **Bathymetry**: There must be exactly one `bathy_atlantic.nc` file representing the domain depth.
- **Wave Data**: Contains boundary conditions. File format strictly matches `waves_atlantic_*.nc`. The pipeline aggregates these files temporally and slices out the target date.
- **Wind Data**: Contains wind forcings. File format strictly matches `wind_atlantic_*.nc`. Like wave data, these files are aggregated and sliced for the target date.

---

## 2. Running the Full Pipeline

The primary orchestrator script is `main.py`. It delegates the work to individual stages without duplicating logic, and wraps the outputs in a convenient, timestamped run directory.

**To run the full end-to-end pipeline (Stages 1, 2, and 3):**
```bash
conda run -n swan_surrogate_env python main.py --execute --stage stage123 \
    --date 2025-09-01 \
    --duration-hours 48 \
    --max-frames 24
```

**Key CLI parameters you must adjust for your specific run:**
- **`--date`**: The start date (YYYY-MM-DD) to slice from the raw data. Must exist in your raw files.
- **`--duration-hours`**: How many consecutive hours to process starting from `--date` (defaults to 24).
- **`--max-frames`**: How many hourly PNG plots to generate starting from the first hour (defaults to 24).
- **`--stage`**: Which stage(s) to execute (e.g., `stage123`, `stage1`, `stage2`, `stage3`).

**What happens under the hood:**
1. A timestamped directory is created (e.g., `run20260603_170053_stage123`).
2. **Stage 1** slices out the `2025-09-01` date from `0_raw_data/`, applies grid standardizations, and saves spatial inputs to `stage1/`.
3. **Stage 2** takes the Stage 1 outputs, applies the trained scalers, fills the boundary channels via IDW, and builds PyTorch-ready sequences stored as `stage2/sequences.pt`.
4. **Stage 3** loads the surrogate model weights and the generated sequences to produce the final `stage3/stage3_predictions.nc` and hourly PNG frames inside `stage3/frames/`.

---

## 3. Running Stages Individually

You can invoke the individual scripts directly if you want to regenerate specific portions of the pipeline.

### Stage 1: General Preprocessing
Converts raw data into standardized 128x128 grid variables.
```bash
conda run -n swan_surrogate_env python stage1.py --date 2025-09-01
```
*Outputs: `wind_inputs_preprocessed_128x128.nc`, `bathymetry_preprocessed_128x128.nc`, and `boundary_preprocessed_128x128.nc`.*

### Stage 2: Sequence Generation
Generates sequential tensor sequences for the PyTorch model.
```bash
conda run -n swan_surrogate_env python stage2.py
```
*Note: If you don't specify an input folder, `stage2.py` automatically looks for the most recently created `stage1` directory in the `user_case` folder.*
*Outputs: `sequences.pt` and `sequence_summary.json`.*

### Stage 3: Model Inference & Plotting
Runs the surrogate model inference and outputs physical variables + plots.
```bash
conda run -n swan_surrogate_env python stage3.py --date 2025-09-01
```
*Note: Like Stage 2, `stage3.py` will automatically attempt to find the latest `stage2/sequences.pt` and `stage1/` folders to execute.*
*Outputs: `stage3_predictions.nc` and an assortment of `.png` visualizations.*
