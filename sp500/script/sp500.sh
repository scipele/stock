#!/bin/bash
set -e

# ======================================================================
#  S&P 500 Intrinsic Value Engine - Orchestrator
# ======================================================================

BASE_DIR="/home/dev/stock/sp500"
PYTHON="/home/dev/py/.venv/bin/python"

PY_DIR="$BASE_DIR/py"
OUTPUT_DIR="$BASE_DIR/output"

# Confirm file structure stability
mkdir -p "$OUTPUT_DIR"

echo "=================================================================="
echo " Running S&P 500 Intrinsic Valuation Engine"
echo "=================================================================="
echo

echo "1. Processing models & generating data grids..."
$PYTHON "$PY_DIR/sp500.py"

echo
echo "=================================================================="
echo " Run Finished Successfully"
echo "=================================================================="
echo

echo "Generated Files:"
if [ -d "$OUTPUT_DIR" ]; then
    ls -lh "$OUTPUT_DIR"
fi

echo
echo "Opening graph artifact..."
xdg-open "$OUTPUT_DIR/sp500_intrinsic_chart.png" >/dev/null 2>&1 &

echo
read -p "Press Enter to close this terminal..."
