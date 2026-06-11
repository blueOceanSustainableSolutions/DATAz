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
conda activate mohid

# Add MOHID libraries to the runtime path
export LD_LIBRARY_PATH="$PWD/lib:$LD_LIBRARY_PATH"

# Run MOHID
cd ZLT_4levels/Lvl1/exe
mpirun -n 8 ../../../bin/MohidWater_mpi.exe .
../../../bin/MohidDDC.exe
