#!/bin/bash

INPUT_FILE_A="../data/tickers_current_positions.csv"
INPUT_FILE_B="../data/tickers_sp_500.csv"
INPUT_FILE_C="../data/tickers_other.csv"
OUTPUT_FILE="../data/tickers_combined.csv"

# Make sure the output folder exists
mkdir -p "$(dirname "$OUTPUT_FILE")"

# Combine files (skip first line of each), sort, remove duplicates, and add header
{
    # echo "tickers"
    # Replace any tickers that contain '.' in tickers with '-'
    { tail -n +2 "$INPUT_FILE_A"; tail -n +2 "$INPUT_FILE_B"; tail -n +2 "$INPUT_FILE_C"; } | sed 's/\./-/g' | sort -u
} > "$OUTPUT_FILE"
