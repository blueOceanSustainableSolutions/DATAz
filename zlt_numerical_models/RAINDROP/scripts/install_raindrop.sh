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
mamba create -y -n raindrop -c conda-forge \
  python=3.12 \
  cartopy \
  copernicusmarine \
  fiona \
  fortran-compiler \
  geopandas \
  make \
  matplotlib \
  netcdf4 \
  numpy \
  pandas \
  pyyaml \
  rich \
  scipy \
  shapely \
  tqdm \
  utm \
  xarray

# Activate the environment
conda activate raindrop

# Compile the acoustics toolbox
make -C solvers/at install
