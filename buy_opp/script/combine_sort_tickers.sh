#!/bin/bash

INPUT_FILE_A="../data/tickers_current_positions.csv"
INPUT_FILE_B="../data/tickers_dow.csv"
INPUT_FILE_C="../data/tickers_sp_500.csv"
INPUT_FILE_D="../data/tickers_russel_2k.csv"
INPUT_FILE_E="../data/tickers_other.csv"
INPUT_FILE_F="../data/tickers_recent_top_scores.csv"
OUTPUT_FILE="../data/tickers_combined.csv"

# Arguments: include_dow  include_sp500  include_russell  include_other  include_top_scores
INCLUDE_DOW="${1:-n}"
INCLUDE_SP500="${2:-n}"
INCLUDE_RUSSELL="${3:-n}"
INCLUDE_OTHER="${4:-n}"
INCLUDE_TOP_SCORES="${5:-n}"

mkdir -p "$(dirname "$OUTPUT_FILE")"

echo "Ticker,Owned" > "$OUTPUT_FILE"

# ---- Current positions (always included) ----
tail -n +2 "$INPUT_FILE_A" 2>/dev/null |
sed 's/\./-/g' |
awk -F',' '{print $1 ",Y"}' > /tmp/current_tickers.txt || true

# ---- Dow (optional) ----
if [[ "$INCLUDE_DOW" == "y" && -f "$INPUT_FILE_B" ]]; then
    tail -n +2 "$INPUT_FILE_B" |
    sed 's/\./-/g' |
    awk -F',' '{print $1 ","}' > /tmp/dow_tickers.txt
else
    > /tmp/dow_tickers.txt
fi

# ---- S&P 500 (optional) ----
if [[ "$INCLUDE_SP500" == "y" && -f "$INPUT_FILE_C" ]]; then
    tail -n +2 "$INPUT_FILE_C" |
    sed 's/\./-/g' |
    awk -F',' '{print $1 ","}' > /tmp/sp500_tickers.txt
else
    > /tmp/sp500_tickers.txt
fi

# ---- Russell 2000 (optional) ----
if [[ "$INCLUDE_RUSSELL" == "y" && -f "$INPUT_FILE_D" ]]; then
    tail -n +2 "$INPUT_FILE_D" |
    sed 's/\./-/g' |
    awk -F',' '{print $1 ","}' > /tmp/russell_tickers.txt
else
    > /tmp/russell_tickers.txt
fi

# ---- Other (optional) ----
if [[ "$INCLUDE_OTHER" == "y" && -f "$INPUT_FILE_E" ]]; then
    tail -n +2 "$INPUT_FILE_E" |
    sed 's/\./-/g' |
    awk -F',' '{print $1 ","}' > /tmp/other_tickers.txt
else
    > /tmp/other_tickers.txt
fi

# ---- Recent top-score tickers (optional) ----
if [[ "$INCLUDE_TOP_SCORES" == "y" && -f "$INPUT_FILE_F" ]]; then
    tail -n +2 "$INPUT_FILE_F" |
    sed 's/\./-/g' |
    awk -F',' '{print $1 ","}' > /tmp/top_scores_tickers.txt
else
    > /tmp/top_scores_tickers.txt
fi

# ---- Merge, deduplicate, prefer Owned=Y ----
cat \
    /tmp/current_tickers.txt \
    /tmp/dow_tickers.txt \
    /tmp/sp500_tickers.txt \
    /tmp/russell_tickers.txt \
    /tmp/other_tickers.txt \
    /tmp/top_scores_tickers.txt |
sort -t',' -k1,1 |
awk -F',' '
{
    if (!seen[$1]) {
        owned[$1] = $2
        seen[$1]  = 1
    } else if ($2 == "Y") {
        owned[$1] = "Y"
    }
}
END {
    for (t in owned)
        print t "," owned[t]
}' |
sort >> "$OUTPUT_FILE"

rm -f /tmp/current_tickers.txt \
    /tmp/dow_tickers.txt \
    /tmp/sp500_tickers.txt \
    /tmp/russell_tickers.txt \
    /tmp/other_tickers.txt \
    /tmp/top_scores_tickers.txt