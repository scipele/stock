#!/bin/bash

# ============================================================
# Schwab Days Held
#
# Overall program runner
#
# 1. Find latest Schwab Positions export
# 2. Find latest Schwab Transaction History export
# 3. Copy them to output/
# 4. Run C++ days_held program
# 5. Generate HTML report with Python
# 6. Open HTML report in default browser
# ============================================================

set -e


# ------------------------------------------------------------
# Program directories
# ------------------------------------------------------------

BASE_DIR="/home/dev/stock/days_held"

CPP_PROGRAM="$BASE_DIR/cpp/bin/days_held"

PYTHON="/home/dev/py/.venv/bin/python"

PYTHON_SCRIPT="$BASE_DIR/py/create_report.py"

OUTPUT_DIR="$BASE_DIR/output"

POSITIONS_FILE="$OUTPUT_DIR/positions.csv"

TRANSACTIONS_FILE="$OUTPUT_DIR/transactions.csv"

REPORT_FILE="$OUTPUT_DIR/days_held.html"


# ------------------------------------------------------------
# Schwab download directory
# ------------------------------------------------------------

DOWNLOAD_DIR="/home/ts/Downloads"


# ------------------------------------------------------------
# Display header
# ------------------------------------------------------------

clear

echo "============================================="
echo " Schwab Days Held"
echo "============================================="
echo


# ------------------------------------------------------------
# Verify required programs/files
# ------------------------------------------------------------

if [ ! -x "$CPP_PROGRAM" ]; then
    echo "ERROR: C++ program not found:"
    echo "  $CPP_PROGRAM"
    exit 1
fi


if [ ! -x "$PYTHON" ]; then
    echo "ERROR: Python virtual environment not found:"
    echo "  $PYTHON"
    exit 1
fi


if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "ERROR: Python report script not found:"
    echo "  $PYTHON_SCRIPT"
    exit 1
fi


mkdir -p "$OUTPUT_DIR"


# ------------------------------------------------------------
# Find latest Schwab Positions export
#
# Schwab filenames look like:
#
# Fund-Positions-2026-08-26-132828.csv
# ------------------------------------------------------------

POSITIONS_SOURCE=$(
    find "$DOWNLOAD_DIR" \
        -maxdepth 1 \
        -type f \
        -name 'Fund-Positions-*.csv' \
        -printf '%T@ %p\n' |
    sort -nr |
    head -n 1 |
    cut -d' ' -f2-
)


if [ -z "$POSITIONS_SOURCE" ]; then
    echo "ERROR: No Schwab Positions file found."
    echo
    echo "Looking for:"
    echo "  $DOWNLOAD_DIR/Fund-Positions-*.csv"
    exit 1
fi


# ------------------------------------------------------------
# Find latest Schwab Transaction History export
#
# Schwab filenames look like:
#
# Fund_XXX456_Transactions_20260826-132818.csv
#
# We intentionally use *Transactions*.csv so the account
# number does not need to be hard-coded.
# ------------------------------------------------------------

TRANSACTIONS_SOURCE=$(
    find "$DOWNLOAD_DIR" \
        -maxdepth 1 \
        -type f \
        -name '*Transactions*.csv' \
        -printf '%T@ %p\n' |
    sort -nr |
    head -n 1 |
    cut -d' ' -f2-
)


if [ -z "$TRANSACTIONS_SOURCE" ]; then
    echo "ERROR: No Schwab Transaction History file found."
    echo
    echo "Looking for:"
    echo "  $DOWNLOAD_DIR/*Transactions*.csv"
    exit 1
fi


# ------------------------------------------------------------
# Display source files
# ------------------------------------------------------------

echo "Schwab files found:"
echo
echo "  Positions:"
echo "    $POSITIONS_SOURCE"
echo
echo "  Transactions:"
echo "    $TRANSACTIONS_SOURCE"
echo


# ------------------------------------------------------------
# Copy source files into output directory
# ------------------------------------------------------------

echo "Copying Schwab files..."
echo

cp "$POSITIONS_SOURCE" "$POSITIONS_FILE"

cp "$TRANSACTIONS_SOURCE" "$TRANSACTIONS_FILE"


echo "  Created:"
echo "    $POSITIONS_FILE"
echo "    $TRANSACTIONS_FILE"
echo


# ------------------------------------------------------------
# Run C++ program
# ------------------------------------------------------------

echo "Running days_held..."
echo

"$CPP_PROGRAM"


# ------------------------------------------------------------
# Verify C++ output
# ------------------------------------------------------------

if [ ! -f "$OUTPUT_DIR/days_held.csv" ]; then
    echo
    echo "ERROR: C++ program did not create:"
    echo "  $OUTPUT_DIR/days_held.csv"
    exit 1
fi


# ------------------------------------------------------------
# Generate HTML report
# ------------------------------------------------------------

echo
echo "Generating HTML report..."
echo

"$PYTHON" "$PYTHON_SCRIPT"


# ------------------------------------------------------------
# Verify HTML output
# ------------------------------------------------------------

if [ ! -f "$REPORT_FILE" ]; then
    echo
    echo "ERROR: HTML report was not created:"
    echo "  $REPORT_FILE"
    exit 1
fi


# ------------------------------------------------------------
# Open report in default browser
# ------------------------------------------------------------

echo
echo "Opening report..."
echo

xdg-open "$REPORT_FILE" >/dev/null 2>&1 &


# ------------------------------------------------------------
# Complete
# ------------------------------------------------------------

echo "============================================="
echo " Complete"
echo "============================================="
echo
echo "Report:"
echo "  $REPORT_FILE"
echo