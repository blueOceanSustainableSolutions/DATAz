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
conda activate raindrop

# Run RAINDROP
cd examples/azores
python3 ../../bin/runNoiseMapKraken.py
python3 ../../bin/read_binary_file.py azores
python3 ../../bin/runNoiseMap.py
