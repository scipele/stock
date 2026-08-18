#!/bin/bash
# SCRIPT 1 – Master orchestrator for Buy Opp + Intrinsic Value + Combined Report

set -e
CUR_POS_TICKERS_FILE="../data/tickers_current_positions.csv"

# Determine the directory of the script and change to that directory
SCRIPT_DIR_A="/home/dev/stock/buy_opp/script"
cd "$SCRIPT_DIR_A"

# ==========================================
# GENERAL QUESTIONS FOR ALL THREE PROGRAMS
# ==========================================
echo "====================================================================================="
echo " Gather User Input for All Three Programs"
echo "====================================================================================="
echo

echo "   ================== Program #1 - Buy Opportunity Questions ======================="
read -p "   1.1  Update the current positions (recom daily)? (y/n) " UPDATE_CUR_POSITIONS
read -p "   1.1b Include S&P 500 tickers? (y/n) " INCLUDE_SP500
read -p "   1.1c Include Russell 2000 tickers? (y/n) " INCLUDE_RUSSELL
read -p "   1.1d Include 'other' tickers? (y/n) " INCLUDE_OTHER
read -p "   1.1e Include recent top-score tickers? (y/n) " INCLUDE_TOP_SCORES
read -p "   1.2  Update fundamentals (recom daily)? (y/n) " UPDATE_FUNDAMENTALS
read -p "   1.3  Update Ticker Metadata (recom monthly)? (y/n) " UPDATE_TICKER_METADATA
read -p "   1.4  Run the C++ scanner? (y/n) " RUN_CPP_SCANNER
echo
echo "   ================== Program #2 - Intrinsic Value Questions ======================="
read -p "   2.1  Copy latest tickers_combined.csv from buy_opp? (y/n) " COPY_TICKERS
read -p "   2.2  Update intrinsic-value data (recom daily/weekly)? (y/n) " UPDATE_DATA
echo
echo "   ================== Program #3 - Data Combination & Report  ======================"
read -p "   3.1  Copy files from the other programs? (y/n): " COPY_FILES
read -p "   3.2  Run the C++ program to combine the files? (y/n): " RUN_CPP_COMBINER
read -p "   3.3  Create the LibreOffice report? (y/n): " CREATE_REPORT

# Convert all user input to lowercase for consistency
UPDATE_CUR_POSITIONS="${UPDATE_CUR_POSITIONS,,}"
INCLUDE_SP500="${INCLUDE_SP500,,}"
INCLUDE_RUSSELL="${INCLUDE_RUSSELL,,}"
INCLUDE_OTHER="${INCLUDE_OTHER,,}"
INCLUDE_TOP_SCORES="${INCLUDE_TOP_SCORES,,}"
UPDATE_FUNDAMENTALS="${UPDATE_FUNDAMENTALS,,}"
UPDATE_TICKER_METADATA="${UPDATE_TICKER_METADATA,,}"
RUN_CPP_SCANNER="${RUN_CPP_SCANNER,,}"
COPY_TICKERS="${COPY_TICKERS,,}"
UPDATE_DATA="${UPDATE_DATA,,}"
COPY_FILES="${COPY_FILES,,}"
RUN_CPP_COMBINER="${RUN_CPP_COMBINER,,}"
CREATE_REPORT="${CREATE_REPORT,,}"

START_TIME=$(date +%s)

echo
echo "============================================"
echo " Program #1 - Stock Buy Opportunity Scanner"
echo "============================================"
echo

# ==========================================
# 1.1 CURRENT POSITIONS
# ==========================================
echo "1.1  Current Positions"
if [[ "$UPDATE_CUR_POSITIONS" == "y" ]]; then
    echo "     → Updating current positions (tickers_current_positions.csv)..."
    ./get_cur_pos_tickers.sh
else
    echo "     → Skipping update of current positions."
fi

# Replace odd ticker symbols with their correct versions (e.g., BRK.B -> BRK-B)
sed -i 's/BRK.B/BRK-B/g' "$CUR_POS_TICKERS_FILE"
sed -i 's/BRK.A/BRK-A/g' "$CUR_POS_TICKERS_FILE"
echo

