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
echo "3. Updating fundamentals (recommended daily)..."
read -p "   Would you like to update fundamentals (recommended daily)? (y/n) " UPDATE_FUNDAMENTALS
if [[ "$UPDATE_FUNDAMENTALS" == "y" ]]; then
    source /home/dev/py/.venv/bin/activate

    python ../py/get_financials.py
    deactivate
fi

echo
echo "4. Running C++ scanner..."
# run compiled C++ scanner
../cpp/bin/buy_opp

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

echo
echo "======================================"
echo " Complete"
echo " Runtime: ${ELAPSED} seconds"
echo " Output: output/summary_all.csv"
echo "======================================"
echo
