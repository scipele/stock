#!/bin/bash
set -e

# ------------------------------------------------------------------
# Intrinsic Value Scanner
# ------------------------------------------------------------------

# Determine the directory of the script and change to that directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

START_TIME=$(date +%s)

echo
echo "======================================"
echo " Intrinsic Value Scanner"
echo "======================================"
echo

# ------------------------------------------------------------------
# 1. Ticker list
# ------------------------------------------------------------------
echo "1. Ticker list"
echo "   Using: ../data/tickers_combined.csv"
echo "   (You can copy/symlink the one from buy_opp or maintain a separate list)"
echo

# Optional: copy the latest combined list from buy_opp
read -p "   Copy latest tickers_combined.csv from buy_opp? (y/n) " COPY_TICKERS
if [[ "$COPY_TICKERS" == "y" || "$COPY_TICKERS" == "Y" ]]; then
    if [[ -f /home/dev/stock/buy_opp/data/tickers_combined.csv ]]; then
        cp /home/dev/stock/buy_opp/data/tickers_combined.csv ../data/tickers_combined.csv
        echo "   → Copied successfully"
    else
        echo "   → WARNING: buy_opp tickers_combined.csv not found"
    fi
fi

# Fix common Yahoo symbol differences (same as your other script)
if [[ -f ../data/tickers_combined.csv ]]; then
    sed -i 's/BRK.B/BRK-B/g' ../data/tickers_combined.csv
    sed -i 's/BRK.A/BRK-A/g' ../data/tickers_combined.csv
fi

# ------------------------------------------------------------------
# 2. Update fundamental / valuation data (Python)
# ------------------------------------------------------------------
echo
read -p "2. Would you like to update intrinsic-value data (recommended daily/weekly)? (y/n) " UPDATE_DATA
if [[ "$UPDATE_DATA" == "y" || "$UPDATE_DATA" == "Y" ]]; then
    echo "   Activating virtual environment and running data gatherer..."
    source /home/dev/py/.venv/bin/activate
    python ../py/get_intrinsic_data.py
    deactivate
    echo "   → Data update complete"
else
    echo "   → Skipping data update (using existing fundamentals_intrinsic.csv)"
fi

# ------------------------------------------------------------------
# 3. C++ number crunching
# ------------------------------------------------------------------
echo
echo "3. C++ valuation engine"
if [[ -x ../cpp/bin/intr_value ]]; then
    echo "   Running C++ scanner..."
    cd ../cpp/bin
    ./intr_value
    cd "$SCRIPT_DIR"
else
    echo "   → C++ binary not found yet (../cpp/bin/intr_value)"
    echo "     (We will add this in the next step)"
fi

# ------------------------------------------------------------------
# 4. Creating LibreOffice report
# ------------------------------------------------------------------
echo
echo "4. Creating LibreOffice report..."
/usr/bin/python3 ../py/create_intrinsic_report.py


END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

echo
echo "   ======================================"
echo "    Complete"
echo "    Runtime: ${ELAPSED} seconds"
echo "    Output: output/summary_intrinsic.csv"
echo "            output/summary_intrinsic.ods"
echo "   ======================================"
echo

echo "5. Opening report in LibreOffice..."
libreoffice ../output/summary_intrinsic.ods >/dev/null 2>&1 &