#!/bin/bash

set -e

# --------------------------------------------------
# Asset Allocation Report Runner
# --------------------------------------------------
BASE_DIR="/home/dev/stock/asset_alloc"
PYTHON="/home/dev/py/.venv/bin/python"

PY_DIR="$BASE_DIR/py"
OUTPUT_DIR="$BASE_DIR/output"


echo "======================================"
echo " Asset Allocation Report"
echo "======================================"
echo

echo "1. Processing Schwab account..."
$PYTHON "$PY_DIR/asset_alloc.py"

echo
echo "2. Processing John Hancock account..."
$PYTHON "$PY_DIR/jh.py"

echo
echo "3. Combining portfolio Assets..."
$PYTHON "$PY_DIR/portfolio.py"

echo
echo "4. Building allocation reports..."
$PYTHON "$PY_DIR/report.py"

echo
echo "5. Building HTML dashboard..."
$PYTHON "$PY_DIR/dashboard.py"

echo
echo "======================================"
echo " Complete"
echo "======================================"
echo

echo "Generated files:"
echo 

ls -lh "$OUTPUT_DIR"


echo
echo "6. Opening report..."
echo "$OUTPUT_DIR/allocation_report.html"

xdg-open "$OUTPUT_DIR/allocation_report.html" >/dev/null 2>&1 &

