#!/bin/bash

# Target files and directories
TICKER_FILE="/home/dev/stock/intraday_charting/input/tickers.csv"
DATA_DIR="/home/dev/stock/intraday_charting/output"
CHART_DIR="/home/dev/stock/intraday_charting/charts"

# 1. Delete old data and charts before starting
echo "Cleaning up old data and charts..."
rm -f "$DATA_DIR"/*
rm -f "$CHART_DIR"/*

# 2. Read previous tickers from the CSV file (skipping the 'ticker' header)
if [ -f "$TICKER_FILE" ]; then
    prev_tickers=$(tail -n +2 "$TICKER_FILE" | tr '\n' ',' | sed 's/,$//')
fi

# 3. Ask the user if they want to reuse the previous tickers
if [ ! -z "$prev_tickers" ]; then
    read -p "Use previous tickers ($prev_tickers)? [Y/n]: " use_prev
else
    use_prev="n"
fi

# 4. If they don't want previous tickers, prompt for new ones and overwrite the file
if [[ "$use_prev" =~ ^[Nn]$ ]]; then
    read -p "Enter tickers separated by commas (e.g., GD, LNG): " user_tickers
    
    # Save the 'ticker' header first
    echo "ticker" > "$TICKER_FILE"
    
    # 1. Strip all spaces globally
    clean_tickers="${user_tickers// /}"
    
    # 2. Convert commas to newlines, skipping empty lines
    echo "$clean_tickers" | tr ',' '\n' | grep . >> "$TICKER_FILE"
else
    echo "Reusing previous tickers..."
fi

# 5. Sort the tickers in the CSV file alphabetically and remove duplicates
if [ -f "$TICKER_FILE" ]; then
    echo "Sorting tickers automatically..."
    
    # Extract tickers, convert commas/spaces to newlines, sort alphabetically, and remove duplicates/blank lines
    sorted_tickers=$(tail -n +2 "$TICKER_FILE" | tr ',' '\n' | tr -d ' ' | sort -u | sed '/^$/d')
    
    # Save the header and sorted tickers back to the original file
    {
        echo "ticker"
        echo "$sorted_tickers"
    } > "$TICKER_FILE"
    
    echo "Tickers successfully sorted and saved."
else
    echo "Error: $TICKER_FILE not found."
fi


# 6. Prompt user for days
read -p "Enter how many days to include on the chart: " chart_days

# 7. Navigate to C++ folder and run the program
echo "Fetching intraday data..."
cd /home/dev/stock/intraday_charting/cpp/bin || exit 1
./fetch_intraday

# 8. Run the Python script using your working VS Code (.venv) path
if [ $? -eq 0 ]; then
    echo "Generating charts for $chart_days days..."
    # Python now handles entry prices automatically via the Schwab export file
    /home/dev/py/.venv/bin/python /home/dev/stock/intraday_charting/py/chart.py --days "$chart_days"
else
    echo "Error: C++ data fetch failed. Skipping chart generation."
    exit 1
fi

# 10. Open the charts directory sorted alphabetically
echo "Opening charts gallery..."
if [ -d "$CHART_DIR" ]; then
    # Bash automatically expands *.png in alphabetical order
    gthumb "$CHART_DIR"/*.png &
    
    # Optional: Force gthumb to stay in alphabetical name mode
    gsettings set org.gnome.gthumb.browser sort-type 'name' 2>/dev/null
else
    echo "Error: Chart directory not found."
fi

# 11. Add a pause
read -n 1 -s -r -p "Press any key to close..."
echo ""
echo "Process complete!"