# ==========================================
# 1.1b–1.1e COMBINE TICKER LISTS
# ==========================================
echo "1.1b–1.1e  Combining ticker lists..."
echo "           tickers_current_positions.csv (always included)"
[[ "$INCLUDE_SP500"     == "y" ]] && echo "           1.1b  tickers_sp_500.csv"
[[ "$INCLUDE_RUSSELL"    == "y" ]] && echo "           1.1c  tickers_russel_2k.csv"
[[ "$INCLUDE_OTHER"      == "y" ]] && echo "           1.1d  tickers_other.csv"
[[ "$INCLUDE_TOP_SCORES" == "y" ]] && echo "           1.1e  tickers_recent_top_scores.csv"
echo "           → Output: tickers_combined.csv"
./combine_sort_tickers.sh "$INCLUDE_SP500" "$INCLUDE_RUSSELL" "$INCLUDE_OTHER" "$INCLUDE_TOP_SCORES"
echo

# ==========================================
# 1.2 FUNDAMENTALS
# ==========================================
echo "1.2  Fundamentals"
if [[ "$UPDATE_FUNDAMENTALS" == "y" ]]; then
    echo "     → Activating virtual environment and running fundamentals gatherer..."
    source /home/dev/py/.venv/bin/activate
    python ../py/get_financials.py
    deactivate
else
    echo "     → Skipping fundamentals update."
fi
echo

# ==========================================
# 1.3 TICKER METADATA
# ==========================================
echo "1.3  Ticker Metadata"
if [[ "$UPDATE_TICKER_METADATA" == "y" ]]; then
    echo "     → Activating virtual environment and running ticker metadata gatherer..."
    source /home/dev/py/.venv/bin/activate
    python ../py/get_ticker_metadata.py
    deactivate
else
    echo "     → Skipping ticker metadata update."
fi
echo

# ==========================================
# 1.4 C++ SCANNER
# ==========================================
echo "1.4  C++ Scanner"
if [[ "$RUN_CPP_SCANNER" == "y" ]]; then
    echo "     → Running C++ scanner..."
    cd ../cpp/bin
    ./buy_opp
    cd "$SCRIPT_DIR_A"
else
    echo "     → Skipping C++ scanner."
fi
echo

# ==========================================
# PROGRAM #2 – Intrinsic Value
# ==========================================
SCRIPT_DIR_B="/home/dev/stock/intr_value/script"
cd "$SCRIPT_DIR_B"

echo
echo "============================================"
echo " Program #2 - Intrinsic Value Scanner"
echo "============================================"
echo

# ------------------------------------------------------------------
# 2.1 Ticker list
# ------------------------------------------------------------------
echo "2.1  Copy Ticker list"
echo "     Using: ../data/tickers_combined.csv"
if [[ "$COPY_TICKERS" == "y" ]]; then
    if [[ -f /home/dev/stock/buy_opp/data/tickers_combined.csv ]]; then
        cp /home/dev/stock/buy_opp/data/tickers_combined.csv ../data/tickers_combined.csv
        echo "     → Copied successfully from buy_opp"
    else
        echo "     → WARNING: buy_opp tickers_combined.csv not found"
    fi
else
    echo "     → Skipping copy (using existing list)"
fi

# Fix common Yahoo symbol differences
if [[ -f ../data/tickers_combined.csv ]]; then
    sed -i 's/BRK.B/BRK-B/g' ../data/tickers_combined.csv
    sed -i 's/BRK.A/BRK-A/g' ../data/tickers_combined.csv
fi
echo

# ------------------------------------------------------------------
# 2.2 Update fundamental / valuation data
# ------------------------------------------------------------------
echo "2.2  Intrinsic-value data update"
if [[ "$UPDATE_DATA" == "y" ]]; then
    echo "     → Activating virtual environment and running data gatherer..."
    source /home/dev/py/.venv/bin/activate
    python ../py/get_intrinsic_data.py
    deactivate
    echo "     → Data update complete"
else
    echo "     → Skipping data update (using existing fundamentals_intrinsic.csv)"
fi
echo

# ------------------------------------------------------------------
# 2.3 C++ number crunching
# ------------------------------------------------------------------
echo "2.3  C++ valuation engine"
if [[ -x ../cpp/bin/intr_value ]]; then
    echo "     → Running C++ scanner..."
    cd ../cpp/bin
    ./intr_value
    cd "$SCRIPT_DIR_B"
else
    echo "     → C++ binary not found yet (../cpp/bin/intr_value)"
fi
echo

