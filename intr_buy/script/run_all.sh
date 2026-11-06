
#!/bin/bash
# SCRIPT 1 – Master orchestrator for Buy Opp + Intrinsic Value + Combined Report

set -e

# Use one explicit project root and absolute paths throughout.
PROJECT_ROOT="/home/dev/stock"

BUY_OPP_DIR="$PROJECT_ROOT/buy_opp"
INTR_VALUE_DIR="$PROJECT_ROOT/intr_value"
INTR_BUY_DIR="$PROJECT_ROOT/intr_buy"

BUY_SCRIPT_DIR="$BUY_OPP_DIR/script"
INTR_VALUE_SCRIPT_DIR="$INTR_VALUE_DIR/script"
INTR_BUY_SCRIPT_DIR="$INTR_BUY_DIR/script"

CUR_POS_TICKERS_FILE="$BUY_OPP_DIR/data/tickers_current_positions.csv"
COMBINED_TICKERS_FILE="$BUY_OPP_DIR/data/tickers_combined.csv"
INTR_TICKERS_FILE="$INTR_VALUE_DIR/data/tickers_combined.csv"

BUY_FUNDAMENTALS_SCRIPT="$BUY_OPP_DIR/py/get_financials.py"
BUY_METADATA_SCRIPT="$BUY_OPP_DIR/py/get_ticker_metadata.py"
BUY_SCANNER="$BUY_OPP_DIR/cpp/bin/buy_opp"
INTR_DATA_SCRIPT="$INTR_VALUE_DIR/py/get_intrinsic_data.py"
INTR_SCANNER="$INTR_VALUE_DIR/cpp/bin/intr_value"
COMBINER="$INTR_BUY_DIR/cpp/bin/intr_buy"
REPORT_SCRIPT="$INTR_BUY_DIR/py/create_intr_buy_report.py"

BUY_SUMMARY="$BUY_OPP_DIR/output/summary_all.csv"
INTR_SUMMARY="$INTR_VALUE_DIR/output/summary_intrinsic.csv"
COMBINED_REPORT="$INTR_BUY_DIR/output/combined_report.ods"

cd "$BUY_SCRIPT_DIR"

# ==========================================
# GENERAL QUESTIONS FOR ALL THREE PROGRAMS
# ==========================================
echo "====================================================================================="
echo " Gather User Input for All Three Programs"
echo "====================================================================================="
echo

echo "   ================== Program #1 - Buy Opportunity Questions ======================="

read -p "   1.1  Include current positions? (y/n) " INCLUDE_CUR_POSITIONS
read -p "   1.1a Include Dow tickers? (y/n) " INCLUDE_DOW
read -p "   1.1b Include S&P 500 tickers? (y/n) " INCLUDE_SP500
read -p "   1.1c Include Russell 2000 tickers? (y/n) " INCLUDE_RUSSELL
read -p "   1.1d Include 'other' tickers? (y/n) " INCLUDE_OTHER
read -p "   1.1e Include recent top-score tickers? (y/n) " INCLUDE_TOP_SCORES

# Convert all user input to lowercase
INCLUDE_CUR_POSITIONS="${INCLUDE_CUR_POSITIONS,,}"
INCLUDE_DOW="${INCLUDE_DOW,,}"
INCLUDE_SP500="${INCLUDE_SP500,,}"
INCLUDE_RUSSELL="${INCLUDE_RUSSELL,,}"
INCLUDE_OTHER="${INCLUDE_OTHER,,}"
INCLUDE_TOP_SCORES="${INCLUDE_TOP_SCORES,,}"

# ==========================================
# HARDCODED INPUTS FOR 1.2 AND AFTER (AUTO-YES)
# ==========================================
UPDATE_FUNDAMENTALS="y"
UPDATE_TICKER_METADATA="y"
RUN_CPP_SCANNER="y"

# Program #2 Variables
COPY_TICKERS="y"
UPDATE_DATA="y"

# Program #3 Variables
COPY_FILES="y"
RUN_CPP_COMBINER="y"
CREATE_REPORT="y"

START_TIME=$(date +%s)

echo
echo "============================================"
echo " Program #1 - Stock Buy Opportunity Scanner"
echo "============================================"
echo

# ==========================================
# 1.1 CURRENT POSITIONS
# ==========================================
echo "   1.1  Current Positions"

