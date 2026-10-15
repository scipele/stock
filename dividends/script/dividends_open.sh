#!/bin/bash
# SCRIPT: Dividend & Stability Screening Orchestrator

set -e

# Resolve paths dynamically relative to script execution directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
OUTPUT_SPREADSHEET="$PROJECT_ROOT/output/dividend_analysis.xlsx"


# Launch LibreOffice Calc automatically
if [[ -f "$OUTPUT_SPREADSHEET" ]]; then
    echo "     → Launching LibreOffice Calc with AutoFilters active..."
    localc "$OUTPUT_SPREADSHEET" & 2>/dev/null
else
    echo "   [Error] Could not launch LibreOffice: Output spreadsheet file not found."
fi
echo

# Prevent terminal from immediately window closing
read -p "Execution complete. Press any key to close terminal..." -n1 -s
echo
