DOWNLOAD_DIR="/home/ts/Downloads"
OUTPUT_FILE="../data/tickers_current_positions.csv"

# Add words here (use lowercase, separate with a pipe |)
EXCLUDE_LINES_WHERE_NAME_CONTAINS="etf|fund|money|adm"

# 1. Find the latest CSV file matching your naming pattern
LATEST_FILE=$(ls -1t "$DOWNLOAD_DIR"/*-Positions-*.csv 2>/dev/null | head -n 1)

echo "       Latest File: $LATEST_FILE"

if [[ -z "$LATEST_FILE" ]]; then
    echo "      Error: No matching files found in $DOWNLOAD_DIR"
    exit 1
fi

# Write the header first, then the tickers
{
    echo "Ticker"
    awk -v exclude="$EXCLUDE_LINES_WHERE_NAME_CONTAINS" '
    {
        # Skip blank lines
        if ($0 ~ /^[[:space:]]*$/) next

        # Extract the first two quoted fields: "ticker","description"
        if (match($0, /^"([^"]*)","([^"]*)"/, a)) {
            ticker      = a[1]
            description = a[2]
        } else {
            next
        }

        # Skip header / cash / totals
        if (ticker == "Symbol" ||
            ticker == "Cash & Cash Investments" ||
            ticker == "Positions Total" ||
            ticker == "") next

        # Existing description-based exclusion
        if (tolower(description) !~ exclude) {
            print ticker
        }
    }' "$LATEST_FILE"
} > "$OUTPUT_FILE"