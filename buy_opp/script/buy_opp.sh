set -e

CUR_POS_TICKERS_FILE="../data/tickers_current_positions.csv"

# Determine the directory of the script and change to that directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

START_TIME=$(date +%s)

echo
echo "======================================"
echo " Stock Buy Opportunity Scanner"
echo "======================================"
echo

read -p "Would you like to update the current positions (recommended daily)? (y/n) " UPDATE_CUR_POSITIONS
if [[ "$UPDATE_CUR_POSITIONS" == "y" ]]; then
    echo "Updating current positions (tickers_current_positions.csv)..."
    ./get_cur_pos_tickers.sh
fi  

# Replace odd ticher symbols with their correct versions (e.g., BRK.B -> BRK-B)
sed -i 's/BRK.B/BRK-B/g' "$CUR_POS_TICKERS_FILE"
sed -i 's/BRK.A/BRK-A/g' "$CUR_POS_TICKERS_FILE"


echo
echo "2. Combining ticker lists... (tickers_current_positions.csv, tickers_sp_500.csv, tickers_other.csv)"
echo "   Output: tickers_combined.csv"
./combine_sort_tickers.sh

echo
# python is run in the virtual environment (up two directories) to ensure correct dependencies are used
# python scripts are loaded from the buy_opp/py directory (up one directory)


read -p "3. Would you like to update fundamentals (recommended daily)? (y/n) " UPDATE_FUNDAMENTALS
if [[ "$UPDATE_FUNDAMENTALS" == "y" ]]; then
    source /home/dev/py/.venv/bin/activate
    python ../py/get_financials.py
    deactivate
fi
echo
read -p "4. Would you like to update Ticker Metadata (recommended monthly) (y/n) " UPDATE_TICKER_METADATA
if [[ "$UPDATE_TICKER_METADATA" == "y" ]]; then
    source /home/dev/py/.venv/bin/activate
    python ../py/get_ticker_metadata.py
    deactivate
fi

echo
echo "5. Running C++ scanner..."

# change directory and run compiled C++ scanner
cd ../cpp/bin
./buy_opp

cd "$SCRIPT_DIR"
echo
echo "6. Creating LibreOffice report..."
/usr/bin/python3 ../py/create_report.py

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

echo
echo "   ======================================"
echo "    Complete"
echo "    Runtime: ${ELAPSED} seconds"
echo "    Output: output/summary_all.csv"
echo "   ======================================"
echo

echo "7. Opening report in LibreOffice..."

libreoffice ../output/summary_all.ods >/dev/null 2>&1 &

read -p "   Press any key to continue..." -n1 -s
echo