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

# ---------- Positions (unchanged – still take the single newest file) ----------
POSITIONS_SOURCE=$(find "$DOWNLOAD_DIR" -maxdepth 1 -type f -name '*-Positions-*.csv' -printf '%T@ %p\n' | sort -nr | head -n 1 | cut -d' ' -f2-)
if [ -z "$POSITIONS_SOURCE" ]; then
    echo "ERROR: No Schwab Positions file found in: $DOWNLOAD_DIR"
    exit 1
fi

cp "$POSITIONS_SOURCE" "$OUTPUT_DIR/positions.csv"
echo "Using positions file: $(basename "$POSITIONS_SOURCE")"

# ---------- Transactions: find latest file for each account, then merge + sort ----------
# Group by account key (everything before _Transactions_) and keep only the newest timestamp for each.
declare -A LATEST_TXN   # account_key → full path of newest file

while IFS= read -r -d '' file; do
    base=$(basename "$file")
    # Extract account key: everything before "_Transactions_"
    if [[ "$base" =~ ^(.+)_Transactions_([0-9]{8}-[0-9]{6})\.csv$ ]]; then
        key="${BASH_REMATCH[1]}"
        ts="${BASH_REMATCH[2]}"
        if [[ -z "${LATEST_TXN[$key]}" ]]; then
            LATEST_TXN[$key]="$file"
        else
            # Compare timestamps from the filenames (YYYYMMDD-HHMMSS sorts correctly as strings)
            existing_base=$(basename "${LATEST_TXN[$key]}")
            if [[ "$existing_base" =~ _Transactions_([0-9]{8}-[0-9]{6})\.csv$ ]]; then
                existing_ts="${BASH_REMATCH[1]}"
                if [[ "$ts" > "$existing_ts" ]]; then
                    LATEST_TXN[$key]="$file"
                fi
            fi
        fi
    fi
done < <(find "$DOWNLOAD_DIR" -maxdepth 1 -type f -name '*_Transactions_*.csv' -print0)

if [ ${#LATEST_TXN[@]} -eq 0 ]; then
    echo "ERROR: No Schwab Transactions files found in: $DOWNLOAD_DIR"
    exit 1
fi

echo "Found latest transactions files for ${#LATEST_TXN[@]} account(s):"
for key in "${!LATEST_TXN[@]}"; do
    echo "  $key → $(basename "${LATEST_TXN[$key]}")"
done

# Merge into a temporary file, then sort by Date
MERGED_TMP=$(mktemp)
HEADER_WRITTEN=0

for key in "${!LATEST_TXN[@]}"; do
    file="${LATEST_TXN[$key]}"
    # Schwab CSVs typically have:
    #   line 1: "Transactions for account ... as of ..."
    #   line 2: "Date","Action","Symbol",...
    #   then data rows
    #   possibly a "Transactions Total" line at the end
    # We skip the first line and any total/summary lines.

    if [ "$HEADER_WRITTEN" -eq 0 ]; then
        # Keep the header row (2nd line)
        sed -n '2p' "$file" > "$MERGED_TMP"
        HEADER_WRITTEN=1
    fi

    # Append data rows only (skip line 1 and any line that looks like a total)
    tail -n +3 "$file" | grep -v -E '^(,"?Transactions Total|"?Transactions Total)' >> "$MERGED_TMP" || true
done

# Sort by the Date column (first column). Dates are MM/DD/YYYY so we convert for proper ordering.
# Output final sorted file.
{
    # Keep header
    head -n 1 "$MERGED_TMP"
    # Sort data rows by converting MM/DD/YYYY → YYYYMMDD for numeric sort, then restore original
    tail -n +2 "$MERGED_TMP" | \
    awk -F',' '
    {
        # Extract date from first field (handles quoted or unquoted)
        date = $1
        gsub(/^"/, "", date)
        gsub(/".*$/, "", date)          # strip anything after date (e.g. " as of ...")
        split(date, d, "/")
        if (length(d[1]) == 1) d[1] = "0" d[1]
        if (length(d[2]) == 1) d[2] = "0" d[2]
        sortkey = d[3] d[1] d[2]
        print sortkey "," $0
    }' | sort -t',' -k1,1 | cut -d',' -f2-
} > "$OUTPUT_DIR/transactions.csv"

rm -f "$MERGED_TMP"

echo "Merged & sorted transactions written to: $OUTPUT_DIR/transactions.csv"
echo "  (total data rows: $(( $(wc -l < "$OUTPUT_DIR/transactions.csv") - 1 )))"

# ---------- Rest of the pipeline (unchanged) ----------
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