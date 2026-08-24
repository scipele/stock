DOWNLOAD_DIR="/home/ts/Downloads"
OUTPUT_FILE="../data/tickers_current_positions.csv"

# Add words here (use lowercase, separate with a pipe |)
EXCLUDE_LINES_WHERE_NAME_CONTAINS="etf|fund|money|adm"

# 1. Find the latest CSV file matching your naming pattern
LATEST_FILE=$(ls -1t "$DOWNLOAD_DIR"/Fund-Positions-*.csv 2>/dev/null | head -n 1)

echo "       Latest File: $LATEST_FILE"

if [[ -z "$LATEST_FILE" ]]; then
    echo "      Error: No matching files found in $DOWNLOAD_DIR"
    exit 1
fi

# Get the total number of lines in the file
TOTAL_LINES=$(wc -l < "$LATEST_FILE")

# 2 & 3. Process the file, filter, and output each ticker on a new line
awk -F ',' -v total="$TOTAL_LINES" -v exclude="$EXCLUDE_LINES_WHERE_NAME_CONTAINS" '
NR > 3 && NR <= total - 2 {
    # Clean out all quotes from the row to prevent parsing bugs
    gsub(/"/, "", $0)
    
    # Split the cleaned row by commas into an array called "fields"
    split($0, fields, ",")
    ticker = fields[1]
    description = fields[2]
    
    # Perform case-insensitive matching using the passed variable
    if (tolower(description) !~ exclude) {
        if (ticker != "") {
            print ticker
        }
    }
}' "$LATEST_FILE" > "$OUTPUT_FILE"


