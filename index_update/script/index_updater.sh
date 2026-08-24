#!/bin/bash

# Dynamically locate the directory path containing this runner script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Define your explicit virtual environment Python path
VENV_PYTHON="/home/dev/py/.venv/bin/python"

# Check if the virtual environment exists before running
if [ ! -f "$VENV_PYTHON" ]; then
    echo "[-] Error: Virtual environment python not found at $VENV_PYTHON"
    echo "[*] Falling back to system python3..."
    VENV_PYTHON="python3"
fi

# Run target Python interface using absolute navigation anchors
"$VENV_PYTHON" "$SCRIPT_DIR/../py/index_updater.py"
