
#!/bin/bash

set -e

INPUT_FILE_A="../data/tickers_current_positions.csv"
INPUT_FILE_B="../data/tickers_dow.csv"
INPUT_FILE_C="../data/tickers_sp_500.csv"
INPUT_FILE_D="../data/tickers_russel_2k.csv"
INPUT_FILE_E="../data/tickers_other.csv"
INPUT_FILE_F="../data/tickers_recent_top_scores.csv"
OUTPUT_FILE="../data/tickers_combined.csv"

# Arguments:
# 1 include_dow
# 2 include_sp500
# 3 include_russell
# 4 include_other
# 5 include_top_scores
# 6 include_current_positions

INCLUDE_DOW="${1:-n}"
INCLUDE_SP500="${2:-n}"
INCLUDE_RUSSELL="${3:-n}"
INCLUDE_OTHER="${4:-n}"
INCLUDE_TOP_SCORES="${5:-n}"
INCLUDE_CUR_POSITIONS="${6:-n}"

mkdir -p "$(dirname "$OUTPUT_FILE")"

# Start with the output header
echo "Ticker,Owned" > "$OUTPUT_FILE"

# Temporary files
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

# ---- Current positions (optional) ----
if [[ "$INCLUDE_CUR_POSITIONS" == "y" && -f "$INPUT_FILE_A" ]]; then
    echo "Including current positions..."
    tail -n +2 "$INPUT_FILE_A" |
        sed 's/\./-/g' |
        awk -F',' 'NF && $1 != "" {print $1 ",Y"}' \
        > "$TMP_DIR/current.txt"
else
    echo "Excluding current positions."
    > "$TMP_DIR/current.txt"
fi

# ---- Dow (optional) ----
if [[ "$INCLUDE_DOW" == "y" && -f "$INPUT_FILE_B" ]]; then
    tail -n +2 "$INPUT_FILE_B" |
        sed 's/\./-/g' |
        awk -F',' 'NF && $1 != "" {print $1 ","}' \
        > "$TMP_DIR/dow.txt"
else
    > "$TMP_DIR/dow.txt"
fi

# ---- S&P 500 (optional) ----
if [[ "$INCLUDE_SP500" == "y" && -f "$INPUT_FILE_C" ]]; then
    tail -n +2 "$INPUT_FILE_C" |
        sed 's/\./-/g' |
        awk -F',' 'NF && $1 != "" {print $1 ","}' \
        > "$TMP_DIR/sp500.txt"
else
    > "$TMP_DIR/sp500.txt"
fi

# ---- Russell 2000 (optional) ----
if [[ "$INCLUDE_RUSSELL" == "y" && -f "$INPUT_FILE_D" ]]; then
    tail -n +2 "$INPUT_FILE_D" |
        sed 's/\./-/g' |
        awk -F',' 'NF && $1 != "" {print $1 ","}' \
        > "$TMP_DIR/russell.txt"
else
    > "$TMP_DIR/russell.txt"
fi

# ---- Other (optional) ----
if [[ "$INCLUDE_OTHER" == "y" && -f "$INPUT_FILE_E" ]]; then
    tail -n +2 "$INPUT_FILE_E" |
        sed 's/\./-/g' |
        awk -F',' 'NF && $1 != "" {print $1 ","}' \
        > "$TMP_DIR/other.txt"
else
    > "$TMP_DIR/other.txt"
fi

# ---- Recent top-score tickers (optional) ----
if [[ "$INCLUDE_TOP_SCORES" == "y" && -f "$INPUT_FILE_F" ]]; then
    tail -n +2 "$INPUT_FILE_F" |
        sed 's/\./-/g' |
        awk -F',' 'NF && $1 != "" {print $1 ","}' \
        > "$TMP_DIR/top_scores.txt"
else
    > "$TMP_DIR/top_scores.txt"
fi

# ---- Merge, deduplicate, prefer Owned=Y ----
cat \
    "$TMP_DIR/current.txt" \
    "$TMP_DIR/dow.txt" \
    "$TMP_DIR/sp500.txt" \
    "$TMP_DIR/russell.txt" \
    "$TMP_DIR/other.txt" \
    "$TMP_DIR/top_scores.txt" |
sort -t',' -k1,1 |
awk -F',' '
NF && $1 != "" {
    if (!seen[$1]) {
        owned[$1] = $2
        seen[$1] = 1
    } else if ($2 == "Y") {
        owned[$1] = "Y"
    }
}
END {
    for (t in owned)
        print t "," owned[t]
}' |
sort >> "$OUTPUT_FILE"

echo "Created: $OUTPUT_FILE"
echo "Current positions included: $INCLUDE_CUR_POSITIONS"
echo "Total tickers: $(($(wc -l < "$OUTPUT_FILE") - 1))"
