#!/bin/bash

INPUT_FILE_A="../data/tickers_current_positions.csv"
INPUT_FILE_B="../data/tickers_sp_500.csv"
INPUT_FILE_C="../data/tickers_other.csv"
OUTPUT_FILE="../data/tickers_combined.csv"

# Make sure the output folder exists
mkdir -p "$(dirname "$OUTPUT_FILE")"

# Combine files (skip first line of each), sort, remove duplicates, and add header
echo "   Ticker,Owned" > "$OUTPUT_FILE"

# Current positions
tail -n +2 "$INPUT_FILE_A" |
sed 's/\./-/g' |
awk -F',' '{print $1 ",Y"}' > /tmp/current_tickers.txt

# S&P 500
tail -n +2 "$INPUT_FILE_B" |
sed 's/\./-/g' |
awk -F',' '{print $1 ","}' > /tmp/sp500_tickers.txt

# Other
tail -n +2 "$INPUT_FILE_C" |
sed 's/\./-/g' |
awk -F',' '{print $1 ","}' > /tmp/other_tickers.txt

cat \
    /tmp/current_tickers.txt \
    /tmp/sp500_tickers.txt \
    /tmp/other_tickers.txt |
sort -t',' -k1,1 |
awk -F',' '
{
    if (!seen[$1]) {
        owned[$1]=$2
        seen[$1]=1
    }
    else if ($2=="Y") {
        owned[$1]="Y"
    }
}
END{
    for (t in owned)
        print t "," owned[t]
}' |
sort >> "$OUTPUT_FILE"

rm -f /tmp/current_tickers.txt
rm -f /tmp/sp500_tickers.txt
rm -f /tmp/other_tickers.txt