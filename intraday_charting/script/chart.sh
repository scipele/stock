#!/bin/bash

# Target files and directories
TICKER_FILE="/home/dev/stock/intraday_charting/input/tickers.csv"
OUTPUT_DIR="/home/dev/stock/intraday_charting/output"
CHART_DIR="/home/dev/stock/intraday_charting/charts"
DOWNLOAD_DIR="$HOME/Downloads"
TOP_BUY_OPP_RANK_FILE="/home/dev/stock/buy_opp/output/summary_all.csv"
TOP_INTR_BUY_RANK_FILE="/home/dev/stock/intr_buy/output/combined_report.csv"

# Words to exclude from position descriptions (case-insensitive)
EXCLUDE_LINES_WHERE_NAME_CONTAINS="etf|fund|money|adm"

# ------------------------------------------------------------------
# Helper: load tickers from the latest Fund-Positions CSV
# ------------------------------------------------------------------
load_positions_from_downloads() {
    local latest_file
    latest_file=$(ls -1t "$DOWNLOAD_DIR"/Fund-Positions-*.csv 2>/dev/null | head -n 1)

    if [[ -z "$latest_file" ]]; then
        echo "Error: No matching Fund-Positions-*.csv found in $DOWNLOAD_DIR" >&2
        return 1
    fi

    echo "       Using positions file: $latest_file" >&2

    local total_lines
    total_lines=$(wc -l < "$latest_file")

    awk -F ',' -v total="$total_lines" -v exclude="$EXCLUDE_LINES_WHERE_NAME_CONTAINS" '
        NR > 3 && NR <= total - 2 {
            gsub(/"/, "", $0)
            split($0, fields, ",")
            ticker = fields[1]
            description = fields[2]
            if (tolower(description) !~ exclude) {
                if (ticker != "") print ticker
            }
        }
    ' "$latest_file"
}


# ------------------------------------------------------------------
# Helper: load top-ranked stocks from summary_all.csv
# ------------------------------------------------------------------
load_top_ranked() {
    local num="$1"
    if [[ ! -f "$TOP_BUY_OPP_RANK_FILE" ]]; then
        echo "Error: $TOP_BUY_OPP_RANK_FILE not found." >&2
        return 1
    fi
    # Column 3 = ticker, skip header, take first $num rows
    awk -F ',' 'NR>1 {print $3}' "$TOP_BUY_OPP_RANK_FILE" | head -n "$num"
}


# ------------------------------------------------------------------
# Helper: load top-intr_buy_ranked stocks from combined_report.csv
# ------------------------------------------------------------------
load_top_intr_buy_ranked() {
    local num="$1"
    if [[ ! -f "$TOP_INTR_BUY_RANK_FILE" ]]; then
        echo "Error: $TOP_INTR_BUY_RANK_FILE not found." >&2
        return 1
    fi
    # Column 3 = ticker, skip header, take first $num rows
    awk -F ',' 'NR>1 {print $2}' "$TOP_INTR_BUY_RANK_FILE" | head -n "$num"
}


# Print a comma-separated list with a fixed leading indent on every line.
# Usage: print_indented_list "           " "ACGL,ADM,AMD,AMP,..."
print_indented_list() {
  local indent=$1
  local list=$2
  local cols width

  # How many characters are available after the indent
  cols=${COLUMNS:-$(tput cols 2>/dev/null || echo 80)}
  width=$(( cols - ${#indent} ))
  (( width < 20 )) && width=60   # safety floor

  # fold after commas when possible, then prefix every line with the indent
  printf '%s\n' "$list" \
    | fold -s -w "$width" \
    | sed "s/^/$indent/"
}


# ------------------------------------------------------------------
# 1. Clean old data & charts
# ------------------------------------------------------------------
echo "1. Cleaning up old data and charts..."
rm -f "$OUTPUT_DIR"/*.csv
rm -f "$CHART_DIR"/*.png


# ------------------------------------------------------------------
# 2. Build the ticker list
# ------------------------------------------------------------------
echo
echo
echo "2. Assemble Tickers to Chart"
tickers=()
prev_tickers=""

# Read previous tickers (if any)
if [[ -f "$TICKER_FILE" ]]; then
    prev_tickers=$(tail -n +2 "$TICKER_FILE" | tr '\n' ',' | sed 's/,$//')
fi

# ----- Option 2.1: reuse previous -----
use_prev="n"
if [[ -n "$prev_tickers" ]]; then
    echo "  2.1 Previous tickers found in $TICKER_FILE:"
    print_indented_list "       " "$prev_tickers"
    read -p "        Use these previous tickers? [Y/n]: " use_prev
    use_prev=${use_prev:-Y}
fi

if [[ "$use_prev" =~ ^[Yy]$ ]]; then
    IFS=',' read -ra tickers <<< "$prev_tickers"
    echo "       Reusing previous tickers."
fi


# ----- Option 2.2: load current positions from Downloads -----
echo
read -p "    2.2 Load current positions from ~/Downloads (Fund-Positions-*.csv)? [y/N]: " use_positions
use_positions=${use_positions:-N}

if [[ "$use_positions" =~ ^[Yy]$ ]]; then
    mapfile -t pos_tickers < <(load_positions_from_downloads)
    if [[ ${#pos_tickers[@]} -eq 0 ]]; then
        echo "        No usable tickers found in the positions file."
    else
        echo "        Loaded ${#pos_tickers[@]} tickers from positions file."
        if [[ "$use_prev" =~ ^[Yy]$ ]]; then
            tickers+=("${pos_tickers[@]}")
        else
            tickers=("${pos_tickers[@]}")
        fi
    fi
fi


# ----- Option 2.3: append top-buy_opp_ranked stocks -----
echo
read -p "    2.3 Append top-buy_opp_ranked stocks? [y/N]: " use_top
use_top=${use_top:-N}

if [[ "$use_top" =~ ^[Yy]$ ]]; then
    read -p "        How many top stocks would you like to add? " num_stocks
    if ! [[ "$num_stocks" =~ ^[0-9]+$ ]] || [[ "$num_stocks" -eq 0 ]]; then
        echo "        Invalid number – skipping top-buy_opp_ranked stocks."
    else
        mapfile -t top_tickers < <(load_top_ranked "$num_stocks")
        if [[ ${#top_tickers[@]} -eq 0 ]]; then
            echo "        No top-buy_opp_ranked tickers found."
        else
            echo "        Adding top ${#top_tickers[@]} ranked stocks:"
            print_indented_list "           " "${top_tickers[*]}"
            tickers+=("${top_tickers[@]}")
        fi
    fi
fi


# ----- Option 2.4: append top-intr_buy ranked stocks -----
echo
read -p "    2.4 Append top-intr_buy ranked stocks? [y/N]: " use_top_intr_buy
use_top_intr_buy=${use_top_intr_buy:-N}

if [[ "$use_top_intr_buy" =~ ^[Yy]$ ]]; then
    read -p "        How many top stocks would you like to add? " num_stocks
    if ! [[ "$num_stocks" =~ ^[0-9]+$ ]] || [[ "$num_stocks" -eq 0 ]]; then
        echo "        Invalid number – skipping top-intr_buy stocks."
    else
        mapfile -t top_intr_buy_tickers < <(load_top_intr_buy_ranked "$num_stocks")
        if [[ ${#top_intr_buy_tickers[@]} -eq 0 ]]; then
            echo "        No top-intr_buy tickers found."
        else
            echo "        Adding top ${#top_intr_buy_tickers[@]} top-intr_buy stocks: ${top_intr_buy_tickers[*]}"
            print_indented_list "           " "${top_intr_buy_tickers[*]}"
            tickers+=("${top_intr_buy_tickers[@]}")
        fi
    fi
fi


# ----- Option 5: manually add extra tickers -----
echo
read -p "    2.5 Manually add any additional tickers? [y/N]: " add_manual

add_manual=${add_manual:-N}

if [[ "$add_manual" =~ ^[Yy]$ ]]; then
    echo "        Enter extra tickers (comma or one per line)."
    echo "        Press Ctrl+D when finished:"
    echo

    user_tickers=$(cat)

    mapfile -t extra < <(
        printf '%s' "$user_tickers" |
        tr ',\t\r' '\n\n\n' |
        sed 's/^[[:space:]]*//;s/[[:space:]]*$//' |
        sed '/^$/d'
    )

    tickers+=("${extra[@]}")
fi


# ------------------------------------------------------------------
# 2.6 Deduplicate, sort, show final list, confirm
# ------------------------------------------------------------------
mapfile -t sorted_tickers < <(
    printf '%s\n' "${tickers[@]}" \
        | tr '[:lower:]' '[:upper:]' \
        | sed '/^$/d' \
        | sort -u
)

echo
echo "    2.6 Final sorted ticker list (${#sorted_tickers[@]} tickers):"
# Join sorted_tickers with commas (no trailing comma)
joined=$(IFS=,; echo "${sorted_tickers[*]}")
print_indented_list "        " "$joined"
echo

# read -p "        Proceed with these tickers? [Y/n]: " proceed
# proceed=${proceed:-Y}
# 
# if [[ ! "$proceed" =~ ^[Yy]$ ]]; then
#     echo "        Aborted by user."
#     exit 0
# fi

# Write the cleaned list back to the ticker file
{
    echo "        ticker"
    printf '%s\n' "${sorted_tickers[@]}"
} > "$TICKER_FILE"

echo "        Tickers saved to $TICKER_FILE"

# ------------------------------------------------------------------
# 6. Prompt for number of days
# ------------------------------------------------------------------
echo
echo
read -p "3. Enter how many days to include on the chart: " chart_days

# ------------------------------------------------------------------
# 7. Fetch data (C++)
# ------------------------------------------------------------------
echo
echo
echo "4. C++ Fetching intraday data..."
cd /home/dev/stock/intraday_charting/cpp/bin || exit 1
./fetch_intraday

# ------------------------------------------------------------------
# 8. Generate charts (Python)
# ------------------------------------------------------------------
echo
echo
if [[ $? -eq 0 ]]; then
    echo "5. Run Python Script: Generating charts for $chart_days days..."
    /home/dev/py/.venv/bin/python /home/dev/stock/intraday_charting/py/chart.py --days "$chart_days"
else
    echo "Error: C++ data fetch failed. Skipping chart generation."
    exit 1
fi

# ------------------------------------------------------------------
# 9. Open charts gallery
# ------------------------------------------------------------------
echo
echo
echo "6. Opening charts gallery..."
if [[ -d "$CHART_DIR" ]]; then
    gthumb "$CHART_DIR"/*.png &
    gsettings set org.gnome.gthumb.browser sort-type 'name' 2>/dev/null
else
    echo "   Error: Chart directory not found."
fi

# ------------------------------------------------------------------
# 10. Pause
# ------------------------------------------------------------------
echo
echo
read -n 1 -s -r -p "Press any key to close..."
