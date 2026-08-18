#!/bin/bash
set -e
CUR_POS_TICKERS_FILE="../data/tickers_current_positions.csv"

# Determine the directory of the script and change to that directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE}" )" && pwd )"
cd "$SCRIPT_DIR"

START_TIME=$(date +%s)

echo
echo "======================================"
echo " Stock Buy Opportunity Scanner"
echo "======================================"
echo

# ==========================================
# COLLECT ALL USER CHOICES UP FRONT
# ==========================================
read -p "1.  Would you like to update the current positions (recommended daily)? (y/n) " UPDATE_CUR_POSITIONS
read -p "1b. Include S&P 500 tickers? (y/n) " INCLUDE_SP500
read -p "1c. Include Russell 2000 tickers? (y/n) " INCLUDE_RUSSELL
read -p "1d. Include 'other' tickers? (y/n) " INCLUDE_OTHER
read -p "1e. Include recent top-score tickers? (y/n) " INCLUDE_TOP_SCORES
read -p "2.  Would you like to update fundamentals (recommended daily)? (y/n) " UPDATE_FUNDAMENTALS
read -p "3.  Would you like to update Ticker Metadata (recommended monthly)? (y/n) " UPDATE_TICKER_METADATA
read -p "4.  Would you like to run the C++ scanner? (y/n) " RUN_CPP_SCANNER
read -p "5.  Would you like to create the LibreOffice report? (y/n) " CREATE_REPORT
echo
echo "======================================"
echo " Starting Processing..."
echo "======================================"
echo

# ==========================================
# 1. CURRENT POSITIONS
# ==========================================
echo "1.  Current Positions"
if [[ "$UPDATE_CUR_POSITIONS" == "y" ]]; then
    echo "    → Updating current positions (tickers_current_positions.csv)..."
    ./get_cur_pos_tickers.sh
else
    echo "    → Skipping update of current positions."
fi

# Replace odd ticker symbols with their correct versions (e.g., BRK.B -> BRK-B)
sed -i 's/BRK.B/BRK-B/g' "$CUR_POS_TICKERS_FILE"
sed -i 's/BRK.A/BRK-A/g' "$CUR_POS_TICKERS_FILE"
echo

# ==========================================
# 1b–1e. COMBINE TICKER LISTS
# ==========================================
echo "1b–1e. Combining ticker lists..."
echo "        tickers_current_positions.csv (always included)"
[[ "$INCLUDE_SP500"     == "y" ]] && echo "        1b. tickers_sp_500.csv"
[[ "$INCLUDE_RUSSELL"    == "y" ]] && echo "        1c. tickers_russel_2k.csv"
[[ "$INCLUDE_OTHER"      == "y" ]] && echo "        1d. tickers_other.csv"
[[ "$INCLUDE_TOP_SCORES" == "y" ]] && echo "        1e. tickers_recent_top_scores.csv"
echo "        → Output: tickers_combined.csv"
./combine_sort_tickers.sh "$INCLUDE_SP500" "$INCLUDE_RUSSELL" "$INCLUDE_OTHER" "$INCLUDE_TOP_SCORES"
echo

# ==========================================
# 2. FUNDAMENTALS
# ==========================================
echo "2.  Fundamentals"
if [[ "$UPDATE_FUNDAMENTALS" == "y" ]]; then
    echo "    → Updating fundamentals..."
    source /home/dev/py/.venv/bin/activate
    python ../py/get_financials.py
    deactivate
else
    echo "    → Skipping fundamentals update."
fi
echo

# ==========================================
# 3. TICKER METADATA
# ==========================================
echo "3.  Ticker Metadata"
if [[ "$UPDATE_TICKER_METADATA" == "y" ]]; then
    echo "    → Updating ticker metadata..."
    source /home/dev/py/.venv/bin/activate
    python ../py/get_ticker_metadata.py
    deactivate
else
    echo "    → Skipping ticker metadata update."
fi
echo

# ==========================================
# 4. C++ SCANNER
# ==========================================
echo "4.  C++ Scanner"
if [[ "$RUN_CPP_SCANNER" == "y" ]]; then
    echo "    → Running C++ scanner..."
    cd ../cpp/bin
    ./buy_opp
    cd "$SCRIPT_DIR"
else
    echo "    → Skipping C++ scanner."
fi
echo

# ==========================================
# 5. CREATE REPORT
# ==========================================
echo "5.  LibreOffice Report"
if [[ "$CREATE_REPORT" == "y" ]]; then
    echo "    → Creating LibreOffice report..."
    if /usr/bin/python3 ../py/create_report.py; then
        echo "    ✅ Report created successfully."
    else
        echo "    ❌ ERROR: Python script failed!"
        echo "    Current directory is: $(pwd)"
        read -p "    Press Enter to see details and exit..."
        exit 1
    fi
else
    echo "    → Skipping LibreOffice report creation."
fi

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

echo
echo "======================================"
echo " Complete"
echo " Runtime: ${ELAPSED} seconds"
echo " Output: output/summary_all.csv"
echo "======================================"
echo

# ==========================================
# 6. OPEN LIBREOFFICE
# ==========================================
echo "6.  Opening report in LibreOffice..."
if setsid libreoffice ../output/summary_all.ods > /tmp/libreoffice_debug.log 2>&1 & then
    echo "    ✅ LibreOffice command executed."
    sleep 1
    if pgrep -f "libreoffice" > /dev/null; then
        echo "    LibreOffice process detected in background."
    else
        echo "    ⚠️  WARNING: LibreOffice command ran, but the process is not active."
        echo "    System error log contains:"
        cat /tmp/libreoffice_debug.log
    fi
else
    echo "    ❌ ERROR: LibreOffice failed to execute!"
    read -p "    Press Enter to close window..."
    exit 1
fi

echo
echo "=== DEBUG PAUSE ==="
echo "The pipeline has finished executing."
read -p "Press Enter to close this terminal window and test if LibreOffice stays open..."