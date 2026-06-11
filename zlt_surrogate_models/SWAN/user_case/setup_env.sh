#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_NAME="swan_surrogate_env"

if ! command -v conda >/dev/null 2>&1; then
  echo "conda is not available on PATH" >&2
  exit 1
fi

source "$(conda info --base)/etc/profile.d/conda.sh"

if conda env list | awk '{print $1}' | grep -Fxq "$ENV_NAME"; then
  echo "Environment $ENV_NAME already exists. Activating..."
else
  echo "Creating conda environment: $ENV_NAME"
  conda create -y -n "$ENV_NAME" python=3.11
fi

conda activate "$ENV_NAME"

echo "Installing required packages..."
python -m pip install --upgrade pip >/dev/null
python -m pip install -r "$REPO_ROOT/src/requirements.txt"

echo "--------------------------------------------------------"
echo "Environment setup complete! To activate it, run:"
echo "conda activate $ENV_NAME"
echo "--------------------------------------------------------"
