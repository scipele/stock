#!/bin/bash
# Launch previously generated Intrinsic Buy report
# Does NOT rerun any programs or regenerate the report.

set -e

# Resolve project paths dynamically
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPORT_FILE="$SCRIPT_DIR/../output/combined_report.ods"

# Verify report exists
if [[ ! -f "$REPORT_FILE" ]]; then
    echo "ERROR: Report not found:"
    echo "  $REPORT_FILE"
    read -p "Press Enter to exit..."
    exit 1
fi

# Open existing report in LibreOffice
echo "Opening existing report in LibreOffice..."
libreoffice "$REPORT_FILE" >/tmp/libreoffice_combined_debug.log 2>&1 &

# press Enter to exit the script after opening the report
read -p "Press Enter to exit..."