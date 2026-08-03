#!/bin/bash
# SCRIPT 1

set -e
CUR_POS_TICKERS_FILE="../data/tickers_current_positions.csv"

# Determine the directory of the script and change to that directory
SCRIPT_DIR_A="/home/dev/stock/buy_opp/script"
cd "$SCRIPT_DIR_A"

# ==========================================
# GENERAL QUESTIONS FOR ALL THREE SCRIPTS
# ==========================================
echo "========================= Program #1 - Buy Opportunity Questions ======================================"
read -p "   1.1 Would you like to update the current positions (recommended daily)? (y/n) " UPDATE_CUR_POSITIONS
read -p "   1.2 Would you like to update fundamentals (recommended daily)? (y/n) " UPDATE_FUNDAMENTALS
read -p "   1.3 Would you like to update Ticker Metadata (recommended monthly)? (y/n) " UPDATE_TICKER_METADATA
read -p "   1.4 Would you like to run the C++ scanner? (y/n) " RUN_CPP_SCANNER
echo 
echo "========================= Program #2 - Intrinsic Value Questions ======================================"
read -p "   2.1 Copy latest tickers_combined.csv from buy_opp? (y/n) " COPY_TICKERS
read -p "   2.2 Would you like to update intrinsic-value data (recommended daily/weekly)? (y/n) " UPDATE_DATA
echo
echo "========================= Program #3 - Data Combination & Report Questions ======================================"
read -p "   3.1 Would you like to copy files from the other programs? (y/n): " COPY_FILES
read -p "   3.2 Would you like to run the C++ program to combine the files? (y/n): " RUN_CPP_COMBINER
read -p "   3.3 Would you like to create the LibreOffice report? (y/n): " CREATE_REPORT

START_TIME=$(date +%s)

echo
echo "============================================"
echo " Program #1 - Stock Buy Opportunity Scanner"
echo "============================================"
echo
echo "   Starting Processing..."
echo

# ==========================================
# EXECUTE STEP 1: CURRENT POSITIONS
# ==========================================
if [[ "$UPDATE_CUR_POSITIONS" == "y" ]]; then
echo "   1.1 Updating stock tickers to use:"
echo "      Updating current positions (tickers_current_positions.csv)..."
 ./get_cur_pos_tickers.sh
fi

# Replace odd ticker symbols with their correct versions (e.g., BRK.B -> BRK-B)
sed -i 's/BRK.B/BRK-B/g' "$CUR_POS_TICKERS_FILE"
sed -i 's/BRK.A/BRK-A/g' "$CUR_POS_TICKERS_FILE"

echo
echo "      Combining ticker lists... (tickers_current_positions.csv, tickers_sp_500.csv, tickers_other.csv)"
echo "      Output: tickers_combined.csv"
./combine_sort_tickers.sh
echo

# ==========================================
# EXECUTE STEP 2: FUNDAMENTALS (Labels matched original step references)
# ==========================================
if [[ "$UPDATE_FUNDAMENTALS" == "y" ]]; then
    echo "   1.2 Activating virtual environment and running fundamentals gatherer..."
    source /home/dev/py/.venv/bin/activate
    python ../py/get_financials.py
    deactivate
fi

echo

# ==========================================
# EXECUTE STEP 3: TICKER METADATA
# ==========================================
if [[ "$UPDATE_TICKER_METADATA" == "y" ]]; then
    echo "   1.3 Activating virtual environment and running ticker metadata gatherer..."
    source /home/dev/py/.venv/bin/activate
    python ../py/get_ticker_metadata.py
    deactivate
fi

echo

# ==========================================
# EXECUTE STEP 4: RUN C++ SCANNER
# ==========================================
if [[ "$RUN_CPP_SCANNER" == "y" ]]; then
 echo "   1.4 Running C++ scanner..."
 # change directory and run compiled C++ scanner
 cd ../cpp/bin
 ./buy_opp
 cd "$SCRIPT_DIR_A"
else
 echo "      Skipping C++ scanner."
fi

echo

# SCRIPT 2
# Determine the directory of the script and change to that directory

SCRIPT_DIR_B="/home/dev/stock/intr_value/script"
cd "$SCRIPT_DIR_B"

START_TIME=$(date +%s)

echo
echo "============================================"
echo " Program #2 - Intrinsic Value Scanner"
echo "============================================"
echo

# ------------------------------------------------------------------
# 1. Ticker list
# ------------------------------------------------------------------
echo "   2.1 Copy Ticker list"
echo "      Using: ../data/tickers_combined.csv"
echo "      (You can copy/symlink the one from buy_opp or maintain a separate list)"
echo

# Optional: copy the latest combined list from buy_opp

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

if [[ "$UPDATE_DATA" == "y" || "$UPDATE_DATA" == "Y" ]]; then
    echo "   2.2 Activating virtual environment and running data gatherer..."
    source /home/dev/py/.venv/bin/activate
    python ../py/get_intrinsic_data.py
    deactivate
    echo "      → Data update complete"
else
    echo "      → Skipping data update (using existing fundamentals_intrinsic.csv)"
fi

