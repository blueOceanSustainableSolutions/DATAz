# MOHID ZLT Model
This repository contains the ZLT setup used in  MOHID Water, an open-source oceanographic model targeted at simulating coastal and estuarine hydrodynamics. More information about MOHID can be found on the [MOHID GitHub repository](https://github.com/Mohid-Water-Modelling-System/Mohid).

## Overview
The MOHID ZLT model uses a nested downscaling method across four domains (Level 1 to Level 4), where domain size decreases and resolution increases at subsequent levels:

- Level 1: A 2D model with a 4000 m resolution spanning the entire Azores archipelago, used exclusively to simulate astronomical tides.
- Level 2: A 3D model that shares the same 4000 m resolution as Level 1 and covers an only slightly smaller area. It incorporates full atmospheric and oceanographic effects.
- Level 3: A 3D intermediate downscaling step with a finer resolution of 2000 m.
- Level 4: The highest-resolution 3D domain (500 m), specifically centered around the Condor Seamount.

## Repository Structure
The MOHID ZLT model is organized according to the following folder structure:

```
+--- README.md
+--- bin
|    +--- MohidDDC.exe
|    +--- MohidWater_mpi.exe
+--- GeneralData
|    +--- Bathymetry
|    |    +--- ZLT_Lvl1_4000m.dat
|    |    +--- ZLT_Lvl2_4000m_smooth_v02.dat
|    |    +--- ZLT_Lvl3_2000m_smooth_v02.dat
|    |    +--- ZLT_Lvl4_500m_smooth_v02.dat
|    +--- Meteo
|    |    +--- ERA5
|    |    |    +--- era5.hdf5
|    +--- Ocean
|    |    +--- CMEMS
|    |    |    +--- cmems.hdf5
|    |    +--- FES
|    |    |    +--- FES2014_ZLT.hdf5
|    +--- TimeSeries
|    |    +--- TimeSerieLocation.dat
+--- lib
|    +--- libhdf5.so.10
|    +--- libhdf5_fortran.so.10
|    +--- libhdf5_hl.so.10
|    +--- libhdf5hl_fortran.so.10
|    +--- libifcoremt.so.5
|    +--- libifport.so.5
|    +--- libimf.so
|    +--- libintlc.so.5
|    +--- libirng.so
|    +--- libnetcdf.so.19
|    +--- libnetcdff.so.7
|    +--- libsvml.so
+--- scripts
|    +--- install_mohid.sh
|    +--- run_mohid.sh
+--- ZLT_4levels
|    +--- Lvl1
|    |    +--- data
|    |    |    +--- Atmosphere_1.dat
|    |    |    +--- Geometry_1.dat
|    |    |    +--- Hydrodynamic_1.dat
|    |    |    +--- InterfaceSedimentWater_1.dat
|    |    |    +--- InterfaceWaterAir_1.dat
|    |    |    +--- Model_1.dat
|    |    |    +--- Nomfich_1.dat
|    |    |    +--- Tide_1.dat
|    |    |    +--- Turbulence_1.dat
|    |    |    +--- WaterProperties_1.dat
|    |    +--- exe
|    |    |    +--- nomfich.dat
|    |    |    +--- tree.dat
|    |    +--- res
|    |    |    +--- Run_1
|    |    +--- Lvl2
|    |    |    +--- ...
```

- The `bin` folder contains the `MohidDDC.exe` and `MohidWater_mpi.exe` executables. These programs are used to combine results originating from a simulation using domain decomposition and run the MOHID simulation, respectively.

- The `GeneralData` folder contains external input files related to bathymetry, the ERA5 meteorological boundary conditions, the CMEMS oceanographic boundary conditions, the FES astronomical tide constituents, and the location file for the time series extraction.

- The `lib` folder contains HDF5, MPI, and NetCFD dependencies required by MOHID.

- The `scripts` folder contains the bash scripts used to install and run the MOHID ZLT model.

- The `ZLT_4levels` folder contains the simulation setup, which is organised in nested structure (Level 2 inside of Level 1, Level 3 inside of Level 2, etc.). Note that the graph above only shows the tree up to the second level. Each folder `Lvl{1-4}` contains the directories:

    - `data`: Setup files for different MOHID modules
    - `exe`: Files describing the folder structure for MOHID
    - `res`: Empty folders in which the HDF and time series output files are placed when running the simulation

## Software Installation
To install MOHID, run the script `install_mohid.sh` using:

```bash
bash scripts/install_mohid.sh
```

For advanced users attempting a custom compilation, instructions are given [here](https://github.com/Mohid-Water-Modelling-System/Mohid/tree/master/Solutions/mohid-in-linux).

## Running the Simulation
To run MOHID, run the script `run_mohid.sh` using:

```bash
bash scripts/run_mohid.sh
```

Please note that the MOHID ZLT model is presently configured using 8 processor cores. The number of cores allocated to the simulation may be adjusted in the `tree.dat` configuration file, shown below.

```
! This first line needs to be commented
! This second line needs to be commented, too
+../exe : 1
++../Lvl2/exe : 1
+++../Lvl2/Lvl3/exe : 1
++++../Lvl2/Lvl3/Lvl4/exe : 5
```

This file specifies the relative paths to the location of the `exe` folders at each level, which contain the `nomfich.dat` files. The number behind each colon describes the number of processors used to compute the corresponding level. Hence, every nested domain is computed on separate processors. Moreover, domain decomposition is utilized at Level 4 to further split computational load. Currently, MOHID only supports domain decomposition on the lowest level, so only the corresponding number may be adapted. Note that the total number of processors indicated in the `tree.dat` configuration file must correspond to the number of processors indicated using the parameter `-n` in the `run_mohid.sh` bash script. If domain decomposition is used at the lowest level, it is necessary to reassemble the separate HDF files produced by MPI after the run. This command (`MohidDDC.exe`) is already included in the `run_mohid.sh` bash script.
