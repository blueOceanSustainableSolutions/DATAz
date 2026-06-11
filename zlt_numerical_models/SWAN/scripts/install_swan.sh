#!/bin/bash
set -e

# Check if Conda is installed
if ! which conda >/dev/null 2>&1; then
    echo "Error: Conda is not installed" >&2
    exit 1
fi

# Source conda.sh 
source "$(conda info --base)/etc/profile.d/conda.sh"

# Accept the Conda terms of service
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r

# Install Mamba
conda create -y -n mamba -c conda-forge mamba

# Activate the environment
conda activate mamba

# Install the remaining packages
mamba create -y -n swan -c conda-forge \
  python=3.12 \
  cdo \
  cdsapi \
  libnetcdf=4.9.2 \
  matplotlib \
  netcdf-fortran=4.6.1 \
  netCDF4 \
  numpy \
  openmpi=4.1.5 \
  pandas
