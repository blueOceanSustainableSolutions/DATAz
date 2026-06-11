# REEF3D Condor Seamount Model
This repository contains the Condor Seamount setup used in REEF3D, an open-source phase-resolved wave model targeted at simulating nearshore hydrodynamics over complex bathymetry and coastlines. More information about REEF3D can be found on the [REEF3D GitHub repository](https://github.com/REEF3D/REEF3D).

## Repository Structure
The REEF3D Condor Seamount model is organized according to the following folder structure:

```
+--- README.md
+--- bin
|    +--- DIVEMesh
|    +--- REEF3D
+--- data
|    +--- bathymetry
|    |    +--- geo.dat
|    +--- settings
|    |    +--- control.txt
|    |    +--- ctrl.txt
|    +--- spectrum
|    |    +--- spectrum-file.dat
+--- results
|    +--- .gitkeep
+--- scripts
|    +--- install_reef3d.sh
|    +--- run_reef3d.sh
```

- The `bin` folder contains the `DIVEMesh` and `REEF3D` executables. These programs are used to generate the computational mesh and perform the numerical simulations, respectively.

- The `data` folder contains the input files required to run DIVEMesh and REEF3D. The `bathymetry` subfolder contains the file `geo.dat`, which describes the bathymetry near the Condor Seamount. The `settings` subfolder contains the files `control.txt` and `ctrl.txt`, which define the mesh generation settings and the simulation settings used by DIVEMesh and REEF3D, respectively. Lastly, the `spectrum` subfolder contains the file `spectrum-file.dat`, which describes the wave spectrum used in the wave generation zone.

- The `results` folder contains the files generated during the execution of the model. These files include the simulation outputs and other data generated throughout the model run.

- The `scripts` folder contains the bash scripts used to install and run the REEF3D Condor Seamount model.

## Software Installation
To install REEF3D, run the script `install_reef3d.sh` using:

```bash
bash scripts/install_reef3d.sh
```

## Running the Simulation
To run REEF3D, run the script `run_reef3d.sh` using:

```bash
bash scripts/run_reef3d.sh
```

Please note that the REEF3D Condor Seamount model is presently configured for MPI-based parallel execution and requires 8 processor cores. The number of cores allocated to the simulation may be adjusted by modifying the value of the parameter `M 10` in the `control.txt` and `ctrl.txt` configuration files, and by modifying the value of the parameter `-n` in the `run_reef3d.sh` bash script.