if [[ "$INCLUDE_CUR_POSITIONS" == "y" ]]; then
    echo "     → Updating current positions..."

    "$BUY_SCRIPT_DIR/get_cur_pos_tickers.sh"

    # Fix common Yahoo Finance symbol differences
    if [[ -f "$CUR_POS_TICKERS_FILE" ]]; then
        sed -i 's/BRK\.B/BRK-B/g' "$CUR_POS_TICKERS_FILE"
        sed -i 's/BRK\.A/BRK-A/g' "$CUR_POS_TICKERS_FILE"
    else
        echo "     ERROR: Current positions file was not created."
        exit 1
    fi
else
    echo "     → Skipping current positions update."
    echo "     → Current positions will be excluded from the scan."
fi

echo

# ==========================================
# 1.1a–1.1e COMBINE TICKER LISTS
# ==========================================
echo "   1.1a–1.1e  Combining ticker lists..."

[[ "$INCLUDE_CUR_POSITIONS" == "y" ]] && echo "           Current positions: INCLUDED"
[[ "$INCLUDE_CUR_POSITIONS" != "y" ]] && echo "           Current positions: EXCLUDED"
[[ "$INCLUDE_DOW"            == "y" ]] && echo "           1.1a  tickers_dow.csv"
[[ "$INCLUDE_SP500"          == "y" ]] && echo "           1.1b  tickers_sp_500.csv"
[[ "$INCLUDE_RUSSELL"        == "y" ]] && echo "           1.1c  tickers_russel_2k.csv"
[[ "$INCLUDE_OTHER"          == "y" ]] && echo "           1.1d  tickers_other.csv"
[[ "$INCLUDE_TOP_SCORES"     == "y" ]] && echo "           1.1e  tickers_recent_top_scores.csv"

echo "           → Output: tickers_combined.csv"

# Sixth argument controls inclusion of current positions
"$BUY_SCRIPT_DIR/combine_sort_tickers.sh" \
    "$INCLUDE_DOW" \
    "$INCLUDE_SP500" \
    "$INCLUDE_RUSSELL" \
    "$INCLUDE_OTHER" \
    "$INCLUDE_TOP_SCORES" \
    "$INCLUDE_CUR_POSITIONS"

echo

# ==========================================
# 1.2 FUNDAMENTALS
# ==========================================
echo "1.2  Buy Opportunity Fundamentals"

if [[ "$UPDATE_FUNDAMENTALS" == "y" ]]; then
    echo "     → Activating virtual environment and running fundamentals gatherer..."
    echo "     Python program: $BUY_FUNDAMENTALS_SCRIPT"
    source /home/dev/py/.venv/bin/activate
    python "$BUY_FUNDAMENTALS_SCRIPT"
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
    python "$BUY_METADATA_SCRIPT"
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
    echo "     → Running C++ scanner: $BUY_SCANNER"
    cd "$BUY_OPP_DIR/cpp/bin"
    "$BUY_SCANNER"
    cd "$BUY_SCRIPT_DIR"
else
    echo "     → Skipping C++ scanner."
fi

echo

# ==========================================
# PROGRAM #2 – INTRINSIC VALUE
# ==========================================
cd "$INTR_VALUE_SCRIPT_DIR"

echo
echo "============================================"
echo " Program #2 - Intrinsic Value Scanner"
echo "============================================"
echo

# ------------------------------------------------------------------
# 2.0 Update Intrinsic-value fundamentals / valuation data (Python)
# ------------------------------------------------------------------
echo

# ------------------------------------------
# 2.1 COPY TICKER LIST
# ------------------------------------------
echo "2.1  Copy Ticker List"
echo "     Using: $INTR_TICKERS_FILE"

if [[ "$COPY_TICKERS" == "y" ]]; then
    if [[ -f "$COMBINED_TICKERS_FILE" ]]; then
        cp "$COMBINED_TICKERS_FILE" "$INTR_TICKERS_FILE"
        echo "     → Copied successfully from buy_opp to"
        echo "     → Full path: $INTR_TICKERS_FILE"
    else
        echo "     ERROR: buy_opp tickers_combined.csv not found"
        exit 1
    fi
else
    echo "     → Skipping copy (using existing list)"
fi

# Fix common Yahoo Finance symbol differences
if [[ -f "$INTR_TICKERS_FILE" ]]; then
    sed -i 's/BRK\.B/BRK-B/g' "$INTR_TICKERS_FILE"
    sed -i 's/BRK\.A/BRK-A/g' "$INTR_TICKERS_FILE"
fi

echo

