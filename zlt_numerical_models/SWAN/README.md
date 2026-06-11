# SWAN Central Group Model
This repository contains the Central Group setup used in SWAN, an open-source phase-averaged wave model targeted at simulating wind-generated waves in coastal regions and inland waters. More information about SWAN can be found on the [SWAN GitLab repository](https://gitlab.tudelft.nl/citg/wavemodels/swan).

## Repository Structure
The SWAN Central Group model is organized according to the following folder structure:

```
+--- README.md
+--- cases
|    +--- Faial
|    |    +--- data
|    |    |    +--- bathymetry.nc
|    |    +--- results
|    |    |    +--- .gitkeep
|    |    +--- storage
|    |    |    +--- waves_atlantic_202410.nc
|    |    |    +--- waves_atlantic_202411.nc
|    |    |    +--- wind_atlantic_2024-10-01.nc
|    |    |    +--- wind_atlantic_2024-11-01.nc
|    |    +--- init_case.py
|    |    +--- input.json
|    |    +--- swan.exe
|    |    +--- swanrun.sh
+--- core
|    +--- __init__.py
|    +--- analyzis
|    |    +--- __init__.py
|    |    +--- waves_analyzis.py
|    +--- domain
|    |    +--- __init__.py
|    |    +--- grid.py
|    |    +--- task.py
|    +--- input_data
|    |    +--- __init__.py
|    |    +--- bathy_gen.py
|    |    +--- bdc_gen.py
|    |    +--- wind_gen.py
|    +--- simulation_case
|    |    +--- __init__.py
|    |    +--- case.py
|    |    +--- case_options.py
|    +--- simulation_coupling
|    |    +--- coupling.py
|    +--- swan
|    |    +--- __init__.py
|    |    +--- config.py
|    |    +--- swan.py
|    |    +--- utils.py
|    +--- utils
|    |    +--- __init__.py
|    |    +--- cdo.py
|    |    +--- date.py
|    |    +--- files.py
|    |    +--- geo.py
|    |    +--- interpolation.py
|    |    +--- netcdf.py
+--- data_sources
|    +--- __init__.py
|    +--- era5.py
+--- scripts
|    +--- install_swan.sh
|    +--- run_swan.sh
+--- templates
|    +--- swan
|    |    +--- config_template.swn
|    |    +--- config_template_stat.swn
```

- The `cases` folder contains the input files required to run SWAN. The `data` subfolder contains the file `bathymetry.nc`, which describes the bathymetry of the Azores region. The `results` folder contains the files generated during the execution of the model. Lastly, the `storage` folder contains the wave and wind data from the ERA5 reanalysis dataset.

- The `core` folder contains the Python source code responsible for generating the SWAN input files, including bathymetry, wind forcing, and wave boundary conditions, and for launching the SWAN executable using `mpirun` to perform parallel simulations.

- The `data_sources` folder contains Python routines for downloading wave and wind data from the ERA5 reanalysis dataset, which are used to define the forcing and boundary conditions for SWAN simulations.

- The `scripts` folder contains the bash scripts used to install and run the SWAN Central Group model.

- The `templates` folder contains configuration file templates that are used by the Python source code to generate the input files required for SWAN simulations, ensuring a consistent and reproducible model setup.

## Software Installation
To install SWAN, run the script `install_swan.sh` using:

```bash
bash scripts/install_swan.sh
```

## Running the Simulation
To run SWAN, run the script `run_swan.sh` using:

```bash
bash scripts/run_swan.sh
```

Please note that the SWAN Central Group model is presently configured for MPI-based parallel execution and requires 8 processor cores. The number of cores allocated to the simulation may be adjusted by modifying the value of the parameter `num_cores` in the `input.json` configuration file.
