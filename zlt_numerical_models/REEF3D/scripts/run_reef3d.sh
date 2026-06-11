#!/bin/bash
set -e

# Check if Conda is installed
if ! which conda >/dev/null 2>&1; then
    echo "Error: Conda is not installed" >&2
    exit 1
fi

# Source conda.sh 
source "$(conda info --base)/etc/profile.d/conda.sh"

# Activate the environment
conda activate reef3d

# Add the Conda libraries to the runtime path
export LD_LIBRARY_PATH="$CONDA_PREFIX/lib:$LD_LIBRARY_PATH"

# Copy the data to the results directory
cp data/bathymetry/geo.dat results/geo.dat
cp data/settings/control.txt results/control.txt
cp data/settings/ctrl.txt results/ctrl.txt
cp data/spectrum/spectrum-file.dat results/spectrum-file.dat

# Run DIVEMesh and REEF3D
cd results
../bin/DIVEMesh
mpirun -n 8 ../bin/REEF3D
