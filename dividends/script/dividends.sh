#!/bin/bash
# SCRIPT: Dividend & Stability Screening Orchestrator

set -e

# Resolve paths dynamically relative to script execution directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
VENV_PATH="/home/dev/py/.venv/bin/activate"
OUTPUT_SPREADSHEET="$PROJECT_ROOT/output/dividend_analysis.xlsx"

cd "$SCRIPT_DIR"

echo "====================================================================================="
echo " Program - Dividend Yield, Stability & System Rank Mapper"
echo "====================================================================================="
echo

START_TIME=$(date +%s)

# Run Engine Segment Directly (No prompt pause)
echo "============================================"
echo " Running Live Market Scan Data Pipeline"
echo "============================================"
echo "     → Activating production virtual environment..."

if [[ -f "$VENV_PATH" ]]; then
    source "$VENV_PATH"
else
    echo "   [Error] Python environment setup missing at: $VENV_PATH"
    echo
    read -p "Press any key to close terminal..." -n1 -s
    exit 1
fi

echo "     → Launching internal parsing engine..."
python ../py/dividends.py

echo "     → Deactivating environment variables..."
deactivate
echo

# Complete Benchmark Calculations
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo "====================================================================================="
echo " Processing Loop Complete"
echo "   Execution Runtime: $DURATION seconds"
echo "   Output Document Location: $OUTPUT_SPREADSHEET"
echo "====================================================================================="
echo

# Launch LibreOffice Calc automatically
if [[ -f "$OUTPUT_SPREADSHEET" ]]; then
    echo "     → Launching LibreOffice Calc with AutoFilters active..."
    localc "$OUTPUT_SPREADSHEET" & 2>/dev/null
else
    echo "   [Error] Could not launch LibreOffice: Output spreadsheet file not found."
fi
echo

# Prevent terminal from immediately window closing
read -p "Execution complete. Press any key to close terminal..." -n1 -s
echo
