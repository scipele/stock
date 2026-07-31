# Determine the directory of the script and change to that directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "Opening script directory: $SCRIPT_DIR"
echo "Opening report in LibreOffice"

libreoffice ../output/summary_all.ods >/dev/null 2>&1 &
