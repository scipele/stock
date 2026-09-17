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
# Find all Schwab Positions exports from every account.
#
# Schwab account exports are named like:
#
#   Indiv_Tony-Positions-2026-09-16-231602.csv
#   Roth_Mary-Positions-2026-09-16-231629.csv
#
# We intentionally match any file ending in "-Positions-*.csv"
# so the script can merge all account holdings together.
# ------------------------------------------------------------

mapfile -t POSITIONS_SOURCES < <(
    find "$DOWNLOAD_DIR" \
        -maxdepth 1 \
        -type f \
        -name '*-Positions-*.csv' \
        -printf '%T@ %p\n' |
    sort -nr |
    cut -d' ' -f2-
)


if [ "${#POSITIONS_SOURCES[@]}" -eq 0 ]; then
    echo "ERROR: No Schwab Positions files found."
    echo
    echo "Looking for:"
    echo "  $DOWNLOAD_DIR/*-Positions-*.csv"
    exit 1
fi


# ------------------------------------------------------------
# Find all Schwab Transaction History exports.
#
# Schwab filenames look like:
#
#   Fund_XXX456_Transactions_20260826-132818.csv
#
# We intentionally use *Transactions*.csv so the account
# number does not need to be hard-coded.
# ------------------------------------------------------------

mapfile -t TRANSACTIONS_SOURCES < <(
    find "$DOWNLOAD_DIR" \
        -maxdepth 1 \
        -type f \
        -name '*Transactions*.csv' \
        -printf '%T@ %p\n' |
    sort -nr |
    cut -d' ' -f2-
)


if [ "${#TRANSACTIONS_SOURCES[@]}" -eq 0 ]; then
    echo "ERROR: No Schwab Transaction History files found."
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
echo "  Positions files:"
for file in "${POSITIONS_SOURCES[@]}"; do
    echo "    $file"
done
echo
echo "  Transactions files:"
for file in "${TRANSACTIONS_SOURCES[@]}"; do
    echo "    $file"
done
echo


# ------------------------------------------------------------
# Merge all positions files into a single CSV that the C++ code
# expects. This keeps only Equity rows and combines duplicate
# symbols across accounts into a single total quantity.
# ------------------------------------------------------------

echo "Merging positions files..."
echo

"$PYTHON" - "$POSITIONS_FILE" "${POSITIONS_SOURCES[@]}" <<'PY'
import csv
import sys
from pathlib import Path

output_path = Path(sys.argv[1])
source_files = [Path(p) for p in sys.argv[2:]]

merged = {}


def parse_number(value):
    if value is None:
        return 0.0

    text = str(value).strip().strip('"')
    if text in ("", "--", "N/A"):
        return 0.0

    text = text.replace('$', '').replace(',', '').replace('%', '').strip()
    if text in ("", "--", "N/A"):
        return 0.0

    try:
        return float(text)
    except ValueError:
        return 0.0


for source_file in source_files:
    with source_file.open("r", newline="") as infile:
        rows = list(csv.reader(infile))

    header = None
    header_index = None
    for i, row in enumerate(rows):
        if not row or all(cell.strip() == "" for cell in row):
            continue
        cleaned = [cell.strip().strip('"') for cell in row]
        if any(cell == "Symbol" for cell in cleaned):
            header = cleaned
            header_index = i
            break

    if header is None:
        continue

    lookup = {name: idx for idx, name in enumerate(header)}
    for row in rows[header_index + 1:]:
        if not row or all(cell.strip() == "" for cell in row):
            continue
        if len(row) <= max(lookup.values()):
            continue

        symbol = row[lookup["Symbol"]].strip().strip('"')
        if not symbol:
            continue
        if symbol in {"Positions Total", "Cash & Cash Investments"}:
            continue

        if "Asset Type" in lookup:
            asset_type = row[lookup["Asset Type"]].strip().strip('"')
        else:
            asset_type = ""

        if asset_type != "Equity":
            continue

        qty = parse_number(row[lookup["Qty (Quantity)"]]) if "Qty (Quantity)" in lookup else 0.0
        description = row[lookup["Description"]].strip().strip('"') if "Description" in lookup else ""

        if qty == 0:
            continue

        entry = merged.setdefault(symbol, {"Description": description, "Qty": 0.0})
        entry["Qty"] += qty
        if not entry["Description"] and description:
            entry["Description"] = description

with output_path.open("w", newline="") as outfile:
    writer = csv.writer(outfile)
    writer.writerow(["Symbol", "Description", "Qty (Quantity)", "Asset Type"])
    for symbol, data in sorted(merged.items()):
        writer.writerow([symbol, data["Description"], data["Qty"], "Equity"])
PY


echo "  Created:"
echo "    $POSITIONS_FILE"
echo


# ------------------------------------------------------------
# Merge all transaction files into a single CSV.
# ------------------------------------------------------------

echo "Merging transaction files..."
echo

"$PYTHON" - "$TRANSACTIONS_FILE" "${TRANSACTIONS_SOURCES[@]}" <<'PY'
import csv
import sys
from pathlib import Path

output_path = Path(sys.argv[1])
source_files = [Path(p) for p in sys.argv[2:]]

header_written = False
header = None

with output_path.open("w", newline="") as outfile:
    writer = csv.writer(outfile)

    for source_file in source_files:
        with source_file.open("r", newline="") as infile:
            rows = list(csv.reader(infile))

        for row in rows:
            if not row or all(cell.strip() == "" for cell in row):
                continue

            cleaned = [cell.strip().strip('"') for cell in row]
            if any(cell == "Date" for cell in cleaned):
                if not header_written:
                    writer.writerow(cleaned)
                    header_written = True
                    header = cleaned
                continue

            if header is None:
                continue

            writer.writerow(row)
PY


echo "  Created:"
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