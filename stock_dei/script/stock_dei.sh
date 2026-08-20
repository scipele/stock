#!/bin/bash
set -e

SCRIPT_PATH=$(dirname "$(realpath "$0")")
PROJECT_PATH=$(realpath "$SCRIPT_PATH/..")

PYTHON_BIN="/usr/bin/python3"
VENV_ACTIVATE="/home/dev/py/.venv/bin/activate"

if [[ -f "$VENV_ACTIVATE" ]]; then
    source "$VENV_ACTIVATE"
    PYTHON_BIN="python"
fi

echo "======================================"
echo "    Stock Sector Diagram Runner"
echo "======================================"
echo "Running from: $(pwd)"
echo
echo "Using Python: $PYTHON_BIN"
echo "Renderer: $PROJECT_PATH/py/stock_dei_render.py"
echo

if "$PYTHON_BIN" "$PROJECT_PATH/py/stock_dei_render.py"; then
    echo
    echo "✅ Diagram generated successfully."
    echo "   SVG : $PROJECT_PATH/output/stock_dei.svg"
    echo "   HTML: $PROJECT_PATH/output/stock_dei.html"

    if command -v xdg-open >/dev/null 2>&1; then
        echo "   Launching generated diagram..."
        xdg-open "$PROJECT_PATH/output/stock_dei.html" >/dev/null 2>&1 &
    elif command -v open >/dev/null 2>&1; then
        echo "   Launching generated diagram..."
        open "$PROJECT_PATH/output/stock_dei.html" >/dev/null 2>&1 &
    else
        echo "   ⚠️ No desktop opener found; open $PROJECT_PATH/output/stock_dei.html manually."
    fi
else
    echo
    echo "❌ ERROR: Diagram generation failed."
    exit 1
fi