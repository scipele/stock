#!/bin/bash

SCRIPT_PATH=$(dirname "$(realpath "$0")")

cd "$SCRIPT_PATH"

echo "Running from:"
pwd

read -p "1. Would you like to copy files from the other programs to be combined with this program? (y/n): " copy_files

if [[ "$copy_files" == "y" ]]; then

    echo "   Copying files from other programs..."

    BUY_FILE="../../buy_opp/output/summary_all.csv"
    INTR_FILE="../../intr_value/output/summary_intrinsic.csv"
    CPP_PROGRAM="../cpp/bin/intr_buy"

    echo
    echo "   Checking files:"
    echo "   BUY_FILE:  $BUY_FILE"
    echo "   INTR_FILE: $INTR_FILE"
    echo

    if [[ -f "$BUY_FILE" ]]; then
        echo "   Found: $BUY_FILE"
    else
        echo "   Missing: $BUY_FILE"
    fi

    if [[ -f "$INTR_FILE" ]]; then
        echo "   Found: $INTR_FILE"
    else
        echo "   Missing: $INTR_FILE"
    fi

    echo

    if [[ -f "$BUY_FILE" && -f "$INTR_FILE" ]]; then

        cp "$BUY_FILE" ../data/summary_all.csv
        cp "$INTR_FILE" ../data/summary_intrinsic.csv

        echo "   Files copied successfully."

    else

        echo "   Error: One or both files do not exist."
        exit 1

    fi

else
    echo "   Skipping file copy."
fi

echo "2. Run the c++ program to combine the files"
echo
# Run the c++ program to combine the files
echo "   Running: $CPP_PROGRAM" 
"$CPP_PROGRAM"


# ------------------------------------------------------------------
# Create LibreOffice report
# ------------------------------------------------------------------

echo
echo "3. Creating LibreOffice report..."
/usr/bin/python3 ../py/create_intr_buy_report.py


echo
echo "4. Opening report in LibreOffice..."

libreoffice ../output/combined_report.ods >/dev/null 2>&1 &

read -p "Press any key to continue..." -n1 -s