# ==========================================
# PROGRAM #3 – Data Combination & Report
# ==========================================
echo
echo "==============================================="
echo " Program #3 - Data Combination & Report Script"
echo "==============================================="
echo

SCRIPT_DIR_C="/home/dev/stock/intr_buy/script"
cd "$SCRIPT_DIR_C"

echo "   Running from: $(pwd)"
echo

# Define paths explicitly based on script location
BUY_FILE="$SCRIPT_DIR_C/../../buy_opp/output/summary_all.csv"
INTR_FILE="$SCRIPT_DIR_C/../../intr_value/output/summary_intrinsic.csv"
CPP_PROGRAM="$SCRIPT_DIR_C/../cpp/bin/intr_buy"

# ==========================================
# 3.1 COPY FILES
# ==========================================
echo "3.1  Copy files from other programs"
if [[ "$COPY_FILES" == "y" ]]; then
    echo "     Checking files for transfer:"
    echo "       BUY_FILE : $BUY_FILE"
    echo "       INTR_FILE: $INTR_FILE"
    echo

    if [[ -f "$BUY_FILE" ]]; then echo "       Found: $BUY_FILE"; else echo "       Missing: $BUY_FILE"; fi
    if [[ -f "$INTR_FILE" ]]; then echo "       Found: $INTR_FILE"; else echo "       Missing: $INTR_FILE"; fi
    echo

    if [[ -f "$BUY_FILE" && -f "$INTR_FILE" ]]; then
        cp "$BUY_FILE"  "$SCRIPT_DIR_C/../data/summary_all.csv"
        cp "$INTR_FILE" "$SCRIPT_DIR_C/../data/summary_intrinsic.csv"
        echo "     → Files copied successfully to local data storage."
    else
        echo "     ❌ Error: One or both files do not exist."
        exit 1
    fi
else
    echo "     → Skipping file copy."
fi
echo

# ==========================================
# 3.2 RUN C++ COMBINER
# ==========================================
echo "3.2  C++ combination engine"
if [[ "$RUN_CPP_COMBINER" == "y" ]]; then
    echo "     → Running executable: $CPP_PROGRAM"
    if [[ -x "$CPP_PROGRAM" ]]; then
        "$CPP_PROGRAM"
        echo "     → Combiner execution complete."
    else
        echo "     ❌ ERROR: C++ executable not found at $CPP_PROGRAM"
        read -p "        Press Enter to exit..."
        exit 1
    fi
else
    echo "     → Skipping C++ dataset amalgamation engine."
fi
echo

# ==========================================
# 3.3 CREATE REPORT
# ==========================================
echo "3.3  LibreOffice report"
if [[ "$CREATE_REPORT" == "y" ]]; then
    echo "     → Spawning Python interpreter for layout engine..."
    if /usr/bin/python3 "$SCRIPT_DIR_C/../py/create_intr_buy_report.py"; then
        echo "     ✅ Report file structured successfully."
    else
        echo "     ❌ ERROR: Python compilation script failed!"
        read -p "        Press Enter to see details and exit..."
        exit 1
    fi
else
    echo "     → Skipping spreadsheet file synthesis."
fi

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

echo
echo "========================================="
echo " All three Programs Completed"
echo " Runtime: ${ELAPSED} seconds"
echo " Output: output/combined_report.ods"
echo "========================================="
echo

# ==========================================
# 4. OPEN LIBREOFFICE
# ==========================================
echo "4.  Opening report in LibreOffice..."
if setsid libreoffice "$SCRIPT_DIR_C/../output/combined_report.ods" > /tmp/libreoffice_combined_debug.log 2>&1 & then
    echo "     ✅ LibreOffice background instance initiated."
    sleep 1
    if pgrep -f "combined_report.ods" > /dev/null || pgrep -f "libreoffice" > /dev/null; then
        echo "     Process target localized in operational thread group."
    else
        echo "     ⚠️  WARNING: Launch execution fired but process tree shows missing thread state."
        echo "     Diagnostic stream reads:"
        cat /tmp/libreoffice_combined_debug.log
    fi
else
    echo "     ❌ ERROR: Shell context refused program allocation execution!"
    read -p "Press Enter to close window..."
    exit 1
fi

echo
echo "=== DEBUG PAUSE ==="
echo "The script run has successfully finished processing data sets."
read -p "Press Enter to terminate this window shell and ensure visual report remains painted..."