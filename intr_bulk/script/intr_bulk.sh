#!/bin/bash
set -e

# ======================================================================
#  Intrinsic Value Bulk Calculator  (Alpha Spread)
# ======================================================================
BASE_DIR="/home/dev/stock/intr_bulk"
PYTHON="/home/dev/py/.venv/bin/python"
PY_DIR="$BASE_DIR/py"
OUTPUT_DIR="$BASE_DIR/output"

# Confirm file structure stability
mkdir -p "$OUTPUT_DIR" "$BASE_DIR/input" "$PY_DIR"

echo "=================================================================="
echo " Intrinsic Value Bulk Calculator"
echo "=================================================================="
echo
echo "1. Processing tickers & generating weighted intrinsic-value grid..."
$PYTHON "$PY_DIR/intr_bulk.py"
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
read -p "Press Enter to close this terminal..."