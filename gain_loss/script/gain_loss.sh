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
DEFAULT_START_DATE="07/09/2026"

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
        printf 'Enter start date (MM/DD/YYYY) [%s]: ' "$DEFAULT_START_DATE" >&2
        IFS= read -r input_start
        START_DATE="${input_start:-$DEFAULT_START_DATE}"
        END_DATE="$(read_date_or_today "Enter end date (MM/DD/YYYY)")"
    else
        START_DATE="$DEFAULT_START_DATE"
        END_DATE="$(date +%m/%d/%Y)"
        echo "No interactive terminal detected; defaulting start date to $START_DATE and end date to today: $END_DATE"
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

if [ ! -x "$CPP_PROGRAM" ] || [ "$CPP_SRC" -nt "$CPP_PROGRAM" ]; then
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

# ---------- Transactions: pick latest history file per account, then merge + sort ----------
# Group by masked account key (e.g. XXX456). If multiple exports exist for the same
# account, keep the newest export timestamp so later Schwab snapshots win.
declare -A BEST_TXN     # account_key -> full path of chosen file
declare -A BEST_ROWS    # account_key -> row count in chosen file
declare -A BEST_TS      # account_key -> timestamp from filename

while IFS= read -r -d '' file; do
    base=$(basename "$file")
    # Extract account key + export timestamp from filename.
    if [[ "$base" =~ ^(.+)_Transactions_([0-9]{8}-[0-9]{6})\.csv$ ]]; then
        raw_key="${BASH_REMATCH[1]}"
        ts="${BASH_REMATCH[2]}"

        # Prefer the masked account id (e.g. XXX456) to avoid duplicate exports
        # that represent the same account under different prefixes.
        if [[ "$raw_key" =~ (XXX[0-9]+)$ ]]; then
            key="${BASH_REMATCH[1]}"
        else
            key="$raw_key"
        fi

        header_line=$(grep -n -m1 '^"Date","Action","Symbol"' "$file" | cut -d':' -f1)
        if [ -z "$header_line" ]; then
            echo "WARNING: Skipping file with unrecognized header: $(basename "$file")"
            continue
        fi

        data_start=$((header_line + 1))
        row_count=$(tail -n +"$data_start" "$file" | grep -v -E '^(,"?Transactions Total|"?Transactions Total)' | wc -l)

        existing_ts="${BEST_TS[$key]:-}"

        if [[ -z "$existing_ts" || "$ts" > "$existing_ts" ]]; then
            BEST_TXN[$key]="$file"
            BEST_ROWS[$key]="$row_count"
            BEST_TS[$key]="$ts"
        fi
    fi
done < <(find "$DOWNLOAD_DIR" -maxdepth 1 -type f -name '*_Transactions_*.csv' -print0)

if [ ${#BEST_TXN[@]} -eq 0 ]; then
    echo "ERROR: No Schwab Transactions files found in: $DOWNLOAD_DIR"
    exit 1
fi

echo "Selected transaction history files for ${#BEST_TXN[@]} account(s):"
for key in "${!BEST_TXN[@]}"; do
    echo "  $key → $(basename "${BEST_TXN[$key]}") (rows: ${BEST_ROWS[$key]})"
done

# Merge into a temporary file, then sort by Date
MERGED_TMP=$(mktemp)
HEADER_WRITTEN=0

for key in "${!BEST_TXN[@]}"; do
    file="${BEST_TXN[$key]}"
    # Schwab CSV layouts can vary. Detect the real header line instead of assuming line numbers.
    header_line=$(grep -n -m1 '^"Date","Action","Symbol"' "$file" | cut -d':' -f1)
    if [ -z "$header_line" ]; then
        echo "WARNING: Skipping file with unrecognized header: $(basename "$file")"
        continue
    fi

    if [ "$HEADER_WRITTEN" -eq 0 ]; then
        header_row=$(sed -n "${header_line}p" "$file")
        echo "\"AccountId\",${header_row}" > "$MERGED_TMP"
        HEADER_WRITTEN=1
    fi

    data_start=$((header_line + 1))
    tail -n +"$data_start" "$file" | \
    grep -v -E '^(,"?Transactions Total|"?Transactions Total)' | \
    awk -v acct="$key" '{ print "\"" acct "\"," $0 }' >> "$MERGED_TMP" || true
done

if [ "$HEADER_WRITTEN" -eq 0 ]; then
    echo "ERROR: Could not find a valid transactions CSV header in selected files."
    rm -f "$MERGED_TMP"
    exit 1
fi

# Sort by the Date column (first column). Dates are MM/DD/YYYY so we convert for proper ordering.
# Output final sorted file.
{
    # Keep header
    head -n 1 "$MERGED_TMP"
    # Sort data rows by converting MM/DD/YYYY in the Date column to YYYYMMDD, then restore original.
    tail -n +2 "$MERGED_TMP" | \
    awk -F',' '
    {
        date = $2
        gsub(/"/, "", date)
        if (match(date, /[0-9]{1,2}\/[0-9]{1,2}\/[0-9]{4}/) == 0) next
        date = substr(date, RSTART, RLENGTH)
        split(date, d, "/")
        sortkey = sprintf("%04d%02d%02d", d[3], d[1], d[2])
        print sortkey "," $0
    }' | sort -t',' -k1,1 | cut -d',' -f2-
} > "$OUTPUT_DIR/transactions.csv"

rm -f "$MERGED_TMP"

echo "Merged & sorted transactions written to: $OUTPUT_DIR/transactions.csv"
echo "  (total data rows: $(( $(wc -l < "$OUTPUT_DIR/transactions.csv") - 1 )))"

LATEST_TXN_DATE=$(awk -F',' '
NR > 1 {
    date = $2
    gsub(/"/, "", date)
    if (match(date, /[0-9]{1,2}\/[0-9]{1,2}\/[0-9]{4}/) == 0) next
    date = substr(date, RSTART, RLENGTH)
    split(date, d, "/")
    key = sprintf("%04d%02d%02d", d[3], d[1], d[2])
    if (key > max_key) {
        max_key = key
        max_date = date
    }
}
END {
    print max_date
}' "$OUTPUT_DIR/transactions.csv")

if [ -n "$LATEST_TXN_DATE" ]; then
    echo "  (latest transaction date in merged file: $LATEST_TXN_DATE)"
fi

# ---------- Rest of the pipeline (unchanged) ----------
echo "Running gain/loss calculation for: $START_DATE to $END_DATE"
"$CPP_PROGRAM" "$START_DATE" "$END_DATE"

if [ ! -f "$OUTPUT_DIR/gain_loss.csv" ]; then
    echo "ERROR: C++ program did not create: $OUTPUT_DIR/gain_loss.csv"
    exit 1
fi

"$PYTHON" "$PYTHON_SCRIPT" "$START_DATE" "$END_DATE"

if [ ! -f "$REPORT_FILE" ]; then
    echo "ERROR: HTML report was not created: $REPORT_FILE"
    exit 1
fi

open_report() {
    if command -v gio >/dev/null 2>&1; then
        gio open "$REPORT_FILE" >/dev/null 2>&1 && return 0
    fi

    if command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$REPORT_FILE" >/dev/null 2>&1 && return 0
    fi

    if command -v code >/dev/null 2>&1; then
        code "$REPORT_FILE" >/dev/null 2>&1 && return 0
    fi

    return 1
}

open_report || echo "WARNING: Could not open report automatically."

echo "Completed successfully."
echo "Report: $REPORT_FILE"