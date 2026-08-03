#!/bin/bash
set -e

SCRIPT_PATH=$(dirname "$(realpath "$0")")
cd "$SCRIPT_PATH"

START_TIME=$(date +%s)

echo "======================================"
echo "    Data Combination & Report Script"
echo "======================================"
echo "Running from: $(pwd)"
echo

# ==========================================
# COLLECT ALL USER CHOICES UP FRONT
# ==========================================
read -p "1. Would you like to copy files from the other programs? (y/n): " COPY_FILES
read -p "2. Would you like to run the C++ program to combine the files? (y/n): " RUN_CPP_COMBINER
read -p "3. Would you like to create the LibreOffice report? (y/n): " CREATE_REPORT
echo
echo "======================================"
echo " Starting Processing..."
echo "======================================"
echo

# Define paths explicitly based on script location
BUY_FILE="$SCRIPT_PATH/../../buy_opp/output/summary_all.csv"
INTR_FILE="$SCRIPT_PATH/../../intr_value/output/summary_intrinsic.csv"
CPP_PROGRAM="$SCRIPT_PATH/../cpp/bin/intr_buy"

# ==========================================
# EXECUTE STEP 1: COPY FILES
# ==========================================
if [[ "$COPY_FILES" == "y" || "$COPY_FILES" == "Y" ]]; then
    echo "1. Checking files for transfer:"
    echo "   BUY_FILE: $BUY_FILE"
    echo "   INTR_FILE: $INTR_FILE"
    echo
    
    if [[ -f "$BUY_FILE" ]]; then echo "   Found: $BUY_FILE"; else echo "   Missing: $BUY_FILE"; fi
    if [[ -f "$INTR_FILE" ]]; then echo "   Found: $INTR_FILE"; else echo "   Missing: $INTR_FILE"; fi
    echo
    
    if [[ -f "$BUY_FILE" && -f "$INTR_FILE" ]]; then
        cp "$BUY_FILE" "$SCRIPT_PATH/../data/summary_all.csv"
        cp "$INTR_FILE" "$SCRIPT_PATH/../data/summary_intrinsic.csv"
        echo "   Files copied successfully to local data storage."
    else
        echo "   ❌ Error: One or both files do not exist."
        read -p "Press Enter to exit..."
        exit 1
    fi
else
    echo "1. Skipping file copy extraction."
fi

# ==========================================
# EXECUTE STEP 2: RUN C++ COMBINATION ENGINE
# ==========================================
echo
if [[ "$RUN_CPP_COMBINER" == "y" || "$RUN_CPP_COMBINER" == "Y" ]]; then
    echo "2. Running C++ engine to aggregate asset streams..."
    echo "   Running executable: $CPP_PROGRAM"
    if [[ -x "$CPP_PROGRAM" ]]; then
        "$CPP_PROGRAM"
        echo "   → Combiner execution complete."
    else
        echo "   ❌ ERROR: C++ executable not found at $CPP_PROGRAM"
        read -p "Press Enter to exit..."
        exit 1
    fi
else
    echo "2. Skipping C++ dataset amalgamation engine."
fi

# ==========================================
# EXECUTE STEP 3: CREATE REPORT (WITH DEBUG)
# ==========================================
echo
if [[ "$CREATE_REPORT" == "y" || "$CREATE_REPORT" == "Y" ]]; then
    echo "3. Spawning Python interpreter for layout engine..."
    if /usr/bin/python3 "$SCRIPT_PATH/../py/create_intr_buy_report.py"; then
        echo "   ✅ Report file structured successfully."
    else
        echo "   ❌ ERROR: Python compilation script failed!"
        read -p "Press Enter to see details and exit..."
        exit 1
    fi
else
    echo "3. Skipping spreadsheet file synthesis."
fi

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

echo
echo " ======================================"
echo " Complete"
echo " Runtime: ${ELAPSED} seconds"
echo " Output: output/combined_report.ods"
echo " ======================================"
echo

# ==========================================
# EXECUTE STEP 4: OPEN LIBREOFFICE (WITH DEBUG)
# ==========================================
echo "4. Attempting standalone engine spawn for LibreOffice..."
if setsid libreoffice "$SCRIPT_PATH/../output/combined_report.ods" > /tmp/libreoffice_combined_debug.log 2>&1 & then
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