# ------------------------------------------
# 2.2 UPDATE FUNDAMENTAL / VALUATION DATA
# ------------------------------------------
echo "2.2  Intrinsic-value data update"

if [[ "$UPDATE_DATA" == "y" ]]; then
    echo "     → Activating virtual environment and running data gatherer..."
    echo "     → Python program: $INTR_DATA_SCRIPT"
    source /home/dev/py/.venv/bin/activate
    python "$INTR_DATA_SCRIPT"
    deactivate
    echo "     program output: "
    echo "     → Full path: $INTR_SUMMARY"
    echo "     → Data update complete"
else
    echo "     → Skipping data update (using existing fundamentals_intrinsic.csv)"
fi

echo

# ------------------------------------------
# 2.3 C++ VALUATION ENGINE
# ------------------------------------------
echo "2.3  C++ valuation engine"

if [[ -x "$INTR_SCANNER" ]]; then
    echo "     → Running C++ scanner: $INTR_SCANNER"
    cd "$INTR_VALUE_DIR/cpp/bin"
    "$INTR_SCANNER"
    cd "$INTR_VALUE_SCRIPT_DIR"
else
    echo "     ERROR: C++ binary not found or not executable: $INTR_SCANNER"
    exit 1
fi

echo

# ==========================================
# PROGRAM #3 – DATA COMBINATION & REPORT
# ==========================================
echo
echo "==============================================="
echo " Program #3 - Data Combination & Report Script"
echo "==============================================="
echo

cd "$INTR_BUY_SCRIPT_DIR"

echo "     Running from: $(pwd)"
echo

# Define paths explicitly
BUY_FILE="$BUY_SUMMARY"
INTR_FILE="$INTR_SUMMARY"
CPP_PROGRAM="$COMBINER"

# ==========================================
# 3.1 COPY FILES
# ==========================================
echo "3.1  Copy files from other programs"

if [[ "$COPY_FILES" == "y" ]]; then
    echo "     Checking files for transfer:"
    echo "       BUY_FILE : $BUY_FILE"
    echo "       INTR_FILE: $INTR_FILE"
    echo

    if [[ -f "$BUY_FILE" ]]; then
        echo "       Found: $BUY_FILE"
    else
        echo "       Missing: $BUY_FILE"
    fi

    if [[ -f "$INTR_FILE" ]]; then
        echo "       Found: $INTR_FILE"
    else
        echo "       Missing: $INTR_FILE"
    fi

    echo

    if [[ -f "$BUY_FILE" && -f "$INTR_FILE" ]]; then
        cp "$BUY_FILE" "$INTR_BUY_DIR/data/summary_all.csv"
        cp "$INTR_FILE" "$INTR_BUY_DIR/data/summary_intrinsic.csv"
        echo "     → Files copied successfully to local data storage."
    else
        echo "     ERROR: One or both input files do not exist."
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
        echo "     ERROR: C++ executable not found at $CPP_PROGRAM"
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
    echo "     → Running Python report layout engine..."

    if /usr/bin/python3 "$REPORT_SCRIPT"; then
        echo "     Report file structured successfully."
    else
        echo "     ERROR: Python report script failed!"
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
echo " All three programs completed"
echo " Runtime: ${ELAPSED} seconds"
echo " Output: $COMBINED_REPORT"
echo "========================================="
echo

# ==========================================
# 4. OPEN LIBREOFFICE
# ==========================================
if [[ "$CREATE_REPORT" == "y" ]]; then
    REPORT_FILE="$COMBINED_REPORT"

    echo "4.  Opening report in LibreOffice..."

    if [[ ! -f "$REPORT_FILE" ]]; then
        echo "     WARNING: Report file not found at: $REPORT_FILE"
        echo "     Skipping auto-open step."
        exit 0
    fi

    if setsid libreoffice "$REPORT_FILE" \
        > /tmp/libreoffice_combined_debug.log 2>&1 & then

        echo "     LibreOffice background instance initiated."
        sleep 1

        if pgrep -f "combined_report.ods" > /dev/null ||
           pgrep -f "libreoffice" > /dev/null; then
            echo "     LibreOffice process detected."
        else
            echo "     WARNING: LibreOffice process was not detected."
            cat /tmp/libreoffice_combined_debug.log
        fi
    else
        echo "     ERROR: Unable to launch LibreOffice."
        exit 1
    fi
else
    echo "4.  Skipping LibreOffice open (report creation was skipped)."
fi

read -p "Press Enter to exit..."