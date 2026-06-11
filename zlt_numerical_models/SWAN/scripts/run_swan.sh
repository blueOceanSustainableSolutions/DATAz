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
conda activate swan

# Add the Conda libraries to the runtime path
export LD_LIBRARY_PATH="$CONDA_PREFIX/lib:$LD_LIBRARY_PATH"

# Run SWAN
cd cases/Faial
python3 init_case.py
