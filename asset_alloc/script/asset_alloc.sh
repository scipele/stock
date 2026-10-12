#!/bin/bash
set -e

BASE_DIR="/home/dev/stock/asset_alloc"
PYTHON="/home/dev/py/.venv/bin/python"

PY_DIR="$BASE_DIR/py"
OUTPUT_DIR="$BASE_DIR/output"

echo "======================================"
echo " Asset Allocation Report"
echo "======================================"
echo

echo "1. Importing Schwab positions → all_assets.csv..."
$PYTHON "$PY_DIR/schwab.py"

# Optional: if you still use manual holdings and want them merged
# echo "1b. Loading manual assets..."
# $PYTHON "$PY_DIR/manual.py"
# (then you’d need a small merge step — see below)

echo
echo "2. Building allocation reports..."
$PYTHON "$PY_DIR/asset_alloc.py"

echo
echo "3. Building HTML dashboard..."
$PYTHON "$PY_DIR/dashboard.py"

echo
echo "======================================"
echo " Complete"
echo "======================================"
echo

echo "Generated files:"
ls -lh "$OUTPUT_DIR"

echo
echo "Opening report..."
xdg-open "$OUTPUT_DIR/allocation_report.html" >/dev/null 2>&1 &

echo
read -p "Press Enter to close this terminal..."