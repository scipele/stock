#!/bin/bash

set -e

BASE_DIR="/home/dev/stock/cur_stock_pos"
PYTHON="/home/dev/py/.venv/bin/python"
PYTHON_SCRIPT="cur_stock_pos.py"
PY_DIR="$BASE_DIR/py"
OUTPUT_DIR="$BASE_DIR/output"

echo "======================================"
echo " Read Current Stock Positions"
echo "======================================"
echo

$PYTHON "$PY_DIR"/"$PYTHON_SCRIPT"

echo
read -p "Press Enter to close this terminal..."