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
read -p "1. Would you like to update the current positions (recommended daily)? (y/n) " UPDATE_CUR_POSITIONS
read -p "2. Would you like to update fundamentals (recommended daily)? (y/n) " UPDATE_FUNDAMENTALS
read -p "3. Would you like to update Ticker Metadata (recommended monthly)? (y/n) " UPDATE_TICKER_METADATA
read -p "4. Would you like to run the C++ scanner? (y/n) " RUN_CPP_SCANNER
read -p "5. Would you like to create the LibreOffice report? (y/n) " CREATE_REPORT
echo
echo "======================================"
echo " Starting Processing..."
echo "======================================"
echo

# ==========================================
# EXECUTE STEP 1: CURRENT POSITIONS
# ==========================================
if [[ "$UPDATE_CUR_POSITIONS" == "y" ]]; then
 echo " Updating current positions (tickers_current_positions.csv)..."
 ./get_cur_pos_tickers.sh
fi

# Replace odd ticker symbols with their correct versions (e.g., BRK.B -> BRK-B)
sed -i 's/BRK.B/BRK-B/g' "$CUR_POS_TICKERS_FILE"
sed -i 's/BRK.A/BRK-A/g' "$CUR_POS_TICKERS_FILE"

echo
echo "Combining ticker lists... (tickers_current_positions.csv, tickers_sp_500.csv, tickers_other.csv)"
echo " Output: tickers_combined.csv"
./combine_sort_tickers.sh
echo

# ==========================================
# EXECUTE STEP 2: FUNDAMENTALS (Labels matched original step references)
# ==========================================
if [[ "$UPDATE_FUNDAMENTALS" == "y" ]]; then
 source /home/dev/py/.venv/bin/activate
 python ../py/get_financials.py
 deactivate
fi

echo

# ==========================================
# EXECUTE STEP 3: TICKER METADATA
# ==========================================
if [[ "$UPDATE_TICKER_METADATA" == "y" ]]; then
 source /home/dev/py/.venv/bin/activate
 python ../py/get_ticker_metadata.py
 deactivate
fi

echo

# ==========================================
# EXECUTE STEP 4: RUN C++ SCANNER
# ==========================================
if [[ "$RUN_CPP_SCANNER" == "y" ]]; then
 echo "Running C++ scanner..."
 # change directory and run compiled C++ scanner
 cd ../cpp/bin
 ./buy_opp
 cd "$SCRIPT_DIR"
else
 echo "Skipping C++ scanner."
fi

echo

# ==========================================
# EXECUTE STEP 5: CREATE REPORT (WITH DEBUG)
# ==========================================
if [[ "$CREATE_REPORT" == "y" ]]; then
    echo "Creating LibreOffice report..."
    if /usr/bin/python3 ../py/create_report.py; then
        echo "✅ Report created successfully."
    else
        echo "❌ ERROR: Python script failed!"
        echo "Current directory is: $(pwd)"
        read -p "Press Enter to see details and exit..."
        exit 1
    fi
else
    echo "Skipping LibreOffice report creation."
fi

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

echo
echo " ======================================"
echo " Complete"
echo " Runtime: ${ELAPSED} seconds"
echo " Output: output/summary_all.csv"
echo " ======================================"
echo

# ==========================================
# EXECUTE STEP 6: OPEN LIBREOFFICE (WITH DEBUG)
# ==========================================
echo "Opening report in LibreOffice..."
if setsid libreoffice ../output/summary_all.ods > /tmp/libreoffice_debug.log 2>&1 & then
    echo "✅ LibreOffice command executed."
    sleep 1
    if pgrep -f "libreoffice" > /dev/null; then
        echo "   LibreOffice process detected in background."
    else
        echo "⚠️ WARNING: LibreOffice command ran, but the process is not active."
        echo "System error log contains:"
        cat /tmp/libreoffice_debug.log
    fi
else
    echo "❌ ERROR: LibreOffice failed to execute!"
    read -p "Press Enter to close window..."
    exit 1
fi

echo
echo "=== DEBUG PAUSE ==="
echo "The pipeline has finished executing."
read -p "Press Enter to close this terminal window and test if LibreOffice stays open..."
