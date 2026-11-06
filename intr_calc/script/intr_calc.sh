
#!/bin/bash

# Run the Alpha stock data parser and open the ODS output.

set -e

ROOT_DIR="/home/dev/stock/intr_calc"
PYTHON="/home/dev/py/.venv/bin/python"
PYTHON_SCRIPT="$ROOT_DIR/py/intr_calc.py"


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

# Run the program.
"$PYTHON" "$PYTHON_SCRIPT"