# ------------------------------------------------------------------
# 3. C++ number crunching
# ------------------------------------------------------------------
echo
echo "   2.3 C++ valuation engine"
if [[ -x ../cpp/bin/intr_value ]]; then
    echo "      Running C++ scanner..."
    cd ../cpp/bin
    ./intr_value
    cd "$SCRIPT_DIR_B"
else
    echo "      → C++ binary not found yet (../cpp/bin/intr_value)"
    echo "         (We will add this in the next step)"
fi

# SCRIPT 3

echo
echo "==============================================="
echo " Program #3 - Data Combination & Report Script"
echo "==============================================="
echo

SCRIPT_DIR_C="/home/dev/stock/intr_buy/script"
cd "$SCRIPT_DIR_C"

START_TIME=$(date +%s)
echo "   Running from: $(pwd)"
echo

# ==========================================
# COLLECT ALL USER CHOICES UP FRONT
# ==========================================
echo
echo "   Starting Processing..."
echo

# Define paths explicitly based on script location
BUY_FILE="$SCRIPT_DIR_C/../../buy_opp/output/summary_all.csv"
INTR_FILE="$SCRIPT_DIR_C/../../intr_value/output/summary_intrinsic.csv"
CPP_PROGRAM="$SCRIPT_DIR_C/../cpp/bin/intr_buy"

# ==========================================
# EXECUTE STEP 1: COPY FILES
# ==========================================
if [[ "$COPY_FILES" == "y" || "$COPY_FILES" == "Y" ]]; then
    echo "   3.1 Checking files for transfer:"
    echo "      BUY_FILE: $BUY_FILE"
    echo "      INTR_FILE: $INTR_FILE"
    echo
    
    if [[ -f "$BUY_FILE" ]]; then echo "   Found: $BUY_FILE"; else echo "   Missing: $BUY_FILE"; fi
    if [[ -f "$INTR_FILE" ]]; then echo "   Found: $INTR_FILE"; else echo "   Missing: $INTR_FILE"; fi
    echo
    
    if [[ -f "$BUY_FILE" && -f "$INTR_FILE" ]]; then
        cp "$BUY_FILE" "$SCRIPT_DIR_C/../data/summary_all.csv"
        cp "$INTR_FILE" "$SCRIPT_DIR_C/../data/summary_intrinsic.csv"
        echo "      Files copied successfully to local data storage."
    else
        echo "      ❌ Error: One or both files do not exist."
        exit 1
    fi
else
    echo "      skipping file copy extraction."
fi

# ==========================================
# EXECUTE STEP 2: RUN C++ COMBINATION ENGINE
# ==========================================
echo
if [[ "$RUN_CPP_COMBINER" == "y" || "$RUN_CPP_COMBINER" == "Y" ]]; then
    echo "   3.2 Running C++ engine to aggregate asset streams..."
    echo "      Running executable: $CPP_PROGRAM"
    if [[ -x "$CPP_PROGRAM" ]]; then
        "$CPP_PROGRAM"
        echo "      → Combiner execution complete."
    else
        echo "      ❌ ERROR: C++ executable not found at $CPP_PROGRAM"
        read -p "   Press Enter to exit..."
        exit 1
    fi
else
    echo "      Skipping C++ dataset amalgamation engine."
fi

# ==========================================
# EXECUTE STEP 3: CREATE REPORT (WITH DEBUG)
# ==========================================
echo
if [[ "$CREATE_REPORT" == "y" || "$CREATE_REPORT" == "Y" ]]; then
    echo "   3.3 Spawning Python interpreter for layout engine..."
    if /usr/bin/python3 "$SCRIPT_DIR_C/../py/create_intr_buy_report.py"; then
        echo "      ✅ Report file structured successfully."
    else
        echo "      ❌ ERROR: Python compilation script failed!"
        read -p "     Press Enter to see details and exit..."
        exit 1
    fi
else
    echo "   3. Skipping spreadsheet file synthesis."
fi

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

echo
echo "   ========================================="
echo "   All three Programs Completed"
echo "   Runtime: ${ELAPSED} seconds"
echo "   Output: output/combined_report.ods"
echo "   ========================================="
echo

# ==========================================
# EXECUTE STEP 4: OPEN LIBREOFFICE (WITH DEBUG)
# ==========================================
echo "4. Attempting standalone engine spawn for LibreOffice..."
if setsid libreoffice "$SCRIPT_DIR_C/../output/combined_report.ods" > /tmp/libreoffice_combined_debug.log 2>&1 & then
    echo "   ✅ LibreOffice background instance initiated."
    sleep 1
    if pgrep -f "combined_report.ods" > /dev/null || pgrep -f "libreoffice" > /dev/null; then
        echo "   Process target localized in operational thread group."
    else
        echo "   ⚠️ WARNING: Launch execution fired but process tree shows missing thread state."
        echo "   Diagnostic stream reads:"
        cat /tmp/libreoffice_combined_debug.log
    fi
else
    echo "   ❌ ERROR: Shell context refused program allocation execution!"
    read -p "Press Enter to close window..."
    exit 1
fi

echo
echo "=== DEBUG PAUSE ==="
echo "The script run has successfully finished processing data sets."
read -p "Press Enter to terminate this window shell and ensure visual report remains painted..."
