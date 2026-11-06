
#!/bin/bash

# Run the Alpha stock data parser and open the ODS output.

set -e

ROOT_DIR="/home/dev/stock/alpha"
PYTHON="/home/dev/py/.venv/bin/python"
PYTHON_SCRIPT="$ROOT_DIR/py/parse.py"
INPUT_FILE="$ROOT_DIR/input/data.csv"
OUTPUT_DIR="$ROOT_DIR/output"
ODS_FILE="$OUTPUT_DIR/parsed_data.ods"

echo "========================================"
echo " Alpha Stock Data Parser"
echo "========================================"

if [ ! -f "$INPUT_FILE" ]; then
    echo "ERROR: Input file not found:"
    echo "  $INPUT_FILE"
    exit 1
fi

if [ ! -x "$PYTHON" ]; then
    echo "ERROR: Python interpreter not found:"
    echo "  $PYTHON"
    exit 1
fi

if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "ERROR: Python script not found:"
    echo "  $PYTHON_SCRIPT"
    exit 1
fi

if ! "$PYTHON" -c "import odf" 2>/dev/null; then
    echo "ERROR: odfpy is not installed."
    echo "Install with:"
    echo "  $PYTHON -m pip install odfpy"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

# Run the parser.
"$PYTHON" "$PYTHON_SCRIPT"

# Confirm the ODS file was created.
if [ ! -f "$ODS_FILE" ]; then
    echo "ERROR: ODS output was not created:"
    echo "  $ODS_FILE"
    exit 1
fi

echo "========================================"
echo "Parsing completed successfully."
echo "Launching LibreOffice..."
echo "========================================"

# Open the generated spreadsheet.
if command -v libreoffice >/dev/null 2>&1; then
    libreoffice "$ODS_FILE" >/dev/null 2>&1 &
else
    echo "ERROR: LibreOffice was not found in PATH."
    exit 1
fi

echo "Opened: $ODS_FILE"
echo "========================================"
