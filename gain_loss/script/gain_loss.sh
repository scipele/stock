#!/bin/bash

set -e

BASE_DIR="/home/dev/stock/gain_loss"
CPP_SRC="$BASE_DIR/cpp/src/gain_loss.cpp"
CPP_PROGRAM="$BASE_DIR/cpp/bin/gain_loss"
PYTHON="/home/dev/py/.venv/bin/python"
PYTHON_SCRIPT="$BASE_DIR/py/create_report.py"
OUTPUT_DIR="$BASE_DIR/output"
REPORT_FILE="$OUTPUT_DIR/days_held.html"
DOWNLOAD_DIR="/home/ts/Downloads"

START_DATE="${1:-}"
END_DATE="${2:-}"

read_date_or_today() {
    local prompt="$1"
    local default_date
    default_date="$(date +%m/%d/%Y)"

    printf '%s [%s]: ' "$prompt" "$default_date" >&2
    IFS= read -r input

    if [ -z "$input" ]; then
        echo "$default_date"
    else
        echo "$input"
    fi
}

if [ -z "$START_DATE" ] || [ -z "$END_DATE" ]; then
    if [ -t 0 ]; then
        START_DATE="$(read_date_or_today "Enter start date (MM/DD/YYYY)")"
        END_DATE="$(read_date_or_today "Enter end date (MM/DD/YYYY)")"
    else
        START_DATE="$(date +%m/%d/%Y)"
        END_DATE="$(date +%m/%d/%Y)"
        echo "No interactive terminal detected; defaulting start and end dates to today: $START_DATE to $END_DATE"
    fi
fi

if [ ! -f "$CPP_SRC" ]; then
    echo "ERROR: C++ source file not found: $CPP_SRC"
    exit 1
fi

if [ ! -x "$PYTHON" ]; then
    echo "ERROR: Python virtual environment not found: $PYTHON"
    exit 1
fi

if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "ERROR: Python report script not found: $PYTHON_SCRIPT"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

if [ ! -x "$CPP_PROGRAM" ]; then
    echo "Compiling C++ gain/loss calculator..."
    g++ -std=c++17 -O2 "$CPP_SRC" -o "$CPP_PROGRAM"
fi

POSITIONS_SOURCE=$(find "$DOWNLOAD_DIR" -maxdepth 1 -type f -name 'Fund-Positions-*.csv' -printf '%T@ %p\n' | sort -nr | head -n 1 | cut -d' ' -f2-)
if [ -z "$POSITIONS_SOURCE" ]; then
    echo "ERROR: No Schwab Positions file found in: $DOWNLOAD_DIR"
    exit 1
fi

TRANSACTIONS_SOURCE=$(find "$DOWNLOAD_DIR" -maxdepth 1 -type f -name '*Transactions*.csv' -printf '%T@ %p\n' | sort -nr | head -n 1 | cut -d' ' -f2-)
if [ -z "$TRANSACTIONS_SOURCE" ]; then
    echo "ERROR: No Schwab Transactions file found in: $DOWNLOAD_DIR"
    exit 1
fi

cp "$POSITIONS_SOURCE" "$OUTPUT_DIR/positions.csv"
cp "$TRANSACTIONS_SOURCE" "$OUTPUT_DIR/transactions.csv"

echo "Running gain/loss calculation for: $START_DATE to $END_DATE"
"$CPP_PROGRAM" "$START_DATE" "$END_DATE"

if [ ! -f "$OUTPUT_DIR/gain_loss.csv" ]; then
    echo "ERROR: C++ program did not create: $OUTPUT_DIR/gain_loss.csv"
    exit 1
fi

"$PYTHON" "$PYTHON_SCRIPT"

if [ ! -f "$REPORT_FILE" ]; then
    echo "ERROR: HTML report was not created: $REPORT_FILE"
    exit 1
fi

echo "Completed successfully."
echo "Report: $REPORT_FILE"
