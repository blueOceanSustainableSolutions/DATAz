# RAINDROP ZLT Model
This repository contains the ZLT setup used in RAINDROP, a Python-based software developed by blueOASIS to generate real-time holistic underwater acoustic maps. More information about RAINDROP can be found on the [RAINDROP GitBook](https://bo0-2.gitbook.io/raindrop-users-guide).

## Repository Structure
The RAINDROP ZLT model is organized according to the following folder structure:

```
+--- README.md
+--- bin
|    +--- assets
|    |    +--- logo_bo.png
|    |    +--- logo_raindrop.png
|    +--- generateNetCDF.py
|    +--- pickle_to_csv.py
|    +--- readAIS.py
|    +--- read_binary_file.py
|    +--- readshd.py
|    +--- runField3D.py
|    +--- runKepler.py
|    +--- runKraken.py
|    +--- runNoiseMap.py
|    +--- runNoiseMapField3D.py
|    +--- runNoiseMapKraken.py
|    +--- runNoiseMapPlot.py
|    +--- runPlot.py
|    +--- writeBathymetry.py
|    +--- writeEnvironment.py
|    +--- writeFLP.py
|    +--- writeSPL.py
+--- examples
|    +--- azores
|    |    +--- ais
|    |    |    +--- position_report.csv
|    |    |    +--- static_ship_data.csv
|    |    +--- bathymetry
|    |    |    +--- coastline
|    |    |    |    +--- azores.cpg
|    |    |    |    +--- azores.dbf
|    |    |    |    +--- azores.prj
|    |    |    |    +--- azores.shp
|    |    |    |    +--- azores.shx
|    |    |    +--- bathymetry.csv
|    |    +--- calcs
|    |    |    +--- freq
|    |    |    |    +--- freq63
|    |    +--- out
|    |    |    +--- ais
|    |    |    +--- latest_maps
|    |    |    +--- maps
|    |    |    +--- nc
|    |    |    +--- pickles
|    |    +--- sources
|    |    |    +--- source1.srcs
|    |    +--- SSP
|    |    |    +--- sound_speed_profile.dat
|    |    +--- controls.yaml
|    |    +--- .gitignore
|    |    +--- azores.dvc
+--- scripts
|    +--- install_raindrop.sh
|    +--- run_raindrop.sh
+--- solvers
|    +--- at
+--- tools
|    +--- AIS
|    |    +--- .gitignore
|    |    +--- aisstream.io
|    +--- Copernicus
|    |    +--- .gitignore
|    |    +--- getSSP_profile.py
```

- The `bin` folder contains the RAINDROP Python source code.

- The `examples` folder contains the input files required to run RAINDROP. The `ais` subfolder contains information about ship ID, position, velocity, name, type, and length. The `bathymetry` subfolder contains the bathymetry of the ZLT. The `calcs` subfolder contains internal files used by RAINDROP to compute the noise maps. The `out` subfolder contains the ais data and noise maps in png, pickle, and netCDF format at each timestep. The `sources` subfolder contains information about the ships in the ZLT at each timestep. Lastly, the `SSP` subfolder contains the sound speed profile considered in the ZLT model.

- The `scripts` folder contains the bash scripts used to install and run the RAINDROP ZLT model.

- The `solvers` folder contains the Acoustics Toolbox Fortran source code. During the installation process, these files are compiled into executable binaries that are subsequently invoked by RAINDROP.

- The `tools` folder contains Python routines used to farm AIS data from aisstream.to and to determine the sound speed profile at a given coordinate using data from the Copernicus Marine Data Store.

## Software Installation
To install RAINDROP, run the script `install_raindrop.sh` using:

```bash
bash scripts/install_raindrop.sh
```

## Running the Simulation
To run RAINDROP, run the script `run_raindrop.sh` using:

```bash
bash scripts/run_raindrop.sh
```

Please note that the RAINDROP ZLT model is presently configured using 8 processor cores. The number of cores allocated to the simulation may be adjusted by modifying the value of the parameter `nCores` in the `controls.yaml` configuration file.
