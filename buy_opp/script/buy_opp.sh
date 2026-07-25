set -e

START_TIME=$(date +%s)

echo
echo "======================================"
echo " Stock Buy Opportunity Scanner"
echo "======================================"
echo

echo "1. Updating current positions (tickers_current_positions.csv)..."
./get_cur_pos_tickers.sh

echo
echo "2. Combining ticker lists... (tickers_current_positions.csv, tickers_watchlist.csv, tickers_custom.csv)"
echo "Output: tickers_combined.csv"
./combine_sort_tickers.sh

echo
# python is run in the virtual environment (up two directories) to ensure correct dependencies are used
# python scripts are loaded from the buy_opp/py directory (up one directory)
source /home/dev/py/.venv/bin/activate

read -p "3. Would you like to update fundamentals (recommended daily)? (y/n) " UPDATE_FUNDAMENTALS
if [[ "$UPDATE_FUNDAMENTALS" == "y" ]]; then
    python ../py/get_financials.py
fi
echo
read -p "4. Would you like to update Ticker Metadata (recommended monthly) (y/n) " UPDATE_TICKER_METADATA
if [[ "$UPDATE_TICKER_METADATA" == "y" ]]; then
    python ../py/get_ticker_metadata.py
fi
deactivate

echo
echo "5. Running C++ scanner..."

# change directory and run compiled C++ scanner
cd ../cpp/bin
./buy_opp

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

echo
echo "======================================"
echo " Complete"
echo " Runtime: ${ELAPSED} seconds"
echo " Output: output/summary_all.csv"
echo "======================================"
echo
read -p "Press any key to continue..." -n1 -s